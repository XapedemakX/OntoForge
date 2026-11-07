"""Requêtes sauvegardées par projet — propriétaire : query (L15).
Stockage : ``$ONTOFORGE_DATA/projects/<id>/queries.json`` (écriture atomique)."""
from __future__ import annotations

import json
import os
import tempfile
import threading
import uuid
from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field, model_validator

from ..projects import store
from .builder import GuidedQuery

_LOCK = threading.RLock()


class SavedQuery(BaseModel):
    id: str = ""
    name: str
    description: str = ""
    guided: Optional[GuidedQuery] = None
    sparql: Optional[str] = None  # requête SPARQL libre (si non guidée)
    created_at: str = ""
    updated_at: str = ""

    @model_validator(mode="after")
    def _one(self) -> "SavedQuery":
        self.name = self.name.strip()
        if not self.name:
            raise ValueError("le nom est obligatoire")
        if self.guided is None and not (self.sparql or "").strip():
            raise ValueError("une requête guidée ou un SPARQL est obligatoire")
        return self


class SavedQueryNotFound(KeyError):
    pass


def _path(pid: str):
    return store.projects_dir() / pid / "queries.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def list_saved(pid: str) -> list[SavedQuery]:
    p = _path(pid)
    if not p.exists():
        return []
    return [SavedQuery.model_validate(x) for x in json.loads(p.read_text(encoding="utf-8"))]


def _write(pid: str, items: list[SavedQuery]) -> None:
    p = _path(pid)
    p.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=p.parent, prefix=".queries-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump([i.model_dump(mode="json") for i in items], fh, ensure_ascii=False, indent=2)
        os.replace(tmp, p)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def get(pid: str, qid: str) -> SavedQuery:
    for i in list_saved(pid):
        if i.id == qid:
            return i
    raise SavedQueryNotFound(qid)


def create(pid: str, q: SavedQuery) -> SavedQuery:
    with _LOCK:
        items = list_saved(pid)
        q.id, q.created_at, q.updated_at = uuid.uuid4().hex[:12], _now(), _now()
        _write(pid, [*items, q])
        return q


def update(pid: str, qid: str, q: SavedQuery) -> SavedQuery:
    with _LOCK:
        items = list_saved(pid)
        for k, old in enumerate(items):
            if old.id == qid:
                q.id, q.created_at, q.updated_at = qid, old.created_at, _now()
                items[k] = q
                _write(pid, items)
                return q
    raise SavedQueryNotFound(qid)


def delete(pid: str, qid: str) -> None:
    with _LOCK:
        items = list_saved(pid)
        if not any(i.id == qid for i in items):
            raise SavedQueryNotFound(qid)
        _write(pid, [i for i in items if i.id != qid])
