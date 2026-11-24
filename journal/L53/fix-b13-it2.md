# L53-b13 : correction, itération 2

Pilote : secu. Réponses à `review-deploiement-b13-it2.md` (979db10 : B3 bloquant, réglages proposés) et `review-devback-b13-it2.md` (aefb51e : KO, B1). Détail : `journal/L53/corrections-b13.md`, section « Itération 2 ».

## Bloquants

| # | Constat | Réponse |
|---|---|---|
| B3 (deploy) | Le repli du README §8 donne `roles/secretmanager.secretAccessor` au compte de construction (contredit §8.2) | **Corrigé.** Remplacé par la vérification des rôles existants (`run.developer` et `iam.serviceAccountUser` sur `ontoforge-run` pour le compte de construction ; `secretAccessor` seulement pour `ontoforge-run`), avec la phrase « jamais d'accès aux secrets pour le compte de construction, ni `roles/run.admin` ». Repli gardé : retirer `--set-secrets` du déclencheur seulement, puis contrôler avec le §7. À VÉRIFIER maintenu : `run.developer` contre `run.admin` pour poser des références de secrets. Aucun autre document ne portait ce repli (recherche dans `docs/` et `deploy/`). |
| B1 (devback) | `test_b17_pyshacl_in_the_server_does_not_reach_the_sparql_parser` ne peut pas échouer (`processor.py` importe `parseQuery` par nom) | **Corrigé.** Reproduit d'abord : avec l'ancien remplacement, `Graph().query("ASK {}")` donne 0 appel. Le compteur remplace `parser.Query.parseString` et `parser.UpdateUnit.parseString` (partagés par toutes les copies) ; témoin positif `test_b17_counter_sees_graph_query_calls` (≥ 1 appel pour un `Graph().query`). Le test pySHACL passe toujours (0 appel). Chapitre 09 fr/en : formulation ajustée ; `fix-b13-it1.md` : rectificatif ajouté. |

## Réglages (proposition du déploiement)

- `ONTOFORGE_LOCAL_STORE_MEMORY_MB` : **640** (avant 704). Retenu.
- `ONTOFORGE_MAX_BODY_MB` : **12** (et non 8). Vérifié dans le code : 8 Mo casserait deux envois permis, les documents de l'assistant (`ONTOFORGE_DOC_MAX_MB`, 10 Mo, `assistant/document.py`) et les imports de schémas (10 Mo cumulés par requête, `importers/limits.py::MAX_TOTAL_MB` ; 2 Mo par fichier, jusqu'à 20 par réglage). Les ontologies (`api/files.py`, 4 × 2 Mo = 8 Mo), le triplestore (5 Mo) et l'assistant (2 Mo) tiennent dans 8. Le corps (12) est compté dans la somme (test, `env.yaml`, README, docs/dev 16 et 17).
- **Nouvelle somme au pire : 1933 Mo** = 175 + 320 + 256 + 342 + 640 + 124 + 64 + 12 ; **marge de 115 Mo** (1921 et 127 avec 8 Mo non compté). Les envois simultanés au-delà du premier sont pris sur la marge (environ 9 corps de 12 Mo avant leur 503).

## Non-bloquants devback

| Point | Réponse |
|---|---|
| 1. Course dans `purge_idle`, `stats` | Corrigé : horloge relue sous `try_write`, `exists` refait sous le verrou de lecture dans `stats`. Test `test_b13_purge_rereads_the_clock_under_the_lock`. |
| 2. Graphe inféré hors budget disque | Corrigé : `materialize` contrôle `check_disk_budget` (triplets inférés moins ceux déjà présents) avant de remplacer le graphe inféré ; 413 tout ou rien, valable pour un chargement et pour `refresh`. Test `test_b13_inferred_graph_counts_in_the_disk_cap_all_or_nothing`. Chapitre 10 fr/en. |
| 3. Test de concurrence, état final | Corrigé : chaque base est purgée avec son avis, ou intacte avec son dernier fichier ; aucun dossier sans `meta.json`. |
| 4. Place de chargement tenue pendant l'attente du verrou | **Non modifié, limite consignée** (chapitre 10 fr/en) : le fichier analysé occupe la mémoire du serveur pendant l'attente, donc relâcher la place avant le verrou romprait la borne de 124 Mo. |
| 5. Contrôle disque non atomique entre projets | Consigné (chapitre 10) : places uniques sur Cloud Run, marge de 1,25. |

## Vérifications

Suite complète : 1669 passés (backend) ; front non modifié.
