# L51 : doc-ok (documentaliste)

Date : 23/11/2026. Branche `lot/L51`. Périmètre : `docs/dev/` (README + chapitres 01 à 18), fr et en.

## Verdict

OK. Le manuel correspond au code. Six inexactitudes (renvois, comptes, formulations) ont été corrigées dans les deux langues, trois points `À CONFIRMER` ont été levés par une vérification, sept restent ouverts et sont listés au README (§5, « Points ouverts »). Aucun fichier de code n'a été modifié.

## Méthode

- Pour chaque chapitre : au moins cinq affirmations techniques relues contre le code (`backend/ontoforge`, `frontend/src`), et tous les chiffres et versions vérifiés. Les versions viennent de `backend/pyproject.toml`, `backend/constraints.txt` et `frontend/package.json`.
- Exécutions réelles : analyse de `samples/trap/trap.ttl` pour les deux cibles (compteurs du chapitre 07), génération sur `samples/automaint/automaint.ttl` (36 `À VÉRIFIER` du chapitre 08), génération des shapes de `trap` (93 NodeShapes), collecte pytest (1607 tests, 75 fichiers `test_*.py`), aide en ligne de commande de HermiT, `java -version`, comptage des clés i18n (2201 de chaque côté), des routeurs (16) et des règles du registre (68).
- Contrôle croisé fr / en : mêmes nombres dans les deux langues (comparaison par script), tests `test_dev_docs.py` et `test_docs_bilingual.py` verts (203 passés).

## Corrections faites

| Chapitre | Correction |
|---|---|
| 01 | Renvoi « chapitre 02 §3 » (dépannage CSRF / `bad_origin`) remplacé par §4.1 ; renvoi « chapitre 15 §9 » (ajouter un écran) remplacé par §13 ; « environ 80 fichiers » de tests remplacé par 75 fichiers `test_*.py` et 1607 tests collectés |
| 04 | `À CONFIRMER` sur l'aide du DSL levé : aucune route ni code du front ne lit `DSL_HELP` ; l'éditeur a ses exemples dans `QuickInput.tsx` et `QuickPanel.tsx` et ses textes sous `ed.dsl.*` |
| 05 | `À CONFIRMER` sur le sens des options HermiT levé (`--help` du jar d'owlready2 : `-c`, `-O`, `-D`, `-I`) ; version Java précisée (21.0.12.1) |
| 07 | `À CONFIRMER` sur le script de rendu de `docs/RULES.md` levé : aucun script versionné (`rules_table` n'a pas d'appelant), aucun test ne compare le fichier au catalogue |
| 11 | Phrase « le test est lancé par le front sur clic » (action `settings_test`) : **confirmée dans `frontend/src`**. Précisée : bouton « Tester la connexion » (`ag.test`) de `frontend/src/assistant-global/ActionCards.tsx::TestCard`, qui appelle `settingsApi.testProvider` ou `testEndpoint` ; le serveur ne l'exécute pas dans la réponse du chat. Modèle par défaut d'`openai_compat` ajouté (`gpt-4o`) |
| 18 | « environ 77 fichiers » remplacé par 75 |
| README | Nouvelle section « Points ouverts » (`{#points-ouverts}`, fr et en) qui liste les points `À CONFIRMER` restants avec lien vers le chapitre ; mention dans les conventions |

## Points `À CONFIRMER` restants (README §5)

02 §4.7 (en-tête `Host` du proxy Vite avec authentification), 05 (version de Java dans une image construite), 06 (Windows), 11 (Bedrock cité par D-006, absent du code), 17 (compression nginx ; exécution réelle du déploiement ; Python 3.12 contre 3.13), 18 (Python 3.12 contre 3.13).

## Vérifié sans écart (échantillon)

- 02 : intervalle de présence 20 s et TTL 60 s ; plafonds du limiteur (900 / 20 / 120 / 10) ; cookie `__Host-ontoforge_session` ; plafond de corps 32 Mo et 50 Mo nginx ; `REPLAYABLE`, `tracksRev`, `WRITE_GET` des deux côtés ; 16 routeurs ; ordre des middlewares.
- 03 : champs de `OntoModel`, `Project`, `PGModel`, `Finding` ; `PGType` ; alias et `populate_by_name` ; `summary` ignore `info`.
- 04 : plafonds 1500 et 10000, `MAX_JSON_DEPTH` 200, formats de `FORMATS`, rollback du DSL à 1500 lignes.
- 05 : variables et valeurs par défaut de HermiT (1024 Mo, 30 s, 300 s, 2 créneaux), `killpg`, `WITH_REASONER`.
- 06 : variables SHACL (30 s, 2048 Mo, CPU = délai + 2 s, créneaux 1 à 32), `Retry-After: 5`, environnement minimal du fils.
- 08 : fichiers produits par cible, 50 entrées d'historique, versions de `standards.json`, 36 `À VÉRIFIER`.
- 09 à 14 : routes, plafonds (5000, 300 nœuds, 1 à 300 s), variables du triplestore, limites d'import, `MAX_OPS` 500, `LIMIT` 200, `MAX_RELEASES` 30, limites des documents Krakie, durée de session 8 h, `AUDIT_MAX` 1000.
- 15 à 18 : registre des écrans, 2201 clés, 18 `lazy`, `MOBILE_Q`, groupes et horaires de Dependabot, jobs de la CI, `CMD` de production (refus sans `ONTOFORGE_EGRESS_ALLOW`), `.dockerignore`, `publish.sh`.

## Humaniseur

humaniseur : fait (23/11/2026, commits `c8b7feb` pour le français et `e053bee` pour l'anglais).

Fichiers repris, fr et en (38 au total) : `docs/dev/README`, `01-vue-ensemble-demarrage`, `02-communication-front-back`, `03-modele-interne`, `04-import-export-rdf`, `05-conformite-owl-hermit`, `06-shacl`, `07-moteur-analyse`, `08-generateurs`, `09-requetes`, `10-triplestore-local`, `11-assistant-krakie`, `12-comptes-partage-admin`, `13-projets-versions`, `14-imports-schemas`, `15-front`, `16-securite`, `17-build-ci-deploiement`, `18-tests` (extensions `.md` et `.en.md`).

Ce qui a été fait :
- gras de tête de puce retiré (438 puces), gras sur les codes HTTP et les termes en code retiré ; le gras en milieu de phrase est gardé quand il porte un avertissement ;
- introductions du type « Ce chapitre explique… » raccourcies (01, 02, 03, 12, 15, 16, 17, 18, README), mention « Rédigé par devback » retirée au chapitre 02 ;
- amorces « Détails vérifiés », « Points vérifiés », « Lecture du schéma » raccourcies ;
- une vingtaine de phrases longues coupées en deux, tournures « permet de », « ce n'est pas qu'un… », « c'est ce qui permet de… » remplacées par l'énoncé direct ;
- aucun tiret long dans la prose (il n'en restait que dans des titres, des cellules de tableau et des chaînes citées, laissés tels quels).

Contrôle après coup, fichier par fichier, contre l'état avant humanisation : blocs de code (dont les schémas Mermaid), éléments entre backquotes (chemins, `chemin::symbole`), liens, ancres `{#id}` et nombres hors code sont identiques. `test_dev_docs.py` et `test_docs_bilingual.py` : 203 passés.

Questions laissées : aucune. Les longues énumérations séparées par des points-virgules (listes de fichiers, de limites, de passes) n'ont pas été coupées : c'est le contenu, pas un tic.
