"""Import RDF → OntoModel.

Applique en sens inverse le *OWL 2 Web Ontology Language Mapping to RDF Graphs* (2e éd., §3 « Mapping from
RDF Graphs to the Structural Specification », tables 3 à 16 de la direction directe) :

* déclarations (§3.2.1, table 7 directe) ;
* expressions de classes (table 13) et de données (table 12), y compris ObjectInverseOf (table 11) ;
* axiomes (table 16) : sous-classes, équivalences, disjonctions (paires, AllDisjointClasses,
  DisjointUnion), HasKey, domaines/portées, inverses, caractéristiques, sous-propriétés, chaînes,
  équivalences/disjonctions de propriétés, assertions (y compris NegativePropertyAssertion,
  sameAs, differentFrom, AllDifferent), DatatypeDefinition ;
* annotations d'entités (§3.2.6) et en-tête d'ontologie (§3.1.2).

Tout triplet non consommé est conservé dans ``OntoModel.unmapped`` (regroupé par sujet, nœuds blancs
rattachés à leur racine) et signalé par un warning ``[unmapped_triple]`` — aucune perte silencieuse.

Les warnings sont des chaînes ``"[code] <sujet> : message"`` ; :func:`parse_warning` les découpe en
``{code, subject, message}`` pour l'API (ImportResult.warnings).
"""
from __future__ import annotations

import re
from decimal import Decimal
from collections import defaultdict
from typing import Iterable, Optional

import rdflib
from rdflib import BNode, Literal, URIRef
from rdflib.collection import Collection
from rdflib.compare import to_canonical_graph
from rdflib.namespace import OWL as _OWL, RDF as _RDF, RDFS as _RDFS, XSD as _XSD

from ..core.onto_model import (
    Annotation, AnnotationProperty, ClassExpr, DataRange, DatatypeDef, DatatypeProperty, Fact, Individual,
    LiteralValue, ObjectProperty, OntClass, OntoModel, OntologyMeta, Restriction, UnmappedAxiom, OWL, RDF,
    RDFS, XSD,
)

SKOS = "http://www.w3.org/2004/02/skos/core#"
DCTERMS = "http://purl.org/dc/terms/"
DC = "http://purl.org/dc/elements/1.1/"

__all__ = ["parse_ontology", "graph_to_model", "detect_format", "parse_warning", "canonical_model",
           "RdfImportError", "BUILTIN_ANNOTATION_PROPERTIES", "is_builtin_datatype"]


class RdfImportError(ValueError):
    """Le contenu n'a pas pu être lu comme RDF (format inconnu ou syntaxe invalide)."""


# --------------------------------------------------------------------------------------------------
# Vocabulaire
# --------------------------------------------------------------------------------------------------
T = _RDF.type
FIRST, REST, NIL = _RDF.first, _RDF.rest, _RDF.nil

# OWL 2 Structural Spec §5.5 : propriétés d'annotation prédéfinies
BUILTIN_ANNOTATION_PROPERTIES = {
    RDFS + "label", RDFS + "comment", RDFS + "seeAlso", RDFS + "isDefinedBy", OWL + "deprecated",
    OWL + "versionInfo", OWL + "priorVersion", OWL + "backwardCompatibleWith", OWL + "incompatibleWith",
}
# Vocabulaires d'annotation « de fait » : tolérés sans déclaration (warning DL)
ANNOTATION_NAMESPACES = (SKOS, DCTERMS, DC, "http://purl.org/vocab/vann/", "http://xmlns.com/foaf/0.1/",
                         "http://schema.org/", "https://schema.org/")

# OWL 2 Structural Spec §4 : carte des datatypes (+ rdfs:Literal)
OWL2_DATATYPE_MAP = {
    RDF + "PlainLiteral", RDF + "XMLLiteral", RDF + "langString", RDFS + "Literal", OWL + "real", OWL + "rational",
    *(XSD + n for n in (
        "decimal", "integer", "nonNegativeInteger", "nonPositiveInteger", "positiveInteger", "negativeInteger",
        "long", "int", "short", "byte", "unsignedLong", "unsignedInt", "unsignedShort", "unsignedByte", "double",
        "float", "string", "normalizedString", "token", "language", "Name", "NCName", "NMTOKEN", "boolean",
        "hexBinary", "base64Binary", "anyURI", "dateTime", "dateTimeStamp")),
}

CHARACTERISTICS = {
    OWL + "FunctionalProperty": "functional", OWL + "InverseFunctionalProperty": "inverseFunctional",
    OWL + "TransitiveProperty": "transitive", OWL + "SymmetricProperty": "symmetric",
    OWL + "AsymmetricProperty": "asymmetric", OWL + "ReflexiveProperty": "reflexive",
    OWL + "IrreflexiveProperty": "irreflexive",
}
DECL_TYPES = {OWL + "Class", RDFS + "Class", RDFS + "Datatype", OWL + "ObjectProperty", OWL + "DatatypeProperty",
              OWL + "AnnotationProperty", OWL + "NamedIndividual", RDF + "Property", OWL + "Ontology"}
RESERVED_NS = (RDF, RDFS, OWL, XSD)

CARD_PREDICATES = {
    OWL + "minCardinality": ("min", False), OWL + "maxCardinality": ("max", False),
    OWL + "cardinality": ("exactly", False), OWL + "minQualifiedCardinality": ("min", True),
    OWL + "maxQualifiedCardinality": ("max", True), OWL + "qualifiedCardinality": ("exactly", True),
}


def is_builtin_datatype(iri: str) -> bool:
    return iri in OWL2_DATATYPE_MAP or iri.startswith(XSD)


def _u(x: str) -> URIRef:
    return URIRef(x)


class Unsupported(Exception):
    """Construction RDF non représentable dans OntoModel (l'axiome part dans `unmapped`)."""


# --------------------------------------------------------------------------------------------------
# Détection de format et parsing
# --------------------------------------------------------------------------------------------------
_EXT = {
    ".ttl": "turtle", ".turtle": "turtle", ".n3": "n3", ".nt": "nt", ".ntriples": "nt", ".trig": "trig",
    ".nq": "nquads", ".rdf": "xml", ".xml": "xml", ".rdfxml": "xml", ".jsonld": "json-ld", ".json": "json-ld",
}
_FORMAT_ALIASES = {
    "ttl": "turtle", "turtle": "turtle", "text/turtle": "turtle", "xml": "xml", "rdfxml": "xml", "rdf/xml": "xml",
    "rdf+xml": "xml", "application/rdf+xml": "xml", "pretty-xml": "xml", "owl": "xml", "json-ld": "json-ld",
    "jsonld": "json-ld", "application/ld+json": "json-ld", "nt": "nt", "ntriples": "nt", "n-triples": "nt",
    "n3": "n3", "trig": "trig", "nquads": "nquads",
}


