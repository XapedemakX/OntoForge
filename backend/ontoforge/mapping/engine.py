"""Moteur de mapping OWL 2 + SHACL → PGModel (lot L3, propriétaire : lead).

analyze(onto, shapes, target, decisions) :
  1. détecte (66 règles, ids stables `<règle>:<IRI sujet>[:suffixe]`, D-035) ;
  2. applique pour chaque constat l'option décidée (si valide) sinon la recommandée pour la cible ;
  3. construit un PGModel complet et cohérent (types de nœuds, relations, propriétés, clés, validations,
     matérialisations), enrichi par les shapes SHACL ;
  4. vérifie les invariants (aucune relation vers un type inexistant, noms uniques, contraintes de cible).
Déterministe : mêmes entrées → même sortie (tout est trié).
"""
from __future__ import annotations

import datetime as _dt
from typing import Optional

from ..core.onto_model import local_name, OntoModel
from ..core.pg_model import PGMeta, PGModel, Target
from ..core.shapes_model import ShapesModel
from . import decisions as _decisions
from .profile_api import get_profile
from .rules import REGISTRY, LAST, classes, data, individuals, keys, naming, objects, shacl as shacl_rules
from .rules._base import Ctx, build_unmapped_graph


def _shape_index(shapes: Optional[ShapesModel], warnings: list[str]) -> dict:
    if shapes is None or not (shapes.shapes or shapes.property_shapes):
        return {}
    try:
        from ..shacl.shacl_to_pg import shape_constraints  # dépendance de l'agent shacl (import paresseux)
    except Exception as exc:  # pragma: no cover - repli si le module manque
        warnings.append(f"shacl_to_pg indisponible ({exc!r}) : shapes ignorées")
        return {}
    try:
        return shape_constraints(shapes)
    except Exception as exc:  # pragma: no cover
        warnings.append(f"shape_constraints a échoué ({exc!r}) : shapes ignorées")
        return {}


def analyze(onto: OntoModel, shapes: Optional[ShapesModel], target: Target,
            decisions: Optional[dict[str, str]] = None) -> PGModel:
    profile = get_profile(target)
    ctx = Ctx(onto=onto, shapes=shapes, target=target, profile=profile, decisions=dict(decisions or {}))
    ctx.sc = _shape_index(shapes, ctx.warnings)
    ctx.g, w = build_unmapped_graph(onto)
    ctx.warnings += w + profile.warnings
    ctx.pg = PGModel(target=target, meta=PGMeta(name=onto.meta.iri, iri=onto.meta.iri))

    # 1. détection --------------------------------------------------------------------------------
    found = []
    for rid, info in REGISTRY.items():
        if rid not in LAST:
            found += info.detect(ctx)
    for rid in sorted(LAST):
        found += REGISTRY[rid].detect(ctx)
    for f in sorted(found, key=lambda x: x.id):
        if f.id in ctx.findings:  # garde-fou : un id = un constat (fusion des sujets liés)
            prev = ctx.findings[f.id]
            prev.related = sorted(set(prev.related) | set(f.related))
            continue
        ctx.findings[f.id] = f

    _reclassify(ctx)
    _attach_roots(ctx)

    # 2. décisions --------------------------------------------------------------------------------
    for g in _decisions.resolve(ctx, decisions):
        ctx.findings[g.id] = g
    ordered = sorted(ctx.findings.values(), key=lambda x: x.id)

    def opt(f):
        return f.chosen or f.recommended

    # 3. construction -----------------------------------------------------------------------------
    for f in ordered:
        p = REGISTRY.get(f.rule)
        if p and p.plan:
            p.plan(ctx, f, opt(f))
    from .rules import annotations as _annotations
    _annotations.after_plan(ctx)  # L49 : ce qu'emporte l'exclusion d'une classe dépréciée est un constat, pas une perte silencieuse
    classes.build_nodes(ctx)
    data.build_props(ctx)
    keys.build_uri(ctx)
    for f in ordered:
        p = REGISTRY.get(f.rule)
        if p and p.build and p.module == "keys":
            p.build(ctx, f, opt(f))
    objects.build_edges(ctx)
    for f in ordered:
        p = REGISTRY.get(f.rule)
        if p and p.build and p.module not in ("keys",):
            p.build(ctx, f, opt(f))
    shacl_rules.build_shacl(ctx)
    individuals.finalize_reference_nodes(ctx)
    for f in naming.finalize(ctx):
        ctx.findings.setdefault(f.id, f)
    for f in _cycle_notes(ctx):
        ctx.findings.setdefault(f.id, f)
    _finalize(ctx)
    return ctx.pg


def _reclassify(ctx: Ctx) -> None:
    """L47 (D-L47-01) : un constat « review » sans vrai choix passe en « auto » (motif dans `auto_reason`).

    Sans vrai choix = une seule option (règles de `catalog.SINGLE_OPTION_AUTO`, vide pour l'instant) ou option recommandée sans perte
    (table `catalog.NO_CHOICE`). Un constat « lost » n'est
    jamais reclassé (D-L14-02). La décision d'un humain sur un tel constat reste appliquée.
    """
    from .rules import catalog
    for f in ctx.findings.values():
        if f.severity != "review" or not f.options:
            continue
        if len({o.id for o in f.options}) == 1:
            reason = catalog.SINGLE_OPTION_REASON if f.rule in catalog.SINGLE_OPTION_AUTO else None
        else:
            nc = catalog.NO_CHOICE.get(f.rule, {}).get(ctx.target)
            reason = nc[1] if nc and f.recommended == nc[0] and nc[0] in {o.id for o in f.options} else None
            if reason and ctx.target == "curiosity" and _tightens_curiosity(ctx, f):
                reason = None
        if reason:
            f.severity = "auto"
            f.auto_reason = reason


