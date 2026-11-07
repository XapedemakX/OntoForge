"""Rapport de transposition (Markdown, français) — `generate(pg, onto=None) -> {"rapport-transposition.md": …}`.

Sections : synthèse chiffrée · hypothèse monde clos (rappelée une fois) · nœuds · relations ·
ce qui est perdu ou à risque (option retenue ou recommandée « non arbitré », impact, compensation) ·
transposé automatiquement · validations à implémenter · matérialisations · constats non transposés.
"""
from __future__ import annotations

from typing import Optional

from ..core.onto_model import OntoModel, local_name
from ..core.pg_model import Finding, PGModel

FILENAME = "rapport-transposition.md"
TARGET_NAME = {"curiosity": "Curiosity", "neo4j": "Neo4j"}
SEV = {"auto": "automatique", "review": "à arbitrer", "lost": "perdu"}
COMP = {"none": "—", "validation": "validation applicative", "materialization": "matérialisation",
        "query": "requête", "documentation": "documentation", "rename": "renommage", "human": "arbitrage humain"}


def _esc(s: Optional[str]) -> str:
    return (s or "").replace("|", "\\|").replace("\n", " ").strip()


def _short(iri: str, onto: Optional[OntoModel]) -> str:
    if onto:
        for pfx, ns in sorted(onto.meta.prefixes.items(), key=lambda kv: -len(kv[1])):
            if ns and iri.startswith(ns) and len(iri) > len(ns):
                return f"{pfx}:{iri[len(ns):]}"
    return local_name(iri) if "#" in iri or "/" in iri else iri


def _compact(text: str, onto: Optional[OntoModel]) -> str:
    """Id lisible : IRIs compactées en CURIE (ex. O10:am:RepairOrder:am:includesOperation#v1)."""
    if onto:
        for pfx, ns in sorted(onto.meta.prefixes.items(), key=lambda kv: -len(kv[1])):
            if ns:
                text = text.replace(ns, f"{pfx}:")
    return text


def _compensation(f: Finding, pg: PGModel) -> str:
    try:
        from ..mapping.rules.catalog import RULES
        comp = COMP.get(RULES.get(f.rule, {}).get("compensation", ""), "")
    except Exception:  # pragma: no cover
        comp = ""
    vals = [v for v in pg.validations if v.id.startswith(f.id + "#")]
    mats = [m for m in pg.materializations if m.id.startswith(f.id + "#")]
    bits = []
    if vals:
        bits.append(f"{len(vals)} validation(s)")
    if mats:
        bits.append(f"{len(mats)} matérialisation(s)")
    chosen = f.chosen or f.recommended
    if chosen in ("ignore", "doc_only", "report", "exclude"):
        return "aucune (documenté)"
    return ", ".join(bits) or comp or "—"


def _option(f: Finding) -> tuple[str, str]:
    oid = f.chosen or f.recommended or "—"
    opt = next((o for o in f.options if o.id == oid), None)
    label = f"`{oid}`" + ("" if f.chosen else " *(non arbitré, recommandé)*")
    return label, (opt.impact if opt else "")


