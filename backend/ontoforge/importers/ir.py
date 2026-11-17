"""Représentation intermédiaire commune aux trois importeurs (L48) : entités, propriétés, relations, avis.

Les importeurs (SQL, CSV, JSON Schema) produisent un :class:`Draft` ; ``builder.py`` le transforme en OntoModel + ShapesModel.
Aucune dépendance au réseau, aucun LLM.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

XSD = "http://www.w3.org/2001/XMLSchema#"


@dataclass
class Notice:
    """Avis destiné à l'humain. ``level`` : ``info`` (rien à faire), ``review`` (à arbitrer ou à vérifier), ``warning`` (perte ou doute)."""
    code: str
    level: str = "info"
    params: dict[str, Any] = field(default_factory=dict)
    subject: Optional[str] = None


@dataclass
class Prop:
    """Propriété de données : ``key`` identifie la propriété dans l'entité (nom source), ``xsd`` est un nom court de datatype (``string``)."""
    key: str
    xsd: str = "string"
    required: bool = False
    many: bool = False
    enum: Optional[list[str]] = None
    comment: str = ""
    src_type: str = ""
    min_count: Optional[int] = None
    max_count: Optional[int] = None
    facets: dict[str, Any] = field(default_factory=dict)   # min_length, max_length, pattern, min_inclusive, max_inclusive, min_exclusive, max_exclusive
    degraded: Optional[str] = None                         # datatype d'origine quand il a été remplacé (xsd:date → dateTime)
    hint: str = ""                                         # nom local souhaité (camelCase) ; sinon camel(key)


@dataclass
class Rel:
    """Relation vers une autre entité (clé étrangère, ``$ref``, table d'association)."""
    key: str
    target: str                       # clé d'entité
    required: bool = False
    many: bool = False
    comment: str = ""
    source: str = ""                  # « colonne orders.customer_id », « table d'association enrollments »…
    union: list[str] = field(default_factory=list)   # portée en union (JSON Schema oneOf/anyOf de références)
    min_count: Optional[int] = None
    max_count: Optional[int] = None
    composite: bool = False
    hint: str = ""                    # nom local souhaité (hasCustomer) ; sinon « has » + clé


@dataclass
class Entity:
    key: str                          # identifiant interne (nom de table, de fichier, de définition)
    name: str                         # nom de classe souhaité (PascalCase)
    comment: str = ""
    source: str = ""                  # « table customers », « fichier clients.csv », « #/$defs/Customer »
    props: list[Prop] = field(default_factory=list)
    rels: list[Rel] = field(default_factory=list)
    keys: list[list[str]] = field(default_factory=list)      # clés (clé primaire d'abord) : listes de Prop.key / Rel.key
    parents: list[str] = field(default_factory=list)         # clés d'entités parentes (sous-classe)
    kind: str = "class"               # class | reified | stub
    assumed_key: bool = False         # clé supposée (colonne « id » d'un CSV ou d'un JSON Schema), à confirmer

    def prop(self, key: str) -> Optional[Prop]:
        return next((p for p in self.props if p.key == key), None)

    def rel(self, key: str) -> Optional[Rel]:
        return next((r for r in self.rels if r.key == key), None)


@dataclass
class Decision:
    """Point à arbitrer par l'humain : un identifiant stable, les choix possibles, le choix par défaut et celui retenu."""
    id: str
    type: str                         # association | subclass | reference | key
    subject: str
    options: list[str]
    default: str
    chosen: str
    params: dict[str, Any] = field(default_factory=dict)


@dataclass
class Draft:
    kind: str                         # sql | csv | json-schema
    entities: dict[str, Entity] = field(default_factory=dict)
    notices: list[Notice] = field(default_factory=list)
    ignored: dict[str, dict[str, Any]] = field(default_factory=dict)
    decisions: list[Decision] = field(default_factory=list)
    files: list[str] = field(default_factory=list)
    dialect: Optional[str] = None

    def notice(self, code: str, level: str = "info", subject: Optional[str] = None, **params: Any) -> None:
        from .limits import MAX_NOTICES
        if code == "degraded_type" and params.get("xsd") == "dateTime" and str(params.get("type", "")).strip().lower() == "date":
            code = "degraded_date"   # date -> dateTime : pas de perte de précision, mais les valeurs doivent être complétées
        if len(self.notices) < MAX_NOTICES:
            self.notices.append(Notice(code, level, params, subject))
        elif len(self.notices) == MAX_NOTICES:
            self.notices.append(Notice("too_many_notices", "warning", {"n": MAX_NOTICES}))

    def ignore(self, category: str, example: str = "") -> None:
        d = self.ignored.setdefault(category, {"count": 0, "examples": []})
        d["count"] += 1
        if example and len(d["examples"]) < 5 and example not in d["examples"]:
            d["examples"].append(example[:160])
