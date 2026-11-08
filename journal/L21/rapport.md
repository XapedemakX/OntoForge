# L21 : rapport de l'agent veille

Date : 7 nov. 2026. Aucun code produit modifié. Aucun test exécuté (livrables documentaires et de configuration).

## Livrables

| Fichier | Contenu |
|---|---|
| `docs/veille/nvidia-auto-ontology.md` | NVIDIA Auto Ontology : text-to-SQL sur bases relationnelles, aucun OWL/RDF ; Apache 2.0 ; idées N1 à N6 |
| `docs/veille/neonto.md` | neonto : cabinet de conseil + éditeur (SaaS par utilisateur) ; positionnement face à Protégé, TopQuadrant, n10s, Curiosity ; idées E1 à E7 |
| `docs/veille/normes.md` | État vérifié le 7/11/2026 : W3C, Neo4j, Curiosity, bibliothèques Python et JavaScript |
| `docs/veille/processus-mise-a-jour.md` | Veille mensuelle, Dependabot, tests W3C et matrice Neo4j, panneau « Krakie, mets-toi à jour » (proposé), circuit de relecture |
| `.github/dependabot.yml` | Configuration prête (pip, npm, docker) |
| `skills/tech-watch/SKILL.md` | Méthode réutilisable |
| `docs/IDEES.md` | Section « Veille 7/11 », idées V-01 à V-21 classées gain/effort |

## Relectures demandées

Aucune n'a eu lieu. Matrice de `docs/TEAM.md` : fiche de veille relue par l'expert du domaine, puis humaniseur.

| Relecteur | Périmètre | Points à vérifier en priorité |
|---|---|---|
| **w3c** | `normes.md` partie 1 ; `processus-mise-a-jour.md` §3.1 | Statuts et dates (RDF 1.2 CR, SPARQL 1.2 WD, SHACL 1.2 WD) ; affirmation « pyshacl ne se présente pas comme SHACL 1.2 » ; pertinence des suites de tests retenues ; absence de tests OWL 2 exploitables |
| **shacl** | `normes.md` §1 (lignes SHACL) ; §4.1 pyshacl | Liste des nouveautés SHACL 1.2 ; effet de pyshacl 0.40 sur `shacl/validate.py` et `editing/files.py` |
| **query** | `normes.md` ligne SPARQL ; `processus` §3.1 | Intérêt réel de SPARQL 1.2 pour `queries/endpoint.py` |
| **neo4j** | `normes.md` partie 2 ; `processus` §3.2 ; idées V-01, V-08, V-14 | Syntaxe des contraintes **non relue en ligne** (page bloquée) ; effet de `CYPHER 5` / `CYPHER 25` sur nos scripts ; noms d'images et prise en charge Enterprise dans testcontainers (À VÉRIFIER) ; graph types |
| **curiosity** | `normes.md` partie 3 ; idées V-02, V-13, V-15 | Règle de compatibilité paquet / serveur ; type de retour de `AddOrUpdate` ; fabrique `Schema` ; page « release notes » douteuse (2.5.0 non datée) |
| **scout** | `processus` §4 (panneau Krakie) | Pertinence d'un cheat code ; contenu du panneau |
| **humain** | tous les fichiers ci-dessus | Style ; le sens ne doit pas bouger, puis `doc` vérifie |
| **doc** | `skills/tech-watch/SKILL.md` | Exactitude des chemins cités |

## Points non vérifiés (à ne pas citer comme acquis)

- API GitHub, API NuGet JSON, pages du manuel Neo4j sur les contraintes et site ossie.apache.org : inaccessibles. Chiffres GitHub de NVIDIA (étoiles, forks) issus d'une lecture automatique de page.
- Page « Editor » de neonto illisible ; tarif absent ; modèle SaaS par utilisateur tiré d'une fiche d'incubateur.
- TopBraid EDG et Composer : non décrits (la page d'accueil actuelle de TopQuadrant n'en parle pas).
- Dates de pyshacl 0.40.2 divergentes entre PyPI (28/10/2026) et son journal (28/07/2026).
- Dependabot : documentation officielle non rechargée dans ce lot.

## Questions pour Jerem

1. Veux-tu que la tâche de veille mensuelle soit programmée (prompt prêt dans `processus-mise-a-jour.md` §1) ?
2. Le panneau « Krakie, mets-toi à jour » : on le code (effort S à M) ?
3. Peux-tu lancer `tools/dotnet/check-curiosity.ps1 -Version 26.11.7740` sous Windows ?

## Trois actions prioritaires

1. Tester le DDL Neo4j sur 5.26 et 2026.10 (`CYPHER 5` et `CYPHER 25`) et exécuter `check-curiosity.ps1` sur 26.11.7740 (V-01, V-02).
2. Montée groupée rdflib / pyshacl / owlrl, suite complète relancée (V-03), avec Dependabot activé (V-04).
3. Brancher les suites de tests W3C en CI, 1.2 en suivi seulement (V-05).
