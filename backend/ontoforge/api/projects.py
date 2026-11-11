"""Projets : CRUD, import de fichiers, édition de l'ontologie / des shapes, DSL, export (CONTRACTS.md §2)."""
from __future__ import annotations

from typing import Literal, Optional

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel

from .. import localize, samples as samples_mod, standards
from ..core.onto_model import OntoModel
from ..core.project import Project
from ..core.shapes_model import ShapesModel
from ..projects import store
from ._common import decode, dump, load_project, parse_error, service

router = APIRouter(prefix="/api", tags=["projects"])

ONTO_MEDIA = {
    "turtle": ("text/turtle", "ttl"),
    "xml": ("application/rdf+xml", "owl"),
    "json-ld": ("application/ld+json", "jsonld"),
    "nt": ("application/n-triples", "nt"),
    "n3": ("text/n3", "n3"),
    "trig": ("application/trig", "trig"),
}


class ProjectCreate(BaseModel):
    name: str
    description: Optional[str] = ""
    sample: Optional[str] = None


class DslRequest(BaseModel):
    text: str
    merge: bool = True


def summary(p: Project) -> dict:
    return {
        "id": p.id,
        "name": p.name,
        "description": p.description,
        "created_at": p.created_at,
        "updated_at": p.updated_at,
        "source_files": p.source_files,
        "target": p.target,
        "stats": {
            "classes": len(p.onto.classes),
            "object_properties": len(p.onto.object_properties),
            "datatype_properties": len(p.onto.datatype_properties),
            "individuals": len(p.onto.individuals),
            "shapes": len(p.shapes.shapes),
        },
    }


def is_shapes_text(text: str) -> bool:
    """Détection kind=auto : présence de sh:NodeShape / sh:PropertyShape (espace de noms SHACL)."""
    return "http://www.w3.org/ns/shacl#" in text and ("NodeShape" in text or "PropertyShape" in text)


def _parse_onto(data: str | bytes, filename: str | None) -> tuple[OntoModel, list[str]]:
    parse_ontology = service("io.rdf_import", "parse_ontology")
    try:
        return parse_ontology(data, None, filename)
    except HTTPException:
        raise
    except Exception as exc:
        raise parse_error(f"l'ontologie « {filename or 'fichier'} »", exc) from None


def _parse_shapes(data: str | bytes, filename: str | None) -> tuple[ShapesModel, list[str]]:
    parse_shapes = service("shacl.import_shapes", "parse_shapes")
    try:
        return parse_shapes(data, None, filename)
    except HTTPException:
        raise
    except Exception as exc:
        raise parse_error(f"les shapes « {filename or 'fichier'} »", exc) from None


# ---- CRUD ------------------------------------------------------------------------------------

@router.get("/projects")
def list_projects() -> list[dict]:
    return [summary(p) for p in store.list_projects()]


@router.post("/projects", response_model=Project, status_code=201)
def create_project(body: ProjectCreate) -> Project:
    if not body.name.strip():
        raise HTTPException(status_code=422, detail="Le nom du projet est obligatoire")
    p = store.create(body.name.strip(), body.description or "")
    data_files: list[tuple[str, str]] = []
    if body.sample:
        try:
            s = samples_mod.get_sample(body.sample)
        except KeyError:
            raise HTTPException(status_code=404, detail=f"Exemple « {body.sample} » introuvable") from None
        notes: list[str] = []
        for fname in s["ontology"][:1]:
            raw = (s["dir"] / fname).read_bytes()
            p.onto, warns = _parse_onto(raw, fname)
            p.source_files.append(fname)
            notes += warns
        for fname in s["shapes"][:1]:
            raw = (s["dir"] / fname).read_bytes()
            p.shapes, warns = _parse_shapes(raw, fname)
            p.source_files.append(fname)
            notes += warns
        for fname in s["data"][:1]:
            data_files.append(("data.ttl", (s["dir"] / fname).read_text(encoding="utf-8")))
            p.source_files.append(fname)
        if notes:
            p.notes = "\n".join(notes[:200])
    store.save(p)
    for name, content in data_files:
        store.write_file(p.id, name, content)
    return p


