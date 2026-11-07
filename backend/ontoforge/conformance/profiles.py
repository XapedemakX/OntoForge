"""Conformité OWL 2 : contrôles structurels DL (Structural Specification) et profils EL / QL / RL.

Travaille sur le graphe RDF (rdflib) : c'est la seule représentation qui conserve tout ce que la
spécification demande de vérifier (déclarations, punning, expressions anonymes, littéraux typés).
Si aucun graphe n'est fourni, il est reconstruit depuis l'OntoModel (io.rdf_export).

Références : OWL 2 Structural Specification (SS), OWL 2 Mapping to RDF Graphs (MAP), OWL 2 Profiles (PROF).
Les codes d'issues W01–W05 sont documentés dans skills/w3c-ontology-conformance/SKILL.md.
"""
from __future__ import annotations

from typing import Optional

import rdflib
from rdflib import BNode, Literal, URIRef
from rdflib.namespace import OWL, RDF, RDFS, XSD

from ..core.onto_model import OntoModel, local_name
from .report import PROFILE_NAMES, ConformanceReport, Issue

SS = "OWL 2 Structural Specification"
PROF = "OWL 2 Profiles"
MAP = "OWL 2 Mapping to RDF Graphs"

RESERVED_NS = (str(RDF), str(RDFS), str(OWL), str(XSD))

# --- Carte des datatypes OWL 2 (SS §4.1-4.3) ---------------------------------------------------
_X = lambda *n: {str(XSD) + x for x in n}  # noqa: E731
_INTS = _X("integer", "nonNegativeInteger", "nonPositiveInteger", "positiveInteger", "negativeInteger",
           "long", "int", "short", "byte", "unsignedLong", "unsignedInt", "unsignedShort", "unsignedByte")
_STRS = _X("string", "normalizedString", "token", "language", "Name", "NCName", "NMTOKEN")
OWL2_DATATYPE_MAP: set[str] = (
    {str(RDF) + "PlainLiteral", str(RDF) + "XMLLiteral", str(RDFS) + "Literal", str(OWL) + "real", str(OWL) + "rational"}
    | _X("decimal", "double", "float", "boolean", "hexBinary", "base64Binary", "anyURI", "dateTime", "dateTimeStamp")
    | _INTS | _STRS
)
_EL_QL_DT = (
    {str(RDF) + "PlainLiteral", str(RDF) + "XMLLiteral", str(RDFS) + "Literal", str(OWL) + "real", str(OWL) + "rational"}
    | _X("decimal", "integer", "nonNegativeInteger", "string", "normalizedString", "token", "Name", "NCName",
         "NMTOKEN", "hexBinary", "base64Binary", "anyURI", "dateTime", "dateTimeStamp")
)
_RL_DT = OWL2_DATATYPE_MAP - {str(OWL) + "real", str(OWL) + "rational"}
PROFILE_DATATYPES = {"EL": _EL_QL_DT, "QL": _EL_QL_DT, "RL": _RL_DT}

CHARACTERISTICS = {
    "FunctionalProperty": "fonctionnelle", "InverseFunctionalProperty": "inverse-fonctionnelle",
    "TransitiveProperty": "transitive", "SymmetricProperty": "symétrique", "AsymmetricProperty": "asymétrique",
    "ReflexiveProperty": "réflexive", "IrreflexiveProperty": "irréflexive",
}
# SS §11.2 : ces axiomes exigent des propriétés simples
SIMPLE_REQUIRED = {"FunctionalProperty", "InverseFunctionalProperty", "AsymmetricProperty", "IrreflexiveProperty"}


def _n(x) -> str:
    return "axiome anonyme" if isinstance(x, BNode) else local_name(str(x))


def _is_reserved(iri) -> bool:
    return isinstance(iri, URIRef) and str(iri).startswith(RESERVED_NS)


# =================================================================================================
# Lecture du graphe : listes, expressions de classes
# =================================================================================================
def rdf_list(g: rdflib.Graph, head) -> list:
    out, seen = [], set()
    while head is not None and head != RDF.nil and head not in seen:
        seen.add(head)
        first = g.value(head, RDF.first)
        if first is not None:
            out.append(first)
        head = g.value(head, RDF.rest)
    return out


class Ctx:
    """Index du graphe : types de propriétés, datatypes déclarés."""

    def __init__(self, g: rdflib.Graph):
        self.g = g
        self.obj_props = set(g.subjects(RDF.type, OWL.ObjectProperty))
        self.data_props = set(g.subjects(RDF.type, OWL.DatatypeProperty))
        self.ann_props = set(g.subjects(RDF.type, OWL.AnnotationProperty))
        self.datatypes = set(g.subjects(RDF.type, RDFS.Datatype))
        self.classes = set(g.subjects(RDF.type, OWL.Class))

    def is_datatype_iri(self, x) -> bool:
        if not isinstance(x, URIRef):
            return False
        s = str(x)
        return (s.startswith(str(XSD)) or s in OWL2_DATATYPE_MAP or s == str(RDF.langString) or x in self.datatypes)


