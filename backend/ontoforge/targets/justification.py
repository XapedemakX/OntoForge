"""Dossier de justification d'une transposition (L47, P-05) : HTML autonome et Markdown, par cible.

Pour un client ou un relecteur : le modèle retenu, ce qui est perdu, ce qui est compensé, les décisions humaines (qui, quand,
pourquoi), les recommandations de l'outil qui n'ont pas été suivies, ce qui reste à arbitrer et ce que le moteur a reclassé
« automatique » sans demander de choix.

Un seul plan intermédiaire (`build_blocks`) est rendu par deux sorties : `render_md` et `render_html`. Tout texte qui vient de
l'ontologie, d'un compte ou d'une raison saisie est traité comme une donnée : échappé à l'affichage (HTML : `html.escape` ; Markdown :
caractères de mise en forme neutralisés), jamais interprété. Le HTML ne contient aucun script, aucun style ou image distants, aucun
gestionnaire d'événement ; il porte sa propre politique `Content-Security-Policy` (`default-src 'none'`).
"""
from __future__ import annotations

import html as _html
import re
from typing import Any, Optional, Union

from ..core.onto_model import OntoModel
from ..core.pg_model import Finding, PGModel
from ..localize.gen import GL, T, using_lang
from .report import TARGET_NAME, _short

Cell = Union[str, tuple]  # texte, ou ("c", texte) pour un identifiant affiché en police fixe
Block = tuple

_ISO = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}")


def _when(at: str) -> str:
    if not at:
        return T("non renseigné", "not recorded")
    return (at[:16].replace("T", " ") + " UTC") if _ISO.match(at) else at


def _label(f: Finding, oid: Optional[str]) -> str:
    if not oid:
        return "—"
    opt = next((o for o in f.options if o.id == oid), None)
    return f"{opt.label} ({oid})" if opt else oid


def _impact(f: Finding, oid: Optional[str]) -> str:
    opt = next((o for o in f.options if o.id == oid), None)
    return opt.impact if opt else ""


def _compensation(f: Finding, pg: PGModel) -> list[str]:
    vals = [v for v in pg.validations if v.id.startswith(f.id + "#")]
    mats = [m for m in pg.materializations if m.id.startswith(f.id + "#")]
    return ([f"{T('Validation', 'Validation')} ({v.kind}) : {v.description}" for v in vals]
            + [f"{T('Matérialisation', 'Materialization')} ({m.kind}) : {m.description}" for m in mats])


def build_blocks(pg: PGModel, onto: Optional[OntoModel], *, project_name: str, generated_at: str, lang: str = "fr") -> list[Block]:
    """Plan du dossier. ``pg`` doit être analysé avec les décisions du projet (``pg.decision_notes`` rempli) et traduit si ``lang == 'en'``."""
    with using_lang(lang):
        return _blocks(pg, onto, project_name, generated_at)


