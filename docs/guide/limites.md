# FAQ des limites connues (itération 2) {#faq-des-limites-connues-iteration-2}

Chaque réponse cite sa source (rapport de lot, revue, décision ou code). Ce qui n'est pas résolu par le code est une question ouverte dans `journal/doc/questions.md` (identifiants `Q-DOC-nn`). État au 4 novembre 2026, mise à jour de l'itération 2 (lot L14). Tests non rejoués par le documentaliste (httpx absent) : 528 verts d'après `journal/L15/review-curiosity-it1.md`.

## Code généré : qu'est-ce qui est vérifié ? {#code-genere-qu-est-ce-qui-est-verifie}

**Le code C# Curiosity compile-t-il ?**
Non vérifié. Il n'y a aucun SDK .NET dans l'environnement de construction. La syntaxe C# est contrôlée par tree-sitter (D-038), pas par un compilateur. Les appels à `Curiosity.Library` non confirmés portent la mention `À VÉRIFIER` dans le code : retour de `AddOrUpdate`, `Link(a, b, X, X)` pour une arête symétrique, `SetAutoCommitCost`, type `Node`, tableaux `T[]`, indexation. Le script `tools/dotnet/check-curiosity.ps1` (projet temporaire net8.0 + `dotnet build`) permet de le vérifier chez vous. Il n'a pas été exécuté (pas de SDK, pas de Windows) et le nom exact du paquet NuGet reste à confirmer (`journal/L13/rapport.md`). Voir Q-DOC-01.

**Le Cypher Neo4j a-t-il été exécuté ?**
Non, sur aucune base réelle (question Q-02 de `journal/questions-jerem.md`). Les formes sont celles de Neo4j 5. Points à vérifier : unicité de relation en Community (supposée 5.7+), `CALL (row) { … } IN TRANSACTIONS` (portée de variable 5.23+), noms de procédures et options n10s et APOC (`apoc.refactor.mergeNodes`) (`journal/L4/rapport-neo4j.md`). Voir Q-DOC-02.

**Pourquoi des contraintes Cypher sont-elles commentées ?**
`NODE KEY`, `IS NOT NULL` et les contraintes de type de propriété sont Enterprise-only. Elles sont séparées dans `schema.cypher` (section Enterprise, Neo4j 5.11+ ; Community 5.7+). En Community, l'unicité (`IS UNIQUE`) est proposée à la place. Seuils de version retenus dans `mapping/profiles/neo4j.py` : contraintes de type de propriété 5.9+ (listes 5.10+, unions 5.11+), `RELATIONSHIP KEY` 5.7+. Aucun n'a été testé sur une instance.

**Le schéma GraphQL est-il utilisable tel quel ?**
Pour Neo4j, il repose sur les directives de la Neo4j GraphQL Library (`@relationship(type:, direction:)`, `@node(labels:)` à partir de la v4, `direction: NONE` pour les relations symétriques). Le résultat est `À VÉRIFIER` selon votre version (5.x / 6.x). Pour Curiosity, aucun GraphQL natif n'est connu. Le schéma sert de contrat de lecture et les résolveurs s'appuieraient sur la Query API (`À VÉRIFIER`). Voir Q-DOC-03.

**Et les requêtes Curiosity produites par le traducteur ?**
Du pseudo-C# de la Query API (`StartAt`, `Where`, accesseurs `n.UID`…), entièrement marqué `À VÉRIFIER`, sans vérification en environnement réel (`journal/L4/rapport-requetes.md`).

## Transposition {#transposition}

**Pourquoi tant de constats « à arbitrer » ?**
Sur l'ontologie piège, le moteur produisait à l'origine environ 130 constats `review` (un I01 par individu, un K03 par type racine). Le bruit a été réduit depuis : D13 `max 1` seul, K03 avec clé IRI et C07 garanti par construction en Curiosity passent en `auto`. Les constats sont groupés par règle dans l'interface et une décision groupée `"<règle>:*"` s'applique à toute une règle (`journal/L3/rapport-moteur.md`, `docs/RULES.md` « Itération 2 »).

