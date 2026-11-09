# Glossaire

Vocabulaire d'OntoForge, du monde OWL/SHACL et du monde property graph. Les références « SS » sont à la *OWL 2 Structural Specification*.

## Ontologie et W3C

| Terme | Définition |
|---|---|
| **OWL 2** | Langage W3C d'ontologies (logique de description). OntoForge lit et écrit OWL 2 / RDFS. |
| **RDF / Turtle** | Modèle de données en triplets (sujet, prédicat, objet) et sa syntaxe lisible. Format d'échange principal d'OntoForge ; RDF/XML, JSON-LD, N-Triples, N3, TriG sont aussi lus. |
| **IRI** | Identifiant global d'une ressource (classe, propriété, individu). Toujours absolu dans les modèles d'OntoForge ; abrégé en **CURIE** (`am:Vehicle`) à l'affichage. |
| **Classe** | Ensemble d'individus (`owl:Class`). Devient un type de nœud (Curiosity) ou un label (Neo4j). |
| **Propriété objet** | Relation entre deux individus (`owl:ObjectProperty`). Devient une arête / relation. |
| **Propriété de données** | Relation entre un individu et un littéral (`owl:DatatypeProperty`). Devient une propriété de nœud. |
| **Individu** | Instance nommée (`owl:NamedIndividual`) ou anonyme (nœud blanc). |
| **Nœud blanc (bnode)** | Individu sans IRI. Pas de clé dérivable : règle K04. |
| **Restriction** | Classe anonyme définie par une propriété et un quantificateur : `some` (∃), `only` (∀), `min`/`max`/`exactly` (cardinalités), `value`, `self`. |
| **Domaine / portée** | `rdfs:domain` / `rdfs:range` : **infèrent** le type du sujet / de l'objet (rdfs2/rdfs3) ; ils ne contraignent pas. Plusieurs domaines = **intersection**. |
| **Union (`owl:unionOf`)** | « A ou B ». Seule une union explicite autorise la duplication d'une propriété (D03/O03). |
| **Propriété fonctionnelle** | Au plus une valeur par sujet (`owl:FunctionalProperty`). |
| **Propriété simple** | Propriété ni transitive, ni définie par chaîne, ni super-propriété / inverse d'une telle propriété (SS §11.2) : seules les propriétés simples admettent des cardinalités en OWL 2 DL. |
| **`owl:hasKey`** | Clé d'une classe. N'impose **ni existence ni unicité** : il infère `sameAs` entre individus nommés de mêmes valeurs (SS §9.5). |
| **Punning** | Même IRI utilisée comme classe et comme individu (SS §5.9), légale en OWL 2 DL (règle C12). |
| **GCI** | *General Class Inclusion* : axiome `subClassOf` dont le sujet est anonyme (règle C13). |
| **OWA (monde ouvert)** | Ce qui n'est pas affirmé n'est pas faux, simplement inconnu. Hypothèse d'OWL. |
| **CWA (monde clos)** | Ce qui n'est pas dans la base est faux. Hypothèse des property graphs. |
| **UNA** | *Unique Name Assumption* : deux noms différents désignent deux choses différentes. Absente d'OWL, supposée par un property graph. |
| **Profils OWL 2 (DL, EL, QL, RL)** | Sous-ensembles d'OWL 2 à propriétés de calcul différentes. OntoForge indique la conformité à chacun, avec les raisons des écarts. |
| **Raisonneur (HermiT)** | Programme qui calcule les inférences d'une ontologie. Optionnel dans OntoForge (sous-processus, jamais bloquant). |
| **Règles W01–W07 / BP01–BP07** | Codes de conformité OWL 2 DL (W) et de bonnes pratiques (BP) de l'écran Conformité. Distincts des règles de transposition. |

## SHACL

