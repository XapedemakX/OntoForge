"""OntoModel — pivot ontologique d'OntoForge (contrat partagé, ne change que par décision tracée).

Représentation d'une ontologie OWL 2 / RDFS orientée transposition : les axiomes « fréquents » sont
structurés en champs dédiés, les expressions de classes arbitraires sont gardées en arbre (ClassExpr),
et tout ce qui n'est pas modélisé est conservé dans `unmapped` pour être signalé, jamais perdu en silence.
Toutes les références sont des IRIs absolues.
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

XSD = "http://www.w3.org/2001/XMLSchema#"
RDF = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
RDFS = "http://www.w3.org/2000/01/rdf-schema#"
OWL = "http://www.w3.org/2002/07/owl#"

LangText = dict[str, str]
"""Texte multilingue : {"fr": "Véhicule", "en": "Vehicle", "": "sans langue"}."""

Characteristic = Literal[
    "functional", "inverseFunctional", "transitive", "symmetric", "asymmetric", "reflexive", "irreflexive"
]
RestrictionKind = Literal["some", "only", "min", "max", "exactly", "value", "self"]


class LiteralValue(BaseModel):
    value: str
    datatype: Optional[str] = None  # IRI xsd:… ; None = xsd:string / plain
    lang: Optional[str] = None


class Annotation(BaseModel):
    property: str
    value: str  # IRI ou forme lexicale
    is_iri: bool = False
    datatype: Optional[str] = None
    lang: Optional[str] = None


class ClassExpr(BaseModel):
    """Expression de classe OWL 2 (arbre).

    op='named'     → iri
    op='and'|'or'  → args
    op='not'       → args[0]
    op='oneOf'     → individuals
    op restriction ('some','only','min','max','exactly','value','self') → property, inverse, n, filler | data_range, value
    """
    op: Literal["named", "and", "or", "not", "oneOf", "some", "only", "min", "max", "exactly", "value", "self"]
    iri: Optional[str] = None
    args: list["ClassExpr"] = Field(default_factory=list)
    individuals: list[str] = Field(default_factory=list)
    property: Optional[str] = None
    inverse: bool = False  # ObjectInverseOf(property)
    n: Optional[int] = None
    filler: Optional["ClassExpr"] = None  # classe qualifiante (object property)
    data_range: Optional[str] = None  # datatype IRI qualifiant (data property)
    value: Optional[LiteralValue | str] = None  # hasValue : individu (IRI) ou littéral


class Restriction(BaseModel):
    """Vue aplatie d'une restriction de superclasse anonyme (rdfs:subClassOf [owl:Restriction ...])."""
    property: str
    inverse: bool = False
    kind: RestrictionKind
    n: Optional[int] = None
    filler: Optional[str] = None  # IRI de classe ou de datatype ; None si non qualifiée ou filler complexe
    filler_expr: Optional[ClassExpr] = None  # quand le filler n'est pas nommé
    value: Optional[LiteralValue | str] = None


class Entity(BaseModel):
    iri: str
    labels: LangText = Field(default_factory=dict)
    comments: LangText = Field(default_factory=dict)
    annotations: list[Annotation] = Field(default_factory=list)  # skos:*, dcterms:*, annotations custom
    deprecated: bool = False


class OntClass(Entity):
    sub_class_of: list[str] = Field(default_factory=list)  # parents nommés
    restrictions: list[Restriction] = Field(default_factory=list)  # superclasses anonymes de type restriction
    super_expressions: list[ClassExpr] = Field(default_factory=list)  # autres superclasses anonymes (and/or/not/oneOf)
    equivalent_to: list[ClassExpr] = Field(default_factory=list)  # nommées (op=named) ou définitions
    disjoint_with: list[str] = Field(default_factory=list)
    disjoint_union_of: list[list[str]] = Field(default_factory=list)
    has_keys: list[list[str]] = Field(default_factory=list)  # owl:hasKey (une liste par axiome)
    one_of: Optional[list[str]] = None  # classe énumérée (owl:oneOf) — individus


class ObjectProperty(Entity):
    domain: list[str] = Field(default_factory=list)  # classes nommées (intersection si plusieurs axiomes)
    range: list[str] = Field(default_factory=list)
    domain_union: list[str] = Field(default_factory=list)  # rdfs:domain [owl:unionOf (...)]
    range_union: list[str] = Field(default_factory=list)
    domain_expr: Optional[ClassExpr] = None  # domaine complexe non réductible
    range_expr: Optional[ClassExpr] = None
    inverse_of: Optional[str] = None
    sub_property_of: list[str] = Field(default_factory=list)
    equivalent_to: list[str] = Field(default_factory=list)
    disjoint_with: list[str] = Field(default_factory=list)
    chains: list[list[str]] = Field(default_factory=list)  # owl:propertyChainAxiom
    characteristics: list[Characteristic] = Field(default_factory=list)