def _blocks(pg: PGModel, onto: Optional[OntoModel], project_name: str, generated_at: str) -> list[Block]:
    t = TARGET_NAME.get(pg.target, pg.target)
    notes = pg.decision_notes
    sh = lambda iri: _short(iri, onto)  # noqa: E731
    todo = [f for f in pg.findings if f.severity in ("review", "lost")]
    decided = [f for f in pg.findings if f.chosen and f.severity != "info"]
    pending = [f for f in todo if not f.chosen]
    lost = [f for f in pg.findings if f.severity == "lost"]
    reclassified = [f for f in pg.findings if f.auto_reason]
    ignored = [f for f in decided if f.chosen != f.recommended]
    B: list[Block] = []
    B.append(("title", T(f"Dossier de justification — {project_name} → {t}", f"Justification file — {project_name} → {t}")))
    B.append(("kv", [(T("Projet", "Project"), project_name), (T("Cible", "Target"), t),
                     (T("Ontologie source", "Source ontology"), ("c", pg.meta.iri or "—")),
                     (T("Établi le", "Issued on"), _when(generated_at)), ("OntoForge", pg.meta.ontoforge_version)]))
    B.append(("p", T("Ce dossier dit ce que la transposition de l'ontologie vers le property graph a changé, ce qui est perdu ou compensé, "
                     "qui a décidé quoi, quand et pourquoi. OWL raisonne en monde ouvert, le schéma property graph est un contrat "
                     "d'ingestion en monde clos : une contrainte OWL qui devient un contrôle est un renforcement, pas une équivalence.",
                     "This file states what moving the ontology to the property graph changed, what is lost or compensated, who "
                     "decided what, when and why. OWL reasons under the open-world assumption, while the property graph schema is a "
                     "closed-world ingestion contract: an OWL constraint that becomes a check is a tightening, not an equivalence.")))

    # ---- synthèse
    s = pg.summary()
    B.append(("h2", T("Synthèse", "Summary"), "synthese"))
    B.append(("table", [T("Indicateur", "Indicator"), T("Valeur", "Value")], [
        [T("Constats analysés", "Findings analysed"), str(len([f for f in pg.findings if f.severity != "info"]))],
        [T("Transposés automatiquement", "Transposed automatically"), str(s["auto"])],
        [T("dont reclassés sans choix à faire", "of which reclassified, no choice to make"), str(len(reclassified))],
        [T("À arbitrer (à revoir + perdus)", "To arbitrate (review + lost)"), str(s["review"] + s["lost"])],
        [T("Perdus (aucun équivalent natif)", "Lost (no native equivalent)"), str(s["lost"])],
        [T("Décisions humaines prises", "Human decisions made"), str(len(decided))],
        [T("Encore à arbitrer", "Still to arbitrate"), str(len(pending))],
        [T("Recommandations non suivies", "Recommendations not followed"), str(len(ignored))],
        [T("Types de nœuds / relations", "Node types / relationships"), f"{len(pg.node_types)} / {len(pg.edge_types)}"],
        [T("Validations / matérialisations", "Validations / materializations"), f"{len(pg.validations)} / {len(pg.materializations)}"],
    ]))

    # ---- modèle retenu
    B.append(("h2", T("Modèle retenu", "Retained model"), "modele"))
    B.append(("table", [T("Type de nœud", "Node type"), T("Clé", "Key"), T("Propriétés", "Properties"), T("Classes OWL sources", "Source OWL classes")],
              [[("c", nt.name), ", ".join(nt.key) or "—", str(len(nt.properties)), ", ".join(sh(x) for x in nt.source) or "—"]
               for nt in pg.node_types.values()]))
    if pg.edge_types:
        B.append(("table", [T("Relation", "Relationship"), T("De", "From"), T("Vers", "To"), T("Source", "Source")],
                  [[("c", e.name), e.from_, e.to, sh(e.source or "") or "—"] for e in pg.edge_types]))

    # ---- perdu
    B.append(("h2", T("Ce qui est perdu", "What is lost"), "perdu"))
    if lost:
        B.append(("p", T("Aucun équivalent natif dans " + t + " : chaque cas est arbitré par une personne, jamais par défaut.",
                         "No native equivalent in " + t + ": each case is arbitrated by a person, never by default.")))
        B.append(("table", [T("Règle", "Rule"), T("Sujet", "Subject"), T("Constat", "Finding"), T("Traitement retenu", "Chosen treatment"),
                            T("Conséquence", "Consequence"), T("Décidé par", "Decided by")],
                  [[("c", f.rule), sh(f.subject), f"{f.title} : {f.detail}", _applied(f), _impact(f, f.chosen or f.recommended), _who(f, notes)] for f in lost]))
    else:
        B.append(("p", T("Aucune perte sans équivalent.", "Nothing is lost without an equivalent.")))

    # ---- compensé
    comp = [(f, _compensation(f, pg)) for f in pg.findings if f.severity != "info"]
    comp = [(f, c) for f, c in comp if c]
    B.append(("h2", T("Ce qui est compensé", "What is compensated"), "compense"))
    B.append(("p", T("Contrôles applicatifs et matérialisations à mettre en œuvre : la base ne les impose pas nativement.",
                     "Application-level checks and materializations to implement: the database does not enforce them natively.")))
    if comp:
        B.append(("table", [T("Règle", "Rule"), T("Sujet", "Subject"), T("Compensation", "Compensation")],
                  [[("c", f.rule), sh(f.subject), "\n".join(c)] for f, c in comp]))
    else:
        B.append(("p", T("Aucune compensation nécessaire.", "No compensation needed.")))

    # ---- décisions humaines
    B.append(("h2", T("Décisions humaines", "Human decisions"), "decisions"))
    if decided:
        B.append(("table", [T("Règle", "Rule"), T("Sujet", "Subject"), T("Option choisie", "Chosen option"), T("Recommandée", "Recommended"),
                            T("Décidé par", "Decided by"), T("Quand", "When"), T("Pourquoi", "Why")],
                  [[("c", f.rule), sh(f.subject), _label(f, f.chosen), _label(f, f.recommended),
                    _by(f, notes), _at(f, notes), _reason(f, notes)] for f in decided]))
        B.append(("p", T("Une décision enregistrée avant le suivi des raisons (ancien format) apparaît sans auteur, sans date et sans raison.",
                         "A decision saved before reasons were tracked (old format) shows no author, no date and no reason.")))
    else:
        B.append(("p", T("Aucune décision enregistrée : les recommandations de l'outil s'appliquent.", "No decision recorded: the tool's recommendations apply.")))

    # ---- recommandations non suivies
    B.append(("h2", T("Recommandations non suivies", "Recommendations not followed"), "non-suivies"))
    if ignored:
        B.append(("table", [T("Règle", "Rule"), T("Sujet", "Subject"), T("Recommandé par l'outil", "Recommended by the tool"),
                            T("Choix retenu", "Choice made"), T("Conséquence du choix", "Consequence of the choice"), T("Pourquoi", "Why")],
                  [[("c", f.rule), sh(f.subject), _label(f, f.recommended), _label(f, f.chosen), _impact(f, f.chosen), _reason(f, notes)] for f in ignored]))
    else:
        B.append(("p", T("Toutes les décisions suivent la recommandation de l'outil.", "Every decision follows the tool's recommendation.")))

    # ---- reste à arbitrer
    B.append(("h2", T("Reste à arbitrer", "Still to arbitrate"), "a-arbitrer"))
    if pending:
        B.append(("p", T(f"La recommandation pour {t} est appliquée en attendant (marquée « non arbitré »).",
                         f"The recommendation for {t} applies meanwhile (marked \"not arbitrated\").")))
        B.append(("table", [T("Règle", "Rule"), T("Sujet", "Subject"), T("Gravité", "Severity"), T("Option appliquée en attendant", "Option applied meanwhile")],
                  [[("c", f.rule), sh(f.subject), T("perdu", "lost") if f.severity == "lost" else T("à revoir", "review"), _label(f, f.recommended)] for f in pending]))
    else:
        B.append(("p", T("Tout est arbitré.", "Everything is arbitrated.")))

    # ---- reclassés
    B.append(("h2", T("Reclassés sans choix à faire", "Reclassified, no choice to make"), "reclasses"))
    if reclassified:
        by_rule: dict[str, list[Finding]] = {}
        for f in reclassified:
            by_rule.setdefault(f.rule, []).append(f)
        B.append(("p", T("Le moteur ne demande pas d'arbitrage quand il n'y a qu'une option, ou quand l'option recommandée ne perd rien et que l'alternative "
                         "consiste à abandonner la contrainte. Une règle qui perd quelque chose n'est jamais reclassée.",
                         "The engine asks for no arbitration when there is only one option, or when the recommended option loses nothing and the "
                         "alternative is to drop the constraint. A rule that loses something is never reclassified.")))
        B.append(("table", [T("Règle", "Rule"), T("Constats", "Findings"), T("Motif", "Reason")],
                  [[("c", r), str(len(fs)), fs[0].auto_reason or ""] for r, fs in sorted(by_rule.items())]))
    else:
        B.append(("p", T("Aucun constat reclassé.", "No finding reclassified.")))
    return B


