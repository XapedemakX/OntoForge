"""Profil cible Neo4j 5 — déclaratif, lu par le moteur de mapping (mapping/engine.py).

Propriétaire : agent neo4j. Sources vérifiées le 2026-11-02 (cf. skills/neo4j-schema-design/SKILL.md) :
- https://neo4j.com/docs/cypher-manual/current/constraints/managing-constraints/
- https://neo4j.com/docs/cypher-manual/current/indexes/search-performance-indexes/managing-indexes/
- https://neo4j.com/docs/cypher-manual/current/indexes/semantic-indexes/full-text-indexes/

Le module ne dépend que de core/pg_model.py. Il expose :
CAPABILITIES, CAPABILITY_NOTES, PG_TO_CYPHER_TYPE, XSD_TYPE_MAP, map_xsd(), node_name(), edge_name(),
reverse_name(), prop_name(), RECOMMENDATIONS, options(), recommend().
"""
from __future__ import annotations

import re
from typing import Any, Optional

from ontoforge.core.pg_model import Option

TARGET = "neo4j"

# ---------------------------------------------------------------------------
# Capacités (mêmes clés que le profil Curiosity). Valeurs : bool, ou "native" | "enterprise" | "none".
# ---------------------------------------------------------------------------
CAPABILITIES: dict[str, Any] = {
    "multi_label": True,
    "edge_properties": True,
    "native_reverse_edges": False,
    "single_string_key": False,
    "composite_key": True,
    "unique_constraint": True,
    "existence_constraint": "enterprise",
    "type_constraint": "enterprise",
    "list_properties": True,
    "relationship_cardinality": False,
    "fulltext": True,
    "facets": False,
    # Clés complémentaires propres à Neo4j (le moteur peut les ignorer)
    "node_key": "enterprise",
    "relationship_key": "enterprise",
    "relationship_constraints": True,
    "decimal_type": False,
    "map_properties": False,
    "point_type": True,
    "min_version": "5.11",
}

CAPABILITY_NOTES: dict[str, str] = {
    "multi_label": "Un nœud porte N labels : l'héritage OWL (C02/C03) se traduit par :Vehicle:ElectricVehicle sans aplatir.",
    "edge_properties": "Les relations portent des propriétés : une classe de réification (R01) peut devenir une relation.",
    "native_reverse_edges": "Pas de type inverse déclaré : une relation est stockée dans un sens et traversée dans les deux "
                            "(MATCH (a)<-[:T]-(b)). owl:inverseOf (O04) = un seul type stocké.",
    "single_string_key": "Les clés peuvent être de tout type scalaire et composites.",
    "composite_key": "UNIQUE composite (Community) ou NODE KEY composite (Enterprise).",
    "unique_constraint": "REQUIRE n.p IS UNIQUE : Community et Enterprise, nœuds ; relations depuis 5.7.",
    "existence_constraint": "REQUIRE n.p IS NOT NULL : Enterprise uniquement (nœuds et relations), pas de composite.",
    "type_constraint": "REQUIRE n.p IS :: <TYPE> : Enterprise, depuis 5.9 ; LIST<T NOT NULL> depuis 5.10 ; unions depuis 5.11.",
    "list_properties": "Listes homogènes de scalaires, sans élément null ; pas de liste de listes ni de MAP.",
    "relationship_cardinality": "Aucune contrainte de cardinalité de relation : O09/O10 deviennent des requêtes de validation.",
    "fulltext": "CREATE FULLTEXT INDEX … ON EACH [...] (Lucene), multi-labels ; interrogé via db.index.fulltext.queryNodes.",
    "facets": "Pas de facettes natives : agrégations Cypher (count par valeur) ou nœuds de référence.",
    "node_key": "IS NODE KEY = unicité + existence, Enterprise uniquement.",
    "relationship_key": "IS RELATIONSHIP KEY, Enterprise, depuis 5.7.",
    "decimal_type": "Pas de type décimal : FLOAT (IEEE 754, perte) ou STRING (exact, non calculable) ou INTEGER en centimes.",
    "map_properties": "Une propriété ne peut pas être une MAP.",
    "min_version": "schema.cypher généré requiert Neo4j 5.11+ pour les contraintes de type sur listes/unions (Enterprise).",
}

