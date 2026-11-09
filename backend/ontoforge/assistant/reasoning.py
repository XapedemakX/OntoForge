"""Krakie : intention « raisonne » (L32). Lance HermiT sur l'ontologie du projet et résume le résultat, en français ou en anglais."""
from __future__ import annotations

import re
import unicodedata
from typing import Any, Optional

_FR = re.compile(r"^(?:peux-tu\s+|pouvez-vous\s+)?(?:raisonne(?:r)?(?:\s+(?:sur\s+)?(?:l'ontologie|le\s+mod[eè]le|dessus))?|lance\s+(?:le\s+|un\s+)?(?:raisonnement|raisonneur|hermit)(?:\s+hermit)?|"
                 r"(?:v[ée]rifie|verifie|contr[oô]le|teste)\s+(?:la\s+|que\s+l'ontologie\s+est\s+)?(?:coh[ée]rence|coh[ée]rente)(?:\s+de\s+l'ontologie)?|"
                 r"l'ontologie\s+est[- ]elle\s+coh[ée]rente|est-ce\s+que\s+l'ontologie\s+est\s+coh[ée]rente|passe\s+hermit)$", re.I)
_EN = re.compile(r"^(?:can\s+you\s+|please\s+)?(?:reason(?:\s+(?:over|about|on)\s+(?:the\s+|my\s+)?ontology)?|(?:run|launch|start)\s+(?:the\s+|a\s+)?(?:reasoner|reasoning|hermit)(?:\s+hermit)?|"
                 r"(?:check|verify|test)\s+(?:the\s+|my\s+)?(?:ontology(?:'s)?\s+)?consisten(?:cy|t)(?:\s+of\s+the\s+ontology)?|"
                 r"is\s+(?:the|my)\s+ontology\s+consistent|check\s+(?:that\s+)?the\s+ontology\s+is\s+consistent)$", re.I)


def _flat(s: str) -> str:
    return unicodedata.normalize("NFC", re.sub(r"\s+", " ", s.strip().strip(".!?")).strip())


def matches(message: str) -> bool:
    t = _flat(message)
    return bool(_FR.match(t) or _EN.match(t))


def _lbl(project: Any, iri: str, lang: str) -> str:
    try:
        return project.onto.label(iri, "en" if lang == "en" else "fr") or iri
    except Exception:  # noqa: BLE001
        return iri


def _names(project: Any, iris: list[str], lang: str, n: int = 5) -> str:
    out = [_lbl(project, i, lang) if i in project.onto.classes or i in project.onto.individuals else re.split(r"[#/]", i)[-1] for i in iris[:n]]
    return ", ".join(out) + (f" (+{len(iris) - n})" if len(iris) > n else "")


def answer(project: Any, message: str, lang: str) -> Optional[dict[str, Any]]:
    """{reply, actions, warnings} si le message demande un raisonnement, sinon None. Jamais d'exception : HermiT absent => réponse explicative."""
    if not matches(message):
        return None
    from ..conformance import hermit as hm
    from ..io.rdf_export import model_to_graph
    en = lang == "en"
    nav = [{"kind": "navigate", "screen": "conformite", "summary": "See the reasoner card in Conformance" if en else "Voir la carte du raisonneur dans Conformité"}]
    try:
        r = hm.run_hermit(model_to_graph(project.onto), lang=lang)
    except hm.HermitUnavailable as e:
        return {"reply": hm.unavailable_message(e, lang), "actions": [], "warnings": []}
    except hm.HermitBusy as e:
        return {"reply": str(e), "actions": [], "warnings": []}
    warns = list(r["warnings"])
    if r["status"] == "timeout":
        return {"reply": warns[-1] if warns else "HermiT timeout", "actions": nav, "warnings": warns[:-1]}
    if r["status"] != "ok":
        return {"reply": r["error"] or "HermiT error", "actions": [], "warnings": warns}
    L: list[str] = []
    if r["consistent"] is False:
        L.append(f"**{'The ontology is inconsistent' if en else 'L’ontologie est incohérente'}** ({r['version']}, {r['duration_ms']} ms).")
        ex = r["explanation"] or {}
        if ex.get("individuals") or ex.get("classes"):
            L.append(("Likely culprits: individuals " if en else "Pistes : individus ") + _names(project, ex.get("individuals", []), lang)
                     + ((" ; classes " if not en else "; classes ") + _names(project, ex["classes"], lang) if ex.get("classes") else "") + ".")
        L.append("HermiT does not give a justification; these are candidates, not proof." if en else "HermiT ne fournit pas de justification : ce sont des pistes, pas une preuve.")
    else:
        L.append(f"**{'The ontology is consistent' if en else 'L’ontologie est cohérente'}** ({r['version']}, {r['duration_ms']} ms).")
        u, h, ri = r["unsatisfiable"], r["hierarchy"], r["reclassified"]
        if u:
            L.append((f"{len(u)} unsatisfiable class(es): " if en else f"{len(u)} classe(s) insatisfiable(s) : ") + _names(project, u, lang) + ".")
        else:
            L.append("No unsatisfiable class." if en else "Aucune classe insatisfiable.")
        ns, ne = len(h["new_subclass"]), len(h["new_equivalent"])
        L.append((f"Inferred: {ns} new subclass relation(s), {ne} equivalence(s), {len(ri)} reclassified individual(s)." if en
                  else f"Inférences : {ns} sous-classe(s) nouvelle(s), {ne} équivalence(s), {len(ri)} individu(s) reclassé(s)."))
    if not r["dl"]["conformant"]:
        L.append("Caution: the ontology goes beyond OWL 2 DL, the result is indicative only." if en else "Attention : l’ontologie sort d’OWL 2 DL, le résultat n’est qu’indicatif.")
    return {"reply": " ".join(L), "actions": nav, "warnings": warns}