def parse_ce(ctx: Ctx, n, depth: int = 0):
    """Expression de classe ou de datatype → arbre de tuples.

    ('class', iri) | ('and'|'or', [..]) | ('not', e) | ('oneOf', [..]) | ('svf'|'avf', (p, inv), filler, is_data)
    | ('value', (p, inv), is_data) | ('self', (p, inv)) | ('card', kind, n, (p, inv), filler|None, is_data)
    | ('dtrestr', base) | ('other', description)
    """
    g = ctx.g
    if isinstance(n, URIRef):
        return ("class", str(n))
    if isinstance(n, Literal) or depth > 25:
        return ("other", "expression illisible")
    if (n, RDF.type, OWL.Restriction) in g or g.value(n, OWL.onProperty) is not None or g.value(n, OWL.onProperties):
        if g.value(n, OWL.onProperties) is not None:
            return ("other", "restriction n-aire (owl:onProperties)")
        p = _prop(g, g.value(n, OWL.onProperty))
        if p is None:
            return ("other", "restriction sans owl:onProperty")
        for pred, kind in ((OWL.someValuesFrom, "svf"), (OWL.allValuesFrom, "avf")):
            f = g.value(n, pred)
            if f is not None:
                fe = parse_ce(ctx, f, depth + 1)
                return (kind, p, fe, _is_data(ctx, p, f, fe))
        if g.value(n, OWL.hasValue) is not None:
            v = g.value(n, OWL.hasValue)
            return ("value", p, isinstance(v, Literal))
        if g.value(n, OWL.hasSelf) is not None:
            return ("self", p)
        for pred, kind, qual in ((OWL.minCardinality, "min", False), (OWL.maxCardinality, "max", False),
                                 (OWL.cardinality, "exactly", False), (OWL.minQualifiedCardinality, "min", True),
                                 (OWL.maxQualifiedCardinality, "max", True), (OWL.qualifiedCardinality, "exactly", True)):
            c = g.value(n, pred)
            if c is not None:
                try:
                    num = int(str(c))
                except ValueError:
                    num = -1
                filler, is_data = None, p[0] in ctx.data_props
                if qual:
                    f = g.value(n, OWL.onClass)
                    f = f if f is not None else g.value(n, OWL.onDataRange)
                    if f is not None:
                        filler = parse_ce(ctx, f, depth + 1)
                        is_data = g.value(n, OWL.onDataRange) is not None or _is_data(ctx, p, f, filler)
                return ("card", kind, num, p, filler, is_data)
        return ("other", "restriction sans quantificateur")
    for pred, kind in ((OWL.intersectionOf, "and"), (OWL.unionOf, "or")):
        h = g.value(n, pred)
        if h is not None:
            return (kind, [parse_ce(ctx, m, depth + 1) for m in rdf_list(g, h)])
    h = g.value(n, OWL.complementOf)
    if h is not None:
        return ("not", parse_ce(ctx, h, depth + 1))
    h = g.value(n, OWL.oneOf)
    if h is not None:
        return ("oneOf", rdf_list(g, h))
    if g.value(n, OWL.onDatatype) is not None:
        return ("dtrestr", str(g.value(n, OWL.onDatatype)))
    if g.value(n, OWL.datatypeComplementOf) is not None:
        return ("not", parse_ce(ctx, g.value(n, OWL.datatypeComplementOf), depth + 1))
    return ("other", "expression anonyme non reconnue")


def _prop(g, node):
    if isinstance(node, URIRef):
        return (str(node), False)
    if node is not None:
        inv = g.value(node, OWL.inverseOf)
        if isinstance(inv, URIRef):
            return (str(inv), True)
    return None


def _is_data(ctx: Ctx, p, f, fe) -> bool:
    if URIRef(p[0]) in ctx.data_props:
        return True
    if URIRef(p[0]) in ctx.obj_props:
        return False
    if isinstance(f, URIRef):
        return ctx.is_datatype_iri(f)
    return fe[0] == "dtrestr" or (fe[0] == "oneOf" and any(isinstance(m, Literal) for m in fe[1]))


# =================================================================================================
# Contrôles structurels OWL 2 DL  (W01–W05)
# =================================================================================================
def _datatype_uses(ctx: Ctx):
    """Génère (datatype_iri, sujet, contexte) pour chaque usage de datatype de l'ontologie."""
    g = ctx.g
    for p in ctx.data_props:
        for r in g.objects(p, RDFS.range):
            if isinstance(r, URIRef):
                yield str(r), str(p), "range"
    for s, o in g.subject_objects(OWL.onDatatype):
        yield str(o), str(s) if isinstance(s, URIRef) else "(datatype anonyme)", "onDatatype"
    for s, o in g.subject_objects(OWL.onDataRange):
        if isinstance(o, URIRef):
            yield str(o), str(s) if isinstance(s, URIRef) else "(restriction)", "onDataRange"
    for pred in (OWL.someValuesFrom, OWL.allValuesFrom):
        for s, o in g.subject_objects(pred):
            if isinstance(o, URIRef) and (str(o).startswith(str(XSD)) or o in ctx.datatypes):
                yield str(o), str(s) if isinstance(s, URIRef) else "(restriction)", "restriction"
    for s, p, o in g:
        if isinstance(o, Literal) and o.datatype is not None:
            yield str(o.datatype), str(s) if isinstance(s, URIRef) else "(littéral)", ("annotation" if p in ctx.ann_props or str(p).startswith(str(RDFS)) else "valeur")