@router.get("/projects/{pid}", response_model=Project)
def get_project(pid: str) -> Project:
    return load_project(pid)


@router.put("/projects/{pid}", response_model=Project)
def put_project(pid: str, body: Project) -> Project:
    old = load_project(pid)
    body.id = old.id
    body.created_at = old.created_at
    body.generations = old.generations  # l'historique est tenu côté serveur
    return store.save(body)


@router.delete("/projects/{pid}", response_model=Project)
def delete_project(pid: str) -> Project:
    load_project(pid)
    from ..localstore import store as local_store
    local_store.drop(pid)  # verrou d'écriture du triplestore local : attend les requêtes en cours, évite le rmtree sous leurs pieds
    return store.delete(pid)


# ---- Import / édition ------------------------------------------------------------------------

@router.post("/projects/{pid}/import")
async def import_file(
    pid: str,
    file: UploadFile = File(...),
    kind: Literal["ontology", "shapes", "auto"] = Form("auto"),
) -> dict:
    p = load_project(pid)
    raw = await file.read()
    if not raw.strip():
        raise HTTPException(status_code=422, detail="Fichier vide")
    if kind == "auto":
        kind = "shapes" if is_shapes_text(decode(raw)) else "ontology"
    if kind == "shapes":
        p.shapes, warnings = _parse_shapes(raw, file.filename)
    else:
        p.onto, warnings = _parse_onto(raw, file.filename)
    if file.filename and file.filename not in p.source_files:
        p.source_files.append(file.filename)
    store.save(p)
    return {"project": dump(p), "warnings": list(warnings), "kind": kind}


@router.put("/projects/{pid}/onto", response_model=Project)
def put_onto(pid: str, body: OntoModel) -> Project:
    p = load_project(pid)
    p.onto = body
    return store.save(p)


@router.put("/projects/{pid}/shapes", response_model=Project)
def put_shapes(pid: str, body: ShapesModel) -> Project:
    p = load_project(pid)
    p.shapes = body
    return store.save(p)


@router.post("/projects/{pid}/dsl")
def apply_dsl(pid: str, body: DslRequest) -> dict:
    p = load_project(pid)
    parse_dsl = service("io.dsl", "parse_dsl")
    model, errors = parse_dsl(body.text, p.onto if body.merge else None)
    p.onto = model
    store.save(p)
    return {"project": dump(p), "errors": localize.tr_deep(dump(errors), localize.ui_lang())}  # messages d'erreur dans la langue de l'interface


# ---- Export ----------------------------------------------------------------------------------

@router.get("/projects/{pid}/export/ontology")
def export_ontology(pid: str, format: str = Query("turtle")) -> Response:
    if format not in ONTO_MEDIA:
        raise HTTPException(status_code=422, detail=f"Format inconnu « {format} » : {', '.join(ONTO_MEDIA)}")
    p = load_project(pid)
    serialize = service("io.rdf_export", "serialize")
    media, ext = ONTO_MEDIA[format]
    text = serialize(p.onto, format)
    return Response(content=text, media_type=f"{media}; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{p.id}.{ext}"'})


@router.get("/projects/{pid}/export/shapes")
def export_shapes(pid: str, format: str = Query("turtle")) -> Response:
    if format not in ONTO_MEDIA:
        raise HTTPException(status_code=422, detail=f"Format inconnu « {format} » : {', '.join(ONTO_MEDIA)}")
    p = load_project(pid)
    serialize_shapes = service("shacl.export_shapes", "serialize_shapes")
    media, ext = ONTO_MEDIA[format]
    text = serialize_shapes(p.shapes, format)
    if format in ("turtle", "ttl"):  # L31 : l'en-tête rappelle la version SHACL ciblée (fonctions 1.2 désactivées) ; commentaire Turtle, sans effet sur le graphe
        text = standards.shacl_header(standards.for_project(p)["shacl"]) + text
    return Response(content=text, media_type=f"{media}; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{p.id}-shapes.{ext}"'})