def _sniff(text: str) -> Optional[str]:
    s = text.lstrip("﻿ \t\r\n")
    head = s[:4000]
    if s.startswith("<?xml") or s.startswith("<rdf:RDF") or re.match(r"<[A-Za-z_][\w.\-]*:?RDF\b", s):
        if re.search(r"<(?:owl:)?Ontology\b[^>]*xmlns=\"http://www\.w3\.org/2002/07/owl#\"", head) and "rdf:RDF" not in head:
            raise RdfImportError("Format OWL/XML détecté : non pris en charge (exporter en RDF/XML ou Turtle depuis Protégé).")
        return "xml"
    if s.startswith("{") or s.startswith("["):
        return "json-ld"
    if re.match(r"(Prefix|Ontology)\s*\(", s):
        raise RdfImportError("Syntaxe fonctionnelle OWL détectée : non prise en charge (exporter en Turtle ou RDF/XML).")
    if re.match(r"(Prefix:|Ontology:|Class:)", s):
        raise RdfImportError("Syntaxe Manchester détectée : non prise en charge (exporter en Turtle ou RDF/XML).")
    if re.search(r"^\s*(@prefix|@base|PREFIX|BASE)\b", head, re.M | re.I):
        return "trig" if re.search(r"^\s*(GRAPH\s+)?<[^>]*>\s*\{", head, re.M) else "turtle"
    if s.startswith("<"):
        return "turtle"  # N-Triples ⊂ Turtle
    if s.startswith("#") or ":" in head:
        return "turtle"
    return None


def detect_format(data: str | bytes, format: Optional[str] = None, filename: Optional[str] = None) -> str:
    """Format rdflib : explicite, puis extension (sauf .owl, ambigu), puis contenu."""
    if format:
        f = _FORMAT_ALIASES.get(format.lower())
        if not f:
            raise RdfImportError(f"Format inconnu : {format!r}.")
        return f
    if filename:
        m = re.search(r"(\.[A-Za-z0-9]+)$", filename.lower())
        if m and m.group(1) in _EXT:
            return _EXT[m.group(1)]
    text = data.decode("utf-8", errors="replace") if isinstance(data, bytes) else data
    f = _sniff(text)
    if not f:
        raise RdfImportError("Impossible de déterminer le format RDF (préciser format=turtle|xml|json-ld|nt).")
    return f


def parse_ontology(data: str | bytes, format: Optional[str] = None, filename: Optional[str] = None
                   ) -> tuple[OntoModel, list[str]]:
    fmt = detect_format(data, format, filename)
    g = rdflib.Graph(bind_namespaces="none")
    try:
        g.parse(data=data, format=fmt)
    except Exception as e:  # noqa: BLE001 — message utilisateur
        raise RdfImportError(f"Erreur de syntaxe ({fmt}) : {e}") from e
    model, warnings = graph_to_model(g)
    return model, [f"[format] : format détecté {fmt}, {len(g)} triplets"] + warnings


def parse_warning(w: str) -> dict:
    """``"[code] sujet : message"`` → ``{code, subject, message}``."""
    m = re.match(r"\[([\w\-]+)\]\s*(?:<([^>]*)>)?\s*:\s*(.*)$", w, re.S)
    if not m:
        return {"code": "info", "subject": None, "message": w}
    return {"code": m.group(1), "subject": m.group(2), "message": m.group(3)}


# --------------------------------------------------------------------------------------------------
# Lecteur
# --------------------------------------------------------------------------------------------------
def _lex(o: Literal) -> str:
    """Forme lexicale ; xsd:decimal est normalisée (« 0 » = « 0.0 ») car les sérialiseurs Turtle réécrivent 0 en 0.0."""
    t = str(o)
    if o.datatype is not None and str(o.datatype) == XSD + "decimal":
        try:
            t = format(Decimal(t.strip()), "f")
        except Exception:
            return t
        if "." not in t:
            t += ".0"
    return t


def _short(p) -> str:
    """Prédicat abrégé de façon stable (indépendante des préfixes du fichier)."""
    for pfx, ns in (("rdf", RDF), ("rdfs", RDFS), ("owl", OWL), ("xsd", XSD)):
        if str(p).startswith(ns):
            return f"{pfx}:{str(p)[len(ns):]}"
    return str(p)


def _lit(o: Literal) -> tuple[str, Optional[str], Optional[str]]:
    return _lex(o), (str(o.datatype) if o.datatype and str(o.datatype) != XSD + 'string' else None), (o.language or None)


def _is_true(o) -> bool:
    return isinstance(o, Literal) and str(o).strip().lower() in ("true", "1")


