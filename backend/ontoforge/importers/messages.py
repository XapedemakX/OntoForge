"""Messages lisibles des importeurs (L48), français et anglais. Les codes sont stables (testés) ; les paramètres sont communs aux deux langues."""
from __future__ import annotations

from typing import Any

NOTICES: dict[str, tuple[str, str]] = {
    "too_many_notices": ("Plus de {n} avis : les suivants ne sont pas listés.", "More than {n} notices: the rest are not listed."),
    "lex_unterminated_comment": ("Commentaire non terminé dans {file} : le reste du fichier est ignoré.", "Unterminated comment in {file}: the rest of the file is ignored."),
    "lex_unterminated_string": ("Chaîne non terminée dans {file} : le reste du fichier est lu comme une chaîne.", "Unterminated string in {file}: the rest of the file is read as a string."),
    "lex_unterminated_ident": ("Identifiant entre guillemets non terminé dans {file}.", "Unterminated quoted identifier in {file}."),
    "table_not_parsed": ("Table « {table} » non analysée (pas de liste de colonnes : CREATE TABLE … AS, LIKE, PARTITION OF…).", "Table “{table}” not parsed (no column list: CREATE TABLE … AS, LIKE, PARTITION OF…)."),
    "duplicate_table": ("Table « {table} » définie deux fois : la première définition est gardée.", "Table “{table}” defined twice: the first definition is kept."),
    "inherits": ("La table « {table} » utilise l'héritage de tables (INHERITS) : la hiérarchie n'est pas reprise, à modéliser par sous-classes si utile.", "Table “{table}” uses table inheritance (INHERITS): the hierarchy is not imported; model it with subclasses if useful."),
    "pk_twice": ("Table « {table} » : plusieurs clés primaires déclarées, la première est gardée.", "Table “{table}”: several primary keys declared, the first is kept."),
    "duplicate_column": ("Colonne « {column} » déclarée deux fois dans « {table} » : la première est gardée.", "Column “{column}” declared twice in “{table}”: the first is kept."),
    "unknown_type": ("Colonne {table}.{column} : type « {type} » inconnu, xsd:string utilisé.", "Column {table}.{column}: unknown type “{type}”, xsd:string used."),
    "syntax_skipped": ("Instruction illisible ignorée dans {file} (ligne {line}).", "Unreadable statement skipped in {file} (line {line})."),
    "fk_target_missing": ("La table « {table} » est référencée mais absente du script : classe vide créée, à compléter.", "Table “{table}” is referenced but missing from the script: an empty class was created, to be completed."),
    "fk_to_association": ("{table} : une clé étrangère vise une table d'association ({target}) ; relation non reprise.", "{table}: a foreign key targets an association table ({target}); relation not imported."),
    "composite_fk": ("Clé étrangère composite {table} ({columns}) vers {target} : une seule propriété objet, les colonnes ne sont pas appariées une à une.", "Composite foreign key {table} ({columns}) to {target}: a single object property, columns are not paired one by one."),
    "reified_class": ("« {table} » a deux clés étrangères et des colonnes en plus : classe réifiée (une propriété objet par clé étrangère).", "“{table}” has two foreign keys plus extra columns: reified class (one object property per foreign key)."),
    "degraded_type": ("{table}.{column} : le type « {type} » n'existe pas dans la table de datatypes OWL 2 ; xsd:{xsd} utilisé (la précision est perdue).", "{table}.{column}: type “{type}” is not in the OWL 2 datatype map; xsd:{xsd} used (precision is lost)."),
    "tinyint1_as_boolean": ("{table}.{column} : TINYINT(1) lu comme booléen (usage MySQL courant) ; à vérifier.", "{table}.{column}: TINYINT(1) read as boolean (usual MySQL use); to check."),
    "float_ambiguous": ("{table}.{column} : FLOAT sans précision ; sa taille réelle dépend du moteur.", "{table}.{column}: FLOAT without precision, its real size depends on the engine."),
    "bit_as_string": ("{table}.{column} : champ de bits lu comme chaîne.", "{table}.{column}: bit field read as a string."),
    "rowversion": ("{table}.{column} : version de ligne SQL Server lue comme xsd:hexBinary.", "{table}.{column}: SQL Server row version read as xsd:hexBinary."),
    "json_as_string": ("{table}.{column} : JSON / XML lu comme chaîne.", "{table}.{column}: JSON / XML read as a string."),
    "geo_as_string": ("{table}.{column} : type géométrique lu comme chaîne (WKT).", "{table}.{column}: geometric type read as a string (WKT)."),
    "set_as_string": ("{table}.{column} : SET MySQL lu comme chaîne (valeurs multiples non modélisées).", "{table}.{column}: MySQL SET read as a string (multiple values not modelled)."),
    "array_column": ("{table}.{column} : colonne tableau, propriété à valeurs multiples.", "{table}.{column}: array column, multi-valued property."),
    "no_primary_key": ("La table « {table} » n'a pas de clé primaire : aucune clé (owl:hasKey) proposée.", "Table “{table}” has no primary key: no key (owl:hasKey) proposed."),
    "key_from_unique": ("« {table} » : sans clé primaire, la contrainte UNIQUE ({columns}) sert de clé.", "“{table}”: without a primary key, the UNIQUE constraint ({columns}) is used as the key."),
    "unique_nullable": ("« {table} » : UNIQUE sur colonnes nullables ({columns}) non reprise comme clé (hasKey ne tolère pas l'absence de valeur comme SQL).", "“{table}”: UNIQUE on nullable columns ({columns}) not imported as a key."),
    "association_collapsed": ("Table d'association « {table} » transformée en propriété objet {source} → {target} (sens arbitraire, pas d'inverse).", "Association table “{table}” turned into an object property {source} → {target} (arbitrary direction, no inverse)."),
    "csv_empty": ("Fichier CSV {file} vide : ignoré.", "CSV file {file} is empty: skipped."),
    "csv_sampled": ("{file} : seules les {rows} premières lignes servent à déduire les types.", "{file}: only the first {rows} rows are used to infer types."),
    "csv_delimiter": ("{file} : séparateur détecté « {delimiter} ».", "{file}: detected delimiter “{delimiter}”."),
    "csv_duplicate_header": ("{file} : colonne « {column} » en double, renommée.", "{file}: duplicate column “{column}”, renamed."),
    "csv_header_numeric": ("{file} : la première ligne ressemble à des données, pas à un en-tête.", "{file}: the first row looks like data, not a header."),
    "csv_no_name": ("{file} : nom de classe non déterminé, « Record » utilisé.", "{file}: class name not determined, “Record” used."),
    "csv_name_clash": ("{file} : le nom de classe « {name} » existe déjà.", "{file}: class name “{name}” already exists."),
    "decimal_comma": ("{column} : nombres à virgule décimale, lus comme chaînes (xsd:decimal exige un point).", "{column}: numbers with a decimal comma, read as strings (xsd:decimal requires a dot)."),
    "date_format": ("{column} : dates dans un format non ISO (jj/mm/aaaa…), lues comme chaînes.", "{column}: dates in a non-ISO format, read as strings."),
    "assumed_key": ("{entity} : la colonne « {column} » est supposée être l'identifiant (owl:hasKey) : à confirmer.", "{entity}: column “{column}” is assumed to be the identifier (owl:hasKey): to confirm."),
    "no_key_candidate": ("{entity} : aucun identifiant évident, aucune clé proposée.", "{entity}: no obvious identifier, no key proposed."),
    "external_ref": ("Référence externe {ref} non suivie (aucun accès réseau ni disque) : classe vide créée.", "External reference {ref} not followed (no network or disk access): an empty class was created."),
    "nullable_required": ("{entity}.{property} : obligatoire mais nul autorisé, non imposé.", "{entity}.{property}: required but null allowed, not enforced."),
    "required_array_empty": ("{entity}.{property} : liste obligatoire sans minItems, non imposée.", "{entity}.{property}: required list without minItems, not enforced."),
    "union_as_string": ("{entity}.{property} : union de types non réductible, lue comme chaîne.", "{entity}.{property}: irreducible type union, read as a string."),
    "mixed_type": ("{entity}.{property} : types multiples ({types}), lus comme chaîne.", "{entity}.{property}: several types ({types}), read as a string."),
    "pattern_dialect": ("Les motifs (pattern) sont repris tels quels : ECMAScript côté JSON Schema, expression SPARQL côté SHACL ; vérifier les cas limites.", "Patterns are copied as is: ECMAScript in JSON Schema, SPARQL regex in SHACL; check edge cases."),
    "json_no_classes": ("Aucun objet trouvé dans le schéma.", "No object found in the schema."),
    "excluded": ("« {name} » exclue de l'import à votre demande.", "“{name}” excluded from the import at your request."),
    "class_renamed": ("Le nom de classe « {name} » existait déjà : renommée {to}.", "Class name “{name}” already existed: renamed {to}."),
    "relation_dropped": ("{entity} : la relation « {relation} » vise une classe exclue, elle n'est pas importée.", "{entity}: relation “{relation}” targets an excluded class, it is not imported."),
    "degraded_date": ("{table}.{column} : le type « {type} » n'existe pas dans la table de datatypes OWL 2 ; xsd:dateTime utilisé. Les valeurs de date devront être complétées en date-heure à l'ingestion (par exemple T00:00:00).", "{table}.{column}: type “{type}” is not in the OWL 2 datatype map; xsd:dateTime used. Date values must be completed to date-times at ingestion (for example T00:00:00)."),
    "bound_tz_assumed": ("{entity} : une borne de date de « {prop} » est complétée en UTC (Z), la colonne ayant un fuseau horaire.", "{entity}: a date bound of “{prop}” is completed in UTC (Z), the column being time-zone aware."),
    "union_reduced": ("{entity} : la relation « {relation} » ne garde qu'une classe après exclusion : portée simple (owl:unionOf exige deux membres).", "{entity}: relation “{relation}” keeps a single class after exclusion: plain range (owl:unionOf needs two members)."),
    "union_empty": ("{entity} : la relation « {relation} » n'a plus aucune classe de portée après exclusion.", "{entity}: relation “{relation}” has no range class left after exclusion."),
    "bound_dropped": ("{entity} : la borne « {value} » de « {prop} » n'est pas une valeur valide du type de la colonne, elle n'est pas importée.", "{entity}: bound “{value}” of “{prop}” is not a valid value of the column type, it is not imported."),
    "check_contradiction": ("{table} : plusieurs CHECK sur « {column} » n'ont aucune valeur commune, énumération non importée.", "{table}: several CHECKs on “{column}” share no value, enumeration not imported."),
    "check_intersected": ("{table} : plusieurs CHECK sur « {column} » sont cumulés (ET) : seules les valeurs communes sont retenues.", "{table}: several CHECKs on “{column}” are combined (AND): only the common values are kept."),
    "key_dropped": ("{entity} : une clé fait référence à un élément exclu, elle est retirée.", "{entity}: a key refers to an excluded element, it is dropped."),
}

