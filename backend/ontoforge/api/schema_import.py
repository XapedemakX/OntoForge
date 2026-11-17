"""Import déterministe SQL DDL / CSV / JSON Schema (L48, CONTRACTS §18). Aperçu sans effet, puis application annulable.

``POST /api/import/schema/preview`` (sans projet : sert l'écran Projets avant la création), ``POST /api/projects/{pid}/import/schema/preview`` et
``POST /api/projects/{pid}/import/schema/apply`` (écriture : propriétaire et éditeur seulement, voir ``collab/routes.py``). Aucun LLM.
"""
from __future__ import annotations

import json
from typing import Any, Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from starlette.concurrency import run_in_threadpool

from .. import localize
from ..importers import messages as M
from ..importers import service
from ..importers.limits import MAX_TOTAL_MB, ImportRefused, max_bytes
from ._common import load_project

router = APIRouter(prefix="/api", tags=["import"])


def _lang() -> str:
    return "en" if str(localize.ui_lang()).startswith("en") else "fr"


def _refuse(exc: ImportRefused) -> HTTPException:
    return HTTPException(status_code=exc.status, detail=M.refusal(exc.code, _lang(), exc.params))


def _options(raw: Optional[str]) -> dict[str, Any]:
    if not raw:
        return {}
    if len(raw) > 200_000:
        raise HTTPException(status_code=413, detail=M.refusal("bad_options", _lang(), {}))
    try:
        v = json.loads(raw)
    except ValueError:
        raise HTTPException(status_code=422, detail=M.refusal("bad_options", _lang(), {})) from None
    if not isinstance(v, dict):
        raise HTTPException(status_code=422, detail=M.refusal("bad_options", _lang(), {}))
    return v


async def _read(files: list[UploadFile]) -> list[tuple[str, bytes]]:
    if len(files) > 50:
        raise _refuse(ImportRefused("too_many_files", 413, max=50))
    lim = max_bytes()
    out, total = [], 0
    for f in files:
        data = await f.read(lim + 1)   # lecture bornée : au-delà, service.run refuse (413)
        total += len(data)
        if total > MAX_TOTAL_MB * 1024 * 1024:
            raise _refuse(ImportRefused("too_big_total", 413, max=MAX_TOTAL_MB))
        out.append((f.filename or "fichier", data))
    return out


async def _run(files: list[UploadFile], kind: Optional[str], options: Optional[str], base_iri: Optional[str]) -> service.ImportResult:
    raw = await _read(files)
    opts = _options(options)
    try:
        return await run_in_threadpool(service.run, raw, kind, opts, base_iri)
    except ImportRefused as exc:
        raise _refuse(exc) from None


@router.post("/import/schema/preview")
async def preview_free(files: list[UploadFile] = File(...), kind: Optional[str] = Form(None), options: Optional[str] = Form(None),
                       base_iri: Optional[str] = Form(None)) -> Any:
    """Aperçu sans projet (écran Projets, avant la création). Aucune écriture."""
    res = await _run(files, kind, options, base_iri)
    return service.describe(res, _lang())


@router.post("/projects/{pid}/import/schema/preview")
async def preview(pid: str, files: list[UploadFile] = File(...), kind: Optional[str] = Form(None), options: Optional[str] = Form(None),
                  base_iri: Optional[str] = Form(None)) -> Any:
    p = load_project(pid, "write")
    res = await _run(files, kind, options, base_iri or p.onto.meta.iri)
    return service.describe(res, _lang(), p)


@router.post("/projects/{pid}/import/schema/apply")
async def apply(pid: str, files: list[UploadFile] = File(...), kind: Optional[str] = Form(None), options: Optional[str] = Form(None),
                base_iri: Optional[str] = Form(None), expect_digest: Optional[str] = Form(None)) -> Any:
    """Rejoue le calcul de l'aperçu et ajoute le résultat au projet (ce qui existe déjà n'est jamais modifié). Annulable par /ops/undo."""
    raw = await _read(files)
    opts = _options(options)
    from ..editing import history, ops as ops_mod
    from ..projects import store
    from ._common import dump

    def work() -> dict[str, Any]:
        if not expect_digest:
            raise ImportRefused("missing_digest", 422)
        res = service.run(raw, kind, opts, base_iri or load_project(pid, "write").onto.meta.iri)
        if expect_digest != res.built.digest:
            raise ImportRefused("stale_preview", 409)
        with history.lock():
            p = load_project(pid, "write")
            before = ops_mod.snapshot(p, ("onto", "shapes"))
            prev = service.describe(res, _lang(), p)   # avant la fusion : les conflits sont ceux d'avant
            merged = service.merge_into(p, res)
            names = ", ".join(res.files)[:80]
            for f in res.files:
                if f not in p.source_files:
                    p.source_files.append(f)
            store.save(p)
            history.record(pid, f"Import {res.kind} : {names}", before)
            st = history.status(pid)
        return {"ok": True, "merged": merged, "project": dump(p), "kind": res.kind, "digest": res.built.digest,
                "can_undo": st["can_undo"], "can_redo": st["can_redo"], "preview": prev}
    try:
        return await run_in_threadpool(work)
    except ImportRefused as exc:
        raise _refuse(exc) from None
