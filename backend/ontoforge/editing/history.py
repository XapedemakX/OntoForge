"""Journal d'opérations par projet (annuler / rétablir). Fichier annexe ``ops-history.json`` du dossier projet.

Chaque entrée stocke l'état **avant** (ou, côté rétablir, l'état écarté) des seuls champs modifiés
(onto, view, perimeters, shapes, decisions). Pile bornée à 200 entrées. Les sauvegardes hors éditeur
(PUT /onto, import…) ne sont pas journalisées : annuler restaure alors les champs de l'entrée.
"""
from __future__ import annotations

import json
import threading
import uuid
from typing import Any

from ..core.project import Project
from ..projects import store
from . import ops as ops_mod

FILE = "ops-history.json"
LIMIT = 200
_lock = threading.RLock()


class EmptyStack(Exception):
    pass


def lock() -> threading.RLock:
    return _lock


def _load(pid: str) -> dict[str, list]:
    raw = store.read_file(pid, FILE)
    if raw:
        try:
            d = json.loads(raw)
            return {"undo": list(d.get("undo", [])), "redo": list(d.get("redo", []))}
        except ValueError:
            pass
    return {"undo": [], "redo": []}


def _save(pid: str, h: dict[str, list]) -> None:
    h["undo"] = h["undo"][-LIMIT:]
    h["redo"] = h["redo"][-LIMIT:]
    store.write_file(pid, FILE, json.dumps(h, ensure_ascii=False))


def _entry(label: str, snap: dict[str, Any]) -> dict:
    from ..projects.store import now_iso
    return {"id": uuid.uuid4().hex[:12], "ts": now_iso(), "label": label, "snapshot": snap}


def record(pid: str, label: str, before: dict[str, Any]) -> None:
    with _lock:
        h = _load(pid)
        h["undo"].append(_entry(label, before))
        h["redo"] = []
        _save(pid, h)


def status(pid: str) -> dict:
    h = _load(pid)
    brief = lambda es: [{"id": e["id"], "ts": e["ts"], "label": e["label"], "fields": sorted(e["snapshot"])} for e in reversed(es)]
    return {"undo": brief(h["undo"]), "redo": brief(h["redo"]), "limit": LIMIT,
            "can_undo": bool(h["undo"]), "can_redo": bool(h["redo"])}


def _swap(p: Project, src: str, dst: str) -> str:
    with _lock:
        h = _load(p.id)
        if not h[src]:
            raise EmptyStack(src)
        e = h[src].pop()
        current = ops_mod.snapshot(p, tuple(e["snapshot"]))
        ops_mod.restore(p, e["snapshot"])
        h[dst].append(_entry(e["label"], current))
        _save(p.id, h)
        return e["label"]


def undo(p: Project) -> str:
    return _swap(p, "undo", "redo")


def redo(p: Project) -> str:
    return _swap(p, "redo", "undo")
