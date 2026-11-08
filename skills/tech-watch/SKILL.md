---
name: tech-watch
description: Méthode de veille technologique et normative pour un outil sémantique (OWL, RDF, SHACL, SPARQL, Neo4j, Curiosity). À utiliser pour analyser un outil ou un projet externe, vérifier l'état des normes W3C et des cibles, comparer les versions suivies par le code aux dernières publiées, et transformer un écart en lot relu. Sources primaires d'abord, rien d'inventé.
---
# Veille techno et normative (L21)

Maintenu par l'agent `veille`. Exemples : `docs/veille/nvidia-auto-ontology.md`, `docs/veille/neonto.md`, `docs/veille/normes.md`, `docs/veille/processus-mise-a-jour.md`.

## 1. Règles de base

1. Source primaire d'abord : dépôt, spécification (`www.w3.org/TR/...`), notes de version, registre de paquets. Un blog ou un résumé ne sert que de piste.
2. Chaque affirmation porte un lien et une date de consultation. Sans lien, elle est marquée « non vérifié ».
3. Lire le code, pas seulement le README. Un outil qui dit « ontology » peut ne contenir aucun RDF (cas NVIDIA Auto Ontology : couche sémantique SQL, zéro OWL).
4. Dire ce qui n'a pas pu être lu (site bloqué, robots, 403, 429) dans une section « Limites ». Ne jamais combler un trou. Sur une erreur 429, s'arrêter et le dire.
5. Ne pas modifier le code produit. Proposer ; un écart devient un lot relu par l'expert du domaine.
6. Vérifier la licence avant d'envisager de reprendre quoi que ce soit.

## 2. Analyser un outil externe

Plan de la fiche (fichier `docs/veille/<sujet>.md`) :
1. Verdict en 5 lignes.
2. Ce que fait vraiment l'outil (pipeline, formats, modèles requis), avec les fichiers lus.
3. Licence, maturité (activité, releases, contributions, tests), risques.
4. Recouvrement avec le produit : tableau critère par critère.
5. Idées à reprendre, classées gain 1-5 / effort S, M, L, avec décision (reprendre, étudier, éviter).
6. Limites et sources.

Outils pratiques :
- Contenu d'un dépôt : `git clone --depth 50`, puis lecture de `pyproject.toml`, `package.json`, des dossiers de code, de la CI. Compter les fichiers de test.
- Pages web : un outil de lecture de page résume ; recouper les chiffres qu'il rapporte (étoiles, forks).
- Fichiers bruts : `https://raw.githubusercontent.com/<org>/<dépôt>/<branche>/<fichier>`.
- Étiquettes d'un dépôt : `git ls-remote --tags <url>`.
- Si l'API GitHub est refusée, ne pas insister : le dire.

## 3. Suivre les normes et les cibles

Pour chaque élément du tableau `normes.md`, six colonnes : version suivie (lue dans le code et les fichiers de dépendances), dernière publiée, statut (REC, CR, WD, Note), écart, fichiers touchés, action (Rien, Surveiller, Tester, Lot).

Où lire l'état :

| Domaine | Source |
|---|---|
| Normes W3C | liste des publications du groupe (`https://www.w3.org/groups/wg/<groupe>/publications/`) et en-tête de chaque `TR` (statut, date, version datée) |
| Suites de tests | `w3c/rdf-tests` (dossiers `rdf/rdf12`, `sparql/sparql12`), `w3c/data-shapes` (`data-shapes-test-suite`, `shacl12-test-suite`) |
| Neo4j | notes de version `neo4j.com/release-notes/database/neo4j-AAAA-MM/`, manuel Cypher (page des ajouts et dépréciations), page des versions prises en charge |
| Curiosity | page NuGet `Curiosity.Library`, bilan mensuel du blog, documentation SDK |
| Python | `https://pypi.org/pypi/<paquet>/json` (champs `info.version`, date de dépôt, `requires_python`) |
| JavaScript | `https://registry.npmjs.org/<paquet>/latest` |
| Rythme et ruptures | `CHANGELOG.md` de la bibliothèque (support d'une norme, ruptures) |

Pièges :
- Un statut W3C change : WD, CR, REC. Ne coder une norme qu'à partir de CR, et seulement si une bibliothèque la supporte et que les tests officiels existent.
- Un brouillon peut changer en quelques jours : toujours citer la date de la version consultée.
- Numérotation Neo4j : calendaire (`ANNÉE.MOIS.patch`) depuis 2025 ; seules certaines versions sont LTS ; Cypher a ses propres versions (5 et 25).
- Curiosity.Library : versions « année.mois.build », publiées plusieurs fois par semaine ; la compatibilité avec le serveur n'est pas documentée.
- Les pages de documentation vieillissent plus vite que le produit (cas de la page de conformité GQL de Neo4j, qui s'arrête à 2025.08, et de la page de notes de version de Curiosity, non datée). Recouper.
- Une dépendance épinglée très en retard peut cacher une rupture : lire le journal des modifications avant de monter (ex. pyshacl 0.40 retire `ConjunctiveGraph`).

## 4. Transformer un écart en lot

1. Écrire l'écart dans `normes.md` (ligne + fichiers touchés).
2. Si la norme change de statut, ou si une syntaxe générée est dépréciée, ou si un test de conformité échoue : écrire un contrat `lots/Lx-veille-<mois>.md` (objectif, fichiers, critères d'acceptation, relecteur).
3. Relecture croisée selon la matrice de `docs/TEAM.md` : expert du domaine, puis humaniseur.
4. La CI valide (pytest, suites W3C, matrice Neo4j). Le chef clôt.

## 5. Automatisation

- Dependabot : `.github/dependabot.yml` (bibliothèques sémantiques regroupées ; montées majeures du frontend traitées en lot).
- Veille mensuelle : tâche planifiée, prompt dans `docs/veille/processus-mise-a-jour.md` §1.
- Tests qui cassent quand une norme change : suites W3C et matrice Neo4j (`processus-mise-a-jour.md` §3).
- `docs/veille/standards.json` : état lisible par machine, alimenté par la veille, prévu pour le panneau « Krakie, mets-toi à jour » (proposé, non codé).

## 6. Format de rendu

- Français, phrases courtes.
- Tableaux pour les comparaisons, listes pour les décisions.
- Pas d'emoji, pas de formules de vente. Un chiffre sans source n'est pas écrit.
- Relecture : expert du domaine, puis humaniseur. Les propositions vont dans `docs/IDEES.md` avec la mention « veille ».
- Événements dans la Salle des agents : agent `veille`, format de `docs/TEAM.md`.

## 7. Retours d'expérience (à enrichir à chaque lot)

- L21 : le nom d'un outil ne dit pas ce qu'il fait. « Auto Ontology » est du text-to-SQL ; « neonto » est un cabinet de conseil avec un éditeur annexe. Lire le code et les pages produit avant de comparer.
- L21 : l'API JSON de NuGet, l'API GitHub et certaines pages du manuel Neo4j (robots) sont inaccessibles depuis l'environnement des agents. Prévoir une lecture de page de repli et le noter.
