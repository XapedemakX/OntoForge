"""Socle des règles de transposition : contexte d'analyse, vues sémantiques, fabrique de constats.

Une règle = `detect(ctx) -> list[Finding]` (pure : ne modifie que des caches de lecture) +
`apply(ctx, finding, option_id)` (construit la partie correspondante du PGModel ou du plan de construction).
Les métadonnées (titre, sévérité, options, recommandation par cible, compensation) sont dans `catalog.py`.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

import rdflib
from rdflib import BNode, Literal, URIRef
from rdflib.namespace import OWL as _OWL, RDF as _RDF, RDFS as _RDFS

from ...core.onto_model import (OWL, RDF, RDFS, XSD, ClassExpr, DataRange, LiteralValue, OntoModel, Restriction,
                                local_name)
from ...core.pg_model import (EdgeType, Finding, Materialization, NodeType, Option, PGModel, PGProperty, Target,
                              Validation)
from ...core.shapes_model import ShapesModel
from ..profile_api import Profile
from . import catalog

THING = OWL + "Thing"
TOP_OBJ = OWL + "topObjectProperty"
TOP_DATA = OWL + "topDataProperty"


def sha8(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:8]


def lower_first(s: str) -> str:
    return s[:1].lower() + s[1:] if s else s


def upper_first(s: str) -> str:
    return s[:1].upper() + s[1:] if s else s


# ================================================================================================
# Vue « graphe » des triplets non mappés (OntoModel.unmapped) : les constructs que l'import n'a pas
# structurés (expressions de classe anonymes, DataRange à facettes, nœuds blancs, owl:Axiom…) sont
# relus ici. Si l'import les structure un jour, les règles lisent d'abord les champs structurés.
# ================================================================================================
def build_unmapped_graph(onto: OntoModel) -> tuple[rdflib.Graph, list[str]]:
    """Graphe des triplets non mappés ; les étiquettes de nœuds blancs sont conservées (from_n3)."""
    from rdflib.util import from_n3
    g = rdflib.Graph()
    warnings: list[str] = []
    for u in onto.unmapped:
        for t in u.triples:
            if len(t) != 3:
                continue
            try:
                g.add(tuple(from_n3(x) for x in t))
            except Exception:
                warnings.append(f"triplet non mappé illisible : {' '.join(map(str, t))[:120]}")
    return g, warnings


def rdf_list(g: rdflib.Graph, node) -> list:
    out, seen = [], set()
    while node is not None and node != _RDF.nil and node not in seen:
        seen.add(node)
        first = g.value(node, _RDF.first)
        if first is None:
            break
        out.append(first)
        node = g.value(node, _RDF.rest)
    return out


def subtree(g: rdflib.Graph, node, seen=None) -> set:
    """Tous les nœuds blancs atteignables depuis `node` (pour marquer un construct comme consommé)."""
    seen = set() if seen is None else seen
    if isinstance(node, BNode) and node not in seen:
        seen.add(node)
        for _, o in g.predicate_objects(node):
            subtree(g, o, seen)
    return seen


def canonical(g: rdflib.Graph, node, depth: int = 0) -> str:
    """Sérialisation canonique d'un nœud (nœuds blancs remplacés par leur contenu, trié) → ids stables."""
    if not isinstance(node, BNode) or depth > 12:
        return node.n3() if hasattr(node, "n3") else str(node)
    parts = sorted(f"{p.n3()} {canonical(g, o, depth + 1)}" for p, o in g.predicate_objects(node)
                   if p not in (_RDF.first, _RDF.rest))
    items = rdf_list(g, node)
    if items:
        parts.append("(" + " ".join(canonical(g, i, depth + 1) for i in items) + ")")
    return "[" + "; ".join(parts) + "]"


def _int(lit) -> Optional[int]:
    try:
        return int(str(lit))
    except Exception:
        return None


