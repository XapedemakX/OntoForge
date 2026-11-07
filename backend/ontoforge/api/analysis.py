"""Conformité, SHACL, analyse / arbitrage, génération, requêtes (CONTRACTS.md §2)."""
from __future__ import annotations

import io
import zipfile
from typing import Any, Optional

from fastapi import APIRouter, Body, File, HTTPException, Query, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel

from .. import localize
from ..core.lang import LABEL_LANG
from ..core.pg_model import PGModel
from ..core.project import GenerationRecord, Project
from ..projects import store
from ._common import check_target, dump, load_project, not_available, optional_service, parse_error, service

router = APIRouter(prefix="/api/projects/{pid}", tags=["analysis"])

DATA_FORMATS = {".ttl": "turtle", ".owl": "xml", ".rdf": "xml", ".xml": "xml", ".jsonld": "json-ld",
                ".json": "json-ld", ".nt": "nt", ".n3": "n3", ".trig": "trig"}


MAX_GENERATIONS = 50


class MergeRequest(BaseModel):
    merge: bool = True
    dry_run: bool = False  # aperçu : renvoie les shapes générées sans enregistrer le projet


class TranslateRequest(BaseModel):
    sparql: str


# ---- helpers ---------------------------------------------------------------------------------

def _scope(p: Project, perimeter: Optional[str]):
    """Ontologie / shapes / constats d'information du périmètre demandé (L9) ; 404 si inconnu."""
    from ..editing import perimeter as per_mod
    try:
        return per_mod.scope(p, perimeter)
    except per_mod.PerimeterNotFound:
        raise HTTPException(status_code=404, detail=f"Périmètre « {perimeter} » introuvable") from None


def run_analysis(p: Project, target: str, perimeter: Optional[str] = None) -> PGModel:
    analyze = service("mapping.engine", "analyze")
    onto, shapes, notes = _scope(p, perimeter)
    token = LABEL_LANG.set(localize.labels_lang())  # libellés lus par les règles : langue des libellés des paramètres
    try:
        pg = analyze(onto, shapes, target, dict(p.decisions.get(target, {})))
    finally:
        LABEL_LANG.reset(token)
    if notes:
        pg.findings.extend(notes)
    for nt in pg.node_types.values():  # D-L9-02 : icône de la première classe source qui en a une
        nt.icon = next((p.view.icons[c] for c in nt.source if c in p.view.icons), None)
    return pg


def _ui(pg: PGModel) -> PGModel:
    """Traduit les textes générés quand ``settings.language.ui`` vaut ``en`` (uniquement pour les réponses d'API affichées)."""
    return localize.localize_pg(pg, localize.ui_lang())


def _target_or_default(p: Project, target: Optional[str]) -> str:
    return check_target(target or p.target)


def _as_files(result: Any) -> dict[str, str]:
    """Accepte dict[nom, contenu] (CONTRACTS) ou list[GeneratedFile{path, content}] (D-017)."""
    if isinstance(result, dict):
        return {str(k): v if isinstance(v, str) else str(v) for k, v in result.items()}
    out: dict[str, str] = {}
    for f in result or []:
        path = getattr(f, "path", None) or (f.get("path") if isinstance(f, dict) else None)
        content = getattr(f, "content", None) if not isinstance(f, dict) else f.get("content")
        if path:
            out[path] = content or ""
    return out


def generate_files(p: Project, target: str, perimeter: Optional[str] = None) -> tuple[dict[str, str], list[str]]:
    files, missing, _ = _generate(p, target, perimeter)
    return files, missing


def _generate(p: Project, target: str, perimeter: Optional[str] = None) -> tuple[dict[str, str], list[str], PGModel]:
    pg = run_analysis(p, target, perimeter)
    onto = _scope(p, perimeter)[0]
    files: dict[str, str] = {}
    missing: list[str] = []
    for mod in (f"targets.{target}", "targets.graphql", "targets.report"):
        fn = optional_service(mod, "generate")
        if fn is None:
            missing.append(mod)
            continue
        files.update(_as_files(fn(pg, onto)))
    if len(missing) == 3:
        raise not_available(f"targets.{target}")
    return files, missing, pg


# ---- conformité ------------------------------------------------------------------------------

@router.get("/conformance")
def conformance(pid: str) -> Any:
    p = load_project(pid)
    check = service("conformance.profiles", "check_conformance")
    return localize.localize_conformance(dump(check(p.onto, None)), localize.ui_lang())


# ---- SHACL -----------------------------------------------------------------------------------

@router.post("/shacl/generate")
def shacl_generate(pid: str, body: MergeRequest = Body(default_factory=MergeRequest)) -> dict:
    p = load_project(pid)
    generate_shapes = service("shacl.owl_to_shacl", "generate_shapes")
    generated, notes = generate_shapes(p.onto)
    if body.dry_run:
        return {"project": dump(p), "generated": dump(generated), "notes": list(notes), "dry_run": True}
    if body.merge:
        merged = p.shapes.model_copy(deep=True)
        for k, v in generated.shapes.items():
            merged.shapes.setdefault(k, v)
        for k, v in generated.property_shapes.items():
            merged.property_shapes.setdefault(k, v)
        for k, v in generated.prefixes.items():
            merged.prefixes.setdefault(k, v)
        p.shapes = merged
    else:
        p.shapes = generated
    store.save(p)
    return {"project": dump(p), "notes": list(notes)}