def _w01(ctx: Ctx, out: list[Issue]):
    seen: set[tuple[str, str]] = set()
    for dt, subj, where in _datatype_uses(ctx):
        key = (dt, subj)
        if key in seen:
            continue
        seen.add(key)
        if dt in OWL2_DATATYPE_MAP or dt in {str(x) for x in ctx.datatypes}:
            continue
        reserved = dt.startswith((str(XSD), str(RDF), str(RDFS), str(OWL)))
        if reserved:
            lvl = "warning" if where == "annotation" else "error"
            extra = (" (valeur d'annotation : toléré par les outils mais hors carte OWL 2)" if where == "annotation" else "")
            out.append(Issue(level=lvl, code="W01", subject=subj, spec_ref=f"{SS} §4.1 et §4.3",
                             message=f"Le datatype {_short(dt)} n'appartient pas à la carte des datatypes OWL 2 : "
                                     f"l'ontologie sort d'OWL 2 DL{extra}."))
        elif where in ("range", "onDatatype", "onDataRange", "restriction"):
            out.append(Issue(level="error", code="W02", subject=subj, spec_ref=f"{SS} §5.2 ; {MAP} §3.1",
                             message=f"Le datatype {_n(dt)} est utilisé sans être déclaré (rdfs:Datatype)."))


def _short(iri: str) -> str:
    for ns, pre in ((str(XSD), "xsd:"), (str(RDF), "rdf:"), (str(RDFS), "rdfs:"), (str(OWL), "owl:")):
        if iri.startswith(ns):
            return pre + iri[len(ns):]
    return iri


def _w02(ctx: Ctx, out: list[Issue]):
    g = ctx.g
    declared_class = set(ctx.classes)
    for s in g.subjects(RDF.type, RDFS.Class):
        if isinstance(s, URIRef) and s not in declared_class:
            out.append(Issue(level="error", code="W02", subject=str(s), spec_ref=f"{MAP} §3.1.2",
                             message=f"{_n(s)} est typée rdfs:Class et non owl:Class : la déclaration OWL 2 DL est absente."))
            declared_class.add(s)
    props = ctx.obj_props | ctx.data_props | ctx.ann_props
    for s in g.subjects(RDF.type, RDF.Property):
        if isinstance(s, URIRef) and s not in props:
            out.append(Issue(level="error", code="W02", subject=str(s), spec_ref=f"{MAP} §3.1.2 ; {SS} §5.8",
                             message=f"{_n(s)} est typée rdf:Property seulement : il faut owl:ObjectProperty, "
                                     f"owl:DatatypeProperty ou owl:AnnotationProperty."))
            props.add(s)
    # propriétés utilisées (prédicats) sans déclaration
    undeclared_props: dict[URIRef, int] = {}
    for p in set(g.predicates()):
        if isinstance(p, URIRef) and not _is_reserved(p) and p not in props:
            undeclared_props[p] = 1
    for pred in (OWL.onProperty, RDFS.subPropertyOf, OWL.equivalentProperty, OWL.propertyDisjointWith, OWL.inverseOf):
        for o in g.objects(None, pred):
            if isinstance(o, URIRef) and not _is_reserved(o) and o not in props:
                undeclared_props[o] = 1
    for p in undeclared_props:
        out.append(Issue(level="error", code="W02", subject=str(p), spec_ref=f"{SS} §5.8 ; {MAP} §3.1.2",
                         message=f"La propriété {_n(p)} est utilisée sans déclaration (owl:ObjectProperty, "
                                 f"owl:DatatypeProperty ou owl:AnnotationProperty)."))
    # classes utilisées sans déclaration
    used: set[URIRef] = set()
    for pred in (RDFS.subClassOf, OWL.disjointWith, OWL.onClass):
        for s, o in g.subject_objects(pred):
            for x in (s, o):
                if isinstance(x, URIRef):
                    used.add(x)
    for s, o in g.subject_objects(OWL.equivalentClass):
        if s in ctx.datatypes:
            continue
        for x in (s, o):
            if isinstance(x, URIRef) and x not in ctx.datatypes:
                used.add(x)
    for p in ctx.obj_props:
        for pred in (RDFS.domain, RDFS.range):
            used.update(o for o in g.objects(p, pred) if isinstance(o, URIRef))
    for p in ctx.data_props:
        used.update(o for o in g.objects(p, RDFS.domain) if isinstance(o, URIRef))
    for pred in (OWL.someValuesFrom, OWL.allValuesFrom):
        for s, o in g.subject_objects(pred):
            if isinstance(o, URIRef) and not ctx.is_datatype_iri(o) and g.value(s, OWL.onProperty) not in ctx.data_props:
                used.add(o)
    for pred in (OWL.unionOf, OWL.intersectionOf, OWL.disjointUnionOf, OWL.members):
        for s, h in g.subject_objects(pred):
            if pred == OWL.members and (s, RDF.type, OWL.AllDisjointProperties) in g:
                continue
            if pred == OWL.members and (s, RDF.type, OWL.AllDifferent) in g:
                continue
            for m in rdf_list(g, h):
                if isinstance(m, URIRef) and not ctx.is_datatype_iri(m):
                    used.add(m)
    for s, o in g.subject_objects(RDF.type):
        if isinstance(s, URIRef) and isinstance(o, URIRef) and not _is_reserved(o):
            used.add(o)
    for c in sorted(used, key=str):
        if _is_reserved(c) or c in declared_class or c in ctx.datatypes:
            continue
        out.append(Issue(level="error", code="W02", subject=str(c), spec_ref=f"{SS} §5.8 ; {MAP} §3.1.2",
                         message=f"La classe {_n(c)} est utilisée sans déclaration owl:Class."))


