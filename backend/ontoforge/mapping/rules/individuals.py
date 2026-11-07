"""Famille I — individus : I01–I05."""
from __future__ import annotations

from ...core.pg_model import EdgeType
from ._base import Ctx, add_materialization, add_validation, finding, sha8
from .classes import node_targets


def _enum_members(ctx: Ctx) -> set[str]:
    out = set()
    for c, v in ctx.onto.classes.items():
        out |= set(v.one_of or [])
        for e, _ in ctx.class_definitions(c):
            if e.op == "oneOf":
                out |= set(e.individuals)
    for grp in ctx.onto.all_different:
        out |= set(grp)
    return out


def oneof_members(ctx: Ctx) -> set[str]:
    """Individus membres d'un owl:oneOf : déjà traités par C08 (nœuds de référence), donc pas d'I01 séparé (L13)."""
    out = set()
    for c, v in ctx.onto.classes.items():
        out |= set(v.one_of or [])
        for e, _ in ctx.class_definitions(c):
            if e.op == "oneOf":
                out |= set(e.individuals)
    return out


def _ranges(ctx: Ctx) -> set[str]:
    return {r for v in ctx.onto.object_properties.values() for r in v.range}


def detect_i01(ctx: Ctx):
    enum, ranges, out = _enum_members(ctx), _ranges(ctx), []
    in_c08 = oneof_members(ctx)
    for i, ind in sorted(ctx.onto.individuals.items()):
        if i in in_c08:
            continue  # C08 porte déjà ce membre (doublon I01/C08)
        has_links = any(f.is_iri and not f.negative for f in ind.facts)
        ref = i in enum or (set(ind.types) & ranges and not has_links)
        out.append(finding(ctx, "I01", i, f"Individu {ctx.short(i)} ({', '.join(ctx.short(t) for t in ind.types) or 'sans type'})"
                           + (" : membre d'une énumération / d'un référentiel." if ref else " : donnée d'exemple."),
                           related=ind.types, reco=None if ref else {"curiosity": "ignore", "neo4j": "ignore"}))
    return out


def detect_i02(ctx: Ctx):
    out, seen = [], set()
    for i, ind in sorted(ctx.onto.individuals.items()):
        for o in ind.same_as:
            if frozenset((i, o)) not in seen:
                seen.add(frozenset((i, o)))
                out.append(finding(ctx, "I02", i, f"{ctx.short(i)} owl:sameAs {ctx.short(o)}.", related=[o]))
    return out


def detect_i03(ctx: Ctx):
    out = []
    for grp in ctx.onto.all_different:
        out.append(finding(ctx, "I03", sorted(grp)[0] if False else grp[0],
                           f"AllDifferent({', '.join(ctx.short(x) for x in grp)}).", related=grp,
                           suffix=sha8(" ".join(sorted(grp)))))
    for i, ind in sorted(ctx.onto.individuals.items()):
        if ind.different_from:
            out.append(finding(ctx, "I03", i, f"{ctx.short(i)} owl:differentFrom "
                               f"{', '.join(ctx.short(x) for x in ind.different_from)}.", related=ind.different_from))
    return out


def detect_i04(ctx: Ctx):
    out = {}
    for i, ind in sorted(ctx.onto.individuals.items()):
        for f in ind.facts:
            if f.negative:
                fid = f"I04:{i}:{f.property}"
                if fid not in out:
                    out[fid] = finding(ctx, "I04", i, f"NegativePropertyAssertion : {ctx.short(i)} "
                                       f"n'a PAS {ctx.short(f.property)} = {ctx.short(f.value) if f.is_iri else repr(f.value)}.",
                                       suffix=f.property, related=[f.property])
    return list(out.values())


def detect_i05(ctx: Ctx):
    out = []
    for i, ind in sorted(ctx.onto.individuals.items()):
        ts = [t for t in ind.types if ctx.is_class(t)]
        minimal = sorted(t for t in ts if not any(o != t and ctx.subsumes(t, o) for o in ts))
        if len(minimal) >= 2:
            out.append(finding(ctx, "I05", i, f"{ctx.short(i)} a plusieurs types non liés : "
                               f"{', '.join(ctx.short(t) for t in minimal)}.", related=minimal))
    return out


DETECT = {"I01": detect_i01, "I02": detect_i02, "I03": detect_i03, "I04": detect_i04, "I05": detect_i05}


def _types(ctx, i):
    ind = ctx.onto.individuals.get(i)
    return ind.types if ind else []


def apply_i01(ctx: Ctx, f, opt):
    if opt != "reference_nodes":
        return
    ref = ctx.plan.setdefault("reference_nodes", {})
    for t in _types(ctx, f.subject):
        for nt in node_targets(ctx, t):
            ref.setdefault(nt, []).append(f.subject)


def apply_i02(ctx: Ctx, f, opt):
    other = f.related[0]
    nts = sorted({nt for x in (f.subject, other) for t in _types(ctx, x) for nt in node_targets(ctx, t)})
    if opt == "merge_nodes":
        add_materialization(ctx, f, "sameAs", f"Fusionner {ctx.short(f.subject)} et {ctx.short(other)} "
                            "(clé canonique + alias).", node_type=nts[0] if nts else None)
    elif nts:
        prof = ctx.profile
        if not any(e.name == prof.edge("sameAs") for e in ctx.pg.edge_types):
            ctx.pg.edge_types.append(EdgeType(name=prof.edge("sameAs"), from_=nts[0], to=nts[0], source=f.subject,
                                              reverse=prof.reverse("sameAs", symmetric=True), symmetric=True,
                                              note="Identité OWL (I02)."))


def apply_i04(ctx: Ctx, f, opt):
    if opt != "validation":
        return
    prop = f.related[0]
    vals = [x for x in ctx.onto.individuals[f.subject].facts if x.negative and x.property == prop]
    nts = sorted({nt for t in _types(ctx, f.subject) for nt in node_targets(ctx, t)})
    for v in vals:
        add_validation(ctx, f, "other", f"{ctx.short(f.subject)} ne doit pas avoir {ctx.short(prop)} = "
                       f"{ctx.short(v.value) if v.is_iri else repr(v.value)}.", node_type=nts[0] if nts else None,
                       params={"individual": f.subject, "property": prop, "value": v.value, "forbidden": True})


APPLY_BUILD = {"I01": apply_i01, "I02": apply_i02, "I04": apply_i04}


def finalize_reference_nodes(ctx: Ctx) -> None:
    """Nœuds de référence : liste des valeurs + propriétés de libellé par langue (les rdfs:label des individus
    sont des données de référence, pas du schéma : ils sont conservés, pas perdus en silence)."""
    from ...core.pg_model import PGProperty
    for nt, iris in sorted(ctx.plan.get("reference_nodes", {}).items()):
        t = ctx.pg.node_types.get(nt)
        if t is None:
            continue
        iris = sorted(set(iris))
        if "Nœuds de référence" not in (t.description or ""):
            t.description = (t.description or "") + f" Nœuds de référence : {', '.join(ctx.local(i) for i in iris)}."
        langs = sorted({l for i in iris for l in ctx.onto.individuals[i].labels if l})
        for lang in langs:
            name = ctx.profile.prop("label", lang)
            if not any(x.name == name for x in t.properties):
                t.properties.append(PGProperty(name=name, type="String", lang=lang, source="http://www.w3.org/2000/01/rdf-schema#label",
                                               note="Libellé des nœuds de référence (rdfs:label des individus)."))
