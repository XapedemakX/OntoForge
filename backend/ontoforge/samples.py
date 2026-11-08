"""Catalogue des exemples livrés (`samples/<nom>/`).

Convention par dossier : ``*-shapes.ttl`` = shapes SHACL, ``*-data.ttl`` = données d'instance,
autres ``*.ttl`` / ``*.owl`` / ``*.rdf`` / ``*.jsonld`` = ontologie. Un ``README.md`` (1re ligne ``# Titre``)
ou un ``title.txt`` donne le titre ; sinon le nom du dossier.
Racine : ``$ONTOFORGE_SAMPLES`` (Docker : ``/app/samples``), défaut ``<dépôt>/samples``.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

ONTO_EXT = (".ttl", ".owl", ".rdf", ".xml", ".jsonld", ".nt", ".n3", ".trig", ".omn")


def samples_root() -> Path:
    env = os.environ.get("ONTOFORGE_SAMPLES")
    if env:
        return Path(env)
    return Path(__file__).resolve().parents[2] / "samples"


def _classify(name: str) -> Optional[str]:
    low = name.lower()
    stem = low.rsplit(".", 1)[0]
    if not low.endswith(ONTO_EXT):
        return None
    if stem.endswith("-nondl"):  # fixture de test de conformité, pas un exemple utilisateur
        return None
    if stem.endswith("-shapes") or stem.endswith("_shapes"):
        return "shapes"
    if stem.endswith("-data") or stem.endswith("_data"):
        return "data"
    return "ontology"


def _title(d: Path) -> str:
    for fname in ("title.txt", "README.md"):
        f = d / fname
        if f.is_file():
            for line in f.read_text(encoding="utf-8").splitlines():
                line = line.strip().lstrip("#").strip()
                if line:
                    return line
    return d.name.replace("-", " ").replace("_", " ").capitalize()


def describe(d: Path) -> dict:
    files = sorted(f.name for f in d.iterdir() if f.is_file() and not f.name.startswith("."))
    roles: dict[str, list[str]] = {"ontology": [], "shapes": [], "data": []}
    for f in files:
        role = _classify(f)
        if role:
            roles[role].append(f)
    # Turtle d'abord : c'est lui qui porte les préfixes d'origine (le RDF/XML sérialisé par rdflib n'en garde que les standards)
    for k in roles:
        roles[k].sort(key=lambda n: (0 if n.lower().endswith(".ttl") else 1, n))
    return {"name": d.name, "title": _title(d), "files": files, **roles}


def list_samples() -> list[dict]:
    root = samples_root()
    if not root.is_dir():
        return []
    return [describe(d) for d in sorted(root.iterdir()) if d.is_dir() and not d.name.startswith(".")]


def get_sample(name: str) -> dict:
    """Description + chemins absolus ; KeyError si inconnu."""
    if not name or "/" in name or "\\" in name or name.startswith("."):
        raise KeyError(name)
    d = samples_root() / name
    if not d.is_dir():
        raise KeyError(name)
    info = describe(d)
    info["dir"] = d
    return info