@router.post("/shacl/validate")
async def shacl_validate(pid: str, file: UploadFile = File(...)) -> Any:
    p = load_project(pid)
    validate = service("shacl.validate", "validate")
    raw = await file.read()
    if not raw.strip():
        raise HTTPException(status_code=422, detail="Fichier de données vide")
    name = (file.filename or "").lower()
    fmt = next((f for ext, f in DATA_FORMATS.items() if name.endswith(ext)), None)
    try:
        report = validate(raw, p.shapes, p.onto, fmt)
    except HTTPException:
        raise
    except Exception as exc:
        raise parse_error(f"les données « {file.filename or 'fichier'} »", exc) from None
    return dump(report)


# ---- analyse et arbitrage ----------------------------------------------------------------------

@router.post("/analyze", response_model=PGModel)
def analyze(pid: str, target: Optional[str] = Query(None), perimeter: Optional[str] = Query(None)) -> PGModel:
    p = load_project(pid)
    return _ui(run_analysis(p, _target_or_default(p, target), perimeter))


@router.put("/decisions/{target}", response_model=PGModel)
def put_decisions(pid: str, target: str, body: dict[str, Optional[str]] = Body(...)) -> PGModel:
    check_target(target)
    p = load_project(pid)
    dec = dict(p.decisions.get(target, {}))
    for fid, opt in body.items():
        if opt is None:
            dec.pop(fid, None)
        else:
            dec[fid] = opt
    p.decisions[target] = dec
    pg = run_analysis(p, target)  # 501 avant toute écriture si le moteur manque
    store.save(p)
    return _ui(pg)


@router.post("/decisions/{target}/accept-recommended", response_model=PGModel)
def accept_recommended(pid: str, target: str, include_lost: bool = Query(False)) -> PGModel:
    """Accepte les recommandations ; les constats « lost » restent à arbitrer par l'humain sauf include_lost=true."""
    check_target(target)
    p = load_project(pid)
    pg = run_analysis(p, target)
    dec = dict(p.decisions.get(target, {}))
    changed = False
    for f in pg.findings:
        if f.severity in (("review", "lost") if include_lost else ("review",)) and not f.chosen and f.id not in dec and f.recommended:
            dec[f.id] = f.recommended
            changed = True
    if not changed:
        return _ui(pg)
    p.decisions[target] = dec
    store.save(p)
    return _ui(run_analysis(p, target))


# ---- génération ------------------------------------------------------------------------------

@router.get("/generate/{target}")
def generate(pid: str, target: str, perimeter: Optional[str] = Query(None)) -> dict:
    check_target(target)
    p = load_project(pid)
    files, missing, pg = _generate(p, target, perimeter)
    summary = {"auto": 0, "review": 0, "lost": 0, "pending": 0}
    for f in pg.findings:
        if f.severity in summary:
            summary[f.severity] += 1
        if f.severity in ("review", "lost") and not f.chosen:
            summary["pending"] += 1
    p.generations.append(GenerationRecord(target=target, perimeter=perimeter, at=store.now_iso(), files=sorted(files),
                                          findings_summary=summary, project_updated_at=p.updated_at))
    del p.generations[:-MAX_GENERATIONS]
    store.save(p, touch=False)  # l'historique ne change pas updated_at (sinon tout serait « obsolète »)
    return {"files": files, "missing": missing}


@router.get("/generations")
def generations(pid: str) -> list[dict]:
    """Historique des générations du projet, la plus récente d'abord."""
    p = load_project(pid)
    return [g.model_dump(mode="json") for g in reversed(p.generations)]


@router.get("/generate/{target}/zip")
def generate_zip(pid: str, target: str, perimeter: Optional[str] = Query(None)) -> Response:
    check_target(target)
    p = load_project(pid)
    files, _ = generate_files(p, target, perimeter)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, content in sorted(files.items()):
            zf.writestr(f"{p.id}-{target}/{name}", content)
    return Response(content=buf.getvalue(), media_type="application/zip",
                    headers={"Content-Disposition": f'attachment; filename="{p.id}-{target}.zip"'})


# ---- requêtes --------------------------------------------------------------------------------

@router.post("/queries/translate")
def translate(pid: str, body: TranslateRequest, target: Optional[str] = Query(None)) -> Any:
    p = load_project(pid)
    fn = service("queries.translate", "translate")
    pg = run_analysis(p, _target_or_default(p, target))
    return dump(fn(body.sparql, pg, p.onto))


@router.get("/queries/competency")
def competency(pid: str, target: Optional[str] = Query(None)) -> Any:
    p = load_project(pid)
    fn = service("queries.competency", "competency_questions")
    pg = run_analysis(p, _target_or_default(p, target))
    lang = localize.ui_lang()
    return localize.tr_deep(dump(fn(pg, p.onto, lang)), lang)
