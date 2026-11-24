# L53 : correction de DF-B12 {#df-b12}

Pilote : devback. Relecteurs : query, curiosity, neo4j. Constat d'origine : `journal/L51/defauts.md` (ligne DF-B12), portée établie par `journal/L52/review-query-back-it1.md`. Tests : `backend/tests/test_l53_b12.py` (it1 : 24 tests, tous rouges sur le code d'avant ; it2 : 32 tests, voir [it2](#it2)). Suite complète : 1648 tests verts avant, 1672 après l'it1, 1680 après l'it2, 1699 après l'it3, **1703 après les finitions** (55 tests dans `test_l53_b12.py`). Défauts de même nature traités dans le lot : [DF-B14](#df-b14), [DF-B15](#df-b15), [DF-B18](#df-b18).

## Problème {#probleme}

`FILTER EXISTS`, `FILTER NOT EXISTS` et `MINUS` dont le sous-motif ne contient que le typage d'une variable déjà liée produisaient `WHERE [NOT] EXISTS { MATCH  }` : du Cypher invalide, refusé par Neo4j, avec `lossy = false` et sans note, sur les deux cibles.

La reproduction a montré une cause plus large que le `MATCH` vide. Le typage du sous-motif passait par `add_type` sur le nœud **extérieur**, qui est partagé. Il modifiait donc le type de la variable du motif principal :
- la classe du sous-motif disparaissait du Cypher ;
- le pseudo-code C# filtrait à l'envers : `?v a am:Vehicle . FILTER NOT EXISTS { ?v a am:ElectricVehicle }` donnait `StartAt(N.ElectricVehicle.Type)` sur la cible neo4j et `.WhereString(…, "ElectricVehicle")` sur curiosity, c'est-à-dire exactement les nœuds à exclure ; pour `MINUS`, la sortie C# n'était même pas marquée partielle ;
- le typage d'un sous-motif s'ajoutait aux types de la variable extérieure ; la note « intersection impossible » de `?v a am:ElectricVehicle . FILTER NOT EXISTS { ?v a am:CombustionVehicle }` venait donc de ce mélange, même si cette perte est réelle (intersection non représentable, revue query it1, voir [it2](#it2)) ;
- avec une relation, la restriction se perdait sans bruit : `?o am:concerns ?v . FILTER EXISTS { ?o am:concerns ?v . ?v a am:ElectricVehicle }` donnait `EXISTS { MATCH (o)-[:CONCERNS]->(v) }` (sans ElectricVehicle) sur curiosity, et une fausse perte sur neo4j.

Même défaut pour un sous-motif sans nouveau nœud qui ne porte que des propriétés. C'est le cas de la requête guidée « n'a pas de … » (filtre nié) : `FILTER NOT EXISTS { ?v am:vin ?x . FILTER(CONTAINS(…)) }` donnait `NOT EXISTS { MATCH  WHERE … }`, et `NOT EXISTS { ?v am:vin ?x }` donnait `NOT EXISTS { MATCH  }`.

Reproduction (API `POST /queries/translate`, projet automaint, cibles neo4j et curiosity) : 28 requêtes écrites pour le lot (les trois de la revue query, classe disjointe, variable déjà typée par un sous-type, sous-motif avec type et relation, propriétés seules, classe absente, deux typages, `EXISTS` dans une expression `||`, `ASK`) et les requêtes guidées. Avant la correction, 30 sorties contenaient un `MATCH` vide.

## Correction {#correction}

Tout est dans `backend/ontoforge/queries/translate.py` :
- `sub_condition` (nouveau) traduit le sous-motif de `EXISTS`, `NOT EXISTS` (par `exists_pattern`) et `MINUS` (par `render_block`) en une condition Cypher complète. Pendant le sous-motif, `_sub_ctx` contient les nœuds extérieurs et `triple` y capture le typage d'un nœud extérieur au lieu de modifier son type.
- `type_predicate` (nouveau) : le typage capturé devient un prédicat. Il reprend l'union « label » ou « label et discriminant » de `node_pat`. Sur neo4j, cela donne `v:ElectricVehicle` / `NOT v:ElectricVehicle`, en accord avec le label général et le label propre posés par `targets/neo4j.py`. Sur curiosity, cela donne `(v:Vehicle AND coalesce(v.VehicleKind = 'ElectricVehicle', false))` ; le `coalesce` sert à ce que `NOT` garde les nœuds sans discriminant. Une classe absente donne `false` ; sous `NOT EXISTS` ou `MINUS`, la condition entière vaut `false` ([it2](#it2)). Un type sans label donne une note `[perte]` et `false`.
- Sous-motif avec un nouveau motif : `[NOT] EXISTS { MATCH … WHERE … }`, avec les prédicats de type dans le `WHERE`. Sous-motif sans nouveau nœud : ancré sur le nœud extérieur, `EXISTS { MATCH (v) WHERE … }`. Dans un sous-motif, `data_triple` exige la valeur (`IS NOT NULL`, ou `size(…) > 0` pour une liste). Rien de traduisible : note `[perte]` et `false`.
- C# Curiosity : `cs_type_check` (nouveau) traduit un typage seul en `.Where(n => n.GetString(N.Vehicle.VehicleKind) == "ElectricVehicle")` (nié : `!(…)`) ou le décide par le type du nœud (filtre retiré s'il est toujours vrai, `.Where(n => false)` s'il est toujours faux). Il est utilisé par `cs_expr` pour `EXISTS` et par `curiosity()` pour `MINUS`. Un nœud aux types multiples : note `[curiosity]`, sortie partielle. Un `MINUS` non traduit marque désormais la sortie C# comme partielle.
- Garde générique dans `translate` (`_EMPTY_MATCH`) : un Cypher qui contient un `MATCH` sans motif n'est jamais renvoyé (`cypher = null`, `supported = false`, note `[perte]`).

Aucune dépendance ajoutée. Manuel : chapitre 09, section [sous-motifs](../../docs/dev/09-requetes.md#sous-motifs) (fr, en), piège DF-B12 retiré.

## Résultat avant / après {#resultat}

| Requête (automaint) | Cible | Avant | Après |
|---|---|---|---|
| `?v a am:Vehicle . FILTER EXISTS { ?v a am:ElectricVehicle }` | neo4j | `WHERE EXISTS { MATCH  }` | `WHERE v:ElectricVehicle` |
| `?v a am:Vehicle . FILTER NOT EXISTS { ?v a am:ElectricVehicle }` | neo4j | `WHERE NOT EXISTS { MATCH  }`, C# `StartAt(N.ElectricVehicle.Type)` | `WHERE NOT v:ElectricVehicle`, C# non produit (type de départ multiple, note) |
| `?v a am:Vehicle . MINUS { ?v a am:ElectricVehicle }` | curiosity | `WHERE NOT EXISTS { MATCH  }`, C# `.WhereString(…, "ElectricVehicle")` | `WHERE NOT (v:Vehicle AND coalesce(v.VehicleKind = 'ElectricVehicle', false))`, C# `.Where(n => !(n.GetString(N.Vehicle.VehicleKind) == "ElectricVehicle"))` |
| `?v a am:ElectricVehicle . FILTER NOT EXISTS { ?v a am:CombustionVehicle }` | neo4j | `MATCH  `, `lossy = true` | `MATCH (v:ElectricVehicle) WHERE NOT v:CombustionVehicle`, `lossy = true` (intersection non représentable, [it2](#it2)) |
| `?o am:concerns ?v . FILTER EXISTS { ?o am:concerns ?v . ?v a am:ElectricVehicle }` | curiosity | `EXISTS { MATCH (o)-[:CONCERNS]->(v) }` (classe perdue) | `EXISTS { MATCH (o)-[:CONCERNS]->(v) WHERE (v:Vehicle AND v.VehicleKind = 'ElectricVehicle') }` |
| guidée « véhicule dont le vin ne contient pas 12o » | les deux | `NOT EXISTS { MATCH  WHERE … }` | `NOT EXISTS { MATCH (v) WHERE v.vin IS NOT NULL AND … }` |
| `?v a am:Vehicle . FILTER EXISTS { ?v a am:NoSuchClass }` | les deux | `EXISTS { MATCH  }` | `WHERE false`, `[perte]` |

Comparaison de toutes les sorties, avant / après (scripts hors dépôt, état d'avant = commit 23b0e1c) :
- Corpus explicite : 126 traductions (fixtures `tests/fixtures/queries` × 2 avec le PG de fixture, avec et sans ontologie ; automaint et trap × neo4j et curiosity : 10 fixtures, questions de compétence (une réponse par cible et par exemple), 28 requêtes du lot sur automaint, 3 requêtes guidées). **33 sorties changent, toutes contiennent `EXISTS`, `NOT EXISTS` ou `MINUS`** : les 14 requêtes du lot dont le sous-motif se réduit à des typages ou à des propriétés, sur les deux cibles (28) ; le sous-motif avec type et relation (`exists_rel_typed`) sur les deux cibles (2) ; la requête guidée à filtre nié sur les deux cibles (2) ; `MINUS` avec relation sur curiosity (1, C# désormais marqué partiel). Les fixtures, les questions de compétence (automaint et trap), les requêtes guidées à étape niée ou optionnelle et les requêtes sans sous-motif ne changent pas.
- Requêtes des tests : chaque appel à `translate` de la suite complète a été enregistré avant et après (80 entrées distinctes communes) : **aucune sortie ne change**.
- Pertes (it1, corrigé en it2) : 7 sorties passaient de `lossy = true` à `false`. La revue query a montré que seule `exists_rel_typed` sur neo4j était une fausse perte (ElectricVehicle porte le label Vehicle). Les 6 autres (`ev_exists_cv`, `ev_notexists_cv`, `notexists_two_types`, sur les deux cibles) sont des intersections non représentables : elles retrouvent `lossy = true` en it2.
- Aucun `MATCH` vide dans les 126 sorties après la correction.

## Itération 2 : revues query, curiosity et neo4j it1 {#it2}

Réponses point par point : `journal/L53/fix-b12-it1.md`. Tests ajoutés ou modifiés dans `backend/tests/test_l53_b12.py` : 32 tests, dont 30 rouges sur 23b0e1c (les deux autres sont des tests de non-régression : FILTER sur une variable principale, garde sur un sous-motif intraduisible) et 15 rouges sur 183f0fd (it1).

**Problème 1 (query).** Un typage de sous-motif incompatible avec les types PG du nœud extérieur, ou deux typages incompatibles entre eux, est une intersection non représentable. Exemples : ElectricVehicle sous CombustionVehicle (aucun type de nœud commun sur neo4j), discriminants différents sur curiosity. L'it1 produisait le prédicat avec `lossy = false`. Sous `NOT EXISTS` / `MINUS`, le résultat PG peut être plus large que celui de SPARQL.
**Correction.** `_check_sub_types` (nouveau) compare chaque typage aux types du nœud par `_compatible`. Deux références sont compatibles si elles ont le même type de nœud (et la même valeur de discriminant quand les deux en ont une), ou si l'un des types porte le label de l'autre (multi-labels neo4j). Une incompatibilité donne une note `[perte]` (« intersection non représentable »), comme `add_type` au niveau principal. Le prédicat ne change pas.
**Résultat.** `ev_exists_cv`, `ev_notexists_cv` et `notexists_two_types` repassent à `lossy = true` sur les deux cibles. `exists_rel_typed` reste sans perte (Vehicle, cible de CONCERNS, est compatible avec ElectricVehicle).

**Problème 2 (query).** Une classe absente du PG sous négation donnait `WHERE true` (ou `NOT EXISTS { … WHERE false }`, toujours vrai) : un résultat élargi, contraire à la règle de sûreté.
**Correction.** Dans `sub_condition`, un sous-motif insatisfiable à cause d'un élément absent (classe absente capturée, nouveau nœud marqué vide, `false` posé par une propriété absente) donne `false` pour toute la condition sous `NOT EXISTS` / `MINUS`, avec une note `[perte]`. C'est cohérent avec le type sans label et le sous-motif intraduisible.
**Résultat.** `notexists_absent`, `minus_absent`, `notexists_rel_absent`, `notexists_new_absent` et `notexists_noprop` donnent `WHERE false` et `lossy = true` sur les deux cibles.

**Problème 3 (curiosity).** Le C# de `exists_rel_typed` perdait la restriction ElectricVehicle sans marquer la sortie partielle : `_simple_exists` ne voyait pas le typage capturé, et `cs_expr` levait `_Unsupported` sans effet sur `curiosity_ok`.
**Correction.** Un typage capturé rend le sous-motif « non simple », et `cs_expr` met `curiosity_ok` à faux chaque fois qu'un `EXISTS` / `NOT EXISTS` n'est pas traduit.
**Résultat.** `exists_rel_typed`, `exists_rel`, `notexists_rel`, `ro_notexists_rel`, les deux requêtes guidées niées (filtre et étape) et la question guidée « garage sans technicien » de `test_query_builder` sont marquées « Traduction partielle » en C#. C'est la seule sortie des tests qui change.

**Autres points.** La garde `_EMPTY_MATCH` ignore les chaînes et identifiants entre accents graves (`_CY_STRINGS`) : `FILTER(?vin = "MATCH }")` est de nouveau traduit. `.Where(n => false)` porte le commentaire `// aucun résultat (type du nœud)` au lieu de `À VÉRIFIER : accesseurs`.

## DF-B14 : MINUS sans variable partagée {#df-b14}

**Problème.** `?v a am:Vehicle . MINUS { ?o a am:RepairOrder }` donnait `WHERE NOT EXISTS { MATCH (o:RepairOrder) }` : aucun résultat dès qu'un ordre existe, avec `lossy = false`. SPARQL 1.1 (§8.3.3) n'exclut rien quand les deux motifs n'ont aucune variable commune. Existait avant L53.
**Correction.** `_Translator.pattern`, branche `Minus` : on calcule les variables partagées (`_vars` des deux opérandes d'algèbre). S'il n'y en a aucune, la condition est retirée, avec une note `[info]` qui cite §8.3.3.
**Résultat.** `MATCH (v:Vehicle) RETURN v.uri AS v` sur les deux cibles (`test_b14_minus_without_shared_variable_removes_nothing`, rouge avant). Un `MINUS` à variable partagée garde son exclusion.

## DF-B15 : FILTER sur une variable d'OPTIONAL {#df-b15}

**Problème.** `?o a am:RepairOrder . OPTIONAL { ?o am:concerns ?v } FILTER(!BOUND(?v))` donnait `MATCH (o:RepairOrder) WHERE NOT (v IS NOT NULL) OPTIONAL MATCH (o)-[:CONCERNS]->(v:Vehicle)`, où `v` n'est pas encore défini : Cypher invalide avec `lossy = false`. Même chose pour `FILTER(?vin = "X")` (propriété d'un nœud optionnel) et `FILTER NOT EXISTS { ?v a … }`. Existait avant L53.
**Correction.** `render_one` : les conditions du bloc principal qui citent une variable (nœud, ou propriété d'un nœud) liée seulement par un `OPTIONAL` (`cond_vars`, nouveau) ne vont plus dans le premier `WHERE`. Elles sont rendues après les `OPTIONAL MATCH`, dans `WITH *` puis `WHERE …`, avec une note `[info]`. `render_block` reçoit la liste à écarter (`skip`), et la boucle des conditions est isolée dans `render_conds`.
**Résultat.** `MATCH (o:RepairOrder)` / `OPTIONAL MATCH (o)-[:CONCERNS]->(v:Vehicle)` / `WITH *` / `WHERE NOT (v IS NOT NULL)` (tests `test_b15_*`, rouges avant). Un FILTER sur une variable du motif principal reste dans le premier `WHERE`.

## Comparaison it2 {#comparaison-it2}

Corpus porté à 148 traductions (11 requêtes ajoutées sur automaint × 2 cibles : MINUS sans variable partagée, FILTER sur variable d'OPTIONAL (3 formes, plus une sur variable principale), littéral « MATCH } », classe ou propriété absente sous négation (4 formes), NOT EXISTS avec relation sous RepairOrder). Le corpus a été rejoué sur trois états : 23b0e1c (avant L53), 183f0fd (it1) et l'it2.
- Avant L53 → it2 : 56 sorties sur 148 changent. Toutes contiennent `EXISTS`, `NOT EXISTS`, `MINUS`, ou un `FILTER` sur une variable d'`OPTIONAL`. Aucune fixture, question de compétence (automaint, trap) ni requête trap ne change. Pertes : seules `exists_rel_typed` (neo4j) et `opt_filter_notexists` (neo4j) passent de `lossy = true` à `false` ; les deux pertes venaient du typage qui modifiait la variable extérieure. Aucune sortie ne passe de `false` à `true`.
- it1 → it2 : 41 sorties changent : pertes rétablies (points 1 et 2), C# marqué partiel (point 3), DF-B14, DF-B15, garde sur les littéraux.
- Requêtes des tests (enregistrement de chaque appel à `translate`, suite complète) : 80 entrées communes avec l'état d'avant, 1 seule change. C'est le C# de la question guidée « garage sans technicien », désormais marqué partiel (point 3).
- Aucun `MATCH` vide dans les 148 sorties. Suite complète : **1680 tests verts**.

## Itération 3 : revues query et curiosity it2 {#it3}

Réponses point par point : `journal/L53/fix-b12-it2.md`. 19 tests ajoutés et un test corrigé ; sur 0e70f58 (it2), 20 des 51 tests de `test_l53_b12.py` échouent, et 49 sur 23b0e1c.

**Problème 1 (query).** Un sous-motif `EXISTS`, `NOT EXISTS` ou `MINUS` portait sur une variable d'`OPTIONAL` (placée après l'`OPTIONAL MATCH` depuis DF-B15). Sur une ligne où la variable n'est pas liée, la sortie s'écartait de SPARQL, avec `lossy = false` :
- `MINUS { ?v a am:ElectricVehicle }` retirait la ligne sur neo4j (`NOT v:…` vaut null), alors que §18.5 la garde (domaines disjoints) ;
- `NOT EXISTS` gardait la ligne sur curiosity (`coalesce`), alors que §18.6 évalue le sous-motif sur tout le graphe ;
- `EXISTS` retirait la ligne sur les deux cibles ;
- `NOT EXISTS { ?v am:vin ?x }` gardait la ligne sur neo4j.

**Correction.** `render_one` expose les nœuds d'OPTIONAL (`_opt_keys`) pendant le rendu des conditions tardives. `sub_condition` (enveloppe de `_sub_core`) regarde les nœuds extérieurs que touche le sous-motif :
- `MINUS` qui ne touche qu'une variable d'OPTIONAL : `(v IS NULL OR <condition>)`, forme exacte ;
- `EXISTS` / `NOT EXISTS` réduit au typage d'une variable d'OPTIONAL : `CASE WHEN v IS NULL THEN [NOT] EXISTS { MATCH (_any1) WHERE <prédicat sur _any1> } ELSE <condition> END`, forme exacte (`type_predicate` reçoit un autre identifiant) ;
- autres cas (propriété, relation, `MINUS` qui touche aussi une variable liée) : note `[perte]`, `lossy = true`.

**Résultat.** `opt_minus`, `opt_notexists` et `opt_exists` ont une forme exacte, sans perte, sur les deux cibles. `opt_notexists_vin` et `opt_minus_rel` passent en perte. Le test `test_b15_…[FILTER NOT EXISTS …]` attend désormais la forme `CASE` ; la forme étant exacte, `not lossy` y reste juste.

**Problème 2 (curiosity).** Un filtre C# produit par `cs_type_check` sur un nœud d'OPTIONAL (hors de la traversée) n'était jamais écrit, sans note ni marque partielle (`opt_filter_notexists`). De plus, sur la cible neo4j, `cs_type_check` jugeait « toujours vrai » un typage par un sous-type d'un nœud atteint par une relation (type `Vehicle` contre `ElectricVehicle`), et le filtre disparaissait.
**Correction.** `curiosity()` note les nœuds dont les filtres sont écrits (chaîne ou sous-ensemble). Tout autre nœud de `node_filters` met `curiosity_ok` à faux et ajoute une note `[curiosity]` « Filtre sur ?v (hors de la traversée…) non écrit ». `cs_type_check` lève `_Unsupported` (sortie partielle) quand le typage vise un autre type de nœud compatible par le label ; il met aussi `curiosity_ok` à faux pour les types multiples.
**Résultat.** `opt_filter_notexists`, `opt_minus`, `opt_exists` et `opt_filter_vin` sont marqués « Traduction partielle » sur les deux cibles (`test_it3_csharp_filter_on_optional_node_marks_partial`).

## DF-B18 : OPTIONAL et BIND dans un sous-motif {#df-b18}

**Problème.** Un `OPTIONAL` ou un `BIND` écrit dans un sous-motif `EXISTS`, `NOT EXISTS` ou `MINUS` débordait dans la requête principale : le bloc optionnel s'ajoutait aux blocs principaux, l'alias du `BIND` restait global, et les nœuds et propriétés du sous-motif restaient visibles. Exemples :
- `MINUS { ?o a am:RepairOrder OPTIONAL { ?o am:concerns ?v } }` ajoutait `OPTIONAL MATCH (o:RepairOrder)-[:CONCERNS]->(v)` à la requête principale ;
- `MINUS { ?o a am:RepairOrder BIND(?o AS ?v) }` donnait `RETURN o AS v` (Cypher invalide) ;
- `SELECT *` avec `NOT EXISTS { ?o am:concerns ?v . ?v am:vin ?x }` donnait `RETURN …, o.uri AS o` (Cypher invalide).

Dans tous ces cas, `lossy = false`. Le défaut existait avant L53.

**Correction.**
- `sub_condition` mémorise nœuds, propriétés, alias et blocs avant le sous-motif, puis restaure le tout après son rendu.
- `_sub_ctx` porte le genre du sous-motif et les variables du motif principal. `pattern` traite `LeftJoin` dans un sous-motif : la partie optionnelle est ignorée (`[info]`), ce qui est exact pour `EXISTS` / `NOT EXISTS` et pour un `MINUS` dont l'`OPTIONAL` ne lie aucune variable du motif principal ; sinon, une note `[perte]` est ajoutée.
- Un `BIND` sur une variable du motif principal donne `[perte]`. Un `BIND` local reste local.
- Une variable propre à un sous-motif projetée par `SELECT` vaut `null`, avec une note `[info]`, comme en SPARQL.

**Résultat.**
- `b18_notexists_opt` : plus d'`OPTIONAL MATCH` principal, sans perte ;
- `b18_minus_opt` : idem, avec `[perte]` ;
- `b18_minus_bind` : `RETURN v.uri AS v, null AS o`, avec `[perte]` ;
- `star_leak` : `null AS o`, `null AS x`, sans perte ;
- `b18_exists_bind_local` : `EXISTS { MATCH (o:RepairOrder)-[:CONCERNS]->(v) WHERE v.vin <> 'X' }`.

Tests : `test_b18_*`, tous rouges avant.

## Comparaison it3 {#comparaison-it3}

Corpus porté à 168 traductions (10 requêtes ajoutées × 2 cibles : sous-motifs sur une variable d'OPTIONAL, DF-B18, `SELECT *`), rejoué sur 23b0e1c, 183f0fd, 0e70f58 et l'it3.
- Avant L53 → it3 : 76 sorties sur 168 changent. Toutes contiennent `EXISTS`, `NOT EXISTS`, `MINUS`, ou un `FILTER` sur une variable d'`OPTIONAL`. Aucune fixture, question de compétence (automaint, trap) ni requête trap ne change.
- it2 → it3 : 24 sorties changent, toutes parmi les requêtes à variable d'OPTIONAL ou DF-B18. `lossy` passe à vrai pour `opt_notexists_vin`, `opt_minus_rel`, `b18_minus_opt` et `b18_minus_bind` (deux cibles), sans autre passage.
- Requêtes des tests : 80 entrées communes avec l'état d'avant, 1 seule change, comme en it2 (C# « garage sans technicien » marqué partiel).
- Aucun `MATCH` vide. Aucun appel nouveau à l'analyseur rdflib dans `translate.py` (`prepareQuery` et `translateGroupGraphPattern` existaient déjà), pour la fusion avec `queries/sparql_lock.py` de L53-b13.

## Finitions après la relecture it3 {#finitions}

Relectures it3 : query, curiosity et neo4j OK. Quatre finitions demandées avant la fusion.
- **C# : FILTER non traduit.** La branche générique « FILTER non traduit en Query API » de `curiosity()` met maintenant `curiosity_ok` à faux : la sortie est marquée partielle. Exemple : `?o a am:RepairOrder . OPTIONAL { ?o am:concerns ?v } FILTER(!BOUND(?v))` donnait `StartAt(N.RepairOrder.Type).Emit("N")`, soit tous les ordres, sans marque. Test `test_finish_untranslated_filter_marks_csharp_partial`.
- **SELECT \*.** Une variable propre à un sous-motif est hors de portée (SPARQL 1.1 §18.2.1) : elle ne donne plus de colonne avec `SELECT *` (note `[info]` « hors de portée »). Nommée dans le `SELECT`, elle garde `null` et la note `[info]` « comme en SPARQL », qui est alors exacte. Le `SELECT *` est reconnu sur le texte de la requête, sans commentaires, chaînes ni IRI (`_SELECT_STAR`, aucun appel à l'analyseur rdflib). Test `test_b18_subpattern_variables_do_not_leak_into_projection` adapté (`SELECT *` puis `SELECT ?v ?o`).
- **Variable d'un OPTIONAL ignoré dans un EXISTS** (`exists_opt_new`, `?w`) : enregistrée comme propre au sous-motif, donc `[info]` au lieu de `[perte]`. Les variables de la partie optionnelle sont maintenant lues par parcours de l'algèbre (`cond_vars`), parce que `_vars` manque sous `EXISTS`. Test `test_finish_variable_of_ignored_optional_in_exists_is_info`.
- **Documentation.** Phrase dépassée de la section Reste reformulée, commentaire de `_opt_keys` remis sur sa ligne (`translate.py`).

**Comparaison.** Corpus de 172 traductions (2 requêtes ajoutées × 2 cibles : `exists_opt_new`, `star_explicit`), rejoué sur 23b0e1c, 0e70f58, a120ca3 et les finitions.

**Correction d'une erreur de mesure.** Le corpus dépassait le limiteur de débit de l'API (`ONTOFORGE_RATE_HEAVY_PER_MIN`, 120 par minute) : les dernières traductions, celles de l'exemple trap, recevaient un 429 sur tous les états, si bien que la comparaison « aucune requête trap ne change » de l'it3 n'était pas mesurée. Les scripts tournent désormais avec `ONTOFORGE_RATE_LIMIT=0`, et plus aucune réponse 429 n'apparaît.
- a120ca3 → finitions : 9 sorties changent.
  - `star_leak` et `b18_minus_bind` (deux cibles) : colonnes `null` retirées.
  - `exists_opt_new` (deux cibles) : `lossy` passe de vrai à faux.
  - `opt_filter_bound` (deux cibles) : C# marqué partiel.
  - trap `q07_filter_regex` sur curiosity : C# marqué partiel, parce que le REGEX n'est pas traduit en Query API.
- Avant L53 → finitions : 81 sorties sur 172 changent. Hors requêtes du lot, ce sont les quatre requêtes guidées niées (filtre et étape, deux cibles), déjà listées, et trap `q07_filter_regex` (C# partiel). Les fixtures en Cypher, les questions de compétence et les autres requêtes trap ne changent pas.
- Requêtes des tests : 80 entrées communes avec l'état d'avant, 7 changent, toutes seulement par la marque « Traduction partielle » du C# (finition 1, et le « garage sans technicien » déjà compté).
- Aucun `MATCH` vide. Suite complète : 1703 verts.

## Reste {#reste}

- DF-B16 (consigné, non corrigé) : sur neo4j, une relation vers un sous-type (`?o am:concerns ?v . ?v a am:ElectricVehicle`, étape guidée niée comprise) donne une fausse perte « Relation incompatible ». Elle est dans le sens sûr.
- Non vérifié contre un vrai Neo4j (`À VÉRIFIER`) : `CASE WHEN v IS NULL THEN EXISTS { MATCH (_any1) WHERE … } ELSE … END` (sous-requête existentielle dans `CASE`), les formes produites (`v:Label` en `WHERE`, `NOT v:Label`, `EXISTS { MATCH (v) WHERE … }` avec `v` lié à l'extérieur, `coalesce` sur une comparaison) sont du Cypher 5 standard, de même que `WITH *` suivi de `WHERE` (DF-B15). `À CONFIRMER` par neo4j sur une base chargée.
- Pseudo-code C# : `n.GetString(N.<Type>.<Discriminant>)` reprend les accesseurs déjà marqués `À VÉRIFIER` ; à relire par curiosity. Sur la cible neo4j, une variable typée par une classe portée par plusieurs types de nœuds (`am:Vehicle`) n'a toujours pas de C# (« Type du nœud de départ inconnu »), comme avant (non-bloquant de la revue query L52).
- `MINUS` à variable partagée est lu comme `NOT EXISTS`. Le côté principal (variable d'`OPTIONAL` non liée : forme exacte ou `[perte]`, [it3](#it3)) et le côté sous-motif (`OPTIONAL` ou `BIND` dans le sous-motif, [DF-B18](#df-b18)) sont traités. Un `EXISTS` avec relation n'est pas traduit en C# (note `[curiosity]`, sortie marquée partielle).
- Le skill `skills/graph-query-translation` (propriétaire query) peut reprendre les règles de la revue query it1 : typage de sous-motif = condition ; intersection non représentable = perte, aussi en sous-motif ; sous négation, une perte vaut `false` ; MINUS sans variable partagée n'exclut rien ; FILTER sur une variable d'OPTIONAL après l'OPTIONAL MATCH.