**Le décimal exact est-il supporté ?**
Oui en Curiosity, non en Neo4j (levé en L13, D-L13-01, `tests/test_decimal.py`). `PGType` contient `Decimal`. Curiosity conserve `xsd:decimal` en `decimal` C# sans constat D05 (28-29 chiffres significatifs : au-delà, théoriquement à perte, revue W3C L13 ; note non ajoutée dans les profils). Neo4j n'a pas de décimal exact et replie en `Float` avec constat D05 (option `string_lexical` pour rester exact, ou entiers en centimes). Reste un point : les requêtes C# lisent un Decimal avec `GetDouble` (aucune API `GetDecimal` confirmée, `À VÉRIFIER`), ce qui perd la précision. `docs/RULES.md` (D05) et le catalogue `catalog.py` décrivent encore « decimal → flottant » (Q-DOC-04).

**Un nom de relation inverse est-il toujours fidèle à l'ontologie ?**
Oui depuis la correction de L13 (levé). `mapping/reverse_names.py` dérive les noms de retour Curiosity (`CoveredBy`, `HasVehicle`, `HasPartTransitive`…) puis `uniquify_reverses(..., reserved=...)` exclut tout nom égal (sans tenir compte de la casse) au nom local d'une propriété OWL ou d'un nom d'arête explicite, et se replie sur `<Arête>Of<Source>` (ex. `PerformedAtOfRepairOrder`). Contrôlé par tests sur automaint et trap (`tests/test_reverse_names.py`). Limite : certains noms restent peu parlants, par exemple `HasParty` pour le retour de `WorksAt` après repli (revue Curiosity L15, non bloquant). Plus aucun suffixe `…Inverse`.

**Pourquoi `I01` et `C08` ont-ils changé ?**
Levé en L13 : I01 n'est plus émis pour un membre d'`owl:oneOf` (porté par C08) ; C08 `reference_nodes` crée lui-même les nœuds de référence. I01 reste émis pour les membres d'un `AllDifferent` seul.

**Comment l'héritage sous une classe abstraite est-il transposé ?**
D-L15-01 : sous une classe abstraite fusionnée (C04 `merge_into_leaves`), les propriétés et relations de l'ancêtre sont recopiées dans chaque feuille concrète ; Technician, Garage, Customer et Brand restent des types distincts avec `DisplayName`. Le repli avec discriminant (`PartyKind`, `VehicleKind`) ne s'applique que sous une racine concrète. `Party` reste un type concret sur automaint. Les projets analysés avant ce correctif gardent l'ancien modèle : relancez l'analyse. Le traducteur de requêtes conserve le filtre discriminant.

**Les classes définies, les axiomes généraux, les chaînes de propriétés sont-ils transposés ?**
Non, ils ne peuvent pas l'être : ce sont des règles d'inférence, sans équivalent dans un property graph (règles C06, C09, C11, C13, O08…). Chacun devient, selon votre arbitrage, un booléen calculé à l'ingestion, une requête de classification / de chemin, une matérialisation, ou une simple ligne du rapport (`doc_only`). Voir [`regles.md`](regles.md).

**L'outil peut-il rendre un constat `lost` sans perte ?**
Non. `lost` signifie qu'aucune option n'est sans perte pour les données. Seule la compensation (validation, matérialisation, requête) limite les dégâts, et le rapport de transposition l'indique.

**Que fait l'outil du monde ouvert ?**
Transposer un axiome en contrainte est un renforcement : OWL infère, le property graph contraint. Par exemple, `owl:hasKey` n'impose ni existence ni unicité, alors qu'une clé Curiosity doit être non vide et qu'un `NODE KEY` impose les deux. `some` n'oblige pas à connaître la valeur. Le rapport rappelle ce changement d'hypothèse une fois.

**Les options marquées « minimales » sont-elles complètes ?**
Avec réserves (rapport du moteur L3, état avant L13) : O05 `edge_pair` côté Neo4j n'ajoute pas l'arête retour ; O12 `materialize_at_ingest` ne produit qu'une matérialisation ; C08 `reference_nodes` crée désormais lui-même les nœuds de référence (L13) ; I01 n'est plus émis pour les membres d'un `owl:oneOf`.

