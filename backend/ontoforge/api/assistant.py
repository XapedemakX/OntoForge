"""Assistant IA de conception (L6). Routes présentes dès L1 ; 501 tant que ``assistant/service.py`` n'existe pas.

Fonctions attendues dans ``ontoforge.assistant.service`` (proposition lead, à confirmer en L6) :
- ``status() -> {provider, model, configured}``
- ``draft(text: str, kind: str, base_iri: str | None) -> {proposal: OntoModel, explanation, warnings}``
- ``propose_shapes(onto: OntoModel, shapes: ShapesModel) -> {proposal: ShapesModel, explanation}``
- ``explain(finding: Finding, target: str, onto: OntoModel) -> str | {text}``
Les propositions ne sont jamais appliquées ici : le front les soumet à revue humaine puis appelle PUT onto/shapes.
"""
from __future__ import annotations

import os
import re
from typing import Any, Literal, Optional

from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from pydantic import BaseModel

from ._common import check_target, decode, dump, load_project, service
from .analysis import run_analysis

router = APIRouter(prefix="/api/assistant", tags=["assistant"])
SERVICE = "assistant.service"


class DraftRequest(BaseModel):
    text: str
    kind: Literal["text", "csv", "sql"] = "text"
    base_iri: Optional[str] = None
    provider_id: Optional[str] = None
    filename: Optional[str] = None  # nom du fichier source (CSV) : sert à nommer la classe proposée


class Attachment(BaseModel):
    name: str
    kind: Literal["csv", "sql", "text", "markdown"] = "text"
    content: str


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    project_id: str
    messages: list[ChatMessage]
    provider_id: Optional[str] = None
    attachments: list[Attachment] = []
    context: Optional[dict[str, Any]] = None  # AssistantContext (L16) : écran, sélection, extra…


class ShapesRequest(BaseModel):
    project_id: str
    provider_id: Optional[str] = None


class ExplainRequest(BaseModel):
    project_id: str
    target: str
    finding_id: str
    provider_id: Optional[str] = None


@router.get("/status")
def status() -> Any:
    return dump(service(SERVICE, "status")())


@router.post("/draft")
def draft(body: DraftRequest) -> Any:
    fn = service(SERVICE, "draft")
    extra = {"filename": body.filename} if body.filename else {}
    return dump(fn(body.text, body.kind, body.base_iri, body.provider_id, **extra))


@router.post("/shapes")
def shapes(body: ShapesRequest) -> Any:
    fn = service(SERVICE, "propose_shapes")
    p = load_project(body.project_id)
    return dump(fn(p.onto, p.shapes, body.provider_id))


@router.post("/explain")
def explain(body: ExplainRequest) -> Any:
    fn = service(SERVICE, "explain")
    check_target(body.target)
    p = load_project(body.project_id)
    pg = run_analysis(p, body.target)
    finding = next((f for f in pg.findings if f.id == body.finding_id), None)
    if finding is None:
        raise HTTPException(status_code=404, detail=f"Constat « {body.finding_id} » introuvable")
    res = fn(finding, body.target, p.onto, body.provider_id)
    return {"text": res} if isinstance(res, str) else dump(res)


@router.post("/chat")
def chat(body: ChatRequest) -> Any:
    fn = service(SERVICE, "chat")
    p = load_project(body.project_id)
    atts = [a.model_dump() for a in body.attachments]
    if body.context is not None:  # L16 : assistant global, conscient de l'écran, qui propose des actions
        from ..assistant import agent
        return dump(agent.run(p, [m.model_dump() for m in body.messages], body.context, body.provider_id, atts))
    res = dump(fn(p, [m.model_dump() for m in body.messages], body.provider_id, atts))
    if isinstance(res, dict):
        res.setdefault("actions", [{"kind": "proposal", "payload": {"proposal": res["proposal"]}, "summary": "Proposition d'ontologie"}]
                       if res.get("proposal") else [])
    return res


class ApplyShapesRequest(BaseModel):
    project_id: str
    patches: list[dict[str, Any]]
    label: Optional[str] = None


@router.post("/shapes/apply")
def apply_shapes(body: ApplyShapesRequest) -> Any:
    """Applique des correctifs de shapes proposés par l'assistant (revalidés), annulables via /ops/undo."""
    from ..assistant import agent
    from ..editing import history, ops as ops_mod
    from ..projects import store
    with history.lock():
        p = load_project(body.project_id)
        patches, _prev, warns = agent.validate_shape_patches(p, body.patches)
        if not patches:
            raise HTTPException(status_code=422, detail="Aucune contrainte valide à appliquer. " + " ".join(warns))
        before = ops_mod.snapshot(p, ("shapes",))
        n = agent.apply_shape_patches(p.shapes, p.onto, patches)
        store.save(p)
        history.record(body.project_id, (body.label or f"Assistant : {n} contrainte(s) de shape")[:120], before)
        st = history.status(body.project_id)
    return {"ok": True, "applied": n, "warnings": warns, "project": dump(p), "can_undo": st["can_undo"], "can_redo": st["can_redo"]}


UPLOAD_MAX = 2 * 1024 * 1024
_TABLE = re.compile(r"(?is)\bcreate\s+(?:or\s+replace\s+)?(?:temp(?:orary)?\s+)?table\s+(?:if\s+not\s+exists\s+)?([`\"\[]?[\w.]+[`\"\]]?)")
_EXT = {".csv": "csv", ".tsv": "csv", ".sql": "sql", ".md": "markdown", ".markdown": "markdown", ".txt": "text"}


