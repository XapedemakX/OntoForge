"""Versions publiées de l'ontologie et en-tête (L49, CONTRACTS.md §19).

``POST /projects/{pid}/releases`` enregistre une version : opération d'édition journalisée (``owl:versionInfo``,
``owl:versionIRI``, ``owl:priorVersion``, ``dcterms:modified``) puis entrée dans ``releases.json`` avec la note de version."""
from __future__ import annotations

import datetime as _dt
from typing import Any, Optional

from fastapi import APIRouter, Body, HTTPException
from pydantic import BaseModel

from .. import localize
from ..conformance import practices
from ..editing import history
from ..editing import ops as ops_mod
from ..projects import releases, store
from ._common import dump, load_project

router = APIRouter(prefix="/api", tags=["releases"])


@router.get("/projects/{pid}/metadata")
def get_metadata(pid: str) -> dict[str, Any]:
    """En-tête de l'ontologie (titre, version, dates, auteurs, contributeurs, vocabulaires, objectif, mots-clés, sources, licence)
    et score de complétude de l'en-tête. La modification passe par ``POST /ops`` (``set_annotations``, ``set_version_iri``)."""
    p = load_project(pid)
    return {"header": practices.header(p.onto), "card": practices.header_card(p.onto),
            "fields": {k: {"property": v[0], "iri": v[1], "multi": v[2], "by_lang": v[3]} for k, v in practices.HEADER_FIELDS.items()}}


@router.get("/projects/{pid}/releases")
def list_releases(pid: str) -> dict[str, Any]:
    load_project(pid)
    rs = releases.history(pid)
    return {"releases": [{k: v for k, v in r.items() if k not in ("changes", "note")} for r in reversed(rs)]}


@router.get("/projects/{pid}/releases/preview")
def preview(pid: str) -> dict[str, Any]:
    p = load_project(pid)
    return releases.preview(pid, p.onto, localize.ui_lang())


@router.get("/projects/{pid}/releases/{version}")
def get_release(pid: str, version: str) -> dict[str, Any]:
    load_project(pid)
    r = releases.get(pid, version)
    if r is None:
        raise HTTPException(status_code=404, detail=f"Version « {version} » introuvable")
    return r


class ReleaseRequest(BaseModel):
    version: Optional[str] = None  # défaut : version proposée par le diff
    note: Optional[str] = None  # défaut : note générée


@router.post("/projects/{pid}/releases", status_code=201)
def create_release(pid: str, body: ReleaseRequest = Body(default_factory=ReleaseRequest)) -> dict[str, Any]:
    lang = localize.ui_lang()
    with history.lock():
        p = load_project(pid, "write")
        if not p.onto.meta.iri:
            raise HTTPException(status_code=422, detail="L'ontologie n'a pas d'IRI : impossible de calculer owl:versionIRI")
        prev = releases.last(pid)
        pv = releases.preview(pid, p.onto, lang)
        try:
            version = releases.check_version(body.version or pv["proposed"], pv["previous"])
        except releases.ReleaseError as exc:
            raise HTTPException(status_code=422, detail=localize.tr(str(exc), lang)) from None
        note = body.note if body.note and body.note.strip() else releases.release_note(
            version, pv["changes"], previous=pv["previous"], proposed=pv["proposed"], level=pv["level"] or "patch", onto=p.onto, lang=lang)
        if len(note) > 50_000:
            raise HTTPException(status_code=422, detail="Note de version trop longue (50 000 caractères au plus)")
        iri = p.onto.meta.iri
        viri = releases.version_iri_for(iri, version)
        now = _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0)
        ops = [{"op": "set_annotations", "iri": iri, "property": practices.VERSION_INFO, "values": [version]},
               {"op": "set_version_iri", "version_iri": viri},
               {"op": "set_annotations", "iri": iri, "property": practices.DCT + "modified", "values": [now.isoformat()]}]
        if prev and prev.get("version_iri") and prev["version_iri"] != viri:
            ops.append({"op": "set_annotations", "iri": iri, "property": practices.PRIOR_VERSION, "values": [prev["version_iri"]]})
        res = ops_mod.apply_ops(p, ops)
        if res.errors:
            raise HTTPException(status_code=422, detail=localize.tr("; ".join(e["message"] for e in res.errors), lang))
        from ..collab import access
        ctx = access.current()
        downgraded = bool(pv["previous"] and pv["level"]) and releases.level_rank(version, pv["previous"]) < releases.LEVELS.index(pv["level"])
        record = {"version": version, "at": now.isoformat(), "by": ctx.identity.user if ctx else None, "previous": pv["previous"],
                  "proposed": pv["proposed"], "level": pv["level"], "counts": pv["counts"], "version_iri": viri,
                  "changes": pv["changes"], "note": note, **({"downgraded": True} if downgraded else {})}
        # releases.json d'abord : si l'écriture du projet échoue ensuite, l'entrée est retirée (jamais un projet versionné sans entrée)
        releases.append(pid, record, p.onto)
        try:
            store.save(p)
        except Exception:
            releases.drop_last(pid, version)
            raise
        if res.changed_keys:
            history.record(pid, releases.history_label(version), res.before)
        return {"release": record, "project": dump(p)}
