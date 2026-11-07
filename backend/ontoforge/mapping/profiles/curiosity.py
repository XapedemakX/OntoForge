"""Profil cible Curiosity — déclaratif, lu par le moteur de mapping (lead).

Propriétaire : agent curiosity (D-014). Sources vérifiées le 2026-11-02 (voir aussi
skills/curiosity-schema-design/SKILL.md) :

- [S1] Defining Schemas ............ https://docs.curiosity.ai/data-connector/schemas
- [S2] Schema reference ............ https://docs.curiosity.ai/workspace-api/schema-reference
- [S3] SDK C# ...................... https://docs.curiosity.ai/workspace-api/sdk-csharp
- [S4] Custom connector from scratch https://docs.curiosity.ai/workspace-build/guides-and-best-practices/tutorials/custom-connector-from-scratch
- [S5] Technical Support data model  https://docs.curiosity.ai/workspace-build/guides-and-best-practices/tutorials/technical-support/data-model
       + https://github.com/curiosity-ai/technical-support (data-connector/INSTRUCTIONS.md)
- [S6] Graph query language ........ https://docs.curiosity.ai/workspace-api/graph-query-language
- [S7] Filters and facets .......... https://docs.curiosity.ai/workspace-build/search-and-nlp/search-configuration/filters-facets

Ce qui n'est pas confirmé par ces sources est marqué « À VÉRIFIER ».
"""
from __future__ import annotations

import re
from typing import Optional

from ontoforge.core.pg_model import PGType

TARGET = "curiosity"

# ---------------------------------------------------------------------------------------------
# Capacités de la plateforme
# ---------------------------------------------------------------------------------------------
CAPABILITIES: dict[str, object] = {
    # [S1][S2] une classe C# [Node] = un type de nœud nommé d'après la classe ; aucun mécanisme
    # de type multiple documenté -> héritage aplati (C02/C03/C04).
    "multi_label": False,
    # [S2] « Edge schemas are just a name » : aucune propriété d'arête -> R01 garde un nœud.
    "edge_properties": False,
    # [S1][S5] arêtes déclarées en paires (HasPart/PartOf) ; Link(a, b, aToB, bToA) crée les deux sens.
    "native_reverse_edges": True,
    # [S2] exactement une propriété [Key] par type, de type string, non vide (rejet au commit).
    "single_string_key": True,
    # [S2] pas de clé composite : à construire de façon déterministe à partir des champs identifiants.
    "composite_key": False,
    # [S2] unicité = identité : deux nœuds du même type et de même clé sont le même nœud (upsert).
    # Aucune contrainte d'unicité sur une autre propriété -> validation applicative.
    "unique_constraint": "key_only",
    # [S2] aucune notion de propriété obligatoire documentée (seule la clé doit être non vide).
    "existence_constraint": "none",
    # [S2] les champs sont typés par le schéma (FieldType / type C#) : contrainte de type native.
    "type_constraint": "native",
    # [S2] ListField / T[] / List<T> ; DictionaryField (clés string) ; TableField (fluent).
    "list_properties": True,
    # [S2] aucune cardinalité d'arête -> validation dans le connecteur (O09/O10).
    "relationship_cardinality": False,
    # [S7] recherche plein texte configurée dans l'espace de travail (Manage → Search), pas dans le
    # schéma C#. Le générateur ne fait que recommander les champs à indexer.
    "fulltext": "workspace_config",
    # [S7] facettes de propriété (string, bool, temps, numérique) et facettes « liées » (graph facets)
    # par arête vers un nœud de référence normalisé -> C08 recommande les nœuds de référence.
    "facets": "property_and_related",
    # --- compléments (lecture libre par le moteur) ---
    "timestamp_property": "at_most_one",  # [S2] un seul [Timestamp], DateTimeOffset ou Time
    "edge_key": False,  # [S2] arêtes non adressables par clé
    "edge_query_direction": "both",  # [S6] arêtes bidirectionnelles, Out() suffit
    "decimal_native": True,  # [S2] FieldType.Decimal -> PGType Decimal (D-L13-01)
    "unsigned_native": True,  # [S2] UInt32 / UInt64
    "geo_point": True,  # [S2] FieldType.GeoPoint
    "reserved_node_fields": ["Type", "UID", "Key", "Timestamp", "Edges", "EdgeCount"],  # [S2]
    "reserved_edge_fields": ["Type", "To", "ToType", "UID", "Timestamp"],  # [S2]
    "nullable_scalars": "collapsed",  # [S2] int? -> int : l'absence de valeur n'est pas distinguée
}

# ---------------------------------------------------------------------------------------------
# Types : IRI xsd/rdf/owl -> (type PG, perte pour Curiosity ?, note)
# Correspondance PG -> C# dans targets/curiosity.py (Integer->long, Float->double, Date->DateTime,
# DateTime->DateTimeOffset, LocalDateTime->DateTime, Time->string, Duration->string).
# ---------------------------------------------------------------------------------------------
XSD = "http://www.w3.org/2001/XMLSchema#"
RDF = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
RDFS = "http://www.w3.org/2000/01/rdf-schema#"
OWL = "http://www.w3.org/2002/07/owl#"