class DataRange(BaseModel):
    """Restriction de datatype : base + facettes (xsd:minInclusive, xsd:pattern…) ou énumération de littéraux."""
    base: Optional[str] = None
    facets: dict[str, str] = Field(default_factory=dict)  # IRI de facette → valeur lexicale
    one_of: list[LiteralValue] = Field(default_factory=list)
    union_of: list[str] = Field(default_factory=list)


class DatatypeProperty(Entity):
    domain: list[str] = Field(default_factory=list)
    domain_union: list[str] = Field(default_factory=list)
    domain_expr: Optional[ClassExpr] = None
    range: list[str] = Field(default_factory=list)  # IRIs de datatypes (xsd:…, rdf:langString, rdfs:Literal, custom)
    range_expr: Optional[DataRange] = None
    functional: bool = False
    sub_property_of: list[str] = Field(default_factory=list)
    equivalent_to: list[str] = Field(default_factory=list)
    disjoint_with: list[str] = Field(default_factory=list)


class AnnotationProperty(Entity):
    sub_property_of: list[str] = Field(default_factory=list)
    domain: list[str] = Field(default_factory=list)
    range: list[str] = Field(default_factory=list)


class DatatypeDef(Entity):
    """rdfs:Datatype déclaré dans l'ontologie (owl:equivalentClass → DataRange)."""
    definition: Optional[DataRange] = None


class Fact(BaseModel):
    property: str
    value: str  # IRI (is_iri) ou forme lexicale
    is_iri: bool = False
    datatype: Optional[str] = None
    lang: Optional[str] = None
    negative: bool = False  # owl:NegativePropertyAssertion


class Individual(Entity):
    types: list[str] = Field(default_factory=list)
    facts: list[Fact] = Field(default_factory=list)
    same_as: list[str] = Field(default_factory=list)
    different_from: list[str] = Field(default_factory=list)


class OntologyMeta(Entity):
    """iri = IRI de l'ontologie ; labels/comments/annotations = métadonnées de l'ontologie."""
    version_iri: Optional[str] = None
    imports: list[str] = Field(default_factory=list)
    prefixes: dict[str, str] = Field(default_factory=dict)


class UnmappedAxiom(BaseModel):
    """Triplets / axiomes lus mais non représentés dans le modèle : toujours remontés à l'utilisateur."""
    description: str
    triples: list[tuple[str, str, str]] = Field(default_factory=list)  # N-Triples abrégés
    subject: Optional[str] = None


class OntoModel(BaseModel):
    meta: OntologyMeta
    classes: dict[str, OntClass] = Field(default_factory=dict)
    object_properties: dict[str, ObjectProperty] = Field(default_factory=dict)
    datatype_properties: dict[str, DatatypeProperty] = Field(default_factory=dict)
    annotation_properties: dict[str, AnnotationProperty] = Field(default_factory=dict)
    datatypes: dict[str, DatatypeDef] = Field(default_factory=dict)
    individuals: dict[str, Individual] = Field(default_factory=dict)
    all_different: list[list[str]] = Field(default_factory=list)  # owl:AllDifferent
    unmapped: list[UnmappedAxiom] = Field(default_factory=list)

    # ---- helpers (lecture seule) -------------------------------------------------
    def label(self, iri: str, lang: str = "fr") -> str:
        for coll in (self.classes, self.object_properties, self.datatype_properties, self.annotation_properties,
                     self.individuals, self.datatypes):
            e = coll.get(iri)
            if e and e.labels:
                return e.labels.get(lang) or e.labels.get("en") or e.labels.get("") or next(iter(e.labels.values()))
        return local_name(iri)

    def ancestors(self, iri: str) -> list[str]:
        seen: list[str] = []
        stack = list(self.classes[iri].sub_class_of) if iri in self.classes else []
        while stack:
            p = stack.pop()
            if p in seen or p == OWL + "Thing":
                continue
            seen.append(p)
            if p in self.classes:
                stack.extend(self.classes[p].sub_class_of)
        return seen

    def children(self, iri: str) -> list[str]:
        return [c.iri for c in self.classes.values() if iri in c.sub_class_of]

    def descendants(self, iri: str) -> list[str]:
        out: list[str] = []
        stack = self.children(iri)
        while stack:
            c = stack.pop()
            if c not in out:
                out.append(c)
                stack.extend(self.children(c))
        return out


def local_name(iri: str) -> str:
    for sep in ("#", "/", ":"):
        if sep in iri:
            tail = iri.rsplit(sep, 1)[1]
            if tail:
                return tail
    return iri


ClassExpr.model_rebuild()
