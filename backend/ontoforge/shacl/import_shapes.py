"""Import SHACL (graphe RDF) → ShapesModel.

Couvre SHACL Core complet :
- cibles explicites (targetClass / targetNode / targetSubjectsOf / targetObjectsOf) et implicites
  (shape qui est aussi une rdfs:Class ou owl:Class → son IRI est ajoutée à `targets.target_class`) ;
- node shapes et property shapes, imbriquées (sh:property) ou autonomes (référencées par sh:node,
  sh:and/or/xone/not, sh:qualifiedValueShape, ou déclarées seules) ;
- tous les chemins (prédicat, inverse, séquence, alternative, zeroOrMore, oneOrMore, zeroOrOne) ;
- listes RDF (sh:in, sh:languageIn, sh:ignoredProperties, sh:and/or/xone) ;
- contraintes de valeur, cardinalité, plage, chaîne, paires, logiques, qualifiées, closed, severity,
  messages multilingues, sh:deactivated, sh:name/sh:description/sh:order/sh:group/sh:defaultValue.
- SHACL-SPARQL (sh:sparql) : conservé **brut** (fragment Turtle ré-injectable) + warning.

Identifiants des nœuds blancs : `_:<indice>-<hash8>` où le hash est calculé sur le contenu
(fermeture récursive) du nœud → identifiants **stables** d'un import à l'autre et après round-trip.

Conventions d'encodage imposées par le contrat (voir journal/L2/demandes-contrat.md) :
- les bornes (`min_inclusive`…) et les cibles `target_node` sont des `str` : un littéral dont le type
  se déduit de sa forme lexicale (entier → xsd:integer, décimal → xsd:decimal, double, booléen,
  date, dateTime) est stocké en forme lexicale ; sinon sous forme N-Triples `"5"^^<…#nonNegativeInteger>`
  (et `"x"@fr`, `"x"` pour une chaîne explicite) ; voir `encode_term` / `decode_term`.
- les triplets non modélisés (rdfs:comment d'une node shape, sh:target SPARQL…) ne sont pas
  conservables dans le contrat actuel : ils sont listés dans les warnings.
"""
from __future__ import annotations

import hashlib
import re
from typing import Iterable, Optional

import rdflib
from rdflib import BNode, Literal, URIRef
from rdflib.collection import Collection
from rdflib.namespace import OWL, RDF, RDFS, XSD

from ..core.onto_model import LiteralValue
from ..core.shapes_model import NodeShape, Path, PropertyShape, QualifiedShape, ShapesModel, Targets

SH = rdflib.Namespace("http://www.w3.org/ns/shacl#")
SPARQL_PLACEHOLDER = "urn:ontoforge:sparql-constraint"

SEVERITIES = {SH.Violation: "Violation", SH.Warning: "Warning", SH.Info: "Info"}
NODE_KINDS = {
    SH.IRI: "IRI", SH.BlankNode: "BlankNode", SH.Literal: "Literal", SH.BlankNodeOrIRI: "BlankNodeOrIRI",
    SH.BlankNodeOrLiteral: "BlankNodeOrLiteral", SH.IRIOrLiteral: "IRIOrLiteral",
}
TARGET_PREDS = {SH.targetClass, SH.targetNode, SH.targetSubjectsOf, SH.targetObjectsOf}
SHAPE_LIST_PARAMS = {SH["and"], SH["or"], SH.xone}
SHAPE_PARAMS = {SH.node, SH["not"], SH.qualifiedValueShape, SH.property}

# prédicats consommés selon le type de shape (le reste → warning « non modélisé »)
COMMON_PREDS = {
    RDF.type, SH["class"], SH.datatype, SH.nodeKind, SH.node, SH["in"], SH.hasValue, SH.pattern, SH.flags,
    SH.minLength, SH.maxLength, SH.minInclusive, SH.maxInclusive, SH.minExclusive, SH.maxExclusive,
    SH.languageIn, SH["and"], SH["or"], SH.xone, SH["not"], SH.sparql, SH.severity, SH.message, SH.deactivated,
} | TARGET_PREDS
NODE_PREDS = COMMON_PREDS | {SH.property, SH.closed, SH.ignoredProperties, RDFS.label}
PROP_PREDS = COMMON_PREDS | {
    SH.path, SH.name, SH.description, SH.minCount, SH.maxCount, SH.uniqueLang, SH.equals, SH.disjoint,
    SH.lessThan, SH.lessThanOrEquals, SH.qualifiedValueShape, SH.qualifiedMinCount, SH.qualifiedMaxCount,
    SH.qualifiedValueShapesDisjoint, SH.order, SH.group, SH.defaultValue,
}

