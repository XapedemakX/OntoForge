"""Localisation des messages générés côté serveur (constats, validations, conformité, notes, questions de compétence).

Le moteur de transposition produit du français (c'est la langue source des règles, de l'ontologie d'exemple et des tests).
Quand ``settings.language.ui`` vaut ``en``, les réponses d'API sont traduites ici, à la frontière HTTP :
- catalogue de règles et justifications de profils : tables ``catalog_en`` / ``profile_en`` (clé = SHA-1[:6] du texte français) ;
- messages composés (détails, validations, notes) : table de fragments ``phrases.PHRASES`` appliquée du plus long au plus court.
Un texte sans traduction reste en français (jamais d'erreur) ; ``tests/test_localize_en.py`` garde la couverture sur l'exemple automaint.
"""
from __future__ import annotations

import hashlib
import re
from contextvars import ContextVar
from typing import Any, Optional

from . import catalog_en, datatype_en, profile_en
from .phrases import PHRASES, REGEXES

# Langue des libellés lus par le moteur de mapping (descriptions de types de nœuds, « Classe X (libellé) »…).
LABEL_LANG: ContextVar[str] = ContextVar("label_lang", default="fr")

_EXACT: dict[str, str] = {**catalog_en.EN, **profile_en.EN}
_PROFIL = re.compile(r"^(?P<head>.*?) — Profil (?P<t>curiosity|neo4j) : (?P<prof>.*)$", re.S)


def key_of(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:6]


def _datatype_notes() -> dict[str, str]:
    """Notes de datatypes des profils (texte français lu dans les profils) -> anglais, via leur clé SHA-1."""
    from ..mapping import profile_api
    from ..mapping.profiles import curiosity, neo4j
    notes = {v["note"] for v in neo4j.XSD_TYPE_MAP.values() if v.get("note")} | {neo4j._DEFAULT_TYPE["note"]}
    notes |= {v[2] for v in curiosity.XSD_TYPE_MAP.values() if v[2]} | {curiosity.DEFAULT_TYPE[2]}
    notes |= {v[2] for v in profile_api._FALLBACK_TYPES.values() if v[2]}
    return {n: datatype_en.EN[key_of(n)] for n in notes if key_of(n) in datatype_en.EN}


def _build() -> list[tuple[str, str]]:
    items = dict(PHRASES)
    try:
        items.update(_datatype_notes())
    except Exception:  # noqa: BLE001 — profils indisponibles : seuls les fragments de base restent
        pass
    return sorted(items.items(), key=lambda kv: -len(kv[0]))


_SORTED = _build()


def ui_lang() -> str:
    """Langue des messages affichés à l'écran (``settings.language.ui``) ; ``fr`` si les paramètres sont illisibles."""
    try:
        from ..settings import store
        return store.load(persist=False).language.ui
    except Exception:  # noqa: BLE001 — jamais d'échec dur pour une traduction
        return "fr"


def labels_lang() -> str:
    try:
        from ..settings import store
        return store.load(persist=False).language.labels
    except Exception:  # noqa: BLE001
        return "fr"


def tr(text: Optional[str], lang: str = "en") -> Optional[str]:
    """Traduit un message français généré par le serveur ; renvoie ``text`` inchangé si ``lang != 'en'`` ou si rien ne correspond."""
    if not text or lang != "en":
        return text
    hit = _EXACT.get(key_of(text))
    if hit:
        return hit
    m = _PROFIL.match(text)
    if m:
        return f"{tr(m['head'], lang)} — Profile {m['t']}: {tr(m['prof'], lang)}"
    out = text
    for fr, en in _SORTED:
        if fr in out:
            out = out.replace(fr, en)
    for rx, rep in REGEXES:
        out = rx.sub(rep, out)
    return out


def localize_pg(pg: Any, lang: str) -> Any:
    """Traduit en place les textes d'un PGModel (constats, options, validations, matérialisations, notes) ; renvoie ``pg``."""
    if lang != "en":
        return pg
    for f in pg.findings:
        f.title = tr(f.title, lang) or f.title
        f.detail = tr(f.detail, lang) or f.detail
        f.rationale = tr(f.rationale, lang)
        for o in f.options:
            o.label = tr(o.label, lang) or o.label
            o.impact = tr(o.impact, lang) or o.impact
    for v in pg.validations:
        v.description = tr(v.description, lang) or v.description
    for m in pg.materializations:
        m.description = tr(m.description, lang) or m.description
        if m.definition:
            m.definition = tr(m.definition, lang)
    for e in pg.edge_types:
        e.description = tr(e.description, lang)
        e.note = tr(e.note, lang)
    for nt in pg.node_types.values():
        nt.description = tr(nt.description, lang)
        for p in nt.properties:
            p.note = tr(p.note, lang)
            p.description = tr(p.description, lang)
    return pg


def tr_deep(obj: Any, lang: str) -> Any:
    """Traduit récursivement toutes les chaînes d'une structure JSON (listes, dict) ; les clés ne changent pas."""
    if lang != "en":
        return obj
    if isinstance(obj, str):
        return tr(obj, lang)
    if isinstance(obj, list):
        return [tr_deep(x, lang) for x in obj]
    if isinstance(obj, dict):
        return {k: tr_deep(v, lang) for k, v in obj.items()}
    return obj


def localize_conformance(report: dict, lang: str) -> dict:
    """Rapport de conformité : messages, violations de profil et notes de raisonneur ; codes, IRIs et références inchangés."""
    if lang != "en":
        return report
    out = dict(report)
    for k in ("profile_violations", "notes", "reasoner_notes", "warnings"):
        if k in out:
            out[k] = tr_deep(out[k], lang)
    if "issues" in out:
        out["issues"] = [{**i, "message": tr(i.get("message"), lang), **({"spec_ref": tr(i["spec_ref"], lang)} if i.get("spec_ref") else {})} if isinstance(i, dict) else i for i in out["issues"]]
    return out
