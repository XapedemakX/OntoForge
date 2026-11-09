"""Versions des normes et des cibles (L31) : référence ``standards.json``, versions d'un projet, contrôle local des écarts.

Aucun appel réseau : tout vient de ``ontoforge/standards/standards.json``, livré avec l'application."""
from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Body, HTTPException

from .. import standards
from ..projects import store
from ._common import load_project

router = APIRouter(prefix="/api", tags=["versions"])


@router.get("/standards")
def get_standards() -> dict[str, Any]:
    """La référence des versions (normes W3C, Neo4j, Curiosity.Library, bibliothèques internes), textes dans la langue de l'interface."""
    return standards.reference()


def _view(p) -> dict[str, Any]:
    explicit = dict(p.target_versions)
    return {"versions": standards.effective(explicit), "explicit": explicit, "defaults": standards.global_defaults(),
            "rows": standards.describe(explicit), "standards_updated": standards.updated()}


@router.get("/projects/{pid}/versions")
def get_versions(pid: str) -> dict[str, Any]:
    return _view(load_project(pid))


@router.put("/projects/{pid}/versions")
def put_versions(pid: str, body: dict[str, Optional[str]] = Body(...)) -> dict[str, Any]:
    """Fixe des versions propres au projet. ``null`` (ou « default ») d'une clé la fait revenir au défaut global.
    Les clés absentes ne changent pas. 422 si la famille est inconnue ou la version mal formée."""
    p = load_project(pid)
    cur = dict(p.target_versions)
    for k, v in body.items():
        if k not in standards.KEYS:
            raise HTTPException(status_code=422, detail=f"Famille inconnue « {k} » : attendu {', '.join(standards.KEYS)}")
        if v is None or v == "default":
            cur.pop(k, None)
            continue
        err = standards.check_format(k, v)
        if err:
            raise HTTPException(status_code=422, detail=err)
        cur[k] = standards.normalize(k, v)
    p.target_versions = cur
    store.save(p)  # une génération antérieure devient « obsolète » : les fichiers dépendent des versions
    return _view(p)


@router.get("/projects/{pid}/versions/check")
def check_versions(pid: str) -> dict[str, Any]:
    """Écarts entre les versions du projet et la référence (obsolète, fin de support, plus récente, incohérence) et recommandation.
    Purement local : aucun appel réseau."""
    p = load_project(pid)
    return standards.check(dict(p.target_versions))
