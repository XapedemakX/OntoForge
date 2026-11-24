verdict: OK
bloquants:
  - aucun.
non-bloquants:
  - Formes nouvelles de l'itération 2, relues sur les 41 sorties changées depuis it1 et sur environ 30 requêtes à moi :
    - `MATCH … OPTIONAL MATCH … WITH * WHERE … RETURN …`, y compris avec `RETURN DISTINCT`, `ORDER BY` / `LIMIT`, `count(*) > 0`, et avec agrégation : `WITH * WHERE …` puis `WITH count(v) AS __agg_1__, …, o AS __agg_3__ WHERE __agg_2__ > 0`.
    - `UNION`, dont seule la branche concernée porte `WITH * WHERE`.
    - `WHERE false`, et `MINUS` retiré (plus de `WHERE`).
    - Littéraux échappés (`'it\'s MATCH , x'`).

    Ce sont des formes Cypher 5 usuelles, et l'ordre des clauses est correct : le filtre vient après les OPTIONAL MATCH et avant l'agrégation. Il n'y a plus aucune variable utilisée avant sa déclaration dans le corpus : DF-B15 est corrigé pour la validité. **À VÉRIFIER** sur une base Neo4j 5 chargée (pas d'exécution possible ici, et la documentation n'a pas été consultée, à la demande du coordinateur) : `WITH *` suivi de `WHERE`, `EXISTS { MATCH (v) WHERE … }` avec `v` lié à l'extérieur (et `v` null après un OPTIONAL MATCH), `coalesce(<comparaison>, false)`, ainsi que `NOT v:L` sur un `v` null (qui devrait valoir null).
  - Sémantique sur la cible neo4j d'un `MINUS` ou d'un `[NOT] EXISTS` qui porte sur une variable d'OPTIONAL non liée : `WITH * WHERE NOT v:ElectricVehicle` retire les lignes où `v` est null, alors que SPARQL les garde pour un MINUS. C'est un écart de sens, non un problème de validité. Il fait l'objet du bloquant de la revue query it2.
  - DF-B14 sur neo4j : `MATCH (v:Vehicle) RETURN v.uri AS v` (MINUS retiré). C'est valide et exact.
  - Hors lot (à ouvrir, voir la revue query it2) : un OPTIONAL ou un BIND dans un sous-motif déborde dans la requête principale. `RETURN o AS v`, où `o` n'est lié que dans `EXISTS { }`, est un Cypher invalide (variable non définie dans cette portée, À VÉRIFIER sur une base). Ce défaut existait avant le lot.
  - DF-B16 (fausse perte « Relation incompatible » vers un sous-type) : il est bien consigné, il n'est pas corrigé (c'est la consigne), et la sortie est inchangée.
  - Suite complète : 1680 verts.
skill: skills/neo4j-schema-design (partie requêtes) : un FILTER de groupe qui porte sur une variable d'OPTIONAL MATCH se rend par `WITH * WHERE …` après le dernier OPTIONAL MATCH du groupe, et avant tout `WITH` d'agrégation ; un prédicat de label sur un nœud qui peut être null vaut null (la ligne est retirée), ce qu'il faut garder en tête pour MINUS et NOT EXISTS. À confirmer sur une base Neo4j 5.
