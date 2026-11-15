"""Historique des générations d'un projet (L41, L40-02) : fichier annexe ``generations.json`` du dossier du projet.

Avant L41, ``GET /generate/{target}`` réécrivait ``project.json`` en entier pour y ajouter une entrée : une route de lecture modifiait le
projet, et pouvait écraser en silence la modification qu'un éditeur enregistrait pendant la génération. L'historique vit maintenant
à part (comme ``collab.json``) : ``project.json`` n'est jamais écrit par une génération.

Compatibilité : un projet créé avant L41 garde son historique dans ``project.json`` (champ ``generations``) ; il est lu tel quel
tant que le fichier annexe n'existe pas, puis repris dans le fichier annexe à la première génération suivante.
Écriture : lecture, ajout et remplacement atomique sous un verrou (un seul écrivain à la fois, quel que soit le nombre de requêtes).
"""
from __future__ import annotations

import json
import threading
from typing import Any

from .. import fsutil
from ..core.project import GenerationRecord, Project
from . import store

FILE = "generations.json"
MAX_GENERATIONS = 50
_lock = threading.RLock()


def _read_file(pid: str) -> list[dict[str, Any]] | None:
    try:
        d = json.loads((store.project_dir(pid) / FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError, store.ProjectNotFound):
        return None
    if not isinstance(d, list):
        return None
    out: list[dict[str, Any]] = []
    for x in d:
        try:
            out.append(GenerationRecord.model_validate(x).model_dump(mode="json"))
        except ValueError:
            continue
    return out


def history(p: Project) -> list[dict[str, Any]]:
    """Historique, du plus ancien au plus récent (fichier annexe, ou champ hérité de ``project.json``)."""
    got = _read_file(p.id)
    return got if got is not None else [g.model_dump(mode="json") for g in p.generations]


def append(p: Project, record: GenerationRecord) -> None:
    """Ajoute une entrée, sous verrou, sans toucher à ``project.json``."""
    with _lock:
        cur = _read_file(p.id)
        if cur is None:
            cur = [g.model_dump(mode="json") for g in p.generations]  # reprise de l'historique hérité
        cur.append(record.model_dump(mode="json"))
        fsutil.atomic_write(store.project_dir(p.id) / FILE, json.dumps(cur[-MAX_GENERATIONS:], ensure_ascii=False, indent=2))