def _w04(ctx: Ctx, out: list[Issue]):
    g = ctx.g
    kinds: dict[URIRef, set[str]] = {}
    for label, coll in (("classe", ctx.classes), ("datatype", ctx.datatypes), ("propriété objet", ctx.obj_props),
                        ("propriété de données", ctx.data_props), ("propriété d'annotation", ctx.ann_props)):
        for s in coll:
            if isinstance(s, URIRef) and not (label == "datatype" and _is_reserved(s)):
                kinds.setdefault(s, set()).add(label)
    for s, ks in sorted(kinds.items(), key=lambda t: str(t[0])):
        bad = False
        if {"classe", "datatype"} <= ks:
            bad = True
        if len(ks & {"propriété objet", "propriété de données", "propriété d'annotation"}) > 1:
            bad = True
        if bad:
            out.append(Issue(level="error", code="W04", subject=str(s), spec_ref=f"{SS} §5.9",
                             message=f"{_n(s)} est déclarée à la fois comme {' et '.join(sorted(ks))} : "
                                     f"ce punning est interdit en OWL 2 DL."))


def _non_simple(ctx: Ctx) -> set[str]:
    """Propriétés non simples (SS §11.2) : composites, leurs inverses et leurs super-propriétés."""
    g = ctx.g
    ns: set[str] = {str(p) for p in g.subjects(RDF.type, OWL.TransitiveProperty)}
    ns |= {str(p) for p in g.subjects(OWL.propertyChainAxiom, None)}
    subs = [(str(a), str(b)) for a, b in g.subject_objects(RDFS.subPropertyOf) if isinstance(a, URIRef) and isinstance(b, URIRef)]
    for a, b in g.subject_objects(OWL.equivalentProperty):
        if isinstance(a, URIRef) and isinstance(b, URIRef):
            subs += [(str(a), str(b)), (str(b), str(a))]
    invs = [(str(a), str(b)) for a, b in g.subject_objects(OWL.inverseOf) if isinstance(a, URIRef) and isinstance(b, URIRef)]
    changed = True
    while changed:
        changed = False
        for a, b in subs:
            if a in ns and b not in ns:
                ns.add(b); changed = True
        for a, b in invs:
            if (a in ns) != (b in ns):
                ns |= {a, b}; changed = True
    return ns


def _w03_w05(ctx: Ctx, out: list[Issue]):
    g = ctx.g
    ns = _non_simple(ctx)
    nsd = {iri: _why_non_simple(ctx, iri) for iri in ns}
    for ch, fr in CHARACTERISTICS.items():
        for p in g.subjects(RDF.type, getattr(OWL, ch)):
            if not isinstance(p, URIRef):
                continue
            if p in ctx.data_props and ch not in ("FunctionalProperty",):
                out.append(Issue(level="error", code="W05", subject=str(p), spec_ref=f"{SS} §9.3",
                                 message=f"La propriété de données {_n(p)} ne peut pas être {fr} : seule la "
                                         f"fonctionnalité est permise sur une propriété de données."))
            elif ch in SIMPLE_REQUIRED and str(p) in ns:
                out.append(Issue(level="error", code="W03", subject=str(p), spec_ref=f"{SS} §11.2 et §9.2",
                                 message=f"La propriété non simple {_n(p)} ({nsd[str(p)]}) ne peut pas être {fr}."))
    for p in ctx.data_props:
        if g.value(p, OWL.inverseOf) is not None or g.value(p, OWL.propertyChainAxiom) is not None:
            out.append(Issue(level="error", code="W05", subject=str(p), spec_ref=f"{SS} §9.3",
                             message=f"La propriété de données {_n(p)} ne peut pas avoir d'inverse ni de chaîne."))
    for r in set(g.subjects(OWL.hasSelf, None)) | {s for s, _ in g.subject_objects(OWL.minCardinality)} \
            | {s for s, _ in g.subject_objects(OWL.maxCardinality)} | {s for s, _ in g.subject_objects(OWL.cardinality)} \
            | {s for s, _ in g.subject_objects(OWL.minQualifiedCardinality)} \
            | {s for s, _ in g.subject_objects(OWL.maxQualifiedCardinality)} \
            | {s for s, _ in g.subject_objects(OWL.qualifiedCardinality)}:
        p = _prop(g, g.value(r, OWL.onProperty))
        if p and p[0] in ns and URIRef(p[0]) not in ctx.data_props:
            kind = "hasSelf" if g.value(r, OWL.hasSelf) is not None else "une cardinalité"
            out.append(Issue(level="error", code="W03", subject=p[0], spec_ref=f"{SS} §11.2 et §8.3",
                             message=f"La propriété non simple {_n(p[0])} ({nsd[p[0]]}) est utilisée dans {kind} (restriction de {_anchor(g, r)})."))
    djs = list(g.subject_objects(OWL.propertyDisjointWith))
    for s in g.subjects(RDF.type, OWL.AllDisjointProperties):
        mem = [m for m in rdf_list(g, g.value(s, OWL.members)) if isinstance(m, URIRef)]
        djs += [(m, None) for m in mem]
    for a, b in djs:
        for p in (a, b):
            if isinstance(p, URIRef) and str(p) in ns:
                out.append(Issue(level="error", code="W03", subject=str(p), spec_ref=f"{SS} §11.2 et §9.2.3",
                                 message=f"La propriété non simple {_n(p)} ({nsd[str(p)]}) ne peut pas figurer dans une disjonction de propriétés."))


