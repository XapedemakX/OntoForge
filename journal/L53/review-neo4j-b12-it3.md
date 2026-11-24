verdict: OK
bloquants:
  - aucun.
non-bloquants:
  - Formes nouvelles de l'it3, relues sur les 24 sorties changées depuis l'it2 et sur 25 requêtes à moi :
    - `WITH * WHERE (v IS NULL OR NOT v:ElectricVehicle)` ;
    - `WITH * WHERE CASE WHEN v IS NULL THEN [NOT] EXISTS { MATCH (_any1) WHERE _any1:ElectricVehicle } ELSE [NOT] v:ElectricVehicle END`, seul, dans un `OR`, avant un `WITH` d'agrégation + `WHERE` (HAVING), et avec `RETURN count(*) > 0` ;
    - `EXISTS { MATCH (v) WHERE v:ElectricVehicle AND CASE WHEN v IS NULL … END }` (CASE imbriqué, branche THEN jamais prise) ;
    - `RETURN …, null AS o`, `count(null) AS n`, `ORDER BY null` ;
    - DF-B18, sans `OPTIONAL MATCH` ajouté à la requête principale.

    Aucune variable n'est utilisée hors de sa portée, aucun `MATCH` n'est vide, et `_any<n>` est un nom neuf. À la lecture, ce sont des formes Cypher 5 valides.
  - **À VÉRIFIER** sur une base Neo4j 5 chargée (exécution impossible ici, documentation non consultée par consigne) :
    - une sous-requête `EXISTS { … }` comme expression dans `CASE WHEN … THEN … ELSE … END` ;
    - un identifiant qui commence par `_` (`_any1`, déjà en usage avec `__agg_1__` et `_v<n>`) ;
    - `ORDER BY null` ;
    - `WITH *` suivi de `WHERE` ;
    - `EXISTS { MATCH (v) WHERE … }` avec `v` lié à l'extérieur et null ;
    - `coalesce` sur une comparaison.
  - Sémantique sur la cible neo4j : `(v IS NULL OR …)` corrige l'écart relevé en it2 pour MINUS. La branche THEN du CASE (`_any1:ElectricVehicle` sur tout le graphe) est exacte avec les labels posés par `targets/neo4j.py`.
  - DF-B16 (fausse perte vers un sous-type) : consigné, inchangé, conforme à la consigne.
  - Suite complète : 1699 verts.
skill: skills/neo4j-schema-design (partie requêtes) : pour une variable d'OPTIONAL MATCH qui peut être null, `NOT v:L` vaut null (la ligne est retirée). Il faut écrire explicitement `v IS NULL OR …`, ou `CASE WHEN v IS NULL THEN … ELSE … END`, et une sous-requête sur une variable neuve quand la condition porte sur tout le graphe. À confirmer sur une base Neo4j 5.
