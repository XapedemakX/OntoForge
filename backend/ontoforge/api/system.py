"""Santé et exemples."""
from __future__ import annotations

from fastapi import APIRouter

from .. import samples as samples_mod

router = APIRouter(prefix="/api", tags=["system"])
VERSION = "0.1.0"


@router.get("/health")
def health() -> dict:
    return {"status": "ok", "version": VERSION}


@router.get("/samples")
def list_samples() -> list[dict]:
    return [{"name": s["name"], "title": s["title"], "files": s["files"],
             "ontology": s["ontology"], "shapes": s["shapes"], "data": s["data"]}
            for s in samples_mod.list_samples()]
