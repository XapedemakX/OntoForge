# Revue devback : L53-b13, itération 2 (commit def5e40)

Relecteur : devback. Lu : `journal/L53/fix-b13-it1.md`, le diff `79a6e40..def5e40` de `backend/ontoforge` et `backend/tests`, les chapitres 09 et 10 (fr, en). Sondes jetables hors dépôt (`/home/claude/tmp-devback`). Aucun fichier du dépôt modifié sauf cette revue.

```
verdict: KO
bloquants:
  - [backend/tests/test_l53_b17.py::test_b17_pyshacl_in_the_server_does_not_reach_the_sparql_parser] le test ne peut pas échouer
```

## Tableau {#tableau}

| Point | Verdict | Constat (fichier, fonction) |
|---|---|---|
| `load_slot`, libération | OK | `store.py::load_slot` : même modèle que `child_slot` (`acquire(blocking=False)` hors du `try`, `release` dans `finally`). `api/local_store.py::load` : le `return` dans le `with` et les `StoreError` passent par le `finally` ; un refus devient `StoreBusy` 503 et `_err` pose `Retry-After: 5`. Test `test_b13_load_slots_give_503_when_busy`. |
| Ordre des verrous, interblocage | OK | Les seules prises bloquantes sont `lock(pid).read()` / `.write()` et les petits verrous internes (`_USE_GUARD`, `_LOCKS_GUARD`, condition du `_RWLock`). Les places (`load_slot`, `child_slot`) et `try_write` ne bloquent jamais. Ordre : place de chargement → `ensure` (`purge_idle` : `try_write` sur les autres projets, rien de tenu) → `lock(pid).write()` → place de fils. `ensure` n'est jamais appelé en tenant un verrou de projet. `_USE_GUARD` est pris sous `try_write`, jamais l'inverse. Pas de cycle possible. |
| Plafond disque : calcul | OK | `check_disk_budget` : `(used + n × 500 o) × 1,25 > cap` → 413. `n_new = len(tmp)` majore les triplets ajoutés (un remplacement compte tout le fichier), et `used` est la taille réelle mesurée (`dir_size_mb`) : le calcul est prudent. Sonde : la recharge d'un même fichier fait passer le dossier de 2,4 à 4,6 Mo (anciens fichiers RocksDB pas encore compactés), et la mesure réelle les compte. |
| Plafond disque : tout ou rien | OK | Contrôle fait sous `lock(pid).write()`, avant `work`, donc avant toute écriture ; `meta.json` intact. Test `test_b13_disk_cap_refuses_a_load_that_does_not_fit` (gros fichier refusé, petit accepté, rien de résiduel). Création d'une base : `ensure` contrôle avant `_sync_ontology`. |
| Purge : sous le verrou de chaque projet | OK | `purge_idle` supprime sous `lock(pid).try_write()` : une requête (lecture tenue pendant tout le fils), un chargement, une inférence ou `stats` (lecture) empêchent la suppression. Test `test_b13_purge_never_deletes_a_database_in_use`. |
| Purge : course avec un usage qui commence | OK avec réserve | Fenêtre étroite décrite en non-bloquant 1 : effets bornés (un 502 ou 503 isolé, ou un fichier chargé dans une base recréée), pas de corruption. |
| Tests de concurrence réels | OK | `test_b13_purge_and_loads_run_concurrently_without_error` : 4 fils, vrais chargements et lectures, horloge remise à 0 à chaque tour, ce qui provoque de vraies purges croisées. Il vérifie les codes et l'arrêt des fils, mais pas l'état des bases à la fin (voir non-bloquant 3). |
| Test fragile durci | OK | Délais à 90 s, chauffe (analyseur et cinq magasins), `done == 3` avec message, fils et faux fils terminés. Cinq passes de `test_l53_b13.py` et `test_l53_b17.py` : 18 verts à chaque fois. |
| Garde DF-B17 élargie (`ast`) | OK | Tous les fichiers du serveur sont couverts (`__init__.py`, `_owlrl_core.py`) ; seuls les quatre scripts de fils sont exclus, par leur nom. Imports renommés, `prepareUpdate`, `translateUpdate`, `.query(` hors Oxigraph : repérés. `test_b17_guard_sees_what_it_claims_to_see` contrôle la garde elle-même. Bonne correction. |
| Test pySHACL | **KO** | Voir bloquant B1. |
| Non-bloquants it1 4, 5, 6 | OK | Parité du chapitre 09 alignée (puce DF-B17 au même endroit) ; phrase du journal corrigée ; imports de `sparql_lock` laissés tels quels, refus motivé, accepté. |
| Suite complète | OK | **1666 passed** en 4 min 41 (`env -u ONTOFORGE_DATA PYTHONPATH=/home/claude/wt/L53-b13/backend /home/claude/venv/bin/python -m pytest -q`). |
| Doc 10 (fr, en) | OK, sauf deux points | Tableau des variables et paragraphe « Disque éphémère » exacts et en parité. Le chapitre 09 décrit le test pySHACL comme une vérification (voir B1). Le chapitre 10 ne dit pas que le graphe inféré n'entre pas dans le budget disque (voir non-bloquant 2). |