XSD_TYPE_MAP: dict[str, tuple[PGType, bool, str]] = {
    # --- nombres réels (OWL 2 §4.1) ---
    OWL + "real": ("Float", True, "owl:real non représentable : double (précision et irrationnels perdus)."),
    OWL + "rational": ("Float", True, "owl:rational -> double (fraction exacte perdue)."),
    XSD + "decimal": ("Decimal", False, "xsd:decimal -> FieldType.Decimal (C# decimal, 28-29 chiffres significatifs) ; "
                                        "sans perte pour les valeurs usuelles."),
    XSD + "integer": ("Integer", True, "Entier non borné -> long 64 bits (dépassement possible)."),
    XSD + "nonNegativeInteger": ("Integer", True, "-> long ; borne >= 0 en validation applicative."),
    XSD + "nonPositiveInteger": ("Integer", True, "-> long ; borne <= 0 en validation applicative."),
    XSD + "positiveInteger": ("Integer", True, "-> long ; borne > 0 en validation applicative."),
    XSD + "negativeInteger": ("Integer", True, "-> long ; borne < 0 en validation applicative."),
    XSD + "long": ("Integer", False, "long (Int64)."),
    XSD + "int": ("Integer", False, "Stocké en long (Int32 existe côté Curiosity, élargissement sans perte)."),
    XSD + "short": ("Integer", False, "Stocké en long (élargissement)."),
    XSD + "byte": ("Integer", False, "Stocké en long (élargissement)."),
    XSD + "unsignedLong": ("Integer", True, "-> long signé : valeurs > 2^63-1 perdues (UInt64 natif non exposé par PGType)."),
    XSD + "unsignedInt": ("Integer", False, "Stocké en long (élargissement)."),
    XSD + "unsignedShort": ("Integer", False, "Stocké en long (élargissement)."),
    XSD + "unsignedByte": ("Integer", False, "Stocké en long (élargissement)."),
    # --- flottants ---
    XSD + "double": ("Float", False, "double."),
    XSD + "float": ("Float", False, "Stocké en double (élargissement)."),
    # --- chaînes ---
    XSD + "string": ("String", False, "string."),
    XSD + "normalizedString": ("String", False, "string (normalisation des blancs à faire à l'ingestion)."),
    XSD + "token": ("String", False, "string (normalisation à l'ingestion)."),
    XSD + "language": ("String", False, "string (code BCP 47) ; FieldType.Language existe, non exposé par PGType."),
    XSD + "Name": ("String", False, "string (motif XML Name en validation si nécessaire)."),
    XSD + "NCName": ("String", False, "string (motif NCName en validation si nécessaire)."),
    XSD + "NMTOKEN": ("String", False, "string."),
    RDF + "PlainLiteral": ("String", True, "rdf:PlainLiteral : la balise de langue est perdue (cf. D06)."),
    # Tolérance hors carte OWL 2 (non conforme, règle W01) : rdf:langString n'est pas un datatype OWL 2 (voir PlainLiteral).
    RDF + "langString": ("String", True, "NON CONFORME OWL 2 (W01) ; littéral à langue : une propriété par langue (D06), ex. LabelFr, LabelEn."),
    RDF + "XMLLiteral": ("String", True, "XML sérialisé en texte : structure et canonicalisation perdues."),
    RDFS + "Literal": ("String", True, "Type inconnu (rdfs:Literal) : stocké en texte, typage perdu."),
    # --- booléen ---
    XSD + "boolean": ("Boolean", False, "bool."),
    # --- binaires ---
    XSD + "hexBinary": ("String", True, "Binaire -> texte hexadécimal : octets non typés, taille x2 (pas de type binaire Curiosity) ; perte D05."),
    XSD + "base64Binary": ("String", True, "Binaire -> texte base64 : octets non typés, taille x1,33 (pas de type binaire Curiosity) ; perte D05."),
    # --- IRI ---
    XSD + "anyURI": ("String", False, "string ; si la cible est une ressource du graphe, préférer une arête."),
    # --- temps (OWL 2) ---
    XSD + "dateTime": ("DateTime", False, "DateTimeOffset (FieldType.Time). Fuseau absent = ambigu : imposer UTC."),
    XSD + "dateTimeStamp": ("DateTime", False, "DateTimeOffset (fuseau obligatoire, conservé)."),
    # --- temps hors OWL 2 (XSD 1.1, fréquents dans les ontologies) ---
    XSD + "date": ("Date", True, "Pas de type date seule : DateTime à minuit (FieldType.Time), sans fuseau."),
    XSD + "time": ("Time", True, "Pas de type heure : texte HH:mm:ss (tri lexical seulement)."),
    XSD + "duration": ("Duration", True, "Pas de type durée : texte ISO 8601 (PnYnMnDTnHnMnS), pas d'arithmétique."),
    XSD + "dayTimeDuration": ("Duration", True, "Texte ISO 8601 (ou secondes en long si calculs nécessaires)."),
    XSD + "yearMonthDuration": ("Duration", True, "Texte ISO 8601 (ou mois en long si calculs nécessaires)."),
    XSD + "gYear": ("Integer", True, "Année en long ; fuseau éventuel perdu."),
    XSD + "gYearMonth": ("String", True, "Texte YYYY-MM."),
    XSD + "gMonth": ("Integer", True, "Mois 1-12 en long."),
    XSD + "gMonthDay": ("String", True, "Texte --MM-DD."),
    XSD + "gDay": ("Integer", True, "Jour 1-31 en long."),
}

