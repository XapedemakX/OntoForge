# L53 : DF-B13 et installation CI sans contraintes

Pilote : secu. Défauts traités : DF-B13, DF-B17 (relevé pendant DF-B13), et l'installation CI. Source : `journal/L51/defauts.md` (DF-B13), `journal/L52/review-secu-back-it2.md`, `journal/L52/corrections-backend.md` (DF-B03, DF-B07, plafonds Cloud Run). Tests : `backend/tests/test_l53_b13.py` (5 tests ; les quatre premiers échouaient avant la correction). Mesures faites le 24/11 sur les jeux du dépôt, hors dépôt (scripts jetables sous `/home/claude/tmp-l53`).

## DF-B13 : places des fils du triplestore local et plafonds Cloud Run {#df-b13}

### Problème

Chaque plafond mémoire (`RLIMIT_AS`, `-Xmx`) borne UN processus fils. Le conteneur Cloud Run (2 Gio, une instance) est menacé par la somme :
- les fils du triplestore local (requêtes de `localstore/runner.py::run_local`, inférence de `localstore/store.py::materialize`) n'avaient aucun nombre de places : seul le verrou lecteurs / écrivain **par projet** les sérialise, donc N appels sur N projets lançaient N fils ;
- `ONTOFORGE_SHACL_MEMORY_MB` valait 2048 (tout le conteneur pour une validation), `ONTOFORGE_HERMIT_SLOTS` 2 avec un tas de 768 Mo (plus la JVM), le triplestore local 1024 Mo par fil : la somme au pire dépassait donc largement 2048 Mo : 175 + 2048 (SHACL) + 1024 (OWL RL) + 2 × (768 + 150) (HermiT, deux places avec la JVM) + 1024 (une seule place du triplestore) = 6107 Mo, et sans borne pour le triplestore (une place de 1024 Mo par projet en parallèle).

Conséquence : un compte autorisé qui travaille sur plusieurs projets en parallèle peut arrêter l'instance (déni de service, CWE-770). Aucune lecture ni écriture de données.

Reproduction : `test_b13_query_children_are_capped_and_overflow_gives_503` lance une requête locale sur chacun de 5 projets (faux `run_limited` qui retient le fils) et lit le pic de fils simultanés : **5** avant, avec cinq réponses 200. Même mesure en processus réels : quatre `POST /store/load` avec `inference=both` sur quatre projets en même temps, comptage des processus `_infer_worker.py` dans `/proc` toutes les 100 ms : **4 fils simultanés**, quatre réponses 200.

### Correction

