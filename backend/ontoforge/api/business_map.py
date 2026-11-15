"""Carte métier (L36a, CONTRACTS.md « Carte métier ») : zones teintées, rôles, cadres, scénarios, mise en page."""
from __future__ import annotations

from typing import Any, Literal, Optional

from fastapi import APIRouter, Body, HTTPException, Query
from pydantic import BaseModel

from ..businessmap import service as svc
from ._common import load_project

router = APIRouter(prefix="/api/projects/{pid}/business-map", tags=["business-map"])

Source = Literal["ontology", "target"]


class SuggestZonesIn(BaseModel):
    strategy: str = "hierarchy"  # perimeters | hierarchy | namespace | communities | llm
    provider_id: Optional[str] = None
    max_zones: int = 8
    seed: int = 0
    apply: bool = False


class SuggestFramesIn(BaseModel):
    apply: bool = False


class LayoutIn(BaseModel):
    iterations: Optional[int] = None
    seed: int = 0
    time_limit_s: Optional[float] = None
    apply: bool = False


def _guard(fn, *a, **kw) -> Any:
    try:
        return fn(*a, **kw)
    except svc.MapError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    except ValueError as exc:  # modèle pydantic ou stratégie invalide
        raise HTTPException(status_code=422, detail=str(exc)) from None


@router.get("")
def get_map(pid: str, source: Source = Query("ontology")) -> dict:
    return _guard(svc.get_map, load_project(pid), source, False)   # L41 : une route de lecture n'écrit pas dans le projet


@router.put("")
def put_map(pid: str, source: Source = Query("ontology"), body: dict = Body(...)) -> dict:
    return _guard(svc.save_state, load_project(pid), source, body)


@router.post("/suggest-zones")
def suggest_zones(pid: str, body: SuggestZonesIn = SuggestZonesIn(), source: Source = Query("ontology")) -> dict:
    return _guard(svc.suggest_zones, load_project(pid), source, body.strategy, provider_id=body.provider_id, seed=body.seed,
                  max_zones=body.max_zones, apply=body.apply)


@router.post("/suggest-frames")
def suggest_frames(pid: str, body: SuggestFramesIn = SuggestFramesIn(), source: Source = Query("ontology")) -> dict:
    return _guard(svc.suggest_frames, load_project(pid), source, body.apply)


@router.post("/layout")
def layout(pid: str, body: LayoutIn = LayoutIn(), source: Source = Query("ontology")) -> dict:
    return _guard(svc.layout, load_project(pid), source, body.iterations, body.seed, body.time_limit_s, body.apply)