# Datatypes de la carte des datatypes OWL 2 (OWL 2 Structural Specification §4) : tous doivent être couverts.
OWL2_DATATYPES: tuple[str, ...] = (
    OWL + "real", OWL + "rational", XSD + "decimal", XSD + "integer", XSD + "nonNegativeInteger",
    XSD + "nonPositiveInteger", XSD + "positiveInteger", XSD + "negativeInteger", XSD + "long", XSD + "int",
    XSD + "short", XSD + "byte", XSD + "unsignedLong", XSD + "unsignedInt", XSD + "unsignedShort",
    XSD + "unsignedByte", XSD + "double", XSD + "float", XSD + "string", XSD + "normalizedString", XSD + "token",
    XSD + "language", XSD + "Name", XSD + "NCName", XSD + "NMTOKEN", XSD + "boolean", XSD + "hexBinary",
    XSD + "base64Binary", XSD + "anyURI", XSD + "dateTime", XSD + "dateTimeStamp", RDF + "XMLLiteral",
    RDF + "PlainLiteral", RDFS + "Literal",
)

DEFAULT_TYPE: tuple[PGType, bool, str] = ("String", True, "Datatype inconnu ou personnalisé : texte, typage perdu.")


def map_datatype(iri: Optional[str]) -> tuple[PGType, bool, str]:
    """Type PG pour un datatype ; datatype absent ou personnalisé -> String avec perte."""
    if not iri:
        return DEFAULT_TYPE
    return XSD_TYPE_MAP.get(iri, DEFAULT_TYPE)


# ---------------------------------------------------------------------------------------------
# Nommage (N01 : PascalCase partout pour Curiosity — classes, constantes d'arêtes, propriétés C#)
# ---------------------------------------------------------------------------------------------
_RESERVED_NODE_FIELDS = set(CAPABILITIES["reserved_node_fields"])  # type: ignore[arg-type]


def _pascal(local: str) -> str:
    """'repair_order' / 'repair-order' / 'repairOrder' / 'Repair Order' -> 'RepairOrder'.

    Les majuscules internes sont conservées ('VIN' reste 'VIN', 'hasDTC' -> 'HasDTC')."""
    chunks = [c for c in re.split(r"[^0-9A-Za-z]+", local or "") if c]
    if len(chunks) > 1 and re.fullmatch(r"[A-Z0-9]+(?:[_\- ][A-Z0-9]+)+", local or ""):
        # UPPER_SNAKE (HAS_MODEL) -> HasModel : les séparateurs ne sont pas perdus (HASMODEL).
        chunks = [c.capitalize() for c in chunks]
    name = "".join(c[0].upper() + c[1:] for c in chunks)
    if not name:
        return "Unnamed"
    if name[0].isdigit():
        name = "N" + name
    return name


def node_name(local: str) -> str:
    """Nom de type de nœud (= nom de classe C# [Node])."""
    return _pascal(local)


def edge_name(local: str) -> str:
    """Nom d'arête (= constante de la classe Edges)."""
    return _pascal(local)


def reverse_name(edge: str, inverse_local: Optional[str] = None, *, symmetric: bool = False) -> str:
    """Nom de l'arête retour.

    - inverse déclaré (owl:inverseOf) -> son nom PascalCase ;
    - symétrique (``symmetric=True`` ou ``inverse_local`` = la propriété elle-même) -> même nom ;
    - sinon dérivé : HasPart -> PartOf, IsPartOf -> HasPart, PartOf -> HasPart ;
      les autres formes reçoivent provisoirement le suffixe 'Inverse', que le moteur remplace ensuite par un
      nom lisible (mapping/reverse_names.py : CoveredBy, HasVehicle, <Arête>Of<Source>), sans usurper le nom
      d'une propriété OWL ; à renommer par l'humain si besoin (finding N01/O01).
    """
    e = edge_name(edge)
    if symmetric:
        return e
    if inverse_local:
        inv = edge_name(inverse_local)
        return inv
    m = re.fullmatch(r"Has([A-Z0-9].*)", e)
    if m:
        return f"{m.group(1)}Of"
    m = re.fullmatch(r"Is([A-Z0-9].*)Of", e)
    if m:
        return f"Has{m.group(1)}"
    m = re.fullmatch(r"([A-Z0-9].*)Of", e)
    if m:
        return f"Has{m.group(1)}"
    return f"{e}Inverse"


