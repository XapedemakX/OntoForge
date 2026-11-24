# 10. Triplestore local (pyoxigraph) {#triplestore-local}

Chaque projet peut avoir un triplestore embarqué, sans serveur externe. On y charge l'ontologie, les individus et des fichiers de données. On l'interroge en SPARQL depuis le requêtage guidé (chapitre [09](09-requetes.md)), on y matérialise une inférence RDFS ou OWL RL et on valide son contenu contre les shapes.

Sources lues : `backend/ontoforge/localstore/store.py`, `backend/ontoforge/localstore/runner.py`, `backend/ontoforge/localstore/_worker.py`, `backend/ontoforge/localstore/_infer_worker.py`, `backend/ontoforge/api/local_store.py`, `backend/ontoforge/api/queries.py`, `docs/CONTRACTS.md` §6.1, tests `backend/tests/test_local_store.py`, `backend/tests/test_local_store_review.py`, `backend/tests/test_local_store_union.py`.

## Fichiers {#fichiers}

| Fichier | Responsabilité |
|---|---|
| `backend/ontoforge/localstore/store.py` | contenu et persistance : graphes nommés, verrou lecteurs / écrivain par projet, synchronisation avec l'ontologie (`ensure`), chargement (`load_data`), inférence (`materialize`), union (`rebuild_union`), statistiques, plafonds (`limits`) |
| `backend/ontoforge/localstore/runner.py` | `run_local` : exécution d'une requête dans un processus fils ; `guard` (lecture seule, refus de `SERVICE`) ; `dataset_clause` (`FROM`, `FROM NAMED`) |
| `backend/ontoforge/localstore/_worker.py` | processus fils des requêtes : ouvre la base en **lecture seule** (`Store.read_only`), n'importe que pyoxigraph |
| `backend/ontoforge/localstore/_infer_worker.py` | processus fils de l'inférence : owlrl sur un N-Triples reçu sur stdin, renvoie les seuls faits nouveaux et utiles (`useful`) |
| `backend/ontoforge/api/local_store.py` | routes `/api/projects/{pid}/store` : `GET /stats`, `POST /load`, `DELETE`, `POST /validate` |

## Disposition {#disposition}

Sur disque : `$ONTOFORGE_DATA/projects/<id>/triplestore/{db/, meta.json}` (base RocksDB d'Oxigraph et métadonnées). Avec `ONTOFORGE_LOCAL_STORE_DIR`, le triplestore vit dans `<dossier>/<id>` (disque local de l'instance) : sur Cloud Run, `/data` est un montage Cloud Storage sur lequel RocksDB (verrous, `mmap`, renommages) ne doit pas vivre. Ce dossier est éphémère et reconstruit à la demande.

| Graphe nommé | Contenu |
|---|---|
| `urn:ontoforge:graph:ontology` | TBox de l'ontologie du projet (sans individus), régénérée à chaque synchronisation |
| `urn:ontoforge:graph:individuals` | individus de l'éditeur, avec leurs nœuds anonymes liés |
| `urn:ontoforge:graph:data:<nom>` | un fichier de données importé (nom normalisé par `slug`) ; tous les graphes du fichier y sont aplatis |
| `urn:ontoforge:graph:inferred` | triplets matérialisés par owlrl, jetables |
| graphe par défaut | **union dédupliquée** des graphes nommés, reconstruite à chaque écriture (`rebuild_union`, D-L19-01) |

D-L19-01 : Oxigraph 0.5.13 sert `use_default_graph_as_union` et plusieurs `FROM` en multi-ensemble (un triplet présent dans deux graphes compte deux fois), contrairement à SPARQL 1.1 §13. Le magasin matérialise donc l'union comme un ensemble, et le fils fusionne lui-même plusieurs `FROM` (`dataset_clause`).

## Flux d'une requête {#flux-requete}

```mermaid
sequenceDiagram
  participant A as api/queries.py (endpoint kind=local)
  participant R as runner.run_local
  participant S as store
  participant W as _worker.py (fils)
  A->>R: sparql, limit, timeout_s
  R->>R: guard : query_form (UPDATE → 403, syntaxe → 422) ; SERVICE → 403
  R->>R: force_limit (limit + 1)
  R->>S: ensure(pid, p) : crée ou resynchronise si l'empreinte de l'ontologie a changé
  R->>S: lock(pid).read()
  R->>W: childproc.run_limited (mémoire, CPU, aucune écriture de fichier, environnement minimal)
  W->>W: Store.read_only(path) ; query ; cellules tronquées
  W-->>R: JSON {form, columns, rows, truncated} ou {error}
  R-->>A: QueryResult (même forme qu'un endpoint distant)
```