**`owl:imports` est-il résolu ?**
Non, l'outil est hors ligne. Les termes importés sont référencés par IRI et signalés (M02, BP05). L'exemple *trap* est conforme DL « sous réserve de la fermeture d'import PROV-O ».

## Conformité OWL et SHACL {#conformite-owl-et-shacl}

**La conformité aux profils EL / QL / RL est-elle fiable ?**
Elle est fondée sur les listes de datatypes et de constructions des *OWL 2 Profiles* recopiées de mémoire, à relire (`journal/L2/rapport-conformite.md`). W06 (RL) est une heuristique (disjonction, complément, `Nothing`) sans propagation par les restrictions. Le classement de `DisjointUnion` hors EL/QL/RL a été confirmé par la revue W3C. Voir Q-DOC-05.

**Et le raisonneur HermiT ?**
Depuis L32, il a son propre bouton (écran Conformité) et sa route `POST /api/projects/{id}/reason` : cohérence, classes insatisfiables, sous-classes et équivalences inférées, individus reclassés. Il tourne dans un sous-processus Java (30 s, 1 Go) fourni par `owlready2` (HermiT 1.3.8).

Limites : pas de justification d'incohérence (la ligne de commande n'en donne pas, OntoForge ne propose que des candidats), monde ouvert, garanties seulement pour OWL 2 DL. Les `owl:imports` ne sont pas suivis (raisonnement sur le seul contenu du projet) et aucune équivalence n'est ajoutable depuis l'éditeur graphique.

Les images (`backend/Dockerfile`, et `deploy/cloudrun/Dockerfile` par défaut) incluent Java ; sans Java ou `owlready2`, la route répond 501. Les tests qui lancent Java sont ignorés si Java manque ; leur exécution dans l'image Docker n'a pas été vérifiée ici (Docker indisponible).

