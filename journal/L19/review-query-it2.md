verdict: OK
bloquants:
  (levés : COUNT/SUM justes sans DISTINCT, FROM multiples fusionnés en ensemble, FROM remplace l'union)
non-bloquants:
  - Mêmes tests que review-w3c-it2 (tests/test_local_store_union.py). Côté requêtage : `FROM a FROM NAMED b` donne un défaut = a et GRAPH = b seul ; `FROM a FROM b FROM NAMED a FROM NAMED b` donne un défaut dédupliqué (2) et GRAPH ?g = 3 ; jointure défaut/GRAPH correcte.
  - Trois chargements concurrents du même contenu (2 000 triplets) : COUNT = 2 000 dans l'union, 6 000 via GRAPH ?g.
  - Lecteurs et écrivains : le verrou fait attendre les requêtes pendant la reconstruction (jusqu'à environ 4 s à 186 000 triplets) ; le délai de la requête ne court pas pendant l'attente du verrou, mais celui du client HTTP peut : à surveiller. Indicateur « reconstruction en cours » recommandé (voir review-w3c-it2), non bloquant.
  - Reste du it1 inchangé : écart avec un endpoint externe (graphe par défaut non union) documenté dans le guide §11 et CONTRACTS §6.1.
skill: skills/graph-query-translation — « sur le triplestore local, l'attente du verrou d'écriture n'est pas comptée dans le délai de requête ».
