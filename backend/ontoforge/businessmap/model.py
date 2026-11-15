"""Modèle persistant de la carte métier (un par projet et par source : ``ontology`` ou ``target``).

Ne contient que ce que l'humain a décidé ou ce qui est mis en cache : le reste (arêtes, rôles déduits, effectifs,
rectangles de zone) est recalculé à chaque lecture.
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

SOURCES = ("ontology", "target")

BUILTIN_ROLES = ("main", "component", "hub", "lookup", "context", "reference", "document", "settings")
# ids d'une version précédente de la carte : lus comme leur équivalent actuel (migration douce des rôles enregistrés)
LEGACY_ROLES = {"issue": "main", "detail": "component", "key": "hub", "classifier": "lookup", "catalogue": "reference",
                "knowledge": "document", "config": "settings"}


def canonical_role(role: Optional[str]) -> Optional[str]:
    """Rôle enregistré lu avec ses anciens ids ramenés au jeu actuel ; un rôle libre (texte de l'humain) reste tel quel."""
    if not role:
        return None
    return LEGACY_ROLES.get(role, role)

EDGE_STYLES = ("scored", "gate", "read", "context", "context_off", "grouped", "disabled", "both", "mention", "oneway")


class Zone(BaseModel):
    id: str
    title: str
    subtitle: str = ""
    color: str = "#e8eefc"
    members: list[str] = Field(default_factory=list)


class Frame(BaseModel):
    id: str
    title: str = ""
    members: list[str] = Field(default_factory=list)
    note: str = ""


class Scenario(BaseModel):
    id: str
    name: str
    description: str = ""
    edge_styles: dict[str, str] = Field(default_factory=dict)  # id d'arête → style (EDGE_STYLES)
    nodes: list[str] = Field(default_factory=list)  # nœuds mis en avant par le scénario


class XY(BaseModel):
    x: float
    y: float


class BusinessMapState(BaseModel):
    zones: list[Zone] = Field(default_factory=list)
    roles: dict[str, str] = Field(default_factory=dict)  # surcharges manuelles : id de nœud → rôle (builtin ou libre)
    role_colors: dict[str, str] = Field(default_factory=dict)  # rôle → couleur de légende (surcharge)
    faded: list[str] = Field(default_factory=list)
    pinned: list[str] = Field(default_factory=list)
    positions: dict[str, XY] = Field(default_factory=dict)
    frames: list[Frame] = Field(default_factory=list)
    scenarios: list[Scenario] = Field(default_factory=list)
    title: Optional[str] = None  # titre de la carte (défaut : nom du projet)
    generated: bool = False  # vrai tant que la carte est la proposition initiale, jamais enregistrée par l'humain
    updated_at: Optional[str] = None
