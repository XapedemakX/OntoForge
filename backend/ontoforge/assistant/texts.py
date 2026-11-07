"""Textes déterministes (repli sans LLM et réponses du fournisseur mock)."""
from __future__ import annotations

from typing import Any

TARGET_NAMES = {"curiosity": "Curiosity", "neo4j": "Neo4j"}


def fallback_explain(finding: dict[str, Any], target: str, lang: str = "fr") -> str:
    if lang == "en":
        return _fallback_explain_en(finding, target)
    tname = TARGET_NAMES.get(target, target)
    lines = [f"Constat {finding.get('rule', '?')} — {finding.get('title', '')}",
             "",
             "Ce que cela signifie : " + (finding.get("detail") or "pas de détail disponible") + ".",
             f"Élément concerné : {finding.get('subject', '?')}."]
    opts = finding.get("options") or []
    if opts:
        lines += ["", "Options possibles :"]
        for o in opts:
            star = " (recommandée)" if o.get("id") == finding.get("recommended") else ""
            lines.append(f"- {o.get('label') or o.get('id')}{star}" + (f" : {o.get('description')}" if o.get("description") else ""))
    if finding.get("recommended"):
        lines += ["", f"Pourquoi pour {tname} : l'option « {finding['recommended']} » est recommandée"
                  + (f" car {finding['rationale']}" if finding.get("rationale") else " pour la cible choisie") + "."]
    lines += ["", "La décision reste la vôtre : elle est enregistrée dans le projet et rejouée à chaque génération."]
    return "\n".join(lines)


def _fallback_explain_en(finding: dict[str, Any], target: str) -> str:
    from ..localize import tr
    tname = TARGET_NAMES.get(target, target)
    t = lambda x: tr(x, "en") or ""  # noqa: E731 — les textes du constat viennent du moteur (français) : traduits à l'affichage
    lines = [f"Finding {finding.get('rule', '?')} — {t(finding.get('title', ''))}",
             "",
             "What this means: " + (t(finding.get("detail") or "") or "no detail available") + ".",
             f"Element concerned: {finding.get('subject', '?')}."]
    opts = finding.get("options") or []
    if opts:
        lines += ["", "Possible options:"]
        for o in opts:
            star = " (recommended)" if o.get("id") == finding.get("recommended") else ""
            lines.append(f"- {t(o.get('label') or '') or o.get('id')}{star}" + (f": {t(o.get('description'))}" if o.get("description") else ""))
    if finding.get("recommended"):
        why = t(finding["rationale"]) if finding.get("rationale") else ""
        lines += ["", f"Why for {tname}: the \"{finding['recommended']}\" option is recommended"
                  + (f" because {why[:1].lower() + why[1:]}" if why else " for the chosen target") + "."]
    lines += ["", "The decision remains yours: it is saved in the project and replayed at each generation."]
    return "\n".join(lines)