def generate(pg: PGModel, onto: Optional[OntoModel] = None) -> dict[str, str]:
    t = TARGET_NAME.get(pg.target, pg.target)
    s = pg.summary()
    by_sev = {k: [f for f in pg.findings if f.severity == k] for k in ("auto", "review", "lost")}
    decided = [f for f in pg.findings if f.severity in ("review", "lost") and f.chosen]
    pending = [f for f in pg.findings if f.severity in ("review", "lost") and not f.chosen]
    L: list[str] = []
    L.append(f"# Rapport de transposition — {pg.meta.name or pg.meta.iri or 'ontologie'} → {t}")
    L.append("")
    if pg.meta.iri:
        L.append(f"Ontologie source : `{pg.meta.iri}` · cible : **{t}** · OntoForge {pg.meta.ontoforge_version}")
        L.append("")
    L.append("## Synthèse")
    L.append("")
    L.append("| Indicateur | Valeur |")
    L.append("|---|---|")
    L.append(f"| Constats | {len(pg.findings)} |")
    L.append(f"| Transposés automatiquement (auto) | {s['auto']} |")
    L.append(f"| À arbitrer (review) | {s['review']} |")
    L.append(f"| Perdus sans compensation native (lost) | {s['lost']} |")
    L.append(f"| Arbitrés / non arbitrés (review + lost) | {s['decided']} / {s['pending']} |")
    L.append(f"| Types de nœuds / relations | {len(pg.node_types)} / {len(pg.edge_types)} |")
    L.append(f"| Validations à implémenter / matérialisations | {len(pg.validations)} / {len(pg.materializations)} |")
    L.append("")
    L.append("> **Hypothèse de monde clos.** OWL raisonne en monde ouvert, sans hypothèse du nom unique : un axiome y "
             "*infère* des faits (domaine, portée, restrictions, clés). Le schéma property graph est un *contrat "
             "d'ingestion* en monde clos : ces axiomes deviennent ici des contraintes ou des validations, ce qui est un "
             "renforcement (ce qui manque est une erreur, deux clés différentes sont deux nœuds). Ce rappel vaut pour "
             "tout le rapport.")
    L.append("")
    if pending:
        L.append(f"**{len(pending)} constat(s) non arbitré(s)** : la recommandation pour {t} a été appliquée "
                 "(marquée « non arbitré »).")
        L.append("")

    # ---------------------------------------------------------------- nœuds
    L.append("## Types de nœuds")
    L.append("")
    L.append("| Type | Labels | Clé | Propriétés | Classes OWL sources |")
    L.append("|---|---|---|---|---|")
    for nt in pg.node_types.values():
        props = ", ".join(p.name + ("*" if p.required else "") + ("[]" if p.is_list else "") + f": {p.type}"
                          for p in nt.properties)
        name = nt.name + (" *(abstrait)*" if nt.abstract else "")
        L.append(f"| {name} | {', '.join(nt.labels)} | {', '.join(nt.key)} | {_esc(props)} | "
                 f"{', '.join(_short(x, onto) for x in nt.source)} |")
    L.append("")
    L.append("`*` obligatoire · `[]` liste.")
    L.append("")
    # ---------------------------------------------------------------- relations
    L.append("## Relations")
    L.append("")
    L.append("| Relation | De | Vers | Retour | Cardinalité (sortie / entrée) | Propriétés | Source | Note |")
    L.append("|---|---|---|---|---|---|---|---|")
    for e in pg.edge_types:
        props = ", ".join(f"{p.name}: {p.type}" for p in e.properties)
        flags = []
        if e.derived:
            flags.append("dérivée")
        if e.symmetric:
            flags.append("symétrique")
        if not e.directed:
            flags.append("non orientée")
        note = "; ".join(flags + ([e.note] if e.note else []))
        L.append(f"| {e.name} | {e.from_} | {e.to} | {e.reverse or '—'} | {e.cardinality.out} / {e.cardinality.in_} | "
                 f"{_esc(props) or '—'} | {_short(e.source or '', onto)} | {_esc(note)} |")
    L.append("")

    # ---------------------------------------------------------------- perdu / à risque
    L.append("## Ce qui est perdu ou à risque")
    L.append("")
    for sev, title in (("lost", "Perdu (aucun équivalent natif)"), ("review", "À risque (à arbitrer)")):
        items = by_sev[sev]
        L.append(f"### {title} — {len(items)}")
        L.append("")
        if not items:
            L.append("Aucun.")
            L.append("")
            continue
        L.append("| Règle | Sujet | Constat | Option retenue | Impact | Compensation |")
        L.append("|---|---|---|---|---|---|")
        for f in items:
            opt, impact = _option(f)
            L.append(f"| {f.rule} | {_short(f.subject, onto)} | {_esc(f.title)} : {_esc(f.detail)} | {opt} | "
                     f"{_esc(impact)} | {_esc(_compensation(f, pg))} |")
        L.append("")

    # ---------------------------------------------------------------- auto
    L.append(f"## Transposé automatiquement — {len(by_sev['auto'])}")
    L.append("")
    counts: dict[str, int] = {}
    for f in by_sev["auto"]:
        counts[f"{f.rule} — {f.title}"] = counts.get(f"{f.rule} — {f.title}", 0) + 1
    for k, n in sorted(counts.items()):
        L.append(f"- {k} : {n}")
    L.append("")

    # ---------------------------------------------------------------- validations
    L.append(f"## Validations à implémenter — {len(pg.validations)}")
    L.append("")
    L.append("Contrôles applicatifs (connecteur / requêtes de détection) : la base ne les impose pas nativement.")
    L.append("")
    if pg.validations:
        L.append("| Id | Type | Cible | Description | Origine |")
        L.append("|---|---|---|---|---|")
        for v in pg.validations:
            tgt = ".".join(x for x in (v.node_type, v.property) if x) or ""
            if v.edge_type:
                tgt = (tgt + " " if tgt else "") + f"[{v.edge_type}]"
            L.append(f"| `{_compact(v.id, onto)}` | {v.kind} | {_esc(tgt)} | "
                     f"{_esc(v.description)} | {_short(v.source or '', onto)} |")
        L.append("")

    # ---------------------------------------------------------------- matérialisations
    L.append(f"## Matérialisations — {len(pg.materializations)}")
    L.append("")
    if pg.materializations:
        L.append("| Type | Cible | Description | Origine |")
        L.append("|---|---|---|---|")
        for m in pg.materializations:
            L.append(f"| {m.kind} | {m.edge_type or m.node_type or '—'} | {_esc(m.description)} | {_short(m.source or '', onto)} |")
    else:
        L.append("Aucune.")
    L.append("")

    # ---------------------------------------------------------------- décisions
    L.append("## Arbitrages")
    L.append("")
    if decided:
        for f in decided:
            L.append(f"- `{f.id}` → `{f.chosen}` (recommandé : `{f.recommended}`)")
    else:
        L.append("Aucun arbitrage enregistré : toutes les recommandations sont appliquées par défaut.")
    orphans = sorted(set(pg.decisions) - {f.id for f in pg.findings})
    if orphans:
        L.append("")
        L.append("Décisions conservées sans constat correspondant (ontologie modifiée) : "
                 + ", ".join(f"`{o}`" for o in orphans))
    L.append("")
    return {FILENAME: "\n".join(L)}
