"""Export OntoModel → RDF (OWL 2 Mapping to RDF Graphs, direction directe : tables 1 à 16).

`model_to_graph(m)` produit un graphe conforme au mapping OWL 2 ; `serialize(m, format)` le sérialise en
Turtle, RDF/XML (forme « pretty » lisible) ou JSON-LD (compacté avec les préfixes du modèle).

Les triplets de `m.unmapped` sont réémis tels quels : `graph_to_model(model_to_graph(m))` redonne
`canonical_model(m)` (comparaison modulo l'ordre des collections ensemblistes).
"""
from __future__ import annotations

from typing import Optional

import rdflib
from rdflib import BNode, Literal, URIRef
from rdflib.collection import Collection
from rdflib.compare import isomorphic
from rdflib.namespace import OWL as _OWL, RDF as _RDF, RDFS as _RDFS, XSD as _XSD

from ..core.onto_model import (
    Annotation, ClassExpr, DataRange, Entity, LiteralValue, OntoModel, Restriction, OWL, RDF, RDFS, XSD,
)
from .rdf_import import is_builtin_datatype

__all__ = ["model_to_graph", "serialize", "FORMATS"]

T = _RDF.type
FORMATS = {"turtle": "turtle", "ttl": "turtle", "xml": "pretty-xml", "rdfxml": "pretty-xml",
           "rdf/xml": "pretty-xml", "pretty-xml": "pretty-xml", "json-ld": "json-ld", "jsonld": "json-ld",
           "nt": "nt", "ntriples": "nt"}
CHAR_IRI = {
    "functional": _OWL.FunctionalProperty, "inverseFunctional": _OWL.InverseFunctionalProperty,
    "transitive": _OWL.TransitiveProperty, "symmetric": _OWL.SymmetricProperty,
    "asymmetric": _OWL.AsymmetricProperty, "reflexive": _OWL.ReflexiveProperty,
    "irreflexive": _OWL.IrreflexiveProperty,
}
CARD = {("min", False): _OWL.minCardinality, ("max", False): _OWL.maxCardinality,
        ("exactly", False): _OWL.cardinality, ("min", True): _OWL.minQualifiedCardinality,
        ("max", True): _OWL.maxQualifiedCardinality, ("exactly", True): _OWL.qualifiedCardinality}
# Facettes dont la valeur n'est pas du type de base (XML Schema Datatypes §4.3)
FACET_INT = {XSD + "length", XSD + "minLength", XSD + "maxLength", XSD + "totalDigits", XSD + "fractionDigits"}
FACET_STR = {XSD + "pattern", RDF + "langRange"}


def _lit(v: str, datatype: Optional[str], lang: Optional[str]) -> Literal:
    if lang:
        return Literal(v, lang=lang)
    return Literal(v, datatype=URIRef(datatype) if datatype else None)