## Bloquant {#bloquants}

**B1. `test_b17_pyshacl_in_the_server_does_not_reach_the_sparql_parser` ne voit aucun appel, et ne peut donc pas échouer.** Le test remplace `rdflib.plugins.sparql.parser.parseQuery` / `parseUpdate`. Or `rdflib/plugins/sparql/processor.py` les a importés par nom (`from rdflib.plugins.sparql.parser import parseQuery, parseUpdate`), et `Graph.query`, `prepareQuery` et pySHACL passent par cette copie. Sonde : avec le même remplacement que le test, `rdflib.Graph().query("ASK {}")` donne **0 appel compté**. Le test passerait donc même si pySHACL analysait du SPARQL à chaque validation, alors que le chapitre 09 (fr, en) et `fix-b13-it1.md` le donnent comme le garde-fou de ce cas. (Ma sonde de l'it1 remplaçait aussi `processor.parseQuery` : sa mesure de « 0 appel » reste valable, mais le test, lui, ne la refait pas.)
Correction attendue :
- remplacer aussi `rdflib.plugins.sparql.processor.parseQuery` et `parseUpdate`, ou plus simplement les points d'entrée de la grammaire (`parser.Query.parseString`, `parser.UpdateUnit.parseString`), que toutes les copies partagent ;
- ajouter un **témoin positif** dans le même test : un `rdflib.Graph().query("ASK {}")` sous le même remplacement doit compter au moins un appel. Sinon le test redevient muet à la prochaine version de rdflib.

## Non-bloquants {#non-bloquants}

1. **Fenêtre de course dans `purge_idle`.** L'horloge (`last`) est lue sous `_USE_GUARD`, puis `try_write` est pris plus tard, sans relire l'horloge. Si, entre les deux, un autre fil fait `ensure(pid)` en entier (`touch`, puis verrou d'écriture pris et rendu) et n'a pas encore pris son verrou suivant, la base qu'il vient de toucher peut être supprimée. Effets possibles, rares et sans corruption : `run_local` lance son fils sur une base absente (502 « erreur interne ») ; `load_data` écrit dans une base recréée vide, et l'ontologie revient au `ensure` suivant ; `stats` peut voir `exists` vrai puis ouvrir une base disparue (503 « illisible »). Correction simple : relire `_LAST_USE[pid]` une fois `try_write` obtenu, et ne purger que si la base est toujours inactive ; dans `stats`, refaire `exists(pid)` sous le verrou de lecture.
2. **Le graphe inféré n'entre pas dans le budget disque.** `check_disk_budget(n_new)` compte le fichier chargé, pas ce que `materialize` ajoute ensuite. `refresh` (calcul de l'inférence sans fichier) ne contrôle rien. Pour automaint, l'inférence n'ajoute que 167 triplets, mais en OWL RL ce volume dépend des données, et la somme au pire (1985 Mo, marge 63 Mo) suppose le dossier borné à 64 Mo. À faire : contrôler après `materialize` (taille réelle, 413 et retour à l'état d'avant, comme pour un échec d'inférence), ou borner le nombre de triplets inférés. Le dire au chapitre 10 et dans le README Cloud Run.
3. **Le test de concurrence purge / chargement** vérifie l'absence de 500, mais pas l'état final. Ajouter : chaque projet chargé en dernier a bien son fichier dans `stats` (`graphs`), et aucun dossier de base sans `meta.json`.
4. **La place de chargement est tenue pendant l'attente du verrou du projet** (`ensure` et `lock(pid).write()` sont bloquants). Sur Cloud Run (`LOAD_SLOTS=1`), une requête de 120 s sur le projet A fait répondre 503 à tous les chargements, sur tous les projets, tant qu'un chargement sur A attend. Pas d'interblocage, mais une disponibilité réduite. Cela reste acceptable pour une démo à un compte ; à noter au chapitre 10.
5. **Le contrôle disque n'est pas atomique entre projets.** Deux chargements sur deux projets peuvent mesurer `used` avant l'écriture de l'autre. Sur Cloud Run, `LOAD_SLOTS=1` les met en série, mais pas la création d'une base par `ensure` (10 000 triplets estimés) ni l'inférence. L'effet est petit et couvert par la marge de 1,25 ; une phrase dans le chapitre 10 suffit.

skill: rien (pour `skills/technical-documentation`, une règle à retenir : un test qui remplace une fonction pour compter ses appels doit contenir un témoin positif, sinon il peut rester muet).