def _applied(f: Finding) -> str:
    return _label(f, f.chosen or f.recommended) + ("" if f.chosen else T(" — non arbitré, recommandation appliquée", " — not arbitrated, recommendation applied"))


def _by(f: Finding, notes: dict) -> str:
    n = notes.get(f.id)
    return n.by if n and n.by else T("non renseigné", "not recorded")


def _at(f: Finding, notes: dict) -> str:
    n = notes.get(f.id)
    return _when(n.at if n else "")


def _reason(f: Finding, notes: dict) -> str:
    n = notes.get(f.id)
    return n.reason if n and n.reason else "—"


def _who(f: Finding, notes: dict) -> str:
    if not f.chosen:
        return T("personne (non arbitré)", "nobody (not arbitrated)")
    return f"{_by(f, notes)}, {_at(f, notes)}" + (f" — {notes[f.id].reason}" if f.id in notes and notes[f.id].reason else "")


# ================================================================================================ Markdown
_MD_SPECIAL = re.compile(r"([\\`*_\[\]<>|&#~!])")


def _md(text: Any) -> str:
    """Texte brut → Markdown inerte : mise en forme, HTML, liens et tableaux neutralisés ; une seule ligne."""
    s = re.sub(r"\s+", " ", str(text)).strip()
    s = _MD_SPECIAL.sub(r"\\\1", s).replace("://", ":\\/\\/")   # une URL nue ne devient pas un lien automatique
    # autolinks étendus (GFM) : `www.` et `a@b` sont aussi neutralisés (L47 it2)
    return re.sub(r"(?i)\bwww\.", lambda m: m.group(0)[:-1] + "\\.", s).replace("@", "\\@")