IGNORED: dict[str, tuple[str, str]] = {
    "index": ("Index (hors UNIQUE simple)", "Indexes (other than plain UNIQUE)"),
    "default": ("Valeurs par défaut", "Default values"),
    "identity": ("Colonnes auto-incrémentées / identité (générées par la base)", "Auto-increment / identity columns (generated by the database)"),
    "collation": ("Jeux de caractères et collations", "Character sets and collations"),
    "view": ("Vues", "Views"), "routine": ("Fonctions et procédures", "Functions and procedures"), "trigger": ("Déclencheurs", "Triggers"),
    "sequence": ("Séquences", "Sequences"), "data": ("Données (INSERT, COPY…)", "Data (INSERT, COPY…)"),
    "session": ("Paramètres de session et transactions", "Session settings and transactions"), "grant": ("Droits d'accès", "Grants"),
    "drop": ("Suppressions (DROP)", "Drops"), "alter_other": ("ALTER TABLE hors ajout de contrainte ou de colonne", "ALTER TABLE other than adding a constraint or a column"),
    "comment_other": ("Commentaires hors table et colonne", "Comments on other objects"), "other_statement": ("Autres instructions", "Other statements"),
    "temp_table": ("Tables temporaires", "Temporary tables"), "table_other": ("Éléments de table non reconnus", "Unrecognised table elements"),
    "storage": ("Options de stockage (moteur, partitions, espaces)", "Storage options (engine, partitions, tablespaces)"),
    "check_complex": ("Contraintes CHECK non traduites (à porter en validation applicative)", "CHECK constraints not translated (to carry as application validation)"),
    "computed": ("Colonnes calculées (expression non reprise)", "Computed columns (expression not imported)"),
    "fk_action": ("Actions de clé étrangère (ON DELETE / ON UPDATE)", "Foreign key actions (ON DELETE / ON UPDATE)"),
    "json_keyword": ("Mots-clés JSON Schema non traduits", "JSON Schema keywords not translated"),
    "json_union_def": ("Définitions en oneOf / anyOf de références", "oneOf / anyOf definitions of references"),
    "json_ref_unresolved": ("Références $ref locales introuvables", "Local $ref references not found"),
    "json_free_object": ("Objets libres sans propriétés", "Free-form objects without properties"),
    "key_uniqueness": ("Unicité des clés : non exprimable en SHACL Core (à vérifier à l'ingestion)", "Key uniqueness: not expressible in SHACL Core (to check at ingestion)"),
}