def parse_class_expr(g: rdflib.Graph, node) -> Optional[ClassExpr]:
    if isinstance(node, URIRef):
        return ClassExpr(op="named", iri=str(node))
    if not isinstance(node, BNode):
        return None
    for pred, op in ((_OWL.intersectionOf, "and"), (_OWL.unionOf, "or")):
        lst = g.value(node, pred)
        if lst is not None:
            args = [parse_class_expr(g, x) for x in rdf_list(g, lst)]
            return ClassExpr(op=op, args=[a for a in args if a])
    c = g.value(node, _OWL.complementOf)
    if c is not None:
        a = parse_class_expr(g, c)
        return ClassExpr(op="not", args=[a] if a else [])
    lst = g.value(node, _OWL.oneOf)
    if lst is not None:
        return ClassExpr(op="oneOf", individuals=[str(x) for x in rdf_list(g, lst)])
    prop = g.value(node, _OWL.onProperty)
    if prop is not None:
        inverse = False
        if isinstance(prop, BNode):
            inv = g.value(prop, _OWL.inverseOf)
            inverse, prop = True, inv
        e = ClassExpr(op="some", property=str(prop) if prop is not None else None, inverse=inverse)
        on_class = g.value(node, _OWL.onClass)
        on_range = g.value(node, _OWL.onDataRange)
        for pred, op in ((_OWL.someValuesFrom, "some"), (_OWL.allValuesFrom, "only")):
            f = g.value(node, pred)
            if f is not None:
                e.op = op
                if isinstance(f, URIRef) and str(f).startswith(XSD):
                    e.data_range = str(f)
                else:
                    e.filler = parse_class_expr(g, f)
                return e
        hv = g.value(node, _OWL.hasValue)
        if hv is not None:
            e.op = "value"
            e.value = str(hv) if isinstance(hv, URIRef) else LiteralValue(value=str(hv), datatype=str(hv.datatype) if getattr(hv, "datatype", None) else None)
            return e
        if g.value(node, _OWL.hasSelf) is not None:
            e.op = "self"
            return e
        for preds, op in (((_OWL.minCardinality, _OWL.minQualifiedCardinality), "min"),
                          ((_OWL.maxCardinality, _OWL.maxQualifiedCardinality), "max"),
                          ((_OWL.cardinality, _OWL.qualifiedCardinality), "exactly")):
            for pr in preds:
                v = g.value(node, pr)
                if v is not None:
                    e.op, e.n = op, _int(v)
                    if on_class is not None:
                        e.filler = parse_class_expr(g, on_class)
                    if on_range is not None:
                        e.data_range = str(on_range)
                    return e
        return e
    return None


def parse_data_range(g: rdflib.Graph, node) -> Optional[DataRange]:
    if isinstance(node, URIRef):
        return DataRange(base=str(node))
    if not isinstance(node, BNode):
        return None
    dr = DataRange()
    base = g.value(node, _OWL.onDatatype)
    if base is not None:
        dr.base = str(base)
        for f in rdf_list(g, g.value(node, _OWL.withRestrictions)):
            for p, o in g.predicate_objects(f):
                dr.facets[str(p)] = str(o)
    lst = g.value(node, _OWL.oneOf)
    if lst is not None:
        for x in rdf_list(g, lst):
            dt = getattr(x, "datatype", None)
            dr.one_of.append(LiteralValue(value=str(x), datatype=str(dt) if dt else None,
                                          lang=getattr(x, "language", None)))
    lst = g.value(node, _OWL.unionOf)
    if lst is not None:
        dr.union_of = [str(x) for x in rdf_list(g, lst)]
    if dr.base is None and not dr.one_of and not dr.union_of:
        return None
    return dr


def expr_text(e: Optional[ClassExpr], short: Callable[[str], str] = local_name) -> str:
    """Rendu lisible (syntaxe Manchester simplifiée)."""
    if e is None:
        return "?"
    if e.op == "named":
        return short(e.iri or "?")
    if e.op in ("and", "or"):
        sep = " and " if e.op == "and" else " or "
        return "(" + sep.join(expr_text(a, short) for a in e.args) + ")"
    if e.op == "not":
        return "not " + expr_text(e.args[0] if e.args else None, short)
    if e.op == "oneOf":
        return "{" + ", ".join(short(i) for i in e.individuals) + "}"
    p = short(e.property or "?")
    if e.inverse:
        p = f"inverse({p})"
    tail = expr_text(e.filler, short) if e.filler else (short(e.data_range) if e.data_range else "")
    if e.op == "value":
        v = e.value.value if isinstance(e.value, LiteralValue) else short(str(e.value))
        return f"{p} value {v}"
    if e.op == "self":
        return f"{p} Self"
    if e.op in ("min", "max", "exactly"):
        return f"{p} {e.op} {e.n} {tail}".strip()
    return f"{p} {e.op} {tail}".strip()


def named_conjuncts(e: Optional[ClassExpr]) -> list[str]:
    if e is None:
        return []
    if e.op == "named":
        return [e.iri] if e.iri else []
    if e.op == "and":
        return [a.iri for a in e.args if a.op == "named" and a.iri]
    return []


