# OntoForge — Carnet d'idées produit

Auteur : éclaireur produit (agent `scout`) — 3 nov. 2026, pour l'itération 2 (vendredi 6 nov.).
Utilisateur cible : architecte données / ontologue en ESN, qui répond à un appel d'offres, livre un POC Curiosity ou Neo4j en quelques jours, doit justifier ses choix au client puis faire évoluer le modèle sans tout casser.

Sources internes : `docs/PLAN-IT2.md`, `README.md`, `docs/ARCHITECTURE.md`, `journal/L3/rapport-moteur.md`, `journal/L5/rapport-front.md`, captures `journal/L5/screens/real-*.png`, revues W3C / Curiosity / Neo4j de `journal/`, `journal/decisions.md`.
Sources externes : listées en bas de chaque idée et dans le benchmark. Le moteur de recherche n'a renvoyé que des titres et liens : les affirmations sur les outils s'appuient sur ces pages et sur la connaissance générale ; celles non confirmées par un lien sont marquées « à revérifier ».

Légende : valeur 1-5 (5 = très utile à l'ingénieur) ; effort S (≤ 1 j) / M (2-4 j) / L (> 4 j) ; lots existants L8-L14 (plan it2), « L15+ » = lots à créer.

---

## 1. Top 5 pour l'itération 2

Mis à jour le 4 nov. 2026 après revue des écrans réels (`journal/L14/review-scout-usage.md`). Critère : ce qui change le plus la journée d'un ingénieur d'ESN, au meilleur rapport valeur / effort, en s'appuyant sur ce qui existe (moteur 66 règles, PGModel, rapport Markdown, assistant).

### 1. Arbitrage par décision structurante, pas par constat (P-01, P-02, P-03) — inchangé, renforcé
**Pourquoi.** Sur automaint, l'écran réel montre encore 48 restants (D13 ×13, O09 ×10, K02 ×6, O10 ×5…) : le bouton « Appliquer à toute la règle » aide, mais P-01 (reclasser en `auto` les constats sans vrai choix) n'est pas appliqué. Le geste « Accepter toutes les recommandations » est tentant mais dangereux (voir revue d'usage B4) : le vrai gain est de ne présenter que les vrais choix, par racine de hiérarchie, avec un champ « pourquoi » qui alimente le dossier de justification.
**Preuve de valeur.** Décisions humaines nécessaires sur automaint : cible < 25 (contre 48 à 80).
**Effort** M. **Risque** faible.

### 2. Dernier kilomètre : « Prochaine action » et génération en un clic (nouveau, voir P-31)
**Pourquoi.** Le parcours Concevoir → Générer est lisible, mais la carte « Générer » est muette (« Rien généré ») et l'historique des générations est local au navigateur. L'ingénieur pressé veut un seul bouton primaire qui change avec l'état du projet (corriger / arbitrer / générer / télécharger). C'est le geste le plus fréquent de la démo et il n'existe pas.
**Preuve de valeur.** Clics du projet ouvert au schéma téléchargé : cible 2.
**Effort** S (bouton) + M (historique serveur). **Risque** faible.

### 3. Import déterministe depuis l'existant : CSV, DDL SQL, JSON Schema, dès l'écran Projets (P-07)
**Pourquoi.** L'assistant gère bien le CSV (aperçu des colonnes, proposition accepte/rejette), mais la zone de dépôt des Projets le refuse : le cas dominant « voici la base du client » passe par un détour. Un importeur déterministe (PK → `hasKey`, FK → relations, tables d'association → réification, types SQL → xsd) rend le résultat reproductible et gratuit en jetons ; le LLM n'enrichit que noms et commentaires.
**Effort** M. **Risque** moyen (dialectes SQL).

### 4. « Dossier de justification » exportable (P-05)
**Pourquoi.** Inchangé : le livrable d'ESN est la réponse écrite au client (pourquoi ce modèle, ce qui est perdu, compensé, décidé par qui et pourquoi). Tous les ingrédients existent ; manque le document unique HTML + Markdown, avec les « pourquoi » saisis à l'arbitrage.
**Effort** M. **Risque** faible.

### 5. Lisibilité du modèle à l'échelle : canvas cadré, zoom sémantique, carte de chaleur des constats (nouveau, voir P-32 ; lié à P-24)
**Pourquoi.** L'éditeur interactif est la promesse centrale de l'it2, mais les captures réelles montrent un graphe de 24 classes illisible en plein cadre (étiquettes de 5 px), une nouvelle classe créée hors champ et une minimap sans lien avec la vue. Un modèle que l'on ne peut pas lire en atelier client n'est pas un outil de modélisation rapide. Cadrage automatique, centrage sur la création, zoom sémantique (icône seule en dézoom) et coloration par sévérité des constats (clic → arbitrage) donnent le « où est le risque » qui manque à la liste.
**Effort** M. **Risque** faible.

**Sortis du Top 5 par l'usage réel** (restent utiles) : diff de versions avec impact (P-10, it3, après le dossier) ; jeu de données d'exemple et tests de compétence (P-12, it3). Le constructeur de requêtes Phrase guidée + code côte à côte est déjà au niveau attendu.

**À ne pas faire en it2 malgré l'attrait** : collaboration temps réel (L), éditeur de mappings vers sources (L), alignement automatique complet avec schema.org/BFO (M-L, bon candidat it3).

### Nouvelles idées issues de l'usage (4 nov.)
- **P-31 — Prochaine action unique sur le tableau de bord.** Problème : carte « Générer » muette, historique local. Proposition : zone « Prochaine action » à état (corriger, arbitrer, générer, télécharger), historique serveur par projet. Valeur 5, effort S-M, risque faible, lot L11 (correctif). Inspiration : écrans d'accueil de Neo4j Data Importer (parcours guidé) [1].
- **P-32 — Zoom sémantique et cadrage du canvas.** Problème : graphe illisible à 24 classes, nouvelle classe hors champ. Proposition : `fitView`, centrage sur création, détail selon le zoom, minimap fidèle. Valeur 5, effort M, risque faible, lot L9 (correctif). Inspiration : WebVOWL (niveaux de détail) [2].

---

## 2. Horizon MAINTENANT (itération 2)

### P-01 — Reclasser les constats sans vrai choix en `auto`
- **Problème** : bruit d'arbitrage (80 restants sur automaint) ; l'architecte arrête de lire.
- **Proposition** : K03 « pas de clé → uri », D13 `max 1` donnée, C07 en Curiosity (types distincts = disjonction garantie), I01 redondant avec C08 passent en `auto` avec trace dans le rapport. Maquette : la barre de triage passe de 93/76/4 à ~150/25/4.
- **Valeur** 5 — **Effort** S — **Risque** faible (écarts d'oracle à tracer dans `ecarts-oracle.md`).
- **Lot** L13 (moteur) — **Inspiration** : revue chef « bruit d'arbitrage » (journal) ; principe « ne demander que ce qui est un vrai choix » de Neo4j Data Importer (propose un modèle par défaut) [1].

### P-02 — Arbitrage par racine de hiérarchie et politiques réutilisables
- **Problème** : une décision C02 par classe peut produire un modèle incohérent (aplatir Brand mais garder Organization) ; les mêmes choix se répètent d'un projet à l'autre.
- **Proposition** : une carte « hiérarchies » (Party, Vehicle, Engine) avec une décision par racine ; export/import de « politique d'arbitrage » (JSON) applicable à un nouveau projet. Maquette : panneau latéral « Appliquer la politique Acme-2026 ».
- **Valeur** 5 — **Effort** M — **Risque** moyen (rejouer des décisions sur une autre ontologie : ids différents, appliquer par règle + condition).
- **Lot** L11 (écran arbitrage, maquette M0) + L13 — **Inspiration** : revue chef ; Stardog / TopBraid « templates » (à revérifier).

### P-03 — Mode « décision rapide » au clavier avec raison en une ligne
- **Problème** : arbitrer à la souris est lent et non justifié.
- **Proposition** : file d'attente d'arbitrage (j/k, 1/2/3 = option, `?` = expliquer), champ « pourquoi » facultatif par décision, repris dans le dossier de justification.
- **Valeur** 4 — **Effort** S — **Risque** faible.
- **Lot** L11 — **Inspiration** : files de tri des outils de revue de code (usage), commentaires de décision de TopBraid EDG (à revérifier).

### P-04 — Mise en avant des pertes « côté client » : score de risque et traduction métier
- **Problème** : « C07 : disjonction de classes » ne parle pas au client.
- **Proposition** : chaque règle `lost`/`review` porte une phrase métier (« Rien n'empêche un Camion d'être aussi une Voiture ») et une compensation chiffrée (nb de validations à écrire). Mascotte pieuvre « inquiète » si perdus > 0 (rôle prévu au plan).
- **Valeur** 4 — **Effort** S — **Risque** faible.
- **Lot** L11 + documentaliste (L12) — **Inspiration** : rapport de transposition existant ; WebVOWL pour la lisibilité des constructs (VOWL) [2].

### P-05 — Dossier de justification client (HTML/Markdown/PDF)
- Voir Top 5 n° 2. **Valeur** 5 — **Effort** M — **Risque** faible. **Lot** L15 (ou extension de `targets/report.py`, propriétaire lead). **Inspiration** : Hackolade (génération de documentation HTML/PDF du modèle) [3], dbdocs [4], Widoco (docs d'ontologie, à revérifier).

### P-06 — Exports de la doc du modèle : dictionnaire de données et diagramme
- **Problème** : le client demande un « dictionnaire de données » Excel/Markdown, pas du C#.
- **Proposition** : export CSV/Markdown (type, propriété, type de donnée, obligatoire, source OWL, description fr/en) + diagramme SVG/PNG/Mermaid du modèle cible (le front a déjà cytoscape).
- **Valeur** 4 — **Effort** S — **Risque** faible. **Lot** L12/L15 — **Inspiration** : SchemaSpy, dbdocs [4], arrows.app (export SVG/PNG, à revérifier).

### P-07 — Import déterministe SQL DDL / CSV / JSON Schema
- Voir Top 5 n° 3. **Valeur** 5 — **Effort** M — **Risque** moyen. **Lot** L10 (imports de l'assistant) en version sans LLM. **Inspiration** : Neo4j Data Importer et le cours GraphAcademy « importing relational to graph » [5], LinkML schema-automator (import depuis JSON Schema, SQL, CSV…) [6].

### P-08 — Aperçu « diff » à chaque geste de l'assistant et de l'éditeur graphique, avec annuler/rétablir par projet
- **Problème** : une modification de graphe interactive sans historique fait peur.
- **Proposition** : pile d'annulation par session + « journal des changements » (qui/quoi/quand) alimenté par chaque PUT /onto ; bouton « revenir à ce point ».
- **Valeur** 4 — **Effort** M — **Risque** moyen. **Lot** L9 — **Inspiration** : Protégé (undo/redo, historique des changements) ; arrows.app (historique), à revérifier.

### P-09 — Vérifier la compilation du code généré dans un conteneur (.NET SDK + Neo4j)
- **Problème** : README « le code Curiosity n'a pas été compilé ; le Cypher n'a pas été exécuté ». Un ingénieur n'osera pas livrer une sortie non éprouvée.
- **Proposition** : script `make verify-targets` (déjà prévu : `dotnet build` en L13) + Neo4j éphémère (Testcontainers/Docker) qui rejoue `schema.cypher` + `ingest.cypher` sur le jeu d'exemple ; badge « compilé / exécuté le … » dans les exports.
- **Valeur** 5 — **Effort** M — **Risque** moyen (image Docker .NET, SDK Curiosity.Library non public : à vérifier).
- **Lot** L13 — **Inspiration** : questions Q-02 de `questions-jerem.md` ; revue Neo4j (Community vs Enterprise).

### P-10 — Snapshots nommés et diff de versions avec impact cible
- Voir Top 5 n° 4. **Valeur** 5 — **Effort** M — **Risque** moyen. **Lot** L15. **Inspiration** : OWLDiff [7], ROBOT diff (à revérifier), Hackolade (comparaison de modèles, à revérifier).

### P-11 — Détection de collisions et conformité des noms après normalisation
- **Problème** : `Warranty` (classe) et `warranty` (propriété) → même nom PascalCase en Curiosity (revue W3C N01) ; noms réservés C# / Cypher.
- **Proposition** : nouvelle règle de lint pré-génération : collisions, mots réservés (C#, Cypher), longueurs, caractères ; correction proposée en un clic (suffixe, préfixe).
- **Valeur** 4 — **Effort** S — **Risque** faible. **Lot** L13 — **Inspiration** : revue W3C L0 (N01 collisions).

### P-12 — Générateur de données d'exemple + exécution des questions de compétence
- Voir Top 5 n° 5. **Valeur** 5 — **Effort** M — **Risque** faible. **Lot** L15 (+ `queries.translate` encore en 501). **Inspiration** : questions de compétence de la méthodologie ontologique (Grüninger & Fox) ; travaux LLM + CQ (OntoChat, Bench4KE) [8].

### P-13 — Périmètres (sous-ensembles) avec « modèle minimum viable » pour un POC
- **Problème** : un client a 300 classes, le POC en veut 15.
- **Proposition** : en plus des périmètres d'ontoSparq (prévus L9), bouton « fermeture minimale » : à partir de 5 classes choisies, calcule les ancêtres, propriétés et cibles nécessaires et signale ce qui est coupé (arêtes pendantes). Maquette : surbrillance du périmètre sur le graphe + liste des « dépendances ajoutées ».
- **Valeur** 5 — **Effort** M — **Risque** moyen (fermeture de restrictions et d'équivalences). **Lot** L9 — **Inspiration** : périmètres ontoSparq (`ref/ontosparq`), modules d'ontologie (OWL API locality modules, à revérifier).

---

## 3. Horizon BIENTÔT (itérations 3-4)

### P-14 — Génération de scripts de migration entre deux versions du modèle
- **Problème** : après un diff (P-10), il faut encore écrire la migration (renommer un label, aplatir un héritage, backfill d'une propriété).
- **Proposition** : sorties `migrate-v1-v2.cypher` et notes `Migration.cs` / checklist Curiosity (types renommés, nouvelles clés).
- **Valeur** 4 — **Effort** L — **Risque** élevé (sémantique des données existantes). **Lot** L16 — **Inspiration** : Neo4j migrations (neo4j-migrations, à revérifier), Hackolade forward/reverse engineering [3].

### P-15 — Rétro-ingénierie d'un graphe existant (Neo4j `db.schema.visualization`, Curiosity)
- **Problème** : le client a déjà un graphe Neo4j sans ontologie documentée.
- **Proposition** : import du schéma réel (`CALL db.schema.visualization()`, `apoc.meta.schema`, à revérifier) → ontologie candidate + écarts avec le modèle cible.
- **Valeur** 4 — **Effort** M — **Risque** moyen. **Lot** L16 — **Inspiration** : Hackolade reverse engineering [3], Neo4j Data Importer [5].

### P-16 — Import XSD et UML (XMI / PlantUML) comme sources
- **Problème** : les clients des secteurs réglementés fournissent XSD ou UML (diagrammes de classes).
- **Proposition** : XSD → classes/propriétés/énumérations (types complexes, `xs:choice` → unionOf à arbitrer) ; UML via XMI ou sous-ensemble PlantUML. Mêmes constats « à arbitrer » que pour OWL.
- **Valeur** 3 — **Effort** L — **Risque** moyen. **Lot** L16 — **Inspiration** : LinkML schema-automator (importeurs XSD/JSON Schema/SQL/RDFS) [6].

### P-17 — Alignement avec des ontologies de référence (schema.org, gist, FIBO, SKOS)
- **Problème** : « votre `Person` est-elle `schema:Person` ? » ; réutiliser évite de réinventer et rassure le client.
- **Proposition** : suggestion de correspondances (`skos:closeMatch`, `owl:equivalentClass` à arbitrer) par similarité de labels + LLM, catalogue local de vocabulaires courants, rapport des alignements. Le `closeMatch` à schema.org vu dans l'assistant (capture `real-assistant.png`) est déjà amorcé.
- **Valeur** 4 — **Effort** L — **Risque** moyen (qualité des alignements : toujours proposer, jamais imposer). **Lot** L17 — **Inspiration** : PoolParty (gestion de vocabulaires, à revérifier), LinkML mappings (`exact_mappings`) [6].

### P-18 — Mode « revue » : commentaires, relecteur, statut d'approbation par élément
- **Problème** : le modèle est validé par le client ; il faut des retours traçables.
- **Proposition** : commentaires par classe/propriété/constat, statuts brouillon / relu / approuvé, export du journal des revues dans le dossier de justification. Sans temps réel : fichiers de projet versionnés (Git).
- **Valeur** 4 — **Effort** L — **Risque** moyen. **Lot** L17 — **Inspiration** : TopBraid EDG (workflows de gouvernance) et PoolParty ; synthèse de comparaison [9].

### P-19 — Projet versionné dans Git (format fichiers stable, diff lisible)
- **Problème** : `project.json`, `onto.ttl` se prêtent mal au diff par ligne si le sérialiseur n'est pas stable.
- **Proposition** : Turtle canonique trié, décisions en JSON trié, bouton « Initialiser un dépôt Git » / « Commit avec message » depuis l'outil ; l'ESN retrouve ses habitudes de revue de code.
- **Valeur** 4 — **Effort** M — **Risque** faible. **Lot** L16 — **Inspiration** : LinkML (schéma YAML versionnable en Git) [6].

### P-20 — Export du schéma en PG-Schema / GQL et de SHACL aligné sur les décisions de validation
- **Problème** : les « validations applicatives » (O09, O10, O11…) sont des constats mais pas des artefacts.
- **Proposition** : (a) export SHACL des décisions de validation (déjà prévu à la feuille de route v0.2) ; (b) export PG-Schema comme format neutre de description du modèle cible [10].
- **Valeur** 3 — **Effort** M — **Risque** moyen (PG-Schema évolue, pas de moteur grand public à ce jour : à revérifier).
- **Lot** L16 — **Inspiration** : PG-Schema (SIGMOD 2023) [10], LinkML SHACL generator [6].

### P-21 — Générateurs de validation exécutables (contrôleur applicatif)
- **Problème** : « validation applicative » = le client doit l'écrire. 86 validations dans le modèle Curiosity d'automaint (capture `real-modele-curiosity.png`).
- **Proposition** : générer le code de validation (C# `Validators.cs`, requêtes Cypher de contrôle `validation.cypher` déjà existantes à étendre) et un rapport de contrôle d'ingestion.
- **Valeur** 5 — **Effort** L — **Risque** moyen. **Lot** L16 — **Inspiration** : revue chef (typage des extrémités après aplatissement), Neo4j constraints.

### P-22 — Cibles supplémentaires : Neptune openCypher, Memgraph, GQL, Kuzu
- **Problème** : l'ESN rencontre aussi Neptune (le projet EKF tourne sur AWS) et Memgraph.
- **Proposition** : profils de capacités additionnels dans `mapping/profiles/`, sans nouvelles règles ; générateur openCypher commun.
- **Valeur** 4 — **Effort** M par cible — **Risque** moyen. **Lot** L17 — **Inspiration** : feuille de route v0.3 d'ARCHITECTURE §7.

### P-23 — Arbres de décision guidés « Curiosity ou Neo4j ? » en amont
- **Problème** : en phase d'appel d'offres, le choix de cible n'est pas fait.
- **Proposition** : questionnaire (volumétrie, besoin de propriétés sur relations, multi-typage, recherche texte, hébergement) → recommandation argumentée + comparaison des pertes par cible côte à côte (déjà possible : analyse × 2 cibles).
- **Valeur** 3 — **Effort** S — **Risque** faible. **Lot** L15 — **Inspiration** : tableau « comparaison de cibles » du rapport de transposition.

### P-24 — Visualisation des constats sur le graphe (carte de chaleur du risque)
- **Problème** : la liste de constats ne dit pas *où* le modèle est fragile.
- **Proposition** : sur le canvas, colorer classes/arêtes selon sévérité maximale ; filtre « montrer seulement ce qui est perdu » ; clic → ouvre l'arbitrage.
- **Valeur** 4 — **Effort** M — **Risque** faible. **Lot** L11 — **Inspiration** : VOWL (code couleur de notation) [2], rendu ontoSparq.

### P-25 — Assistant : critique de modèle et « patrons de modélisation »
- **Problème** : l'assistant propose mais ne critique pas ; les ingénieurs réinventent rôle, adresse, événement, version, période de validité.
- **Proposition** : bibliothèque de patrons (rôle, n-aire, période de validité, hiérarchie de localisation, version de document) insérables en un clic avec l'impact par cible ; commande « critique mon modèle » qui s'appuie sur lint + règles + LLM.
- **Valeur** 4 — **Effort** M — **Risque** moyen. **Lot** L17 — **Inspiration** : Ontology Design Patterns (ODP), skill `ontology-rapid-design`.

---

## 4. Horizon PLUS TARD

### P-26 — Collaboration en temps réel (édition à plusieurs, curseurs)
- **Problème** : deux ingénieurs sur le même modèle en atelier client.
- **Proposition** : CRDT ou verrou par entité ; en attendant, P-18 + Git.
- **Valeur** 3 — **Effort** L — **Risque** élevé. **Lot** L20+ — **Inspiration** : Gra.fo, WebProtégé (collaboration en ligne, à revérifier).

### P-27 — Éditeur de mappings source → graphe (au-delà du modèle)
- **Problème** : le modèle est prêt, reste à lier colonnes et champs au schéma.
- **Proposition** : écran « mapping » (colonne SQL / champ JSON → propriété), génération de connecteurs (`Connector.cs`, LOAD CSV) pilotés par ce mapping ; ontologie comme couche sémantique virtuelle (R2RML/OBDA comme export).
- **Valeur** 5 — **Effort** L — **Risque** élevé. **Lot** L20+ — **Inspiration** : Stardog Designer (mappings de sources, virtual graphs) [11], Neo4j Data Importer [5], metaphactory (à revérifier).

### P-28 — Raisonneur intégré avec explications (« pourquoi cette classe est insatisfiable ? »)
- **Problème** : HermiT optionnel et non intégré (Java absent de Debian 13, D-040) ; les erreurs de cohérence sont opaques.
- **Proposition** : raisonneur embarqué (ELK/HermiT via service dédié) + justifications d'axiomes (« explanations ») dans l'écran Conformité.
- **Valeur** 3 — **Effort** L — **Risque** moyen. **Lot** L20+ — **Inspiration** : Protégé (explication de cohérence, plugin).

### P-29 — Suivi des standards : SHACL 1.2, RDF 1.2 / RDF-star, GQL
- **Problème** : les projets 2027 utiliseront des fonctions SHACL 1.2 (expressions de nœuds, règles, selon le brouillon) et RDF 1.2 (triple terms) qui permettent des *annotations de relation* proches des propriétés d'arêtes.
- **Proposition** : veille continue ; lorsque RDF 1.2 sera stable, règle de transposition « triple annoté → relation porteuse de propriétés » (aujourd'hui R01 réification). SHACL 1.2 Core est en brouillon W3C actif en 2026 [12] : ne pas coder avant stabilité.
- **Valeur** 3 — **Effort** M — **Risque** moyen (standards mouvants). **Lot** L20+ — **Inspiration** : SHACL 1.2 Core [12], PG-Schema [10].

### P-30 — Bibliothèque de modèles de départ par secteur (kits de démarrage)
- **Problème** : la page blanche, même assistée, coûte du temps ; l'ESN a des secteurs récurrents.
- **Proposition** : kits (maintenance, achats, RH, santé, ITIL/CMDB) téléchargeables, chaque kit avec ontologie, shapes, jeu d'exemple, politique d'arbitrage. Générique, sans données client.
- **Valeur** 4 — **Effort** M (par kit) — **Risque** faible. **Lot** L20+ — **Inspiration** : exemple automaint ; LinkML (schémas communautaires) [6].

### P-31 — Tableau de bord d'un portefeuille de projets (maturité, couverture, risques)
- **Problème** : un référent technique suit plusieurs réponses d'appels d'offres.
- **Proposition** : vue multi-projets (état, nombre de perdus non traités, dernière génération, prochaine échéance).
- **Valeur** 2 — **Effort** M — **Risque** faible. **Lot** L20+ — **Inspiration** : tableau de bord par projet prévu au plan it2.

### P-32 — Mode « atelier client » : présentation lecture seule et vocabulaire métier
- **Problème** : projeter l'outil devant un client non-ontologue.
- **Proposition** : vue simplifiée (diagramme + glossaire + « questions auxquelles le modèle répond »), masquant IRI et constructs OWL, labels fr/en bascule.
- **Valeur** 3 — **Effort** M — **Risque** faible. **Lot** L20+ — **Inspiration** : WebVOWL (visualisation destinée aux non-experts) [2], Gra.fo (modélisation visuelle collaborative, à revérifier).

### P-33 — Télémétrie locale et « qualité de modèle » (métriques)
- **Problème** : comment dire qu'un modèle est « bon » ?
- **Proposition** : indicateurs calculés (profondeur d'héritage, classes sans label, propriétés orphelines, % couverture par shapes, ratio perdu/auto) avec seuils par défaut, suivis dans le temps entre snapshots.
- **Valeur** 3 — **Effort** S — **Risque** faible. **Lot** L17 — **Inspiration** : OOPS! (détection de pièges d'ontologie, à revérifier), lint existant (W07, BP01-07).

### P-34 — Export vers formats d'outils tiers (Hackolade, arrows.app JSON, dbdiagram/DBML, Mermaid)
- **Problème** : le client garde ses outils ; l'interopérabilité évite l'enfermement.
- **Proposition** : exports de diagramme (Mermaid, DBML pour la vue « relationnelle » dérivée, JSON arrows.app) ; import arrows.app pour partir d'un croquis d'atelier.
- **Valeur** 3 — **Effort** S par format — **Risque** faible. **Lot** L17 — **Inspiration** : arrows.app [5], dbdiagram/dbdocs [4].

---

## 5. Benchmark

| Outil / standard | Ce qu'il fait bien | Ce qu'OntoForge peut faire mieux pour un ingénieur qui transpose vers Curiosity/Neo4j |
|---|---|---|
| **Protégé** (Stanford) | Référence de l'édition OWL complète, plugins (raisonneur, explications, OWLDiff [7]) ; gratuit | Pas de notion de cible property graph, aucun constat de perte, interface dense. OntoForge : saisie rapide, constats de perte par cible, arbitrage tracé, export prêt à l'emploi |
| **WebVOWL** (VOWL) | Visualisation lisible d'une ontologie pour non-experts [2] | Lecture seule ; ne dit pas ce qui survit en graphe. OntoForge : graphe éditable + carte de risque (P-24) + mode atelier (P-32) |
| **TopBraid EDG / PoolParty** | Gouvernance : workflows, rôles, SKOS/taxonomies, qualité [9] | Lourds et chers pour un POC de trois semaines, orientés RDF. OntoForge : revue légère (P-18), dossier de justification (P-05), cibles LPG |
| **metaphactory** | Plateforme de graphes de connaissances, modélisation et applications sur RDF (à revérifier) | Cible RDF/SPARQL uniquement. OntoForge : sortie directe vers schémas Curiosity / Neo4j et rapport de pertes |
| **Stardog Designer** | Modélisation visuelle + mapping de sources vers un graphe de connaissances [11] | Lié à la plateforme Stardog. OntoForge : indépendant, import de l'existant (P-07), plus tard mappings (P-27) |
| **Neo4j Data Importer / arrows.app** | Prise en main très rapide : modèle visuel + CSV/SQL → graphe ; GraphAcademy [5] | Pas d'ontologie, pas de justification d'un choix, pas de diff de version. OntoForge : ontologie → modèle avec constats, import SQL/CSV déterministe (P-07), éditeur graphique |
| **Hackolade Studio** | Modélisation polyglotte, rétro-ingénierie et génération de scripts pour Neo4j et d'autres, documentation HTML/PDF [3] | Pas d'OWL/SHACL natif ni de raisonnement sur ce qui se perd en transposition. OntoForge : sémantique ontologique d'abord, dossier de justification, politiques d'arbitrage |
| **Gra.fo** | Éditeur visuel collaboratif d'ontologies / schémas (à revérifier) | Peu d'aide à la transposition. OntoForge : analyse et génération pour les deux cibles |
| **LinkML** | Un schéma YAML, de multiples générateurs (OWL, SHACL, JSON Schema, SQL…), importeurs schema-automator [6] | Pas de cible property graph (Curiosity/Neo4j), pas d'arbitrage interactif. OntoForge : s'en inspirer pour les importeurs et pour le schéma versionné en Git (P-19) |
| **dbdiagram.io / dbdocs** | DSL simple (DBML), diagrammes et documentation de base relationnelle en ligne [4] | Relationnel uniquement. OntoForge : même fluidité de saisie (DSL) pour OWL, documentation et diagramme du modèle graphe (P-06) |
| **OWLDiff / ROBOT diff** | Comparaison et fusion d'ontologies OWL [7] | S'arrêtent à l'ontologie. OntoForge : diff du modèle cible, décisions invalidées, notes de migration (P-10, P-14) |
| **PG-Schema / GQL** | Langage de schéma de property graph (SIGMOD 2023), avec types, contraintes et héritage ; base d'un futur standard [10] | Pas d'outil de conception grand public. OntoForge : export PG-Schema comme format neutre (P-20) |
| **SHACL 1.2** | Validation de graphes RDF ; version 1.2 en cours de standardisation au W3C [12] | Reste côté RDF. OntoForge : shapes ↔ validations du modèle cible (O09-O11, D13), suivi des évolutions (P-29) |
| **Approches LLM (OntoChat, Bench4KE…)** | Génération de questions de compétence et d'ontologies depuis du texte [8] | Qualité variable, peu de traçabilité. OntoForge : le LLM propose, chaque élément est accepté ou rejeté, vérifié par lint et règles (déjà en place) |

Positionnement en une phrase : **OntoForge est le seul outil de la liste qui part du sens (ontologie) et dit, élément par élément, ce qu'on garde, ce qu'on compense et ce qu'on perd en arrivant sur Curiosity ou Neo4j, avec le dossier pour le justifier.**

---

## 6. Retours internes recueillis (traçabilité des idées)

| Source | Retour | Idée |
|---|---|---|
| Rapport moteur L3, « limites » | Volume d'arbitrage ~130 constats sur trap ; regroupement par règle proposé | P-01, P-02 |
| Revue chef (non-bloquants) | D13/O09/K03/C02/C07 bruyants ; décision par racine ; typage des extrémités après aplatissement | P-01, P-02, P-21 |
| Rapport front L5 | IRI non renommable, domaines en union en lecture seule, aide DSL dupliquée | à traiter par L9 ; non listé ici (dette technique) |
| Revue W3C L0/L1/L2 | Collisions de noms (N01), `AllDisjointClasses` n-aire perdu au round-trip, W07 trop bavard | P-11, dette moteur |
| Rapports Curiosity/Neo4j | Decimal absent de PGType ; code jamais compilé / exécuté ; NODE KEY Enterprise | P-09 |
| `questions-jerem.md` Q-02 | Exécuter les sorties sur une vraie instance | P-09 |
| `PLAN-IT2.md` | Périmètres, constructeur de requêtes, assistant plein écran, mascotte | P-13, P-12, P-04 |
| Capture `real-requetes.png` | Questions de compétence encore « bientôt disponible » | P-12 |
| Capture `real-modele-curiosity.png` | 86 validations applicatives à écrire, graphe dense peu lisible | P-21, P-24 |

---

## Veille 7/11

Auteur : agent `veille` (lot L21). Idées issues des fiches `docs/veille/nvidia-auto-ontology.md`, `neonto.md`, `normes.md`, `processus-mise-a-jour.md`. Mention « veille ». Gain 1-5, effort S / M / L. Classées par rapport gain / effort, la meilleure en premier. Identifiants V-xx pour ne pas heurter P-xx.

| # | Idée | Gain | Effort | Source | Détail |
|---|---|---|---|---|---|
| V-01 | Tester le DDL Neo4j sur 5.26 et 2026.10, en `CYPHER 5` et `CYPHER 25` | 5 | M | normes.md §2 | Neo4j est passé aux versions calendaires et à Cypher 25. Aucune preuve que notre DDL passe partout. Rejoint P-09. D-L21-03 : test manuel par Jerem, pas de matrice en CI. |
| V-02 | Exécuter `check-curiosity.ps1` avec `Curiosity.Library` 26.11.7740 et lever les À VÉRIFIER | 5 | S | normes.md §3 | Le script n'a jamais tourné. La doc du SDK confirme maintenant les noms d'appels utilisés. D-L21-03 : validation manuelle par Jerem. |
| V-03 | Montée groupée rdflib 7.6, pyshacl 0.40, owlrl 7.6 | 4 | S | normes.md §4.1 | Onze versions mineures de retard sur pyshacl. 0.40 casse `ConjunctiveGraph` (non utilisé chez nous). Écartée par D-L21-02 : pas de montée de version. |
| V-04 | Dependabot actif avec la configuration du dépôt | 4 | S | processus §2 | `.github/dependabot.yml` est prêt. Reste à activer les alertes côté GitHub. D-L21-02 : Dependabot signale, rien n'est fusionné sans l'accord de Jerem. |
| V-05 | Suites de tests W3C en CI (RDF 1.1, SHACL 1.0 bloquants ; RDF 1.2 et SHACL 1.2 en suivi) | 4 | M | processus §3.1 | Les suites existent (`w3c/rdf-tests`, `w3c/data-shapes`, dossier `shacl12-test-suite`). Un taux de réussite suivi dit quand coder la 1.2. D-L21-03 limite la CI aux tests backend, au build front et aux recettes : hors CI pour l'instant. |
| V-06 | Veille mensuelle programmée + `standards.json` | 4 | S | processus §1 | Prompt prêt. Sortie : diff de `normes.md`, lot si écart. Écartée par D-L21-01 : veille à la demande. |
| V-07 | Amorcer une ontologie depuis du texte et des PDF dans l'assistant, avec extrait source obligatoire | 3 | M | nvidia-auto-ontology.md | Le texte existe déjà (pièce jointe tronquée à 12 000 caractères). Ajouter extraction PDF, découpage, traçabilité, avertissement de confidentialité. |
| V-08 | Option de génération « graph type » Neo4j | 3 | M | normes.md §2 | Disponible en version générale depuis 2026.06. Équivalent Neo4j de PG-Schema. Rejoint P-20. |
| V-09 | Contrôles déterministes sur les propositions de l'assistant (schéma strict, noms, doublons, IRI) | 4 | S | nvidia-auto-ontology.md | Même approche que NVIDIA : sortie structurée stricte puis règles. L'essai à blanc existe déjà pour les opérations ; l'étendre aux propositions. |
| V-10 | Métriques de qualité d'ontologie avec seuils | 3 | S | neonto.md | Rejoint P-33. neonto en fait un produit, donc un besoin. S'appuyer sur la littérature d'Achim Reiz. |
| V-11 | « Krakie, mets-toi à jour » : panneau caché d'état des normes et bibliothèques, lu dans `standards.json` | 3 | S à M | processus §4 | Proposé, non codé. Réponse à « votre outil est-il à jour de SHACL 1.2 ? ». À décider par Jerem. |
| V-12 | Détection de ce que le modèle ne couvre pas, appliquée aux questions de compétence | 4 | M | nvidia-auto-ontology.md | Idée du `check_answerable` de NVIDIA. Rejoint P-12. |
| V-13 | Épingler la version de `Curiosity.Library` dans les sorties et README générés | 3 | S | normes.md §3 | Aujourd'hui : « version à aligner ». Demander à Curiosity la règle de compatibilité avec le serveur. |
| V-14 | Actualiser les en-têtes générés « Neo4j 5.x » vers la numérotation calendaire | 3 | S | normes.md §2 | Cosmétique mais crédibilité auprès d'un client qui a Neo4j 2026. |
| V-15 | Attribut `[Timestamp]` pour les propriétés de date et heure côté Curiosity | 2 | S | normes.md §3 | Présent dans la doc des schémas. À valider par l'expert Curiosity. |
| V-16 | Serveur MCP en lecture sur le projet (ontologie, constats, rapport) | 3 | M | neonto.md, nvidia | NVIDIA et TopQuadrant exposent leur contexte aux agents par MCP. |
| V-17 | Page de comparaison « OntoForge, Protégé, n10s, Curiosity » pour les clients | 2 | S | neonto.md | Messages de positionnement déjà rédigés. À relire par w3c, neo4j, curiosity avant diffusion. |
| V-18 | Export YAML Apache Ossie | 2 | M | nvidia | Seulement sur demande client. Spécification non lue (site inaccessible). |
| V-19 | Montée React 19, Vite 8, TypeScript 7 | 2 | L | normes.md §4.2 | Pas urgent. Lot dédié, hors période de livraison. Écartée par D-L21-02. |
| V-20 | Suivre RDF 1.2 (passage en recommandation) puis règle « triple annoté vers relation porteuse de propriétés » | 3 | M | normes.md §1 | Remplace RDF-star. Ne pas coder avant CR confirmé et support de bibliothèque. Précise P-29. |
| V-21 | Ne pas faire : éditeur dans VS Code, SaaS par utilisateur | 1 | L | neonto.md | Champ occupé par Protégé et neonto. OntoForge se distingue sur le dernier kilomètre et la perte de sémantique. |

Remarque sur P-29 : au 7/11/2026, SHACL 1.2 Core est un brouillon du 02/11/2026 et RDF 1.2 Concepts est CR depuis le 07/04/2026 (normes.md). La prudence de P-29 reste de mise.

---

## 7. Sources

1. Neo4j, « Discover AuraDB Free: week 16 – the CSV data importer tool » — https://neo4j.com/developer-blog/discover-auradb-free-week-16-the-csv-data-importer-tool
2. Lohmann et al., « Visualizing ontologies with VOWL », Semantic Web Journal — https://journals.sagepub.com/doi/full/10.3233/SW-150200
3. Hackolade, solution brief Neo4j et aide en ligne — https://hackolade.com/help/help.html
4. dbdiagram.io, « How to create database documentation using dbdocs with DBML » — https://blog.dbdiagram.io/how-to-create-database-documentation-using-dbdocs-with-dbml
5. Neo4j GraphAcademy, « Importing relational to graph » — https://graphacademy.neo4j.com/courses/importing-relational-to-graph/3-importing/2-extracting-data
6. LinkML, générateurs et schema-automator — https://linkml.io/linkml/generators/index.html et https://linkml.io/schema-automator/introduction.html
7. Protégé wiki, OWLDiff — https://protegewiki.stanford.edu/wiki/OWLDiff
8. Bench4KE (génération de questions de compétence) — https://arxiv.org/pdf/2505.24554 ; « Leveraging LLM for automated ontology extraction » — https://arxiv.org/pdf/2412.00608
9. Comparatif d'outils de gestion d'ontologies — https://www.rajeshkumar.xyz/blog/?p=2007 (source secondaire, à recouper)
10. Angles et al., « PG-Schema: Schemas for Property Graphs » — https://arxiv.org/abs/2211.10962
11. Stardog Designer — https://docs.stardog.com/archive/9.2.1/stardog-applications/designer
12. W3C, SHACL 1.2 Core (Working Draft) — https://www.w3.org/TR/shacl12-core/
