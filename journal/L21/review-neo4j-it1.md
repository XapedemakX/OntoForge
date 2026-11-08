# L21 — revue neo4j, itération 1

Relecteur : expert Neo4j (agent `neo4j`). Date : 7/11/2026. Périmètre : `docs/veille/normes.md` partie 2, `processus-mise-a-jour.md` §3.2, idées V-01, V-08 et V-14, au regard de `backend/ontoforge/targets/neo4j.py`.
Sources relues le 7/11/2026 : notes de version 2026.10, page des versions prises en charge (support.neo4j.com), Cypher 25 « deprecations, additions, removals », manuel des opérations « Configure the Cypher default version ».

```
verdict: OK
bloquants:
  (aucun après correction)
non-bloquants:
  - [docs/veille/normes.md:53] graph types : GA en 2026.06 et aperçu en 2026.02, c'est confirmé. Il manque l'édition : graph types et contraintes `NODE_LABEL_EXISTENCE` / `RELATIONSHIP_*_LABEL` réservés à l'Enterprise ou ouverts à la Community ? À VÉRIFIER avant d'ouvrir A6. Si c'est Enterprise seulement, l'option doit rester une section commentée, comme la section 4 actuelle de schema.cypher.
  - [docs/veille/normes.md:52] syntaxe des contraintes non relue sur sa page, bloquée par robots. La page des ajouts et suppressions ne déprécie pas `IS UNIQUE`, `IS NODE KEY`, `IS NOT NULL` ni `IS ::`, et `indexProvider` est bien retiré en 2025.06. Le test A3 (testcontainers) reste la seule preuve recevable : à garder en tête des actions.
  - [backend/ontoforge/targets/neo4j.py:339] A3/A4 pertinentes. L'en-tête d'ingest.cypher conseille `CALL (row) { … }` (5.23+) et mentionne `CALL { WITH row … }` « avant ». L'import par `WITH` est déprécié en Cypher 5 : en Cypher 25, n'écrire que la forme à portée, sans `WITH`. À intégrer à A4.
  - [backend/ontoforge/targets/neo4j.py:692] « relations depuis 5.7 » et « 5.9+, listes 5.10+ » restent justes pour 5.x. Ajouter une ligne pour 2026.x (contraintes `IS :: VECTOR<…>`, Enterprise) seulement si un PGType vecteur est créé (normes.md l. 54 : Surveiller, d'accord).
  - [docs/veille/processus-mise-a-jour.md:131] matrice : ajouter une cellule Community 2026.x. C'est la configuration la plus probable d'un POC client, et le `neo4j.conf` fourni y met Cypher 25 par défaut (confirmé).
  - [docs/veille/normes.md:56] « addition de maps (2026.10) » : confirmé par les notes 2026.10 (opérateur `+` sur les maps).
corrigé par le relecteur (dans normes.md) :
  - l. 13 et 50 : 2026.10.1 n'est pas daté sur la page des notes de version. La date du 23/10 est marquée À VÉRIFIER ; 2026.10.0 est bien du 20/10/2026.
  - l. 51 : l'action « écrire le préfixe en tête des scripts » est fausse. `CYPHER 25` ne s'applique qu'à la requête qu'il précède : il faut le répéter devant chaque instruction, ou fixer le langage par défaut de la base (`db.query.default_language` / langage par défaut de la base).
  - Vérifiés exacts : 5.26 seule LTS en cours, correctifs jusqu'au 06/06/2028 ; 4.4 hors support depuis le 30/11/2025 ; 2026.10 corrigée jusqu'à la sortie de 2026.11 ; Cypher 5 par défaut dans le paramètre, `neo4j.conf` fourni réglé sur CYPHER_25 depuis 2026.02 ; VECTOR 2025.10 ; SEARCH 2026.01 ; `db.index.vector.query*` dépréciées en 2026.04 ; FOR…IN et IS LABELED 2026.04 ; GROUP BY 2026.07 ; numéros de ligne cités dans neo4j.py (225-271, 309, 339, 610, 693).
skill: neo4j-schema-design → « Le préfixe CYPHER 5 / CYPHER 25 vaut pour une requête : dans un script multi-instructions, le répéter devant chaque instruction ou fixer le défaut de la base. »
```