def walk(e: Optional[ClassExpr]):
    if e is None:
        return
    yield e
    for a in e.args:
        yield from walk(a)
    if e.filler:
        yield from walk(e.filler)


# ================================================================================================
@dataclass
class Ctx:
    onto: OntoModel
    shapes: Optional[ShapesModel]
    target: Target
    profile: Profile
    decisions: dict[str, str]
    sc: dict = field(default_factory=dict)  # index shacl_to_pg.shape_constraints (vide si indisponible)
    g: rdflib.Graph = field(default_factory=rdflib.Graph)
    pg: PGModel = None  # type: ignore[assignment]
    warnings: list[str] = field(default_factory=list)
    consumed: set = field(default_factory=set)  # nœuds blancs du graphe non mappé expliqués par une règle
    findings: dict[str, Finding] = field(default_factory=dict)
    # ----- plan de construction (rempli par les apply, lu par les builders) -----
    plan: dict[str, Any] = field(default_factory=dict)
    cache: dict[str, Any] = field(default_factory=dict)

    # ------------------------------------------------------------------ accès aux constats
    def option(self, fid: str, default: Optional[str] = None) -> Optional[str]:
        f = self.findings.get(fid)
        if not f:
            return default
        return f.chosen or f.recommended or default

    def option_of(self, rule: str, subject: str, suffix: Optional[str] = None, default: Optional[str] = None):
        return self.option(make_id(rule, subject, suffix), default)

    def by_rule(self, rule: str) -> list[Finding]:
        return [f for f in self.findings.values() if f.rule == rule]

    # ------------------------------------------------------------------ nommage
    def local(self, iri: str) -> str:
        return self.plan.get("rename", {}).get(iri) or local_name(iri)

    def short(self, iri: str) -> str:
        for pfx, ns in sorted(self.onto.meta.prefixes.items(), key=lambda kv: -len(kv[1])):
            if ns and iri.startswith(ns) and len(iri) > len(ns):
                return f"{pfx}:{iri[len(ns):]}"
        return local_name(iri)

    # ------------------------------------------------------------------ vues sémantiques (cachées)
    def _c(self, key: str, fn: Callable[[], Any]) -> Any:
        if key not in self.cache:
            self.cache[key] = fn()
        return self.cache[key]

    def is_class(self, iri: str) -> bool:
        return iri in self.onto.classes

    def is_data_prop(self, iri: str) -> bool:
        return iri in self.onto.datatype_properties

    def is_obj_prop(self, iri: str) -> bool:
        return iri in self.onto.object_properties

    def parents(self, c: str) -> list[str]:
        """Parents nommés effectifs : rdfs:subClassOf + appartenance à un owl:disjointUnionOf."""
        def build():
            out: dict[str, list[str]] = {k: [p for p in v.sub_class_of if p != THING and p in self.onto.classes]
                                         for k, v in self.onto.classes.items()}
            for k, v in self.onto.classes.items():
                for du in v.disjoint_union_of:
                    for ch in du:
                        if ch in out and k not in out[ch]:
                            out[ch].append(k)
            return {k: sorted(set(v)) for k, v in out.items()}
        return self._c("parents", build).get(c, [])

    def children(self, c: str) -> list[str]:
        def build():
            out: dict[str, list[str]] = {}
            for k in sorted(self.onto.classes):
                for p in self.parents(k):
                    out.setdefault(p, []).append(k)
            return out
        return self._c("children", build).get(c, [])

    def ancestors(self, c: str) -> list[str]:
        out, stack = [], list(self.parents(c))
        while stack:
            p = stack.pop(0)
            if p not in out and p != c:
                out.append(p)
                stack.extend(self.parents(p))
        return out

    def descendants(self, c: str) -> list[str]:
        out, stack = [], list(self.children(c))
        while stack:
            p = stack.pop(0)
            if p not in out and p != c:
                out.append(p)
                stack.extend(self.children(p))
        return out

    def subsumes(self, a: str, b: str) -> bool:
        return a == b or a in self.ancestors(b)

    def direct_instances(self, c: str) -> list[str]:
        return sorted(i for i, ind in self.onto.individuals.items() if c in ind.types)

    # ---- expressions anonymes relues depuis le graphe non mappé --------------------------------
    def class_definitions(self, c: str) -> list[tuple[ClassExpr, Any]]:
        """Définitions (owl:equivalentClass non nommées) : [(expr, nœud blanc | None)]."""
        def build():
            out: dict[str, list] = {}
            for k, v in self.onto.classes.items():
                for e in v.equivalent_to:
                    if e.op != "named":
                        out.setdefault(k, []).append((e, None))
            for s, o in self.g.subject_objects(_OWL.equivalentClass):
                if isinstance(s, URIRef) and isinstance(o, BNode) and str(s) in self.onto.classes:
                    e = parse_class_expr(self.g, o)
                    if e:
                        out.setdefault(str(s), []).append((e, o))
            return out
        return self._c("defs", build).get(c, [])

    def anon_supers(self, c: str) -> list[tuple[ClassExpr, Any]]:
        """Super-classes anonymes : expressions structurées + relues (restrictions inverses, unions…)."""
        def build():
            out: dict[str, list] = {}
            for k, v in self.onto.classes.items():
                for e in v.super_expressions:
                    out.setdefault(k, []).append((e, None))
            for s, o in self.g.subject_objects(_RDFS.subClassOf):
                if isinstance(s, URIRef) and isinstance(o, BNode):
                    e = parse_class_expr(self.g, o)
                    if e:
                        out.setdefault(str(s), []).append((e, o))
            return out
        return self._c("supers", build).get(c, [])

    def all_restrictions(self, c: str) -> list[tuple[Restriction, Any]]:
        """Restrictions de super-classe (structurées + relues depuis le graphe)."""
        out = [(r, None) for r in self.onto.classes[c].restrictions] if c in self.onto.classes else []
        for e, node in self.anon_supers(c):
            if e.op in ("some", "only", "min", "max", "exactly", "value", "self") and e.property:
                filler = e.filler.iri if e.filler and e.filler.op == "named" else e.data_range
                out.append((Restriction(property=e.property, inverse=e.inverse, kind=e.op, n=e.n, filler=filler,
                                        filler_expr=e.filler if e.filler and e.filler.op != "named" else None,
                                        value=e.value), node))
        return out

    def gcis(self) -> list[tuple[ClassExpr, str, Any]]:
        def build():
            out = []
            for s, o in self.g.subject_objects(_RDFS.subClassOf):
                if isinstance(s, BNode) and isinstance(o, URIRef):
                    e = parse_class_expr(self.g, s)
                    if e:
                        out.append((e, str(o), s))
            return sorted(out, key=lambda t: (t[1], canonical(self.g, t[2])))
        return self._c("gcis", build)

    def datatype_def(self, d: str) -> tuple[Optional[DataRange], Any]:
        dd = self.onto.datatypes.get(d)
        if dd and dd.definition:
            return dd.definition, None
        for o in self.g.objects(URIRef(d), _OWL.equivalentClass):
            dr = parse_data_range(self.g, o)
            if dr:
                return dr, o
        return None, None

    def range_expr(self, p: str) -> tuple[Optional[DataRange], Any]:
        dp = self.onto.datatype_properties.get(p)
        if dp and dp.range_expr:
            return dp.range_expr, None
        for o in self.g.objects(URIRef(p), _RDFS.range):
            if isinstance(o, BNode):
                dr = parse_data_range(self.g, o)
                if dr:
                    return dr, o
        return None, None

    def union_of(self, p: str, which: str) -> tuple[list[str], Any]:
        """Domaine / portée en owl:unionOf (structuré ou relu)."""
        prop = self.onto.object_properties.get(p) or self.onto.datatype_properties.get(p)
        if prop is not None:
            val = getattr(prop, f"{which}_union", None)
            if val:
                return sorted(val), None
        pred = _RDFS.domain if which == "domain" else _RDFS.range
        for o in self.g.objects(URIRef(p), pred):
            if isinstance(o, BNode):
                e = parse_class_expr(self.g, o)
                if e and e.op == "or" and all(a.op == "named" for a in e.args):
                    return sorted(a.iri for a in e.args if a.iri), o
        return [], None

    def anon_individuals(self) -> list[dict]:
        """Individus anonymes : (ancre nommée, propriété, nœud blanc typé)."""
        def build():
            out = []
            for s, p, o in self.g:
                if isinstance(s, URIRef) and isinstance(o, BNode) and str(p) in self.onto.object_properties:
                    types = sorted(str(t) for t in self.g.objects(o, _RDF.type) if isinstance(t, URIRef))
                    facts = sorted((str(pp), str(oo)) for pp, oo in self.g.predicate_objects(o) if pp != _RDF.type)
                    out.append({"anchor": str(s), "property": str(p), "node": o, "types": types, "facts": facts,
                                "canon": f"{s.n3()} {p.n3()} {canonical(self.g, o)}"})
            return sorted(out, key=lambda d: d["canon"])
        return self._c("anon_ind", build)

    def anon_class_assertions(self) -> list[tuple[str, ClassExpr, Any]]:
        def build():
            out = []
            for s, o in self.g.subject_objects(_RDF.type):
                if isinstance(s, URIRef) and isinstance(o, BNode):
                    e = parse_class_expr(self.g, o)
                    if e:
                        out.append((str(s), e, o))
            return sorted(out, key=lambda t: (t[0], canonical(self.g, t[2])))
        return self._c("anon_ca", build)

    def axiom_annotations(self) -> list[dict]:
        def build():
            out = []
            for ax in self.g.subjects(_RDF.type, _OWL.Axiom):
                src, prop, tgt = (self.g.value(ax, _OWL.annotatedSource), self.g.value(ax, _OWL.annotatedProperty),
                                  self.g.value(ax, _OWL.annotatedTarget))
                ann = sorted((str(p), str(o)) for p, o in self.g.predicate_objects(ax)
                             if p not in (_RDF.type, _OWL.annotatedSource, _OWL.annotatedProperty, _OWL.annotatedTarget))
                out.append({"node": ax, "source": str(src) if src else None, "property": str(prop) if prop else None,
                            "target": str(tgt) if tgt else None, "annotations": ann,
                            "canon": f"{src} {prop} {tgt}"})
            return sorted(out, key=lambda d: d["canon"])
        return self._c("axioms", build)

    def endpoints(self, p: str, which: str) -> dict:
        """Domaine / portée effectifs : classes nommées (axiomes multiples = intersection) + conjoints nommés d'une
        expression `A ⊓ B` (domain(A ⊓ B) ⊨ domain(A) ∧ domain(B)). `expr` = expression complexe éventuelle,
        `reducible` = faux si elle contient autre chose que des classes nommées en conjonction (→ G01)."""
        key = f"ep:{p}:{which}"
        if key in self.cache:
            return self.cache[key]
        prop = self.onto.object_properties.get(p) or self.onto.datatype_properties.get(p)
        out = {"classes": [], "expr": None, "node": None, "reducible": True}
        if prop is None:
            return out
        named = list(getattr(prop, which, []) or [])
        if which == "range" and p in self.onto.datatype_properties:
            out["classes"] = named
            self.cache[key] = out
            return out
        expr, node = getattr(prop, f"{which}_expr", None), None
        if expr is None:
            pred = _RDFS.domain if which == "domain" else _RDFS.range
            for o in sorted(self.g.objects(URIRef(p), pred), key=lambda x: canonical(self.g, x)):
                if isinstance(o, BNode):
                    e = parse_class_expr(self.g, o)
                    if e and not (e.op == "or" and all(a.op == "named" for a in e.args)):
                        expr, node = e, o
                        break
        if expr is not None:
            conj = named_conjuncts(expr)
            reducible = expr.op in ("and", "named") and len(conj) == len(expr.args or [expr])
            out.update(expr=expr, node=node, reducible=reducible)
            named += [c for c in conj if c not in named]
        out["classes"] = named
        self.cache[key] = out
        return out

    def consume(self, node) -> None:
        if node is not None:
            self.consumed |= subtree(self.g, node)

    # ---- propriétés --------------------------------------------------------------------------
    def non_simple(self) -> set[str]:
        """Propriétés objet non simples (SS §11.2) : transitives, à chaîne, et leurs super-propriétés / inverses."""
        def build():
            ops = self.onto.object_properties
            seeds = {p for p, v in ops.items() if "transitive" in v.characteristics or v.chains}
            out = set(seeds)
            changed = True
            while changed:
                changed = False
                for p, v in ops.items():
                    if p in out:
                        for sp in v.sub_property_of:
                            if sp in ops and sp not in out:
                                out.add(sp); changed = True
                        if v.inverse_of and v.inverse_of not in out:
                            out.add(v.inverse_of); changed = True
                    elif v.inverse_of in out:
                        out.add(p); changed = True
            return out
        return self._c("non_simple", build)

    def inverse_of(self, p: str) -> Optional[str]:
        def build():
            m: dict[str, str] = {}
            for k, v in sorted(self.onto.object_properties.items()):
                if v.inverse_of:
                    m.setdefault(k, v.inverse_of)
                    m.setdefault(v.inverse_of, k)
            return m
        return self._c("inverse", build).get(p)

    def facts_using(self, p: str, include_negative: bool = False) -> list[tuple[str, Any]]:
        out = []
        for i, ind in sorted(self.onto.individuals.items()):
            for f in ind.facts:
                if f.property == p and (include_negative or not f.negative):
                    out.append((i, f))
        return out

    def restricting_classes(self, p: str) -> list[str]:
        return sorted({c for c in self.onto.classes for r, _ in self.all_restrictions(c) if r.property == p and not r.inverse})

    def shape_classes(self, p: str, inverse: bool = False) -> list[str]:
        bucket = "inverse_properties" if inverse else "properties"
        return sorted(c for c, ce in self.sc.get("classes", {}).items() if p in ce.get(bucket, {}))

    def shape_prop(self, c: str, p: str, inverse: bool = False) -> Optional[dict]:
        bucket = "inverse_properties" if inverse else "properties"
        return self.sc.get("classes", {}).get(c, {}).get(bucket, {}).get(p)


