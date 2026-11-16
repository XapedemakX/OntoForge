# Inventaire des savoir-faire et des skills (16/11/2026)

Source : CLAUDE.md, `docs/TEAM.md`, `skills/`, `.claude/agents/`, `lots/`, `journal/` (décisions, rapports, revues), `deploy/cloudrun/`, `tools/`. « Candidat compte » = générique, à promouvoir en skill du compte de l'utilisateur après relecture ; « Dépôt » = reste dans `skills/`.

## 1. Inventaire des procédures

| # | Procédure | Fréquence observée | Valeur | Hors OntoForge ? | Couverture existante |
|---|---|---|---|---|---|
| 1 | Transposition OWL → property graph, arbitrage des pertes | chaque lot moteur (L2 à L36) | très haute | oui (méthode) | `owl-to-property-graph` (+ copie compte) |
| 2 | Schéma Curiosity depuis une ontologie | chaque lot Curiosity | haute | oui | `curiosity-schema-design` (+ copie compte) |
| 3 | Schéma Neo4j, requêtes SPARQL → Cypher, SHACL, conformité W3C, conception rapide | fréquent | haute | oui | `neo4j-schema-design`, `graph-query-translation`, `shacl-modeling`, `w3c-ontology-conformance`, `ontology-rapid-design` |
| 4 | Pilotage d'équipe d'agents (contrats, revues OK/KO, escalade, Salle des agents, règle de coût des modèles, limite d'usage) | chaque lot (L0 à L44) | très haute | oui | `ontoforge-delivery` (à jour, §11 ajouté) |
| 5 | Recette Playwright par lot (backend jetable, ports uniques, reproduction de la version déployée) | 30 scripts, ~1 par lot | très haute | oui | aucune → **créé** `recette-playwright-par-lot` |
| 6 | Doc bilingue fr/en : ancres `{#id}`, captures par script, optimisation, scan OCR | L28, L33, L34, chaque lot d'écran | haute | oui | `technical-documentation` couvre le fond, pas la mécanique → **créé** `doc-bilingue-captures` |
| 7 | Audit de sécurité CVE/CWE, tests d'attaque, rapports publics et non publics | L39 à L43, audit global | très haute | oui | aucune → **créé** `audit-securite-cve-cwe` |
| 8 | Relecture croisée multi-rôles (matrice) | chaque lot | très haute | oui | `ontoforge-delivery` + matrice `docs/TEAM.md` ; checklist → `ontoforge-cloture-lot` |
| 9 | Humanisation des textes | fin de chaque lot doc | moyenne | oui | `humanizer` (suffisant) |
| 10 | Publication GitHub avec détecteur de secrets | chaque livraison | haute | oui | aucune (seulement `publish.sh`) → **créé** `publication-github-securisee` |
| 11 | Déploiement Cloud Run pas à pas sous PowerShell | L37-L38, mises à jour | haute | oui | README de déploiement seul, pièges non capitalisés → **créé** `deploiement-cloud-run-powershell` |
| 12 | Audit et refonte mobile (émulation, mesures, maquette, feuilles du bas, gestes) | L44 (1 lot, long) | haute | oui | aucune → **créé** `audit-mobile-refonte` |
| 13 | i18n sûre (lecture avant écriture, `os.replace`, parité, pluriels) | quasi chaque lot front | moyenne | oui | règle d'une ligne dans les fiches d'agents → **créé** `i18n-ecriture-sure` |
| 14 | Clôture de lot (tests, revues, doc-ok, humaniseur, publication) | chaque lot | haute | non (propre au dépôt) | `docs/TEAM.md` éparpillé → **créé** `ontoforge-cloture-lot` |
| 15 | Veille techno et normative | L21, ponctuel | moyenne | oui | `tech-watch` |
| 16 | Découverte produit, carnet d'idées | L9, ponctuel | moyenne | oui | `product-discovery` |
| 17 | Documentation technique d'un logiciel livré par lots | chaque lot | haute | oui | `technical-documentation` (mis à jour : renvois) |
| 18 | Salle des agents (événements `ArtifactData`) | continu | moyenne | partiel | `ontoforge-delivery` §8 + `docs/TEAM.md` ; pas de skill propre |
| 19 | Reprise après limite d'usage (`send_later`, reprise par message) | 3 à 4 fois | moyenne | oui | `ontoforge-delivery` §10 |
| 20 | Génération de jeux de démo, vidéo/GIF de démonstration (`tools/video`, `tools/demo`) | L18, L30, L37 | faible | oui | aucune |
| 21 | Connecteur de données Curiosity (POC) | hors dépôt | haute | oui | skill du compte `curiosity-data-connector` |

## 2. Décision par procédure

| Priorité | Action | Skill | Portée | Justification courte |
|---|---|---|---|---|
| 1 | Créer | `recette-playwright-par-lot` | **candidat compte** | 30 scripts, pièges (ports, CSP, tactile) coûteux à redécouvrir |
| 2 | Créer | `audit-securite-cve-cwe` | **candidat compte** | 5 audits, méthode et gabarits identiques à chaque fois |
| 3 | Créer | `deploiement-cloud-run-powershell` | **candidat compte** | pièges `gcloud.cmd`, `^@^`, stderr, `.gcloudignore`, volume : connaissance rare |
| 4 | Créer | `doc-bilingue-captures` | **candidat compte** | mécanique fr/en + captures reproductibles, absente de `technical-documentation` |
| 5 | Créer | `publication-github-securisee` | **candidat compte** | circuit dépôt lourd → clone léger, détecteur de secrets |
| 6 | Créer | `audit-mobile-refonte` | **candidat compte** | méthode mesurée + maquette avant code |
| 7 | Créer | `i18n-ecriture-sure` | **candidat compte** | petit, mais évite l'écrasement silencieux entre agents |
| 8 | Créer | `ontoforge-cloture-lot` | Dépôt | enchaînement propre à `docs/TEAM.md` |
| 9 | Mettre à jour | `ontoforge-delivery` | Dépôt (version générique déjà possible) | `name` aligné sur le dossier (clôt Q-DOC-11), §11 : matrice, rôles ajoutés, skills voisins |
| 10 | Mettre à jour | `technical-documentation` | Dépôt | renvois vers `doc-bilingue-captures` et `i18n-ecriture-sure` |
| 11 | Mettre à jour | `docs/TEAM.md`, README fr/en | Dépôt | colonne « Skills maintenus » des rôles git, deploy, secu, mobile ; compteur de skills |
| 12 | Garder tel quel | skills 1 à 3, 9, 15, 16 | Dépôt | déjà couverts et maintenus par leur agent |
| 13 | Ne pas faire | skill « Salle des agents » | — | 10 lignes, déjà dans `docs/TEAM.md` et `ontoforge-delivery` §8 |
| 14 | Ne pas faire | skill « reprise après limite » | — | déjà `ontoforge-delivery` §10 |
| 15 | Ne pas faire | skill « humanisation » supplémentaire | — | `humanizer` suffit |
| 16 | Ne pas faire (pour l'instant) | skill vidéo/GIF de démo | — | fréquence faible, outils à stabiliser |
| 17 | Ne pas dupliquer | transposition OWL, schéma Curiosity | déjà au compte | `owl-to-property-graph` et `curiosity-schema-design` existent côté compte ; resynchroniser depuis `skills/` à chaque lot moteur |

## 3. Notes de maintenance
- Les brouillons « candidat compte » ne contiennent aucun secret, nom de client ni donnée personnelle ; ils citent des chemins du dépôt (`tools/…`) comme exemples à adapter. Avant promotion, remplacer ces chemins par des exemples génériques si besoin.
- À vérifier avant promotion : l'interface DNS exacte du registraire (OVH) dans `deploiement-cloud-run-powershell` n'est pas documentée dans le dépôt ; le skill la marque À VÉRIFIER.
- Dette notée en passant : pluriels « (s) » dans l'interface (voir revue humaniseur L44) ; texte généré côté serveur toujours en français.