def prop_name(local: str) -> str:
    """Nom de propriété C# : PascalCase ; un nom réservé par Curiosity ([S2] Type, UID, Key, Timestamp,
    Edges, EdgeCount) reçoit le suffixe 'Value' (type -> TypeValue)."""
    name = _pascal(local)
    if name in _RESERVED_NODE_FIELDS:
        name += "Value"
    return name


def lang_prop_name(local: str, lang: str) -> str:
    """D06 : une propriété par langue — label + fr -> LabelFr."""
    return prop_name(local) + _pascal(lang.replace("-", "_").lower())


# ---------------------------------------------------------------------------------------------
# Recommandations par règle du catalogue (docs/ARCHITECTURE.md §4). Le lead les traduit en option ids.
# compensation : none | validation | materialization | query | documentation | rename | human
# ---------------------------------------------------------------------------------------------
RECOMMENDATIONS: dict[str, dict] = {
    "C01": {"approach": "Une classe OWL instanciable = un type de nœud [Node] (classe C#).",
            "rationale": "Correspondance directe [S1] ; le nom de type est le nom de la classe.",
            "compensation": "none"},
    "C02": {"approach": "Aplatir : recopier les propriétés héritées dans la feuille et ajouter une propriété "
                        "discriminante (ex. VehicleKind) quand le parent est instancié ou interrogé.",
            "rationale": "Un nœud = un seul type [S1][S2] : pas de multi-label pour porter la hiérarchie ; le "
                         "discriminant reste filtrable et utilisable en facette [S7].",
            "compensation": "validation"},
    "C03": {"approach": "Choisir un parent principal (celui qui apporte la clé et le plus de propriétés), "
                        "aplatir les autres en propriétés discriminantes booléennes ou texte.",
            "rationale": "Mono-type : un seul ancêtre peut définir le type de nœud ; les autres appartenances "
                         "deviennent des attributs filtrables.",
            "compensation": "human"},
    "C04": {"approach": "Pas de type de nœud pour la classe abstraite : fusion de ses propriétés dans chaque "
                        "feuille + discriminant.",
            "rationale": "Un type sans instance directe encombre le schéma et la recherche ; requêtes sur le "
                         "parent = union des feuilles (ou un type unique aplati si les feuilles sont proches).",
            "compensation": "query"},
    "C05": {"approach": "Fusionner les classes équivalentes nommées en un seul type de nœud (nom principal choisi "
                        "par l'humain), l'autre IRI gardée en documentation.",
            "rationale": "Deux types distincts dupliqueraient les nœuds (même clé, types différents).",
            "compensation": "documentation"},
    "C06": {"approach": "Matérialiser la classification à l'ingestion : propriété discriminante ou booléenne "
                        "calculée par le connecteur depuis la définition (restriction).",
            "rationale": "Aucun raisonneur côté Curiosity : l'appartenance définie doit être calculée et stockée.",
            "compensation": "materialization"},
    "C07": {"approach": "Validation applicative dans le connecteur (une même clé ne doit pas apparaître dans les "
                        "deux types ; un discriminant scalaire garantit la disjonction des sous-types aplatis).",
            "rationale": "Aucune contrainte de disjonction côté plateforme [S2].",
            "compensation": "validation"},
    "C08": {"approach": "Énumération -> nœuds de référence (un type, une instance par valeur, clé = valeur) reliés "
                        "par une paire d'arêtes ; propriété texte seulement pour un petit ensemble figé.",
            "rationale": "Les facettes liées (related facets) filtrent par arête vers un nœud normalisé et suivent "
                         "les renommages sans dénormalisation [S7].",
            "compensation": "validation"},
    "C09": {"approach": "Documenter l'union / intersection anonyme ; ne rien générer (ou discriminant si l'humain "
                        "nomme la classe).",
            "rationale": "Pas de type anonyme dans un schéma C# ; la sémantique ensembliste est perdue.",
            "compensation": "documentation"},
    "K01": {"approach": "[Key] string = IRI (propriété Uri) quand aucune clé métier n'existe.",
            "rationale": "Clé string unique, stable et non vide exigée [S2] ; l'IRI satisfait ces trois conditions.",
            "compensation": "none"},
    "K02": {"approach": "owl:hasKey -> [Key] string ; clé composite -> propriété Id calculée par concaténation "
                        "déterministe des composants (séparateur '|'), composants gardés en [Property].",
            "rationale": "Une seule clé string par type [S2] ; la doc recommande de construire la clé de façon "
                         "déterministe à partir des champs identifiants, jamais un UUID aléatoire.",
            "compensation": "validation"},
    "K03": {"approach": "Sans clé métier : [Key] Uri (IRI de l'individu) ; proposer une propriété candidate si une "
                        "data property fonctionnelle et obligatoire existe.",
            "rationale": "La ré-ingestion doit être idempotente (AddOrUpdate par clé) [S2][S4].",
            "compensation": "human"},
    "D01": {"approach": "Data property à domaine unique -> [Property] typée sur le nœud.",
            "rationale": "Correspondance directe ; seules les propriétés attribuées sont ingérées [S1].",
            "compensation": "none"},
    "D02": {"approach": "Sans domaine : rattacher aux types qui l'utilisent (restrictions, shapes, individus) ; "
                        "à défaut, arbitrage humain.",
            "rationale": "Une propriété C# appartient à une classe : pas de propriété globale.",
            "compensation": "human"},
    "D03": {"approach": "Domaine multiple : dupliquer la [Property] sur chaque type du domaine, même nom.",
            "rationale": "Pas d'héritage de schéma ; même nom = même facette transverse possible.",
            "compensation": "none"},
    "D04": {"approach": "Non fonctionnelle -> liste (T[]) ; si les valeurs sont partagées, préférer des nœuds de "
                        "référence.",
            "rationale": "ListField / T[] supportés [S2].",
            "compensation": "none"},
    "D05": {"approach": "Appliquer XSD_TYPE_MAP ; types sans équivalent (decimal, gYear, duration, time, custom) -> "
                        "type le plus proche + validation / format documenté.",
            "rationale": "Types Curiosity : String, Boolean, entiers, Float, Double, Decimal, Time, GeoPoint, "
                         "Language, UID128 [S2] ; pas de date seule, heure, durée.",
            "compensation": "validation"},
    "D06": {"approach": "Littéraux multilingues -> une propriété par langue (LabelFr, LabelEn) ; ou un "
                        "Dictionary<string,string> si les langues sont ouvertes.",
            "rationale": "Pas de type langString ; DictionaryField à clés string existe [S2] (indexation/facettes "
                         "d'un dictionnaire : À VÉRIFIER).",
            "compensation": "none"},
    "D07": {"approach": "Fonctionnelle -> propriété scalaire.",
            "rationale": "Correspondance directe.",
            "compensation": "none"},
    "O01": {"approach": "Object property -> paire d'arêtes (constante aller + constante retour dans Edges), "
                        "liées par Link(a, b, aller, retour).",
            "rationale": "Arêtes nommées, bidirectionnelles, déclarées par paires [S1][S5].",
            "compensation": "none"},
    "O02": {"approach": "Domaine ou portée manquants : déduire des restrictions / shapes ; sinon arbitrage humain.",
            "rationale": "Le connecteur doit savoir quels types de nœuds lier.",
            "compensation": "human"},
    "O03": {"approach": "Domaine/portée multiples : un même nom d'arête utilisé pour chaque paire de types "
                        "(constante unique dans Edges).",
            "rationale": "Le schéma d'arête n'est qu'un nom [S2] : il n'est pas lié à un couple de types.",
            "compensation": "none"},
    "O04": {"approach": "owl:inverseOf -> la paire aller/retour native ; une seule déclaration, un seul Link.",
            "rationale": "Le retour est gratuit [S1][S3].",
            "compensation": "none"},
    "O05": {"approach": "Symétrique -> l'arête est son propre retour (même constante des deux côtés).",
            "rationale": "Évite deux noms pour une même relation. Link(a, b, X, X) : À VÉRIFIER.",
            "compensation": "none"},
    "O06": {"approach": "Transitive : traverser à la requête (Out() répété, profondeur bornée) par défaut ; "
                        "matérialiser une arête dérivée (ex. PartOfAncestor) si la requête est fréquente.",
            "rationale": "Pas de fermeture transitive ni de chemin de longueur variable documentés [S6].",
            "compensation": "materialization"},
    "O07": {"approach": "Sous-propriété : stocker l'arête la plus spécifique ; matérialiser l'arête parente "
                        "seulement si elle est interrogée seule.",
            "rationale": "Pas de hiérarchie d'arêtes ; Out() sans type traverse tout [S6].",
            "compensation": "materialization"},
    "O08": {"approach": "Chaîne de propriétés : matérialiser l'arête raccourcie dans le connecteur.",
            "rationale": "Pas d'inférence côté plateforme.",
            "compensation": "materialization"},
    "O09": {"approach": "Fonctionnelle / max 1 / exactly 1 : contrôle de cardinalité dans le connecteur "
                        "(compteur de liens par clé source) ; Link(..., unique: true) évite les doublons.",
            "rationale": "Pas de cardinalité d'arête côté plateforme [S2] ; unique=true dans Link [S3].",
            "compensation": "validation"},
    "O10": {"approach": "some / min n : contrôle d'existence dans le connecteur après création des liens.",
            "rationale": "Pas de contrainte d'existence [S2].",
            "compensation": "validation"},
    "O11": {"approach": "only : garanti par construction (le connecteur ne lie que les types prévus) + contrôle "
                        "du type cible.",
            "rationale": "Le schéma d'arête n'impose pas les types d'extrémités [S2].",
            "compensation": "validation"},
    "O12": {"approach": "hasValue : propriété à valeur fixe posée par le connecteur ou lien vers le nœud de "
                        "référence correspondant.",
            "rationale": "Pas de valeur par défaut dans le schéma.",
            "compensation": "validation"},
    "O13": {"approach": "Réflexive / irréflexive / asymétrique : contrôle dans le connecteur au moment du Link.",
            "rationale": "Aucune contrainte de ce type côté plateforme.",
            "compensation": "validation"},
    "R01": {"approach": "Garder la classe de réification comme type de nœud (ex. PartInstallation) avec ses "
                        "propriétés et une paire d'arêtes vers chaque participant ; clé composite calculée.",
            "rationale": "Les arêtes Curiosity ne portent pas de propriétés [S2] : dé-réifier perdrait les attributs.",
            "compensation": "none"},
    "A01": {"approach": "Annotations -> commentaires de documentation XML (/// summary) du code généré.",
            "rationale": "Pas de métadonnées de schéma documentées ; la doc reste avec le code.",
            "compensation": "documentation"},
    "I01": {"approach": "Individus d'une énumération ou d'un référentiel -> nœuds de référence ingérés par le "
                        "connecteur ; autres individus ignorés (données d'exemple).",
            "rationale": "Les nœuds de référence alimentent les facettes liées [S7].",
            "compensation": "human"},
    "N01": {"approach": "PascalCase partout (types, arêtes, propriétés C#) ; noms réservés suffixés 'Value' ; "
                        "retours non dérivables suffixés 'Inverse' à renommer.",
            "rationale": "Conventions C# et exemples officiels (Device, HasPart/PartOf, SupportCaseSummary) [S5].",
            "compensation": "rename"},
    "X00": {"approach": "Construct non traité en itération 1 : documenté dans le rapport, aucune génération.",
            "rationale": "Aucune perte silencieuse (D-023).",
            "compensation": "documentation"},
}