def _anchor(g, bnode) -> str:
    for s in g.subjects(RDFS.subClassOf, bnode):
        return _n(s) if isinstance(s, URIRef) else "classe anonyme"
    for s in g.subjects(OWL.equivalentClass, bnode):
        return _n(s) if isinstance(s, URIRef) else "classe anonyme"
    return "classe anonyme"


def _why_non_simple(ctx: Ctx, iri: str) -> str:
    g, u = ctx.g, URIRef(iri)
    if (u, RDF.type, OWL.TransitiveProperty) in g:
        return "transitive"
    if (u, OWL.propertyChainAxiom, None) in g:
        return "définie par une chaîne"
    subs = [str(a) for a in g.subjects(RDFS.subPropertyOf, u)]
    invs = [str(a) for a in list(g.objects(u, OWL.inverseOf)) + list(g.subjects(OWL.inverseOf, u))]
    return "super-propriété ou inverse d'une propriété composite" if (subs or invs) else "composite"


def _malformed(ctx: Ctx, out: list[Issue]):
    g = ctx.g
    for r in g.subjects(RDF.type, OWL.Restriction):
        if g.value(r, OWL.onProperty) is None and g.value(r, OWL.onProperties) is None:
            out.append(Issue(level="error", code="W02", subject=_anchor(g, r), spec_ref=f"{MAP} §3.2",
                             message=f"Une restriction de {_anchor(g, r)} n'a pas de owl:onProperty : le graphe n'est pas un axiome OWL 2 valide."))


def _ill_typed(g: rdflib.Graph, out: list[Issue]) -> None:
    """Littéral hors de l'espace lexical de son datatype : ill-typed (RDF 1.1 Concepts §3.3), ontologie incohérente."""
    for s, p, o in g:
        if isinstance(o, Literal) and o.datatype is not None and str(o.datatype) in OWL2_DATATYPE_MAP \
                and getattr(o, "ill_typed", False):
            out.append(Issue(level="error", code="W01", subject=str(s) if isinstance(s, URIRef) else None,
                             spec_ref=f"{SS} §5.7 ; RDF 1.1 Concepts §3.3",
                             message=f"Le littéral « {o} » n'est pas une forme lexicale valide de {_short(str(o.datatype))} : "
                                     f"littéral mal typé, l'ontologie est incohérente."))


def dl_issues(g: rdflib.Graph) -> list[Issue]:
    ctx = Ctx(g)
    out: list[Issue] = []
    _w01(ctx, out)
    _w02(ctx, out)
    _w04(ctx, out)
    _w03_w05(ctx, out)
    _malformed(ctx, out)
    _ill_typed(g, out)
    uniq, seen = [], set()
    for i in out:
        k = (i.code, i.subject, i.message)
        if k not in seen:
            seen.add(k)
            uniq.append(i)
    return uniq


# =================================================================================================
# Profils EL / QL / RL
# =================================================================================================
THING, NOTHING = str(OWL.Thing), str(OWL.Nothing)


def _dr_bad(profile: str, dr) -> list[str]:
    """Datatype / data range hors profil."""
    if dr[0] == "class":
        if dr[1] not in PROFILE_DATATYPES[profile] and dr[1].startswith((str(XSD), str(RDF), str(RDFS), str(OWL))):
            return [f"datatype {_short(dr[1])} non supporté"]
        return []
    if dr[0] == "dtrestr":
        return ["restriction de datatype à facettes (DatatypeRestriction)"]
    if dr[0] == "oneOf":  # PROF §2.2 : DataOneOf seulement en EL, à un seul littéral
        return [] if profile == "EL" and len(dr[1]) == 1 else ["énumération de littéraux (DataOneOf)" + (" à plusieurs valeurs" if profile == "EL" else "")]
    if dr[0] == "and":  # DataIntersectionOf permis dans les 3 profils
        return [b for m in dr[1] for b in _dr_bad(profile, m)]
    if dr[0] == "or":
        return ["DataUnionOf"]
    if dr[0] == "not":
        return ["DataComplementOf"]
    return ["data range non reconnu"]