# Type PG (pg_model.PGType) → type Cypher des contraintes IS :: <TYPE>
PG_TO_CYPHER_TYPE: dict[str, str] = {
    "String": "STRING",
    "Integer": "INTEGER",
    "Float": "FLOAT",
    "Decimal": "FLOAT",  # pas de décimal natif : repli FLOAT (ne devrait pas être émis par ce profil)
    "Boolean": "BOOLEAN",
    "Date": "DATE",
    "DateTime": "ZONED DATETIME",
    "LocalDateTime": "LOCAL DATETIME",
    "Time": "LOCAL TIME",
    "Duration": "DURATION",
}

# Type PG → fonction Cypher de conversion à l'ingestion (None = valeur JSON brute)
PG_TO_CYPHER_CAST: dict[str, Optional[str]] = {
    "String": None, "Integer": "toInteger", "Float": "toFloat", "Decimal": "toFloat", "Boolean": "toBoolean",
    "Date": "date", "DateTime": "datetime", "LocalDateTime": "localdatetime", "Time": "localtime",
    "Duration": "duration",
}

# ---------------------------------------------------------------------------
# Datatypes OWL 2 (OWL 2 Structural Spec §4 « datatype map ») + XSD 1.1 usuels → type PG.
# ---------------------------------------------------------------------------
XSD = "http://www.w3.org/2001/XMLSchema#"
RDF = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
RDFS = "http://www.w3.org/2000/01/rdf-schema#"
OWL = "http://www.w3.org/2002/07/owl#"


def _t(pg: str, lossy: bool = False, note: str = "", owl2: bool = True) -> dict[str, Any]:
    return {"type": pg, "lossy": lossy, "note": note, "owl2": owl2}


_INT64 = "INTEGER Neo4j = entier signé 64 bits : valeurs hors [-2^63, 2^63-1] refusées."
XSD_TYPE_MAP: dict[str, dict[str, Any]] = {
    # Numériques
    XSD + "decimal": _t("Float", True, "Pas de décimal Neo4j : FLOAT perd la précision (montants). "
                        "Perte signalée et à arbitrer (D-L13-01) ; alternatives : INTEGER en centimes ou STRING lexical."),
    XSD + "integer": _t("Integer", True, "xsd:integer non borné → " + _INT64),
    XSD + "nonNegativeInteger": _t("Integer", True, _INT64 + " Borne >= 0 → validation range."),
    XSD + "nonPositiveInteger": _t("Integer", True, _INT64 + " Borne <= 0 → validation range."),
    XSD + "positiveInteger": _t("Integer", True, _INT64 + " Borne > 0 → validation range."),
    XSD + "negativeInteger": _t("Integer", True, _INT64 + " Borne < 0 → validation range."),
    XSD + "long": _t("Integer"),
    XSD + "int": _t("Integer", False, "Bornes 32 bits non contrôlées (validation range si nécessaire)."),
    XSD + "short": _t("Integer", False, "Bornes 16 bits non contrôlées."),
    XSD + "byte": _t("Integer", False, "Bornes 8 bits non contrôlées."),
    XSD + "unsignedLong": _t("Integer", True, "unsignedLong > 2^63-1 non représentable."),
    XSD + "unsignedInt": _t("Integer"),
    XSD + "unsignedShort": _t("Integer"),
    XSD + "unsignedByte": _t("Integer"),
    XSD + "double": _t("Float"),
    XSD + "float": _t("Float", False, "Stocké en double précision (élargissement sans perte)."),
    OWL + "real": _t("Float", True, "owl:real (réels arbitraires) approché par FLOAT."),
    OWL + "rational": _t("Float", True, "owl:rational approché par FLOAT (ou STRING 'p/q')."),
    # Chaînes
    XSD + "string": _t("String"),
    XSD + "normalizedString": _t("String", False, "Normalisation des blancs non contrôlée (validation pattern)."),
    XSD + "token": _t("String", False, "Contrainte lexicale non contrôlée."),
    XSD + "language": _t("String", False, "Code BCP 47 non contrôlé (validation pattern)."),
    XSD + "Name": _t("String"),
    XSD + "NCName": _t("String"),
    XSD + "NMTOKEN": _t("String"),
    RDF + "PlainLiteral": _t("String", True, "Étiquette de langue perdue : une propriété par langue (D06)."),
    RDF + "langString": _t("String", True, "Étiquette de langue perdue : une propriété par langue (name_fr, name_en) (D06). Hors carte OWL 2 (W01) : tolérance seulement.", owl2=False),
    RDF + "XMLLiteral": _t("String", True, "Stocké en texte, structure XML non interrogeable."),
    RDFS + "Literal": _t("String", True, "Littéral non typé : STRING par défaut, type d'origine perdu."),
    # Booléen, binaire, URI
    XSD + "boolean": _t("Boolean"),
    XSD + "hexBinary": _t("String", True, "Binaire encodé en texte hexadécimal (ou LIST<INTEGER>)."),
    XSD + "base64Binary": _t("String", True, "Binaire encodé en texte base64."),
    XSD + "anyURI": _t("String", False, "URI en STRING ; si la cible est une ressource, préférer une relation."),
    # Temporels OWL 2
    XSD + "dateTime": _t("DateTime", False, "ZONED DATETIME si fuseau présent ; sans fuseau, Neo4j applique le fuseau "
                        "par défaut (db.temporal.timezone) — préférer LocalDateTime si les données sont sans fuseau."),
    XSD + "dateTimeStamp": _t("DateTime"),
    # Temporels XSD hors OWL 2 (fréquents)
    XSD + "date": _t("Date", False, "Fuseau éventuel de xsd:date perdu.", owl2=False),
    XSD + "time": _t("Time", True, "LOCAL TIME : fuseau éventuel perdu (ZONED TIME possible).", owl2=False),
    XSD + "duration": _t("Duration", False, "DURATION Cypher (mois, jours, secondes) : sémantique proche ; "
                        "comparaisons < > non définies sur DURATION.", owl2=False),
    XSD + "dayTimeDuration": _t("Duration", False, "", owl2=False),
    XSD + "yearMonthDuration": _t("Duration", False, "", owl2=False),
    XSD + "gYear": _t("Integer", True, "Année seule : INTEGER (ex. 2024) ; fuseau perdu. Alternative : DATE au 1er janvier.",
                      owl2=False),
    XSD + "gYearMonth": _t("String", True, "'YYYY-MM' en STRING (ou DATE au 1er du mois).", owl2=False),
    XSD + "gMonth": _t("Integer", True, "Mois 1-12 en INTEGER.", owl2=False),
    XSD + "gDay": _t("Integer", True, "Jour 1-31 en INTEGER.", owl2=False),
    XSD + "gMonthDay": _t("String", True, "'--MM-DD' en STRING.", owl2=False),
    RDF + "HTML": _t("String", True, "HTML stocké en texte.", owl2=False),
    RDF + "JSON": _t("String", True, "JSON stocké en texte (pas de MAP en propriété).", owl2=False),
}