_INT = re.compile(r"^[+-]?\d+$")
_DEC = re.compile(r"^[+-]?\d*\.\d+$")
_DBL = re.compile(r"^[+-]?(\d+\.?\d*|\.\d+)[eE][+-]?\d+$")
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}(Z|[+-]\d{2}:\d{2})?$")
_DATETIME = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})?$")


# ---------------------------------------------------------------------------------------------
# Encodage des termes dans les champs `str` du contrat
# ---------------------------------------------------------------------------------------------
def _guess_datatype(lex: str) -> Optional[URIRef]:
    if _INT.match(lex):
        return XSD.integer
    if _DEC.match(lex):
        return XSD.decimal
    if _DBL.match(lex):
        return XSD.double
    if lex in ("true", "false"):
        return XSD.boolean
    if _DATETIME.match(lex):
        return XSD.dateTime
    if _DATE.match(lex):
        return XSD.date
    return None


def encode_term(t: rdflib.term.Node) -> str:
    """Terme RDF → str (IRI absolue, forme lexicale si le type est déductible, sinon N-Triples)."""
    if isinstance(t, URIRef):
        return str(t)
    if isinstance(t, BNode):
        return f"_:{t}"
    assert isinstance(t, Literal)
    lex = str(t)
    if t.language:
        return f'"{_esc(lex)}"@{t.language}'
    if t.datatype is not None and t.datatype != XSD.string and _guess_datatype(lex) == t.datatype:
        return lex
    if t.datatype is None or t.datatype == XSD.string:
        return f'"{_esc(lex)}"'
    return f'"{_esc(lex)}"^^<{t.datatype}>'


_NT_LIT = re.compile(r'^"((?:[^"\\]|\\.)*)"(?:@([A-Za-z0-9-]+)|\^\^<([^>]+)>)?$')


def decode_term(s: str) -> rdflib.term.Node:
    """Inverse de `encode_term`."""
    m = _NT_LIT.match(s)
    if m:
        lex = _unesc(m.group(1))
        if m.group(2):
            return Literal(lex, lang=m.group(2))
        if m.group(3):
            return Literal(lex, datatype=URIRef(m.group(3)))
        return Literal(lex)
    if s.startswith("_:"):
        return BNode(s[2:])
    dt = _guess_datatype(s)
    if dt is not None:
        return Literal(s, datatype=dt)
    if re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", s):
        return URIRef(s)
    return Literal(s)


