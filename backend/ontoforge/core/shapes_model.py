"""ShapesModel — pivot SHACL d'OntoForge (contrat partagé).

Couvre SHACL Core. Les contraintes SHACL-SPARQL sont conservées brutes (`sparql`) et signalées.
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

from .onto_model import LiteralValue

Severity = Literal["Violation", "Warning", "Info"]
NodeKind = Literal["IRI", "BlankNode", "Literal", "BlankNodeOrIRI", "BlankNodeOrLiteral", "IRIOrLiteral"]


class Path(BaseModel):
    """Chemin SHACL. kind='predicate' → iri ; 'inverse'|'zeroOrMore'|'oneOrMore'|'zeroOrOne' → args[0] ;
    'sequence'|'alternative' → args."""
    kind: Literal["predicate", "inverse", "sequence", "alternative", "zeroOrMore", "oneOrMore", "zeroOrOne"]
    iri: Optional[str] = None
    args: list["Path"] = Field(default_factory=list)


class QualifiedShape(BaseModel):
    shape: str  # IRI ou id de shape
    min_count: Optional[int] = None
    max_count: Optional[int] = None
    disjoint: bool = False


class Constraints(BaseModel):
    """Contraintes partagées entre NodeShape et PropertyShape."""
    class_: list[str] = Field(default_factory=list, alias="class")
    datatype: Optional[str] = None
    node_kind: Optional[NodeKind] = None
    node: list[str] = Field(default_factory=list)  # sh:node → shapes
    in_: list[LiteralValue | str] = Field(default_factory=list, alias="in")
    has_value: list[LiteralValue | str] = Field(default_factory=list)
    pattern: Optional[str] = None
    flags: Optional[str] = None
    min_length: Optional[int] = None
    max_length: Optional[int] = None
    min_inclusive: Optional[str] = None
    max_inclusive: Optional[str] = None
    min_exclusive: Optional[str] = None
    max_exclusive: Optional[str] = None
    language_in: list[str] = Field(default_factory=list)
    and_: list[str] = Field(default_factory=list, alias="and")
    or_: list[str] = Field(default_factory=list, alias="or")
    xone: list[str] = Field(default_factory=list)
    not_: list[str] = Field(default_factory=list, alias="not")
    sparql: list[str] = Field(default_factory=list)  # SHACL-SPARQL brut
    severity: Severity = "Violation"
    messages: dict[str, str] = Field(default_factory=dict)  # lang → message
    deactivated: bool = False

    model_config = {"populate_by_name": True}


class PropertyShape(Constraints):
    id: str  # IRI ou id de blank node stable
    path: Path
    names: dict[str, str] = Field(default_factory=dict)
    descriptions: dict[str, str] = Field(default_factory=dict)
    min_count: Optional[int] = None
    max_count: Optional[int] = None
    unique_lang: bool = False
    equals: list[str] = Field(default_factory=list)
    disjoint: list[str] = Field(default_factory=list)
    less_than: list[str] = Field(default_factory=list)
    less_than_or_equals: list[str] = Field(default_factory=list)
    qualified: list[QualifiedShape] = Field(default_factory=list)
    order: Optional[float] = None
    group: Optional[str] = None
    default_value: Optional[LiteralValue | str] = None


class Targets(BaseModel):
    target_class: list[str] = Field(default_factory=list)  # inclut la cible implicite (shape qui est aussi une classe)
    target_node: list[str] = Field(default_factory=list)
    target_subjects_of: list[str] = Field(default_factory=list)
    target_objects_of: list[str] = Field(default_factory=list)


class NodeShape(Constraints):
    id: str
    targets: Targets = Field(default_factory=Targets)
    properties: list[PropertyShape] = Field(default_factory=list)
    closed: bool = False
    ignored_properties: list[str] = Field(default_factory=list)
    labels: dict[str, str] = Field(default_factory=dict)


class ShapesModel(BaseModel):
    shapes: dict[str, NodeShape] = Field(default_factory=dict)
    property_shapes: dict[str, PropertyShape] = Field(default_factory=dict)  # property shapes autonomes (référencées)
    prefixes: dict[str, str] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


Path.model_rebuild()