class _Reader:
    def __init__(self, g: rdflib.Graph):
        self.g = g
        self.consumed: set[tuple] = set()
        self.warnings: list[str] = []
        self.m = OntoModel(meta=OntologyMeta(iri=""))
        self.kinds: dict[URIRef, set[str]] = defaultdict(set)

    # ---- utilitaires ---------------------------------------------------------------------------
    def warn(self, code: str, subject, msg: str) -> None:
        subj = f"<{subject}>" if subject is not None and not isinstance(subject, BNode) else ""
        self.warnings.append(f"[{code}] {subj} : {msg}".replace("]  :", "] :"))

    def use(self, *triples) -> None:
        self.consumed.update(triples)

    def bnode_triples(self, n) -> set[tuple]:
        return {(n, p, o) for p, o in self.g.predicate_objects(n)}

    def read_list(self, node) -> tuple[list, set[tuple]]:
        items, used, seen = [], set(), set()
        while node != NIL:
            if not isinstance(node, BNode) or node in seen:
                raise Unsupported("liste RDF mal formée")
            seen.add(node)
            firsts = list(self.g.objects(node, FIRST))
            rests = list(self.g.objects(node, REST))
            if len(firsts) != 1 or len(rests) != 1 or len(self.bnode_triples(node)) != 2:
                raise Unsupported("liste RDF mal formée")
            items.append(firsts[0])
            used |= {(node, FIRST, firsts[0]), (node, REST, rests[0])}
            node = rests[0]
        return items, used

    def is_datatype_node(self, n) -> bool:
        if isinstance(n, URIRef):
            return is_builtin_datatype(str(n)) or "datatype" in self.kinds.get(n, set())
        if isinstance(n, BNode):
            return (n, T, _RDFS.Datatype) in self.g or any(
                (n, p, None) in self.g for p in (_OWL.onDatatype, _OWL.datatypeComplementOf))
        return False

    def is_data_property(self, p) -> bool:
        return "data" in self.kinds.get(p, set())

    # ---- expressions de classes (table 13) -----------------------------------------------------
    def parse_ce(self, n) -> tuple[ClassExpr, set[tuple]]:
        if isinstance(n, URIRef):
            return ClassExpr(op="named", iri=str(n)), set()
        if not isinstance(n, BNode):
            raise Unsupported("littéral en position d'expression de classe")
        own = self.bnode_triples(n)
        used: set[tuple] = set()
        types = set(self.g.objects(n, T))
        for t in types & {_OWL.Class, _OWL.Restriction}:
            used.add((n, T, t))

        def single(p):
            vals = list(self.g.objects(n, p))
            if len(vals) > 1:
                raise Unsupported(f"plusieurs {p}")
            return vals[0] if vals else None

        expr: Optional[ClassExpr] = None
        for p, op in ((_OWL.intersectionOf, "and"), (_OWL.unionOf, "or")):
            lst = single(p)
            if lst is not None:
                items, lu = self.read_list(lst)
                args = []
                for it in items:
                    e, u = self.parse_ce(it)
                    args.append(e)
                    used |= u
                used |= lu | {(n, p, lst)}
                expr = ClassExpr(op=op, args=args)
        c = single(_OWL.complementOf)
        if c is not None and expr is None:
            e, u = self.parse_ce(c)
            used |= u | {(n, _OWL.complementOf, c)}
            expr = ClassExpr(op="not", args=[e])
        lst = single(_OWL.oneOf)
        if lst is not None and expr is None:
            items, lu = self.read_list(lst)
            if not all(isinstance(i, URIRef) for i in items):
                raise Unsupported("owl:oneOf avec individus anonymes ou littéraux")
            used |= lu | {(n, _OWL.oneOf, lst)}
            expr = ClassExpr(op="oneOf", individuals=[str(i) for i in items])
        if expr is None and _OWL.Restriction in types:
            expr, u = self.parse_restriction(n, single)
            used |= u
        if expr is None or not own <= used:
            raise Unsupported("expression de classe non reconnue ou triplets supplémentaires")
        return expr, used

    def parse_property_expr(self, p) -> tuple[str, bool, set[tuple]]:
        if isinstance(p, URIRef):
            return str(p), False, set()
        if isinstance(p, BNode):
            invs = list(self.g.objects(p, _OWL.inverseOf))
            if len(invs) == 1 and isinstance(invs[0], URIRef) and len(self.bnode_triples(p)) == 1:
                return str(invs[0]), True, {(p, _OWL.inverseOf, invs[0])}
        raise Unsupported("expression de propriété non reconnue")

    def parse_restriction(self, n, single) -> tuple[ClassExpr, set[tuple]]:
        if (n, _OWL.onProperties, None) in self.g:
            raise Unsupported("restriction n-aire (owl:onProperties)")
        prop = single(_OWL.onProperty)
        if prop is None:
            raise Unsupported("owl:Restriction sans owl:onProperty")
        piri, inverse, used = self.parse_property_expr(prop)
        used |= {(n, _OWL.onProperty, prop)}
        is_data = self.is_data_property(_u(piri))
        for pred, kind in ((_OWL.someValuesFrom, "some"), (_OWL.allValuesFrom, "only")):
            f = single(pred)
            if f is not None:
                used.add((n, pred, f))
                if is_data or self.is_datatype_node(f):
                    if not isinstance(f, URIRef):
                        raise Unsupported("restriction de données avec DataRange complexe")
                    return ClassExpr(op=kind, property=piri, inverse=inverse, data_range=str(f)), used
                e, u = self.parse_ce(f)
                return ClassExpr(op=kind, property=piri, inverse=inverse, filler=e), used | u
        v = single(_OWL.hasValue)
        if v is not None:
            used.add((n, _OWL.hasValue, v))
            if isinstance(v, Literal):
                val, dt, lang = _lit(v)
                return ClassExpr(op="value", property=piri, inverse=inverse,
                                 value=LiteralValue(value=val, datatype=dt, lang=lang)), used
            if isinstance(v, URIRef):
                return ClassExpr(op="value", property=piri, inverse=inverse, value=str(v)), used
            raise Unsupported("owl:hasValue sur individu anonyme")
        s = single(_OWL.hasSelf)
        if s is not None:
            if not _is_true(s):
                raise Unsupported("owl:hasSelf différent de true")
            return ClassExpr(op="self", property=piri, inverse=inverse), used | {(n, _OWL.hasSelf, s)}
        for pred, (kind, qualified) in CARD_PREDICATES.items():
            k = single(_u(pred))
            if k is None:
                continue
            try:
                num = int(str(k))
            except ValueError as e:
                raise Unsupported("cardinalité non entière") from e
            used.add((n, _u(pred), k))
            expr = ClassExpr(op=kind, property=piri, inverse=inverse, n=num)
            if qualified:
                oc, odr = single(_OWL.onClass), single(_OWL.onDataRange)
                if oc is not None:
                    e, u = self.parse_ce(oc)
                    expr.filler = e
                    used |= u | {(n, _OWL.onClass, oc)}
                elif odr is not None:
                    if not isinstance(odr, URIRef):
                        raise Unsupported("cardinalité qualifiée sur DataRange complexe")
                    expr.data_range = str(odr)
                    used.add((n, _OWL.onDataRange, odr))
                else:
                    raise Unsupported("cardinalité qualifiée sans owl:onClass / owl:onDataRange")
            return expr, used
        raise Unsupported("restriction sans contrainte reconnue")

    # ---- data ranges (table 12) ----------------------------------------------------------------
    def parse_data_range(self, n) -> tuple[DataRange, set[tuple]]:
        if isinstance(n, URIRef):
            return DataRange(base=str(n)), set()
        if not isinstance(n, BNode):
            raise Unsupported("DataRange invalide")
        own = self.bnode_triples(n)
        used = {(n, T, _RDFS.Datatype)} if (n, T, _RDFS.Datatype) in self.g else set()
        dr: Optional[DataRange] = None
        base = list(self.g.objects(n, _OWL.onDatatype))
        if len(base) == 1 and isinstance(base[0], URIRef):
            dr = DataRange(base=str(base[0]))
            used.add((n, _OWL.onDatatype, base[0]))
            for wr in self.g.objects(n, _OWL.withRestrictions):
                items, lu = self.read_list(wr)
                used |= lu | {(n, _OWL.withRestrictions, wr)}
                for it in items:
                    ft = self.bnode_triples(it) if isinstance(it, BNode) else set()
                    if len(ft) != 1:
                        raise Unsupported("facette mal formée")
                    (_, fp, fv), = ft
                    if not isinstance(fv, Literal):
                        raise Unsupported("valeur de facette non littérale")
                    if str(fp) in dr.facets:
                        raise Unsupported("facette répétée")
                    dr.facets[str(fp)] = _lex(fv)
                    used |= ft
        lst = list(self.g.objects(n, _OWL.oneOf))
        if dr is None and len(lst) == 1:
            items, lu = self.read_list(lst[0])
            if not all(isinstance(i, Literal) for i in items):
                raise Unsupported("DataOneOf avec non-littéraux")
            dr = DataRange(one_of=[LiteralValue(value=v, datatype=d, lang=la) for v, d, la in map(_lit, items)])
            used |= lu | {(n, _OWL.oneOf, lst[0])}
        un = list(self.g.objects(n, _OWL.unionOf))
        if dr is None and len(un) == 1:
            items, lu = self.read_list(un[0])
            if not all(isinstance(i, URIRef) for i in items):
                raise Unsupported("DataUnionOf de DataRanges complexes")
            dr = DataRange(union_of=[str(i) for i in items])
            used |= lu | {(n, _OWL.unionOf, un[0])}
        if dr is None or not own <= used:
            raise Unsupported("DataRange non reconnu (intersection, complément ou triplets supplémentaires)")
        return dr, used

    # ---- passes ----------------------------------------------------------------------------------
    def run(self) -> tuple[OntoModel, list[str]]:
        self.collect_prefixes()
        self.declarations()
        self.ontology_header()
        self.entities()
        self.axioms()
        self.individual_assertions()
        self.anonymous_axioms()
        self.annotations()
        self.collect_unmapped()
        return canonical_model(self.m), self.warnings

    def collect_prefixes(self) -> None:
        used_ns = set()
        for t in self.g:
            for x in t:
                if isinstance(x, URIRef):
                    used_ns.add(str(x))
                elif isinstance(x, Literal) and x.datatype:
                    used_ns.add(str(x.datatype))
        for pfx, ns in self.g.namespaces():
            ns = str(ns)
            if pfx == "xml":
                continue
            if ns in (RDF, RDFS, OWL, XSD):
                continue  # toujours liés par l'export : non significatifs
            if any(u.startswith(ns) for u in used_ns):
                self.m.meta.prefixes[pfx] = ns

    def declarations(self) -> None:
        g = self.g
        for s, o in g.subject_objects(T):
            if not isinstance(s, URIRef):
                continue
            o = str(o)
            if o == OWL + "Class":
                self.kinds[s].add("class")
            elif o == RDFS + "Class":
                self.kinds[s].add("class")
                self.warn("rdfs_class", s, "rdfs:Class traité comme owl:Class (OWL 2 Mapping §3.1 : rdfs:Class n'est pas une déclaration OWL 2).")
            elif o == RDFS + "Datatype":
                self.kinds[s].add("datatype")
            elif o == OWL + "ObjectProperty":
                self.kinds[s].add("object")
            elif o == OWL + "DatatypeProperty":
                self.kinds[s].add("data")
            elif o == OWL + "AnnotationProperty":
                self.kinds[s].add("annotation")
            elif o == OWL + "NamedIndividual":
                self.kinds[s].add("individual")
            elif o == OWL + "Ontology":
                self.kinds[s].add("ontology")
            elif o == OWL + "InverseFunctionalProperty" or o in CHARACTERISTICS and o != OWL + "FunctionalProperty":
                # caractéristiques réservées aux propriétés objet (Structural Spec §9.2)
                if not self.kinds[s] & {"object", "data"}:
                    self.kinds[s].add("object_implied")
        # rdf:Property non typée : inférence (portée datatype → data property)
        for s in set(g.subjects(T, _RDF.Property)):
            if not isinstance(s, URIRef) or self.kinds[s] & {"object", "data", "annotation"}:
                if isinstance(s, URIRef):
                    self.use((s, T, _RDF.Property))
                continue
            ranges = list(g.objects(s, _RDFS.range))
            objs = [o for _, o in g.subject_objects(s)]
            if any(self.is_datatype_node(r) for r in ranges) or (not ranges and objs and all(isinstance(o, Literal) for o in objs)):
                self.kinds[s].add("data")
                self.warn("untyped_property", s, "rdf:Property non typée : inférée owl:DatatypeProperty (portée datatype ou valeurs littérales).")
            elif ranges or (objs and all(isinstance(o, URIRef) for o in objs)):
                self.kinds[s].add("object")
                self.warn("untyped_property", s, "rdf:Property non typée : inférée owl:ObjectProperty (portée classe ou valeurs IRI).")
            else:
                self.kinds[s].add("annotation")
                self.warn("untyped_property", s, "rdf:Property non typée sans indice : traitée comme owl:AnnotationProperty.")
            self.use((s, T, _RDF.Property))
        for s, ks in self.kinds.items():
            if "object_implied" in ks:
                ks.discard("object_implied")
                if not ks & {"object", "data"}:
                    ks.add("object")
                    self.warn("undeclared_property", s, "caractéristique de propriété objet sans déclaration owl:ObjectProperty : déclaration inférée.")
        # individus typés par une classe sans owl:NamedIndividual
        for s, o in g.subject_objects(T):
            if isinstance(s, URIRef) and isinstance(o, URIRef) and (str(o) == OWL + "Thing" or (
                    str(o) not in DECL_TYPES and str(o) not in CHARACTERISTICS and not str(o).startswith(RESERVED_NS))):
                if "individual" not in self.kinds[s]:
                    self.kinds[s].add("individual")
                    self.warn("undeclared_individual", s, "individu typé sans déclaration owl:NamedIndividual.")
        # punning
        for s, ks in self.kinds.items():
            ents = ks & {"class", "datatype", "object", "data", "annotation", "individual"}
            if len(ents) > 1:
                bad = (len(ents & {"object", "data", "annotation"}) > 1) or ({"class", "datatype"} <= ents)
                level = "punning_illegal" if bad else "punning"
                self.warn(level, s, f"IRI utilisée comme {', '.join(sorted(ents))}"
                          + (" — interdit en OWL 2 DL (Structural Spec §5.9)." if bad else " (métamodélisation OWL 2, Structural Spec §5.9)."))

    def ontology_header(self) -> None:
        onts = sorted(s for s, ks in self.kinds.items() if "ontology" in ks)
        meta = self.m.meta
        if not onts:
            ns = self.m.meta.prefixes.get("")
            meta.iri = ns.rstrip("#/") if ns else ""
            if not meta.iri:
                counts: dict[str, int] = defaultdict(int)
                for s in self.kinds:
                    counts[re.sub(r"[^#/]*$", "", str(s))] += 1
                meta.iri = max(counts, key=counts.get).rstrip("#/") if counts else "urn:ontoforge:anonymous"
            self.warn("no_ontology_header", None, f"pas de déclaration owl:Ontology : IRI déduite « {meta.iri} ».")
            return
        if len(onts) > 1:
            self.warn("multiple_ontologies", onts[1], "plusieurs owl:Ontology : seule la première est retenue, les autres en non-mappé.")
        o = onts[0]
        meta.iri = str(o)
        self.use((o, T, _OWL.Ontology))
        for v in self.g.objects(o, _OWL.versionIRI):
            if isinstance(v, URIRef) and meta.version_iri is None:
                meta.version_iri = str(v)
                self.use((o, _OWL.versionIRI, v))
        for v in self.g.objects(o, _OWL.imports):
            if isinstance(v, URIRef):
                meta.imports.append(str(v))
                self.use((o, _OWL.imports, v))
                self.warn("unresolved_import", v, "owl:imports non résolu (travail hors-ligne) : la fermeture d'import n'est pas chargée.")

    def entity(self, s: URIRef):
        """Entités créées pour l'IRI (plusieurs en cas de punning)."""
        out = []
        ks = self.kinds.get(s, set())
        m, iri = self.m, str(s)
        if "class" in ks:
            out.append(m.classes.setdefault(iri, OntClass(iri=iri)))
        if "datatype" in ks:
            out.append(m.datatypes.setdefault(iri, DatatypeDef(iri=iri)))
        if "object" in ks:
            out.append(m.object_properties.setdefault(iri, ObjectProperty(iri=iri)))
        if "data" in ks:
            out.append(m.datatype_properties.setdefault(iri, DatatypeProperty(iri=iri)))
        if "annotation" in ks:
            out.append(m.annotation_properties.setdefault(iri, AnnotationProperty(iri=iri)))
        if "individual" in ks:
            out.append(m.individuals.setdefault(iri, Individual(iri=iri)))
        return out

    def entities(self) -> None:
        decl = {"class": OWL + "Class", "datatype": RDFS + "Datatype", "object": OWL + "ObjectProperty",
                "data": OWL + "DatatypeProperty", "annotation": OWL + "AnnotationProperty",
                "individual": OWL + "NamedIndividual"}
        for s in list(self.kinds):
            self.entity(s)
            for k in self.kinds[s]:
                if k in decl:
                    self.use((s, T, _u(decl[k])))
            if "class" in self.kinds[s]:
                self.use((s, T, _RDFS.Class))

    def ensure(self, iri, kind: str, why: str) -> None:
        """Référence à une entité non déclarée : création + warning (OWL 2 DL exige la déclaration)."""
        if not isinstance(iri, URIRef) or str(iri).startswith(RESERVED_NS):
            return
        if kind in self.kinds[iri]:
            return
        if kind == "class" and "datatype" in self.kinds[iri]:
            return
        self.kinds[iri].add(kind)
        self.entity(iri)
        self.warn("undeclared_entity", iri, f"{why} : entité non déclarée, déclaration ajoutée ({kind}).")

    # ---- axiomes sur entités nommées -------------------------------------------------------------
    def axioms(self) -> None:
        g, m = self.g, self.m
        for s, p, o in sorted(g):
            if not isinstance(s, URIRef):
                continue
            ks = self.kinds.get(s, set())
            t = (s, p, o)
            ps = str(p)
            try:
                if ps == RDFS + "subClassOf" and "class" in ks:
                    self._subclass(s, o, t)
                elif ps == OWL + "equivalentClass" and "class" in ks:
                    self._equivalent_class(s, o, t)
                elif ps == OWL + "equivalentClass" and "datatype" in ks:
                    dr, u = self.parse_data_range(o)
                    dd = m.datatypes[str(s)]
                    if dd.definition is not None:
                        raise Unsupported("plusieurs DatatypeDefinition")
                    dd.definition = dr
                    self.use(t, *u)
                elif ps == OWL + "disjointWith" and "class" in ks and isinstance(o, URIRef):
                    m.classes[str(s)].disjoint_with.append(str(o))
                    self.ensure(o, "class", "owl:disjointWith")
                    self.use(t)
                elif ps == OWL + "disjointUnionOf" and "class" in ks:
                    items, u = self.read_list(o)
                    if not all(isinstance(i, URIRef) for i in items):
                        raise Unsupported("DisjointUnion d'expressions anonymes")
                    m.classes[str(s)].disjoint_union_of.append([str(i) for i in items])
                    for i in items:
                        self.ensure(i, "class", "owl:disjointUnionOf")
                    self.use(t, *u)
                elif ps == OWL + "hasKey" and "class" in ks:
                    items, u = self.read_list(o)
                    if not all(isinstance(i, URIRef) for i in items):
                        raise Unsupported("HasKey sur expression de propriété anonyme")
                    m.classes[str(s)].has_keys.append([str(i) for i in items])
                    self.use(t, *u)
                elif ps == OWL + "oneOf" and "class" in ks:
                    items, u = self.read_list(o)
                    if not all(isinstance(i, URIRef) for i in items) or m.classes[str(s)].one_of is not None:
                        raise Unsupported("owl:oneOf non représentable")
                    m.classes[str(s)].one_of = [str(i) for i in items]
                    for i in items:
                        self.ensure(i, "individual", "membre de owl:oneOf")
                    self.warn("oneof_on_named_class", s, "owl:oneOf porté directement par une classe nommée (OWL 1) : relu comme EquivalentClasses(C ObjectOneOf(...)).")
                    self.use(t, *u)
                elif ps in (RDFS + "domain", RDFS + "range") and ks & {"object", "data", "annotation"}:
                    self._domain_range(s, ps, o, t, ks)
                elif ps == OWL + "inverseOf" and "object" in ks and isinstance(o, URIRef):
                    op = m.object_properties[str(s)]
                    if op.inverse_of is not None:
                        raise Unsupported("plusieurs owl:inverseOf (un seul représentable)")
                    op.inverse_of = str(o)
                    self.ensure(o, "object", "owl:inverseOf")
                    self.use(t)
                elif ps == RDF + "type" and str(o) in CHARACTERISTICS and ks & {"object", "data"}:
                    ch = CHARACTERISTICS[str(o)]
                    if "object" in ks:
                        m.object_properties[str(s)].characteristics.append(ch)
                        self.use(t)
                    if "data" in ks:
                        if ch == "functional":
                            m.datatype_properties[str(s)].functional = True
                            self.use(t)
                        else:
                            self.warn("illegal_characteristic", s, f"caractéristique « {ch} » sur une propriété de données : illégal en OWL 2 (Structural Spec §9.3), non mappé.")
                elif ps == RDFS + "subPropertyOf" and ks & {"object", "data", "annotation"} and isinstance(o, URIRef):
                    for e in self.entity(s):
                        if isinstance(e, (ObjectProperty, DatatypeProperty, AnnotationProperty)):
                            e.sub_property_of.append(str(o))
                    self.use(t)
                elif ps == OWL + "propertyChainAxiom" and "object" in ks:
                    items, u = self.read_list(o)
                    if not all(isinstance(i, URIRef) for i in items):
                        raise Unsupported("chaîne avec ObjectInverseOf (non représentable)")
                    m.object_properties[str(s)].chains.append([str(i) for i in items])
                    self.use(t, *u)
                elif ps == OWL + "equivalentProperty" and ks & {"object", "data"} and isinstance(o, URIRef):
                    for e in self.entity(s):
                        if isinstance(e, (ObjectProperty, DatatypeProperty)):
                            e.equivalent_to.append(str(o))
                    self.use(t)
                elif ps == OWL + "propertyDisjointWith" and ks & {"object", "data"} and isinstance(o, URIRef):
                    for e in self.entity(s):
                        if isinstance(e, (ObjectProperty, DatatypeProperty)):
                            e.disjoint_with.append(str(o))
                    self.use(t)
            except Unsupported as e:
                self.warn("unsupported_axiom", s, f"{p.n3(g.namespace_manager)} : {e} — conservé en non-mappé.")

    def _subclass(self, s, o, t) -> None:
        c = self.m.classes[str(s)]
        if isinstance(o, URIRef):
            c.sub_class_of.append(str(o))
            self.ensure(o, "class", "rdfs:subClassOf")
            self.use(t)
            return
        e, u = self.parse_ce(o)
        if e.op in ("some", "only", "min", "max", "exactly", "value", "self"):
            c.restrictions.append(_to_restriction(e))
        else:
            c.super_expressions.append(e)
        self.use(t, *u)

    def _equivalent_class(self, s, o, t) -> None:
        c = self.m.classes[str(s)]
        if isinstance(o, URIRef):
            c.equivalent_to.append(ClassExpr(op="named", iri=str(o)))
            self.ensure(o, "class", "owl:equivalentClass")
            self.use(t)
            return
        e, u = self.parse_ce(o)
        if e.op == "oneOf" and c.one_of is None:
            c.one_of = list(e.individuals)
            for i in e.individuals:
                self.ensure(_u(i), "individual", "membre de owl:oneOf")
        else:
            c.equivalent_to.append(e)
        self.use(t, *u)

    def _domain_range(self, s, ps, o, t, ks) -> None:
        m, iri = self.m, str(s)
        is_dom = ps.endswith("domain")
        if "annotation" in ks and isinstance(o, URIRef):
            ap = m.annotation_properties[iri]
            (ap.domain if is_dom else ap.range).append(str(o))
            self.use(t)
            return
        if "object" in ks or (is_dom and "data" in ks):
            ent = m.object_properties[iri] if "object" in ks else m.datatype_properties[iri]
            if isinstance(o, URIRef):
                (ent.domain if is_dom else ent.range).append(str(o))
                self.ensure(o, "class", "rdfs:domain" if is_dom else "rdfs:range")
                self.use(t)
                return
            e, u = self.parse_ce(o)
            union_field = "domain_union" if is_dom else "range_union"
            expr_field = "domain_expr" if is_dom else "range_expr"
            if e.op == "or" and all(a.op == "named" for a in e.args) and not getattr(ent, union_field):
                setattr(ent, union_field, [a.iri for a in e.args])
                for a in e.args:
                    self.ensure(_u(a.iri), "class", "unionOf de domaine/portée")
            elif getattr(ent, expr_field) is None:
                setattr(ent, expr_field, e)
            else:
                raise Unsupported("plusieurs domaines/portées complexes")
            self.use(t, *u)
            return
        if "data" in ks:  # portée de propriété de données
            dp = m.datatype_properties[iri]
            if isinstance(o, URIRef):
                dp.range.append(str(o))
                if not is_builtin_datatype(str(o)) and "datatype" not in self.kinds.get(o, set()):
                    self.ensure(o, "datatype", "rdfs:range de propriété de données")
                self.use(t)
                return
            if dp.range_expr is not None:
                raise Unsupported("plusieurs portées DataRange complexes")
            dr, u = self.parse_data_range(o)
            dp.range_expr = dr
            self.use(t, *u)

    # ---- assertions ------------------------------------------------------------------------------
    def individual_assertions(self) -> None:
        g, m = self.g, self.m
        for s, p, o in sorted(g):
            if not isinstance(s, URIRef) or (s, p, o) in self.consumed:
                continue
            ks = self.kinds.get(s, set())
            ps = str(p)
            if ps == RDF + "type" and "individual" in ks:
                if isinstance(o, URIRef) and (str(o) == OWL + "Thing" or (
                        str(o) not in DECL_TYPES and not str(o).startswith(RESERVED_NS))):
                    m.individuals[str(s)].types.append(str(o))
                    self.ensure(o, "class", "rdf:type d'individu")
                    self.use((s, p, o))
                elif isinstance(o, BNode):
                    self.warn("unsupported_axiom", s, "ClassAssertion sur expression anonyme : conservé en non-mappé.")
                continue
            if ps in (OWL + "sameAs", OWL + "differentFrom") and isinstance(o, URIRef):
                if "individual" not in ks:
                    self.kinds[s].add("individual")
                    self.entity(s)
                    self.warn("undeclared_individual", s, f"{ps.split('#')[1]} sur une IRI non déclarée comme individu.")
                self.ensure(o, "individual", ps.split("#")[1])
                ind = m.individuals[str(s)]
                (ind.same_as if ps.endswith("sameAs") else ind.different_from).append(str(o))
                self.use((s, p, o))
                continue
            pk = self.kinds.get(p, set())
            if ps.startswith(RESERVED_NS) or "annotation" in pk or ps in BUILTIN_ANNOTATION_PROPERTIES:
                continue
            if not pk & {"object", "data"}:
                if ps.startswith(ANNOTATION_NAMESPACES):
                    continue
                if "individual" not in ks:
                    continue  # annotation non déclarée sur une entité (traitée en passe annotations)
                self.warn("undeclared_property", p, "propriété non déclarée utilisée dans une assertion : fait conservé, typage inconnu.")
            if "individual" not in ks:
                if ks:
                    self.kinds[s].add("individual")
                    self.entity(s)
                    self.warn("punning", s, "entité utilisée comme sujet d'une assertion de propriété : individu (punning) ajouté.")
                else:
                    self.kinds[s].add("individual")
                    self.entity(s)
                    self.warn("undeclared_individual", s, "sujet d'assertion non déclaré : individu ajouté.")
            ind = m.individuals[str(s)]
            if isinstance(o, URIRef):
                ind.facts.append(Fact(property=ps, value=str(o), is_iri=True))
                if "object" in pk:
                    self.ensure(o, "individual", "objet d'une assertion de propriété objet")
            elif isinstance(o, Literal):
                v, dt, la = _lit(o)
                ind.facts.append(Fact(property=ps, value=v, datatype=dt, lang=la))
            else:
                self.warn("anonymous_individual", s, f"valeur anonyme (nœud blanc) pour {p.n3(g.namespace_manager)} : individu anonyme non représentable, conservé en non-mappé.")
                continue
            self.use((s, p, o))

    def anonymous_axioms(self) -> None:
        """Axiomes portés par un nœud blanc racine : AllDisjointClasses, AllDifferent, NegativePropertyAssertion…"""
        g, m = self.g, self.m
        for n in sorted(set(s for s in g.subjects() if isinstance(s, BNode))):
            types = set(g.objects(n, T))
            own = self.bnode_triples(n)
            try:
                if _OWL.AllDisjointClasses in types or _OWL.AllDisjointProperties in types:
                    lsts = list(g.objects(n, _OWL.members))
                    if len(lsts) != 1 or len(own) != 2:
                        raise Unsupported("AllDisjoint* mal formé")
                    items, u = self.read_list(lsts[0])
                    if not all(isinstance(i, URIRef) for i in items):
                        raise Unsupported("AllDisjointClasses d'expressions anonymes")
                    for i, a in enumerate(items):
                        for b in items[i + 1:]:
                            if _OWL.AllDisjointClasses in types:
                                self.ensure(a, "class", "owl:AllDisjointClasses")
                                m.classes[str(a)].disjoint_with.append(str(b))
                            else:
                                for e in self.entity(a):
                                    if isinstance(e, (ObjectProperty, DatatypeProperty)):
                                        e.disjoint_with.append(str(b))
                    kind = "AllDisjointClasses" if _OWL.AllDisjointClasses in types else "AllDisjointProperties"
                    self.warn("nary_disjoint_expanded", None, f"owl:{kind} ({len(items)} membres) relu en disjonctions par paires (sémantique équivalente ; la forme n-aire n'est pas conservée à l'export).")
                    self.use(*own, *u)
                elif _OWL.AllDifferent in types:
                    lsts = list(g.objects(n, _OWL.distinctMembers)) + list(g.objects(n, _OWL.members))
                    if len(lsts) != 1 or len(own) != 2:
                        raise Unsupported("AllDifferent mal formé")
                    items, u = self.read_list(lsts[0])
                    if not all(isinstance(i, URIRef) for i in items):
                        raise Unsupported("AllDifferent avec individus anonymes")
                    for i in items:
                        self.ensure(i, "individual", "owl:AllDifferent")
                    m.all_different.append([str(i) for i in items])
                    self.use(*own, *u)
                elif _OWL.NegativePropertyAssertion in types:
                    src = list(g.objects(n, _OWL.sourceIndividual))
                    prop = list(g.objects(n, _OWL.assertionProperty))
                    ti = list(g.objects(n, _OWL.targetIndividual))
                    tv = list(g.objects(n, _OWL.targetValue))
                    if len(src) != 1 or len(prop) != 1 or len(ti) + len(tv) != 1 or len(own) != 4 \
                            or not isinstance(src[0], URIRef) or not isinstance(prop[0], URIRef):
                        raise Unsupported("NegativePropertyAssertion mal formée")
                    self.ensure(src[0], "individual", "owl:sourceIndividual")
                    ind = m.individuals[str(src[0])]
                    if ti:
                        if not isinstance(ti[0], URIRef):
                            raise Unsupported("cible anonyme")
                        ind.facts.append(Fact(property=str(prop[0]), value=str(ti[0]), is_iri=True, negative=True))
                    else:
                        if not isinstance(tv[0], Literal):
                            raise Unsupported("owl:targetValue non littéral")
                        v, dt, la = _lit(tv[0])
                        ind.facts.append(Fact(property=str(prop[0]), value=v, datatype=dt, lang=la, negative=True))
                    self.use(*own)
            except Unsupported as e:
                self.warn("unsupported_axiom", None, f"axiome anonyme : {e} — conservé en non-mappé.")

    # ---- annotations -----------------------------------------------------------------------------
    def annotations(self) -> None:
        g, m = self.g, self.m
        for s in sorted(set(x for x in g.subjects() if isinstance(x, URIRef))):
            targets: list = list(self.entity(s))
            if "ontology" in self.kinds.get(s, set()) and str(s) == m.meta.iri:
                targets.append(m.meta)
            if not targets:
                continue
            labels: dict[str, list[Literal]] = defaultdict(list)
            for p, o in sorted(g.predicate_objects(s)):
                t = (s, p, o)
                if t in self.consumed:
                    continue
                ps = str(p)
                pk = self.kinds.get(p, set())
                if pk & {"object", "data"} or (ps.startswith(RESERVED_NS) and ps not in BUILTIN_ANNOTATION_PROPERTIES):
                    continue
                if isinstance(o, BNode):
                    continue
                if ps == OWL + "deprecated" and _is_true(o):
                    for e in targets:
                        e.deprecated = True
                    self.use(t)
                    continue
                if ps in (RDFS + "label", RDFS + "comment") and isinstance(o, Literal) and o.datatype is None:
                    labels[ps].append(o)
                    continue
                if "annotation" not in pk and ps not in BUILTIN_ANNOTATION_PROPERTIES:
                    if not ps.startswith(ANNOTATION_NAMESPACES):
                        self.warn("undeclared_annotation_property", p, "propriété non déclarée utilisée comme annotation (OWL 2 DL exige owl:AnnotationProperty).")
                    else:
                        self.warn("undeclared_annotation_property", p, "propriété d'annotation non déclarée (OWL 2 DL : déclarer owl:AnnotationProperty).")
                    self.kinds[p].add("annotation_used")
                for e in targets:
                    e.annotations.append(_annotation(ps, o))
                self.use(t)
            for ps, lits in labels.items():
                field = "labels" if ps.endswith("label") else "comments"
                for lit in sorted(lits, key=lambda x: (x.language or "", str(x))):
                    lang = lit.language or ""
                    for e in targets:
                        d = getattr(e, field)
                        if lang in d and d[lang] != str(lit):
                            e.annotations.append(_annotation(ps, lit))
                        else:
                            d[lang] = str(lit)
                    self.use((s, _u(ps), lit))
        # déduplication des warnings « non déclarée »
        seen, out = set(), []
        for w in self.warnings:
            if w.startswith("[undeclared_annotation_property]") and w in seen:
                continue
            seen.add(w)
            out.append(w)
        self.warnings = out

    def collect_unmapped(self) -> None:
        rest = rdflib.Graph()
        for t in self.g:
            if t not in self.consumed:
                rest.add(t)
        if not len(rest):
            return
        canon = to_canonical_graph(rest)  # labels de nœuds blancs déterministes (round-trip stable)
        objs_b = {o for _, _, o in canon if isinstance(o, BNode)}
        roots = sorted({s for s in canon.subjects() if not (isinstance(s, BNode) and s in objs_b)}, key=str)
        assigned: set = set()

        def closure(node, acc):
            for p, o in sorted(canon.predicate_objects(node)):
                t = (node, p, o)
                if t in assigned:
                    continue
                assigned.add(t)
                acc.append(t)
                if isinstance(o, BNode):
                    closure(o, acc)

        groups = []
        for r in roots:
            acc: list = []
            closure(r, acc)
            if acc:
                groups.append((r, acc))
        left = [t for t in sorted(canon) if t not in assigned]  # cycles de nœuds blancs
        if left:
            groups.append((left[0][0], left))
        nsm = self.g.namespace_manager
        for subj, triples in groups:
            subject = None if isinstance(subj, BNode) else str(subj)
            preds = sorted({_short(p) for _, p, _ in triples})
            desc = f"{len(triples)} triplet(s) non mappé(s) ({', '.join(preds[:6])}{'…' if len(preds) > 6 else ''})"
            self.m.unmapped.append(UnmappedAxiom(
                description=desc, subject=subject,
                triples=[(s.n3(), p.n3(), o.n3()) for s, p, o in triples]))
            self.warn("unmapped_triple", subj, desc + " — conservé dans `unmapped`, réémis à l'export.")