def _tightens_curiosity(ctx: Ctx, f) -> bool:
    """Vrai si la validation Curiosity d'un constat O09 renforce le modèle : `exactly n` (n >= 1) contient un minimum, donc exige la donnée
    et fait sortir le connecteur en code 2. Un `max n` ou une propriété fonctionnelle ne demande aucune donnée de plus."""
    if f.rule != "O09" or not ctx.is_class(f.subject) or not f.related:
        return False
    return any(r.property == f.related[0] and r.kind == "exactly" and (r.n or 0) >= 1
               for r, _ in ctx.all_restrictions(f.subject))


def _attach_roots(ctx: Ctx) -> None:
    """L47 (P-02) : racine de hiérarchie du sujet des constats d'héritage, pour l'arbitrage par branche (la plus petite IRI si plusieurs racines)."""
    from .rules import catalog
    for f in ctx.findings.values():
        if f.rule in catalog.HIERARCHY_RULES and ctx.is_class(f.subject):
            roots = [a for a in ctx.ancestors(f.subject) if not ctx.parents(a)]
            f.root = min(roots) if roots else f.subject


def _cycle_notes(ctx: Ctx) -> list:
    """Constats d'information BP03 : cycles de sous-classes déjà présents (import, ancien projet). Jamais une erreur."""
    from ..core.pg_model import Finding
    from ..editing.cycles import find_cycles
    out = []
    for cyc in find_cycles(ctx.onto):
        names = ", ".join(ctx.short(x) for x in cyc)
        detail = (f"La classe {names} est déclarée sous-classe d'elle-même : en OWL 2 cet axiome est sans effet. Retirez-le." if len(cyc) == 1 else
                  f"Les classes {names} forment un cycle de sous-classes : en OWL 2 elles sont équivalentes entre elles. "
                  "Le moteur les transpose chacune comme un type de nœud propre, sans héritage aplati entre elles. "
                  "Corrigez le cycle (retirez une des sous-classes) ou déclarez une équivalence explicite.")
        out.append(Finding(
            id=f"BP03:{cyc[0]}", rule="BP03", severity="info", title="Cycle de sous-classes",
            detail=detail,
            subject=cyc[0], related=cyc[1:]))
    return out


def _finalize(ctx: Ctx) -> None:
    pg, prof = ctx.pg, ctx.profile
    uri = prof.prop("uri")
    # Neo4j : un sous-type hérite de la clé de son ancêtre (labels[1:]) quand il n'a que la clé par défaut
    if prof.multi_label:
        for nt in pg.node_types.values():
            if nt.key == [uri]:
                for lab in nt.labels[1:]:
                    anc = pg.node_types.get(lab)
                    if anc and anc.key and anc.key != [uri]:
                        nt.key = list(anc.key)
                        break
    # Curiosity : un seul label, pas de propriétés d'arête, reverse toujours renseigné
    if ctx.target == "curiosity":
        for nt in pg.node_types.values():
            nt.labels = [nt.name]
        for e in pg.edge_types:
            if e.properties:
                e.note = ((e.note or "") + " Propriétés d'arête retirées (non supportées par Curiosity).").strip()
                e.properties = []
            if not e.reverse:
                e.reverse = prof.reverse(e.name) or f"{e.name}Inverse"
        from .reverse_names import uniquify_reverses
        uniquify_reverses(pg.edge_types, is_default=lambda e: not e.symmetric and e.reverse == f"{e.name}Inverse",
                           reserved=[local_name(u) for u in list(ctx.onto.object_properties) + list(ctx.onto.datatype_properties)])
    # cohérence : aucune relation vers un type inexistant
    pg.edge_types = [e for e in pg.edge_types if e.from_ in pg.node_types and e.to in pg.node_types]
    # dédoublonnage + tri déterministe
    seen, edges = set(), []
    for e in sorted(pg.edge_types, key=lambda e: (e.name, e.from_, e.to, e.source or "", e.derived)):
        k = (e.name, e.from_, e.to)
        if k not in seen:
            seen.add(k)
            edges.append(e)
    pg.edge_types = edges
    pg.node_types = dict(sorted(pg.node_types.items()))
    for nt in pg.node_types.values():
        if not nt.key:
            nt.key = [uri]
        nt.source = list(dict.fromkeys(nt.source))
    vids, vals = set(), []
    for v in sorted(pg.validations, key=lambda v: v.id):
        if v.id not in vids:
            vids.add(v.id)
            vals.append(v)
    pg.validations = vals
    pg.materializations = sorted(pg.materializations, key=lambda m: m.id)
    pg.findings = sorted(ctx.findings.values(), key=lambda f: f.id)
    pg.decisions = _decisions.clean(ctx.decisions)
