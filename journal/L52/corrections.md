# L52 : synthèse des corrections pour Jerem

Les 20 défauts relevés par L51 (`journal/L51/defauts.md`) sont corrigés. Chacun a un test qui échouait avant et passe après, sauf les défauts de documentation et DF-F07 (la CI). Deux défauts nouveaux restent ouverts : DF-B12 et DF-B13.

Chiffres du lot, sur la branche `integration/L52` :
- suite backend : 1607 tests avant, 1648 après (1645 pour le volet backend, 3 de plus pour les garde-fous du front lancés par pytest) ;
- tests Node du front : 4 avant, 19 après ;
- recettes `e2e_ui`, `l35_sidebar`, `l38_settings_krakie`, `mobile_l45` et `l40_partage` vertes sur le volet front ; `npm run build` vert.

Le détail de chaque défaut (problème avec reproduction, correction, résultat avec mesure avant / après, reste) se trouve dans `corrections-backend.md` (DF-B01 à B11, F03, F09) et `corrections-front.md` (DF-F01, F02, F04 à F08).

## Les 20 défauts

| Id | Gravité | Problème | Résultat | Détail |
|---|---|---|---|---|
| DF-B01 | mineure | `LABEL_LANG` déclaré deux fois, la copie de `localize` n'était lue par personne | doublon retiré ; test : une seule définition | [corrections-backend.md#df-b01](corrections-backend.md#df-b01) |
| DF-B02 | mineure | export de l'ontologie en `n3` et `trig` annoncé mais en erreur 500 | `n3` et `trig` répondent 200 ; relecture identique à l'export N-Triples (583 triplets sur automaint) | [corrections-backend.md#df-b02](corrections-backend.md#df-b02) |
| DF-B03 | majeure | OWL RL tournait dans un fil abandonné au délai, qui continuait à consommer CPU et mémoire | processus fils tué au délai : retour en 2,0 s pour un délai de 2 s, aucun fil restant ; coût de 0,25 s par contrôle | [corrections-backend.md#df-b03](corrections-backend.md#df-b03) |
| DF-B04 | mineure | une valeur non numérique des variables HermiT donnait un 500 ou empêchait de charger le module | valeur par défaut et avertissement au journal ; `POST /reason` ne répond plus 500 | [corrections-backend.md#df-b04](corrections-backend.md#df-b04) |
| DF-B05 | mineure | trois conditions toujours vraies (`or True`) laissées par des essais | conditions retirées, sorties inchangées ; un test interdit le motif dans tout `backend/ontoforge` | [corrections-backend.md#df-b05](corrections-backend.md#df-b05), [it2](corrections-backend.md#df-b05-it2) |
| DF-B06 | majeure | sur Neo4j, `?v a am:Vehicle` donnait `MATCH (v)` (tous les nœuds) quand plusieurs types partagent un label | `MATCH (v:Vehicle)` ; sur 45 requêtes comparées, 7 sorties changent, toutes en neo4j, aucune en curiosity | [corrections-backend.md#df-b06](corrections-backend.md#df-b06), [it2](corrections-backend.md#df-b06-it2) |
| DF-B07 | majeure | l'inférence du triplestore local héritait de tout l'environnement du serveur, sans plafond mémoire ni CPU | lancée par `childproc.run_limited`, environnement réduit, plafond atteint = 413 lisible (avant : 500) | [corrections-backend.md#df-b07](corrections-backend.md#df-b07) |
| DF-B08 | majeure | le chargement du triplestore local ne passait pas par `safe_parse` : entités XML internes développées | DOCTYPE refusé en 422, et la garde échoue fermée sur les en-têtes mal formés (relevé par la relecture sécurité) ; élément de plus de 16 Mio : 413 au lieu de 500 | [corrections-backend.md#df-b08](corrections-backend.md#df-b08), [it2](corrections-backend.md#df-b08-it2), [16 Mio](corrections-backend.md#element-16-mio-it2) |
| DF-B09 | mineure | docstring de `collab/routes.py` citant un test inexistant | renvoi vers `test_collab.py::test_every_route_is_classified` | [corrections-backend.md#df-b09](corrections-backend.md#df-b09) |
| DF-B10 | mineure | docstring de `main.py` citant `docs/guide/deploiement.md`, absent | renvoi vers le chapitre 17 du manuel et `deploy/cloudrun/README.md` | [corrections-backend.md#df-b10](corrections-backend.md#df-b10) |
| DF-B11 | mineure | docstring de `localize` citant `test_localize_en.py`, absent | renvoi vers `test_english.py` et `test_generation_lang.py`, qui existent et passent | [corrections-backend.md#df-b11](corrections-backend.md#df-b11) |
| DF-F01 | mineure | « Serveur injoignable » en dur, donc en français dans l'interface anglaise | message traduit partout (`ui.unreachable`) ; test : aucun message en dur (4 fichiers fautifs avant) | [corrections-front.md#df-f01](corrections-front.md#df-f01) |
| DF-F02 | majeure (dette) | sept variantes du même bloc `fetch` + lecture de `detail` | un seul point d'envoi, `lib/http.ts::request` ; deux tests le gardent (8 fichiers fautifs avant) | [corrections-front.md#df-f02](corrections-front.md#df-f02) |
| DF-F03 | mineure | refus produits par les middlewares (413, CSRF, origine, route non classée) en français seulement | traduits selon le compte ou l'interface ; `code` inchangé | [corrections-backend.md#df-f03](corrections-backend.md#df-f03) |
| DF-F04 | mineure | deux évènements `window` émis sans récepteur | évènements supprimés (le rafraîchissement passe par `bindProjectSetter`) ; un test exige un récepteur pour tout évènement `ontoforge:*` | [corrections-front.md#df-f04](corrections-front.md#df-f04) |
| DF-F05 | mineure | getter `ApiError.notReady` mort, commentaire périmé | getter supprimé ; `tsc -b` confirme l'absence d'appelant | [corrections-front.md#df-f05](corrections-front.md#df-f05) |
| DF-F06 | mineure | `ORDER` de `docs.ts` citait une page `deploiement` absente | entrée retirée ; un test vérifie que chaque page citée existe | [corrections-front.md#df-f06](corrections-front.md#df-f06) |
| DF-F07 | mineure | Playwright installé sans version dans la CI | épinglé à `playwright@1.63.0` ; pas de test (job manuel) | [corrections-front.md#df-f07](corrections-front.md#df-f07) |
| DF-F08 | mineure | rien ne gardait la parité de `fr.json` et `en.json` (2201 clés) | test de parité (clés, `{x}`, valeurs non vides), lancé par `npm test` et par la CI ; essai par mutation concluant | [corrections-front.md#df-f08](corrections-front.md#df-f08) |
| DF-F09 | mineure | README : `pip install` du backend sans `constraints.txt` | `-c constraints.txt` dans les deux README et le chapitre 01 | [corrections-backend.md#df-f09](corrections-backend.md#df-f09) |

## Défauts ouverts

Les deux sont consignés dans `journal/L51/defauts.md` avec le statut « ouvert, lot à venir » ; rien n'est corrigé dans L52.

DF-B12 (majeure). Un `FILTER EXISTS`, `FILTER NOT EXISTS` ou `MINUS` dont le sous-motif ne contient que le typage d'une variable déjà imprimée donne `WHERE [NOT] EXISTS { MATCH  }`, du Cypher invalide, sur les deux cibles, sans note `[perte]`. Pour `NOT EXISTS` et `MINUS`, la classe du sous-motif disparaît aussi. Le défaut existait avant L52 (même sortie dans l'ancien code). La revue query l'a séparé de DF-B06 : la cause est dans `exists_pattern`, et la correction juste mérite sa recette. Correction prévue : rendre le sous-motif en prédicat de label ou de discriminant, et à défaut poser une note `[perte]`. Détail : [corrections-backend.md#df-b12](corrections-backend.md#df-b12). Le manuel le signale au chapitre 09 (pièges).

DF-B13 (majeure). Chaque plafond mémoire borne un processus fils, pas leur somme. Les fils du triplestore local n'ont pas de nombre de places (seul le verrou par projet les sérialise), `ONTOFORGE_SHACL_MEMORY_MB` vaut 2048 par défaut et `ONTOFORGE_HERMIT_SLOTS` 2. Plusieurs projets en parallèle peuvent dépasser les 2 Gio de l'instance Cloud Run et l'arrêter. L52 améliore la situation : les plafonds OWL RL et triplestore local sont posés dans `deploy/cloudrun/env.yaml` (voir [corrections-backend.md#plafonds-cloud-run-it2](corrections-backend.md#plafonds-cloud-run-it2)). Le défaut n'est pas fermé pour autant. Corrections prévues : places bornées pour le triplestore local (503 avec `Retry-After`), plafond SHACL à 1024 si la mesure le permet, `ONTOFORGE_HERMIT_SLOTS` à 1 dans `env.yaml`. Le manuel le signale aux chapitres 10 et 16.

## Choix qui vous reviennent

1. Quand traiter DF-B12 et DF-B13, et dans quel ordre. Les deux sont majeurs : DF-B13 touche l'instance en ligne, DF-B12 la justesse des requêtes générées.
2. Références `$ref` en URL dans l'import JSON Schema (`importers/json_schema.py`). Le `or True` retiré en DF-B05 annulait une exclusion des URL. Le comportement actuel est conservé : l'URL est cherchée par son nom de fichier parmi les fichiers déposés, sans accès réseau, comme le décrit le chapitre 14. Exclure les URL changerait ce comportement, à trancher avec le pilote des imports.
3. Page « déploiement » dans `docs/guide/`. DF-F06 a retiré la mention plutôt que de créer la page, le déploiement étant décrit au chapitre 17 du manuel et dans le skill de déploiement. Si vous voulez une page, il faut l'ajouter au dossier puis à `ORDER`.
4. Langue des refus avant authentification (401 sans session, 413). Ils suivent le réglage global de langue, pas celui du compte, car ces filtres passent avant l'authentification. Un compte anglais sur un serveur réglé en français voit donc un 413 en français (chapitre 02). Deux options : mémoriser la langue globale quelques secondes, ce qui allège aussi la lecture des réglages à chaque refus, ou afficher côté front un texte traduit par clé.
5. CI. Deux jobs de `.github/workflows/ci.yml` (lignes 65 et 109) installent encore le backend sans `constraints.txt`, et le job `recettes` n'a pas été rejoué sur GitHub avec Playwright 1.63.0. Il faut le lancer une fois après le push pour confirmer que Chromium se télécharge à cette version.
6. Suites possibles, hors lot : proposer le type racine pour `StartAt` quand une requête a plusieurs types de départ (note « Type du nœud de départ inconnu » restée sur la cible neo4j) ; ajouter à la recette mobile un parcours « serveur coupé » et un parcours « session expirée puis reconnexion ».
