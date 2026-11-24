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
- Processus fils : délai tenu pour de vrai (le fils est tué), plafonds posés par `backend/ontoforge/childproc.py::run_limited` (chapitre [06](06-shacl.md#flux-validation)).

## Chargement et inférence {#chargement}

`backend/ontoforge/localstore/store.py::load_data` : taille du fichier plafonnée, lecture **en flux** dans un magasin mémoire temporaire (`parse_to_store`, arrêt dès que le plafond de triplets est dépassé), vérification du total, remplacement du graphe du fichier, inférence éventuelle ; si l'inférence échoue, l'ancien contenu du graphe est restauré (tout ou rien). Avant la lecture, `parse_to_store` applique les gardes de `backend/ontoforge/io/safe_parse.py` (depuis L52, DF-B08). `check_xml(raw, strict=True)` refuse tout `DOCTYPE` en RDF/XML, car Oxigraph 0.5.13 développerait les entités internes. Il échoue fermé : un début de document qu'expat ne sait pas lire jusqu'au premier élément, ou un encodage déclaré inconnu, est aussi refusé, parce qu'Oxigraph est plus tolérant qu'expat et poursuivrait. L'import d'ontologie (`parse_into`) garde le mode non strict, rdflib étant aussi strict qu'expat. `check_jsonld` refuse un contexte JSON-LD distant et une imbrication de plus de 200 niveaux. Un refus donne un 422 et rien n'est écrit. Le lecteur d'Oxigraph refuse aussi lui-même un contexte distant restant (message traduit par `_parse_error`).

`materialize` calcule la fermeture owlrl (sémantiques `rdfs`, `owlrl`, `both`) de l'ontologie, des individus et des données, dans le processus fils `_infer_worker.py`, lancé par `backend/ontoforge/childproc.py::run_limited` comme les requêtes (environnement réduit, mémoire `ONTOFORGE_LOCAL_STORE_MEMORY_MB`, CPU = délai + 2 s ; depuis L52, DF-B07), puis remplace le graphe inféré. Délai dépassé : 504 ; plafond mémoire ou CPU atteint (fils tué par un signal ou `MemoryError`) : 413 « mémoire ou temps de calcul plafonnés ». Le fils ne renvoie que les faits utiles sur les individus (types de classes du domaine, valeurs de propriétés ; ni bruit de vocabulaire ni objets anonymes, qu'Oxigraph renommerait au rechargement). Il signale sur stderr les `owl:hasKey` ignorés (prp-key trop lente dans owlrl) et les `owl:sameAs` déduits ; ces signaux deviennent des notes en français, traduites à la réponse.

`POST /store/validate` valide les individus et les données (sans la TBox ; avec le graphe inféré si `include_inferred`) contre les shapes du projet, par la même fonction `validate` que le chapitre 06.

## Plafonds {#plafonds}

| Variable | Défaut | Effet |
|---|---|---|
| `ONTOFORGE_LOCAL_STORE_MAX_TRIPLES` | 1 000 000 | triplets dans le magasin ; au-delà, 413 |
| `ONTOFORGE_LOCAL_STORE_MAX_UPLOAD_MB` | 25 | taille d'un fichier chargé ; 413 |
| `ONTOFORGE_LOCAL_STORE_MAX_INFERENCE_TRIPLES` | 30 000 | triplets sources de l'inférence (owlrl matérialise en mémoire) ; 413 |
| `ONTOFORGE_LOCAL_STORE_MAX_VALIDATION_TRIPLES` | 60 000 | triplets passés à la validation SHACL |
| `ONTOFORGE_LOCAL_STORE_TIMEOUT_S` | 20 | délai d'une requête (la requête peut demander de 1 à 120 s) ; 504 |
| `ONTOFORGE_LOCAL_STORE_INFERENCE_TIMEOUT_S` | 90 | délai de l'inférence ; 504 |
| `ONTOFORGE_LOCAL_STORE_MEMORY_MB` | 3072 (Cloud Run : 1024) | plafond d'espace d'adressage de chaque fils de requête et d'inférence ; 413 si l'inférence l'atteint. Mesuré le 24/11 : 640 Mo au moins pour un fils de requête (ouverture de la base) ; 1024 Mo suffisent à l'inférence au plafond de 30 000 triplets sources (58 s). Aucune place limitée : plusieurs projets peuvent lancer des fils en même temps |
| `ONTOFORGE_LOCAL_STORE_DIR` | — | dossier local (éphémère) à la place de `<projet>/triplestore` |

`limits()` relit ces variables à chaque appel (minimum 1, valeur invalide → défaut).

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

## Comment ajouter… {#comment-ajouter}

**…une sémantique d'inférence.** L'ajouter à `SEMANTICS`, la traiter dans `_infer_worker.py` (et dans son filtre `useful`), et la proposer dans la route `POST /store/load` (`inference`).

**…un format de fichier.** L'ajouter à `FORMATS` et `FORMAT_NAMES` (format pyoxigraph), et à `detect_format` si le contenu peut le révéler. Faire passer le contenu par les contrôles de `backend/ontoforge/io/safe_parse.py` s'il s'agit de XML ou de JSON-LD.