# ---------------------------------------------------------------------------------------------
# Compléments : règles ajoutées par la revue W3C (journal/L0/review-w3c-catalogue.md §3.1) et
# identifiants d'options normatifs (vocabulaire de samples/trap/expected-findings.yaml, D-031).
# Le catalogue de transposition compte 66 règles ; W01-W07 sont des règles de conformité (L2).
# ---------------------------------------------------------------------------------------------
_EXTRA: dict[str, dict] = {
    "C10": {"approach": "owl:disjointUnionOf : un type de nœud parent + discriminant obligatoire (valeurs = enfants).",
            "rationale": "Mono-type [S2] : « exactement un enfant » est garanti par un discriminant scalaire obligatoire.",
            "compensation": "validation"},
    "C11": {"approach": "owl:complementOf : propriété booléenne matérialisée à l'ingestion, ou documentation.",
            "rationale": "Pas de négation ni de raisonneur côté plateforme.",
            "compensation": "materialization"},
    "C12": {"approach": "Punning classe/individu : type de nœud (classe) ET nœud de référence (individu), noms distincts.",
            "rationale": "Même IRI, deux rôles : un type [Node] et une instance de référence ne peuvent pas porter le même nom C#.",
            "compensation": "rename"},
    "C13": {"approach": "Axiome général d'inclusion : classification matérialisée à l'ingestion (booléen calculé).",
            "rationale": "Aucun raisonneur côté Curiosity.",
            "compensation": "materialization"},
    "K04": {"approach": "Individu anonyme : [Key] générée (hash déterministe ou IRI skolem .well-known/genid).",
            "rationale": "La clé string doit être stable et non vide [S2] ; jamais d'UUID aléatoire (ré-ingestion idempotente).",
            "compensation": "none"},
    "K05": {"approach": "owl:hasKey incluant une propriété objet : clé string = concaténation des propriétés et de la clé "
                        "du nœud cible (séparateur '|').",
            "rationale": "Une seule clé string par type [S2] ; la clé du nœud lié est disponible à l'ingestion.",
            "compensation": "validation"},
    "D08": {"approach": "owl:oneOf sur datatype : propriété string + validation des valeurs autorisées.",
            "rationale": "Pas de type énuméré dans le schéma [S2] ; la liste de valeurs se contrôle dans le connecteur "
                         "(nœuds de référence si les valeurs doivent servir de facette).",
            "compensation": "validation"},
    "D09": {"approach": "Datatype défini / facettes (min/max, pattern, length) : type de base natif + validation.",
            "rationale": "Aucune restriction de facette XSD côté plateforme.",
            "compensation": "validation"},
    "D10": {"approach": "Portée rdfs:Literal ou absente : string.",
            "rationale": "Type inconnu : texte, typage perdu.",
            "compensation": "documentation"},
    "D11": {"approach": "Sous-propriété de données : conserver la propriété la plus spécifique ; dupliquer dans le parent "
                        "seulement si le parent est interrogé seul.",
            "rationale": "Pas de hiérarchie de propriétés.",
            "compensation": "materialization"},
    "D12": {"approach": "Plusieurs domaines/portées (intersection) : type natif de l'intersection des datatypes + validation "
                        "(ex. nonNegativeInteger ∩ int -> long >= 0).",
            "rationale": "Le type C# doit couvrir l'intersection ; les bornes se valident dans le connecteur.",
            "compensation": "validation"},
    "D13": {"approach": "Restriction sur propriété de données (some / only / cardinalité) : validation applicative ; "
                        "exactly 1 / min 1 -> contrôle de présence (pas de propriété obligatoire native).",
            "rationale": "Aucune contrainte d'existence [S2] ; int? replié en int : l'absence n'est pas distinguable.",
            "compensation": "validation"},
    "O14": {"approach": "ObjectInverseOf anonyme : arête retour nommée de la paire si elle existe, sinon traversée "
                        "inverse (Out() sur l'arête retour).",
            "rationale": "Le retour est natif : la traversée inverse est une arête comme une autre [S1][S6].",
            "compensation": "query"},
    "O15": {"approach": "InverseFunctional : contrôle dans le connecteur (au plus un lien entrant par cible).",
            "rationale": "Pas de cardinalité d'arête [S2].",
            "compensation": "validation"},
    "O16": {"approach": "Cardinalité qualifiée : validation comptant les liens vers le type cible précis.",
            "rationale": "Pas de cardinalité d'arête, ni de filtre par type cible dans le schéma [S2].",
            "compensation": "validation"},
    "O17": {"approach": "owl:hasSelf : booléen matérialisé (ex. IsSelfEmployed) calculé à l'ingestion.",
            "rationale": "Pas d'auto-restriction côté plateforme.",
            "compensation": "materialization"},
    "O18": {"approach": "topObjectProperty / topDataProperty en super-propriété : ignoré (documenté).",
            "rationale": "Propriété universelle sans contenu opérationnel.",
            "compensation": "documentation"},
    "O19": {"approach": "owl:equivalentProperty : fusionner les noms d'arêtes (nom canonique, alias en documentation).",
            "rationale": "Deux noms d'arête pour une même relation fragmenteraient les requêtes.",
            "compensation": "documentation"},
    "O20": {"approach": "propertyDisjointWith : contrôle dans le connecteur (même couple de nœuds non lié par les deux arêtes).",
            "rationale": "Aucune contrainte de disjonction d'arêtes côté plateforme.",
            "compensation": "validation"},
    "O21": {"approach": "Plusieurs domaines/portées sur une propriété objet (= intersection) : classe la plus spécifique si "
                        "l'une subsume l'autre, sinon arbitrage humain (souvent erreur de modélisation).",
            "rationale": "Le connecteur doit lier des types précis ; une intersection sans sous-classe commune n'a "
                         "pas d'instance.",
            "compensation": "human"},
    "R02": {"approach": "Relation n-aire (>= 3 rôles) : type de nœud porteur + une paire d'arêtes par rôle ; clé calculée.",
            "rationale": "Les arêtes Curiosity sont binaires et sans propriété [S2] (pattern n-aire W3C SWBP).",
            "compensation": "none"},
    "A02": {"approach": "Annotations d'axiome (owl:Axiom) : rapport ; propriété de provenance seulement si l'humain la demande.",
            "rationale": "Pas de métadonnées sur les arêtes [S2].",
            "compensation": "documentation"},
    "A03": {"approach": "owl:deprecated : élément exclu du schéma (option : conservé avec drapeau [Obsolete] / commentaire).",
            "rationale": "Un type ou une propriété obsolète encombre la recherche et les facettes.",
            "compensation": "documentation"},
    "M01": {"approach": "En-tête d'ontologie (versionIRI, versionInfo, dcterms) : repris dans l'en-tête des fichiers générés.",
            "rationale": "Pas de métadonnées de schéma côté plateforme ; la traçabilité reste dans le code.",
            "compensation": "documentation"},
    "M02": {"approach": "owl:imports : charger la fermeture hors-ligne ; sinon termes importés = références externes + constat.",
            "rationale": "Le schéma généré doit être autonome ; un terme importé non résolu reste un nœud de référence ou une propriété texte.",
            "compensation": "documentation"},
    "I02": {"approach": "owl:sameAs : fusion des nœuds (clé canonique, alias en propriété liste) ; arête SameAs en option.",
            "rationale": "Deux nœuds pour une même entité casseraient l'idempotence de la clé [S2].",
            "compensation": "materialization"},
    "I03": {"approach": "differentFrom / AllDifferent : aucun effet (UNA) ; renforcement noté au rapport.",
            "rationale": "Le graphe suppose des entités distinctes si les clés diffèrent.",
            "compensation": "none"},
    "I04": {"approach": "NegativePropertyAssertion : contrôle dans le connecteur (lien ou valeur interdits).",
            "rationale": "Pas de contrainte négative côté plateforme.",
            "compensation": "validation"},
    "I05": {"approach": "Individu à plusieurs types : type principal + discriminant (propriété booléenne ou texte).",
            "rationale": "Un nœud = un seul type [S1][S2].",
            "compensation": "human"},
    "G01": {"approach": "Construct non représentable : listé au rapport, jamais supprimé en silence.",
            "rationale": "Aucune perte silencieuse (D-023).",
            "compensation": "documentation"},
}

