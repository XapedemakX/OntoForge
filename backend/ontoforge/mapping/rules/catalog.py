"""Catalogue normatif des règles de transposition OWL 2 / SHACL → LPG (source de docs/RULES.md).

66 règles de transposition (ARCHITECTURE §4 corrigé par journal/L0/review-w3c-catalogue.md, D-031/D-031bis)
+ 3 règles d'outillage (S01, S02 : SHACL ; G02 : décision invalide).
Identifiants d'options = vocabulaire normatif de samples/trap/expected-findings.yaml (D-031).

Champs : family, construct, detect (texte), severity, title, options {id: {label, impact, targets?}},
reco {curiosity, neo4j}, rationale {cible|*: texte}, compensation (none | validation | materialization |
query | documentation | rename | human), it1 (règle Must de D-032).
"""
from __future__ import annotations

C, N = "curiosity", "neo4j"
BOTH = (C, N)
IT1 = set("C01 C02 C03 C04 C05 C07 K01 K02 K03 D01 D02 D04 D05 D06 D07 O01 O02 O03 O04 O05 O06 O07 O09 O10 "
          "R01 R02 A01 N01".split())


def o(label: str, impact: str, targets=BOTH) -> dict:
    return {"label": label, "impact": impact, "targets": tuple(targets)}


def r(family, construct, detect, severity, title, options, reco, rationale, compensation):
    if isinstance(reco, str):
        reco = {C: reco, N: reco}
    if isinstance(rationale, str):
        rationale = {"*": rationale}
    return dict(family=family, construct=construct, detect=detect, severity=severity, title=title,
                options=options, reco=reco, rationale=rationale, compensation=compensation)


VALIDATION = o("Validation applicative", "La contrainte devient un contrôle exécuté à l'ingestion (connecteur) ou "
               "une requête de détection ; rien n'est bloqué nativement par la base.")
DOC = o("Documenter seulement", "Rien n'est généré : la sémantique est perdue pour les données, tracée au rapport.")
IGNORE = o("Ignorer", "Aucune génération ni contrôle ; l'axiome est seulement listé au rapport.")
REPORT = o("Lister au rapport", "Information conservée dans le rapport de transposition uniquement.")