- Synchronisation paresseuse : `ensure` compare une empreinte SHA-1 de l'ontologie (`signature`) à celle de `meta.json` ; si elle a changé, il réécrit les graphes ontologie et individus, et marque l'inférence `stale`.
- Verrou : `_RWLock` par projet (`lock(pid)`), plusieurs lecteurs ou un seul écrivain. La suppression d'un projet (`drop`) attend les requêtes en cours.
- Ouverture courte : `_with_store` ouvre la base, appelle la fonction, refait l'union après une écriture, puis supprime la seule référence et appelle `gc.collect()` : Oxigraph ne referme RocksDB qu'à la destruction de l'objet. Le traceback d'une exception est effacé pour la même raison (il garderait la base ouverte).
- Processus fils : délai tenu pour de vrai (le fils est tué), plafonds posés par `backend/ontoforge/childproc.py::run_limited` (chapitre [06](06-shacl.md#flux-validation)). Nombre de fils borné depuis L53 (DF-B13) : `store.py::child_slot` (un `BoundedSemaphore` pris sans attendre, `ONTOFORGE_LOCAL_STORE_SLOTS`, 2 par défaut, entre 1 et 32, lu à l'import) entoure chaque lancement de fils, **requêtes et inférence ensemble, tous projets confondus**. Plein : `StoreBusy` (sous-classe de `StoreError`, 503, `retry_after = 5`), rendu en `Retry-After: 5` par `api/queries.py::_ep_error` et `api/local_store.py::_err` ; une inférence refusée annule le chargement (tout ou rien, le graphe précédent est rétabli). La place est prise juste avant le lancement et rendue après (même sur délai ou erreur), jamais pendant l'attente du verrou du projet.

## Chargement et inférence {#chargement}

`backend/ontoforge/localstore/store.py::load_data` : taille du fichier plafonnée, lecture **en flux** dans un magasin mémoire temporaire (`parse_to_store`, arrêt dès que le plafond de triplets est dépassé), vérification du total, remplacement du graphe du fichier, inférence éventuelle ; si l'inférence échoue, l'ancien contenu du graphe est restauré (tout ou rien). Avant la lecture, `parse_to_store` applique les gardes de `backend/ontoforge/io/safe_parse.py` (depuis L52, DF-B08). `check_xml(raw, strict=True)` refuse tout `DOCTYPE` en RDF/XML, car Oxigraph 0.5.13 développerait les entités internes. Il échoue fermé : un début de document qu'expat ne sait pas lire jusqu'au premier élément, ou un encodage déclaré inconnu, est aussi refusé, parce qu'Oxigraph est plus tolérant qu'expat et poursuivrait. L'import d'ontologie (`parse_into`) garde le mode non strict, rdflib étant aussi strict qu'expat. `check_jsonld` refuse un contexte JSON-LD distant et une imbrication de plus de 200 niveaux. Un refus donne un 422 et rien n'est écrit. Le lecteur d'Oxigraph refuse aussi lui-même un contexte distant restant (message traduit par `_parse_error`).

`materialize` calcule la fermeture owlrl (sémantiques `rdfs`, `owlrl`, `both`) de l'ontologie, des individus et des données, dans le processus fils `_infer_worker.py`, lancé par `backend/ontoforge/childproc.py::run_limited` comme les requêtes (environnement réduit, mémoire `ONTOFORGE_LOCAL_STORE_MEMORY_MB`, CPU = délai + 2 s ; depuis L52, DF-B07), puis remplace le graphe inféré. Délai dépassé : 504 ; plafond mémoire ou CPU atteint (fils tué par un signal ou `MemoryError`) : 413 « mémoire ou temps de calcul plafonnés ». Le fils ne renvoie que les faits utiles sur les individus (types de classes du domaine, valeurs de propriétés ; ni bruit de vocabulaire ni objets anonymes, qu'Oxigraph renommerait au rechargement). Il signale sur stderr les `owl:hasKey` ignorés (prp-key trop lente dans owlrl) et les `owl:sameAs` déduits ; ces signaux deviennent des notes en français, traduites à la réponse.

`POST /store/validate` valide les individus et les données (sans la TBox ; avec le graphe inféré si `include_inferred`) contre les shapes du projet, par la même fonction `validate` que le chapitre 06.

## Plafonds {#plafonds}

| Variable | Défaut | Effet |
|---|---|---|
| `ONTOFORGE_LOCAL_STORE_MAX_TRIPLES` | 1 000 000 (Cloud Run : 50 000) | triplets dans le magasin ; au-delà, 413 |
| `ONTOFORGE_LOCAL_STORE_MAX_UPLOAD_MB` | 25 (Cloud Run : 5) | taille d'un fichier chargé ; 413 |
| `ONTOFORGE_LOCAL_STORE_MAX_INFERENCE_TRIPLES` | 30 000 | triplets sources de l'inférence (owlrl matérialise en mémoire) ; 413 |
| `ONTOFORGE_LOCAL_STORE_MAX_VALIDATION_TRIPLES` | 60 000 | triplets passés à la validation SHACL |
| `ONTOFORGE_LOCAL_STORE_TIMEOUT_S` | 20 | délai d'une requête (la requête peut demander de 1 à 120 s) ; 504 |
| `ONTOFORGE_LOCAL_STORE_INFERENCE_TIMEOUT_S` | 90 | délai de l'inférence ; 504 |
| `ONTOFORGE_LOCAL_STORE_MEMORY_MB` | 3072 (Cloud Run : 640) | plafond d'espace d'adressage de chaque fils de requête et d'inférence ; 413 si l'inférence l'atteint. Mesuré le 24/11 : ouvrir la base demande 576 Mo pour 4 700 triplets (512 Mo échouent) et 640 Mo pour 1 000 000 triplets, le plafond du magasin (32 Mo résidents) ; l'inférence à 31 000 triplets sources tient en 576 Mo (92 Mo résidents). Ce plancher laisse peu de mémoire de travail : la valeur Cloud Run de 640 Mo est le plus bas réglage qui a passé 10 essais sur 10 (requête agrégée sur une base de 50 000 triplets ; 608 Mo aussi, 512 Mo échouent 2 fois sur 10) |
| `ONTOFORGE_LOCAL_STORE_SLOTS` | 2 (Cloud Run : 1) | nombre de fils simultanés, requêtes et inférence ensemble, tous projets ; entre 1 et 32, valeur invalide → 2 ; plein : 503 avec `Retry-After: 5` |
| `ONTOFORGE_LOCAL_STORE_LOAD_SLOTS` | 4 (Cloud Run : 1) | chargements de fichiers simultanés (analyse et écriture dans le **serveur**, environ 1,7 Mo de mémoire pour 1 000 triplets) ; entre 1 et 8 ; plein : 503 avec `Retry-After: 5` (`load_slot`, prise par la route avant la lecture du fichier) |
| `ONTOFORGE_LOCAL_STORE_TOTAL_MB` | 0 = sans plafond (Cloud Run : 64) | plafond de la taille totale du dossier `ONTOFORGE_LOCAL_STORE_DIR` (disque en mémoire sur Cloud Run) ; un chargement dont `(taille du dossier + 500 octets × triplets) × 1,25` le dépasserait est refusé : 413 « Espace du triplestore local plein ». Sans effet quand le triplestore vit dans le dossier du projet |
| `ONTOFORGE_LOCAL_STORE_IDLE_MIN` | 0 = jamais (Cloud Run : 30) | minutes d'inactivité au bout desquelles la base d'un projet est supprimée (`purge_idle`). **Les fichiers de données chargés sont perdus** ; l'ontologie et les individus reviennent à la demande. `stats` renvoie alors `purged` (fichiers perdus, message traduit) jusqu'au rechargement d'un fichier |
| `ONTOFORGE_LOCAL_STORE_DIR` | — | dossier local (éphémère) à la place de `<projet>/triplestore` |

`limits()` relit ces variables à chaque appel (minimum 1, valeur invalide → défaut ; 0 permis pour `TOTAL_MB` et `IDLE_MIN`). `LOAD_SLOTS` et `SLOTS` sont lues à l'import.

Disque éphémère (D-L53-02) : `purge_idle` s'exécute au début de `ensure` et de `load_data` (donc avant toute requête locale), sans tâche de fond. Pour chaque base ancienne, elle prend `lock(pid).try_write()` : si une requête, un chargement ou une inférence tient le verrou, la base est laissée et sera purgée plus tard. L'horloge d'usage (`touch`) est mise à jour par `ensure` ; `stats` ne la met pas à jour (une page ouverte ne maintient pas une base en vie). `clear`, `drop` et `purge` oublient aussi l'avis de purge. L'horloge est relue une seconde fois une fois le verrou obtenu : un usage qui commence entre la lecture et le verrou sauve la base ; `stats` refait `exists` sous le verrou de lecture. Le graphe inféré entre dans le plafond : `materialize` contrôle `check_disk_budget` (triplets inférés moins ceux déjà présents) AVANT de remplacer le graphe inféré, refus 413 tout ou rien (l'ancien graphe est gardé ; un chargement qui demandait l'inférence restaure son fichier). Le contrôle n'est pas atomique entre projets (deux calculs de taille peuvent se croiser) : sur Cloud Run, une seule place de chargement et une seule d'inférence les mettent en série, le reste tient dans la marge de 1,25. Limite connue : la place de chargement est tenue pendant l'attente du verrou du projet (le fichier analysé occupe la mémoire du serveur pendant ce temps), donc une requête longue sur un projet fait répondre 503 aux autres chargements ; acceptable pour une démo à un compte. Le test `test_b13_purge_and_loads_run_concurrently_without_error` fait tourner chargements, lectures et purges ensemble et vérifie l'état final des bases.

## Librairies {#librairies}

| Librairie | Version | Pourquoi |
|---|---|---|
| pyoxigraph | 0.5.13 | moteur SPARQL 1.1 Query embarqué (Oxigraph, RocksDB) ; évaluation dans `docs/veille/triplestore-embarque.md` |
| owlrl | 7.1.2 | inférence RDFS / OWL RL dans le fils |
| rdflib | 7.1.1 | export de l'ontologie, analyse SPARQL des garde-fous, graphe passé à la validation (`to_rdflib`) |

## Décisions {#decisions}

- D-L19-01 : graphe par défaut = union dédupliquée matérialisée ; plusieurs `FROM` fusionnés en ensemble.
- L41 (L39-02, L39-03) : requêtes dans un processus fils plafonné.

## Pièges et limites {#pieges}

- Pas d'écriture SPARQL : le triplestore se remplit par `POST /store/load`, jamais par `INSERT`.
- Union recalculée à chaque écriture : coût proportionnel au contenu ; c'est le prix d'un graphe par défaut correct.
- Inférence en mémoire : 30 000 triplets sources au plus ; pour plus, un endpoint avec raisonnement.
- `owl:hasKey` n'est pas appliquée par l'inférence locale (note dans la réponse).
- Un littéral ou une IRI de plus de 16 Mio fait lever `MemoryError` au lecteur d'Oxigraph (taille maximale de son tampon), même sous le plafond d'envoi de 25 Mo : `parse_to_store` répond 413 « élément trop gros » (L52 ; avant, 500).
- Nœuds anonymes : Oxigraph les renomme à chaque chargement ; ne pas compter sur leurs étiquettes.
- `guard`, `_has_service` et `dataset_clause` de `localstore/runner.py` analysent la requête avec rdflib dans le processus du serveur : ces appels passent par `queries/sparql_lock.py` (L53, DF-B17), parce que l'analyseur n'est pas réentrant. Avant, deux requêtes simultanées pouvaient échouer en 422, et `_has_service` (second filet sur `SERVICE`) et `dataset_clause` (lecture des `FROM`), qui avalent les erreurs d'analyse, étaient sautés en silence.

## Comment ajouter… {#comment-ajouter}

**…une sémantique d'inférence.** L'ajouter à `SEMANTICS`, la traiter dans `_infer_worker.py` (et dans son filtre `useful`), et la proposer dans la route `POST /store/load` (`inference`).

**…un format de fichier.** L'ajouter à `FORMATS` et `FORMAT_NAMES` (format pyoxigraph), et à `detect_format` si le contenu peut le révéler. Faire passer le contenu par les contrôles de `backend/ontoforge/io/safe_parse.py` s'il s'agit de XML ou de JSON-LD.
