"""Familles A / M / G — annotations, métadonnées d'ontologie, constructs non représentables."""
from __future__ import annotations

from ...core.onto_model import RDFS
from ._base import Ctx, finding, sha8

LABEL = RDFS + "label"


def _entities(ctx: Ctx):
    o = ctx.onto
    for coll in (o.classes, o.object_properties, o.datatype_properties, o.datatypes, o.individuals):
        for k, v in coll.items():
            yield k, v


def detect_a01(ctx: Ctx):
    out = []
    for iri, e in sorted(_entities(ctx), key=lambda kv: kv[0]):
        ann = [a for a in e.annotations if a.property != LABEL]
        if e.comments or ann:
            kinds = sorted({ctx.short(a.property) for a in ann} | ({"rdfs:comment"} if e.comments else set()))
            if any(f.id == f"A01:{iri}" for f in out):
                continue
            out.append(finding(ctx, "A01", iri, f"{ctx.short(iri)} : {', '.join(kinds)} → documentation du schéma."))
    return out


def detect_a02(ctx: Ctx):
    out = []
    for ax in ctx.axiom_annotations():
        ctx.consume(ax["node"])
        subj = ax["source"] or ctx.onto.meta.iri
        out.append(finding(ctx, "A02", subj, f"Axiome annoté ({ctx.short(ax['property'] or '?')} "
                           f"{ctx.short(ax['target'] or '?')}) : "
                           + "; ".join(f"{ctx.short(p)} = {v}" for p, v in ax["annotations"]),
                           suffix=sha8(ax["canon"]), related=[x for x in (ax["target"],) if x]))
    return out


def detect_a03(ctx: Ctx):
    return [finding(ctx, "A03", iri, f"{ctx.short(iri)} est dépréciée (owl:deprecated).")
            for iri, e in sorted(_entities(ctx), key=lambda kv: kv[0]) if e.deprecated]


def detect_m01(ctx: Ctx):
    m = ctx.onto.meta
    bits = [f"versionIRI {m.version_iri}" if m.version_iri else None,
            f"{len(m.annotations)} annotation(s)" if m.annotations else None]
    return [finding(ctx, "M01", m.iri, f"Ontologie {m.iri} : " + (", ".join(b for b in bits if b) or "en-tête minimal") + ".")]


def detect_m02(ctx: Ctx):
    m = ctx.onto.meta
    return [finding(ctx, "M02", m.iri, f"owl:imports {imp} : fermeture d'import non chargée (hors-ligne) ; les termes "
                    "importés restent des références externes.", suffix=imp, related=[imp]) for imp in sorted(m.imports)]


def detect_g01(ctx: Ctx):
    """À exécuter EN DERNIER : un triplet non mappé que nulle règle n'a expliqué produit un G01."""
    from rdflib import BNode
    from ._base import canonical, expr_text
    out = []
    # domaine / portée complexes non réductibles à des classes nommées : constat explicite (jamais silencieux)
    props = sorted(set(ctx.onto.object_properties) | set(ctx.onto.datatype_properties))
    for p in props:
        for which in ("domain", "range"):
            ep = ctx.endpoints(p, which)
            if ep["expr"] is None or ep["reducible"]:
                continue
            ctx.consume(ep["node"])
            canon = canonical(ctx.g, ep["node"]) if ep["node"] is not None else expr_text(ep["expr"])
            kept = ", ".join(ctx.short(c) for c in ep["classes"]) or "aucune classe nommée"
            out.append(finding(ctx, "G01", p, f"{'Domaine' if which == 'domain' else 'Portée'} complexe de "
                               f"{ctx.short(p)} : {expr_text(ep['expr'], ctx.short)} — rattaché à : {kept} ; "
                               "le reste de l'expression n'est pas transposé.", suffix=sha8(which + canon),
                               related=ep["classes"]))
    for u in ctx.onto.unmapped:
        nodes = set()
        for t in u.triples:
            for term in (t[0], t[2]):
                if isinstance(term, str) and term.startswith("_:"):
                    nodes.add(term[2:])
        consumed = {str(b) for b in ctx.consumed}
        if nodes and nodes & consumed:
            continue
        subj = u.subject
        if not subj:
            subj = next((t[0].strip("<>") for t in u.triples if t[0].startswith("<")), ctx.onto.meta.iri)
        out.append(finding(ctx, "G01", subj, f"Construct non représentable : {u.description}",
                           suffix=sha8(u.description + repr(sorted(u.triples)))))
    return out


DETECT = {"A01": detect_a01, "A02": detect_a02, "A03": detect_a03, "M01": detect_m01, "M02": detect_m02}
DETECT_LAST = {"G01": detect_g01}


def apply_a03(ctx: Ctx, f, opt):
    ctx.plan.setdefault("deprecated", {})[f.subject] = opt


def apply_m01(ctx: Ctx, f, opt):
    m = ctx.onto.meta
    ctx.pg.meta.iri = m.iri
    ctx.pg.meta.name = m.labels.get("fr") or next((a.value for a in m.annotations if a.property.endswith("/title")
                                                   and a.lang == "fr"), None) or ctx.short(m.iri)


APPLY_PLAN = {"A03": apply_a03, "M01": apply_m01}


def apply_a03_build(ctx: Ctx, f, opt):
    if opt == "flag_deprecated":
        for nt in ctx.pg.node_types.values():
            if f.subject in nt.source:
                nt.description = "[DÉPRÉCIÉ] " + (nt.description or "")


APPLY_BUILD = {"A03": apply_a03_build}