| Terme | Définition |
|---|---|
| **SHACL** | Langage W3C de *contraintes* sur des graphes RDF : plus proche d'un schéma de données qu'OWL. |
| **NodeShape / PropertyShape** | Shape portant sur des nœuds cibles / sur les valeurs d'un chemin de propriété. |
| **Contrainte** | `sh:minCount`, `sh:maxCount`, `sh:datatype`, `sh:class`, `sh:in`, `sh:pattern`, `sh:closed`… |
| **Rapport de validation** | `conforms` + liste de résultats (`focus`, `path`, `severity`, `constraint`, `message`, `value`, `shape`). |
| **Inférence (validation)** | Désactivée par défaut dans OntoForge (D-034) : en RDFS, `sh:closed` verrait les super-propriétés. |

## Property graph et cibles

| Terme | Définition |
|---|---|
| **Property graph (LPG)** | Graphe de nœuds et de relations orientées, portant des propriétés ; schéma = contrat d'ingestion (monde clos). |
| **Curiosity** | Plateforme de graphe de connaissances (cible prioritaire). Schéma en classes C# `[Node]`, `[Key]`, `[Property]`, arêtes en **paires aller/retour**, un seul type par nœud. |
| **Neo4j** | Base de graphe (cible secondaire). Multi-labels, propriétés de relation, contraintes Cypher. |
| **Type de nœud** | `NodeType` du `PGModel` : nom, labels, clé, propriétés. |
| **Type d'arête / relation** | `EdgeType` : `from`, `to`, `reverse`, cardinalité. En Curiosity, sans propriétés. |
| **Clé** | Propriété(s) identifiant un nœud : `[Key]` (Curiosity), `UNIQUE` / `NODE KEY` (Neo4j). |
| **`uri` / `Uri`** | Propriété portant l'IRI d'origine d'un nœud (marquée `urn:ontoforge:iri`), clé par défaut. |
| **Discriminant** | Propriété `<racine>Kind` qui porte le sous-type quand la hiérarchie est aplatie (Curiosity). |
| **Multi-label** | Plusieurs labels par nœud (héritage naturel en Neo4j). |
| **Paire d'arêtes** | Curiosity : chaque relation est déclarée avec son retour (`Link(a, b, aller, retour)`). |
| **Réification** | Représenter une relation par un nœud intermédiaire (R01 binaire, R02 n-aire). **Dé-réifier** : remplacer ce nœud par une relation portant des propriétés (Neo4j seulement). |
| **Matérialisation** | Calculer et stocker un fait que le raisonneur infèrerait (fermeture transitive, chaîne, classification, `sameAs`). |
| **Validation (applicative)** | Contrôle exécuté à l'ingestion (connecteur) ou requête de détection, là où la base ne peut pas contraindre. |
| **NODE KEY** | Contrainte Neo4j Enterprise : existence + unicité d'un ensemble de propriétés. |
| **Enterprise / Community** | Éditions de Neo4j : certaines contraintes (`NODE KEY`, `IS NOT NULL`, types) sont Enterprise-only. |
| **GraphQL (schéma)** | `schema.graphql` généré pour les deux cibles ; pour Neo4j, directives de la Neo4j GraphQL Library (`À VÉRIFIER`). |

## Arbitrage OntoForge

| Terme | Définition |
|---|---|
| **Constat (`Finding`)** | Résultat d'une règle sur un élément de l'ontologie : identifiant, sévérité, options, recommandation. |
| **Sévérité `auto`** | Transposition triviale, appliquée directement. |
| **Sévérité `review`** | Perte possible : à arbitrer par l'humain. |
| **Sévérité `lost`** | Aucun équivalent natif : perte certaine tant qu'une compensation n'est pas choisie. |
| **Option** | Une façon de transposer un constat (`multi_label`, `validation`…). Les identifiants forment le vocabulaire normatif de `samples/trap/expected-findings.yaml`. |
| **Recommandation** | Option appliquée tant que l'humain n'a pas arbitré, propre à la cible. |
| **Décision** | `{constat: option}` mémorisée dans le projet par cible et rejouée à chaque analyse ; groupée : `"<règle>:*"`. |
| **Compensation** | Ce que le moteur génère pour limiter la perte : validation, matérialisation, requête, documentation. |
| **Ontologie piège (`trap`)** | `samples/trap/trap.ttl` : exerce les 66 règles et les pièges sémantiques (`must_not`). |
| **Oracle** | `samples/trap/expected-findings.yaml` : constats minimaux attendus, rejoués par les tests. |
| **`À VÉRIFIER`** | Marque d'une API externe (Curiosity.Library, Neo4j, pySHACL…) dont le comportement n'est pas confirmé par exécution. |
| **`X00`** | Ancien constat générique pour les règles non implémentées ; plus émis (les 66 règles sont implémentées). |