# ================================================================================================
# Fabrique de constats
# ================================================================================================
def make_id(rule: str, subject: str, suffix: Optional[str] = None) -> str:
    return f"{rule}:{subject}" + (f":{suffix}" if suffix else "")


def finding(ctx: Ctx, rule: str, subject: str, detail: str, *, suffix: Optional[str] = None,
            related: Optional[list[str]] = None, severity: Optional[str] = None, reco: Optional[dict] = None,
            options: Optional[list[str]] = None, title: Optional[str] = None, rationale: Optional[str] = None) -> Finding:
    """Construit un Finding complet à partir du catalogue : options filtrées pour la cible, recommandation,
    justification. `reco` = {cible: option} surcharge la recommandation du catalogue pour ce constat."""
    spec = catalog.RULES[rule]
    t = ctx.target
    opt_ids = options or [o for o, meta in spec["options"].items() if t in meta.get("targets", ("curiosity", "neo4j"))]
    recommended = (reco or {}).get(t) or spec["reco"].get(t)
    if recommended not in opt_ids:
        opt_ids = list(opt_ids) + [recommended] if recommended in spec["options"] else list(opt_ids)
    opts = [Option(id=o, label=spec["options"][o]["label"], impact=spec["options"][o]["impact"],
                   recommended_for=[t] if o == recommended else []) for o in opt_ids]
    rat = rationale or spec.get("rationale", {}).get(t) or spec.get("rationale", {}).get("*") or ""
    prof = ctx.profile.rationale(rule)
    if prof and prof not in rat:
        rat = (rat + " — " if rat else "") + f"Profil {t} : {prof}"
    return Finding(id=make_id(rule, subject, suffix), rule=rule, severity=severity or spec["severity"],
                   title=title or spec["title"], detail=detail, subject=subject, related=list(related or []),
                   options=opts, recommended=recommended, rationale=rat or None)


