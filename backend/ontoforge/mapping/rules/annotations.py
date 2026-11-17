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


IS_REPLACED_BY = "http://purl.org/dc/terms/isReplacedBy"


def detect_a03(ctx: Ctx):
    """L49 : constat à arbitrer (exclure par défaut, ou garder avec drapeau) ; remplaçant cité (dcterms:isReplacedBy)."""
    out = []
    for iri, e in sorted(_entities(ctx), key=lambda kv: kv[0]):
        if not e.deprecated:
            continue
        reps = sorted({a.value for a in e.annotations if a.property == IS_REPLACED_BY})
        detail = f"{ctx.short(iri)} est dépréciée (owl:deprecated)."
        if reps:
            detail += " Remplacée par : " + ", ".join(ctx.short(r) for r in reps) + "."
        out.append(finding(ctx, "A03", iri, detail, related=reps))
    return out


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




def _endpoints(ctx: Ctx, p: str) -> list[list[str]]:
    """Extrémités résolues comme à la construction (revue it2) : ``objects.resolve`` pour une relation (domaine, portée,
    union, inverse, restrictions, shapes, faits : règle O02), classes porteuses de ``data.build_props`` pour un attribut."""
    if p in ctx.onto.object_properties:
        from .objects import resolve
        return [resolve(ctx, p, "domain"), resolve(ctx, p, "range")]
    from .data import _dom, _users
    union, _ = ctx.union_of(p, "domain")
    if union:
        return [list(union)]
    if _dom(ctx, p):
        return [_dom(ctx, p)]
    return [_users(ctx, p)] if ctx.option_of("D02", p, default="attach_to_users") == "attach_to_users" else [[]]


def exclusion_losses(ctx: Ctx) -> dict[str, dict[str, list[str]]]:
    """Classes dépréciées exclues → propriétés NON dépréciées qu'elles emportent : ``{classe: {"full": [...], "partial": [...]}}``.

    Perte totale : d'un côté au moins, toutes les extrémités résolues sont exclues (aucune arête ou propriété générée).
    Perte partielle : une partie seulement des extrémités d'un côté est exclue (union, plusieurs domaines) ; le reste est généré.
    Revues L49 it1 et it2 : jamais de perte silencieuse."""
    o, plan = ctx.onto, ctx.plan.get("deprecated", {})
    excl = {c for c, v in o.classes.items() if v.deprecated and plan.get(c, "exclude") == "exclude"}
    out: dict[str, dict[str, list[str]]] = {}
    if not excl:
        return out
    props = [(p, v) for p, v in sorted(o.object_properties.items())] + [(p, v) for p, v in sorted(o.datatype_properties.items())]
    for p, v in props:
        if v.deprecated:
            continue
        sides = [set(x) for x in _endpoints(ctx, p)]
        hit = set().union(*(side & excl for side in sides))
        if not hit:
            continue
        full = any(side and side <= excl for side in sides)
        for c in sorted(hit):
            out.setdefault(c, {"full": [], "partial": []})["full" if full else "partial"].append(p)
    return out


def after_plan(ctx: Ctx) -> None:
    """Après les décisions : le constat A03 d'une classe exclue liste ce qu'il emporte ; le constat de base (O01, O02, D01…)
    d'une propriété totalement emportée passe de « auto » ou « review » à « lost » (perdu, à l'humain : D-L14-02), avec la
    raison ; une perte partielle est seulement notée (le reste est généré)."""
    losses = exclusion_losses(ctx)
    for c, d in losses.items():
        a03 = ctx.findings.get(f"A03:{c}")
        if a03 is not None:
            if d["full"] and "Exclure entraîne la perte de" not in a03.detail:
                a03.detail += " Exclure entraîne la perte de : " + ", ".join(ctx.short(p) for p in d["full"]) + "."
            if d["partial"] and " En partie : " not in a03.detail:
                a03.detail += " En partie : " + ", ".join(ctx.short(p) for p in d["partial"]) + "."
            a03.related = list(dict.fromkeys(a03.related + d["full"]))
        for p, full in [(p, True) for p in d["full"]] + [(p, False) for p in d["partial"]]:
            fs = sorted((x for x in ctx.findings.values() if x.subject == p and x.rule[:1] in ("O", "D")), key=lambda x: x.id)
            base = next((x for x in fs if x.rule in ("O01", "O02", "D01", "D02", "O03", "D03")), fs[0] if fs else None)
            if base is None:
                continue
            if full:
                base.severity = "lost"
                note = f" Non générée : {ctx.short(c)} est dépréciée et exclue (A03:{ctx.short(c)})."
            else:
                note = f" Générée en partie : les extrémités vers {ctx.short(c)}, dépréciée et exclue, sont perdues (A03:{ctx.short(c)})."
            if note not in base.detail:
                base.detail += note

def apply_m01(ctx: Ctx, f, opt):
    m = ctx.onto.meta
    ctx.pg.meta.iri = m.iri
    ctx.pg.meta.name = m.labels.get("fr") or next((a.value for a in m.annotations if a.property.endswith("/title")
                                                   and a.lang == "fr"), None) or ctx.short(m.iri)


APPLY_PLAN = {"A03": apply_a03, "M01": apply_m01}


def apply_a03_build(ctx: Ctx, f, opt):
    """Option « garder avec drapeau » : préfixe [DÉPRÉCIÉ] sur le type de nœud, la relation ou la propriété issus de l'entité."""
    if opt != "flag_deprecated":
        return
    tag = "[DÉPRÉCIÉ] "
    for nt in ctx.pg.node_types.values():
        if f.subject in nt.source and not (nt.description or "").startswith(tag):
            nt.description = tag + (nt.description or "")
        for p in nt.properties:
            if p.source == f.subject and not (p.description or "").startswith(tag):
                p.description = tag + (p.description or "")
    for e in ctx.pg.edge_types:
        if e.source == f.subject and not (e.description or "").startswith(tag):
            e.description = tag + (e.description or "")


APPLY_BUILD = {"A03": apply_a03_build}
