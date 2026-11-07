# Rapport L4 requêtes (agent query)

## État à la reprise
`translate.py` (1597 l.) et `targets/graphql.py` (372 l.) étaient déjà complets et fonctionnels ; manquaient `competency.py`, fixtures SPARQL, tests et skill. Rien n'a été réécrit.

## Livré
- `queries/competency.py` : 5-10 questions (liste, relation, comptage, OPTIONAL, transitive, filtre, sous-classe aplatie, chemin 2 sauts) avec sparql, cypher, curiosity, lossy, notes. Sur AutoMaint : 10 questions, aucune lossy.
- Fixtures : `tests/fixtures/queries/q01..q10.sparql` (+ `pg_automaint.json`, `onto_automaint.json` existants).
- Tests : `test_translate.py` (15), `test_graphql.py` (5, SDL validé par graphql-core) : 19 verts avec `pytest tests/test_translate.py tests/test_graphql.py`.
- Skill `skills/graph-query-translation/SKILL.md`.

## Constats
- Dans AutoMaint, `am:ownedBy` et `am:ofModel` ne sont pas dans le PGModel (seuls `owns`, `hasModel`) : une requête SPARQL qui les utilise sort `[perte]` (testé). À arbitrer côté mapping (propriété inverse non déclarée owl:inverseOf).
- Sortie Curiosity = pseudo-C# marqué À VÉRIFIER (pas de vérification en environnement réel).
- GraphQL émis seulement pour lectures simples arborescentes (sans filtre/agrégat).
- Suite complète non relancée (seuls mes fichiers testés). Événements : ajoutés à `journal/events.jsonl` (ArtifactData non chargé, fallback autorisé) ; l'événement `done` est à republier par le lead.
