"""Langue de génération des fichiers exportés (commentaires, en-têtes, README, rapport de transposition).

Par défaut : la langue de l'interface (``settings.language.ui``) ; un appel d'export peut la forcer (``lang=fr|en``).
Les générateurs écrivent leurs textes avec ``T(fr, en)``. Le code (identifiants, noms de types, d'arêtes, de propriétés)
et les libellés de l'ontologie sont des données : ils ne passent jamais par ici.
Hors appel d'API (tests, usage direct d'un générateur), la langue vaut ``fr`` tant qu'on ne l'a pas fixée avec ``using_lang``.
"""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from typing import Iterator, Optional

LANGS = ("fr", "en")
GEN_LANG: ContextVar[str] = ContextVar("gen_lang", default="fr")


def normalize(lang: Optional[str]) -> Optional[str]:
    """``fr`` / ``en`` (insensible à la casse, variantes régionales acceptées) ; ``None`` si absent ou inconnu."""
    if not lang:
        return None
    base = str(lang).strip().lower().replace("_", "-").split("-")[0]
    return base if base in LANGS else None


def resolve(lang: Optional[str] = None) -> str:
    """Langue effective d'une génération : ``lang`` demandée, sinon langue de l'interface."""
    got = normalize(lang)
    if got:
        return got
    from . import ui_lang
    return "en" if ui_lang() == "en" else "fr"


def GL() -> str:
    return GEN_LANG.get()


def T(fr: str, en: str) -> str:
    """Texte dans la langue de génération courante."""
    return en if GEN_LANG.get() == "en" else fr


@contextmanager
def using_lang(lang: Optional[str]) -> Iterator[str]:
    """Fixe la langue de génération le temps du bloc (``None`` : ne change rien)."""
    got = normalize(lang)
    if got is None:
        yield GEN_LANG.get()
        return
    token = GEN_LANG.set(got)
    try:
        yield got
    finally:
        GEN_LANG.reset(token)
