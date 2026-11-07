"""Outils communs aux routers : import paresseux des services (→ 501), accès projet (→ 404), sérialisation."""
from __future__ import annotations

import importlib
import logging
from typing import Any, Callable

from fastapi import HTTPException
from pydantic import BaseModel

from ..core.project import Project
from ..projects import store

log = logging.getLogger(__name__)

TARGETS = ("curiosity", "neo4j")


def not_available(module: str, reason: str | None = None) -> HTTPException:
    if reason:
        log.info("module %s indisponible : %s", module, reason)
    return HTTPException(status_code=501, detail=f"module {module} pas encore disponible")


def service(module: str, func: str) -> Callable[..., Any]:
    """Résout ``ontoforge.<module>.<func>`` à l'appel ; 501 si le module ou la fonction n'existe pas encore."""
    try:
        mod = importlib.import_module(f"ontoforge.{module}")
    except ImportError as exc:
        raise not_available(module, str(exc)) from None
    fn = getattr(mod, func, None)
    if fn is None:
        raise not_available(module, f"fonction {func} absente")
    return fn


def optional_service(module: str, func: str) -> Callable[..., Any] | None:
    try:
        return service(module, func)
    except HTTPException:
        return None


def load_project(pid: str) -> Project:
    try:
        return store.get(pid)
    except store.ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Projet « {pid} » introuvable") from None


def check_target(target: str) -> str:
    if target not in TARGETS:
        raise HTTPException(status_code=422, detail=f"Cible inconnue « {target} » : attendu curiosity ou neo4j")
    return target


def dump(obj: Any) -> Any:
    """Sérialisation JSON (alias pydantic : from/in/class…) de résultats de services au type libre."""
    if isinstance(obj, BaseModel):
        return obj.model_dump(mode="json", by_alias=True)
    if isinstance(obj, dict):
        return {k: dump(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [dump(v) for v in obj]
    return obj


def parse_error(what: str, exc: Exception) -> HTTPException:
    msg = str(exc).strip() or exc.__class__.__name__
    if len(msg) > 800:
        msg = msg[:800] + "…"
    return HTTPException(status_code=422, detail=f"Impossible de lire {what} : {msg}")


def decode(data: bytes) -> str:
    for enc in ("utf-8-sig", "latin-1"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")
