# Rapport L4 — agent neo4j

## Livré
- `backend/ontoforge/mapping/profiles/neo4j.py` : CAPABILITIES (min 5.11, Community vs Enterprise), XSD_TYPE_MAP, nommage, **67 entrées RECOMMENDATIONS** (66 règles + X00) réécrites avec les identifiants du vocabulaire de l'oracle `samples/trap/expected-findings.yaml` (la reprise partait d'ids non conformes et de 37 règles).
- `backend/ontoforge/targets/neo4j.py` (déjà écrit par l'agent précédent, relu) : schema.cypher, ingest.cypher, validation.cypher, model.mmd, README-neo4j.md ; déterministe.
- `backend/tests/fixtures/pg_neo4j_automaint.json` (ids d'options alignés sur l'oracle), `test_profile_neo4j.py` (41 tests), `test_target_neo4j.py` (21 tests). Suite complète : 154 verts.
- `skills/neo4j-schema-design/SKILL.md`.

## À VÉRIFIER (non testé sur une instance Neo4j)
1. Contrainte d'unicité sur relation : Community ? (supposé oui, 5.7+).
2. `CALL (row) { … } IN TRANSACTIONS` (variable scope 5.23+).
3. Noms exacts des procédures et options n10s.
4. Conversion `xsd:duration` -> `duration()` pour mois/années.
5. Aucune exécution contre un vrai Neo4j : formes vérifiées par regex seulement.

## Écarts / demandes de contrat
- Aucune modification de `pg_model.py`. Pas de goldens `tests/golden/neo4j/*` (hors périmètre possédé) : invariants testés par regex.
- Oracle : C09, D05, O13 ont deux recommandations selon le sujet ; le profil donne une valeur par règle (le moteur choisira par contexte, toutes les options existent).
- Profil Neo4j : `reverse_name` renvoie toujours None (inverse non stocké, O04).