def _el_bad(ctx: Ctx, e) -> list[str]:
    k = e[0]
    if k == "class":
        return []
    if k == "and":
        return [b for m in e[1] for b in _el_bad(ctx, m)]
    if k == "or":
        return ["ObjectUnionOf"]
    if k == "not":
        return ["ObjectComplementOf"]
    if k == "oneOf":
        return ["ObjectOneOf à plusieurs individus"] if len(e[1]) != 1 else []
    if k == "svf":
        if e[1][1]:
            return ["ObjectInverseOf"]
        return _dr_bad("EL", e[2]) if e[3] else _el_bad(ctx, e[2])
    if k == "avf":
        return ["ObjectAllValuesFrom"]
    if k == "value":
        return []
    if k == "self":
        return []
    if k == "card":
        return ["cardinalité (" + {"min": "min", "max": "max", "exactly": "exactement"}[e[1]] + f" {e[2]})"]
    return [e[1] if len(e) > 1 else "expression non supportée"]


def _ql_sub_bad(ctx: Ctx, e) -> list[str]:
    k = e[0]
    if k == "class":
        return []
    if k == "svf":
        if e[3]:
            return [] if e[2] == ("class", str(RDFS.Literal)) else ["DataSomeValuesFrom dans une sous-classe (filler rdfs:Literal exigé)"]
        return [] if e[2] == ("class", THING) else ["ObjectSomeValuesFrom qualifiée dans une sous-classe (le filler doit être owl:Thing)"]
    return [{"and": "ObjectIntersectionOf", "or": "ObjectUnionOf", "not": "ObjectComplementOf", "oneOf": "ObjectOneOf",
             "avf": "ObjectAllValuesFrom", "value": "hasValue", "self": "hasSelf", "card": "cardinalité"}.get(k, "expression non supportée")
            + " en position de sous-classe"]


def _ql_super_bad(ctx: Ctx, e) -> list[str]:
    k = e[0]
    if k == "class":
        return []
    if k == "and":
        return [b for m in e[1] for b in _ql_super_bad(ctx, m)]
    if k == "not":
        return _ql_sub_bad(ctx, e[1])
    if k == "svf":
        if e[3]:
            return _dr_bad("QL", e[2])
        return [] if e[2][0] == "class" else ["ObjectSomeValuesFrom à filler anonyme"]
    return [{"or": "ObjectUnionOf", "oneOf": "ObjectOneOf", "avf": "ObjectAllValuesFrom", "value": "hasValue",
             "self": "hasSelf", "card": "cardinalité"}.get(k, "expression non supportée") + " en position de super-classe"]


def _rl_sub_bad(ctx: Ctx, e) -> list[str]:
    k = e[0]
    if k == "class":
        return ["owl:Thing (interdit en RL, PROF §4.2)"] if e[1] == THING else []
    if k in ("and", "or"):
        return [b for m in e[1] for b in _rl_sub_bad(ctx, m)]
    if k == "oneOf":
        return []
    if k == "svf":
        return _dr_bad("RL", e[2]) if e[3] else ([] if e[2] == ("class", THING) else _rl_sub_bad(ctx, e[2]))
    if k == "value":
        return []
    return [{"not": "ObjectComplementOf", "avf": "ObjectAllValuesFrom", "self": "hasSelf", "card": "cardinalité"}.get(k, "expression non supportée")
            + " en position de sous-classe"]


def _rl_super_bad(ctx: Ctx, e) -> list[str]:
    k = e[0]
    if k == "class":
        return ["owl:Thing (interdit en RL, PROF §4.2)"] if e[1] == THING else []
    if k == "and":
        return [b for m in e[1] for b in _rl_super_bad(ctx, m)]
    if k == "not":
        return _rl_sub_bad(ctx, e[1])
    if k == "avf":
        return _dr_bad("RL", e[2]) if e[3] else _rl_super_bad(ctx, e[2])
    if k == "value":
        return []
    if k == "card":
        if e[1] == "max" and e[2] in (0, 1):
            f = e[4]
            return [] if f is None or f == ("class", THING) or e[5] or not _rl_sub_bad(ctx, f) else _rl_sub_bad(ctx, f)
        return [f"cardinalité {e[1]} {e[2]} (seules max 0 et max 1 sont permises)"]
    return [{"svf": "ObjectSomeValuesFrom", "or": "ObjectUnionOf", "oneOf": "ObjectOneOf", "self": "hasSelf"}.get(k, "expression non supportée")
            + " en position de super-classe"]


def _rl_equiv_bad(ctx: Ctx, e) -> list[str]:
    k = e[0]
    if k == "class":
        return [] if e[1] != THING else ["owl:Thing dans une équivalence"]
    if k == "and":
        return [b for m in e[1] for b in _rl_equiv_bad(ctx, m)]
    if k == "value":
        return []
    name = {"svf": "ObjectSomeValuesFrom", "avf": "ObjectAllValuesFrom", "or": "ObjectUnionOf", "not": "ObjectComplementOf",
            "oneOf": "ObjectOneOf", "card": "cardinalité", "self": "hasSelf"}.get(k, k)
    return [f"{name} dans une classe équivalente (seuls classes nommées, intersections et hasValue sont permis)"]


