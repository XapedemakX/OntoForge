"""PGModel — pivot property graph d'OntoForge (contrat partagé) + constats et décisions d'arbitrage."""
from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

Target = Literal["curiosity", "neo4j"]
Severity = Literal["auto", "review", "lost", "info"]  # info (D-L9-02) : constat informatif, jamais compté ni arbitré
PGType = Literal["String", "Integer", "Float", "Decimal", "Boolean", "Date", "DateTime", "LocalDateTime", "Time", "Duration"]
Card = Literal["0..1", "1", "0..*", "1..*"]


class PGProperty(BaseModel):
    name: str
    type: PGType = "String"
    is_list: bool = False  # propriété multivaluée (tableau)
    required: bool = False
    unique: bool = False
    indexed: bool = False
    source: Optional[str] = None  # IRI OWL / id de shape d'origine
    description: Optional[str] = None
    enum: list[str] = Field(default_factory=list)
    default: Optional[Any] = None
    pattern: Optional[str] = None
    lang: Optional[str] = None  # propriété dédiée à une langue (label_fr)
    note: Optional[str] = None


class NodeType(BaseModel):
    name: str
    labels: list[str] = Field(default_factory=list)  # labels[0] = principal ; Curiosity : un seul
    source: list[str] = Field(default_factory=list)  # classes OWL fusionnées dans ce type
    key: list[str] = Field(default_factory=list)  # noms de propriétés formant la clé
    properties: list[PGProperty] = Field(default_factory=list)
    description: Optional[str] = None
    icon: Optional[str] = None  # D-L9-02 : icône Font Awesome (« fa-car »), reprise de Project.view.icons
    abstract: bool = False
    discriminator: Optional[str] = None  # propriété portant le sous-type (héritage aplati)
    discriminator_values: list[str] = Field(default_factory=list)


class Cardinality(BaseModel):
    out: Card = "0..*"
    in_: Card = Field("0..*", alias="in")
    model_config = {"populate_by_name": True}


class EdgeType(BaseModel):
    name: str
    from_: str = Field(alias="from")  # nom de NodeType
    to: str
    reverse: Optional[str] = None  # Curiosity : toujours renseigné
    source: Optional[str] = None
    description: Optional[str] = None
    properties: list[PGProperty] = Field(default_factory=list)  # toujours vide pour Curiosity
    cardinality: Cardinality = Field(default_factory=Cardinality)
    directed: bool = True
    symmetric: bool = False
    derived: bool = False  # relation matérialisée (fermeture transitive, chaîne, super-propriété)
    note: Optional[str] = None
    model_config = {"populate_by_name": True}


ValidationKind = Literal["cardinality", "existence", "disjoint", "allValuesFrom", "enum", "irreflexive",
                         "asymmetric", "functional", "hasValue", "pattern", "range", "closed", "other"]


class Validation(BaseModel):
    id: str
    kind: ValidationKind
    node_type: Optional[str] = None
    edge_type: Optional[str] = None
    property: Optional[str] = None
    params: dict[str, Any] = Field(default_factory=dict)  # min, max, targets, values, pattern, ...
    description: str
    source: Optional[str] = None
    severity: Literal["Violation", "Warning", "Info"] = "Violation"


MaterializationKind = Literal["transitiveClosure", "propertyChain", "superProperty", "classification", "inverse",
                              "symmetric", "sameAs"]


class Materialization(BaseModel):
    id: str
    kind: MaterializationKind
    edge_type: Optional[str] = None
    chain: list[str] = Field(default_factory=list)
    parent: Optional[str] = None
    node_type: Optional[str] = None
    definition: Optional[str] = None  # texte lisible (ex. définition de classe OWL)
    description: str
    source: Optional[str] = None


class Option(BaseModel):
    id: str
    label: str
    impact: str  # ce que l'on perd / gagne
    recommended_for: list[Target] = Field(default_factory=list)


class Finding(BaseModel):
    id: str  # stable : f"{rule}:{subject}" (+ suffixe) — sert de clé aux décisions
    rule: str  # ex. C02
    severity: Severity
    title: str
    detail: str
    subject: str  # IRI concernée
    related: list[str] = Field(default_factory=list)
    options: list[Option] = Field(default_factory=list)
    recommended: Optional[str] = None  # option id pour la cible courante
    chosen: Optional[str] = None  # option id décidée par l'humain (None = non arbitré)
    rationale: Optional[str] = None  # justification de la recommandation


class PGMeta(BaseModel):
    name: str = ""
    iri: Optional[str] = None
    generated_at: Optional[str] = None
    ontoforge_version: str = "0.1.0"


class PGModel(BaseModel):
    target: Target
    meta: PGMeta = Field(default_factory=PGMeta)
    node_types: dict[str, NodeType] = Field(default_factory=dict)
    edge_types: list[EdgeType] = Field(default_factory=list)
    validations: list[Validation] = Field(default_factory=list)
    materializations: list[Materialization] = Field(default_factory=list)
    findings: list[Finding] = Field(default_factory=list)
    decisions: dict[str, str] = Field(default_factory=dict)  # finding id → option id
    model_config = {"populate_by_name": True}

    def summary(self) -> dict[str, int]:
        out = {"auto": 0, "review": 0, "lost": 0, "decided": 0, "pending": 0}
        for f in self.findings:
            if f.severity == "info":
                continue
            out[f.severity] += 1
            if f.severity != "auto":
                out["decided" if f.chosen else "pending"] += 1
        return out
