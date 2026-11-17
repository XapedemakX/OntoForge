"""Bornes des importeurs déterministes (L48) : taille, nombre d'éléments, profondeur, temps.

Toute entrée est hostile par principe : chaque boucle d'analyse appelle :meth:`Budget.tick`, et chaque dépassement lève
:class:`ImportRefused` avec un code stable (le message lisible est composé par ``messages.py``).
"""
from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from typing import Any


class ImportRefused(Exception):
    """Entrée refusée ou dépassement de borne. ``status`` est le code HTTP voulu (413 trop gros, 422 illisible, 408 trop long)."""

    def __init__(self, code: str, status: int = 422, **params: Any):
        super().__init__(code)
        self.code, self.status, self.params = code, status, params


def _env_int(name: str, default: int, lo: int, hi: int) -> int:
    try:
        return min(hi, max(lo, int(os.environ.get(name, default))))
    except ValueError:
        return default


def max_bytes() -> int:
    """Taille maximale d'un fichier d'import (``ONTOFORGE_IMPORT_MAX_MB``, 2 Mo par défaut, 20 Mo au plus)."""
    return _env_int("ONTOFORGE_IMPORT_MAX_MB", 2, 1, 20) * 1024 * 1024


MAX_FILES = 50
MAX_TOTAL_MB = 10          # plafond cumulé par requête (en plus des 2 Mo par fichier)
MAX_TOKENS = 600_000
MAX_DEPTH = 32            # parenthèses SQL, imbrication JSON
MAX_TABLES = 400          # tables, ou classes pour JSON Schema / CSV
MAX_COLUMNS_TABLE = 1024
MAX_COLUMNS_TOTAL = 20_000
MAX_IDENT = 128
MAX_STRING = 4_000        # un littéral ou un commentaire plus long est tronqué
MAX_ENUM = 500
MAX_JSON_NODES = 300_000
MAX_CSV_ROWS = 2_000      # lignes lues pour déduire les types (le reste du fichier n'est pas lu)
MAX_CSV_FIELD = 10_000
MAX_NOTICES = 400


def time_limit() -> float:
    """Durée maximale d'une analyse, en secondes (``ONTOFORGE_IMPORT_MAX_SECONDS``, 8 par défaut)."""
    return float(_env_int("ONTOFORGE_IMPORT_MAX_SECONDS", 8, 1, 60))


@dataclass
class Budget:
    """Compteur de travail partagé par tout un import : horloge monotone + nombre d'unités traitées."""
    seconds: float = field(default_factory=time_limit)
    started: float = field(default_factory=time.monotonic)
    units: int = 0

    def tick(self, n: int = 1) -> None:
        self.units += n
        if n > 1 or not (self.units & 511):   # l'horloge est lue toutes les 512 unités
            self.check()

    def check(self) -> None:
        if time.monotonic() - self.started > self.seconds:
            raise ImportRefused("too_slow", 408, seconds=int(self.seconds))
