"""Rapport de transposition (Markdown, français) — `generate(pg, onto=None) -> {"rapport-transposition.md": …}`.

Sections : synthèse chiffrée · hypothèse monde clos (rappelée une fois) · nœuds · relations ·
ce qui est perdu ou à risque (option retenue ou recommandée « non arbitré », impact, compensation) ·
transposé automatiquement · validations à implémenter · matérialisations · constats non transposés.
"""
from __future__ import annotations

from typing import Optional

from .. import standards
from ..localize.gen import GL, T, using_lang
from ..core.onto_model import OntoModel, local_name
from ..core.pg_model import Finding, PGModel

FILENAME = "rapport-transposition.md"
TARGET_NAME = {"curiosity": "Curiosity", "neo4j": "Neo4j"}
SEV = {"auto": "automatique", "review": "à arbitrer", "lost": "perdu"}
COMP = {"none": "—", "validation": "validation applicative", "materialization": "matérialisation",
        "query": "requête", "documentation": "documentation", "rename": "renommage", "human": "arbitrage humain"}
COMP_EN = {"none": "—", "validation": "application-level validation", "materialization": "materialization",
           "query": "query", "documentation": "documentation", "rename": "renaming", "human": "human arbitration"}


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
        comp = (COMP_EN if GL() == "en" else COMP).get(RULES.get(f.rule, {}).get("compensation", ""), "")
    except Exception:  # pragma: no cover
        comp = ""
    vals = [v for v in pg.validations if v.id.startswith(f.id + "#")]
    mats = [m for m in pg.materializations if m.id.startswith(f.id + "#")]
    bits = []
    if vals:
        bits.append(f"{len(vals)} validation(s)")
    if mats:
        bits.append(T(f"{len(mats)} matérialisation(s)", f"{len(mats)} materialization(s)"))
    chosen = f.chosen or f.recommended
    if chosen in ("ignore", "doc_only", "report", "exclude"):
        return T("aucune (documenté)", "none (documented)")
    return ", ".join(bits) or comp or "—"


def _option(f: Finding) -> tuple[str, str]:
    oid = f.chosen or f.recommended or "—"
    opt = next((o for o in f.options if o.id == oid), None)
    label = f"`{oid}`" + ("" if f.chosen else T(" *(non arbitré, recommandé)*", " *(not arbitrated, recommended)*"))
    return label, (opt.impact if opt else "")


def _versions_section(pg: PGModel) -> list[str]:
    """Versions de normes et de cibles utilisées pour cette génération, avec leur statut et les écarts connus (contrôle local)."""
    v = {**standards.defaults(), **{k: x for k, x in (pg.meta.target_versions or {}).items() if x}}
    keys = ("neo4j", "cypher") if pg.target == "neo4j" else ("curiosity_library",)
    keys += ("rdf", "shacl", "sparql")
    lg = GL()
    out = [T("## Versions utilisées", "## Versions used"), "", T("| Norme ou cible | Version | Statut |", "| Standard or target | Version | Status |"), "|---|---|---|"]
    for k in keys:
        out.append(f"| {standards._TXT[lg]['fam'][k]} | {v[k]} | {standards.status_label(k, v[k], lg)} |")
    out.append("")
    gaps = standards.check(v, lg, base=standards.defaults())["gaps"]
    out += [f"- {g['message']}" + (f" {g['recommendation']['message']}" if g.get("recommendation") else "") for g in gaps]
    out.append(T(f"Référence des versions : standards.json du {standards.updated()}. "
                 "Ce qui n'est pas vérifiable (compatibilité avec le serveur Curiosity, support exact de Neo4j) est marqué À VÉRIFIER.",
                 f"Versions reference: standards.json dated {standards.updated()}. "
                 "Whatever cannot be verified (compatibility with the Curiosity server, exact Neo4j support) is marked TO VERIFY."))
    out.append("")
    return out


def generate(pg: PGModel, onto: Optional[OntoModel] = None, lang: Optional[str] = None) -> dict[str, str]:
    """Rapport Markdown ; ``lang`` fr/en (défaut : langue de génération courante). Libellés, identifiants et IRIs restent des données."""
    with using_lang(lang):
        return _generate(pg, onto)


