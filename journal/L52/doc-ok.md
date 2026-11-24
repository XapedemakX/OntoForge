# L52 : doc-ok

verdict: OK (documentaliste, 24/11/2026, branche `integration/L52`)

## Ce qui a été vérifié

- `corrections-backend.md` et `corrections-front.md` : les 20 défauts (DF-B01 à B11, DF-F01 à F09) ont chacun Problème, Correction, Résultat et Reste. Ajouts : `**Reste.**` manquants (B01, B02, B04, B09, B10, B11, B12) ; le Reste de DF-B03 mettait à jour la décision sur `ONTOFORGE_OWLRL_SLOTS` (posé en it2).
- Tests cités : tous existent (`backend/tests/test_l52_corrections.py`, 26 fonctions, plus `test_front_guards.py`, `test_english.py`, `test_collab.py`, `test_local_store*.py`, `frontend/tests/api_clients.test.mjs`, `http_detail.test.mjs`, `i18n_parity.test.mjs`). Rejoués : `test_l52_corrections.py` et `test_front_guards.py` 41 verts, `node --test` 19 / 19. Les fichiers cités comme absents (`test_collab_routes`, `test_localize_en`) le sont bien.
- `docs/dev` (01, 02, 03, 04, 05, 09, 10, 15, 16, 17, 18, README) lu contre le code : `reasoner.py` (fils, places 1 à 32, notes), `hermit.py::_env_number`, `safe_parse.check_xml(strict)`, `store.py` (413, 422), `auth/middleware.py::localized`, `lib/http.ts`, `fapi.ts`, `ci.yml` (`npm test`, `playwright@1.63.0`), `env.yaml`, `rdf_export.FORMATS`, nombre de fichiers de test (77), `npm test` (19).
- CHANGELOG fr et en : les deux sections L52 (front, backend) se renvoient l'une à l'autre et à `journal/L52/corrections.md`.

## Corrections de la doc (aucun code touché)

- Ch. 02 (fr, en) : liste inexacte des clients qui n'acceptaient que la chaîne (`fapi` ne lisait pas `detail`, `aapi` et `gapi` lisaient la liste) ; renvoi vers le chapitre 01 qui ne contenait pas l'astuce du port 8000, remplacé par un lien vers `#depannage`.
- Ch. 16 (fr, en) : « les fils sont bornés par des sémaphores » et « aucun écart connu » étaient faux pour le triplestore local (pas de places, DF-B13) ; le chapitre 17 renvoyait au chapitre 16 pour « chaque plafond borne un fils, pas la somme », absent. Ajoutés.
- Ch. 09 (fr, en) : piège DF-B12 (ouvert) ajouté.
- CHANGELOG fr et en : « conséquence visible » corrigé (le serveur renvoie une chaîne, rien ne change à l'écran, relevé par la revue scout) ; nouveau message réseau signalé ; chapitres touchés par le front ajoutés ; défauts ouverts DF-B12 et DF-B13 ; liste des chapitres backend portée à 16 à 18.
- `docs/guide/architecture.md` et `.en.md` : la phrase « pas de test automatisé du front » contredisait `npm test` (19 tests, lancé par la CI). Reformulée. L'évènement `ontoforge:project` y était déjà retiré par devfront.
- Créé : `journal/L52/corrections.md` (synthèse pour Jerem).

## Points laissés

- `docs/guide/` n'a pas été relu hors `architecture` et `CHANGELOG` (hors périmètre du lot) ; les captures n'ont pas bougé.
- Rien tiré de `journal/securite/` dans les documents publics ; DF-B13 est décrit comme dans `journal/L51/defauts.md`, sans détail d'exploitation.
- Contrôles : `pytest tests/test_dev_docs.py tests/test_docs_bilingual.py tests/test_help_map.py` verts.

humaniseur : fait

Passé sur `journal/L52/corrections.md`, les deux sections L52 du CHANGELOG (fr, en) et les paragraphes L52 des chapitres 05, 10 et 17 du manuel (phrases longues coupées, gras décoratif retiré). Contrôle avant / après : blocs de code, liens, ancres, identifiants et nombres identiques. Aucune question ouverte sur le sens.