def _annotation(ps: str, o) -> Annotation:
    if isinstance(o, Literal):
        v, dt, la = _lit(o)
        return Annotation(property=ps, value=v, datatype=dt, lang=la)
    return Annotation(property=ps, value=str(o), is_iri=True)


def _to_restriction(e: ClassExpr) -> Restriction:
    r = Restriction(property=e.property, inverse=e.inverse, kind=e.op, n=e.n, value=e.value)
    if e.data_range:
        r.filler = e.data_range
    elif e.filler is not None:
        if e.filler.op == "named":
            r.filler = e.filler.iri
        else:
            r.filler_expr = e.filler
    return r


def graph_to_model(g: rdflib.Graph) -> tuple[OntoModel, list[str]]:
    return _Reader(g).run()


# --------------------------------------------------------------------------------------------------
# Forme canonique (comparaison modulo l'ordre des collections ensemblistes)
# --------------------------------------------------------------------------------------------------
def _key(x) -> str:
    return x.model_dump_json() if hasattr(x, "model_dump_json") else repr(x)


def _uniq_sorted(xs: Iterable, key=_key) -> list:
    out, seen = [], set()
    for x in sorted(xs, key=key):
        k = key(x)
        if k not in seen:
            seen.add(k)
            out.append(x)
    return out