**La validation SHACL utilise-t-elle l'inférence ?**
Non par défaut (D-034) : sans inférence, les 8 violations de `trap-data.ttl` (y compris via un projet : seule la TBox de l'ontologie est fournie à pySHACL, pas ses individus, D-L14-01) et les 4 de `automaint-data.ttl` sont garanties ; avec RDFS, `sh:closed` voit les super-propriétés. Une option d'inférence existe côté service (`inference="rdfs"`), mais l'API HTTP ne l'expose pas (aucun paramètre `inference` dans `api/analysis.py`).

**Les shapes générées équivalent-elles à l'ontologie ?**
Non : un axiome OWL n'est pas une contrainte SHACL. L'écran liste « ce que la génération ne reproduit pas à l'identique » (notes de `generate_shapes`).

## Interface {#interface}

**Qu'est-ce qui est en lecture seule dans l'éditeur ?**
Domaine/portée en union, chaînes de propriétés, équivalences complexes, faits des individus et autres superclasses anonymes : conservés et transposés, mais non modifiables à l'écran (`journal/L5/rapport-front.md`). L'IRI d'une entité n'est pas renommable après création.

**L'aide du DSL est-elle à jour ?**
Elle est embarquée dans le front : l'API ne l'expose pas (pas de `GET` d'aide). Elle peut donc différer de `DSL_HELP` si le DSL évolue.

**Quelles limites a l'éditeur graphique ?**
(`journal/L9/rapport-front.md`, `rapport-backend.md`.) Déplacer un nœud crée une entrée d'annulation ; la saisie rapide n'est pas annulable ; une classe créée avec un périmètre actif n'y est pas ajoutée ; les propriétés de données et les équivalences ne sont pas dessinées comme arêtes ; une propriété objet à plusieurs domaines/portées donne une arête par couple (la supprimer supprime la propriété entière) ; annuler restaure les champs de l'entrée même si un `PUT` hors éditeur est intervenu entre-temps ; supprimer une entité ne nettoie pas les shapes (avertissement) ; pas de verrou inter-processus (un seul worker) ; catalogue de 80 icônes Font Awesome (noms à confirmer avec la version embarquée, À VÉRIFIER) ; sur mobile, consultation seulement. L'écran Shapes du parcours est un placeholder « bientôt disponible » ; les shapes se gèrent dans l'écran SHACL.

**Les périmètres sont-ils sûrs ?**
Ils filtrent classes, propriétés (domaine et portée entièrement dans le périmètre), restrictions, clés, individus et shapes ; chaque coupe produit un constat d'information P01 à P03. Ces constats sont émis avec la sévérité `auto` (le niveau `info` accepté par D-L9-02 n'est pas encore dans `core/pg_model.py`) et gonflent donc le compteur « auto ». `OntClass.abstract` n'existe pas encore : l'éditeur déduit « abstrait » d'une union disjointe ou de l'annotation `urn:ontoforge:abstract`. L'icône d'une classe n'est pas transmise au modèle cible (`NodeType.icon` prévu).

**Le tableau de bord, Krakie et les écrans de l'itération 1 sont-ils aboutis ?**
Les écrans Analyse, Modèle, Exports, Conformité et SHACL ont été rebranchés dans le nouveau shell sans refonte en profondeur (sélecteur de cible dupliqué dans Analyse et Modèle, boutons texte sans icône : `journal/L11/rapport.md`). Le diagramme du modèle (L13 : polices lisibles, ajustement, molette, + / − / Ajuster) n'a pas été vérifié visuellement dans le rapport L13. Aucun test automatisé du front.

**Peut-on changer la langue ?**
Interface fr/en (Paramètres). Les libellés d'ontologie s'affichent dans la langue des labels choisie ; le lexique FR → EN du langage naturel est minimal.

**Pourquoi la page est-elle lourde ?**
Le bundle dépasse 500 ko (CodeMirror + Cytoscape), sans impact fonctionnel.

## Assistant IA {#assistant-ia}

**Que se passe-t-il sans clé ?**
Fournisseur `mock` : il ne connaît que le domaine automobile pour le texte libre et relaie un squelette pour CSV/SQL. Aucune proposition n'est appliquée sans votre acceptation.

**Les fournisseurs Anthropic, OpenAI-compatible, Ollama fonctionnent-ils ?**
Testés uniquement avec des réponses HTTP simulées (`httpx`) ; le bouton « Tester » des Paramètres appelle, lui, l'URL réelle : le format réel (`response_format` OpenAI, `format: json` Ollama, modèle par défaut hors Anthropic) est `À VÉRIFIER` en conditions réelles (`journal/L6/rapport-assistant.md`).

**Quelles sont les limites d'entrée ?**
Texte trop long → `413` ; non configuré → `503` ; JSON invalide du LLM après une relance → `502`. Le dépôt de fichier (`/assistant/upload`) est limité à 2 Mo (413) et refuse un fichier vide (422).

**Un fournisseur réel a-t-il été éprouvé avec le chat, la proposition et la question en langage naturel ?**
Non : le mock ne renvoie qu'un squelette et le prompt `[TASK:nl]` n'a pas été éprouvé sur un vrai modèle (aucun réseau en test) ; à valider sur votre fournisseur (`journal/L10/rapport-front.md`, `journal/L15/rapport-backend.md`). Les shapes proposées s'appliquent par fusion, pas élément par élément ; le mini-graphe de proposition est une grille simple (étiquettes parfois superposées) ; l'historique de conversation n'est conservé que dans le navigateur (80 messages).

**Krakie global : qu'est-ce qui n'est pas éprouvé ?**
Le prompt `[TASK:agent]` n'a pas été essayé sur un vrai fournisseur (pas de réseau en test) : le JSON est validé strictement et une réponse non JSON s'affiche comme texte. « Annuler » n'est offert que pour la dernière modification. Le repli sans LLM ne comprend que les tournures listées dans le guide utilisateur. Le panneau recouvre la partie droite de l'en-tête quand il est ouvert (`journal/L16/cloture.md`).

**Quelles sont les limites des écrans refaits en L17 ?**
Vue liste : faits d'individus, équivalences et expressions complexes en lecture seule. Shapes : contraintes motif, plage et liste non éditables en ligne. Requêtes : l'autocomplétion de libellés mélange le français et l'anglais (`journal/L17/cloture.md`).

## Exploitation {#exploitation}

**`docker compose up --build` a-t-il été vérifié ?**
Non dans l'environnement de construction (Docker Hub inaccessible, D-012) : le Dockerfile et le compose sont relus statiquement ; la recette réelle se fait chez vous. Le port publié est `ONTOFORGE_PORT` (8088 par défaut dans `docker-compose.yml` et `.env.example`) ; `CLAUDE.md` et `journal/L7/plan-recette.md` mentionnent encore 8080. Voir Q-DOC-07.

**Y a-t-il une authentification ?**
Non : l'API n'est pas authentifiée et le CORS est ouvert par défaut (`ONTOFORGE_CORS_ORIGINS=*`). OntoForge est conçu pour un poste local ; ne l'exposez pas sur Internet en l'état. Les clés de fournisseurs LLM et secrets d'endpoints sont chiffrés côté serveur (`ONTOFORGE_SECRET_KEY`), mais cela ne remplace pas une authentification.

**Où sont mes données ?**
Dans le volume Docker `ontoforge-data` (`/data/projects/<id>/`). Aucune donnée n'est envoyée à un service externe, sauf si vous configurez un fournisseur LLM (le contenu soumis à l'assistant part alors chez ce fournisseur).