# Option recommandée pour Curiosity (vocabulaire de samples/trap/expected-findings.yaml) et alternatives.
_OPTIONS: dict[str, tuple[str, tuple[str, ...]]] = {
    "A01": ("schema_metadata", ("ignore",)), "A02": ("report", ("provenance_property",)),
    "A03": ("exclude", ("flag_deprecated",)),
    "C01": ("node_type", ()), "C02": ("flatten_into_leaves", ("primary_parent_discriminator",)),
    "C03": ("primary_parent_discriminator", ("flatten_into_leaves",)),
    "C04": ("merge_into_leaves", ("node_type",)), "C05": ("merge_types", ("doc_only",)),
    "C06": ("materialize_at_ingest", ("validation", "doc_only")), "C07": ("validation", ("doc_only",)),
    "C08": ("reference_nodes", ("enum_property",)), "C09": ("doc_only", ()),
    "C10": ("primary_parent_discriminator", ("flatten_into_leaves",)),
    "C11": ("materialize_at_ingest", ("doc_only",)), "C12": ("reference_nodes", ("rename",)),
    "C13": ("materialize_at_ingest", ("doc_only",)),
    "D01": ("property", ()), "D02": ("attach_to_users", ("ignore",)), "D03": ("duplicate_per_type", ()),
    "D04": ("list_property", ("reference_nodes",)), "D05": ("native_type", ("string_lexical",)),
    "D06": ("per_language_property", ("string_property",)), "D07": ("scalar", ()),
    "D08": ("enum_property", ("reference_nodes",)), "D09": ("validation", ("native_type",)),
    "D10": ("string_property", ()), "D11": ("most_specific_type", ("duplicate_per_type",)),
    "D12": ("native_type", ("validation",)), "D13": ("validation", ("ignore",)),
    "G01": ("report", ()),
    "I01": ("reference_nodes", ("ignore",)), "I02": ("merge_nodes", ("same_as_edge",)),
    "I03": ("noop_una", ()), "I04": ("validation", ("report",)),
    "I05": ("primary_parent_discriminator", ("flatten_into_leaves",)),
    "K01": ("uri_key", ("node_key",)), "K02": ("uri_key", ("key_concat", "node_key")),
    "K03": ("generated_key", ("uri_key",)), "K04": ("generated_key", ("uri_key",)),
    "K05": ("key_concat", ("generated_key",)),
    "M01": ("schema_metadata", ()), "M02": ("external_reference", ("load_closure_offline",)),
    "N01": ("rename", ()),
    "O01": ("edge_pair", ("single_direction",)), "O02": ("edge_pair", ("report",)),
    "O03": ("edge_pair", ("merge_relationship_types",)), "O04": ("edge_pair", ("resolve_named_inverse",)),
    "O05": ("self_reverse", ("edge_pair",)), "O06": ("materialize_closure", ("var_length_query", "ignore")),
    "O07": ("most_specific_type", ("materialize_closure",)),
    "O08": ("materialize_closure", ("path_query", "ignore")),
    "O09": ("validation", ("ignore",)), "O10": ("validation", ("ignore",)), "O11": ("validation", ("ignore",)),
    "O12": ("validation", ("property",)), "O13": ("validation", ("ignore",)),
    "O14": ("reverse_traversal", ("resolve_named_inverse",)), "O15": ("validation", ("ignore",)),
    "O16": ("validation", ("ignore",)), "O17": ("materialize_at_ingest", ("validation",)),
    "O18": ("ignore", ()), "O19": ("merge_relationship_types", ("edge_pair",)),
    "O20": ("validation", ("ignore",)), "O21": ("intersection_domain", ("most_specific_type",)),
    "R01": ("keep_node", ("dereify_relationship",)), "R02": ("keep_node", ()),
    "X00": ("report", ()),
}

for _rule, _extra in _EXTRA.items():
    RECOMMENDATIONS.setdefault(_rule, _extra)
for _rule, (_opt, _alts) in _OPTIONS.items():
    if _rule in RECOMMENDATIONS:
        RECOMMENDATIONS[_rule]["option"] = _opt
        RECOMMENDATIONS[_rule]["alternatives"] = list(_alts)

# La cible Curiosity impose une seule option pour K01 dans l'oracle ; K02 et K03 documentent la concaténation.
CATALOGUE_RULES: tuple[str, ...] = tuple(sorted(r for r in RECOMMENDATIONS if r != "X00"))