- `backend/ontoforge/localstore/store.py` : `BoundedSemaphore` (`_SLOTS`, variable `ONTOFORGE_LOCAL_STORE_SLOTS`, 2 par défaut, entre 1 et 32, valeur invalide → 2, lu à l'import comme SHACL) et gestionnaire `child_slot()` qui prend une place sans attendre et lève `StoreBusy` (sous-classe de `StoreError`, 503, `retry_after = 5`) si elles sont toutes prises. Une seule famille de places pour les requêtes et l'inférence, tous projets confondus (même plafond mémoire, donc même coût).
- `localstore/runner.py` : `run_local` prend la place juste avant `run_limited` (donc après le verrou du projet, jamais pendant l'attente) ; `StoreBusy` devient `EndpointError(503, retry_after=5)`. `materialize` fait de même ; `StoreBusy` remonte, `load_data` rétablit le graphe précédent (tout ou rien, comme pour un plafond atteint).
- `queries/endpoint.py` : `EndpointError` porte un `retry_after` facultatif. `api/queries.py::_ep_error` et `api/local_store.py::_err` posent l'en-tête `Retry-After` quand il existe. Message traduit en anglais dans `localize/phrases.py`.
- `deploy/cloudrun/env.yaml` : 1 place par famille et plafonds mesurés (tableau ci-dessous). Test de garde `test_b13_cloudrun_env_sum_at_worst_fits_in_2_gib` : relit le fichier, refait la somme, échoue au-delà de 2048 Mo.
- Documentation : `deploy/cloudrun/README.md` (section « Plafonds et somme au pire »), manuel `docs/dev` chapitres 05, 06, 10, 16, 17 (fr, en), CHANGELOG fr / en.

Mesures (24/11 ; « AS » = plus petit `RLIMIT_AS` qui réussit parmi les valeurs essayées, « RSS » = pic de mémoire résidente du fils) :

| Famille | Cas | AS minimal | RSS |
|---|---|---|---|
| SHACL | « trap », inférence `none` et `both` | 64 Mo (48 échoue) | 33 et 38 Mo |
| SHACL | automaint + données, 42 000 triplets de données, `none` | 192 Mo (128 échoue) | 124 Mo |
| SHACL | automaint, 4 100 triplets, inférence `both` | délai de 30 s atteint (SIGXCPU à 32 s) avant tout plafond mémoire, quel que soit le plafond essayé (256 à 2048 Mo) | 116 Mo à 32 s |
| OWL RL (conformité) | 7 000 triplets, 10 s | 96 Mo (le plus bas essayé) | 52 Mo |
| OWL RL | 22 000 triplets | délai de 30 s (SIGXCPU à 32 s) avant tout plafond mémoire, de 128 à 256 Mo | 104 Mo à 32 s |
| HermiT | « trap », tas de 32 à 768 Mo | 32 Mo réussit mais la taille de la sortie diffère sous 128 Mo ; 128 Mo donne la même sortie qu'à 768 Mo | 130 Mo (tas 32) à 252 Mo (tas 768) |
| HermiT | automaint + 4 700 triplets de données, délai de 51 s (au-dessus des 30 s par défaut) | tas de 128 Mo suffisant | 225 Mo (tas 128), 366 Mo (tas 512) |
| Triplestore local, requête | base de 4 700 triplets (2,5 Mo sur disque) | 576 Mo (512 échoue) | 32 Mo |
| Triplestore local, requête | base de 1 000 000 triplets (312 Mo sur disque, le plafond du magasin) | 640 Mo (576 échoue) | 32 Mo |
| Triplestore local, inférence `both` | 28 000 à 31 000 triplets sources (le plafond est de 30 000) | 512 Mo réussit à 28 000, 576 Mo à 31 000 (plus bas essayé) | 86 à 92 Mo |

Valeurs retenues et somme au pire (toutes les places prises en même temps) :

| Variable | Avant | Après | Au pire (Mo) |
|---|---|---|---|
| Serveur | — | — | 175 |
| `ONTOFORGE_SHACL_SLOTS` × `ONTOFORGE_SHACL_MEMORY_MB` | 1 × 2048 (défaut) | 1 × 320 | 320 |
| `ONTOFORGE_OWLRL_SLOTS` × `ONTOFORGE_OWLRL_MEMORY_MB` | 1 × 1024 | 1 × 256 | 256 |
| `ONTOFORGE_HERMIT_SLOTS` × (`ONTOFORGE_HERMIT_MAX_MB` + JVM 150) | 2 × (768 + JVM) | 1 × (192 + 150) | 342 |
| `ONTOFORGE_LOCAL_STORE_SLOTS` × `ONTOFORGE_LOCAL_STORE_MEMORY_MB` (fils) | sans limite × 1024 | 1 × 704 (it2 : 640) | 704 (it2 : 640, voir [Itération 2](#it2)) |
| Chargement d'un fichier dans le serveur : `ONTOFORGE_LOCAL_STORE_LOAD_SLOTS` × ((`MAX_TRIPLES` + 20 000) × 1,7 Mo / 1 000 + `MAX_UPLOAD_MB`) (it1) | sans place, 1 000 000 triplets, 25 Mo (environ 1 Go) | 1 × ((50 000 + 20 000) × 1,7 / 1 000 + 5) | 124 |
| Disque en mémoire : `ONTOFORGE_LOCAL_STORE_TOTAL_MB` (it1) | sans plafond | 64 | 64 |
| **Total** | 6107 Mo avec une seule place du triplestore, hors chargement et disque ; sans borne en réalité | | **1985 Mo, marge de 63 Mo** (it1 ; 1861 Mo avant la relecture, qui ne comptait ni le chargement ni le disque) |

Choix, plafond par rapport au plus petit qui réussit sur le plus gros cas mesuré : SHACL 320 pour 192 (1,7 fois, sa mémoire dépend du volume de données) ; OWL RL 256 pour 96 (2,7 fois) ; tas HermiT 192 pour 128 (1,5 fois) ; triplestore 768 pour 640 (1,2 fois : le plancher d'espace d'adressage de RocksDB, environ 600 Mo, laisse peu de mémoire de travail, d'où le budget le plus large pour cette famille, pris sur SHACL, OWL RL et HermiT dont les besoins mesurés sont bas). 150 Mo de JVM sont comptés hors tas pour HermiT (130 Mo mesurés pour une JVM de tas 32 Mo). Les caps Python sont des plafonds d'espace d'adressage : la somme des pics résidents mesurés (175 + 124 + 104 + 225 + 92 = 720 Mo, soit environ 0,7 Gio) est d'environ 0,7 Gio, mais le calcul retient les plafonds pour que la garantie ne dépende pas du contenu des fichiers.

### Résultat avant / après

| Mesure | Avant | Après |
|---|---|---|
| Fils de requête simultanés pour 5 projets (test, faux fils) | 5 (cinq 200) | 2 au plus (deux 200, trois 503 avec `Retry-After: 5`) |
| Fils d'inférence simultanés pour 4 chargements `both` sur 4 projets (processus réels, `/proc`) | 4 (quatre 200) | `SLOTS=2` : 2 (deux 200, deux 503) ; `SLOTS=1` : 1 (un 200, trois 503) |
| Somme au pire de `env.yaml` | 6107 Mo avec une seule place du triplestore local ; sans borne en réalité | 1985 Mo (chargement et disque en mémoire compris, it1) |
| Défauts d'`env.yaml` | SHACL 2048 Mo, HermiT 2 places | SHACL 320 Mo, HermiT 1 place |

Tests (`backend/tests/test_l53_b13.py`) :
- `test_b13_query_children_are_capped_and_overflow_gives_503` : reproduction et correction (échouait avant : 5 fils).
- `test_b13_slots_are_released_after_use_and_after_error` : trois délais d'affilée, la place revient chaque fois.
- `test_b13_inference_shares_the_same_slots` : places prises → chargement avec inférence refusé en 503, aucun fils lancé, fichier non enregistré.
- `test_b13_slot_count_is_configurable` : défaut 2, 5, valeur invalide → 2, 0 → 1, 999 → 32.
- `test_b13_cloudrun_env_sum_at_worst_fits_in_2_gib` : somme de `env.yaml` ≤ 2048 Mo et égale à 1985 (à mettre à jour avec la documentation), purge active.

Suite complète : **1658 tests verts en 4 min 44** après DF-B17 (1653 après DF-B13, dont 5 nouveaux ; DF-B17 en ajoute 5 ; commande du contrat, `ONTOFORGE_DATA` non défini).

### Reste

- Avec une seule place, une seule requête ou inférence du triplestore local tourne à la fois sur toute l'instance : les autres reçoivent 503 et doivent réessayer. Acceptable pour une démo à un administrateur ; à rouvrir si plusieurs comptes travaillent en même temps (le calcul permet de passer le triplestore à 2 places en baissant un autre plafond, ou en passant à une instance de 4 Gio).
- (Traité en it1, D-L53-02, voir « Itération 1 ».) Sur Cloud Run, le système de fichiers de l'instance est en mémoire (confirmé par la documentation Cloud Run) : le triplestore local vit dans `/tmp/ontoforge-triplestore` et ses fichiers comptent dans les 2 Gio en plus du calcul ci-dessus (2,5 Mo pour 4 700 triplets ; le plafond de 1 000 000 triplets par projet peut en faire beaucoup plus, et il n'y a pas de purge des projets inactifs). À suivre par deploy : plafond d'espace total ou purge.
- Une validation SHACL sur de très gros fichiers (plus que les 42 000 triplets mesurés) peut dépasser 320 Mo : elle est alors interrompue avec le message « mémoire ou temps de calcul plafonnés », sans arrêter l'instance.
- Le front doit déjà gérer le 503 de SHACL ; à vérifier par devfront qu'il affiche aussi le message du 503 des requêtes locales et du chargement (le corps est `{"detail": ...}` avec `Retry-After`).
- Constaté pendant ce lot : l'analyseur SPARQL de rdflib n'est pas réentrant. Consigné sous DF-B17 et corrigé ci-dessous ; le test de concurrence de DF-B13 ne décale plus les départs.

## CI : installation sans contraintes {#ci}

### Problème

`.github/workflows/ci.yml` : le job `backend` installait avec `-c backend/constraints.txt`, mais deux autres installations ne le faisaient pas : l'étape « Audit de développement (informatif) » du job `audit-dependances` (ligne 65) et l'étape « Installer le backend » du job `recettes` (ligne 109). Elles résolvaient des versions libres, différentes de celles des images et des tests : l'audit de développement et les recettes pouvaient porter sur autre chose que ce qui est livré.

### Correction

Les deux lignes deviennent `pip install -c backend/constraints.txt -e "backend[dev]"`. Aucun autre changement du workflow.

### Résultat

Vérification de la résolution dans un environnement jetable, hors dépôt (`/home/claude/tmp-l53/venv-dry`, Python 3.12 comme la CI, `/home/claude/venv` intouché) : `pip install --dry-run -c backend/constraints.txt -e "backend[dev]"` réussit et résout l'ensemble (`Would install … fastapi-0.133.0 … pydantic-2.10.3 … pyoxigraph-0.5.13 … rdflib-7.1.1 …`), sans conflit entre les contraintes et l'extra `dev`. Le job `recettes` ne tourne qu'à la demande : non exécuté ici. Documentation : chapitre 17 du manuel (fr, en).

### Reste

Rien sur ce point. Les jobs ne sont pas exécutés ici (pas de GitHub Actions) : première exécution à regarder au prochain push.

## DF-B17 : analyseur SPARQL de rdflib non réentrant {#df-b17}

### Problème

L'analyseur de `rdflib.plugins.sparql.parser` est construit avec pyparsing ; ses éléments de grammaire sont des objets partagés par tout le processus et modifiés pendant l'analyse. Le serveur traite chaque requête HTTP dans un fil : deux analyses simultanées se gênent. Conséquences, sur des requêtes valides :
- `query_form` (appelé par `guard` pour toute requête locale et par `run_select`) lève une erreur interne, rendue en 422 « SPARQL invalide : Param.postParse2() missing 1 required positional argument… » ;
- `localstore/runner.py::_has_service` (second filet sur `SERVICE`, après le contrôle lexical) et `dataset_clause` (lecture des `FROM`) avalent toute erreur d'analyse (rendent `False` et `None`) : sous charge, le second filet et la lecture des `FROM` sont sautés en silence ; le contrôle lexical de `SERVICE` reste actif, donc la protection ne tombe pas, mais elle perd sa redondance ;
- `queries/translate.py` (`prepareQuery`) et `queries/builder.py` (`guided_from_sparql`) rendent des notes d'erreur ou une requête guidée refusée au hasard.

Gravité majeure (résultat faux sans alerte, pas de fuite de données). Reproduction (avant correction, tous les essais échouaient) :
- 8 fils appellent chacun 40 fois `query_form` avec quatre requêtes valides, départ simultané : **320 erreurs sur 320 appels** (« <lambda>() missing 1 required positional argument: 'x' », « … 'tokenList' ») ;
- `prepareQuery` dans les mêmes conditions : erreurs aussi ;
- 5 `POST /query/run` simultanés (non échelonnés) sur 5 projets, 6 tours : 422 « SPARQL invalide » au hasard.

### Correction

- Nouveau module `backend/ontoforge/queries/sparql_lock.py` : un `RLock` unique pour le processus et quatre fonctions (`parse_query`, `parse_update`, `prepare_query`, `translate_parsed`) qui tiennent le verrou le temps d'une analyse (quelques millisecondes, jamais pendant l'exécution d'une requête ni un appel réseau).
- Appels directs remplacés (recherche par `grep` de `parseQuery`, `parseUpdate`, `prepareQuery`, `translateQuery`, `rdflib.plugins.sparql`, `.query(` dans `backend/ontoforge`) : `queries/endpoint.py::query_form`, `localstore/runner.py::_has_service` et `dataset_clause`, `queries/translate.py::translate`, `queries/builder.py::guided_from_sparql`. Les autres appels de `.query(` visent Oxigraph (`businessmap/counts.py`, `localstore/_worker.py`), qui n'utilise pas pyparsing ; l'assistant et le requêtage guidé passent par `translate` et `query_form`, donc par le verrou. Les scripts des processus fils ont leur propre processus : sans objet.
- Test de garde `test_b17_no_sparql_parser_call_outside_the_lock` : aucun appel direct au parseur hors de `sparql_lock.py`. Il EXCLUT les quatre scripts de processus fils (par leur nom) : ils ont leur propre processus. Version it1 : voir « Itération 1 », point 5.
- Le test de concurrence de DF-B13 ne décale plus ses départs (barrière sur cinq fils).
- Manuel : chapitres 09 et 10 (fr, en) ; CHANGELOG fr / en.

### Résultat

| Mesure | Avant | Après |
|---|---|---|
| 8 fils × 40 `query_form` valides, départ simultané | 320 erreurs sur 320 | 0 erreur |
| `prepare_query` dans les mêmes conditions | erreurs | 0 erreur |
| 5 `POST /query/run` simultanés sur 5 projets, 6 tours | 422 « SPARQL invalide » au hasard | trente 200 |
| `_has_service` et `dataset_clause` sous 8 fils | réponses possibles `False` / `None` à tort | réponses identiques à un appel isolé |

Coût du verrou (`query_form` sur une requête simple avec OPTIONAL, FILTER et ORDER BY, 100 appels par fil, 24/11) :

| | Sans verrou (code d'avant) | Avec verrou |
|---|---|---|
| 1 fil : médiane par appel | 5,2 ms | 4,8 ms |
| 5 fils simultanés : médiane par appel | 19,8 ms | 23,6 ms |
| 5 fils simultanés : durée totale pour 500 appels | 2,8 s | 2,6 s |

L'analyse est un calcul Python : elle ne tourne de toute façon pas en parallèle (verrou global de l'interpréteur). Le verrou ne change donc pas le débit total (2,6 s contre 2,8 s) ; la latence d'un appel parmi cinq simultanés vaut environ cinq analyses, soit une vingtaine de millisecondes, négligeable devant l'exécution de la requête (délai de 20 s) et les fils de requête.

Tests : `backend/tests/test_l53_b17.py` (5 tests). Avec la correction mais `LOCK` remplacé par un verrou vide, `test_b17_query_form_is_safe_under_concurrency` et `test_b17_prepare_query_is_safe_under_concurrency` échouent à chaque essai ; le test d'API est probabilistique (il a échoué sur le code d'origine, pas à chaque essai avec un verrou vide).

### Reste

- Sur le code d'origine, 4 tests sur 5 échouaient (`query_form`, `prepare_query` et le test d'API par les erreurs d'analyse, le test de garde par les appels directs). Le test de `_has_service` / `dataset_clause` passait : ces fonctions avalent l'erreur et le départ simultané ne la déclenche pas à chaque essai ; il reste comme garde-fou, pas comme preuve de reproduction.
- Les modules qui recevraient un nouvel appel au parseur doivent passer par `sparql_lock` : le test de garde le vérifie sur tout `backend/ontoforge`.
- `translateGroupGraphPattern` et `traverse` (algèbre de rdflib, dans `queries/translate.py`) travaillent sur un résultat déjà analysé et n'appellent pas pyparsing : laissés hors verrou. À revoir si rdflib change.

## Itération 1 (relectures deploy, devback, devfront ; décision D-L53-02) {#it1}

Réponse point par point : `journal/L53/fix-b13-it1.md`. Résumé :

- **Le déploiement de L53 doit appliquer `env.yaml`.** Avant it1, `deploy-demo.ps1` et `cloudbuild-trigger.yaml` ne faisaient que `services update --image` : les nouvelles variables (places, plafonds, purge) n'auraient jamais été appliquées et le défaut aurait été annoncé corrigé sans l'être (7131 Mo au pire avec les anciennes valeurs). Les deux fichiers appliquent maintenant `--env-vars-file deploy/cloudrun/env.yaml`, `--memory 2Gi`, `--max-instances 1` et `--set-secrets` (mêmes noms que l'étape 5 du README). Jerem lance ensuite la commande de contrôle `gcloud run services describe` du README §7. La documentation de `--env-vars-file` n'a pas pu être consultée (accès refusé) : on ne sait pas s'il retire les variables issues de Secret Manager, d'où les secrets redonnés. Aucune commande gcloud n'a été lancée ici.
- **Mémoire du serveur (B2).** Un chargement analyse et écrit dans le serveur (mesuré : +101 Mo pour 50 000 triplets, +164 Mo pour 100 000, +249 Mo pour 200 000 ; le déploiement avait mesuré environ 1 Go pour 990 000). Places de chargement (`ONTOFORGE_LOCAL_STORE_LOAD_SLOTS`, 1 sur Cloud Run, 503 + `Retry-After`) et plafond de 50 000 triplets / 5 Mo sur Cloud Run, comptés dans la somme.
- **Disque en mémoire (D-L53-02, « Les deux »).** Plafond total `ONTOFORGE_LOCAL_STORE_TOTAL_MB` (64) avec refus 413, et purge des bases inactives `ONTOFORGE_LOCAL_STORE_IDLE_MIN` (30), comptés dans la somme ; le serveur est une valeur mesurée (121 à 146 Mo au repos, 175 retenus), plus une constante sans justification.
- Test de concurrence de DF-B13 durci, test de garde de DF-B17 étendu, panneau du triplestore qui relit l'état du serveur après un échec.

(It1, remplacé par l'[itération 2](#it2) : 1933 Mo, marge 115 Mo.) Sommes au pire de `env.yaml` : 1985 Mo = 175 + 320 + 256 + 342 + 704 + 124 + 64, marge de 63 Mo. Plus de marge demanderait de baisser le plafond d'espace d'adressage des fils du triplestore (704, plancher mesuré 640) ou de passer à une instance de 4 Gio.

### Reste (it1)

- Les 63 Mo de marge sont minces : le serveur au repos (121 à 146 Mo) peut grossir avec le nombre de projets ouverts ; si le serveur dépasse 175 Mo en usage réel, la somme dépasse 2048 Mo. À mesurer sur l'instance réelle (`gcloud run services describe` ne donne pas la mémoire utilisée ; tableau de bord Cloud Run).
- La purge n'a pas de tâche de fond : une base inactive reste tant que personne n'utilise le triplestore ; le plafond total, lui, est déterministe.
- `--set-secrets` dans le déclencheur Cloud Build : le compte de construction n'a pas de rôle sur Secret Manager ; À VÉRIFIER au premier essai (README §8). Repli indiqué.
- pySHACL en processus (`editing/files.py`) : hors du test de garde de DF-B17, vérifié par un test à part (zéro appel au parseur).

Suite complète it1 : 1666 passés (backend) ; frontend npm test 22 passés, npm run build réussi.

## Itération 2 (relectures deploy et devback, it2) {#it2}

Réponse point par point : `journal/L53/fix-b13-it2.md`.

- **Somme au pire : 1933 Mo, marge de 115 Mo** (it1 : 1985 Mo, 63 Mo) = 175 serveur + 320 SHACL + 256 OWL RL + 342 HermiT + 640 fils du triplestore (avant : 704) + 124 chargement + 64 disque + 12 corps de requête (nouveau). `ONTOFORGE_LOCAL_STORE_MEMORY_MB` passe à 640 (mesure du déploiement : 10 essais sur 10 à 608 et 640 Mo pour une base de 50 000 triplets, 8 sur 10 à 512). `ONTOFORGE_MAX_BODY_MB` passe de 32 (défaut) à **12**, et non 8 : vérification faite, 8 Mo casserait deux envois permis, les documents de l'assistant (`ONTOFORGE_DOC_MAX_MB`, 10 Mo) et les imports de schémas (10 Mo cumulés par requête, `importers/limits.py`) ; les autres envois (ontologies 4 × 2 Mo = 8 Mo dans `api/files.py`, triplestore 5 Mo, assistant 2 Mo) tiennent dans 8. Les envois simultanés au-delà du premier sont pris sur la marge (environ 9 corps de 12 Mo).
- **B3 (README §8).** Le repli qui donnait `roles/secretmanager.secretAccessor` au compte de construction est retiré (il contredisait §8.2). Remplacé par la vérification des rôles existants (`run.developer`, `iam.serviceAccountUser` sur `ontoforge-run` ; `secretAccessor` pour `ontoforge-run` seulement) ; garde-fou écrit : jamais d'accès aux secrets pour le compte de construction, ni `run.admin`. Repli conservé : retirer `--set-secrets` du déclencheur seulement, puis contrôler avec le §7. À VÉRIFIER maintenu : `run.developer` suffit-il à poser des références de secrets (la documentation cite `run.admin`) ?
- **Test pySHACL de DF-B17 (devback B1).** Il ne pouvait pas échouer : `processor.py` a importé `parseQuery` par nom. Le compteur remplace maintenant les points d'entrée de la grammaire (`parser.Query.parseString`, `parser.UpdateUnit.parseString`), que toutes les copies partagent, et un témoin positif (`test_b17_counter_sees_graph_query_calls` : un `Graph().query` doit compter au moins un appel) garantit qu'il peut échouer. Chapitre 09 fr/en et `fix-b13-it1.md` corrigés (le garde-fou n'était pas celui qui était annoncé).
- **Purge (devback 1).** `purge_idle` relit l'horloge une seconde fois sous `try_write` ; `stats` refait `exists` sous le verrou de lecture. Test `test_b13_purge_rereads_the_clock_under_the_lock`.
- **Budget disque (devback 2).** `materialize` compte les triplets inférés (moins ceux déjà présents) avec `check_disk_budget` AVANT de remplacer le graphe inféré : 413 tout ou rien, ancien graphe gardé, chargement restauré, aussi pour `refresh`. Test `test_b13_inferred_graph_counts_in_the_disk_cap_all_or_nothing`.
- **Test de concurrence (devback 3).** Il vérifie l'état final : chaque base est purgée avec son avis ou intacte avec son dernier fichier, aucun dossier sans `meta.json`.
- **Disponibilité (devback 4).** Non modifié, limite consignée (docs/dev 10) : la place de chargement est tenue pendant l'attente du verrou du projet, parce que le fichier analysé occupe la mémoire du serveur pendant ce temps ; la relâcher avant le verrou romprait la borne de 124 Mo. Contrôle non atomique entre projets (devback 5) : consigné, couvert par la marge de 1,25 et par les places uniques.

### Reste (it2)

- Les 115 Mo de marge restent à confirmer sur l'instance réelle (tableau de bord Cloud Run) : la somme est un pire cas, le serveur au repos mesuré (121 à 146 Mo) est plus bas que les 175 retenus.
- Le déploiement de L53 doit être fait par `deploy-demo.ps1` (ou l'étape 5), puis contrôlé avec la commande du README §7 : Jerem, aucune commande gcloud lancée ici.

Suite complète it2 : 1669 passés (backend) ; front non modifié.