def profile_check(g: rdflib.Graph) -> dict[str, list[str]]:
    """Retourne, pour EL / QL / RL, la liste des violations (une phrase chacune)."""
    ctx = Ctx(g)
    v: dict[str, list[str]] = {"EL": [], "QL": [], "RL": []}

    def add(p: str, subj, msg: str):
        line = f"{_n(subj) if subj is not None else 'ontologie'} : {msg} (hors OWL 2 {p})."
        if line not in v[p]:
            v[p].append(line)

    # ---- axiomes de classes
    for s, o in g.subject_objects(RDFS.subClassOf):
        sub, sup = parse_ce(ctx, s), parse_ce(ctx, o)
        anchor = s if isinstance(s, URIRef) else (o if isinstance(o, URIRef) else None)
        if isinstance(s, BNode) and isinstance(o, URIRef):
            anchor = o
        for b in _el_bad(ctx, sub) + _el_bad(ctx, sup):
            add("EL", anchor, f"{b} dans SubClassOf")
        for b in _ql_sub_bad(ctx, sub) + _ql_super_bad(ctx, sup):
            add("QL", anchor, b + " dans SubClassOf")
        for b in _rl_sub_bad(ctx, sub) + _rl_super_bad(ctx, sup):
            add("RL", anchor, b + " dans SubClassOf")
    for s, o in g.subject_objects(OWL.equivalentClass):
        if s in ctx.datatypes or (isinstance(o, BNode) and (o, RDF.type, RDFS.Datatype) in g):
            # DatatypeDefinition est permise dans les 3 profils (PROF §2.2, §3.2, §4.2) : seule sa portée compte.
            for p in v:
                for bb in _dr_bad(p, parse_ce(ctx, o if s in ctx.datatypes else s)):
                    add(p, s if s in ctx.datatypes else o, bb + " dans la définition de datatype")
            continue
        a, b_ = parse_ce(ctx, s), parse_ce(ctx, o)
        anchor = s if isinstance(s, URIRef) else o if isinstance(o, URIRef) else None
        for bb in _el_bad(ctx, a) + _el_bad(ctx, b_):
            add("EL", anchor, f"{bb} dans EquivalentClasses")
        for bb in _ql_sub_bad(ctx, a) + _ql_sub_bad(ctx, b_):
            add("QL", anchor, bb + " dans EquivalentClasses")
        for bb in _rl_equiv_bad(ctx, a) + _rl_equiv_bad(ctx, b_):
            add("RL", anchor, bb + " dans EquivalentClasses")
    disj = [(s, o) for s, o in g.subject_objects(OWL.disjointWith)]
    for s in g.subjects(RDF.type, OWL.AllDisjointClasses):
        mem = rdf_list(g, g.value(s, OWL.members))
        disj += [(a, b) for i, a in enumerate(mem) for b in mem[i + 1:]]
    for a, b in disj:
        pa, pb = parse_ce(ctx, a), parse_ce(ctx, b)
        anchor = a if isinstance(a, URIRef) else None
        for bb in _ql_sub_bad(ctx, pa) + _ql_sub_bad(ctx, pb):
            add("QL", anchor, bb + " dans DisjointClasses")
        for bb in _rl_sub_bad(ctx, pa) + _rl_sub_bad(ctx, pb):
            add("RL", anchor, bb + " dans DisjointClasses")
    for s, _ in g.subject_objects(OWL.disjointUnionOf):
        for p in v:
            add(p, s, "DisjointUnion")  # absent de ClassAxiom dans PROF §2.2, §3.2, §4.2
    # ---- domaines, portées
    for pred, name in ((RDFS.domain, "ObjectPropertyDomain"), (RDFS.range, "ObjectPropertyRange")):
        for s, o in g.subject_objects(pred):
            if not isinstance(s, URIRef) or s in ctx.ann_props:
                continue
            e = parse_ce(ctx, o)
            if s in ctx.data_props and pred == RDFS.range:
                for p in v:
                    for bb in _dr_bad(p, e):
                        add(p, s, f"{bb} comme portée")
                continue
            for bb in _el_bad(ctx, e):
                add("EL", s, f"{bb} dans {name}")
            for bb in _ql_super_bad(ctx, e):
                add("QL", s, f"{bb} dans {name}")
            for bb in _rl_super_bad(ctx, e):
                add("RL", s, f"{bb} dans {name}")
    # ---- propriétés
    deny = {
        "EL": {"FunctionalProperty", "InverseFunctionalProperty", "SymmetricProperty", "AsymmetricProperty", "IrreflexiveProperty"},
        "QL": {"FunctionalProperty", "InverseFunctionalProperty", "TransitiveProperty"},
        "RL": {"ReflexiveProperty"},
    }
    for p in v:
        for ch in deny[p]:
            for s in g.subjects(RDF.type, getattr(OWL, ch)):
                if p == "EL" and ch == "FunctionalProperty" and s in ctx.data_props:
                    continue  # FunctionalDataProperty appartient à EL (PROF §2.2)
                add(p, s, f"propriété {CHARACTERISTICS[ch]} ({ch})")
    for s in g.subjects(OWL.propertyChainAxiom, None):
        add("QL", s, "chaîne de propriétés (PropertyChain)")
    for s, o in g.subject_objects(OWL.inverseOf):
        if isinstance(s, URIRef):
            add("EL", s, "InverseObjectProperties")
    for s, o in g.subject_objects(OWL.propertyDisjointWith):
        add("EL", s, "DisjointDataProperties" if s in ctx.data_props else "DisjointObjectProperties")
    for s in g.subjects(RDF.type, OWL.AllDisjointProperties):
        add("EL", s if isinstance(s, URIRef) else None, "DisjointObjectProperties")
    for s, o in g.subject_objects(OWL.hasKey):
        add("QL", s, "HasKey")
        for bb in _rl_sub_bad(ctx, parse_ce(ctx, s)):
            add("RL", s, bb + " dans HasKey")
    # ---- individus
    for s in g.subjects(RDF.type, OWL.NegativePropertyAssertion):
        add("QL", None, "assertion de propriété négative")  # exclue de QL (PROF §3), admise en EL et RL
    for s, o in g.subject_objects(OWL.sameAs):
        add("QL", s, "owl:sameAs")
    for s, o in g.subject_objects(RDF.type):
        if isinstance(o, BNode) and isinstance(s, URIRef):
            e = parse_ce(ctx, o)
            add("QL", s, "assertion de type sur une expression anonyme (ClassAssertion)")
            for bb in _el_bad(ctx, e):
                add("EL", s, f"{bb} dans ClassAssertion")
            for bb in _rl_super_bad(ctx, e):
                add("RL", s, f"{bb} dans ClassAssertion")
    # ---- datatypes des littéraux
    for p in v:
        bad = {str(o.datatype) for o in g.objects(None, None) if isinstance(o, Literal) and o.datatype is not None
               and str(o.datatype) not in PROFILE_DATATYPES[p] and str(o.datatype).startswith((str(XSD), str(RDF)))}
        for dt in sorted(bad):
            add(p, None, f"littéral de datatype {_short(dt)} non supporté")
    return v