def _md_cell(c: Cell) -> str:
    if isinstance(c, tuple):
        return "`" + str(c[1]).replace("`", "'").replace("|", "\\|").replace("\n", " ") + "`"
    return "<br>".join(_md(x) for x in str(c).split("\n")) if "\n" in str(c) else _md(c)


def render_md(blocks: list[Block]) -> str:
    out: list[str] = []
    for b in blocks:
        k = b[0]
        if k == "title":
            out += [f"# {_md(b[1])}", ""]
        elif k == "h2":
            out += [f"## {_md(b[1])}", ""]
        elif k == "p":
            out += [_md(b[1]), ""]
        elif k == "kv":
            out += [f"- **{_md(a)}** : {_md_cell(v)}" if GL() == "fr" else f"- **{_md(a)}**: {_md_cell(v)}" for a, v in b[1]] + [""]
        elif k == "table":
            out.append("| " + " | ".join(_md(h) for h in b[1]) + " |")
            out.append("|" + "---|" * len(b[1]))
            out += ["| " + " | ".join(_md_cell(c) for c in row) + " |" for row in b[2]]
            out.append("")
    return "\n".join(out).rstrip("\n") + "\n"


# ================================================================================================ HTML
from ..security import STRICT_CSP as CSP  # noqa: E402  (source unique : `security.SecurityHeaders` la compare à égalité)