def canonical_model(m: OntoModel) -> OntoModel:
    """Copie de `m` où les collections à sémantique d'ensemble sont triées et dédoublonnées.

    L'ordre des listes RDF (chaînes, clés, unions, oneOf) est conservé : il est porteur de sens ou
    du moins de la forme de l'axiome. `graph_to_model(model_to_graph(m)) == canonical_model(m)`.
    """
    m = m.model_copy(deep=True)
    def ents():
        for coll in (m.classes, m.object_properties, m.datatype_properties, m.annotation_properties,
                     m.datatypes, m.individuals):
            yield from coll.values()
        yield m.meta
    for e in ents():
        e.annotations = _uniq_sorted(e.annotations)
        for f in ("sub_class_of", "disjoint_with", "domain", "range", "sub_property_of", "types", "same_as",
                  "different_from", "imports"):
            if hasattr(e, f):
                setattr(e, f, sorted(set(getattr(e, f))))
        for f in ("restrictions", "super_expressions", "facts"):
            if hasattr(e, f):
                setattr(e, f, _uniq_sorted(getattr(e, f)))
        if isinstance(e, OntClass):
            e.equivalent_to = _uniq_sorted(e.equivalent_to)
            e.disjoint_union_of = _uniq_sorted(e.disjoint_union_of, key=repr)
            e.has_keys = _uniq_sorted(e.has_keys, key=repr)
        if isinstance(e, (ObjectProperty, DatatypeProperty)):
            e.equivalent_to = sorted(set(e.equivalent_to))
        if isinstance(e, ObjectProperty):
            e.chains = _uniq_sorted(e.chains, key=repr)
            order = ["functional", "inverseFunctional", "transitive", "symmetric", "asymmetric", "reflexive", "irreflexive"]
            e.characteristics = sorted(set(e.characteristics), key=order.index)
    m.all_different = _uniq_sorted(m.all_different, key=repr)
    m.unmapped = _uniq_sorted(m.unmapped)
    return m
