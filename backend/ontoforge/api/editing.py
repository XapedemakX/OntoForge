"""Éditeur graphique (L9) : opérations unitaires + annuler/rétablir, icônes, périmètres, graphe (CONTRACTS.md §5)."""
from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Body, HTTPException, Query
from pydantic import BaseModel, Field

from .. import localize
from ..core.project import Perimeter, Project
from ..editing import graph as graph_mod
from ..editing import history, icons as icon_catalog
from ..editing import ops as ops_mod
from ..editing import perimeter as per_mod
from ..projects import store
from ._common import dump, load_project

router = APIRouter(prefix="/api", tags=["editing"])


# ---- icônes ----------------------------------------------------------------------------------------------

@router.get("/icons")
def icons(q: Optional[str] = Query(None)) -> dict:
    found = icon_catalog.search(q)
    return {"icons": found, "total": len(found)}


# ---- opérations ----------------------------------------------------------------------------------------

def _result(p: Project, *, ok: bool, applied: int, errors: list, warnings: list, label: Optional[str] = None) -> dict:
    st = history.status(p.id)
    lang = localize.ui_lang()  # erreurs et avertissements d'opérations dans la langue de l'interface
    return {"ok": ok, "project": dump(p), "applied": applied, "errors": localize.tr_deep(errors, lang), "warnings": localize.tr_deep(warnings, lang),
            "can_undo": st["can_undo"], "can_redo": st["can_redo"], **({"label": label} if label else {})}


@router.post("/projects/{pid}/ops")
def post_ops(pid: str, body: Any = Body(...)) -> dict:
    """Corps : ``{ops: [...], label?}`` ou directement la liste. Tout ou rien ; HTTP 200 même en cas d'erreurs
    d'opérations (``ok=false``, ``errors`` par index, projet inchangé)."""
    ops = body.get("ops") if isinstance(body, dict) else body
    label = body.get("label") if isinstance(body, dict) else None
    with history.lock():
        p = load_project(pid)
        res = ops_mod.apply_ops(p, ops)
        if res.errors:
            return _result(p, ok=False, applied=0, errors=res.errors, warnings=res.warnings)
        if res.changed_keys:
            names = list(dict.fromkeys(o["op"] for o in ops))
            lab = (label or ", ".join(names))[:120]
            store.save(p)
            history.record(pid, lab, res.before)
        return _result(p, ok=True, applied=res.applied, errors=[], warnings=res.warnings)


@router.get("/projects/{pid}/ops/history")
def ops_history(pid: str) -> dict:
    load_project(pid)
    return history.status(pid)


def _swap(pid: str, redo: bool) -> dict:
    with history.lock():
        p = load_project(pid)
        try:
            label = history.redo(p) if redo else history.undo(p)
        except history.EmptyStack:
            raise HTTPException(status_code=409, detail="Rien à rétablir" if redo else "Rien à annuler") from None
        store.save(p)
        return _result(p, ok=True, applied=0, errors=[], warnings=[], label=label)


@router.post("/projects/{pid}/ops/undo")
def ops_undo(pid: str) -> dict:
    return _swap(pid, False)


@router.post("/projects/{pid}/ops/redo")
def ops_redo(pid: str) -> dict:
    return _swap(pid, True)


# ---- graphe --------------------------------------------------------------------------------------------

@router.get("/projects/{pid}/graph")
def graph(pid: str, perimeter: Optional[str] = Query(None), lang: str = Query("fr"),
          include: str = Query("", description="datatypes,individuals")) -> dict:
    p = load_project(pid)
    try:
        onto, _, _ = per_mod.scope(p, perimeter)
    except per_mod.PerimeterNotFound:
        raise HTTPException(status_code=404, detail=f"Périmètre « {perimeter} » introuvable") from None
    inc = {x.strip() for x in include.split(",") if x.strip()}
    return graph_mod.build_graph(onto, p.view, lang, inc)


# ---- périmètres ------------------------------------------------------------------------------------------

class PerimeterIn(BaseModel):
    id: Optional[str] = None
    name: str = Field(min_length=1)
    description: str = ""
    classes: list[str] = Field(default_factory=list)
    properties: list[str] = Field(default_factory=list)
    include_descendants: bool = False


class ActiveIn(BaseModel):
    id: Optional[str] = None


