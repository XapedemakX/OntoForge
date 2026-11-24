# Revue devback : L53-b13, itération 3 (commit ce8cf1d)

Relecteur : devback. Lu : `journal/L53/fix-b13-it2.md`, le diff `aefb51e..ce8cf1d` (`backend/ontoforge`, `backend/tests`, `docs/dev`). Sondes de sabotage jetables hors dépôt (`/home/claude/tmp-devback/sabot`, `/home/claude/tmp-devback/it1code`). Aucun fichier du dépôt modifié sauf cette revue.

```
verdict: OK
bloquants: aucun
```

## Tableau {#tableau}

| Point | Verdict | Constat et preuve |
|---|---|---|
| B1 : compteur sur `Query.parseString` / `UpdateUnit.parseString` | OK | `_count_sparql_parses` remplace les points d'entrée de la grammaire, que partagent toutes les copies (`parser.parseQuery`, `processor.parseQuery`), et `monkeypatch` les restaure. |
| Le témoin peut échouer | OK | Copie du test, hors dépôt, avec l'ancien compteur (remplacement de `parser.parseQuery` seul) : `test_b17_counter_sees_graph_query_calls` **échoue** (`assert 0 >= 1`). |
| Le test pySHACL peut échouer | OK | Copie du test, hors dépôt, où pySHACL reçoit la shape `sh:sparql` comme graphe de shapes avec `advanced=True` : `test_b17_pyshacl_in_the_server_does_not_reach_the_sparql_parser` **échoue** (`['Query'] == []`). Le témoin passe dans la même copie. Le test d'origine reste vert (0 appel avec les arguments de `editing/files.py::_shacl_shacl`). |
| NB 1 : `purge_idle` relit l'horloge sous `try_write` | OK | Relecture sous `_USE_GUARD`, verrou d'écriture tenu. `touch` ne demande pas le verrou du projet : un usage qui commence avant la purge est donc toujours vu. Le test `test_b13_purge_rereads_the_clock_under_the_lock`, lancé sur le code de l'it1 (`aefb51e`), **échoue** : il prouve bien la correction. |
| NB 1 : `stats` | OK | `exists` refait sous le verrou de lecture : une base purgée entre-temps donne `exists: False` au lieu d'un 503. |
| NB 2 : graphe inféré dans le budget disque, `refresh` compris | OK | `materialize` contrôle (inférés − présents) avant `_replace_graph`. Le 413 laisse l'ancien graphe inféré en place. Dans `load_data`, le bloc `except` de `work` restaure le fichier. Dans `refresh`, rien n'est écrit. Le test `test_b13_inferred_graph_counts_in_the_disk_cap_all_or_nothing` couvre les deux cas et **échoue** sur le code de l'it1. |
| NB 3 : test de concurrence, état final | OK | Chaque base est soit purgée avec son avis, soit intacte avec son dernier fichier (un triplet) ; aucun dossier sans `meta.json`. |
| NB 4 : place de chargement pendant l'attente du verrou | OK (limite consignée) | Raison acceptée : relâcher la place avant le verrou laisserait le fichier analysé en mémoire hors de la borne de 124 Mo. La limite est consignée au chapitre 10 (fr, en). |
| NB 5 : contrôle non atomique entre projets | OK (consigné) | Chapitre 10. |
| Suite complète | OK | **1669 passed** en 4 min 10 (depuis `backend/`, `env -u ONTOFORGE_DATA PYTHONPATH=/home/claude/wt/L53-b13/backend /home/claude/venv/bin/python -m pytest -q`). Lancée depuis la racine du dépôt, 3 tests échouent parce qu'ils lisent `../samples` en chemin relatif : ce sont des tests anciens, sans rapport avec le lot, et c'est la commande du contrat qui s'applique. |
| Doc 09, 10, 16, 17 : parité fr / en | OK | Mêmes ancres et même nombre de lignes dans chaque paire de fichiers. |

## Non-bloquants {#non-bloquants}

1. `docs/dev/10-triplestore-local.md` et `.en.md`, ligne 73 : la valeur Cloud Run passe à 640, mais la phrase finale dit toujours « 704 Mo en laissent environ 100 ». Avec 640, il reste environ 64 Mo au-dessus du plancher de 576 Mo mesuré pour une base de 50 000 triplets au plus, et aucune marge pour une base de 1 000 000 triplets (640 mesurés). À corriger.
2. `journal/L53/corrections-b13.md`, ligne 48 : le tableau « Valeurs retenues » indique encore « 1 × 704 | 704 » pour les fils. Il faut soit le mettre à jour, soit le dater comme valeur de l'it1.

skill: rien (règle confirmée pour `skills/technical-documentation` : prouver qu'un test « garde-fou » peut échouer, en le sabotant hors du dépôt).