class _Writer:
    def __init__(self, m: OntoModel):
        self.m = m
        self.g = rdflib.Graph(bind_namespaces="core")
        for pfx, ns in m.meta.prefixes.items():
            self.g.bind(pfx, URIRef(ns), override=True, replace=True)

    def add(self, s, p, o) -> None:
        self.g.add((s, p, o))

    def lst(self, items) -> BNode:
        head = BNode()
        Collection(self.g, head, list(items))
        if not items:
            return _RDF.nil  # type: ignore[return-value]
        return head

    def is_data(self, prop: str, filler: Optional[str]) -> bool:
        if prop in self.m.datatype_properties:
            return True
        if prop in self.m.object_properties:
            return False
        return bool(filler) and (is_builtin_datatype(filler) or filler in self.m.datatypes)

    # ---- expressions -----------------------------------------------------------------------------
    def ce(self, e: ClassExpr):
        if e.op == "named":
            return URIRef(e.iri)
        n = BNode()
        if e.op in ("and", "or"):
            self.add(n, T, _OWL.Class)
            self.add(n, _OWL.intersectionOf if e.op == "and" else _OWL.unionOf, self.lst([self.ce(a) for a in e.args]))
        elif e.op == "not":
            self.add(n, T, _OWL.Class)
            self.add(n, _OWL.complementOf, self.ce(e.args[0]))
        elif e.op == "oneOf":
            self.add(n, T, _OWL.Class)
            self.add(n, _OWL.oneOf, self.lst([URIRef(i) for i in e.individuals]))
        else:
            self.restriction(n, e.property, e.inverse, e.op, e.n,
                             filler=self.ce(e.filler) if e.filler is not None else None,
                             data_range=e.data_range, value=e.value)
        return n

    def prop_expr(self, prop: str, inverse: bool):
        if not inverse:
            return URIRef(prop)
        b = BNode()
        self.add(b, _OWL.inverseOf, URIRef(prop))
        return b

    def restriction(self, n, prop, inverse, kind, num, filler=None, data_range=None, value=None) -> None:
        self.add(n, T, _OWL.Restriction)
        self.add(n, _OWL.onProperty, self.prop_expr(prop, inverse))
        target = filler if filler is not None else (URIRef(data_range) if data_range else None)
        if kind in ("some", "only"):
            self.add(n, _OWL.someValuesFrom if kind == "some" else _OWL.allValuesFrom,
                     target if target is not None else _OWL.Thing)
        elif kind == "value":
            if isinstance(value, LiteralValue):
                self.add(n, _OWL.hasValue, _lit(value.value, value.datatype, value.lang))
            else:
                self.add(n, _OWL.hasValue, URIRef(str(value)))
        elif kind == "self":
            self.add(n, _OWL.hasSelf, Literal(True))
        else:
            qualified = target is not None
            self.add(n, CARD[(kind, qualified)], Literal(str(num if num is not None else 0), datatype=_XSD.nonNegativeInteger))
            if qualified:
                self.add(n, _OWL.onDataRange if data_range else _OWL.onClass, target)

    def flat_restriction(self, r: Restriction):
        n = BNode()
        if r.filler_expr is not None:
            self.restriction(n, r.property, r.inverse, r.kind, r.n, filler=self.ce(r.filler_expr), value=r.value)
        elif r.filler and self.is_data(r.property, r.filler):
            self.restriction(n, r.property, r.inverse, r.kind, r.n, data_range=r.filler, value=r.value)
        else:
            self.restriction(n, r.property, r.inverse, r.kind, r.n,
                             filler=URIRef(r.filler) if r.filler else None, value=r.value)
        return n

    def data_range(self, d: DataRange):
        if d.facets:
            n = BNode()
            self.add(n, T, _RDFS.Datatype)
            self.add(n, _OWL.onDatatype, URIRef(d.base))
            facets = []
            for f, v in d.facets.items():
                fb = BNode()
                dt = XSD + "nonNegativeInteger" if f in FACET_INT else (XSD + "string" if f in FACET_STR else d.base)
                lit = Literal(v) if f in FACET_STR else Literal(v, datatype=URIRef(dt))
                self.add(fb, URIRef(f), lit)
                facets.append(fb)
            self.add(n, _OWL.withRestrictions, self.lst(facets))
            return n
        if d.one_of:
            n = BNode()
            self.add(n, T, _RDFS.Datatype)
            self.add(n, _OWL.oneOf, self.lst([_lit(x.value, x.datatype, x.lang) for x in d.one_of]))
            return n
        if d.union_of:
            n = BNode()
            self.add(n, T, _RDFS.Datatype)
            self.add(n, _OWL.unionOf, self.lst([URIRef(x) for x in d.union_of]))
            return n
        return URIRef(d.base) if d.base else _RDFS.Literal

    # ---- entités ---------------------------------------------------------------------------------
    def annotate(self, s: URIRef, e: Entity) -> None:
        for lang, v in e.labels.items():
            self.add(s, _RDFS.label, Literal(v, lang=lang or None))
        for lang, v in e.comments.items():
            self.add(s, _RDFS.comment, Literal(v, lang=lang or None))
        for a in e.annotations:
            self.add(s, URIRef(a.property), URIRef(a.value) if a.is_iri else _lit(a.value, a.datatype, a.lang))
        if e.deprecated:
            self.add(s, _OWL.deprecated, Literal(True))

    def run(self) -> rdflib.Graph:
        m, add = self.m, self.add
        if m.meta.iri:
            o = URIRef(m.meta.iri)
            add(o, T, _OWL.Ontology)
            if m.meta.version_iri:
                add(o, _OWL.versionIRI, URIRef(m.meta.version_iri))
            for i in m.meta.imports:
                add(o, _OWL.imports, URIRef(i))
            self.annotate(o, m.meta)
        for iri, ap in m.annotation_properties.items():
            s = URIRef(iri)
            add(s, T, _OWL.AnnotationProperty)
            for x in ap.sub_property_of:
                add(s, _RDFS.subPropertyOf, URIRef(x))
            for x in ap.domain:
                add(s, _RDFS.domain, URIRef(x))
            for x in ap.range:
                add(s, _RDFS.range, URIRef(x))
            self.annotate(s, ap)
        for iri, dt in m.datatypes.items():
            s = URIRef(iri)
            add(s, T, _RDFS.Datatype)
            if dt.definition is not None:
                add(s, _OWL.equivalentClass, self.data_range(dt.definition))
            self.annotate(s, dt)
        for iri, c in m.classes.items():
            s = URIRef(iri)
            add(s, T, _OWL.Class)
            for x in c.sub_class_of:
                add(s, _RDFS.subClassOf, URIRef(x))
            for r in c.restrictions:
                add(s, _RDFS.subClassOf, self.flat_restriction(r))
            for e in c.super_expressions:
                add(s, _RDFS.subClassOf, self.ce(e))
            for e in c.equivalent_to:
                add(s, _OWL.equivalentClass, self.ce(e))
            if c.one_of is not None:
                add(s, _OWL.equivalentClass, self.ce(ClassExpr(op="oneOf", individuals=c.one_of)))
            for x in c.disjoint_with:
                add(s, _OWL.disjointWith, URIRef(x))
            for u in c.disjoint_union_of:
                add(s, _OWL.disjointUnionOf, self.lst([URIRef(x) for x in u]))
            for k in c.has_keys:
                add(s, _OWL.hasKey, self.lst([URIRef(x) for x in k]))
            self.annotate(s, c)
        for iri, p in m.object_properties.items():
            s = URIRef(iri)
            add(s, T, _OWL.ObjectProperty)
            for ch in p.characteristics:
                add(s, T, CHAR_IRI[ch])
            for x in p.domain:
                add(s, _RDFS.domain, URIRef(x))
            for x in p.range:
                add(s, _RDFS.range, URIRef(x))
            if p.domain_union:
                add(s, _RDFS.domain, self.ce(ClassExpr(op="or", args=[ClassExpr(op="named", iri=x) for x in p.domain_union])))
            if p.range_union:
                add(s, _RDFS.range, self.ce(ClassExpr(op="or", args=[ClassExpr(op="named", iri=x) for x in p.range_union])))
            if p.domain_expr is not None:
                add(s, _RDFS.domain, self.ce(p.domain_expr))
            if p.range_expr is not None:
                add(s, _RDFS.range, self.ce(p.range_expr))
            if p.inverse_of:
                add(s, _OWL.inverseOf, URIRef(p.inverse_of))
            for x in p.sub_property_of:
                add(s, _RDFS.subPropertyOf, URIRef(x))
            for x in p.equivalent_to:
                add(s, _OWL.equivalentProperty, URIRef(x))
            for x in p.disjoint_with:
                add(s, _OWL.propertyDisjointWith, URIRef(x))
            for ch in p.chains:
                add(s, _OWL.propertyChainAxiom, self.lst([URIRef(x) for x in ch]))
            self.annotate(s, p)
        for iri, p in m.datatype_properties.items():
            s = URIRef(iri)
            add(s, T, _OWL.DatatypeProperty)
            if p.functional:
                add(s, T, _OWL.FunctionalProperty)
            for x in p.domain:
                add(s, _RDFS.domain, URIRef(x))
            if p.domain_union:
                add(s, _RDFS.domain, self.ce(ClassExpr(op="or", args=[ClassExpr(op="named", iri=x) for x in p.domain_union])))
            if p.domain_expr is not None:
                add(s, _RDFS.domain, self.ce(p.domain_expr))
            for x in p.range:
                add(s, _RDFS.range, URIRef(x))
            if p.range_expr is not None:
                add(s, _RDFS.range, self.data_range(p.range_expr))
            for x in p.sub_property_of:
                add(s, _RDFS.subPropertyOf, URIRef(x))
            for x in p.equivalent_to:
                add(s, _OWL.equivalentProperty, URIRef(x))
            for x in p.disjoint_with:
                add(s, _OWL.propertyDisjointWith, URIRef(x))
            self.annotate(s, p)
        for iri, ind in m.individuals.items():
            s = URIRef(iri)
            add(s, T, _OWL.NamedIndividual)
            for t in ind.types:
                add(s, T, URIRef(t))
            for f in ind.facts:
                val = URIRef(f.value) if f.is_iri else _lit(f.value, f.datatype, f.lang)
                if f.negative:
                    n = BNode()
                    add(n, T, _OWL.NegativePropertyAssertion)
                    add(n, _OWL.sourceIndividual, s)
                    add(n, _OWL.assertionProperty, URIRef(f.property))
                    add(n, _OWL.targetIndividual if f.is_iri else _OWL.targetValue, val)
                else:
                    add(s, URIRef(f.property), val)
            for x in ind.same_as:
                add(s, _OWL.sameAs, URIRef(x))
            for x in ind.different_from:
                add(s, _OWL.differentFrom, URIRef(x))
            self.annotate(s, ind)
        for members in m.all_different:
            n = BNode()
            add(n, T, _OWL.AllDifferent)
            add(n, _OWL.members, self.lst([URIRef(x) for x in members]))  # Mapping table 16 (owl:members)
        if m.unmapped:
            nt = "\n".join(" ".join(t) + " ." for u in m.unmapped for t in u.triples)
            extra = rdflib.Graph()
            extra.parse(data=nt, format="nt")
            for t in extra:
                self.g.add(t)
        return self.g


