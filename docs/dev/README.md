# Manuel du développeur d'OntoForge {#manuel-developpeur}

Ce manuel décrit comment OntoForge est codé : où vit chaque fonction, quelles librairies (en version exacte) et pourquoi, comment les pièces se parlent, quels pièges attendent le prochain développeur et comment ajouter un écran, une règle, une route ou une recette. Il s'adresse à une personne qui reprend le projet sans les agents qui l'ont écrit. Pour *utiliser* OntoForge, lire le guide utilisateur (`docs/guide/utilisateur.md`) ; pour le catalogue des règles, `docs/guide/regles.md`. English version: [README.en.md](README.en.md).

État vérifié le 23 novembre 2026 (lot L51, décision D-L51-01). Le manuel est publié sur GitHub avec le reste du dépôt et **n'est pas embarqué dans l'application**.

## 1. Sommaire {#sommaire}

| # | Chapitre | Contenu |
|---|---|---|
| 01 | [Vue d'ensemble et démarrage](01-vue-ensemble-demarrage.md) | arborescence, librairies, lancer en dev (venv, Docker), tests, recettes |
| 02 | [Communication front ↔ back](02-communication-front-back.md) | `frontend/src/api.ts`, routes FastAPI, sessions et CSRF, `If-Match` / 409 / 428, limiteur, erreurs, téléchargements, proxy |
| 03 | [Modèle interne](03-modele-interne.md) | `core/` : ontologie, projet, modèle property graph |
| 04 | [Import et export RDF](04-import-export-rdf.md) | rdflib, formats, JSON-LD, garde-fous d'entrée |
| 05 | [Conformité OWL 2, lint, HermiT](05-conformite-owl-hermit.md) | profils, lint, raisonneur en sous-processus |
| 06 | [SHACL](06-shacl.md) | génération des shapes, pySHACL borné, méta-validation |
| 07 | [Moteur d'analyse et catalogue de règles](07-moteur-analyse.md) | constats auto / à arbitrer / perdu, reclassement, oracle |
| 08 | [Générateurs](08-generateurs.md) | Curiosity (C#), Neo4j (Cypher), GraphQL, rapport, dossier de justification |
| 09 | [Requêtes](09-requetes.md) | traduction SPARQL → Cypher / C#, endpoints |
| 10 | [Triplestore local](10-triplestore-local.md) | pyoxigraph |
| 11 | [Assistant Krakie](11-assistant-krakie.md) | agent, actions proposées, fournisseurs LLM, garde-fous |
| 12 | [Comptes, partage, administration](12-comptes-partage-admin.md) | présence, journal d'activité |
| 13 | [Projets et versions](13-projets-versions.md) | stockage, annuler / rétablir, versions SemVer |
| 14 | [Imports SQL, CSV, JSON Schema](14-imports-schemas.md) | import déterministe |
| 15 | [Front : shell, état, design system, i18n, éditeurs, téléphone](15-front.md) | `frontend/src/` |
| 16 | [Sécurité transverse](16-securite.md) | netguard, CSP, durcissement, sous-processus (sans détail exploitable) |
| 17 | [Build, CI, Docker, Cloud Run, publication](17-build-ci-deploiement.md) | de la source à la production |
| 18 | [Tests](18-tests.md) | pytest, oracle, recettes Playwright, captures |

Chaque chapitre existe aussi en anglais (`NN-sujet.en.md`, mêmes ancres).

## 2. Parcours de lecture {#parcours}

| Je veux… | Lire, dans l'ordre |
|---|---|
| comprendre le projet en une heure | 01, puis le §2 du 02, puis 07 |
| **comprendre un appel du front** jusqu'au code serveur | 02 (schéma de séquence), 15 §4, puis le chapitre du sous-système appelé |
| **ajouter une règle de transposition** | 07 (catalogue, détection), 08 (effet sur le code généré), 18 §4 (oracle), `docs/RULES.md` |
| ajouter ou modifier un générateur | 03 (`PGModel`), 08, 18 |
| **ajouter une route d'API** | 02 §9, 12 (classification par projet et rôles), 03 (modèles), 18 |
| **ajouter un écran** | 15 §13, 02 §9, 18 §11 |
| ajouter une langue ou un texte | 15 §6, `skills/i18n-ecriture-sure/SKILL.md` |
| comprendre les sessions, le partage, les conflits | 12, 02 §4, 13 |
| comprendre l'assistant et ses garde-fous | 11, 16, 15 §5 |
| toucher à l'import / export | 04, 14, 03 |
| déployer ou corriger la CI | 17, 16, `deploy/cloudrun/README.md` |
| durcir ou auditer | 16, 02 §4.1 et 4.4, 17 §4 |
| écrire une recette ou un test | 18, 01 §5.3 |

## 3. Conventions du manuel {#conventions}

- Plan de chaque chapitre : rôle ; fichiers et responsabilités ; flux (schéma Mermaid) ; librairies avec version exacte et raison ; structures clés ; décisions (D-xxx) ; pièges ; « comment ajouter… ».
- Citer le code : un chemin depuis la racine du dépôt entre backquotes, par exemple `backend/ontoforge/ratelimit.py`. Un symbole se cite `chemin::symbole` (fonction, classe ou constante de module ; `chemin::Classe.méthode` pour un membre ; `chemin::objet.membre` en TypeScript). Pas de numéros de ligne (ils bougent).
- Contrôle automatique : `backend/tests/test_dev_docs.py` vérifie que chaque chemin cité existe, que chaque `chemin::symbole` existe dans le fichier, que les titres et ancres `{#id}` sont identiques en fr et en, que les liens internes sont valides, que les 18 chapitres existent et qu'aucun renvoi à un fichier du dossier des audits de sécurité ni aucun secret n'apparaît. Les blocs de code ne sont pas contrôlés.
- Exemples : un chemin ou symbole qui n'existe pas encore (fichier à créer, nom hypothétique) se préfixe par `exemple:` dans les backquotes (`exemple:frontend/src/screens/Nouveau.tsx`) ; les motifs contenant `<n>`, `*`, `…`, `{x}` ou une espace ne sont pas contrôlés non plus.
- Ancres : chaque titre de niveau 1 ou 2 porte une ancre `{#id}` ; l'ancre ne se traduit pas. Les liens internes visent ces ancres (`02-communication-front-back.md#if-match`).
- Ce qui n'est pas vérifié est marqué `À CONFIRMER` et listé au §5 [Points ouverts](#points-ouverts) ; une API externe non confirmée dans le code est marquée `À VÉRIFIER`.
- Références : `D-xxx` renvoie à `journal/decisions.md` ; `DF-Fxx` / `DF-Bxx` à `journal/L51/defauts.md` (défauts de code relevés pendant la rédaction ; leur correction en L52 et L53 est décrite dans `journal/L52/` et `journal/L53/` ; DF-B16 reste ouvert) ; `SEC-xx` aux constats de sécurité résumés au chapitre 16 (les rapports d'audit ne sont pas publiés).
- Versions : lues dans `backend/pyproject.toml`, `backend/constraints.txt`, `frontend/package.json`.
- Rien de sensible : ni secret, ni identifiant de projet cloud, ni détail exploitable d'une vulnérabilité.
- Langue : le manuel est en français et en anglais ; le code, les noms de fichiers et les identifiants restent en anglais ou en français comme dans le dépôt (les clés d'interface sont en français, les noms de fonctions en anglais).

## 4. Autres documents {#autres-documents}

| Document | Pour quoi |
|---|---|
| `docs/guide/architecture.md` | catalogue des modules (point de vue utilisateur / architecture) |
| `docs/CONTRACTS.md` | contrats d'interface figés (API, modèles) |
| `docs/RULES.md` | catalogue normatif des règles de transposition |
| `docs/PLAN.md`, `journal/decisions.md` | plan et décisions |
| `docs/TEAM.md` | protocole d'équipe d'agents, cycle d'un lot, relectures |
| `docs/guide/contribuer.md` | guide de contribution |
| `skills/` | méthodes réutilisables (documentation, recettes, i18n, déploiement…) |

## 5. Points ouverts {#points-ouverts}

Ce que le manuel n'a pas pu vérifier (marque `À CONFIRMER` dans le chapitre). Les défauts de code, eux, sont dans `journal/L51/defauts.md`.

| Chapitre | Point | Pourquoi ce n'est pas vérifié |
|---|---|---|
| [02 §4.7](02-communication-front-back.md#proxy) | En-tête `Host` conservé par le proxy de Vite (`changeOrigin` par défaut) quand l'authentification est active | pas exécuté avec les comptes activés |
| [05](05-conformite-owl-hermit.md#hermit-installation) | Version de Java dans une image Docker construite (celle de `default-jre-headless` de Debian 13) | le build Docker n'est pas possible dans l'environnement de travail (D-012) ; 21.0.12.1 est la version de l'environnement de test |
| [06](06-shacl.md#pieges) | Comportement de `childproc.run_limited` sous Windows (`resource` absent) | non testé, l'application tourne en conteneur Linux |
| [11](11-assistant-krakie.md#fournisseurs) | D-006 cite Bedrock, absent du code : passage prévu par un point d'accès compatible OpenAI | question ouverte à Jerem, aucun code ne le montre |
| [17](17-build-ci-deploiement.md#pieges) | Compression de `nginx.conf` (défaut de l'image nginx) | image non construite ici |
| [17](17-build-ci-deploiement.md#cloud-run) | Exécution réelle des commandes de déploiement | l'opération est faite par Jerem, aucun journal dans le dépôt |
| [17](17-build-ci-deploiement.md#pieges), [18](18-tests.md#pieges) | Écart de comportement entre Python 3.12 (CI, images) et 3.13 (venv des agents) | le venv de travail est en 3.13 ; la suite n'a pas été rejouée en 3.12 |
