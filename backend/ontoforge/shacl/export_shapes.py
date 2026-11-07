"""Export ShapesModel → graphe RDF / Turtle (inverse de import_shapes).

Conventions de normalisation (documentées, sans perte sémantique) :
- les shapes d'IRI sont typées (sh:NodeShape / sh:PropertyShape) ; les shapes anonymes ne le sont pas ;
- une node shape dont l'IRI figure dans ses propres `target_class` est exportée avec `a rdfs:Class`
  (cible implicite) et non `sh:targetClass <soi-même>` ;
- `severity="Violation"` (défaut SHACL) et les booléens à `false` ne sont pas écrits.
Ainsi `graph_to_shapes(shapes_to_graph(m))` ≡ `m`, et Turtle → modèle → Turtle est isomorphe pour tout
document qui respecte ces conventions (cas de `samples/trap/trap-shapes.ttl`).
"""
from __future__ import annotations

import rdflib
from rdflib import BNode, Literal, URIRef
from rdflib.collection import Collection
from rdflib.namespace import RDF, RDFS, XSD

from ..core.onto_model import LiteralValue
from ..core.shapes_model import Constraints, NodeShape, Path, PropertyShape, ShapesModel
from .import_shapes import SH, SPARQL_PLACEHOLDER, decode_term

_NODE_KIND_IRI = {k: SH[k] for k in ("IRI", "BlankNode", "Literal", "BlankNodeOrIRI", "BlankNodeOrLiteral",
                                     "IRIOrLiteral")}


def shapes_to_graph(s: ShapesModel) -> rdflib.Graph:
    """ShapesModel → rdflib.Graph (SHACL Core + fragments SHACL-SPARQL ré-injectés)."""
    return _Writer(s).run()[0]


def shapes_to_graph_with_ids(s: ShapesModel) -> tuple[rdflib.Graph, dict[rdflib.term.Node, str]]:
    """Comme `shapes_to_graph`, renvoie aussi la table nœud RDF → id de shape du modèle (utile au rapport)."""
    return _Writer(s).run()


def serialize_shapes(s: ShapesModel, format: str = "turtle") -> str:
    fmt = {"ttl": "turtle", "rdf": "xml", "rdfxml": "xml", "jsonld": "json-ld"}.get(format, format)
    return shapes_to_graph(s).serialize(format=fmt)


def _lit_value(v: LiteralValue | str) -> rdflib.term.Node:
    if isinstance(v, LiteralValue):
        if v.lang:
            return Literal(v.value, lang=v.lang)
        return Literal(v.value, datatype=URIRef(v.datatype) if v.datatype else None)
    if v.startswith("_:"):
        return BNode(v[2:])
    return URIRef(v)