## Itération 2

| Terme | Définition |
|---|---|
| **Périmètre** | Sous-ensemble nommé de l'ontologie (classes, propriétés, avec ou sans descendants) à transposer ; plusieurs par projet ; sélectionné par `?perimeter=<id>`. Il n'est jamais appliqué implicitement : `active_perimeter` est un état d'interface. Constats d'information P00–P03. |
| **Opération (`op`)** | Geste d'édition atomique (`add_class`, `rename_entity`…) envoyé à `POST /ops` ; un lot est appliqué en entier ou pas du tout. |
| **Propriété simple** | Propriété non transitive, non cible d'une chaîne et sans super-propriété non simple : seule autorisée pour cardinalités, fonctionnelle, asymétrique… (OWL 2 Structural Spec §11.2). |
| **Requête guidée (`GuidedQuery`)** | Requête construite comme une phrase (« Je cherche un Véhicule qui a pour ordre de réparation… ») : racine, étapes, filtres, colonnes ; traduite en SPARQL, Cypher, Curiosity et GraphQL. |
| **Question en langage naturel** | Texte libre converti en requête guidée modifiable (`/query/nl`) : correspondance déterministe avec les labels + LLM facultatif ; tout élément inconnu est retiré (`unmatched`). |
| **Endpoint SPARQL actif** | Endpoint, parmi ceux déclarés dans les Paramètres, sur lequel s'exécutent les requêtes ; un seul à la fois. |
| **Proposition** | Ensemble de classes, propriétés ou modifications suggéré par l'assistant, affiché en surbrillance (ajout vert, modification orange) et accepté ou rejeté élément par élément ; rien n'est appliqué avant acceptation. |
| **Discriminant** | Propriété (`VehicleKind`, `PartyKind`) qui conserve le type d'origine quand des sous-classes sont repliées sous une racine concrète. |
| **Recopie dans les feuilles** | Sous une classe abstraite fusionnée (C04 `merge_into_leaves`), propriétés et relations de l'ancêtre dupliquées dans chaque sous-type concret (D-L15-01). |
| **Fournisseur LLM** | Configuration `{type, URL, modèle, clé}` (`anthropic`, `openai_compat`, `ollama`, `mock`) ; la clé est chiffrée côté serveur. |
| **Clé maître** | `ONTOFORGE_SECRET_KEY` : dérive la clé de chiffrement (Fernet) des secrets ; à défaut, fichier `.secret`. |
| **Krakie** | Mascotte d'OntoForge : petite pieuvre en pixel art couleur lagon, 9 poses (accueil, réfléchit, lit, loupe, graphe, contente, inquiète, forge, trophée). Elle forge (deux marteaux sur une enclume) pendant une génération ou une transposition, puis brandit un trophée en forme de graphe quand c'est fini. |
| **Tableau de bord** | Écran d'accueil d'un projet : état des quatre étapes et prochaine action. |
| **Saisie rapide** | Panneau de l'éditeur : une ligne de DSL = un axiome. |

## Équipe d'agents

| Terme | Définition |
|---|---|
| **Lot (`Lx`)** | Unité de travail contractualisée dans `lots/Lx.md`. |
| **Pilote / relecteur** | L'agent qui produit un lot / ceux qui le relisent en croisé. |
| **Revue (`verdict: OK\|KO`)** | Fichier `journal/Lx/review-<relecteur>-it<N>.md`. |
| **Salle des agents** | Artifact de suivi en direct (collection `events`). |
| **Skill** | Méthode réutilisable maintenue par un agent dans `skills/<nom>/SKILL.md`. |