RULES: dict[str, dict] = {
    # =========================================================================================== CLASSES
    "C01": r("classes", "owl:Class nommée", "Toute classe nommée déclarée.", "auto", "Classe → type de nœud",
             {"node_type": o("Type de nœud", "Un type de nœud [Node] (classe C#).", [C]),
              "label": o("Label", "Un label PascalCase.", [N])},
             {C: "node_type", N: "label"}, "Correspondance directe.", "none"),
    "C02": r("classes", "rdfs:subClassOf (parent nommé unique)", "Classe ayant exactement un parent nommé effectif.",
             "review", "Héritage simple",
             {"multi_label": o("Multi-labels", "Neo4j : le nœud porte son label et ceux de ses ancêtres (requêtes sur le "
                               "parent naturelles). Curiosity : pas de multi-type, repli en liste de types `types` "
                               "(propriété multivaluée) dans le type concret."),
              "flatten_into_leaves": o("Aplatir sur la racine concrète", "Les sous-classes de la hiérarchie sont repliées "
                                       "dans le type de nœud de la racine concrète (propriétés recopiées) avec un "
                                       "discriminant `<racine>Kind` ; leurs restrictions deviennent des validations "
                                       "filtrées par discriminant ; requêtes par sous-type = filtre."),
              "node_type": o("Type de nœud distinct", "Le sous-type garde son propre type de nœud, propriétés du parent "
                             "recopiées ; les relations du parent sont dupliquées vers lui (Curiosity).")},
             {C: "flatten_into_leaves", N: "multi_label"},
             {C: "Curiosity est mono-type (un nœud = une classe C#) : la hiérarchie s'aplatit, le discriminant reste "
                 "filtrable et utilisable en facette.",
              N: "Neo4j porte plusieurs labels par nœud : l'héritage passe sans perte de requêtabilité."}, "none"),
    "C03": r("classes", "Héritage multiple", "Classe ayant au moins deux parents nommés effectifs.", "review",
             "Héritage multiple",
             {"multi_label": o("Multi-labels", "Tous les parents deviennent des labels (Neo4j) ; Curiosity : liste de types."),
              "primary_parent_discriminator": o("Parent principal + discriminant", "Un parent principal porte le type ; "
                                                "les autres appartenances deviennent des booléens `is<Parent>`."),
              "node_type": o("Type de nœud distinct", "Type propre, propriétés de tous les parents recopiées.")},
             {C: "primary_parent_discriminator", N: "multi_label"},
             {C: "Mono-type : un seul ancêtre peut définir le type de nœud (le plus riche en propriétés).",
              N: "Aucune limite au nombre de labels."}, "human"),
    "C04": r("classes", "Classe probablement abstraite", "Heuristique OWA : classe avec sous-classes, sans instance "
             "directe, sans clé, impliquée dans au plus une propriété objet, hors disjointUnion (C10).", "review",
             "Classe probablement abstraite",
             {"merge_into_leaves": o("Fusionner dans les feuilles", "Pas de type de nœud : ses propriétés et relations "
                                     "sont recopiées dans chaque sous-type concret."),
              "secondary_label": o("Label secondaire seulement", "Type abstrait : le label est porté par les nœuds des "
                                   "sous-classes, jamais seul.", [N]),
              "node_type": o("Garder un type de nœud", "Type concret ; les sous-types s'y replient (Curiosity).")},
             {C: "merge_into_leaves", N: "secondary_label"},
             "Sous OWA, l'absence d'instance directe ne se prouve pas : c'est une heuristique à confirmer.", "query"),
    "C05": r("classes", "owl:equivalentClass entre classes nommées", "equivalentClass dont l'argument est nommé.",
             "review", "Classes nommées équivalentes",
             {"merge_types": o("Fusionner (nom canonique + alias)", "Un seul type ; l'autre IRI devient un alias "
                               "documenté (même extension : sans perte)."),
              "node_type": o("Deux types distincts", "Duplication des nœuds et des clés : à synchroniser.")},
             "merge_types", "EquivalentClasses(A B) avec A, B nommées : extensions identiques, la fusion ne perd rien.",
             "documentation"),
    "C06": r("classes", "Classe définie (equivalentClass anonyme : restriction / intersection)",
             "Classe nommée avec une définition nécessaire et suffisante.", "lost", "Classe définie (classification)",
             {"computed_label": o("Label calculé", "Job de classification (requête) rejoué après chaque ingestion."),
              "materialize_at_ingest": o("Matérialiser à l'ingestion", "Booléen `is<Classe>` calculé par le connecteur."),
              "doc_only": DOC},
             {C: "materialize_at_ingest", N: "computed_label"},
             "Aucun raisonneur côté LPG : l'appartenance définie doit être calculée et stockée, ou perdue.",
             "materialization"),
    "C07": r("classes", "owl:disjointWith / owl:AllDisjointClasses", "Classe déclarant des disjonctions.", "lost",
             "Disjonction de classes",
             {"validation": VALIDATION, "ignore": IGNORE}, "validation",
             {C: "Mono-type : la disjonction est garantie entre types distincts ; à valider si des classes sont fusionnées.",
              N: "Aucune contrainte native : requête de détection d'un nœud portant les deux labels."}, "validation"),
    "C08": r("classes", "owl:oneOf (classe énumérée)", "Classe dont la définition est une énumération d'individus.",
             "review", "Classe énumérée",
             {"reference_nodes": o("Nœuds de référence", "Un type, un nœud par valeur, relié par une relation : "
                                   "facettes liées, renommage sans dénormalisation."),
              "enum_property": o("Propriété énumérée", "Propriété texte + validation des valeurs ; la relation disparaît.")},
             "reference_nodes", "Les valeurs portent des labels multilingues : des nœuds de référence les conservent.",
             "validation"),
    "C09": r("classes", "owl:unionOf / owl:intersectionOf anonymes", "Union/intersection anonyme en équivalence ou "
             "en super-classe (hors définitions C06).", "lost", "Expression booléenne anonyme",
             {"doc_only": DOC, "secondary_label": o("Label calculé sur les membres", "Le nom de l'union devient un "
                                                     "label porté par les nœuds des classes membres.", [N])},
             {C: "doc_only", N: "secondary_label"},
             "Pas de type anonyme en LPG ; la sémantique ensembliste est perdue sauf label de regroupement.",
             "documentation"),
    "C10": r("classes", "owl:disjointUnionOf", "Classe partitionnée en sous-classes disjointes.", "review",
             "Union disjointe (partition)",
             {"primary_parent_discriminator": o("Type parent + discriminant obligatoire", "Un type de nœud parent + "
                                                "enum `<parent>Kind` obligatoire (exactement une valeur)."),
              "multi_label": o("Labels parent + enfants", "Labels parent et enfants + validation « exactement un "
                               "label enfant »."),
              "validation": VALIDATION},
             {C: "primary_parent_discriminator", N: "multi_label"}, "La partition devient une contrainte de complétude "
             "et d'exclusivité, à valider.", "validation"),
    "C11": r("classes", "owl:complementOf", "Complément dans une définition ou une super-classe.", "lost",
             "Complément de classe",
             {"computed_label": o("Label calculé par requête (NOT)", "Classification par absence de label/propriété : "
                                  "monde clos, à rejouer."),
              "materialize_at_ingest": o("Matérialiser à l'ingestion", "Booléen calculé par le connecteur."),
              "doc_only": DOC},
             {C: "materialize_at_ingest", N: "computed_label"},
             "Le complément OWL (monde ouvert) devient une négation par défaut (monde clos) : sur-classification possible.",
             "materialization"),
    "C12": r("classes", "Punning classe / individu (SS §5.9)", "Même IRI déclarée classe et individu.", "review",
             "Punning classe / individu",
             {"reference_nodes": o("Type + nœud de référence, noms distincts", "Le type de nœud (classe) et le nœud "
                                   "de référence (individu) coexistent sous des noms distincts."),
              "ignore": o("Ignorer l'individu", "L'usage individu est perdu.")},
             "reference_nodes", "Métamodélisation légale en OWL 2 DL ; en LPG, deux éléments distincts.", "documentation"),
    "C13": r("classes", "Axiome général d'inclusion (GCI)", "rdfs:subClassOf dont le sujet est anonyme.", "lost",
             "Axiome général d'inclusion",
             {"computed_label": o("Job de classification", "Requête qui pose le label conclu."),
              "materialize_at_ingest": o("Matérialiser à l'ingestion", "Booléen calculé par le connecteur."),
              "doc_only": DOC},
             {C: "materialize_at_ingest", N: "computed_label"}, "Règle d'inférence sans équivalent LPG.",
             "materialization"),
    # =========================================================================================== CLÉS
    "K01": r("keys", "Identité IRI d'un individu nommé", "Individu nommé (IRI).", "auto", "Identité IRI",
             {"uri_key": o("Clé = uri", "[Key] string = IRI (Curiosity).", [C]),
              "unique_constraint": o("Propriété uri + UNIQUE", "Identité RDF conservée, MERGE idempotent.", [N])},
             {C: "uri_key", N: "unique_constraint"}, "L'IRI est unique, stable et non vide.", "none"),
    "K02": r("keys", "owl:hasKey sur propriétés de données", "Axiome HasKey ne portant que des propriétés de données.",
             "review", "Clé OWL (hasKey)",
             {"node_key": o("Clé = propriétés hasKey", "Neo4j : NODE KEY (existence + unicité, Enterprise ; UNIQUE en "
                            "Community). Curiosity : [Key] = la propriété. RENFORCEMENT : hasKey n'impose ni existence "
                            "ni unicité."),
              "unique_constraint": o("UNIQUE seulement", "Unicité sans existence obligatoire.", [N]),
              "uri_key": o("Clé = uri, unicité validée", "La clé reste l'IRI ; l'unicité des valeurs hasKey devient une "
                           "validation applicative."),
              "key_concat": o("Concaténation", "Clé composite concaténée (séparateur '|').", [C])},
             {C: "uri_key", N: "node_key"},
             {C: "[Key] Curiosity doit être non vide pour chaque nœud : poser la clé sur une propriété que l'ontologie "
                 "ne rend pas obligatoire est un renforcement ; uri reste sûr, la clé métier est validée.",
              N: "hasKey (SS §9.5) infère sameAs entre individus nommés de mêmes valeurs ; NODE KEY ajoute l'existence "
                 "obligatoire : renforcement à faire valider."}, "validation"),
    "K03": r("keys", "Classe sans clé métier", "Classe concrète sans hasKey (ni ancêtre à clé).", "review",
             "Pas de clé métier",
             {"uri_key": o("Clé = uri", "Identifiant technique (IRI)."),
              "generated_key": o("Clé générée", "Hash déterministe des valeurs identifiantes ou IRI skolem "
                                 "`/.well-known/genid/` (instances sans IRI)."),
              "property": o("Choisir une propriété métier", "Arbitrage humain : la propriété devient la clé.")},
             "uri_key", "uri si les instances ont une IRI ; clé générée si elles sont anonymes (nœuds blancs).", "human"),
    "K04": r("keys", "Individu anonyme (nœud blanc, SS §5.6.2)", "Valeur objet nœud blanc typé.", "review",
             "Individu anonyme",
             {"generated_key": o("Clé générée", "hash(propriétaire + propriété + valeurs) ou IRI skolem."),
              "ignore": o("Ignorer", "L'individu n'est pas ingéré.")},
             "generated_key", "Un nœud blanc n'a pas d'IRI : aucune clé n'est dérivable (pas K01).", "materialization"),
    "K05": r("keys", "owl:hasKey incluant une propriété objet", "Axiome HasKey portant au moins une propriété objet.",
             "review", "Clé composite avec propriété objet",
             {"key_concat": o("Concaténation avec la clé de la cible", "Clé = valeur | clé du nœud cible.", [C]),
              "materialize_key": o("Copier la clé de la cible + NODE KEY", "Propriété `<cible>Key` recopiée à "
                                   "l'ingestion puis NODE KEY composite.", [N]),
              "uri_key": o("Clé = uri", "Unicité composite seulement validée.")},
             {C: "key_concat", N: "materialize_key"}, "Une clé LPG ne porte que des propriétés du nœud.", "materialization"),
    # =========================================================================================== DONNÉES
    "D01": r("data", "Propriété de données à domaine nommé unique", "Un seul rdfs:domain nommé.", "auto",
             "Propriété de données", {"property": o("Propriété", "Propriété typée sur le nœud.")}, "property",
             "Correspondance directe (le domaine RDFS infère ; il devient ici un contrat de schéma, monde clos).", "none"),
    "D02": r("data", "Propriété de données sans domaine", "Aucun rdfs:domain.", "review", "Propriété sans domaine",
             {"attach_to_users": o("Rattacher aux utilisateurs", "Posée sur les types qui l'utilisent (restrictions, "
                                   "shapes, assertions) ; non posée si elle n'est utilisée que via ses sous-propriétés."),
              "ignore": o("Ignorer", "Propriété non transposée.")},
             "attach_to_users", "Une propriété LPG appartient à un type de nœud.", "human"),
    "D03": r("data", "Domaine = owl:unionOf (union explicite)", "rdfs:domain [owl:unionOf (…)].", "review",
             "Domaine en union",
             {"duplicate_per_type": o("Dupliquer sur chaque type", "Même nom sur chaque membre de l'union.")},
             "duplicate_per_type", "Seule une union explicite autorise la duplication (≠ plusieurs rdfs:domain, D12).",
             "none"),
    "D04": r("data", "Propriété de données non fonctionnelle", "Ni FunctionalProperty, ni max/exactly 1, ni "
             "sh:maxCount 1.", "review", "Propriété non fonctionnelle",
             {"list_property": o("Liste", "Tableau homogène (T[] / LIST<T>)."),
              "scalar": o("Scalaire", "Une seule valeur ; valeurs multiples perdues à l'ingestion.")},
             "scalar", "OWA : l'absence de FunctionalProperty ne prouve pas la multivaluation : liste si plusieurs "
             "valeurs sont observées, scalaire sinon.", "none"),
    "D05": r("data", "Typage xsd avec perte", "decimal, hexBinary/base64Binary, dateTimeStamp, owl:real/rational, "
             "types hors carte OWL 2 (gYear, date, duration… : aussi W01).", "review", "Type de données avec perte",
             {"native_type": o("Type natif le plus proche", "decimal → flottant (précision), dateTimeStamp → date-heure "
                               "à fuseau, gYear → entier…"),
              "string_lexical": o("Forme lexicale en texte", "Exact mais non calculable / non comparable numériquement.")},
             "native_type", "Pas de décimal ni de binaire natifs en LPG.", "validation"),
    "D06": r("data", "Valeurs multilingues (rdf:PlainLiteral, @lang)", "Portée rdf:PlainLiteral / rdf:langString "
             "(non conforme, W01) ou littéraux à langue observés.", "review", "Valeurs multilingues",
             {"per_language_property": o("Une propriété par langue", "label_fr, label_en ; langues hors liste perdues."),
              "string_property": o("Texte sans langue", "Étiquette de langue perdue.")},
             "per_language_property", "Pas de littéral à langue en LPG.", "none"),
    "D07": r("data", "owl:FunctionalProperty (données)", "Propriété de données fonctionnelle.", "auto",
             "Propriété fonctionnelle", {"scalar": o("Scalaire", "Valeur unique (+ contrainte de type si l'édition le permet).")},
             "scalar", "Correspondance directe.", "none"),
    "D08": r("data", "DataOneOf (énumération de littéraux)", "Portée owl:oneOf de littéraux.", "review",
             "Énumération de littéraux",
             {"enum_property": o("Propriété énumérée + validation", "Texte + contrôle des valeurs (pas de contrainte "
                                 "d'énumération native)."),
              "reference_nodes": o("Nœuds de référence", "Une valeur = un nœud ; la propriété devient une relation.")},
             "enum_property", "Petit ensemble figé de littéraux.", "validation"),
    "D09": r("data", "Datatype défini / facettes", "rdfs:Datatype défini par owl:withRestrictions (min/max, pattern, "
             "length).", "review", "Datatype à facettes",
             {"validation": o("Type de base + validation", "Le type de base natif est utilisé ; bornes et motifs "
                              "deviennent des validations."),
              "native_type": o("Type de base seul", "Facettes perdues.")},
             "validation", "Aucune facette native en LPG.", "validation"),
    "D10": r("data", "Portée rdfs:Literal ou absente", "Portée non contrainte.", "review", "Littéral non typé",
             {"string_property": o("Texte", "Typage d'origine perdu.")}, "string_property",
             "Type inconnu : texte par défaut.", "none"),
    "D11": r("data", "rdfs:subPropertyOf entre propriétés de données", "Sous-propriété de données.", "lost",
             "Sous-propriété de données",
             {"most_specific_type": o("Propriété la plus spécifique", "La super-propriété n'est pas stockée : une "
                                      "requête sur le parent doit lister les sous-propriétés."),
              "materialize_closure": o("Dupliquer dans la super-propriété", "Valeur recopiée dans le parent (double écriture).")},
             "most_specific_type", "Pas de hiérarchie de propriétés en LPG.", "materialization"),
    "D12": r("data", "Plusieurs rdfs:domain / rdfs:range (données) = intersection", "Au moins deux domaines nommés ou "
             "deux portées.", "review", "Intersection de domaines / portées",
             {"native_type": o("Type natif de l'intersection", "Type le plus restrictif + validation des bornes."),
              "intersection_domain": o("Domaine = intersection", "Posée sur les nœuds appartenant à tous les "
                                       "domaines (souvent erreur de modélisation)."),
              "duplicate_per_type": o("Traiter comme une union", "Écart sémantique (rdfs2) : à n'utiliser que si "
                                      "l'ontologie est fautive.")},
             "native_type", "Plusieurs axiomes de domaine/portée se cumulent (RSEM rdfs2/rdfs3).", "validation"),
    "D13": r("data", "Restriction sur propriété de données", "some / only / cardinalité / onDataRange.", "review",
             "Restriction sur propriété de données",
             {"validation": o("Validation", "exactly 1 / min 1 → propriété obligatoire + contrôle."), "ignore": IGNORE},
             "validation", "Les restrictions OWL infèrent ; en LPG elles deviennent des contrôles (monde clos).",
             "validation"),
    # =========================================================================================== OBJETS
    "O01": r("objects", "Propriété objet à domaine et portée nommés uniques", "Un domaine et une portée nommés.",
             "auto", "Propriété objet → relation",
             {"edge_pair": o("Paire d'arêtes aller / retour", "Constante aller + retour, Link(a, b, aller, retour).", [C]),
              "relationship": o("Type de relation", "UPPER_SNAKE, un sens stocké.", [N])},
             {C: "edge_pair", N: "relationship"}, "Correspondance directe.", "none"),
    "O02": r("objects", "Propriété objet sans domaine ou sans portée", "Domaine ou portée absents.", "review",
             "Domaine / portée manquants",
             {"edge_pair": o("Résoudre puis paire d'arêtes", "Extrémités déduites des restrictions, shapes, assertions "
                             "et de l'inverse.", [C]),
              "relationship": o("Résoudre puis relation", "Extrémités déduites des restrictions, shapes, assertions et "
                                "de l'inverse.", [N]),
              "ignore": o("Ignorer", "Relation non transposée.")},
             {C: "edge_pair", N: "relationship"}, "Le connecteur doit savoir quels types relier.", "human"),
    "O03": r("objects", "Domaine / portée = owl:unionOf", "rdfs:domain ou rdfs:range [owl:unionOf (…)].", "review",
             "Domaine / portée en union",
             {"edge_pair": o("Une arête par paire de types", "Même nom d'arête pour chaque paire.", [C]),
              "relationship": o("Un type, plusieurs paires de labels", "Validation des paires autorisées.", [N])},
             {C: "edge_pair", N: "relationship"}, "Union explicite seulement (≠ plusieurs rdfs:range : O21).", "validation"),
    "O04": r("objects", "owl:inverseOf", "Paire de propriétés inverses.", "auto", "Propriétés inverses",
             {"edge_pair": o("Paire aller / retour", "Curiosity : retour natif gratuit. Neo4j : les deux sens stockés "
                             "(double écriture)."),
              "single_direction": o("Un seul sens stocké", "L'autre sens est traversé ; le nom inverse est documenté.", [N])},
             {C: "edge_pair", N: "single_direction"}, "Un seul fait, deux noms.", "none"),
    "O05": r("objects", "owl:SymmetricProperty", "Propriété symétrique.", "review", "Propriété symétrique",
             {"self_reverse": o("Arête = son propre retour", "Même constante dans les deux sens.", [C]),
              "undirected_query": o("Un sens stocké, requêtes non orientées", "MATCH (a)-[:T]-(b) ; sens stocké arbitraire.", [N]),
              "edge_pair": o("Stocker les deux sens", "Doublons à l'agrégation.")},
             {C: "self_reverse", N: "undirected_query"}, "Évite deux faits pour une relation symétrique.", "none"),
    "O06": r("objects", "owl:TransitiveProperty", "Propriété transitive.", "lost", "Propriété transitive",
             {"materialize_closure": o("Matérialiser la fermeture", "Arête dérivée `<nom>Transitive` recalculée après "
                                       "ingestion."),
              "var_length_query": o("Requête à longueur variable", "-[:T*1..]-> : compensation complète en lecture, "
                                    "aucune contrainte.", [N]),
              "ignore": IGNORE},
             {C: "materialize_closure", N: "var_length_query"},
             {C: "Pas de chemin de longueur variable documenté : la fermeture est matérialisée.",
              N: "Les chemins variables sont natifs en Cypher (compensation complète en lecture seulement)."},
             "materialization"),
    "O07": r("objects", "rdfs:subPropertyOf (objet)", "Sous-propriété objet (hors topObjectProperty).", "lost",
             "Sous-propriété objet",
             {"most_specific_type": o("Type le plus spécifique", "Seule la sous-relation est stockée ; requête parent = "
                                      "union de types."),
              "materialize_closure": o("Matérialiser aussi le parent", "Relation parente dérivée (double écriture).")},
             "most_specific_type", "Pas de hiérarchie de types de relation en LPG.", "materialization"),
    "O08": r("objects", "owl:propertyChainAxiom", "Propriété définie par une chaîne.", "lost", "Chaîne de propriétés",
             {"materialize_closure": o("Matérialiser le raccourci", "Arête dérivée recalculée après ingestion."),
              "path_query": o("Requête de chemin", "Non stocké ; calculé à la lecture.", [N])},
             {C: "materialize_closure", N: "path_query"}, "Aucune inférence côté LPG.", "materialization"),
    "O09": r("objects", "Fonctionnelle / max 1 / exactly 1 (objet)", "FunctionalProperty ou restriction max/exactly ≤ 1.",
             "review", "Cardinalité ≤ 1 d'une relation (max / exactly / fonctionnelle)",
             {"validation": VALIDATION, "ignore": IGNORE}, "validation",
             "Aucune contrainte de cardinalité de relation en LPG.", "validation"),
    "O10": r("objects", "some / min n (objet, non qualifiée)", "Restriction d'existence.", "review",
             "Existence d'une relation", {"validation": VALIDATION, "ignore": IGNORE}, "validation",
             "OWA : some n'oblige pas à connaître la valeur ; en LPG c'est un contrôle de complétude.", "validation"),
    "O11": r("objects", "only (allValuesFrom)", "Restriction universelle.", "lost", "Restriction universelle",
             {"validation": o("Validation du type de la cible", "Contrôle que la cible a le bon type."), "ignore": IGNORE},
             "validation", "only infère le type de la cible (OWA) ; ≠ sh:class qui le vérifie.", "validation"),
    "O12": r("objects", "hasValue", "Restriction de valeur.", "review", "Valeur imposée",
             {"validation": VALIDATION,
              "materialize_at_ingest": o("Poser la valeur à l'ingestion", "Relation / valeur créée par le connecteur.")},
             "validation", "Pas de valeur par défaut dans un schéma LPG.", "validation"),
    "O13": r("objects", "Réflexive / irréflexive / asymétrique", "Caractéristiques de propriété.", "lost",
             "Caractéristiques de propriété",
             {"validation": VALIDATION, "ignore": o("Ignorer", "Rien n'est généré (réflexivité : ne jamais matérialiser "
                                                    "les boucles).")},
             "validation", "Aucune contrainte native ; la réflexivité globale est souvent une erreur.", "validation"),
    "O14": r("objects", "ObjectInverseOf anonyme", "[owl:inverseOf :p] dans une restriction ou une chaîne.", "review",
             "Propriété inverse anonyme",
             {"reverse_traversal": o("Traversée inverse", "Lecture par le sens retour de la relation."),
              "resolve_named_inverse": o("Inverse nommé", "Utiliser l'inverse nommé s'il existe.")},
             "reverse_traversal", "Pas d'inverse anonyme en LPG, mais toute relation se traverse dans les deux sens.",
             "validation"),
    "O15": r("objects", "owl:InverseFunctionalProperty", "Propriété inverse-fonctionnelle.", "review",
             "Propriété inverse-fonctionnelle", {"validation": VALIDATION, "ignore": IGNORE}, "validation",
             "Au plus une relation entrante par cible : contrôle applicatif.", "validation"),
    "O16": r("objects", "Cardinalité qualifiée (onClass)", "min/max/exactly avec owl:onClass, propriété simple.",
             "review", "Cardinalité qualifiée", {"validation": VALIDATION, "ignore": IGNORE}, "validation",
             "Validation filtrée par type de la cible.", "validation"),
    "O17": r("objects", "owl:hasSelf", "Restriction ObjectHasSelf.", "lost", "Restriction hasSelf",
             {"materialize_at_ingest": o("Booléen matérialisé", "Booléen calculé à l'ingestion (boucle détectée)."),
              "validation": VALIDATION},
             {C: "materialize_at_ingest", N: "validation"}, "Une boucle n'est pas un concept de schéma LPG.",
             "materialization"),
    "O18": r("objects", "owl:topObjectProperty / topDataProperty en super-propriété", "subPropertyOf top.", "auto",
             "Super-propriété universelle", {"ignore": o("Ignorer (documenté)", "Aucun effet en LPG.")}, "ignore",
             "La propriété universelle relie tout à tout : sans contenu transposable.", "documentation"),
    "O19": r("objects", "owl:equivalentProperty", "Propriétés objet équivalentes.", "review", "Propriétés équivalentes",
             {"merge_relationship_types": o("Fusionner les types de relation", "Nom canonique + alias documenté."),
              "doc_only": o("Garder séparées", "Deux types de relation pour un même fait : à synchroniser.")},
             "merge_relationship_types", "Même extension : fusion sans perte.", "documentation"),
    "O20": r("objects", "owl:propertyDisjointWith / AllDisjointProperties", "Propriétés disjointes.", "lost",
             "Propriétés disjointes", {"validation": VALIDATION, "ignore": IGNORE}, "validation",
             "Deux relations ne peuvent relier la même paire : contrôle applicatif.", "validation"),
    "O21": r("objects", "Plusieurs rdfs:domain / rdfs:range (objet) = intersection", "Au moins deux domaines ou portées "
             "nommés.", "review", "Intersection de domaines / portées",
             {"intersection_domain": o("Domaine = intersection", "Relation depuis chaque domaine + validation "
                                       "« appartient à tous » (souvent erreur de modélisation)."),
              "most_specific_type": o("Classe la plus spécifique", "Si l'une subsume l'autre."),
              "duplicate_per_type": o("Traiter comme une union", "Écart sémantique : seulement si l'ontologie est fautive.")},
             "intersection_domain", "rdfs2/rdfs3 : le sujet est instance des DEUX classes ; à arbitrer.", "human"),
    # =========================================================================================== RÉIFICATION
    "R01": r("reification", "Classe de réification binaire", "Exactement 2 rôles objet fonctionnels (ou max/exactly 1) "
             "+ des propriétés de données, classe non cible d'autres relations.", "review", "Réification binaire",
             {"dereify_relationship": o("Relation porteuse de propriétés", "Plus de nœud intermédiaire ; la relation "
                                        "porte les propriétés et ne peut être cible d'autres relations.", [N]),
              "keep_node": o("Garder un nœud", "Un saut de plus, extensible.")},
             {C: "keep_node", N: "dereify_relationship"},
             {C: "Les arêtes Curiosity ne portent pas de propriétés : dé-réifier perdrait les attributs.",
              N: "Neo4j : les relations portent des propriétés, la réification binaire se dé-réifie."}, "none"),
    "R02": r("reification", "Relation n-aire (≥ 3 rôles)", "Au moins 3 rôles objet fonctionnels.", "review",
             "Relation n-aire", {"keep_node": o("Garder un nœud (pattern n-aire W3C SWBP)", "Seule représentation possible.")},
             "keep_node", "Une relation LPG relie exactement deux nœuds.", "none"),
    # =========================================================================================== ANNOTATIONS / MÉTA
    "A01": r("annotations", "Annotations (rdfs:comment, skos:*, dcterms:*)", "Entité portant des annotations au-delà "
             "de rdfs:label.", "auto", "Annotations",
             {"schema_metadata": o("Métadonnées du schéma", "Commentaires de documentation du code / schéma généré.")},
             "schema_metadata", "Documentation conservée avec le schéma.", "documentation"),
    "A02": r("annotations", "Annotations d'axiome (owl:Axiom)", "Réification d'axiome annotée.", "review",
             "Annotation d'axiome",
             {"report": REPORT, "provenance_property": o("Propriété de provenance", "Sur la relation correspondante "
                                                         "(Neo4j) ; sinon rapport.", [N])},
             "report", "Les méta-données d'axiome n'ont pas d'équivalent de schéma.", "documentation"),
    "A03": r("annotations", "owl:deprecated true", "Entité dépréciée.", "auto", "Entité dépréciée",
             {"exclude": o("Exclure", "Non générée."), "flag_deprecated": o("Garder avec drapeau", "Générée, marquée dépréciée.")},
             "exclude", "Une entité dépréciée ne doit pas entrer dans un nouveau schéma.", "none"),
    "M01": r("meta", "En-tête d'ontologie", "owl:Ontology (IRI, versionIRI, versionInfo, dcterms).", "auto",
             "Métadonnées d'ontologie", {"schema_metadata": o("En-tête du schéma généré", "Nom, version, IRI d'origine.")},
             "schema_metadata", "Traçabilité.", "documentation"),
    "M02": r("meta", "owl:imports", "Import déclaré.", "review", "Import d'ontologie",
             {"external_reference": o("Références externes", "Termes importés non chargés : référencés par IRI, constat."),
              "load_closure_offline": o("Charger la fermeture (cache hors-ligne)", "Nécessite une copie locale.")},
             "external_reference", "Outil hors-ligne : la fermeture d'import n'est pas résolue.", "human"),
    "G01": r("general", "Construct non représentable (OntoModel.unmapped)", "Triplets non consommés par une règle.",
             "lost", "Construct non transposé", {"report": REPORT}, "report",
             "Aucune perte silencieuse : tout ce qui n'est pas transposé est listé.", "documentation"),
    # =========================================================================================== INDIVIDUS
    "I01": r("individuals", "Individu nommé", "Individu déclaré dans l'ontologie.", "review", "Individu",
             {"reference_nodes": o("Nœud de référence", "Ingéré comme donnée de référence (facettes)."),
              "ignore": o("Ignorer", "Donnée d'exemple non ingérée.")},
             "reference_nodes", "Membres d'énumérations et référentiels → nœuds ; autres individus : données d'exemple.",
             "human"),
    "I02": r("individuals", "owl:sameAs", "Individus identiques.", "lost", "Identité (sameAs)",
             {"merge_nodes": o("Fusion des nœuds", "Clé canonique + alias."),
              "same_as_edge": o("Relation SAME_AS", "Deux nœuds reliés ; requêtes à adapter.")},
             "merge_nodes", "Pas d'UNA en OWL ; le LPG suppose l'UNA : fusion explicite.", "materialization"),
    "I03": r("individuals", "owl:differentFrom / owl:AllDifferent", "Assertions de différence.", "auto",
             "Différence d'individus", {"noop_una": o("Aucun effet (UNA)", "Le LPG suppose l'UNA partout (renforcement).")},
             "noop_una", "Déjà garanti par des clés distinctes.", "none"),
    "I04": r("individuals", "owl:NegativePropertyAssertion", "Assertion négative.", "lost", "Assertion négative",
             {"validation": o("Validation (relation / valeur interdite)", "Contrôle applicatif."), "ignore": IGNORE},
             "validation", "Pas de fait négatif en LPG (monde clos : l'absence suffit, l'interdiction se valide).",
             "validation"),
    "I05": r("individuals", "Individu à plusieurs types", "Types non reliés par subsomption.", "review",
             "Individu multi-typé",
             {"multi_label": o("Multi-labels", "Tous les types en labels."),
              "primary_parent_discriminator": o("Type principal + discriminant", "Un type porte le nœud ; les autres en "
                                                "discriminants.")},
             {C: "primary_parent_discriminator", N: "multi_label"}, "Mono-type Curiosity.", "human"),
    # =========================================================================================== NOMMAGE
    "N01": r("naming", "Conventions de nommage / collisions", "Nom hors convention (snake_case, tiret…) ou collision "
             "après normalisation (insensible à la casse).", "auto", "Nommage",
             {"rename": o("Renommer", "Nom normalisé (Curiosity : PascalCase ; Neo4j : PascalCase / UPPER_SNAKE / "
                          "camelCase) ; collision → préfixe `has`."),
              "ignore": o("Garder le nom", "Collision possible dans le code généré.")},
             "rename", "Conventions de la cible ; noms uniques exigés.", "rename"),
    # =========================================================================================== OUTILLAGE
    "S01": r("shacl", "Conflit OWL / SHACL", "Contrainte SHACL incompatible avec l'axiome OWL (cardinalité, type).",
             "review", "Conflit OWL / SHACL",
             {"shacl_wins": o("Priorité aux shapes", "Le schéma suit la shape (contrat de données)."),
              "owl_wins": o("Priorité à OWL", "La shape est ignorée pour ce point.")},
             "shacl_wins", "Les shapes décrivent le contrat de données ; OWL décrit ce qui est inférable.", "human"),
    "S02": r("shacl", "Propriété SHACL non déclarée en OWL", "Chemin de shape absent de l'ontologie.", "review",
             "Propriété issue des shapes",
             {"property": o("Ajouter la propriété", "Créée depuis la shape (type sh:datatype)."), "ignore": IGNORE},
             "property", "Les shapes complètent le schéma.", "none"),
    "G02": r("general", "Décision invalide", "Option inconnue pour le constat visé.", "review", "Décision ignorée",
             {"report": REPORT}, "report", "La recommandation est appliquée à la place.", "human"),
}

TRANSPOSITION_RULES = [k for k in RULES if k not in ("S01", "S02", "G02")]
assert len(TRANSPOSITION_RULES) == 66, len(TRANSPOSITION_RULES)