_DEFAULT_TYPE = _t("String", True, "Datatype inconnu ou personnalisé (facettes xsd:pattern, minInclusive…) : "
                   "STRING par défaut, restrictions → validations.", owl2=False)


def map_xsd(datatype_iri: Optional[str]) -> dict[str, Any]:
    """Retourne {type, lossy, note, owl2} pour un IRI de datatype (None → rdfs:Literal)."""
    if not datatype_iri:
        return dict(XSD_TYPE_MAP[RDFS + "Literal"])
    return dict(XSD_TYPE_MAP.get(datatype_iri, _DEFAULT_TYPE))


# ---------------------------------------------------------------------------
# Nommage (N01) : PascalCase labels, UPPER_SNAKE relations, camelCase propriétés.
# ---------------------------------------------------------------------------
def _local(name: str) -> str:
    for sep in ("#", "/", ":"):
        if sep in name:
            name = name.rsplit(sep, 1)[1]
    return name


def _words(name: str) -> list[str]:
    s = _local(name)
    s = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", s)
    s = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1 \2", s)
    return [w for w in re.split(r"[^A-Za-z0-9]+", s) if w]


def _fix_leading_digit(s: str, prefix: str) -> str:
    return prefix + s if s and s[0].isdigit() else s


def node_name(name: str) -> str:
    """auto:electric_vehicle → ElectricVehicle (acronymes conservés : VIN → Vin)."""
    out = "".join(w[:1].upper() + w[1:].lower() if w.isupper() and len(w) > 1 else w[:1].upper() + w[1:]
                  for w in _words(name))
    return _fix_leading_digit(out, "N") or "Node"


def edge_name(name: str) -> str:
    """auto:isPartOf → IS_PART_OF ; auto:installedOn → INSTALLED_ON."""
    out = "_".join(w.upper() for w in _words(name))
    return _fix_leading_digit(out, "R_") or "RELATED_TO"


def reverse_name(name: str, inverse: Optional[str] = None) -> Optional[str]:
    """Neo4j ne stocke pas de type inverse : toujours None (le sens inverse est traversé, O04)."""
    return None