REFUSALS: dict[str, tuple[str, str]] = {
    "too_slow": ("Analyse interrompue : plus de {seconds} s.", "Analysis stopped: more than {seconds} s."),
    "ident_too_long": ("Identifiant de plus de {max} caractères (ligne {line}).", "Identifier longer than {max} characters (line {line})."),
    "too_deep": ("Imbrication trop profonde (plus de {max} niveaux).", "Nesting too deep (more than {max} levels)."),
    "too_many_tokens": ("Script trop long (plus de {max} éléments lexicaux).", "Script too long (more than {max} tokens)."),
    "syntax": ("Instruction illisible (ligne {line}).", "Unreadable statement (line {line})."),
    "too_many_tables": ("Trop de tables ou de classes (plus de {max}).", "Too many tables or classes (more than {max})."),
    "too_many_columns": ("Trop de colonnes (plus de {max} par table, {total} au total).", "Too many columns (more than {max} per table, {total} in total)."),
    "too_many_nodes": ("Document trop volumineux (plus de {max} nœuds).", "Document too large (more than {max} nodes)."),
    "json_invalid": ("JSON invalide : {detail}", "Invalid JSON: {detail}"),
    "json_not_schema": ("{file} n'est pas un JSON Schema reconnu.", "{file} is not a recognised JSON Schema."),
    "not_text": ("Le fichier n'est pas du texte.", "The file is not text."),
    "no_file": ("Aucun fichier reçu.", "No file received."),
    "too_many_files": ("Trop de fichiers (maximum {max}).", "Too many files (maximum {max})."),
    "too_big": ("{file} dépasse {max} Mo.", "{file} exceeds {max} MB."),
    "too_big_total": ("Les fichiers dépassent {max} Mo au total.", "The files exceed {max} MB in total."),
    "missing_digest": ("L'application exige l'empreinte de l'aperçu (expect_digest) : relancez l'aperçu.", "Applying requires the preview digest (expect_digest): run the preview again."),
    "empty_file": ("{file} est vide.", "{file} is empty."),
    "unknown_kind": ("Format non reconnu : attendu SQL (DDL), CSV ou JSON Schema.", "Unrecognised format: expected SQL (DDL), CSV or JSON Schema."),
    "mixed_kinds": ("Les fichiers sont de formats différents : déposez un seul format à la fois.", "The files are of different formats: drop one format at a time."),
    "sql_no_table": ("Aucune instruction CREATE TABLE reconnue.", "No CREATE TABLE statement recognised."),
    "nothing_found": ("Rien à importer : aucune classe trouvée.", "Nothing to import: no class found."),
    "bad_base_iri": ("IRI de base invalide (http, https ou urn, sans espace).", "Invalid base IRI (http, https or urn, no spaces)."),
    "stale_preview": ("Le résultat a changé depuis l'aperçu : relancez l'aperçu.", "The result changed since the preview: run the preview again."),
    "bad_options": ("Options illisibles.", "Unreadable options."),
}

DECISIONS: dict[str, tuple[str, str]] = {
    "association": ("« {table} » est une table d'association : propriété objet N-N ou classe ?", "“{table}” is an association table: N-N object property or class?"),
    "subclass": ("« {table} » partage sa clé avec « {parent} » : propriété objet ou sous-classe ?", "“{table}” shares its key with “{parent}”: object property or subclass?"),
    "reference": ("{entity}.{column} ressemble à une référence vers {target} : simple valeur ou relation ?", "{entity}.{column} looks like a reference to {target}: plain value or relation?"),
}


class _Safe(dict):
    def __missing__(self, k: str) -> str:
        return "{" + k + "}"


def fmt(table: dict[str, tuple[str, str]], code: str, lang: str, params: dict[str, Any] | None = None) -> str:
    pair = table.get(code)
    if pair is None:
        return code
    return pair[0 if lang == "fr" else 1].format_map(_Safe(params or {}))


def notice(code: str, lang: str, params: dict[str, Any]) -> str:
    return fmt(NOTICES, code, lang, params)


def refusal(code: str, lang: str, params: dict[str, Any]) -> str:
    return fmt(REFUSALS, code, lang, params)
