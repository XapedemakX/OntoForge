"""Stockage fichier des projets OntoForge.

Disposition : ``$ONTOFORGE_DATA/projects/<id>/`` (défaut ``./data``) contenant
``project.json`` (Project pydantic, source de vérité), ``decisions.json`` (copie lisible des arbitrages)
et, quand les modules d'export existent, ``onto.ttl`` / ``shapes.ttl`` réécrits à chaque sauvegarde.
Écritures atomiques (fichier temporaire + ``os.replace``).
"""
from __future__ import annotations

import json
import logging
import os
import re
import shutil
import tempfile
import unicodedata
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .. import fsutil
from ..core.project import Project

log = logging.getLogger(__name__)

ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,80}$")


class ProjectNotFound(KeyError):
    """Projet inconnu (ou identifiant invalide)."""


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def data_dir() -> Path:
    return Path(os.environ.get("ONTOFORGE_DATA", "./data"))


def projects_dir() -> Path:
    return data_dir() / "projects"


def slugify(text: str, max_len: int = 40) -> str:
    norm = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii").lower()
    slug = re.sub(r"[^a-z0-9]+", "-", norm).strip("-")[:max_len].strip("-")
    return slug or "projet"


def new_id(name: str) -> str:
    return f"{slugify(name)}-{uuid.uuid4().hex[:6]}"


def project_dir(project_id: str) -> Path:
    if not ID_RE.match(project_id or ""):
        raise ProjectNotFound(project_id)
    return projects_dir() / project_id


def _atomic_write(path: Path, content: str | bytes) -> None:
    """Écriture atomique (fichier temporaire + renommage), compatible avec un montage Cloud Storage FUSE : voir ``fsutil``."""
    fsutil.atomic_write(path, content)


# ---- API du module (CONTRACTS.md §1) -------------------------------------------------------

def list_projects() -> list[Project]:
    root = projects_dir()
    if not root.is_dir():
        return []
    out: list[Project] = []
    for d in sorted(root.iterdir()):
        pj = d / "project.json"
        if d.is_dir() and pj.is_file():
            try:
                out.append(Project.model_validate_json(pj.read_text(encoding="utf-8")))
            except Exception as exc:  # projet corrompu : on le signale sans casser la liste
                log.warning("project.json illisible dans %s : %s", d, exc)
    out.sort(key=lambda p: p.updated_at, reverse=True)
    return out


def get(project_id: str) -> Project:
    pj = project_dir(project_id) / "project.json"
    if not pj.is_file():
        raise ProjectNotFound(project_id)
    return Project.model_validate_json(pj.read_text(encoding="utf-8"))


def exists(project_id: str) -> bool:
    try:
        return (project_dir(project_id) / "project.json").is_file()
    except ProjectNotFound:
        return False


def create(name: str, description: str = "", **fields) -> Project:
    """Construit un nouveau projet (non sauvegardé) avec id et horodatages."""
    ts = now_iso()
    pid = new_id(name)
    while exists(pid):
        pid = new_id(name)
    return Project(id=pid, name=name, description=description, created_at=ts, updated_at=ts, **fields)


def save(project: Project, touch: bool = True) -> Project:
    d = project_dir(project.id)
    if touch:
        project.updated_at = now_iso()
    _atomic_write(d / "project.json", project.model_dump_json(by_alias=True, indent=2))
    _atomic_write(d / "decisions.json", json.dumps(project.decisions, indent=2, ensure_ascii=False))
    _export_side_files(project, d)
    return project


def delete(project_id: str) -> Project:
    p = get(project_id)
    shutil.rmtree(project_dir(project_id))
    try:  # triplestore hors du dossier du projet (ONTOFORGE_LOCAL_STORE_DIR) : nettoyage au mieux
        from ..localstore import store as _ls
        _ls.purge(project_id)
    except Exception:  # noqa: BLE001
        pass
    return p


def write_file(project_id: str, name: str, content: str | bytes) -> Path:
    """Fichier annexe du projet (ex. ``data.ttl`` d'un exemple)."""
    if "/" in name or "\\" in name or name.startswith("."):
        raise ValueError(f"nom de fichier invalide : {name}")
    path = project_dir(project_id) / name
    _atomic_write(path, content)
    return path


def read_file(project_id: str, name: str) -> Optional[str]:
    path = project_dir(project_id) / name
    return path.read_text(encoding="utf-8") if path.is_file() else None


def _export_side_files(project: Project, d: Path) -> None:
    """onto.ttl / shapes.ttl : import paresseux, ignoré si le module d'export n'existe pas encore."""
    try:
        from ..io.rdf_export import serialize
    except ImportError:
        serialize = None
    if serialize is not None:
        try:
            _atomic_write(d / "onto.ttl", serialize(project.onto, "turtle"))
        except Exception as exc:
            log.warning("export onto.ttl échoué pour %s : %s", project.id, exc)
    try:
        from ..shacl.export_shapes import serialize_shapes
    except ImportError:
        serialize_shapes = None
    if serialize_shapes is not None:
        try:
            _atomic_write(d / "shapes.ttl", serialize_shapes(project.shapes, "turtle"))
        except Exception as exc:
            log.warning("export shapes.ttl échoué pour %s : %s", project.id, exc)