def _generate(pg: PGModel, onto: Optional[OntoModel] = None) -> dict[str, str]:
    t = TARGET_NAME.get(pg.target, pg.target)
    s = pg.summary()
    by_sev = {k: [f for f in pg.findings if f.severity == k] for k in ("auto", "review", "lost")}
    decided = [f for f in pg.findings if f.severity in ("review", "lost") and f.chosen]
    pending = [f for f in pg.findings if f.severity in ("review", "lost") and not f.chosen]
    L: list[str] = []
    L.append(T(f"# Rapport de transposition — {pg.meta.name or pg.meta.iri or 'ontologie'} → {t}",
               f"# Transposition report — {pg.meta.name or pg.meta.iri or 'ontology'} → {t}"))
    L.append("")
    if pg.meta.iri:
        L.append(T(f"Ontologie source : `{pg.meta.iri}` · cible : **{t}** · OntoForge {pg.meta.ontoforge_version}",
                   f"Source ontology: `{pg.meta.iri}` · target: **{t}** · OntoForge {pg.meta.ontoforge_version}"))
        L.append("")
    L.extend(_versions_section(pg))
    L.append(T("## Synthèse", "## Summary"))
    L.append("")
    L.append(T("| Indicateur | Valeur |", "| Indicator | Value |"))
    L.append("|---|---|")
    L.append(T(f"| Constats | {len(pg.findings)} |", f"| Findings | {len(pg.findings)} |"))
    L.append(T(f"| Transposés automatiquement (auto) | {s['auto']} |", f"| Transposed automatically (auto) | {s['auto']} |"))
    L.append(T(f"| À arbitrer (review) | {s['review']} |", f"| To arbitrate (review) | {s['review']} |"))
    L.append(T(f"| Perdus sans compensation native (lost) | {s['lost']} |", f"| Lost without native compensation (lost) | {s['lost']} |"))
    L.append(T(f"| Arbitrés / non arbitrés (review + lost) | {s['decided']} / {s['pending']} |",
               f"| Arbitrated / not arbitrated (review + lost) | {s['decided']} / {s['pending']} |"))
    L.append(T(f"| Types de nœuds / relations | {len(pg.node_types)} / {len(pg.edge_types)} |",
               f"| Node types / relationships | {len(pg.node_types)} / {len(pg.edge_types)} |"))
    L.append(T(f"| Validations à implémenter / matérialisations | {len(pg.validations)} / {len(pg.materializations)} |",
               f"| Validations to implement / materializations | {len(pg.validations)} / {len(pg.materializations)} |"))
    L.append("")
    L.append(T("> **Hypothèse de monde clos.** OWL raisonne en monde ouvert, sans hypothèse du nom unique : un axiome y "
               "*infère* des faits (domaine, portée, restrictions, clés). Le schéma property graph est un *contrat "
               "d'ingestion* en monde clos : ces axiomes deviennent ici des contraintes ou des validations, ce qui est un "
               "renforcement (ce qui manque est une erreur, deux clés différentes sont deux nœuds). Ce rappel vaut pour "
               "tout le rapport.",
               "> **Closed-world assumption.** OWL reasons under the open-world assumption, without the unique name "
               "assumption: an axiom *infers* facts (domain, range, restrictions, keys). The property graph schema is an "
               "*ingestion contract* under the closed-world assumption: these axioms become constraints or validations here, "
               "which is a tightening (what is missing is an error, two different keys are two nodes). This reminder applies "
               "to the whole report."))
    L.append("")
    if pending:
        L.append(T(f"**{len(pending)} constat(s) non arbitré(s)** : la recommandation pour {t} a été appliquée "
                   "(marquée « non arbitré »).",
                   f"**{len(pending)} finding(s) not arbitrated**: the recommendation for {t} was applied "
                   "(marked \"not arbitrated\")."))
        L.append("")

    # ---------------------------------------------------------------- nœuds
    L.append(T("## Types de nœuds", "## Node types"))
    L.append("")
    L.append(T("| Type | Labels | Clé | Propriétés | Classes OWL sources |", "| Type | Labels | Key | Properties | Source OWL classes |"))
    L.append("|---|---|---|---|---|")
    for nt in pg.node_types.values():
        props = ", ".join(p.name + ("*" if p.required else "") + ("[]" if p.is_list else "") + f": {p.type}"
                          for p in nt.properties)
        name = nt.name + (T(" *(abstrait)*", " *(abstract)*") if nt.abstract else "")
        L.append(f"| {name} | {', '.join(nt.labels)} | {', '.join(nt.key)} | {_esc(props)} | "
                 f"{', '.join(_short(x, onto) for x in nt.source)} |")
    L.append("")
    L.append(T("`*` obligatoire · `[]` liste.", "`*` required · `[]` list."))
    L.append("")
    # ---------------------------------------------------------------- relations
    L.append(T("## Relations", "## Relationships"))
    L.append("")
    L.append(T("| Relation | De | Vers | Retour | Cardinalité (sortie / entrée) | Propriétés | Source | Note |",
               "| Relationship | From | To | Reverse | Cardinality (out / in) | Properties | Source | Note |"))
    L.append("|---|---|---|---|---|---|---|---|")
    for e in pg.edge_types:
        props = ", ".join(f"{p.name}: {p.type}" for p in e.properties)
        flags = []
        if e.derived:
            flags.append(T("dérivée", "derived"))
        if e.symmetric:
            flags.append(T("symétrique", "symmetric"))
        if not e.directed:
            flags.append(T("non orientée", "undirected"))
        note = "; ".join(flags + ([e.note] if e.note else []))
        L.append(f"| {e.name} | {e.from_} | {e.to} | {e.reverse or '—'} | {e.cardinality.out} / {e.cardinality.in_} | "
                 f"{_esc(props) or '—'} | {_short(e.source or '', onto)} | {_esc(note)} |")
    L.append("")

    # ---------------------------------------------------------------- perdu / à risque
    L.append(T("## Ce qui est perdu ou à risque", "## What is lost or at risk"))
    L.append("")
    for sev, title in (("lost", T("Perdu (aucun équivalent natif)", "Lost (no native equivalent)")), ("review", T("À risque (à arbitrer)", "At risk (to arbitrate)"))):
        items = by_sev[sev]
        L.append(f"### {title} — {len(items)}")
        L.append("")
        if not items:
            L.append(T("Aucun.", "None."))
            L.append("")
            continue
        L.append(T("| Règle | Sujet | Constat | Option retenue | Impact | Compensation |", "| Rule | Subject | Finding | Chosen option | Impact | Compensation |"))
        L.append("|---|---|---|---|---|---|")
        for f in items:
            opt, impact = _option(f)
            L.append(f"| {f.rule} | {_short(f.subject, onto)} | {_esc(f.title)}{T(" : ", ": ")}{_esc(f.detail)} | {opt} | "
                     f"{_esc(impact)} | {_esc(_compensation(f, pg))} |")
        L.append("")

    # ---------------------------------------------------------------- auto
    L.append(T(f"## Transposé automatiquement — {len(by_sev['auto'])}", f"## Transposed automatically — {len(by_sev['auto'])}"))
    L.append("")
    counts: dict[str, int] = {}
    for f in by_sev["auto"]:
        counts[f"{f.rule} — {f.title}"] = counts.get(f"{f.rule} — {f.title}", 0) + 1
    for k, n in sorted(counts.items()):
        L.append(f"- {k}{T(' : ', ': ')}{n}")
    L.append("")

    # ---------------------------------------------------------------- validations
    L.append(T(f"## Validations à implémenter — {len(pg.validations)}", f"## Validations to implement — {len(pg.validations)}"))
    L.append("")
    L.append(T("Contrôles applicatifs (connecteur / requêtes de détection) : la base ne les impose pas nativement.",
               "Application-level checks (connector / detection queries): the database does not enforce them natively."))
    L.append("")
    if pg.validations:
        L.append(T("| Id | Type | Cible | Description | Origine |", "| Id | Type | Target | Description | Origin |"))
        L.append("|---|---|---|---|---|")
        for v in pg.validations:
            tgt = ".".join(x for x in (v.node_type, v.property) if x) or ""
            if v.edge_type:
                tgt = (tgt + " " if tgt else "") + f"[{v.edge_type}]"
            L.append(f"| `{_compact(v.id, onto)}` | {v.kind} | {_esc(tgt)} | "
                     f"{_esc(v.description)} | {_short(v.source or '', onto)} |")
        L.append("")

    # ---------------------------------------------------------------- matérialisations
    L.append(T(f"## Matérialisations — {len(pg.materializations)}", f"## Materializations — {len(pg.materializations)}"))
    L.append("")
    if pg.materializations:
        L.append(T("| Type | Cible | Description | Origine |", "| Type | Target | Description | Origin |"))
        L.append("|---|---|---|---|")
        for m in pg.materializations:
            L.append(f"| {m.kind} | {m.edge_type or m.node_type or '—'} | {_esc(m.description)} | {_short(m.source or '', onto)} |")
    else:
        L.append(T("Aucune.", "None."))
    L.append("")

    # ---------------------------------------------------------------- décisions
    L.append(T("## Arbitrages", "## Arbitrations"))
    L.append("")
    if decided:
        for f in decided:
            L.append(T(f"- `{f.id}` → `{f.chosen}` (recommandé : `{f.recommended}`)", f"- `{f.id}` → `{f.chosen}` (recommended: `{f.recommended}`)"))
    else:
        L.append(T("Aucun arbitrage enregistré : toutes les recommandations sont appliquées par défaut.",
                   "No arbitration recorded: all recommendations are applied by default."))
    orphans = sorted(set(pg.decisions) - {f.id for f in pg.findings})
    if orphans:
        L.append("")
        L.append(T("Décisions conservées sans constat correspondant (ontologie modifiée) : ", "Decisions kept without a matching finding (ontology modified): ")
                 + ", ".join(f"`{o}`" for o in orphans))
    L.append("")
    return {FILENAME: "\n".join(L)}
