"""Éditeur de fichiers (L22) : arbre, lecture, validation en direct, diff et application (CONTRACTS.md §5bis)."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Request
from fastapi.routing import APIRoute
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from .. import localize
from ..editing import files as fm
from ..editing import history
from ..editing import ops as ops_mod
from ..projects import store
from ._common import dump, load_project

MAX_BODY = 4 * fm.MAX_BYTES  # un texte de 2 Mo échappé en JSON peut atteindre plusieurs fois sa taille


class _TooBig(Exception):
    pass


class _LimitedRoute(APIRoute):
    """Refuse (413) un corps HTTP trop gros, d'après Content-Length puis en comptant les octets reçus (corps en morceaux)."""

    def get_route_handler(self):
        inner = super().get_route_handler()

        async def handler(request: Request):
            if request.method in ("PUT", "POST"):
                cl = request.headers.get("content-length")
                if cl and cl.isdigit() and int(cl) > MAX_BODY:
                    return _too_big()
                total = 0
                receive = request.receive

                async def counting():
                    nonlocal total
                    msg = await receive()
                    if msg["type"] == "http.request":
                        total += len(msg.get("body", b""))
                        if total > MAX_BODY:
                            raise _TooBig()
                    return msg

                request = Request(request.scope, counting)
            try:
                return await inner(request)
            except _TooBig:
                return _too_big()

        return handler


def _too_big() -> JSONResponse:
    return _err(413, f"Corps de requête trop volumineux (> {MAX_BODY // 1_000_000} Mo)", f"Request body too large (> {MAX_BODY // 1_000_000} MB)")


router = APIRouter(prefix="/api", tags=["files"], route_class=_LimitedRoute)


class ContentIn(BaseModel):
    path: str
    content: str


class ApplyIn(BaseModel):
    content: str
    base_etag: Optional[str] = None
    force: bool = False


def _err(status: int, fr: str, en: str, **extra) -> JSONResponse:
    lang = localize.ui_lang()
    return JSONResponse(status_code=status, content={"detail": en if lang == "en" else fr, **extra})


def _missing(path: str) -> JSONResponse:
    return _err(404, f"Fichier « {path} » introuvable", f"File \"{path}\" not found")


@router.get("/projects/{pid}/files")
def list_files(pid: str) -> dict:
    return fm.tree(load_project(pid))


@router.post("/projects/{pid}/files/validate")
def validate_file(pid: str, body: ContentIn) -> dict:
    p = load_project(pid)
    return {"diagnostics": fm.validate(p, body.path, body.content, localize.ui_lang())}


@router.post("/projects/{pid}/files/diff")
def diff_file(pid: str, body: ContentIn):
    p = load_project(pid)
    try:
        cur = fm.read(p, body.path)
        prep = fm.prepare(p, body.path, body.content, localize.ui_lang())
    except fm.FileNotFound:
        return _missing(body.path)
    except fm.ReadOnlyFile:
        return _err(403, "Fichier généré en lecture seule", "Generated file is read-only")
    except fm.Invalid as e:
        return _err(422, "Syntaxe invalide : corrigez les erreurs avant d'appliquer", "Invalid syntax: fix the errors before applying",
                    diagnostics=e.diagnostics)
    return {"changed": prep.changed, "summary": prep.summary, "current": cur["content"], "after": prep.after_text,
            "etag": cur["etag"], "warnings": prep.warnings, "source": cur.get("source")}


@router.get("/projects/{pid}/files/{path:path}")
def read_file(pid: str, path: str):
    p = load_project(pid)
    try:
        return fm.read(p, path)
    except fm.FileNotFound:
        return _missing(path)


@router.put("/projects/{pid}/files/{path:path}")
def put_file(pid: str, path: str, body: ApplyIn):
    lang = localize.ui_lang()
    with history.lock():
        p = load_project(pid)
        try:
            cur = fm.read(p, path) if not path.startswith(fm.GENERATED_PREFIX) else None
            prep = fm.prepare(p, path, body.content, lang)
        except fm.FileNotFound:
            return _missing(path)
        except fm.ReadOnlyFile:
            return _err(403, "Fichier généré en lecture seule : modifiez l'ontologie ou les décisions",
                        "Generated file is read-only: edit the ontology or the decisions")
        except fm.Invalid as e:
            return _err(422, "Syntaxe invalide : le fichier n'a pas été appliqué", "Invalid syntax: the file was not applied",
                        diagnostics=e.diagnostics)
        assert cur is not None
        if body.base_etag and body.base_etag != cur["etag"] and not body.force:
            return _err(409, "Le projet a changé ailleurs pendant l'édition", "The project changed elsewhere while you were editing",
                        current_etag=cur["etag"], current_content=cur["content"], version=p.updated_at)
        if not prep.changed:
            st = history.status(pid)
            return {"ok": True, "changed": False, "project": dump(p), "content": cur["content"], "etag": cur["etag"],
                    "summary": prep.summary, "warnings": prep.warnings, "diagnostics": fm.validate(p, path, prep.after_text, lang),
                    "source": cur.get("source"), "can_undo": st["can_undo"], "can_redo": st["can_redo"], "version": p.updated_at}
        if prep.model_changed:
            key = fm.SNAPSHOT_KEY[path]
            before = ops_mod.snapshot(p, (key,))
            if prep.onto is not None:
                p.onto = prep.onto
            elif prep.shapes is not None:
                p.shapes = prep.shapes
            else:
                p.decisions = prep.decisions or {}
            store.save(p)
            history.record(pid, f"Fichier {path} appliqué"[:120], before)
        # sinon : seul le texte change (commentaires, mise en forme) ; le modèle est identique, pas d'entrée d'historique
        fm.remember_source(p, path, prep)
        st = history.status(pid)
        text, note = fm.served(p, path)
        return {"ok": True, "changed": True, "project": dump(p), "content": text, "etag": fm.etag_of(text), "source": note, "summary": prep.summary,
                "warnings": prep.warnings, "diagnostics": fm.validate(p, path, text, lang),
                "can_undo": st["can_undo"], "can_redo": st["can_redo"], "version": p.updated_at}