## Paramètres, secrets et endpoints SPARQL {#parametres-secrets-et-endpoints-sparql}

**Où sont les clés d'API, et sont-elles protégées ?**
Chiffrées côté serveur (Fernet, clé dérivée de `ONTOFORGE_SECRET_KEY`), jamais renvoyées au navigateur ; sans clé maître, une clé est générée dans `$ONTOFORGE_DATA/.secret`. Une mauvaise clé maître rend les clés `key_unreadable` (à ressaisir) ; la rotation annule tout sans rien écrire si l'ancienne clé est fausse. Il n'y a pas de filtrage SSRF sur les URL de fournisseur et d'endpoint (outil mono-utilisateur auto-hébergé, D-L8-01) : à revoir avant toute exposition publique. `cryptography` s'installe via `pyproject.toml` ; l'image Docker n'a pas été reconstruite pour le vérifier.

**Peut-on exécuter les requêtes SPARQL maintenant ?**
Oui, sur l'endpoint actif (levé en itération 2, CONTRACTS §6), en lecture seule : les mises à jour sont refusées, le `LIMIT` est forcé (plafond 5000), le délai est celui de l'endpoint. Limites : « Inclure les sous-classes » est global (pas par étape) ; les propriétés de données sélectionnées sont des `OPTIONAL` (différence de sémantique avec une question de compétence où elles étaient obligatoires) ; domaine ou portée complexes approximés dans les suggestions ; l'aperçu graphe ne trace des arêtes que pour les requêtes guidées ; pas de comptage, agrégat ni tri en langage naturel ; l'année supposée des dates relatives est l'année courante ; le lexique FR → EN est minimal. Les traductions Curiosity relèvent de la Query API, absente de l'API C# vérifiée : `n.UID`, `Emit`, `AsEnumerable`, `WhereString` restent hypothétiques et les colonnes multiples ne sont lisibles qu'en C# (revue Curiosity L15).

**Y a-t-il des données pour essayer ?**
`samples/automaint/automaint-demo-data.ttl` (~4100 triplets : 40 véhicules, 6 garages, 15 techniciens, 30 clients inventés, 120 ordres de réparation, 160 relevés kilométriques) à charger dans votre endpoint ; `tools/demo/generate_demo_data.py` le régénère à l'identique (graine fixe). Il est conforme aux shapes sans inférence. Pas de propriété « ville » dans l'ontologie : « Toulouse » est un filtre sur le nom affiché du garage. Les hybrides sont typées `am:Vehicle` seulement. Ce fichier se liste comme « données » à côté de `automaint-data.ttl` (4 violations attendues) : choisissez le bon à la validation.