def model_to_graph(m: OntoModel) -> rdflib.Graph:
    return _Writer(m).run()


def serialize(m: OntoModel, format: str = "turtle") -> str:
    fmt = FORMATS.get(format.lower())
    if not fmt:
        raise ValueError(f"Format d'export inconnu : {format!r} (turtle, xml, json-ld, nt).")
    g = model_to_graph(m)
    if fmt == "json-ld":
        ctx = {p: ns for p, ns in m.meta.prefixes.items() if p}
        for p, ns in (("owl", OWL), ("rdf", RDF), ("rdfs", RDFS), ("xsd", XSD)):
            ctx.setdefault(p, ns)
        return g.serialize(format="json-ld", context=ctx, indent=2)
    if fmt == "pretty-xml":
        try:
            out = g.serialize(format="pretty-xml")
            if not isomorphic(rdflib.Graph().parse(data=out, format="xml"), g):
                raise ValueError("pretty-xml non fidèle")
        except Exception:  # noqa: BLE001 — limite du sérialiseur rdflib (ex. rdf:type vers un nœud blanc)
            out = g.serialize(format="xml")
        return out
    out = g.serialize(format=fmt)
    if fmt == "turtle":
        header = f"# OntoForge — export Turtle de <{m.meta.iri}>\n" if m.meta.iri else ""
        return header + out
    return out