def prop_name(name: str, lang: Optional[str] = None) -> str:
    """auto:mileage_km → mileageKm ; rdfs:label + lang 'fr' → label_fr (D06)."""
    ws = _words(name)
    if not ws:
        return "value"
    out = ws[0][:1].lower() + (ws[0][1:].lower() if ws[0].isupper() else ws[0][1:])
    out += "".join(w[:1].upper() + (w[1:].lower() if w.isupper() else w[1:]) for w in ws[1:])
    out = _fix_leading_digit(out, "p")
    if lang:
        out += "_" + re.sub(r"[^A-Za-z0-9]", "_", lang.lower())
    return out


# ---------------------------------------------------------------------------
# Recommandations par règle du catalogue (journal/L0/review-w3c-catalogue.md, 66 règles + X00).
# Identifiants d'options = vocabulaire normatif de samples/trap/expected-findings.yaml (recommended = oracle).
# Entrée : options (id, label, impact), recommended (id), rationale.
def _o(id_: str, label: str, impact: str) -> dict[str, str]:
    return {"id": id_, "label": label, "impact": impact}


def _r(rec: str, rationale: str, *opts: tuple[str, str, str]) -> dict[str, Any]:
    assert any(o[0] == rec for o in opts), rec
    return {"options": [_o(*o) for o in opts], "recommended": rec, "rationale": rationale}


_IGN = ("ignore", "Ignorer", "Construct perdu, non documenté dans le schéma.")
_VAL = "Requête de détection dans validation.cypher"

