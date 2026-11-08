"""Triplestore local embarqué par projet (L19, CONTRACTS §6.1) : chargement, statistiques, vidage, validation SHACL.

Les requêtes passent par `POST /query/run` avec `endpoint: {kind: "local"}` (voir api/queries.py).
"""
from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Body, File, Form, HTTPException, UploadFile

from .. import localize, samples as samples_mod
from ..localstore import store as st
from ..projects import store as project_store
from ._common import dump, load_project, service

router = APIRouter(prefix="/api/projects/{pid}/store", tags=["local-store"])


def _err(exc: st.StoreError) -> HTTPException:
    return HTTPException(status_code=exc.status, detail=str(exc))


def _sample_file(p: Any, sample: str) -> tuple[str, bytes]:
    """Jeu de démonstration : `demo` = celui de l'exemple d'origine du projet ; sinon nom d'un dossier de samples/."""
    if sample.lower() in ("demo", "true", "1"):
        d = st.demo_for(p)
        if d is None:
            raise HTTPException(status_code=404, detail="Aucun jeu de données de démonstration pour ce projet (il ne vient pas d'un exemple livré avec un jeu de démo).")
        sample, fname = d["sample"], d["file"]
    else:
        try:
            info = samples_mod.get_sample(sample)
        except KeyError:
            raise HTTPException(status_code=404, detail=f"Exemple « {sample} » introuvable.") from None
        demo = [f for f in info["data"] if "demo" in f.lower()] or info["data"]
        if not demo:
            raise HTTPException(status_code=404, detail=f"L'exemple « {sample} » n'a pas de fichier de données.")
        fname = demo[0]
    return fname, (samples_mod.get_sample(sample)["dir"] / fname).read_bytes()


def _loc(s: dict[str, Any]) -> dict[str, Any]:
    """Notes d'inférence dans la langue de l'interface (le texte est stocké en français)."""
    if s.get("inference") and s["inference"].get("notes"):
        s["inference"] = {**s["inference"], "notes": localize.tr_deep(s["inference"]["notes"], localize.ui_lang())}
    return s


@router.get("/stats")
def stats(pid: str) -> Any:
    p = load_project(pid)
    try:
        return _loc(st.stats(pid, p))
    except st.StoreError as exc:
        raise _err(exc) from None


@router.post("/load")
def load(pid: str, file: Optional[UploadFile] = File(None), sample: Optional[str] = Form(None),
         inference: Optional[str] = Form(None)) -> Any:
    """Charge un fichier (Turtle, N-Triples, JSON-LD, RDF/XML) ou un échantillon de démonstration (`sample=demo`).
    Sans fichier ni échantillon : resynchronise l'ontologie et les individus du projet. `inference` : none | rdfs | owlrl | both
    (absent = conserver le réglage actuel)."""
    p = load_project(pid)
    inference = inference or None
    try:
        if file is not None and file.filename:
            cap = st.limits()["max_upload_mb"] * 1024 * 1024
            raw = file.file.read(cap + 1)
            return _loc(st.load_data(pid, p, raw, file.filename, inference=inference))
        if sample:
            fname, raw = _sample_file(p, sample)
            return _loc(st.load_data(pid, p, raw, fname, source="sample", inference=inference))
        return _loc(st.refresh(pid, p, inference))
    except st.StoreError as exc:
        raise _err(exc) from None


@router.delete("")
def clear(pid: str) -> Any:
    p = load_project(pid)
    st.clear(pid)
    return _loc(st.stats(pid, p))


@router.post("/validate")
def validate(pid: str, body: Optional[dict[str, Any]] = Body(None)) -> Any:
    """Valide le contenu du triplestore (individus + données importées, sans la TBox) contre les shapes SHACL du projet."""
    p = load_project(pid)
    body = body or {}
    inference = body.get("inference") or "none"
    try:
        st.ensure(pid, p)
    except st.StoreError as exc:
        raise _err(exc) from None
    graphs = (st.G_INDIVIDUALS, *st.data_graphs(pid))
    if body.get("include_inferred"):
        graphs = (*graphs, st.G_INFERRED)
    try:
        g = st.to_rdflib(pid, graphs, st.limits()["max_validation_triples"])
    except st.StoreError as exc:
        raise _err(exc) from None
    report = service("shacl.validate", "validate")(g, p.shapes, p.onto, None, inference)
    out = dump(report)
    out["validated_triples"] = len(g)
    if not len(g):
        out.setdefault("warnings", []).append("Le triplestore local ne contient encore aucune donnée à valider (chargez un fichier ou les données de démonstration).")
    lg = localize.ui_lang()
    out["warnings"] = localize.tr_deep(out.get("warnings", []), lg)
    return out

