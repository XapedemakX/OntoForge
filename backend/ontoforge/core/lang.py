"""Langue des libellés lus par le moteur de transposition (descriptions des types de nœuds, « Classe X (libellé) »…).

Positionnée par l'API autour de ``analyze`` à partir de ``settings.language.labels`` ; ``fr`` par défaut (tests, CLI).
"""
from __future__ import annotations

from contextvars import ContextVar

LABEL_LANG: ContextVar[str] = ContextVar("label_lang", default="fr")


def label_lang() -> str:
    return LABEL_LANG.get()