RECOMMENDATIONS: dict[str, dict[str, Any]] = {
    # --- Classes -----------------------------------------------------------------------------
    "C01": _r("label", "Correspondance directe classe → label PascalCase.",
              ("label", "Label PascalCase", "Un label par classe nommée.")),
    "C02": _r("multi_label", "Un nœud porte nativement plusieurs labels : (:Vehicle:ElectricVehicle) conserve l'héritage et "
              "permet MATCH (n:Vehicle) sans UNION.",
              ("multi_label", "Multi-labels (parent + sous-classe)", "Héritage conservé ; contraintes posées par label, "
               "propriétés du parent non recopiées."),
              ("flatten_into_leaves", "Aplatir dans les feuilles", "Un label par nœud ; requête sur le parent = UNION."),
              ("primary_parent_discriminator", "Label parent + propriété discriminante",
               "Sous-classes perdues comme labels ; modèle aligné sur Curiosity.")),
    "C03": _r("multi_label", "Pas de limite pratique au nombre de labels : l'héritage multiple est fidèle.",
              ("multi_label", "Multi-labels (tous les parents)", "Héritage multiple fidèle."),
              ("primary_parent_discriminator", "Parent principal + discriminant", "Second parent perdu comme label.")),
    "C04": _r("secondary_label", "Un label abstrait factorise contraintes et requêtes ; aucun nœud ne le porte seul.",
              ("secondary_label", "Label secondaire seulement", "Contraintes du label s'appliquent à toutes les sous-classes."),
              ("merge_into_leaves", "Fusionner dans les feuilles", "Label abstrait disparu ; contraintes dupliquées."),
              ("node_type", "Label autonome instanciable", "Autorise des nœuds du seul label abstrait.")),
    "C05": _r("merge_types", "Classes équivalentes = mêmes instances : un seul label canonique, l'alias est documenté.",
              ("merge_types", "Fusionner (nom canonique + alias documenté)", "Un des noms disparaît du schéma."),
              ("multi_label", "Porter les deux labels", "Redondance à maintenir à l'ingestion.")),
    "C06": _r("computed_label", "Pas de raisonneur dans Neo4j : le label dérivé est posé par une requête de classification "
              "rejouée après ingestion.",
              ("computed_label", "Label calculé (SET n:Label par requête)", "À rejouer après chaque ingestion."),
              ("materialize_at_ingest", "Calculé par l'ETL", "Définition hors base."),
              ("doc_only", "Documenter seulement", "Pas de label stocké."), _IGN),
    "C07": _r("validation", "Aucune contrainte native de disjonction de labels.",
              ("validation", "Requête MATCH (n:A:B)", "Détection a posteriori, non bloquante à l'écriture."),
              ("doc_only", "Documenter seulement", "Aucun contrôle."), _IGN),
    "C08": _r("reference_nodes", "Les valeurs de l'énumération deviennent des nœuds interrogeables (sauts supplémentaires, "
              "attributs possibles) ; en propriété, aucune contrainte native de liste de valeurs.",
              ("reference_nodes", "Nœuds de référence + relation", "Valeurs interrogeables ; un saut de plus."),
              ("enum_property", "Propriété STRING + validation de valeurs", "Plus simple ; valeurs vérifiées hors schéma.")),
    "C09": _r("secondary_label", "Restriction d'existence/de valeur anonyme : seul un label secondaire de regroupement est "
              "transposable ; le reste est documenté.",
              ("secondary_label", "Label secondaire (si la classe est nommée)", "Regroupement conservé, définition perdue."),
              ("doc_only", "Documenter, ne pas transposer", "Expression de classe perdue.")),
    "C10": _r("multi_label", "Union disjointe : labels parent + enfants ; « exactement un enfant » vérifié par requête.",
              ("multi_label", "Parent + labels enfants + validation", "Exclusivité non native."),
              ("primary_parent_discriminator", "Parent + discriminant obligatoire", "Enfants non labels."),
              ("doc_only", "Documenter seulement", "Aucun contrôle.")),
    "C11": _r("computed_label", "Complément : label calculé par requête (WHERE NOT n:A) ou documenté.",
              ("computed_label", "Label calculé par requête", "À rejouer après ingestion."),
              ("doc_only", "Documenter", "Définition perdue."), _IGN),
    "C12": _r("reference_nodes", "Punning : label pour la classe, nœud de référence distinct pour l'individu.",
              ("reference_nodes", "Label + nœud de référence (noms distincts)", "Deux objets à relier à la main."),
              ("rename", "Renommer l'un des deux", "Perte de l'IRI commune."),
              ("doc_only", "Documenter", "Lien classe/individu perdu.")),
    "C13": _r("computed_label", "Axiome général d'inclusion : classification par requête, pas de moteur d'inférence.",
              ("computed_label", "Job de classification Cypher", "À rejouer après ingestion."),
              ("materialize_at_ingest", "Matérialisé à l'ingestion", "Logique dupliquée dans l'ETL."),
              ("doc_only", "Documenter", "Axiome perdu.")),
    # --- Clés --------------------------------------------------------------------------------
    "K01": _r("unique_constraint", "Propriété uri + contrainte UNIQUE : compatible n10s (Resource.uri), MERGE idempotent, "
              "Community.",
              ("unique_constraint", "uri + IS UNIQUE", "Identité RDF conservée, disponible en Community."),
              ("uri_key", "uri comme clé (NODE KEY, Enterprise)", "Existence garantie en plus."),
              ("generated_key", "Clé générée sans IRI", "Aller-retour RDF impossible.")),
    "K02": _r("node_key", "owl:hasKey ≈ NODE KEY (unicité + existence) : c'est un renforcement par rapport à l'OWL, à "
              "arbitrer ; Community : UNIQUE composite généré, existence par validation.",
              ("node_key", "IS NODE KEY (Enterprise) / IS UNIQUE (Community)", "Renforcement : propriétés obligatoires."),
              ("unique_constraint", "IS UNIQUE seulement", "Existence non garantie."),
              ("key_concat", "Clé concaténée en une propriété", "Clé composite masquée.")),
    "K03": _r("generated_key", "Pas de clé OWL : clé générée (uri ou UUID) pour l'idempotence du MERGE.",
              ("generated_key", "Clé générée (uri / hash)", "Identifiant technique sans sens métier."),
              ("unique_constraint", "Choisir une propriété métier + IS UNIQUE", "Arbitrage humain requis.")),
    "K04": _r("generated_key", "Individu anonyme : IRI skolem /.well-known/genid/ ou hash déterministe.",
              ("generated_key", "Clé skolem / hash", "Stable si la source est stable."),
              _IGN),
    "K05": _r("materialize_key", "Neo4j ne peut pas contraindre une propriété de relation sur le nœud : copier la clé de la "
              "cible en propriété puis NODE KEY.",
              ("materialize_key", "Copier la clé de la cible en propriété + NODE KEY", "Redondance à maintenir."),
              ("key_concat", "Concaténer avec la clé de la cible", "Clé opaque."),
              ("unique_constraint", "Ignorer la partie objet", "Clé partielle.")),
    # --- Propriétés de données ---------------------------------------------------------------
    "D01": _r("property", "Directe.", ("property", "Propriété camelCase", "Typée si l'Enterprise est disponible.")),
    "D02": _r("attach_to_users", "Pas de domaine déclaré : rattacher aux labels qui l'utilisent (restrictions / shapes) ; "
              "Neo4j est sans schéma imposé.",
              ("attach_to_users", "Rattacher aux labels utilisateurs", "Peut multiplier la propriété."),
              ("property", "Propriété libre sans label", "Aucun contrôle."), _IGN),
    "D03": _r("duplicate_per_type", "Domaine en union : la propriété est posée sur chaque label ; contraintes par label.",
              ("duplicate_per_type", "Dupliquer sur chaque label", "Contraintes à poser par label."),
              ("secondary_label", "Label commun technique", "Nouveau label à maintenir.")),
    "D04": _r("list_property", "Listes natives homogènes LIST<T NOT NULL> ; pas de null, pas de propriétés par valeur.",
              ("list_property", "Liste homogène", "Index RANGE/TEXT inutilisables par élément."),
              ("scalar", "Scalaire (dernière valeur)", "Valeurs multiples perdues."),
              ("reference_nodes", "Nœuds valeurs + relation", "Plus lourd, interrogeable.")),
    "D05": _r("native_type", "Type Neo4j le plus proche (decimal → FLOAT avec perte, gYear → INTEGER…) ; la perte est "
              "signalée et à valider par l'humain.",
              ("native_type", "Type Neo4j le plus proche", "Perte selon le type (voir XSD_TYPE_MAP)."),
              ("string_lexical", "STRING lexical exact", "Calculs et comparaisons numériques impossibles.")),
    "D06": _r("per_language_property", "Pas de littéral avec langue ni de MAP en propriété : une propriété par langue "
              "(label_fr, label_en).",
              ("per_language_property", "Une propriété par langue", "Langues hors liste perdues."),
              ("string_property", "Langue par défaut seulement", "Autres langues perdues.")),
    "D07": _r("scalar", "Fonctionnelle : scalaire (+ IS :: TYPE en Enterprise).",
              ("scalar", "Scalaire", "Aucune perte.")),
    "D08": _r("enum_property", "Pas de contrainte de liste de valeurs : propriété + requête de contrôle.",
              ("enum_property", "Propriété + validation de valeurs", "Valeurs vérifiées hors schéma"),
              ("reference_nodes", "Nœuds de référence", "Un saut de plus.")),
    "D09": _r("validation", "Facettes (min/max, pattern, longueur) : type de base natif + requête de contrôle (=~).",
              ("validation", "Type de base + validation", "Facettes hors schéma."),
              ("string_property", "STRING sans contrôle", "Facettes perdues.")),
    "D10": _r("string_property", "rdfs:Literal ou portée absente : STRING.",
              ("string_property", "STRING", "Typage perdu.")),
    "D11": _r("most_specific_type", "Super-propriété de données : la propriété la plus spécifique est conservée ; le parent "
              "n'est pas dupliqué (option disponible).",
              ("most_specific_type", "Propriété la plus spécifique", "La requête sur le parent est perdue."),
              ("duplicate_per_type", "Dupliquer dans la propriété parente", "Redondance à maintenir.")),
    "D12": _r("native_type", "Intersection de portées : type natif de l'intersection des datatypes (+ validation si "
              "lexical).",
              ("native_type", "Type de l'intersection", "Perte si incompatible."),
              ("string_lexical", "STRING lexical", "Typage perdu.")),
    "D13": _r("validation", "Restriction sur propriété de données : exactly 1 → IS NOT NULL (Enterprise) ou requête.",
              ("validation", "Requête de validation", "Détection a posteriori."), _IGN),
    # --- Propriétés d'objet ------------------------------------------------------------------
    "O01": _r("relationship", "Type de relation UPPER_SNAKE entre deux labels.",
              ("relationship", "Type de relation", "Direct.")),
    "O02": _r("relationship", "Domaine/portée absents : résoudre depuis restrictions / shapes, sinon relation sans "
              "contrainte d'extrémités.",
              ("relationship", "Relation, extrémités résolues", "Peut être incomplet."),
              ("ignore", "Ignorer la relation", "Relation absente du schéma.")),
    "O03": _r("relationship", "Un type de relation n'est pas lié à une paire de labels en Neo4j : un type, plusieurs paires.",
              ("relationship", "Un type, plusieurs paires de labels", "Validation par paire."),
              ("duplicate_per_type", "Un type par paire", "Nom dupliqué.")),
    "O04": _r("single_direction", "Traversée bidirectionnelle gratuite : un seul sens stocké, le nom de l'inverse est "
              "documenté (n10s ne crée pas non plus d'inverse).",
              ("single_direction", "Un seul sens stocké", "Nom inverse seulement documenté."),
              ("edge_pair", "Matérialiser les deux sens", "Double écriture, risque d'incohérence.")),
    "O05": _r("undirected_query", "Symétrique : un sens stocké arbitraire, requêtes non orientées -[:T]-.",
              ("undirected_query", "Un sens stocké + MATCH non orienté", "Le sens stocké est arbitraire."),
              ("edge_pair", "Stocker les deux sens", "Doublons à l'agrégation."),
              ("self_reverse", "Relation à elle-même pour inverse", "Écriture double.")),
    "O06": _r("var_length_query", "Les chemins à longueur variable sont natifs (*1..) ; la fermeture est matérialisée "
              "seulement si les performances l'exigent.",
              ("var_length_query", "Requête [:T*1..]", "Coût à l'exécution sur grands graphes."),
              ("materialize_closure", "Matérialiser la fermeture (relation dérivée)", "À recalculer après ingestion.")),
    "O07": _r("most_specific_type", "Super-propriété : le type le plus spécifique est stocké, -[:CHILD|PARENT]- couvre le "
              "parent.",
              ("most_specific_type", "Type le plus spécifique", "Requête parent = union de types."),
              ("materialize_closure", "Matérialiser aussi le parent", "Relations dupliquées.")),
    "O08": _r("path_query", "Chaîne de propriétés : requête de chemin MATCH (a)-[:P]->()-[:Q]->(c).",
              ("path_query", "Requête de chemin", "Non stocké."),
              ("materialize_closure", "Matérialiser la chaîne", "À recalculer.")),
    "O09": _r("validation", "Aucune contrainte de cardinalité de relation en Neo4j.",
              ("validation", "Requête COUNT {} ≤ 1", "Détection a posteriori."),
              ("property", "Ramener la cible en propriété", "Relation perdue.")),
    "O10": _r("validation", "Cardinalité min/max/exacte : requête de validation.",
              ("validation", "Requête de validation", "Détection a posteriori."), _IGN),
    "O11": _r("validation", "Irréflexive / asymétrique : requête (a)-[:T]->(a) ou paire inverse.",
              ("validation", "Requête de détection", "Détection a posteriori."), _IGN),
    "O12": _r("validation", "Restriction hasValue / someValuesFrom : requête de validation.",
              ("validation", "Requête de validation", "Détection a posteriori."), _IGN),
    "O13": _r("validation", "allValuesFrom : le label de la cible est vérifié par requête, jamais par contrainte.",
              ("validation", "Requête sur le label de la cible", "Détection a posteriori."),
              ("ignore", "Ignorer", "Restriction perdue.")),
    "O14": _r("reverse_traversal", "ObjectInverseOf anonyme : traversée inverse <-[:T]-.",
              ("reverse_traversal", "Traversée inverse", "Aucune perte."),
              ("resolve_named_inverse", "Inverse nommé s'il existe", "Dépend de l'ontologie.")),
    "O15": _r("validation", "InverseFunctional : au plus une relation entrante, par requête.",
              ("validation", "Requête sur l'entrant", "Détection a posteriori."), _IGN),
    "O16": _r("validation", "Cardinalité qualifiée : validation filtrée par label de la cible.",
              ("validation", "Requête filtrée par label", "Détection a posteriori."), _IGN),
    "O17": _r("validation", "hasSelf : booléen matérialisé ou requête (a)-[:T]->(a).",
              ("validation", "Requête de détection", "Détection a posteriori."),
              ("materialize_at_ingest", "Booléen matérialisé", "À recalculer."), _IGN),
    "O18": _r("ignore", "Super-propriété universelle : aucun effet, documenté.", _IGN),
    "O19": _r("merge_relationship_types", "Propriétés équivalentes : un type canonique + alias documenté.",
              ("merge_relationship_types", "Fusionner (canonique + alias)", "Un nom disparaît."),
              ("edge_pair", "Garder les deux types", "Redondance.")),
    "O20": _r("validation", "Propriétés disjointes : requête de détection des paires en commun.",
              ("validation", "Requête de détection", "Détection a posteriori."), _IGN),
    "O21": _r("intersection_domain", "Plusieurs domaines/portées = intersection ; garder la classe la plus spécifique si "
              "l'une subsume l'autre, sinon arbitrer.",
              ("intersection_domain", "Intersection (classe la plus spécifique)", "Souvent une erreur de modélisation."),
              ("duplicate_per_type", "Union (lecture naïve)", "Sémantique inversée.")),
    # --- Réification -------------------------------------------------------------------------
    "R01": _r("dereify_relationship", "Relation porteuse de propriétés (Neo4j le permet) : plus de nœud intermédiaire ; une "
              "relation ne peut pas être cible d'une autre relation.",
              ("dereify_relationship", "Relation porteuse de propriétés", "Un saut de moins ; non extensible."),
              ("keep_node", "Garder un nœud intermédiaire", "Un saut de plus, extensible.")),
    "R02": _r("keep_node", "Relation n-aire (≥ 3 rôles) : un nœud intermédiaire.",
              ("keep_node", "Garder un nœud (patron n-aire)", "Un saut de plus.")),
    # --- Annotations / métadonnées / import --------------------------------------------------
    "A01": _r("schema_metadata", "Étiquettes et commentaires : documentation du schéma (commentaires Cypher, README).",
              ("schema_metadata", "Métadonnées du schéma", "Absentes de la base.")),
    "A02": _r("report", "Annotations d'axiome : rapport ; propriété de provenance sur la relation seulement sur demande.",
              ("report", "Rapport de transposition", "Provenance perdue."),
              ("provenance_property", "Propriété de provenance sur la relation", "Alourdit les relations.")),
    "A03": _r("exclude", "Entité dépréciée : exclue du schéma (option : conservée avec drapeau).",
              ("exclude", "Exclure", "Absente du schéma."),
              ("flag_deprecated", "Garder avec drapeau deprecated", "Schéma plus lourd.")),
    "M01": _r("schema_metadata", "En-tête d'ontologie : en-tête du schéma généré.",
              ("schema_metadata", "En-tête généré", "Absent de la base.")),
    "M02": _r("external_reference", "Imports : fermeture chargée hors ligne si disponible, sinon termes importés = références "
              "externes signalées.",
              ("load_closure_offline", "Charger la fermeture hors ligne (cache)", "Dépend de l'accès réseau."),
              ("external_reference", "Références externes + constat", "Termes importés non transposés.")),
    # --- Individus ---------------------------------------------------------------------------
    "I01": _r("reference_nodes", "Individus nommés : nœuds de référence ingérés (MERGE sur uri).",
              ("reference_nodes", "Nœuds de référence", "Données de référence ingérées."), _IGN),
    "I02": _r("merge_nodes", "owl:sameAs : fusion des nœuds (clé canonique + alias) ; relation SAME_AS en option.",
              ("merge_nodes", "Fusion des nœuds (canonique + alias)", "Perte de l'identité distincte."),
              ("same_as_edge", "Relation SAME_AS", "Équivalence non appliquée aux requêtes.")),
    "I03": _r("noop_una", "Le graphe suppose l'UNA : differentFrom sans effet, renforcement noté au rapport.",
              ("noop_una", "Aucun effet (UNA)", "Renforcement implicite.")),
    "I04": _r("validation", "Assertion négative : requête de détection de la relation/valeur interdite.",
              ("validation", "Requête de détection", "Détection a posteriori."), _IGN),
    "I05": _r("multi_label", "Individu à plusieurs types : multi-labels.",
              ("multi_label", "Multi-labels", "Aucune perte."),
              ("primary_parent_discriminator", "Type principal + discriminant", "Types secondaires perdus.")),
    # --- Nommage / divers --------------------------------------------------------------------
    "N01": _r("rename", "Conventions Cypher : PascalCase (labels), UPPER_SNAKE (relations), camelCase (propriétés) ; nom "
              "d'origine conservé en source.",
              ("rename", "Appliquer les conventions Neo4j", "Noms d'origine en source.")),
    "G01": _r("report", "Construct valide mais non représentable dans OntoModel : listé au rapport, jamais supprimé en "
              "silence.",
              ("report", "Lister au rapport", "Non transposé.")),
    "X00": _r("report", "Construct non traité par le moteur : rapport.",
              ("report", "Lister au rapport", "Non transposé.")),
}


def options(rule_id: str, ctx: Optional[dict[str, Any]] = None) -> list[Option]:
    """Options de la règle pour Neo4j, au format pg_model.Option (recommended_for renseigné)."""
    entry = RECOMMENDATIONS.get(rule_id)
    if not entry:
        return []
    rec = recommend(rule_id, ctx)
    return [Option(id=o["id"], label=o["label"], impact=o["impact"],
                   recommended_for=["neo4j"] if o["id"] == rec else []) for o in entry["options"]]


def recommend(rule_id: str, ctx: Optional[dict[str, Any]] = None) -> Optional[str]:
    """Option recommandée ; contexte facultatif.

    ctx reconnus : R01 {"links": int} (object properties fonctionnelles de la classe de réification).
    """
    entry = RECOMMENDATIONS.get(rule_id)
    if not entry:
        return None
    ctx = ctx or {}
    if rule_id == "R01" and int(ctx.get("links", 2)) >= 3:
        return "keep_node"
    return entry["recommended"]