# ================================================================================================
# Helpers PG
# ================================================================================================
def add_validation(ctx: Ctx, f: Finding, kind: str, description: str, *, node_type: Optional[str] = None,
                   edge_type: Optional[str] = None, prop: Optional[str] = None, params: Optional[dict] = None,
                   severity: str = "Violation") -> Validation:
    k = sum(1 for v in ctx.pg.validations if v.id.startswith(f.id + "#v")) + 1
    v = Validation(id=f"{f.id}#v{k}", kind=kind, node_type=node_type, edge_type=edge_type, property=prop,
                   params=params or {}, description=description, source=f.subject, severity=severity)
    ctx.pg.validations.append(v)
    return v


def add_materialization(ctx: Ctx, f: Finding, kind: str, description: str, **kw) -> Materialization:
    k = sum(1 for m in ctx.pg.materializations if m.id.startswith(f.id + "#m")) + 1
    m = Materialization(id=f"{f.id}#m{k}", kind=kind, description=description, source=f.subject, **kw)
    ctx.pg.materializations.append(m)
    return m


def props_of(ctx: Ctx, iri: str) -> list[tuple[NodeType, PGProperty]]:
    return [(nt, p) for nt in ctx.pg.node_types.values() for p in nt.properties if p.source == iri]


def edges_of(ctx: Ctx, iri: str) -> list[EdgeType]:
    return [e for e in ctx.pg.edge_types if e.source == iri and not e.derived]


__all__ = [n for n in dir() if not n.startswith("__")]
