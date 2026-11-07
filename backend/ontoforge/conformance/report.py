"""Modèle du rapport de conformité W3C (contrat : docs/CONTRACTS.md, conformance/profiles.py)."""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

PROFILE_NAMES = ("DL", "EL", "QL", "RL", "RDFS")
Level = Literal["error", "warning", "info"]


class Issue(BaseModel):
    level: Level
    code: str  # W01..W07 (conformité), BP01.. (bonnes pratiques)
    message: str  # français, une phrase
    subject: Optional[str] = None  # IRI concernée
    spec_ref: Optional[str] = None  # ex. « OWL 2 Structural Specification §11.2 »


class ReasonerInfo(BaseModel):
    used: str = "none"  # none | owlrl | owlrl+hermit
    consistent: Optional[bool] = None  # None = non évalué
    unsatisfiable: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class ConformanceReport(BaseModel):
    profiles: dict[str, bool] = Field(default_factory=lambda: {k: False for k in PROFILE_NAMES})
    profile_violations: dict[str, list[str]] = Field(default_factory=lambda: {k: [] for k in PROFILE_NAMES})
    issues: list[Issue] = Field(default_factory=list)
    reasoner: ReasonerInfo = Field(default_factory=ReasonerInfo)

    def codes(self) -> set[str]:
        return {i.code for i in self.issues}