class _Writer:
    def __init__(self, s: ShapesModel):
        self.s = s
        self.g = rdflib.Graph()
        self.nodes: dict[str, rdflib.term.Node] = {}
        self.ids: dict[rdflib.term.Node, str] = {}
        self.written: set[str] = set()
        self.by_id_ps: dict[str, PropertyShape] = {}
        for ns in s.shapes.values():
            for ps in ns.properties:
                self.by_id_ps.setdefault(ps.id, ps)
        self.by_id_ps.update(s.property_shapes)

    def ref(self, sid: str) -> rdflib.term.Node:
        if sid not in self.nodes:
            n = BNode() if sid.startswith("_:") else URIRef(sid)
            self.nodes[sid] = n
            self.ids[n] = sid
        return self.nodes[sid]

    def run(self):
        g = self.g
        g.bind("sh", SH)
        g.bind("xsd", XSD)
        g.bind("rdfs", RDFS)
        for p, ns in self.s.prefixes.items():
            g.bind(p, ns, override=True)
        for ns in self.s.shapes.values():
            self.write_node(ns)
        for ps in self.s.property_shapes.values():
            self.write_prop(ps)
        # références vers des property shapes non encore écrites (ex. sh:node vers une PS imbriquée)
        return g, self.ids

    def lst(self, items: list) -> rdflib.term.Node:
        if not items:
            return RDF.nil
        head = BNode()
        Collection(self.g, head, list(items))
        return head

    def common(self, n, c: Constraints) -> None:
        g = self.g
        for cl in c.class_:
            g.add((n, SH["class"], URIRef(cl)))
        if c.datatype:
            g.add((n, SH.datatype, URIRef(c.datatype)))
        if c.node_kind:
            g.add((n, SH.nodeKind, _NODE_KIND_IRI[c.node_kind]))
        for sid in c.node:
            g.add((n, SH.node, self.shape(sid)))
        if c.in_:
            g.add((n, SH["in"], self.lst([_lit_value(v) for v in c.in_])))
        for v in c.has_value:
            g.add((n, SH.hasValue, _lit_value(v)))
        if c.pattern is not None:
            g.add((n, SH.pattern, Literal(c.pattern)))
        if c.flags is not None:
            g.add((n, SH.flags, Literal(c.flags)))
        if c.min_length is not None:
            g.add((n, SH.minLength, Literal(c.min_length)))
        if c.max_length is not None:
            g.add((n, SH.maxLength, Literal(c.max_length)))
        for attr, p in (("min_inclusive", SH.minInclusive), ("max_inclusive", SH.maxInclusive),
                        ("min_exclusive", SH.minExclusive), ("max_exclusive", SH.maxExclusive)):
            v = getattr(c, attr)
            if v is not None:
                g.add((n, p, decode_term(v)))
        if c.language_in:
            g.add((n, SH.languageIn, self.lst([Literal(x) for x in c.language_in])))
        for attr, p in (("and_", SH["and"]), ("or_", SH["or"]), ("xone", SH.xone)):
            items = getattr(c, attr)
            if items:
                g.add((n, p, self.lst([self.shape(x) for x in items])))
        for sid in c.not_:
            g.add((n, SH["not"], self.shape(sid)))
        for frag in c.sparql:
            self.sparql(n, frag)
        if c.severity != "Violation":
            g.add((n, SH.severity, SH[c.severity]))
        for lang, msg in c.messages.items():
            g.add((n, SH.message, Literal(msg, lang=lang or None)))
        if c.deactivated:
            g.add((n, SH.deactivated, Literal(True)))

    def shape(self, sid: str) -> rdflib.term.Node:
        """Référence de shape : écrit la shape anonyme/PS référencée si elle est dans le modèle."""
        node = self.ref(sid)
        if sid not in self.written:
            if sid in self.s.shapes:
                self.write_node(self.s.shapes[sid])
            elif sid in self.by_id_ps:
                self.write_prop(self.by_id_ps[sid])
        return node

    def sparql(self, owner, frag: str) -> None:
        sub = rdflib.Graph()
        sub.parse(data=frag, format="turtle")
        root = BNode()
        placeholder = URIRef(SPARQL_PLACEHOLDER)
        for pfx, ns in sub.namespaces():
            if pfx and pfx not in dict(self.g.namespaces()):
                self.g.bind(pfx, ns)
        remap: dict = {}
        for s_, p, o in sub:
            s2 = root if s_ == placeholder else remap.setdefault(s_, BNode()) if isinstance(s_, BNode) else s_
            o2 = root if o == placeholder else remap.setdefault(o, BNode()) if isinstance(o, BNode) else o
            self.g.add((s2, p, o2))
        self.g.add((owner, SH.sparql, root))

    def write_node(self, ns: NodeShape) -> None:
        if ns.id in self.written:
            return
        self.written.add(ns.id)
        g = self.g
        n = self.ref(ns.id)
        if isinstance(n, URIRef):
            g.add((n, RDF.type, SH.NodeShape))
        t = ns.targets
        for c in t.target_class:
            if c == ns.id:
                g.add((n, RDF.type, RDFS.Class))
            else:
                g.add((n, SH.targetClass, URIRef(c)))
        for v in t.target_node:
            g.add((n, SH.targetNode, decode_term(v)))
        for p in t.target_subjects_of:
            g.add((n, SH.targetSubjectsOf, URIRef(p)))
        for p in t.target_objects_of:
            g.add((n, SH.targetObjectsOf, URIRef(p)))
        self.common(n, ns)
        if ns.closed:
            g.add((n, SH.closed, Literal(True)))
        if ns.ignored_properties:
            g.add((n, SH.ignoredProperties, self.lst([URIRef(x) for x in ns.ignored_properties])))
        for lang, lab in ns.labels.items():
            g.add((n, RDFS.label, Literal(lab, lang=lang or None)))
        for ps in ns.properties:
            g.add((n, SH.property, self.ref(ps.id)))
            self.write_prop(ps)

    def write_prop(self, ps: PropertyShape) -> None:
        if ps.id in self.written:
            return
        self.written.add(ps.id)
        g = self.g
        n = self.ref(ps.id)
        if isinstance(n, URIRef):
            g.add((n, RDF.type, SH.PropertyShape))
        g.add((n, SH.path, self.path(ps.path)))
        self.common(n, ps)
        for lang, v in ps.names.items():
            g.add((n, SH.name, Literal(v, lang=lang or None)))
        for lang, v in ps.descriptions.items():
            g.add((n, SH.description, Literal(v, lang=lang or None)))
        if ps.min_count is not None:
            g.add((n, SH.minCount, Literal(ps.min_count)))
        if ps.max_count is not None:
            g.add((n, SH.maxCount, Literal(ps.max_count)))
        if ps.unique_lang:
            g.add((n, SH.uniqueLang, Literal(True)))
        for attr, p in (("equals", SH.equals), ("disjoint", SH.disjoint), ("less_than", SH.lessThan),
                        ("less_than_or_equals", SH.lessThanOrEquals)):
            for v in getattr(ps, attr):
                g.add((n, p, URIRef(v)))
        for q in ps.qualified:
            g.add((n, SH.qualifiedValueShape, self.shape(q.shape)))
            if q.min_count is not None:
                g.add((n, SH.qualifiedMinCount, Literal(q.min_count)))
            if q.max_count is not None:
                g.add((n, SH.qualifiedMaxCount, Literal(q.max_count)))
            if q.disjoint:
                g.add((n, SH.qualifiedValueShapesDisjoint, Literal(True)))
        if ps.order is not None:
            o = ps.order
            g.add((n, SH.order, Literal(int(o)) if float(o).is_integer() else Literal(o, datatype=XSD.decimal)))
        if ps.group:
            g.add((n, SH.group, URIRef(ps.group)))
        if ps.default_value is not None:
            g.add((n, SH.defaultValue, _lit_value(ps.default_value)))

    def path(self, p: Path) -> rdflib.term.Node:
        if p.kind == "predicate":
            return URIRef(p.iri or "")
        if p.kind == "sequence":
            return self.lst([self.path(a) for a in p.args])
        if p.kind == "alternative":
            b = BNode()
            self.g.add((b, SH.alternativePath, self.lst([self.path(a) for a in p.args])))
            return b
        pred = {"inverse": SH.inversePath, "zeroOrMore": SH.zeroOrMorePath, "oneOrMore": SH.oneOrMorePath,
                "zeroOrOne": SH.zeroOrOnePath}[p.kind]
        b = BNode()
        self.g.add((b, pred, self.path(p.args[0])))
        return b


def path_to_sparql(p: Path, compact=None) -> str:
    """Rendu SPARQL 1.1 d'un chemin (`^p`, `p/q`, `p|q`, `p*`, `p+`, `p?`) ; `compact(iri)->str` optionnel."""
    c = compact or (lambda i: f"<{i}>")
    if p.kind == "predicate":
        return c(p.iri or "")
    if p.kind == "inverse":
        return "^" + _wrap(p.args[0], compact)
    if p.kind == "sequence":
        return "/".join(_wrap(a, compact) for a in p.args)
    if p.kind == "alternative":
        return "|".join(_wrap(a, compact) for a in p.args)
    suffix = {"zeroOrMore": "*", "oneOrMore": "+", "zeroOrOne": "?"}[p.kind]
    return _wrap(p.args[0], compact) + suffix


def _wrap(p: Path, compact) -> str:
    s = path_to_sparql(p, compact)
    return s if p.kind in ("predicate", "inverse") or len(p.args) <= 1 else f"({s})"
