# L52 : corrections backend (DF-B01 à DF-B11, DF-F03, DF-F09)

Pilote : devback. Source des constats : `journal/L51/defauts.md`. Tests de non-régression : `backend/tests/test_l52_corrections.py` (chaque test a été lancé sur le code d'avant la correction et échouait, sauf défaut purement documentaire). Suite complète avant le lot : 1607 tests verts en 221 s ; après : **1629 tests verts en 261 s** (22 tests ajoutés). Après l'itération 2 : **1645 tests verts en 246 s**. Les 40 s de plus viennent surtout du démarrage du fils owlrl à chaque contrôle de conformité (environ 0,25 s, voir DF-B03) et du test chronométré de DF-B03.

## DF-B01 : doublon de `LABEL_LANG` {#df-b01}

**Problème.** `backend/ontoforge/localize/__init__.py:20` redéclarait `LABEL_LANG`, déjà défini dans `backend/ontoforge/core/lang.py:9`. Personne ne lisait celui de `localize` : poser `localize.LABEL_LANG` n'aurait eu aucun effet. Reproduction : `hasattr(ontoforge.localize, "LABEL_LANG")` valait `True`.

**Correction.** Déclaration retirée de `localize/__init__.py` (un commentaire renvoie à `core/lang.py`). Aucun code ne l'importait (vérifié par `grep`). Manuel : chapitre 03 (fr, en).

**Résultat.** `test_b01_label_lang_has_a_single_definition` : échouait avant, passe après. `test_english.py` reste vert.

**Reste.** Rien.

## DF-B02 : export de l'ontologie en `n3` et `trig` {#df-b02}

**Problème.** `GET /api/projects/{pid}/export/ontology?format=n3` (ou `trig`) répondait 500 : `ONTO_MEDIA` (`backend/ontoforge/api/projects.py`) annonçait ces formats, mais `FORMATS` (`backend/ontoforge/io/rdf_export.py`) ne les connaissait pas et `serialize` levait `ValueError`. Reproduction (client de test, exemple automaint) : `n3 500 Internal Server Error`, `trig 500 Internal Server Error`.

**Correction.** rdflib sait sérialiser le graphe du modèle dans les deux formats : `n3` et `trig` ajoutés à `FORMATS` (TriG : le graphe par défaut seul). Pas de 422 nécessaire. Manuel : chapitre 04 (fr, en).

**Résultat.** Après : `n3 200 text/n3`, `trig 200 application/trig`, et la relecture de chaque export est isomorphe à l'export N-Triples (583 triplets sur automaint). Tests ajoutés : `test_b02_export_n3_and_trig_are_faithful` (deux formats) et `test_b02_every_advertised_format_is_serializable` (tout format de `ONTO_MEDIA` est dans `FORMATS`, pour empêcher la même divergence plus tard). Les trois échouaient avant.

**Reste.** Rien. TriG ne porte que le graphe par défaut : le modèle n'a pas de graphes nommés.

## DF-B03 : owlrl en processus fils tuable et borné {#df-b03}

**Problème.** `backend/ontoforge/conformance/reasoner.py::reason` lançait owlrl dans un fil `daemon` et l'abandonnait au délai (30 s). Un fil Python ne se tue pas : le calcul continuait en arrière-plan (CPU et mémoire), et chaque `GET /conformance` relancé sur une grosse ontologie en ajoutait un. Reproduction (chaîne de 400 individus reliés par une propriété transitive, délai 2 s) : retour après 2,01 s avec la note de dépassement, mais `threading.active_count()` passait de 1 à 2 et restait à 2 deux secondes plus tard.

**Correction.**
- `backend/ontoforge/conformance/_owlrl_core.py` (nouveau) : calcul OWL RL (`closure`), contournement `prp-key` (`apply_prp_key`) et heuristique `unsat`, déplacés de `reasoner.py` sans changement de logique ; n'importe que rdflib et owlrl.
- `backend/ontoforge/conformance/_owlrl_worker.py` (nouveau) : script du fils, N-Triples sur stdin, JSON sur stdout ; charge `_owlrl_core.py` par son chemin (le fils tourne en `python -I`).
- `reasoner.py::reason` : lancement par `childproc.run_limited` (délai = `timeout`, CPU = délai + 2 s, mémoire `ONTOFORGE_OWLRL_MEMORY_MB` = 2048, environnement réduit, `cwd=/`, session séparée). Au délai, `subprocess.run` tue le fils. Plafond mémoire ou CPU : note « mémoire ou temps de calcul plafonnés ». Au plus `ONTOFORGE_OWLRL_SLOTS` (2) calculs simultanés ; au-delà, note « trop de raisonnements en cours » sans lancer de fils (le contrôle de conformité répond quand même, le raisonnement reste « jamais bloquant »).
- `childproc.py` : alias `TimeoutExpired` (le test SEC-21 interdit le mot `subprocess` dans `reasoner.py`).
- `localize/phrases.py` : traductions anglaises des deux nouvelles notes et de « OWL RL indisponible : », qui n'était pas traduit.
- Manuel : chapitres 05 et 16 (fr, en).

**Résultat.**
- `test_b03_owlrl_timeout_is_enforced_and_child_killed` (chronométré) : même entrée, délai 2 s, retour en moins de 4 s (mesuré : 2,0 s), aucun fil en plus, aucun fil owlrl de ce processus encore présent dans `/proc`. Avant : échec (`assert 2 == 1` sur le nombre de fils).
- `test_b03_owlrl_result_unchanged_in_child` : la classe insatisfiable est toujours trouvée ; `test_conformance_profiles.py` (prp-key) reste vert.
- `test_b03_owlrl_busy_slots_give_a_note` : places saturées → note, pas de fils.
- Coût : sur automaint, `reason` passe de 0,35 à 0,45 s (en processus) à 0,6 s environ (fils), soit 0,25 s de démarrage du fils par contrôle.

**Reste.** Rien sur ce défaut. Le réglage `ONTOFORGE_OWLRL_SLOTS` pour Cloud Run, laissé à deploy en it1, est posé en it2 (section « Plafonds Cloud Run »). Relu par secu : OK.

## DF-B04 : variables HermiT non numériques {#df-b04}

**Problème.** `backend/ontoforge/conformance/hermit.py` lisait `ONTOFORGE_HERMIT_TIMEOUT` et `ONTOFORGE_HERMIT_MAX_TIMEOUT` par `float()` sans `try` (500 à chaque `POST /reason` si la valeur n'est pas un nombre), et `ONTOFORGE_HERMIT_SLOTS` par `int()` à l'import. Reproduction : `ONTOFORGE_HERMIT_SLOTS=deux python -c "import ontoforge.conformance.hermit"` sortait en erreur (`ValueError: invalid literal for int() with base 10: 'deux'`) ; `ONTOFORGE_HERMIT_TIMEOUT=abc` → `configured_timeout()` levait `ValueError: could not convert string to float: 'abc'`.

**Correction.** Fonction `_env_number(name, default, cast)` dans `hermit.py` : valeur absente → défaut ; valeur non numérique, `nan` ou infinie → défaut et avertissement au journal `ontoforge.conformance.hermit` (nom de la variable, valeur reçue, défaut appliqué). Utilisée pour les quatre variables (`TIMEOUT`, `MAX_TIMEOUT`, `MAX_MB`, `SLOTS`, ce dernier avec un minimum de 1). Manuel : chapitre 05 (tableau des variables, pièges ; fr, en).

**Résultat.** Après : import réussi avec `SLOTS=deux` (2 places, avertissement « ONTOFORGE_HERMIT_SLOTS='deux' n'est pas un nombre valide : valeur par défaut 2 utilisée. ») ; `configured_timeout()` rend 30.0 avec `TIMEOUT=abc`. Tests : `test_b04_invalid_hermit_timeouts_fall_back_with_a_log`, `test_b04_invalid_hermit_slots_does_not_break_import` (import dans un processus séparé), `test_b04_reason_route_survives_invalid_timeout` (`POST /reason` ne répond jamais 500). Les trois échouaient avant.

**Reste.** Rien.

## DF-B05 : condition toujours vraie dans `translate` {#df-b05}

**Problème.** `backend/ontoforge/queries/translate.py:1621` : `if t.curiosity_ok or True:`, reste d'un essai. Le bloc s'exécutait toujours ; la condition laissait croire le contraire.

**Correction.** Condition retirée, bloc remonté d'un niveau, commentaire qui dit le comportement réel (la Query API Curiosity est toujours tentée ; une traduction incomplète est marquée « partielle »). Aucun changement de comportement.

**Résultat.** `test_b05_no_always_true_condition_in_translate` (le source de `translate` ne contient plus `or True`) ; `test_translate.py`, `test_query_builder.py`, `test_query_options.py` verts, sorties inchangées.

**Reste.** Deux autres `... or True` relevés en passant, hors liste L51 et non corrigés ici : `backend/ontoforge/importers/json_schema.py:205` et `backend/ontoforge/importers/csv_import.py:90`. À traiter dans un lot importeurs.

## DF-B06 : label perdu quand plusieurs types de nœuds partagent un label {#df-b06}

**Problème.** `backend/ontoforge/queries/translate.py::_Translator.node_pat` ne posait aucun label quand une classe était portée par plusieurs types de nœuds partageant **un seul** label : ni la branche `len(nts) == 1` ni `elif len(labels) > 1` ne s'appliquait. Reproduction (automaint, cible neo4j, sans décision, `POST /queries/translate`) : `SELECT ?v WHERE { ?v a am:Vehicle }` → `MATCH (v)` puis `RETURN v.uri AS v`, sans note `[perte]`. `am:Vehicle` y est porté par `Vehicle`, `ElectricVehicle` et `CombustionVehicle`, tous de label `Vehicle` (le générateur `targets/neo4j.py` pose bien tous les labels sur chaque nœud, voir `Mapper.merge_label` et la ligne des labels supplémentaires). Résultat : un sur-ensemble (tous les nœuds du graphe), contraire à la règle de prudence du traducteur.

**Correction.** Dans `node_pat`, branche plusieurs types : le motif est l'union des références possibles, chacune valant « label » ou « label ET discriminant ». Une référence sans discriminant absorbe celles de même label qui en ont un. Un seul label restant → `(v:Label)` ; plusieurs termes → condition `WHERE (v:A OR v:B OR (v:C AND v.kind = 'x'))`. Garde-fou : si un type possible n'a pas de label (le générateur n'en produit pas aujourd'hui), une note `[perte]` explicite le signale (sur-ensemble possible). Manuel : chapitre 09 (exemple exécuté corrigé, piège retiré ; fr, en).

**Résultat.**
- Après : `MATCH (v:Vehicle)` ; l'exemple du chapitre 09 (`STRSTARTS(?vin, "VF")`) donne `MATCH (v:Vehicle) WHERE v.vin STARTS WITH 'VF'`.
- Comparaison avant / après sur 45 requêtes (les 10 requêtes de `tests/fixtures/queries`, les questions de compétence d'automaint et 3 requêtes ajoutées, cibles neo4j et curiosity) : 7 sorties changent, toutes sur la cible neo4j et toutes de la même façon (`(v)` → `(v:Vehicle)`, `(b)` → `(b:Vehicle)`, etc.) ; aucune sortie Curiosity ne change.
- Tests : `test_b06_shared_label_is_kept_on_neo4j` (API, trois requêtes dont un sous-type et une relation ; échouait avant) et `test_b06_union_of_labels_and_discriminators` (labels multiples, absorption d'un discriminant, discriminant conservé).

**Reste (pour query).**
- Pour la cible neo4j, le pseudo-code Curiosity de la même requête reste absent avec la note « Type du nœud de départ inconnu » : trois types de départ possibles, `StartAt` n'en prend qu'un. Comportement honnête, inchangé.
- Défaut distinct relevé pendant la comparaison, non corrigé : `?v a am:Vehicle . FILTER EXISTS { ?v a am:Vehicle }` donne `WHERE EXISTS { MATCH  }` (motif vide, Cypher invalide), avant comme après : `exists_pattern` ne rend rien quand le sous-motif ne contient qu'un typage d'une variable déjà imprimée. Consigné en it2 comme **DF-B12** (voir ci-dessous).

## DF-B07 : inférence du triplestore local par `childproc.run_limited` {#df-b07}

**Problème.** `backend/ontoforge/localstore/store.py::materialize` lançait `_infer_worker.py` par `subprocess.run` direct : le fils héritait de **tout** l'environnement du serveur (clés d'API, clé maître, mots de passe éventuels) et n'avait ni plafond mémoire (`RLIMIT_AS`) ni plafond CPU ; seuls le délai et le plafond de triplets sources le bornaient. Incohérent avec la règle d'isolement de L41 suivie par les requêtes du même module et par SHACL. Reproduction (espion sur `subprocess.run`, chargement avec `inference=rdfs`) : commande `[python, -I, .../_infer_worker.py, rdfs]`, sans lanceur à plafonds, `env` absent (donc hérité, avec la variable témoin `ONTOFORGE_FAKE_SECRET_L52`). Autre défaut constaté : un fils tué par un signal sans rien écrire sur stderr faisait lever `IndexError` (`splitlines()[-1]` sur une liste vide), donc un 500.

**Correction.**
- `store.py::materialize` : `childproc.run_limited(worker, nt, timeout=…, mem_mb=ONTOFORGE_LOCAL_STORE_MEMORY_MB, cpu_s=délai + 2, fsize=0, args=[semantics])`, comme `runner.py`. Délai : 504 (inchangé). Fils tué par un signal ou `MemoryError` : 413 « Inférence … interrompue : mémoire ou temps de calcul plafonnés … ». Autre échec : 500 avec la dernière ligne de stderr, ou « erreur inconnue » si stderr est vide.
- `_infer_worker.py` : `MemoryError` intercepté (code 3, message court) ; `main()` sous `if __name__ == "__main__"` (le lanceur de `childproc` exécute le script sous ce nom ; le test `test_useful_filter_unit` importe le module sans lancer `main`).
- `localize/phrases.py` : traduction anglaise du nouveau message.
- Plafond mémoire : celui des requêtes (`ONTOFORGE_LOCAL_STORE_MEMORY_MB`, 3072 Mo), pas de nouvelle variable.
- Manuel : chapitres 10 et 16 (fr, en).

**Résultat.**
- `test_b07_inference_child_is_limited_and_gets_no_secret` : la commande contient le lanceur à plafonds (`RLIMIT_AS`), `env` est réduit et sans la variable témoin, `start_new_session=True`, sémantique passée en argument. Avant : échec (pas de lanceur).
- `test_b07_inference_killed_by_a_cap_gives_a_clean_413` (SIGKILL, SIGXCPU, `MemoryError`) : 413 lisible. Avant : 200 (le fils simulé n'était pas appelé) et, sur le vrai chemin, 500 par `IndexError`.
- `test_local_store*.py` (72 tests) verts : résultats d'inférence inchangés.
- Mesure du plafond sur un fils réel (une ligne N-Triples, sémantique owlrl) : 40 Mo → échec à l'import (`MemoryError`), 60 Mo et plus → succès. Le défaut de 3072 Mo laisse donc toute la marge pour le calcul.

**Reste.** À relire par secu : le réseau n'est pas coupé par le système dans le fils (comme pour SHACL et les requêtes) ; owlrl ne l'utilise pas pour ces entrées.

## DF-B08 : chargement du triplestore local passé par `io/safe_parse.py` {#df-b08}

**Problème.** `backend/ontoforge/localstore/store.py::parse_to_store` lisait les fichiers par `pyoxigraph.parse` sans les gardes de `backend/ontoforge/io/safe_parse.py` : le refus de tout `DOCTYPE` en RDF/XML ne s'appliquait pas sur ce chemin. Les entités externes n'étaient pas résolues, mais Oxigraph 0.5.13 développe les entités **internes**. Reproduction (`POST /store/load`, RDF/XML déclarant trois entités imbriquées, facteur 10 par niveau) : 200, fichier chargé avec la valeur développée. Un JSON-LD imbriqué sur 300 niveaux était aussi accepté (l'import d'ontologie le refuse au-delà de 200).

**Correction.** `parse_to_store` appelle `safe_parse.check_xml` (RDF/XML) ou `safe_parse.check_jsonld` (JSON-LD) avant Oxigraph ; un refus devient `StoreError` 422 « « fichier » : <message de safe_parse> », avant toute écriture. Pour un contexte JSON-LD distant, le message historique du triplestore (« le contexte JSON-LD distant est refusé… ») est conservé. Taille : déjà bornée par `load_data` (`ONTOFORGE_LOCAL_STORE_MAX_UPLOAD_MB`, 25 Mo) avant la lecture, et le nombre de triplets par le plafond de lecture en flux. Les quatre messages de refus de `safe_parse` reçoivent une traduction anglaise (`localize/phrases.py`), utile aussi à l'import d'ontologie, où ils n'étaient pas traduits. Manuel : chapitres 04, 10 et 16 (fr, en).

**Résultat.**
- Après : la même entrée donne 422 « « x.rdf » : Fichier RDF/XML refusé : il déclare un DOCTYPE ou des entités XML… », et le graphe du fichier n'existe pas.
- Tests : `test_b08_rdfxml_with_internal_entities_is_refused`, `test_b08_refusal_is_translated` (interface anglaise : « RDF/XML file refused »), `test_b08_deep_jsonld_is_refused_and_plain_rdfxml_still_loads` (un RDF/XML sans DOCTYPE se charge toujours). Les trois échouaient avant (200).
- `test_rdfxml_external_entity_not_resolved` et `test_jsonld_remote_context_*` restent verts, sans aucun appel réseau.

**Reste.** Le `À CONFIRMER` de L51 sur la borne de l'expansion d'Oxigraph devient sans objet sur ce chemin (aucun DOCTYPE n'arrive plus à Oxigraph) ; à relire par secu.

## DF-B09 : docstring de `collab/routes.py` {#df-b09}

**Problème.** La docstring de `backend/ontoforge/collab/routes.py` renvoyait à `tests/test_collab_routes.py`, qui n'existe pas.

**Correction.** Renvoi corrigé vers `backend/tests/test_collab.py::test_every_route_is_classified`, le test qui parcourt toutes les routes. Défaut documentaire : pas de test ajouté.

**Résultat.** Le fichier cité existe (vérifié) ; aucun autre renvoi à `test_collab_routes` dans le dépôt hors journal.

**Reste.** Rien.

## DF-B10 : docstring de `main.py` {#df-b10}

**Problème.** La docstring de `backend/ontoforge/main.py` renvoyait à `docs/guide/deploiement.md`, absent du dépôt.

**Correction.** Renvoi vers `docs/dev/17-build-ci-deploiement.md` et `deploy/cloudrun/README.md` (variables de déploiement), et `docs/dev/16-securite.md` pour les variables de sécurité citées. Défaut documentaire : pas de test ajouté.

**Résultat.** Les trois fichiers cités existent. La page `deploiement` citée par `frontend/src/lib/docs.ts` (DF-F06) relève du front.

**Reste.** Rien.

## DF-B11 : docstring de `localize/__init__.py` {#df-b11}

**Problème.** La docstring de `backend/ontoforge/localize/__init__.py` disait que `tests/test_localize_en.py` gardait la couverture de la traduction anglaise ; ce fichier n'existe pas.

**Correction.** Point `À CONFIRMER` de L51 levé : la couverture sur automaint est assurée par `backend/tests/test_english.py` (`test_analysis_texts_have_no_french_in_english` : constats et validations de l'analyse sans accent français ; `test_conformance_and_error_messages_in_english` : conformité et erreurs) et par `backend/tests/test_generation_lang.py` (fichiers générés). La docstring cite désormais ces tests. Le chapitre 18 ne cite pas `test_localize*` (il cite `test_local_store*`, qui existe) : rien à y changer. Défaut documentaire : pas de test ajouté.

**Résultat.** Les tests cités existent et passent.

**Reste.** Rien.

## DF-F03 : refus des middlewares traduits {#df-f03}

**Problème.** Les réponses écrites directement par les couches ASGI contournaient `main.py::_http_error` et `localize` : texte français seulement. Concernés : 413 de `backend/ontoforge/security.py::BodyLimit`, 403 `bad_origin` et `csrf` (et aussi 401 `auth_required`, 403 `password_change_required`) de `backend/ontoforge/auth/middleware.py`, 403 `unclassified` et 401 de `backend/ontoforge/collab/middleware.py`. Reproduction (authentification active, compte passé en anglais par `PUT /api/auth/preferences`) : `POST /api/projects` sans jeton → `{"detail": "Jeton CSRF absent ou invalide : rechargez la page.", "code": "csrf"}`.

**Correction.**
- `auth/middleware.py::localized(text, lang=None)` : même mécanisme que `_http_error` (`localize.tr` vers l'anglais) ; langue du compte si elle est connue, sinon `localize.ui_lang()` (compte de la requête, puis réglage global). Ne lève jamais.
- `AuthMiddleware` : les refus CSRF et origine utilisent la langue du compte (session déjà lue) ; 401 et mot de passe provisoire aussi traduits.
- `CollabMiddleware` : `unclassified` et 401 traduits (la langue du compte y est déjà posée par l'authentification).
- `BodyLimit` : 413 traduit, message calculé seulement au refus (pas de lecture des réglages à chaque écriture). Langue : réglage global, car ce filtre passe avant l'authentification.
- `localize/phrases.py` : sept textes anglais. Les champs `code` ne changent pas.
- Manuel : chapitre 02 (fr, en).

**Résultat.** Après : `{"detail": "Missing or invalid CSRF token: reload the page.", "code": "csrf"}`, `{"detail": "Origin refused.", "code": "bad_origin"}`, 413 « Request too large (limit 1 MB). » avec et sans `Content-Length` quand l'interface est en anglais ; texte français inchangé sinon. Tests : `test_f03_csrf_and_origin_refusals_follow_the_account_language`, `test_f03_unclassified_and_413_follow_the_interface_language` (échouaient avant) ; `test_auth.py`, `test_security.py`, `test_collab.py`, `test_l42_admin.py`, `test_english.py` verts (182 tests).

**Reste.** Le 413 ne suit pas la langue du **compte**, seulement le réglage global (ordre des filtres) : documenté au chapitre 02. À relire par secu (aucun contenu de la requête n'entre dans le message).

## DF-F09 : README, installation avec les contraintes {#df-f09}

**Problème.** La section « Développement sans Docker » de `README.md` (et `README.en.md`) installait le backend par `pip install -e ".[dev]"` sans `-c constraints.txt` : versions non épinglées, alors que la CI (job de tests) et les images installent avec `backend/constraints.txt`.

**Correction.** `pip install -c constraints.txt -e ".[dev]"` dans les deux README (la commande s'exécute depuis `backend/`, où se trouve le fichier) ; la phrase du chapitre 01 qui signalait l'écart est remplacée (fr, en). Défaut documentaire : pas de test ajouté.

**Résultat.** README, chapitre 01 et job `tests` de la CI (`pip install -c backend/constraints.txt -e "backend[dev]"`) donnent la même installation.

**Reste (pour devfront, propriétaire de la CI).** Deux autres jobs de `.github/workflows/ci.yml` (lignes 65 et 106 au 24/11) installent encore `pip install -e "backend[dev]"` sans contraintes.

## Fichiers partagés touchés

- `backend/ontoforge/localize/phrases.py` (traductions : DF-B03, B07, B08, F03), `backend/ontoforge/childproc.py` (alias `TimeoutExpired`, docstring).
- `README.md`, `README.en.md` (DF-F09), `docs/guide/CHANGELOG.md` et `.en.md` (section L52 backend), `journal/L51/defauts.md` (colonne « Statut » ajoutée ; les lignes des défauts front sont laissées vides pour devfront).
- Manuel `docs/dev` : chapitres 01, 02, 03, 04, 05, 09, 10, 16, 18 et le README du manuel (fr, en). `test_dev_docs.py` vert.

## Points à relire

- **secu** : DF-B03 (`reasoner.py`, `_owlrl_worker.py` : plafonds, places, environnement), DF-B07 (`store.py::materialize` : plafond mémoire partagé avec les requêtes, 413), DF-B08 (`store.py::parse_to_store` : gardes `check_xml` / `check_jsonld`, message historique conservé pour un contexte distant), DF-F03 (langue des refus : aucun contenu de la requête dans le message). Le réseau n'est pas coupé par le système dans les fils (inchangé, comme SHACL et les requêtes).
- **query** : DF-B06 (`translate.py::_Translator.node_pat`, union des types et absorption des discriminants) ; défaut distinct relevé, non corrigé : `FILTER EXISTS { ?v a am:Vehicle }` sur une variable déjà typée donne `EXISTS { MATCH  }`.
# Itération 2 : corrections après les relectures (secu KO, query OK, devfront OK)

Réponses point par point : `journal/L52/fix-back-it1.md`.

## DF-B08 (it2) : la garde RDF/XML du triplestore local échoue fermée {#df-b08-it2}

**Problème.** Relevé par secu (SEC-L52-01 et SEC-L52-02, détail dans le rapport non publié de `journal/securite/`). `safe_parse.check_xml` laissait passer un document dont expat ne savait pas lire le début (erreur d'analyse avalée, « rdflib produira son message »). C'est juste pour l'import d'ontologie, où rdflib est aussi strict qu'expat. Mais Oxigraph, plus tolérant, poursuivait la lecture et développait les entités internes d'un DOCTYPE qu'expat n'avait jamais vu. Reproduction : plusieurs en-têtes RDF/XML légèrement mal formés suivis d'un DOCTYPE à entités, envoyés à `POST /store/load`, donnaient 200 avant cette correction (seule l'entrée canonique donnait 422). Un encodage déclaré inconnu donnait 500 (`LookupError` non attrapée).

**Correction.** `check_xml(data, strict=False)` : en mode strict, toute erreur d'analyse avant le premier élément et tout encodage inconnu lèvent `UnsafeRdfError`. `localstore/store.py::parse_to_store` appelle `check_xml(raw, strict=True)`. `parse_into`, donc l'import d'ontologie, n'a pas changé : le mode non strict laisse passer l'erreur d'analyse, et une `LookupError` remonte comme avant. Deux nouveaux messages, traduits en anglais. Manuel : chapitre 10 (fr, en).

**Résultat.** Les huit variantes mal formées de la revue et l'entrée canonique donnent toutes 422 « Fichier RDF/XML refusé… » ; rien n'est écrit. Avant : 200 pour les variantes et 500 pour l'encodage. Tests :
- `test_b08_malformed_rdfxml_header_fails_closed` (9 cas, à 3 niveaux d'entités, pour que rien ne coûte si le test échoue) ;
- `test_b08_valid_rdfxml_still_loads_in_the_store` (`samples/automaint/automaint.owl` et un RDF/XML avec BOM et commentaire se chargent toujours) ;
- `test_b08_parse_into_is_unchanged_for_malformed_headers`.

`test_io_import_export.py`, `test_sec_*.py` et `test_local_store*.py` restent verts.

## Plafonds Cloud Run (it2) {#plafonds-cloud-run-it2}

**Problème.** Relevé par secu (non bloquant) : `deploy/cloudrun/env.yaml` ne posait ni `ONTOFORGE_OWLRL_SLOTS` ni `ONTOFORGE_OWLRL_MEMORY_MB` (valeurs par défaut : 2 places de 2048 Mo), et le plafond du triplestore local (`ONTOFORGE_LOCAL_STORE_MEMORY_MB`, 3072 Mo par défaut) dépassait à lui seul les 2 Gio du conteneur, qui tourne en instance unique.

**Correction.** `env.yaml` : `ONTOFORGE_OWLRL_SLOTS: "1"`, `ONTOFORGE_OWLRL_MEMORY_MB: "1024"`, `ONTOFORGE_LOCAL_STORE_MEMORY_MB: "1024"`. Justification de la dernière valeur, mesurée le 24/11 sur automaint :
- fils de requête (`SELECT (COUNT(*) …)` sur le triplestore local) : échec à 512 et 576 Mo (fils tué, 502), succès à 640 Mo et au-delà ; l'ouverture de la base RocksDB réserve beaucoup d'espace d'adressage ;
- fils d'inférence (sémantique `both`) : 14 600 triplets sources en 28 s, 29 600 (juste sous le plafond de 30 000) en 58 s, tous deux à 1024 Mo, sous le délai de 90 s ;
- serveur : 155 à 175 Mo de mémoire résidente maximale pendant ces mesures.

1024 Mo laisse donc environ 380 Mo de marge au-dessus du minimum d'une requête, permet l'inférence au plafond, et un fils seul ne peut plus prendre plus de la moitié du conteneur. Documentation : `deploy/cloudrun/README.md`, manuel chapitres 05, 10 et 17 (fr, en).

**Résultat.** `env.yaml` relu par `test_dev_docs.py` et les tests qui citent le déploiement (verts).

**Reste.** Chaque plafond borne un fils, pas leur somme. Le triplestore local n'a pas de places limitées (seul le verrou par projet sérialise) : plusieurs projets en parallèle peuvent encore dépasser 2 Gio. `ONTOFORGE_SHACL_MEMORY_MB` vaut 2048 par défaut et n'est pas réduit dans `env.yaml`. Les deux restent à suivre (un `BoundedSemaphore` pour le triplestore local, comme pour SHACL) ; à trancher avec deploy et secu.

## Élément de plus de 16 Mio au chargement du triplestore local (it2) {#element-16-mio-it2}

**Problème.** Relevé par secu (SEC-L52-03, défaut ancien, hors liste L51). Un littéral ou une IRI de plus de 16 Mio, sous le plafond d'envoi de 25 Mo, fait lever `MemoryError` au lecteur d'Oxigraph (taille maximale de son tampon : 16 777 216 octets). `parse_to_store` ne l'attrapait pas : 500 sur `POST /store/load`. Le processus restait intact. Reproduction : Turtle avec un littéral de 17 Mio → 500 ; N-Triples avec une IRI de 17 Mio → 500.

**Correction.** `localstore/store.py::parse_to_store` attrape `MemoryError` et répond 413 « « fichier » : un élément du fichier (littéral ou IRI) est trop gros pour le lecteur RDF (16 Mio au plus). », traduit en anglais. Rien n'est écrit (la lecture se fait dans un magasin temporaire). Manuel : chapitre 10, pièges (fr, en).

**Résultat.** Les deux entrées donnent 413 ; un chargement normal qui suit réussit. Test : `test_store_oversized_element_gives_a_clean_413` (deux cas ; échouait avant avec 500).

**Reste.** Le message attribue toute `MemoryError` du lecteur à la taille d'un élément ; c'est la seule cause observée, le plafond de triplets borne le reste.

## DF-B05 (it2) : les deux autres `or True` {#df-b05-it2}

**Problème.** Deux conditions toujours vraies relevées en it1 (section DF-B05, « Reste ») : `backend/ontoforge/importers/json_schema.py:205` (`… if not re.match(<URL>, base) or True else None`) et `backend/ontoforge/importers/csv_import.py:90` (`… and (i >= n or True)`).

**Correction.** Conditions retirées, sans changement de comportement :
- `json_schema.py` : une référence vers un autre fichier, URL comprise, est toujours cherchée par son nom parmi les fichiers déposés (jamais téléchargée). Un commentaire le dit maintenant.
- `csv_import.py` : une ligne vide est sautée, au milieu comme en fin de fichier.

Le test de DF-B05 couvre désormais tout `backend/ontoforge` : `test_b05_no_always_true_condition_anywhere_in_backend` cherche, par l'analyseur de jetons Python (commentaires exclus), un `or` suivi de `True`. Il échouait avant (les deux emplacements ci-dessus) et passe après.

**Résultat.** `test_l48_import.py` et les tests d'import (121) verts, sorties inchangées.

**Reste.** L'expression régulière de `json_schema.py` laisse penser que l'auteur voulait exclure les URL de cette recherche par nom ; le `or True` l'annulait. Le comportement actuel, conforme au manuel (chapitre 14 : « sauf si le fichier visé fait partie des fichiers déposés »), est conservé. Exclure les URL serait un changement de comportement, à trancher par le pilote des imports (L48).

## DF-B06 (it2) : tests du garde-fou et de la cible curiosity {#df-b06-it2}

**Problème.** Relevé par query (non bloquant) : la branche « type possible sans label » de `node_pat` (note `[perte]`) n'avait pas de test, et aucun test n'affirmait que la cible curiosity était inchangée.

**Correction.** Tests seuls, pas de changement de code :
- `test_b06_type_without_label_gives_an_explicit_loss` : une référence sans label et une avec label donnent `(v)`, sans condition, et une seule note `[perte]` qui nomme `?v`.
- `test_b06_curiosity_target_output_unchanged` : sur automaint, cible curiosity, `am:Vehicle` → `MATCH (v:Vehicle)` et `am:ElectricVehicle` → `MATCH (v:Vehicle) WHERE v.VehicleKind = 'ElectricVehicle'`, comme avant L52.

**Résultat.** Les deux passent. Le premier échoue sur le `translate.py` d'avant DF-B06 (aucune note n'était émise) ; le second y passe aussi, ce qui confirme que la sortie curiosity n'a pas bougé.

## DF-B12 consigné (it2) {#df-b12}

**Problème.** Défaut distinct de DF-B06, relevé par devback en it1 ; la revue query l'a tranché : lot dédié, pas L52. Portée établie par query : `FILTER EXISTS`, `FILTER NOT EXISTS` et `MINUS` dont le sous-motif ne contient qu'un typage d'une variable déjà imprimée donnent `EXISTS { MATCH  }`, du Cypher invalide, sur les deux cibles, sans note `[perte]` (`lossy = false`). Pour `NOT EXISTS` et `MINUS`, la classe du sous-motif est perdue.

**Correction.** Aucune dans L52 (décision de query). Ligne DF-B12 ajoutée à `journal/L51/defauts.md`, gravité majeure, statut « ouvert, lot à venir », avec le constat et la correction attendue (prédicat de label ou de discriminant ; à défaut, note `[perte]`).

**Résultat.** Le défaut est tracé ; la sortie actuelle n'a pas changé.

**Reste.** Tout le défaut : correction dans un lot dédié (voir `journal/L51/defauts.md`, DF-B12).