_CSS = """
:root{color-scheme:light dark;--bg:#fff;--fg:#1c2330;--mut:#5b6678;--line:#d6dce6;--head:#eef2f8;--acc:#1f5fbf}
@media (prefers-color-scheme:dark){:root{--bg:#141922;--fg:#e6eaf2;--mut:#9aa6ba;--line:#2e3747;--head:#1d2431;--acc:#7fb0ff}}
html{background:var(--bg)}body{margin:0 auto;max-width:1100px;padding:24px 16px 48px;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
h1{font-size:1.6rem;margin:0 0 12px}h2{font-size:1.2rem;margin:32px 0 8px;padding-top:8px;border-top:1px solid var(--line)}
p{margin:8px 0}dl{display:grid;grid-template-columns:max-content 1fr;gap:4px 16px;margin:12px 0}dt{color:var(--mut)}dd{margin:0;overflow-wrap:anywhere}
nav ul{display:flex;flex-wrap:wrap;gap:4px 16px;padding:0;margin:12px 0;list-style:none}nav a{color:var(--acc)}
.wrap{overflow-x:auto}table{border-collapse:collapse;width:100%;margin:8px 0;font-size:.92rem}
th,td{border:1px solid var(--line);padding:6px 8px;text-align:left;vertical-align:top;overflow-wrap:anywhere}th{background:var(--head)}
code{font:.9em ui-monospace,SFMono-Regular,Menlo,monospace}footer{margin-top:32px;color:var(--mut);font-size:.85rem}
@media print{body{max-width:none;padding:0}h2{break-after:avoid}tr{break-inside:avoid}}
"""


def _h(text: Any) -> str:
    return _html.escape(str(text), quote=True)


def _html_cell(c: Cell) -> str:
    if isinstance(c, tuple):
        return f"<code>{_h(c[1])}</code>"
    return "<br>".join(_h(x) for x in str(c).split("\n"))


def render_html(blocks: list[Block], lang: str = "fr") -> str:
    title = next((b[1] for b in blocks if b[0] == "title"), "")
    nav = [(b[2], b[1]) for b in blocks if b[0] == "h2"]
    out = ["<!doctype html>", f'<html lang="{"en" if lang == "en" else "fr"}">', "<head>", '<meta charset="utf-8">',
           f'<meta http-equiv="Content-Security-Policy" content="{_h(CSP)}">',
           '<meta name="viewport" content="width=device-width, initial-scale=1">', '<meta name="referrer" content="no-referrer">',
           f"<title>{_h(title)}</title>", f"<style>{_CSS}</style>", "</head>", "<body>"]
    for b in blocks:
        k = b[0]
        if k == "title":
            out.append(f"<h1>{_h(b[1])}</h1>")
        elif k == "h2":
            if b[2] == nav[0][0]:
                out.append("<nav aria-label=\"" + _h(T("Sommaire", "Contents")) + "\"><ul>" + "".join(f'<li><a href="#{_h(i)}">{_h(n)}</a></li>' for i, n in nav) + "</ul></nav>")
            out.append(f'<h2 id="{_h(b[2])}">{_h(b[1])}</h2>')
        elif k == "p":
            out.append(f"<p>{_h(b[1])}</p>")
        elif k == "kv":
            out.append("<dl>" + "".join(f"<dt>{_h(a)}</dt><dd>{_html_cell(v)}</dd>" for a, v in b[1]) + "</dl>")
        elif k == "table":
            out.append('<div class="wrap"><table><thead><tr>' + "".join(f'<th scope="col">{_h(x)}</th>' for x in b[1]) + "</tr></thead><tbody>"
                       + "".join("<tr>" + "".join(f"<td>{_html_cell(c)}</td>" for c in row) + "</tr>" for row in b[2]) + "</tbody></table></div>")
    out += [f"<footer>{_h(T('Document généré par OntoForge. Aucun script, aucune ressource distante.', 'Document generated by OntoForge. No script, no remote resource.'))}</footer>",
            "</body>", "</html>"]
    return "\n".join(out) + "\n"


def generate(pg: PGModel, onto: Optional[OntoModel], *, project_name: str, fmt: str, generated_at: str, lang: str = "fr") -> str:
    """Dossier au format ``md`` ou ``html``. ``pg`` : analyse du projet pour la cible, traduite si ``lang == 'en'``."""
    blocks = build_blocks(pg, onto, project_name=project_name, generated_at=generated_at, lang=lang)
    with using_lang(lang):
        return render_html(blocks, lang) if fmt == "html" else render_md(blocks)