def detect_kind(name: str, text: str) -> str:
    ext = os.path.splitext(name.lower())[1]
    if ext in _EXT:
        return _EXT[ext]
    if _TABLE.search(text):
        return "sql"
    lines = [ln for ln in text.splitlines()[:10] if ln.strip()]
    for sep in (",", ";", "\t"):
        if len(lines) >= 2 and lines[0].count(sep) >= 1 and len({ln.count(sep) for ln in lines}) == 1:
            return "csv"
    return "markdown" if re.search(r"(?m)^#{1,6}\s", text) else "text"


@router.post("/upload")
async def upload(file: UploadFile = File(...)) -> Any:
    data = await file.read(UPLOAD_MAX + 1)
    if len(data) > UPLOAD_MAX:
        raise HTTPException(status_code=413, detail=f"Fichier trop volumineux (maximum {UPLOAD_MAX // 1024 // 1024} Mo).")
    if not data.strip():
        raise HTTPException(status_code=422, detail="Le fichier est vide.")
    text = decode(data)
    name = os.path.basename(file.filename or "fichier")
    kind = detect_kind(name, text)
    lines = text.splitlines()
    preview: dict[str, Any] = {"lines": lines[:20], "total_lines": len(lines), "truncated": len(lines) > 20}
    if kind == "sql":
        preview["tables"] = [m.strip('`"[]') for m in _TABLE.findall(text)]
    elif kind == "csv" and lines:
        sep = max((",", ";", "\t"), key=lines[0].count)
        preview["columns"] = [c.strip() for c in lines[0].split(sep)]
    return {"name": name, "kind": kind, "preview": preview, "size": len(data), "content": text}


# ----------------------------------------------------------------------------- L25 : amorcer depuis un document
class DocPage(BaseModel):
    page: int
    text: str


class DocPayload(BaseModel):
    name: str
    pages: list[DocPage]


class DocEstimateRequest(BaseModel):
    document: DocPayload
    provider_id: Optional[str] = None


class DocDraftRequest(BaseModel):
    project_id: str
    document: DocPayload
    provider_id: Optional[str] = None
    confirm_hosted: bool = False


def _doc_of(payload: DocPayload) -> Any:
    from ..assistant import document as docs
    lim = docs.limits()
    doc = docs.Document(payload.name[:200], [docs.Page(p.page, p.text) for p in payload.pages])
    if len(doc.pages) > max(lim["max_pages"], 1) * 60 or doc.chars > lim["max_chars"]:
        raise HTTPException(status_code=413, detail="Document trop volumineux.")
    if not doc.pages or not doc.chars:
        raise HTTPException(status_code=422, detail="Document vide.")
    return doc


DEMO_FILES = {"fr": "automaint-cahier-des-charges.pdf", "en": "automaint-requirements.pdf"}


@router.get("/document/demo")
def document_demo(lang: Optional[str] = Query(None, description="fr ou en ; défaut : langue de l'interface")) -> Any:
    """Document de démonstration (samples/automaint), en lecture seule : noms de fichier fixes, dans la langue de l'interface (ou ``lang``)."""
    from fastapi.responses import Response
    from .. import samples as samples_mod
    from ..localize import gen
    if lang and gen.normalize(lang) is None:
        raise HTTPException(status_code=422, detail=f"Langue inconnue « {lang} » (fr ou en) / unknown language \"{lang}\" (fr or en)")
    name = DEMO_FILES[gen.resolve(lang)]
    f = samples_mod.samples_root() / "automaint" / name
    if not f.is_file():
        raise HTTPException(status_code=404, detail="Document de démonstration absent de cette installation. / Demo document missing from this installation.")
    return Response(f.read_bytes(), media_type="application/pdf", headers={"Content-Disposition": f'inline; filename="{name}"'})


@router.post("/document/upload")
async def document_upload(file: UploadFile = File(...)) -> Any:
    """Lit un .txt, .md ou .pdf (texte natif) : pages de texte, tailles, limites. Aucun appel réseau, rien n'est analysé ici."""
    from ..assistant import document as docs
    from ..localize import ui_lang
    lim = docs.limits()
    data = await file.read(lim["max_bytes"] + 1)
    try:
        doc = docs.extract(os.path.basename(file.filename or "document"), data)
    except docs.DocumentError as exc:
        raise HTTPException(status_code=exc.status, detail=exc.message(ui_lang())) from None
    return {"name": doc.name, "size": len(data), "pages": [{"page": p.page, "text": p.text} for p in doc.pages], "page_count": len(doc.pages),
            "chars": doc.chars, "limits": lim}


@router.post("/document/estimate")
def document_estimate(body: DocEstimateRequest) -> Any:
    """Nombre d'appels et taille envoyée, et si le fournisseur est hébergé (avertissement de confidentialité) ; n'envoie rien."""
    from ..assistant import docdraft, service
    return docdraft.plan(_doc_of(body.document), service._provider(body.provider_id))


@router.post("/document/draft")
def document_draft(body: DocDraftRequest) -> Any:
    """Brouillon d'ontologie traçable depuis un document. Rien n'est appliqué : le front soumet chaque élément à confirmation."""
    from ..assistant import docdraft, service
    from ..localize import ui_lang
    p = load_project(body.project_id)
    return dump(docdraft.draft_document(p, _doc_of(body.document), service._provider(body.provider_id), ui_lang(), body.confirm_hosted))