def rdfs_check(g: rdflib.Graph) -> list[str]:
    """Violations « ontologie RDFS pure » : usage de constructions OWL au-delà de la déclaration."""
    ok_types = {OWL.Ontology, OWL.Class, OWL.ObjectProperty, OWL.DatatypeProperty, OWL.AnnotationProperty, OWL.NamedIndividual}
    ok_preds = {OWL.imports, OWL.versionInfo, OWL.versionIRI, OWL.priorVersion, OWL.deprecated}
    seen: dict[str, str] = {}
    for s, p, o in g:
        if str(p).startswith(str(OWL)) and p not in ok_preds:
            seen.setdefault(_short(str(p)), _n(s))
        elif p == RDF.type and isinstance(o, URIRef) and str(o).startswith(str(OWL)) and o not in ok_types:
            seen.setdefault(_short(str(o)), _n(s))
    return [f"{subj} : utilise {c}, construction OWL absente de RDFS." for c, subj in sorted(seen.items())]


# =================================================================================================
# Point d'entrée
# =================================================================================================
def _graph_of(onto: OntoModel) -> rdflib.Graph:
    from ..io.rdf_export import model_to_graph
    return model_to_graph(onto)


def check_conformance(onto: OntoModel, graph: Optional[rdflib.Graph] = None, *, run_reasoner: bool = True,
                      hermit: bool = False, timeout: float = 30.0) -> ConformanceReport:
    from . import lint as _lint
    from . import reasoner as _reasoner

    g = graph if graph is not None else _graph_of(onto)
    rep = ConformanceReport()
    dl = dl_issues(g)
    rep.issues.extend(dl)
    rep.profile_violations["DL"] = sorted({f"{i.code} : {i.message}" for i in dl if i.level == "error"})
    rep.profiles["DL"] = not rep.profile_violations["DL"]
    pv = profile_check(g)
    for p in ("EL", "QL", "RL"):
        rep.profile_violations[p] = pv[p]
        rep.profiles[p] = not pv[p] and rep.profiles["DL"]  # un profil est un sous-ensemble syntaxique d'OWL 2 DL
    rv = rdfs_check(g)
    rep.profile_violations["RDFS"] = rv
    rep.profiles["RDFS"] = not rv
    rep.issues.extend(_lint.lint(onto, g, include_dl=False))
    if run_reasoner:
        res = _reasoner.reason(g, hermit=hermit, timeout=timeout)
        rep.reasoner = res
        for c in res.unsatisfiable:
            rep.issues.append(Issue(level="error", code="W06", subject=c, spec_ref=f"{SS} §9.1",
                                    message=f"La classe {_n(c)} est insatisfiable : elle ne peut avoir aucune instance."))
        if res.consistent is False:
            rep.issues.append(Issue(level="error", code="W06", subject=None, spec_ref=f"{SS} §2",
                                    message="L'ontologie est incohérente : aucun modèle ne la satisfait (voir les notes du raisonneur)."))
    return rep