def _esc(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def _unesc(s: str) -> str:
    return s.replace("\\n", "\n").replace('\\"', '"').replace("\\\\", "\\")


def term_to_value(t: rdflib.term.Node) -> LiteralValue | str:
    """Valeur de sh:in / sh:hasValue / sh:defaultValue : IRI → str, littéral → LiteralValue."""
    if isinstance(t, Literal):
        dt = str(t.datatype) if t.datatype is not None and t.datatype != XSD.string else None
        return LiteralValue(value=str(t), datatype=dt, lang=t.language or None)
    if isinstance(t, BNode):
        return f"_:{t}"
    return str(t)


# ---------------------------------------------------------------------------------------------
# Lecture
# ---------------------------------------------------------------------------------------------
def parse_shapes(data: str | bytes, format: str | None = None,
                 filename: str | None = None) -> tuple[ShapesModel, list[str]]:
    """Parse un document SHACL (turtle par défaut ; xml, json-ld, nt, n3, trig) → (ShapesModel, warnings)."""
    fmt = guess_format(data, format, filename)
    g = rdflib.Graph()
    try:
        g.parse(data=data, format=fmt)
    except Exception as exc:  # noqa: BLE001 — remonté à l'utilisateur
        return ShapesModel(warnings=[f"Erreur d'analyse RDF ({fmt}) : {exc}"]), [f"Erreur d'analyse RDF ({fmt}) : {exc}"]
    return graph_to_shapes(g)


def guess_format(data: str | bytes, format: str | None = None, filename: str | None = None) -> str:
    aliases = {"ttl": "turtle", "rdf": "xml", "owl": "xml", "rdfxml": "xml", "jsonld": "json-ld",
               "json": "json-ld", "n-triples": "nt", "ntriples": "nt"}
    if format:
        return aliases.get(format.lower(), format.lower())
    if filename:
        ext = filename.rsplit(".", 1)[-1].lower()
        if ext in ("ttl", "turtle"):
            return "turtle"
        if ext in ("rdf", "owl", "xml"):
            return "xml"
        if ext in ("jsonld", "json"):
            return "json-ld"
        if ext in ("nt", "n3", "trig"):
            return {"nt": "nt", "n3": "n3", "trig": "trig"}[ext]
    head = (data[:400].decode("utf-8", "replace") if isinstance(data, bytes) else data[:400]).lstrip()
    if head.startswith("<?xml") or head.startswith("<rdf:RDF"):
        return "xml"
    if head.startswith("{") or head.startswith("["):
        return "json-ld"
    return "turtle"


class _Reader:
    def __init__(self, g: rdflib.Graph):
        self.g = g
        self.warnings: list[str] = []
        self.model = ShapesModel()
        self.ids: dict[rdflib.term.Node, str] = {}
        self.consumed: set[tuple] = set()
        self.done_nodes: set[rdflib.term.Node] = set()
        self.prop_in_node: set[rdflib.term.Node] = set()  # property shapes rattachées par sh:property

    # -- utilitaires ---------------------------------------------------------------------------
    def curie(self, t) -> str:
        try:
            return self.g.namespace_manager.normalizeUri(t) if isinstance(t, URIRef) else str(t)
        except Exception:  # noqa: BLE001
            return str(t)

    def objs(self, s, p) -> list:
        out = sorted(self.g.objects(s, p), key=lambda o: (isinstance(o, BNode), self._sig(o)))
        for o in out:
            self.consumed.add((s, p, o))
        return out

    def one(self, s, p):
        vals = self.objs(s, p)
        if len(vals) > 1:
            self.warnings.append(f"{self.label(s)} : plusieurs valeurs pour {self.curie(p)}, seule la première est gardée.")
        return vals[0] if vals else None

    def lst(self, head) -> list:
        items: list = []
        node = head
        seen = set()
        while node is not None and node != RDF.nil and node not in seen:
            seen.add(node)
            first = self.g.value(node, RDF.first)
            rest = self.g.value(node, RDF.rest)
            if first is None:
                self.warnings.append(f"Liste RDF mal formée à {node}.")
                break
            self.consumed.add((node, RDF.first, first))
            self.consumed.add((node, RDF.rest, rest))
            items.append(first)
            node = rest
        return items

    def _sig(self, node, stack: Optional[frozenset] = None) -> str:
        """Signature de contenu (récursive, sans cycle) pour un ordre et des ids déterministes."""
        if not isinstance(node, BNode):
            return node.n3()
        stack = stack or frozenset()
        if node in stack:
            return "<cycle>"
        parts = sorted(f"{p.n3()} {self._sig(o, stack | {node})}" for p, o in self.g.predicate_objects(node))
        return "[" + " ; ".join(parts) + "]"

    def node_id(self, node, hint: str = "s") -> str:
        if node in self.ids:
            return self.ids[node]
        if isinstance(node, URIRef):
            nid = str(node)
        else:
            h = hashlib.sha1(self._sig(node).encode()).hexdigest()[:8]
            nid = f"_:{hint}-{h}"
            n = 2
            used = set(self.ids.values())
            base = nid
            while nid in used:
                nid = f"{base}-{n}"
                n += 1
        self.ids[node] = nid
        return nid

    def label(self, node) -> str:
        return self.ids.get(node) or self.curie(node)

    def hint_for(self, node) -> str:
        path = self.g.value(node, SH.path)
        if path is not None:
            if isinstance(path, URIRef):
                return _local(str(path))
            inv = self.g.value(path, SH.inversePath)
            if isinstance(inv, URIRef):
                return "inv-" + _local(str(inv))
            return "path"
        return "shape"

    # -- détection des shapes ------------------------------------------------------------------
    def collect(self) -> None:
        g = self.g
        candidates: set = set()
        for t in (SH.NodeShape, SH.PropertyShape):
            candidates.update(g.subjects(RDF.type, t))
        for p in TARGET_PREDS:
            candidates.update(g.subjects(p, None))
        candidates.update(g.subjects(SH.path, None))
        for p in SHAPE_PARAMS:
            candidates.update(o for o in g.objects(None, p))
        for p in SHAPE_LIST_PARAMS:
            for head in g.objects(None, p):
                candidates.update(self._peek_list(head))
        for p in (SH.property,):
            self.prop_in_node.update(g.objects(None, p))
        # sous-graphes ignorés : contraintes SPARQL et déclarations de préfixes
        candidates = {c for c in candidates if not isinstance(c, Literal)}
        ordered = sorted(candidates, key=lambda n: (isinstance(n, BNode), self._sig(n)))
        for node in ordered:
            self.node_id(node, self.hint_for(node))
        for node in ordered:
            if node in self.done_nodes:
                continue
            if (node, SH.path, None) in g:
                ps = self.read_property_shape(node)
                if node not in self.prop_in_node:
                    self.model.property_shapes[ps.id] = ps
            else:
                ns = self.read_node_shape(node)
                self.model.shapes[ns.id] = ns
        # rattachement des property shapes à leurs node shapes (après lecture)
        self._attach_properties(ordered)

    def _peek_list(self, head) -> list:
        items, node, seen = [], head, set()
        while node is not None and node != RDF.nil and node not in seen:
            seen.add(node)
            f = self.g.value(node, RDF.first)
            if f is None:
                break
            items.append(f)
            node = self.g.value(node, RDF.rest)
        return items

    def _attach_properties(self, ordered) -> None:
        self._props_cache: dict = getattr(self, "_props_cache", {})
        for node in ordered:
            nid = self.ids[node]
            if nid not in self.model.shapes:
                continue
            props = []
            for p in self.objs(node, SH.property):
                ps = self._props_cache.get(p)
                if ps is None:
                    if (p, SH.path, None) not in self.g:
                        self.warnings.append(f"{nid} : sh:property {self.label(p)} sans sh:path, ignorée.")
                        continue
                    ps = self.read_property_shape(p)
                props.append(ps)
            self.model.shapes[nid].properties = props
        # property shapes rattachées à une property shape (sh:property sur une property shape : non modélisé)
        for node in self.prop_in_node:
            for s in self.g.subjects(SH.property, node):
                if (s, SH.path, None) in self.g:
                    self.warnings.append(
                        f"{self.label(s)} : sh:property sur une property shape non modélisé (utiliser sh:node).")
                    if node in self._props_cache:
                        ps = self._props_cache[node]
                        self.model.property_shapes.setdefault(ps.id, ps)

    # -- lecture des contraintes communes ------------------------------------------------------
    def read_common(self, node) -> dict:
        d: dict = {}
        d["class_"] = [str(o) for o in self.objs(node, SH["class"])]
        dt = self.one(node, SH.datatype)
        d["datatype"] = str(dt) if dt is not None else None
        nk = self.one(node, SH.nodeKind)
        if nk is not None:
            if nk in NODE_KINDS:
                d["node_kind"] = NODE_KINDS[nk]
            else:
                self.warnings.append(f"{self.label(node)} : sh:nodeKind inconnu {self.curie(nk)}.")
        d["node"] = [self.shape_ref(o) for o in self.objs(node, SH.node)]
        ins = self.one(node, SH["in"])
        d["in_"] = [term_to_value(v) for v in self.lst(ins)] if ins is not None else []
        d["has_value"] = [term_to_value(v) for v in self.objs(node, SH.hasValue)]
        pat = self.objs(node, SH.pattern)
        if len(pat) > 1:
            self.warnings.append(f"{self.label(node)} : plusieurs sh:pattern, seul le premier est gardé.")
        d["pattern"] = str(pat[0]) if pat else None
        fl = self.one(node, SH.flags)
        d["flags"] = str(fl) if fl is not None else None
        for key, p in (("min_length", SH.minLength), ("max_length", SH.maxLength)):
            v = self.one(node, p)
            d[key] = int(v) if v is not None else None
        for key, p in (("min_inclusive", SH.minInclusive), ("max_inclusive", SH.maxInclusive),
                       ("min_exclusive", SH.minExclusive), ("max_exclusive", SH.maxExclusive)):
            v = self.one(node, p)
            d[key] = encode_term(v) if v is not None else None
        li = self.one(node, SH.languageIn)
        d["language_in"] = [str(v) for v in self.lst(li)] if li is not None else []
        for key, p in (("and_", SH["and"]), ("or_", SH["or"]), ("xone", SH.xone)):
            vals = self.objs(node, p)
            if len(vals) > 1:
                self.warnings.append(
                    f"{self.label(node)} : plusieurs {self.curie(p)} — fusionnés en une seule liste (sémantique modifiée pour or/xone).")
            items: list[str] = []
            for head in vals:
                items.extend(self.shape_ref(o) for o in self.lst(head))
            d[key] = items
        d["not_"] = [self.shape_ref(o) for o in self.objs(node, SH["not"])]
        d["sparql"] = [self.read_sparql(node, o) for o in self.objs(node, SH.sparql)]
        sev = self.one(node, SH.severity)
        if sev is not None:
            if sev in SEVERITIES:
                d["severity"] = SEVERITIES[sev]
            else:
                self.warnings.append(f"{self.label(node)} : sévérité personnalisée {self.curie(sev)} ramenée à Violation.")
        d["messages"] = self.lang_map(node, SH.message)
        deact = self.one(node, SH.deactivated)
        d["deactivated"] = bool(deact.toPython()) if isinstance(deact, Literal) else False
        return d

    def lang_map(self, node, p) -> dict[str, str]:
        out: dict[str, str] = {}
        for o in self.objs(node, p):
            lang = o.language if isinstance(o, Literal) and o.language else ""
            if lang in out:
                self.warnings.append(f"{self.label(node)} : plusieurs {self.curie(p)} pour la langue '{lang}', un seul gardé.")
                continue
            out[lang] = str(o)
        return out

    def shape_ref(self, o) -> str:
        """Référence vers une shape (sh:node, sh:and…) : IRI ou id stable de nœud blanc."""
        if isinstance(o, Literal):
            self.warnings.append(f"Référence de shape littérale ignorée : {o!r}.")
            return str(o)
        return self.node_id(o, self.hint_for(o))

    def read_sparql(self, owner, node) -> str:
        """Fragment Turtle autonome de la contrainte SPARQL (racine = SPARQL_PLACEHOLDER)."""
        sub = rdflib.Graph()
        for pfx, ns in self.g.namespaces():
            sub.bind(pfx, ns)
        root = URIRef(SPARQL_PLACEHOLDER)
        stack, seen = [node], set()
        while stack:
            n = stack.pop()
            if n in seen:
                continue
            seen.add(n)
            for p, o in self.g.predicate_objects(n):
                self.consumed.add((n, p, o))
                sub.add((root if n == node else n, p, root if o == node else o))
                if isinstance(o, BNode) or (p == SH.prefixes and isinstance(o, URIRef)):
                    stack.append(o)
                if p == SH.declare:
                    stack.append(o)
        self.warnings.append(
            f"{self.label(owner)} : contrainte SHACL-SPARQL conservée brute (non interprétée par l'analyse, "
            "validée par pySHACL ; à traduire en validation applicative côté property graph).")
        return sub.serialize(format="turtle")

    def read_targets(self, node) -> Targets:
        t = Targets(
            target_class=[str(o) for o in self.objs(node, SH.targetClass)],
            target_node=[encode_term(o) for o in self.objs(node, SH.targetNode)],
            target_subjects_of=[str(o) for o in self.objs(node, SH.targetSubjectsOf)],
            target_objects_of=[str(o) for o in self.objs(node, SH.targetObjectsOf)],
        )
        if isinstance(node, URIRef):
            for cls_type in (RDFS.Class, OWL.Class):
                if (node, RDF.type, cls_type) in self.g:
                    self.consumed.add((node, RDF.type, cls_type))
                    if str(node) not in t.target_class:
                        t.target_class.append(str(node))
                    if cls_type == OWL.Class:
                        self.warnings.append(
                            f"{self.label(node)} : cible implicite via owl:Class (SHACL exige rdfs:Class ; pySHACL "
                            "l'accepte seulement si owl:Class ⊑ rdfs:Class est présent) — exportée en rdfs:Class.")
        for o in self.g.objects(node, SH.target):
            self.warnings.append(f"{self.label(node)} : cible SPARQL (sh:target) non modélisée, ignorée.")
        return t

    def check_unknown(self, node, allowed: set) -> None:
        for p, o in self.g.predicate_objects(node):
            if p in allowed or (node, p, o) in self.consumed:
                continue
            if p == RDF.type and o in (SH.NodeShape, SH.PropertyShape, SH.Shape):
                continue
            self.warnings.append(
                f"{self.label(node)} : triplet non modélisé {self.curie(p)} {self.curie(o) if not isinstance(o, Literal) else repr(str(o))} (perdu à l'export).")

    # -- node / property shapes ----------------------------------------------------------------
    def read_node_shape(self, node) -> NodeShape:
        self.done_nodes.add(node)
        nid = self.node_id(node, "shape")
        d = self.read_common(node)
        closed = self.one(node, SH.closed)
        ign = self.one(node, SH.ignoredProperties)
        ns = NodeShape(
            id=nid, targets=self.read_targets(node), **d,
            closed=bool(closed.toPython()) if isinstance(closed, Literal) else False,
            ignored_properties=[str(v) for v in self.lst(ign)] if ign is not None else [],
            labels=self.lang_map(node, RDFS.label),
        )
        self.check_unknown(node, NODE_PREDS)
        return ns

    def read_property_shape(self, node) -> PropertyShape:
        cache = getattr(self, "_props_cache", None)
        if cache is None:
            cache = self._props_cache = {}
        if node in cache:
            return cache[node]
        self.done_nodes.add(node)
        pid = self.node_id(node, self.hint_for(node))
        d = self.read_common(node)
        path_node = self.one(node, SH.path)
        path = self.read_path(path_node)
        if any((node, p, None) in self.g for p in TARGET_PREDS):
            self.warnings.append(f"{pid} : property shape avec cibles propres — cibles non modélisées sur une "
                                 "PropertyShape dans le contrat (perdues à l'export).")
            for p in TARGET_PREDS:
                self.objs(node, p)
        mc = self.one(node, SH.minCount)
        xc = self.one(node, SH.maxCount)
        ul = self.one(node, SH.uniqueLang)
        order = self.one(node, SH.order)
        group = self.one(node, SH.group)
        dv = self.one(node, SH.defaultValue)
        qualified = []
        qvs = self.objs(node, SH.qualifiedValueShape)
        qmin = self.one(node, SH.qualifiedMinCount)
        qmax = self.one(node, SH.qualifiedMaxCount)
        qdis = self.one(node, SH.qualifiedValueShapesDisjoint)
        for q in qvs:
            qualified.append(QualifiedShape(
                shape=self.shape_ref(q),
                min_count=int(qmin) if qmin is not None else None,
                max_count=int(qmax) if qmax is not None else None,
                disjoint=bool(qdis.toPython()) if isinstance(qdis, Literal) else False))
        if (qmin is not None or qmax is not None) and not qvs:
            self.warnings.append(f"{pid} : sh:qualifiedMin/MaxCount sans sh:qualifiedValueShape, ignoré.")
        if self.g.value(node, SH.closed) is not None:
            self.warnings.append(f"{pid} : sh:closed sur une property shape non modélisé (perdu à l'export).")
            self.objs(node, SH.closed)
            self.objs(node, SH.ignoredProperties)
        ps = PropertyShape(
            id=pid, path=path, **d,
            names=self.lang_map(node, SH.name), descriptions=self.lang_map(node, SH.description),
            min_count=int(mc) if mc is not None else None, max_count=int(xc) if xc is not None else None,
            unique_lang=bool(ul.toPython()) if isinstance(ul, Literal) else False,
            equals=[str(o) for o in self.objs(node, SH.equals)],
            disjoint=[str(o) for o in self.objs(node, SH.disjoint)],
            less_than=[str(o) for o in self.objs(node, SH.lessThan)],
            less_than_or_equals=[str(o) for o in self.objs(node, SH.lessThanOrEquals)],
            qualified=qualified,
            order=float(order) if order is not None else None,
            group=str(group) if group is not None else None,
            default_value=term_to_value(dv) if dv is not None else None,
        )
        self.check_unknown(node, PROP_PREDS)
        cache[node] = ps
        return ps

    def read_path(self, node) -> Path:
        if node is None:
            self.warnings.append("Property shape sans sh:path.")
            return Path(kind="predicate", iri="")
        if isinstance(node, URIRef):
            return Path(kind="predicate", iri=str(node))
        if isinstance(node, Literal):
            self.warnings.append(f"Chemin littéral invalide : {node!r}.")
            return Path(kind="predicate", iri=str(node))
        if (node, RDF.first, None) in self.g:
            return Path(kind="sequence", args=[self.read_path(x) for x in self.lst(node)])
        for p, kind in ((SH.inversePath, "inverse"), (SH.zeroOrMorePath, "zeroOrMore"),
                        (SH.oneOrMorePath, "oneOrMore"), (SH.zeroOrOnePath, "zeroOrOne")):
            v = self.g.value(node, p)
            if v is not None:
                self.consumed.add((node, p, v))
                return Path(kind=kind, args=[self.read_path(v)])
        alt = self.g.value(node, SH.alternativePath)
        if alt is not None:
            self.consumed.add((node, SH.alternativePath, alt))
            return Path(kind="alternative", args=[self.read_path(x) for x in self.lst(alt)])
        self.warnings.append(f"Chemin SHACL non reconnu : {self._sig(node)}.")
        return Path(kind="predicate", iri="")

    # -- triplets hors shapes ------------------------------------------------------------------
    def report_leftovers(self) -> None:
        shape_nodes = set(self.ids)
        left = [t for t in self.g if t not in self.consumed and t[0] not in shape_nodes]
        # les triplets des listes / chemins déjà consommés sont exclus ; le reste est hors périmètre shapes
        if left:
            subjects = sorted({self.curie(s) if isinstance(s, URIRef) else "_:" for s, _, _ in left})
            self.warnings.append(
                f"{len(left)} triplet(s) hors shapes ignorés (ontologie, métadonnées…) : sujets "
                + ", ".join(subjects[:8]) + (" …" if len(subjects) > 8 else ""))


def graph_to_shapes(g: rdflib.Graph) -> tuple[ShapesModel, list[str]]:
    """Graphe RDF → (ShapesModel, warnings). Les warnings sont aussi copiés dans `model.warnings`."""
    r = _Reader(g)
    r.collect()
    r.report_leftovers()
    r.model.prefixes = {p: str(ns) for p, ns in g.namespaces() if p and not _is_default_prefix(p, str(ns))}
    r.model.warnings = list(r.warnings)
    return r.model, list(r.warnings)


_DEFAULT_BINDINGS = {
    "brick", "csvw", "dc", "dcat", "dcmitype", "dcterms", "dcam", "doap", "foaf", "geo", "odrl", "org",
    "prof", "prov", "qb", "schema", "sosa", "ssn", "time", "vann", "void", "wgs", "skos", "xml", "owl", "rdf",
    "rdfs", "xsd", "sh",
}


def _is_default_prefix(prefix: str, ns: str) -> bool:
    # rdflib lie d'office de nombreux préfixes ; on ne garde que ceux du document + les usuels utiles
    return prefix in _DEFAULT_BINDINGS and prefix not in ("owl", "rdf", "rdfs", "xsd", "sh", "skos")


def _local(iri: str) -> str:
    for sep in ("#", "/", ":"):
        if sep in iri and iri.rsplit(sep, 1)[1]:
            return re.sub(r"[^A-Za-z0-9_-]", "", iri.rsplit(sep, 1)[1]) or "x"
    return "x"


def iter_all_property_shapes(model: ShapesModel) -> Iterable[tuple[Optional[NodeShape], PropertyShape]]:
    """Toutes les property shapes (imbriquées puis autonomes), avec leur node shape parente si imbriquée."""
    for ns in model.shapes.values():
        for ps in ns.properties:
            yield ns, ps
    for ps in model.property_shapes.values():
        yield None, ps
