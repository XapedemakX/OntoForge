"""Projet OntoForge : ontologie + shapes + décisions d'arbitrage par cible."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from .onto_model import OntoModel, OntologyMeta
from .pg_model import Target
from .shapes_model import ShapesModel


class Position(BaseModel):
    x: float
    y: float


class ProjectView(BaseModel):
    """État d'affichage de l'éditeur graphique (L9). Aucun générateur n'en dépend."""
    icons: dict[str, str] = Field(default_factory=dict)  # IRI d'entité → "fa-..." (Font Awesome)
    positions: dict[str, Position] = Field(default_factory=dict)
    collapsed: list[str] = Field(default_factory=list)


class Perimeter(BaseModel):
    """Sous-ensemble de l'ontologie à analyser / générer (repris des « configs » d'ontoSparq)."""
    id: str
    name: str
    description: str = ""
    classes: list[str] = Field(default_factory=list)
    properties: list[str] = Field(default_factory=list)  # vide = toutes les propriétés dont domaine et portée sont dans le périmètre
    include_descendants: bool = False


class GenerationRecord(BaseModel):
    """Trace d'une génération (GET /generate/{target}) : historique par projet, côté serveur."""
    target: Target
    perimeter: Optional[str] = None
    at: str
    files: list[str] = Field(default_factory=list)
    findings_summary: dict[str, int] = Field(default_factory=dict)  # auto / review / lost / pending
    project_updated_at: str = ""  # état du projet au moment de la génération (détection « obsolète »)


class Project(BaseModel):
    id: str
    name: str
    description: str = ""
    created_at: str
    updated_at: str
    target: Target = "curiosity"
    onto: OntoModel = Field(default_factory=lambda: OntoModel(meta=OntologyMeta(iri="https://w3id.org/ontoforge/new#")))
    shapes: ShapesModel = Field(default_factory=ShapesModel)
    decisions: dict[str, dict[str, str]] = Field(default_factory=lambda: {"curiosity": {}, "neo4j": {}})
    source_files: list[str] = Field(default_factory=list)
    notes: Optional[str] = None
    view: ProjectView = Field(default_factory=ProjectView)  # L9, rétrocompatible
    perimeters: list[Perimeter] = Field(default_factory=list)  # L9
    active_perimeter: Optional[str] = None  # L9 : état d'interface, n'influe pas sur analyze/generate
    generations: list[GenerationRecord] = Field(default_factory=list)  # L14, rétrocompatible
