"""Trace des décisions humaines (L47, D-L47-02) : qui, quand, pourquoi.

Les décisions elles-mêmes restent `Project.decisions[cible] = {id de constat: id d'option}` (format inchangé, lu par le moteur) ;
la trace vit à côté, dans `Project.decision_notes[cible]`. Un projet sans trace (ancien format) est valide : ses décisions valent
« choix sans raison » ; elles apparaissent dans le dossier de justification avec auteur et date « non renseignés ».
"""
from __future__ import annotations

import re
from typing import Any, Optional

from ..core.pg_model import DecisionNote
from ..core.project import Project

MAX_REASON = 280
VIAS = ("manual", "recommended", "rule", "branch")
_WS = re.compile(r"\s+")
_CTRL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f  ]")


class ReasonTooLong(ValueError):
    pass


def clean_reason(text: Any) -> str:
    """Raison en une ligne : retours à la ligne et espaces multiples ramenés à un espace, caractères de contrôle retirés.

    Lève `ReasonTooLong` au-delà de `MAX_REASON` caractères (on refuse plutôt que de tronquer une justification) ; `ValueError` si ce n'est pas du texte."""
    if text is None:
        return ""
    if not isinstance(text, str):
        raise ValueError("reason")
    out = _WS.sub(" ", _CTRL.sub(" ", text)).strip()
    if len(out) > MAX_REASON:
        raise ReasonTooLong(out)
    return out


def current_user() -> str:
    """Compte qui écrit (L40) ; `local` sans authentification."""
    try:
        from ..collab import access
        c = access.current()
        if c is not None and c.identity.user:
            return c.identity.user
    except Exception:  # noqa: BLE001 — la trace ne doit jamais faire échouer une décision
        pass
    return "local"


def apply_changes(p: Project, target: str, changes: dict[str, Optional[str]], *, reason: Optional[str] = None,
                  reasons: Optional[dict[str, str]] = None, via: str = "manual", now: str = "") -> None:
    """Applique `changes` (id de constat → option, `None` = retirer) à `p.decisions[target]` et tient la trace à jour.

    Règle de la raison : fournie (même vide) → remplace ; absente → conservée si l'option ne change pas, sinon vide.
    Une décision rejouée à l'identique sans raison ne réécrit pas la trace (l'auteur et la date d'origine restent)."""
    dec = dict(p.decisions.get(target, {}))
    notes = dict(p.decision_notes.get(target, {}))
    by = current_user()
    for fid, opt in changes.items():
        if opt is None:
            dec.pop(fid, None)
            notes.pop(fid, None)
            continue
        prev = dec.get(fid)
        dec[fid] = opt
        given = (reasons or {}).get(fid, reason)
        if given is None and prev == opt:
            continue
        notes[fid] = DecisionNote(option=opt, reason=clean_reason(given) if given is not None else "", by=by, at=now,
                                  via=via if via in VIAS else "manual")
    p.decisions[target] = dec
    live = {k: v for k, v in notes.items() if dec.get(k) == v.option}
    if live:
        p.decision_notes[target] = live
    else:
        p.decision_notes.pop(target, None)


def notes_for(p: Project, target: str) -> dict[str, DecisionNote]:
    """Traces cohérentes avec les décisions courantes (une trace dont l'option a changé hors de ce circuit est ignorée)."""
    dec = p.decisions.get(target, {})
    return {k: v for k, v in p.decision_notes.get(target, {}).items() if dec.get(k) == v.option}