def _check_members(p: Project, body: PerimeterIn) -> None:
    bad_c = [c for c in body.classes if c not in p.onto.classes]
    bad_p = [x for x in body.properties if x not in p.onto.object_properties and x not in p.onto.datatype_properties]
    if bad_c or bad_p:
        raise HTTPException(status_code=422, detail="Éléments inconnus dans le périmètre — classes : "
                            f"{bad_c or 'aucune'} ; propriétés : {bad_p or 'aucune'}")


def _find(p: Project, perimeter_id: str) -> Perimeter:
    for per in p.perimeters:
        if per.id == perimeter_id:
            return per
    raise HTTPException(status_code=404, detail=f"Périmètre « {perimeter_id} » introuvable")


def _dedupe(xs: list[str]) -> list[str]:
    return list(dict.fromkeys(xs))


@router.get("/projects/{pid}/perimeters")
def list_perimeters(pid: str) -> list:
    return dump(load_project(pid).perimeters)


@router.post("/projects/{pid}/perimeters", status_code=201)
def create_perimeter(pid: str, body: PerimeterIn) -> Any:
    with history.lock():
        p = load_project(pid)
        _check_members(p, body)
        base = store.slugify(body.id or body.name) or "perimetre"
        taken = {x.id for x in p.perimeters}
        if body.id and base in taken:
            raise HTTPException(status_code=409, detail=f"Le périmètre « {base} » existe déjà")
        pid_new, i = base, 2
        while pid_new in taken or pid_new in ("active", "all", "none"):
            pid_new, i = f"{base}-{i}", i + 1
        per = Perimeter(id=pid_new, name=body.name, description=body.description, classes=_dedupe(body.classes),
                        properties=_dedupe(body.properties), include_descendants=body.include_descendants)
        before = ops_mod.snapshot(p, ("perimeters",))
        p.perimeters.append(per)
        store.save(p)
        history.record(pid, f"Périmètre « {per.name} » créé", before)
        return dump(per)


@router.put("/projects/{pid}/perimeters/active")
def set_active(pid: str, body: ActiveIn) -> dict:
    p = load_project(pid)
    if body.id is not None:
        _find(p, body.id)
    p.active_perimeter = body.id
    store.save(p)
    return {"active_perimeter": p.active_perimeter}


@router.get("/projects/{pid}/perimeters/{perimeter_id}")
def get_perimeter(pid: str, perimeter_id: str) -> Any:
    return dump(_find(load_project(pid), perimeter_id))


@router.get("/projects/{pid}/perimeters/{perimeter_id}/preview")
def preview_perimeter(pid: str, perimeter_id: str) -> dict:
    p = load_project(pid)
    per = _find(p, perimeter_id)
    onto, _, notes = per_mod.restrict(p.onto, per)
    return {"counts": {"classes": len(onto.classes), "object_properties": len(onto.object_properties),
                       "datatype_properties": len(onto.datatype_properties), "individuals": len(onto.individuals)},
            "excluded": [{"id": f.id, "rule": f.rule, "title": f.title, "detail": f.detail} for f in notes]}


@router.put("/projects/{pid}/perimeters/{perimeter_id}")
def update_perimeter(pid: str, perimeter_id: str, body: PerimeterIn) -> Any:
    with history.lock():
        p = load_project(pid)
        per = _find(p, perimeter_id)
        _check_members(p, body)
        before = ops_mod.snapshot(p, ("perimeters",))
        per.name, per.description = body.name, body.description
        per.classes, per.properties = _dedupe(body.classes), _dedupe(body.properties)
        per.include_descendants = body.include_descendants
        store.save(p)
        history.record(pid, f"Périmètre « {per.name} » modifié", before)
        return dump(per)


@router.delete("/projects/{pid}/perimeters/{perimeter_id}")
def delete_perimeter(pid: str, perimeter_id: str) -> dict:
    with history.lock():
        p = load_project(pid)
        per = _find(p, perimeter_id)
        before = ops_mod.snapshot(p, ("perimeters",))
        p.perimeters = [x for x in p.perimeters if x.id != perimeter_id]
        if p.active_perimeter == perimeter_id:
            p.active_perimeter = None
        store.save(p)
        history.record(pid, f"Périmètre « {per.name} » supprimé", before)
        return {"deleted": perimeter_id, "active_perimeter": p.active_perimeter}
