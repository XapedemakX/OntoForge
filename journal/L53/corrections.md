# L53 : synthèse des corrections pour Jerem

Six défauts de `journal/L51/defauts.md` sont corrigés (DF-B12, B13, B14, B15, B17, B18), plus l'installation sans `constraints.txt` de deux jobs de la CI. DF-B16 reste ouvert. Chaque défaut a des tests qui échouaient avant et passent maintenant.

Chiffres, sur la branche `integration/L53` (fusion de `lot/L53-b12` et `lot/L53-b13`) : suite backend 1724 tests verts (1648 avant le lot), `npm test` 22 sur 22, `npm run build` réussi, recettes `e2e_ui`, `l19`, `l40`, `mobile_l45`, `l48` et `l49` vertes. Aucune dépendance ajoutée, aucune montée de version. Les relectures query, curiosity, neo4j (requêtes) et deploy, devback, devfront (plafonds) sont toutes à OK à l'itération 3.

Le détail (reproduction, correction, mesures avant / après, reste) est dans `corrections-b12.md` (requêtes) et `corrections-b13.md` (plafonds, CI).

## Les défauts

### DF-B12 (majeure) : sous-motifs EXISTS, NOT EXISTS, MINUS réduits à un typage
- Problème. `FILTER [NOT] EXISTS { ?v a am:ElectricVehicle }` et `MINUS` du même genre donnaient `WHERE [NOT] EXISTS { MATCH  }`, du Cypher invalide, sur les deux cibles, sans note de perte. Le typage du sous-motif modifiait aussi le type de la variable extérieure : la classe disparaissait et le pseudo-code C# filtrait à l'envers (« véhicules qui ne sont pas électriques » donnait les électriques).
- Correction. Le sous-motif devient une condition complète (`sub_condition`, `type_predicate`) : `WHERE NOT v:ElectricVehicle` sur Neo4j, test du discriminant sur Curiosity, C# par `cs_type_check`. Une intersection non représentable ou une classe absente devient une perte signalée. Un garde-fou interdit tout `MATCH` vide dans la sortie.
- Résultat. 0 `MATCH` vide sur 172 traductions comparées (30 avant). Sur le corpus, 81 sorties sur 172 changent par rapport à avant L53, toutes liées à `EXISTS`, `NOT EXISTS`, `MINUS` ou à un `FILTER` sur variable d'`OPTIONAL`, ou le C# d'une requête marqué partiel. Fixtures, questions de compétence et requêtes des tests : aucune autre sortie ne change. Détail : [corrections-b12.md#df-b12](corrections-b12.md#df-b12).

### DF-B14 (majeure) : MINUS sans variable partagée
- Problème. `?v a am:Vehicle . MINUS { ?o a am:RepairOrder }` donnait `NOT EXISTS { MATCH (o:RepairOrder) }` : aucun résultat dès qu'un ordre existe, sans perte signalée. SPARQL 1.1 (§8.3.3) n'exclut rien dans ce cas.
- Correction. Sans variable commune, la condition est retirée, avec une note `[info]`.
- Résultat. `MATCH (v:Vehicle) RETURN v.uri AS v` sur les deux cibles. Détail : [corrections-b12.md#df-b14](corrections-b12.md#df-b14).

### DF-B15 (majeure) : FILTER sur une variable d'OPTIONAL
- Problème. `OPTIONAL { ?o am:concerns ?v } FILTER(!BOUND(?v))` plaçait le filtre avant l'`OPTIONAL MATCH` qui déclare `v` : Cypher invalide, `lossy = false`.
- Correction. Ces conditions sont rendues après les `OPTIONAL MATCH`, dans `WITH * WHERE …`. `MINUS` et `[NOT] EXISTS` sur une variable d'`OPTIONAL` suivent SPARQL (forme exacte) ou sont signalés comme perte.
- Résultat. Cypher valide ; un filtre sur une variable du motif principal reste dans le premier `WHERE`. Détail : [corrections-b12.md#df-b15](corrections-b12.md#df-b15).

### DF-B18 (majeure) : OPTIONAL et BIND dans un sous-motif
- Problème. Un `OPTIONAL` ou un `BIND` écrit dans un sous-motif débordait dans la requête principale (`OPTIONAL MATCH` en trop, `RETURN o AS v` avec `o` indéfini, `SELECT *` invalide).
- Correction. Le sous-motif restaure l'état d'avant son rendu ; l'`OPTIONAL` interne est ignoré (`[info]` ou `[perte]` selon le cas), le `BIND` sur une variable principale est une perte.
- Résultat. Plus de débordement ; une variable propre au sous-motif donne `null` (ou aucune colonne avec `SELECT *`). Détail : [corrections-b12.md#df-b18](corrections-b12.md#df-b18).

### DF-B13 (majeure) : somme des plafonds mémoire sur Cloud Run
- Problème. Chaque plafond borne un seul fils, pas leur somme. Les fils du triplestore local n'avaient aucun nombre de places, SHACL valait 2048 Mo et HermiT 2 places : la somme au pire dépassait largement les 2 Gio de l'instance (6107 Mo avec une seule place du triplestore, sans borne en réalité). Un compte autorisé qui travaille sur plusieurs projets pouvait arrêter l'instance (CWE-770).
- Correction. Places bornées pour le triplestore local (`ONTOFORGE_LOCAL_STORE_SLOTS`, 503 + `Retry-After: 5`), places pour le chargement de fichier (50 000 triplets et 5 Mo sur Cloud Run), plafond d'espace disque total (64 Mo, 413) et purge des bases inactives (30 min) (décision D-L53-02), `ONTOFORGE_MAX_BODY_MB` à 12. Plafonds de `env.yaml` mesurés : SHACL 320, OWL RL 256, HermiT 1 place au tas de 192, fils du triplestore 640. Un test relit `env.yaml` et refuse toute somme au-delà de 2048 Mo.
- Résultat. Fils de requête simultanés pour 5 projets : 5 avant, 2 au plus après (les autres reçoivent 503). Somme au pire : 1933 Mo = 175 serveur + 320 + 256 + 342 + 640 + 124 chargement + 64 disque + 12 corps de requête, marge de 115 Mo sous 2048. Détail : [corrections-b13.md#df-b13](corrections-b13.md#df-b13).

### DF-B17 (majeure) : analyseur SPARQL de rdflib non réentrant
- Problème. Relevé pendant DF-B13. Deux analyses simultanées échouaient au hasard (422 « SPARQL invalide » sur une requête valide) ; dans le triplestore local, le second contrôle de `SERVICE` et la lecture de `FROM` pouvaient être sautés en silence.
- Correction. Un verrou unique (`queries/sparql_lock.py`) autour de toute analyse ; un test de garde interdit tout appel direct au parseur hors de ce module.
- Résultat. 8 fils × 40 appels : 320 erreurs sur 320 avant, 0 après ; 5 `POST /query/run` simultanés : 30 réponses 200. Coût : environ 5 ms par analyse, débit total inchangé. Détail : [corrections-b13.md#df-b17](corrections-b13.md#df-b17).

### CI : installation sans contraintes
- Problème. Les jobs `audit-dependances` et `recettes` installaient le backend sans `-c backend/constraints.txt` : versions libres, différentes de celles livrées.
- Correction et résultat. `-c backend/constraints.txt` ajouté aux deux étapes ; la résolution passe (essai à blanc en Python 3.12). Les jobs ne sont pas exécutés ici. Détail : [corrections-b13.md#ci](corrections-b13.md#ci).

## Ce que Jerem doit faire

1. Déployer L53 en appliquant `env.yaml`. Lancer `.\deploy\cloudrun\deploy-demo.ps1`, ou l'étape 5 de `deploy/cloudrun/README.md`. Depuis L53, le script et le déclencheur Cloud Build appliquent `env.yaml`, `--memory 2Gi`, `--max-instances 1` et les secrets ; avant, seule l'image changeait et les nouveaux plafonds n'auraient pas été posés. Aucune commande gcloud n'a été lancée par l'équipe.
2. Contrôler le résultat avec la commande du README §7 (`gcloud run services describe ontoforge …`, lecture seule, aucune valeur de secret). Attendu : `ONTOFORGE_SECRET_KEY` et `ONTOFORGE_AUTH_USERS` présents en `secretKeyRef`, `ONTOFORGE_SHACL_MEMORY_MB: 320`, `ONTOFORGE_LOCAL_STORE_SLOTS: 1`, `ONTOFORGE_LOCAL_STORE_TOTAL_MB: 64`, `ONTOFORGE_LOCAL_STORE_IDLE_MIN: 30`, `memory: 2Gi`, `maxScale: '1'`.
3. Points À VÉRIFIER (rien n'a pu être essayé sans accès à Google Cloud ni à une base Neo4j) :
   - Secrets avec `--env-vars-file`. La documentation de gcloud n'a pas pu être consultée : on ne sait pas si `--env-vars-file` retire les variables venues de Secret Manager. Les secrets sont donc redonnés par `--set-secrets`. Le contrôle du point 2 le confirme.
   - Rôles du compte Cloud Build (README §8). Vérifier que le compte de construction a `run.developer` et `iam.serviceAccountUser` sur `ontoforge-run`, et que seul `ontoforge-run` a `secretAccessor`. Jamais d'accès aux secrets pour le compte de construction, ni `run.admin`.
   - `run.developer` ou `run.admin`. La documentation cite `run.admin` pour poser des références de secrets ; `run.developer` suffit-il ? Au premier essai du déclencheur. Repli : retirer `--set-secrets` du déclencheur seulement, puis contrôler avec le §7.
   - Formes Cypher sur une vraie base Neo4j 5. `CASE WHEN v IS NULL THEN EXISTS { MATCH (_any1) WHERE … } ELSE … END`, `EXISTS { MATCH (v) WHERE … }` avec `v` lié à l'extérieur, `v:Label` en `WHERE`, `NOT v:Label`, `coalesce` sur une comparaison, `WITH *` suivi de `WHERE`. Ce sont des formes Cypher 5 standard, à confirmer sur une base chargée.
4. Mesurer la marge sur l'instance réelle. Les 115 Mo de marge sont un calcul au pire cas ; le serveur au repos mesure 121 à 146 Mo (175 retenus). Regarder la mémoire dans le tableau de bord Cloud Run après quelques usages.
5. Premier push. Les jobs `audit-dependances` et `recettes` de la CI n'ont pas tourné ici : regarder leur première exécution. Le job `recettes` n'a toujours pas été rejoué avec Playwright 1.63.0.

## Reste ouvert

- DF-B16 (mineure, ouvert). Sur Neo4j, une relation vers un sous-type (`?o am:concerns ?v . ?v a am:ElectricVehicle`) donne une fausse perte « Relation incompatible ». Elle est dans le sens sûr. Lot à venir.
- Limites consignées, non corrigées (chapitres 09 et 10 du manuel) :
  - disponibilité des chargements : la place de chargement est tenue pendant l'attente du verrou du projet, parce que le fichier analysé occupe la mémoire du serveur ; la relâcher romprait la borne de 124 Mo. Une requête longue sur un projet fait donc répondre 503 aux autres chargements ;
  - inférence et budget disque estimé : le budget disque de l'inférence est une estimation (500 octets par triplet, marge de 1,25) et le contrôle entre projets n'est pas atomique ; la purge n'a pas de tâche de fond, donc une base inactive reste tant que personne n'utilise le triplestore ;
  - ordre des colonnes de `SELECT *` : non déterministe d'une exécution à l'autre, déjà vrai avant L53, aucun test n'en dépend ;
  - C# cosmétique des éléments absents : sous une négation, une classe ou une propriété absente donne `WHERE false` en Cypher mais un C# partiel complet plutôt que `.Where(n => false)` ; la sortie est marquée partielle, donc honnête ;
  - une seule place du triplestore local sur toute l'instance : les autres requêtes reçoivent 503 ; acceptable pour une démo à un administrateur, à rouvrir si plusieurs comptes travaillent en même temps (passer à 2 places demande de baisser un autre plafond ou une instance de 4 Gio).
- Six choix de `journal/L52/corrections.md` qui vous reviennent. Le premier (quand traiter DF-B12 et DF-B13) est réglé par ce lot. Restent : références `$ref` en URL dans l'import JSON Schema ; page « déploiement » dans `docs/guide/` ; langue des refus avant authentification ; CI (le job `recettes` avec Playwright 1.63.0 reste à lancer une fois après le push, l'installation sans contraintes est corrigée) ; suites possibles hors lot (type racine pour `StartAt` avec plusieurs types de départ, parcours mobile « serveur coupé » et « session expirée »).
- Sept `À CONFIRMER` du manuel (`docs/dev/README.md`, §5 Points ouverts) : en-tête `Host` du proxy de Vite avec l'authentification, version de Java dans l'image Docker, `run_limited` sous Windows, Bedrock cité par D-006, compression de `nginx.conf`, exécution réelle des commandes de déploiement, écart Python 3.12 / 3.13. Reportés par D-L52-01.
- Skill. `skills/graph-query-translation` (propriétaire query) peut reprendre les règles de la revue query : typage de sous-motif = condition, intersection non représentable = perte, sous négation une perte vaut `false`, `MINUS` sans variable partagée n'exclut rien, `FILTER` sur variable d'`OPTIONAL` après l'`OPTIONAL MATCH`.
