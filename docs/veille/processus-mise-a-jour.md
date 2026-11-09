# Processus de mise à jour : normes, bibliothèques, cibles

Auteur : agent `veille`. Lot L21. Rédigé le 7 nov. 2026.
Question de Jerem : « comment s'assurer d'être aux dernières normes W3C ou aux standards Neo4j / Curiosity, comment mettre à jour le code automatiquement ».

> État depuis L31 (8 nov. 2026). `standards.json` est réel : `backend/ontoforge/standards/standards.json`, livré avec l'application et lu par l'API (`GET /api/standards`), les générateurs et le contrôle de versions d'un projet. Il remplace l'emplacement `docs/veille/standards.json` cité plus bas. La veille le met à jour en même temps que `normes.md`, champ `updated` compris : c'est lui qui réarme la bulle « plus tard » de Krakie. Il porte W3C (RDF, OWL, SHACL, SPARQL : statut et date), Neo4j (5.26 LTS, 2026.10, 4.4) et Cypher, Curiosity.Library, et les bibliothèques internes à titre d'information. Les dépréciations de syntaxe se traduisent par une entrée `rules` ou `features` du fichier, pas par du code.

## Réponse courte

On ne met pas un code sémantique à jour « automatiquement » sans filet. On automatise trois étapes (détecter, proposer, prouver) et on garde une quatrième, humaine (décider) :

1. Détecter : une veille mensuelle compare ce qu'OntoForge suit à ce qui est publié (`standards.json` contre W3C, Neo4j, NuGet, PyPI, npm).
2. Proposer : Dependabot ouvre les demandes de montée de bibliothèques. L'agent veille ouvre un lot pour les normes et les cibles.
3. Prouver : des tests de conformité officiels (W3C) et une matrice Neo4j cassent la CI quand quelque chose bouge.
4. Décider : un expert relit, puis le chef ouvre ou ferme le lot.

Décisions de Jerem du 7/11 (`journal/decisions.md`), qui prévalent sur les propositions de cette fiche :

- D-L21-01 : pas de veille mensuelle planifiée pour l'instant. La veille se fait à la demande ; la tâche du §1 n'est pas créée.
- D-L21-02 : pas de montée de version, on reste sur une base stable. Dependabot signale, rien n'est fusionné sans l'accord de Jerem, mises à jour de sécurité comprises (proposées, puis arbitrées).
- D-L21-03 : validation Neo4j et Curiosity manuelle. Pas de testcontainers ni de compilation Curiosity en CI ; la CI se limite aux tests backend, au build front et aux recettes. Le « prouver » ci-dessus (tests W3C, matrice Neo4j) reste donc une cible, pas l'état actuel.

Ce qui ne s'automatise pas : décider de coder RDF 1.2 ou SHACL 1.2, choisir une syntaxe Neo4j par défaut, passer une version de Curiosity en production.

```
 veille mensuelle ──► normes.md + standards.json ──► écart ? ──► lot ouvert
        ▲                                                        │
 Dependabot (hebdo) ──► PR de bibliothèque ──────────────────────┤
                                                                  ▼
                              expert relit ──► CI : tests W3C + matrice Neo4j + pytest
                                                                  ▼
                                                chef clôt ──► git livre
```

---

## 1. Tâche planifiée de veille mensuelle

Statut : non créée (D-L21-01). Le prompt ci-dessous sert à lancer la veille à la demande, à la main.

Quoi : une exécution par mois de l'agent `veille` (fiche `.claude/agents/veille-techno.md`, méthode `skills/tech-watch/SKILL.md`).

Quand : le 5 de chaque mois à 19 h 17, heure de Paris, pour éviter les créneaux chargés du matin américain. Expression : `CRON_TZ=Europe/Paris 17 19 5 * *`.

Proposition de prompt (à copier dans la tâche planifiée) :

> Tu es l'agent veille d'OntoForge (dépôt /home/claude/OntoForge). Lis `.claude/agents/veille-techno.md` et `skills/tech-watch/SKILL.md`. Relis les flux de la liste `docs/veille/processus-mise-a-jour.md` §1 « Flux ». Compare à `docs/veille/standards.json` (s'il existe) et à `docs/veille/normes.md`. Mets à jour `normes.md` (colonnes dernière version, statut, date de consultation). Si un écart change l'action proposée, ou si une norme change de statut (WD → CR → REC), écris `lots/Lx-veille-<mois>.md` avec l'écart, les fichiers touchés et le relecteur. Ne modifie pas le code produit. En cas d'erreur 429, arrête-toi et dis-le. Rapport de 10 lignes maximum.

Flux à relire (adresses vérifiées le 7/11/2026 ; une adresse qui change est elle-même un écart à signaler) :

| Domaine | Flux | Comment | Ce qu'on cherche |
|---|---|---|---|
| W3C RDF/SPARQL | https://www.w3.org/groups/wg/rdf-star/publications/ | page des publications du groupe | Changement de statut ou de date |
| W3C SHACL | https://www.w3.org/groups/wg/data-shapes/publications/ | idem | idem |
| W3C JSON-LD | https://www.w3.org/groups/wg/json-ld/publications/ | idem | Apparition d'un JSON-LD 1.2 |
| W3C OWL | https://www.w3.org/TR/owl2-overview/ | page du document | Mention d'une révision |
| Suites de tests | https://github.com/w3c/rdf-tests, https://github.com/w3c/data-shapes | `git ls-remote` et journal des commits | Nouveaux dossiers (`rdf12`, `sparql12`, `shacl12-test-suite`) |
| Neo4j | https://neo4j.com/release-notes/database/ (pages `neo4j-AAAA-MM`) ; https://neo4j.com/docs/cypher-manual/25/deprecations-additions-removals-compatibility/ ; https://support.neo4j.com/s/article/115013134648-Neo4j-Supported-Versions | lecture de page | Nouvelle version, LTS, dépréciation de syntaxe générée |
| Curiosity | https://www.nuget.org/packages/Curiosity.Library ; https://blog.curiosity.ai/ (bilan mensuel) ; https://docs.curiosity.ai/ (journal des modifications) | lecture de page | Nouvelle version, changement d'API de bibliothèque |
| PyPI | `https://pypi.org/pypi/<paquet>/json` (rdflib, pyshacl, owlrl, pyoxigraph, fastapi, pydantic, …) | HTTP JSON | Version, date, `requires_python` |
| npm | `https://registry.npmjs.org/<paquet>/latest` | HTTP JSON | idem |
| Journaux | `CHANGELOG.md` de rdflib, pySHACL, Oxigraph (adresses brutes GitHub) | HTTP | Ruptures, support RDF 1.2 / SHACL 1.2 |

Contraintes constatées aujourd'hui : l'API JSON de NuGet et le manuel Cypher sur les contraintes sont refusés par les outils de l'agent (proxy et robots). La veille lit alors la page web, et le dit dans la section « Limites » de `normes.md`.

Sortie attendue : un diff de `normes.md`, une mise à jour de `standards.json`, et soit rien, soit un lot ouvert. Un mois sans écart produit une ligne dans le journal et aucun lot.

Règle d'ouverture d'un lot :

| Situation | Action |
|---|---|
| Norme W3C passe CR ou REC | Lot « évaluer le support », relecteur w3c |
| Nouvelle version Neo4j avec dépréciation de syntaxe que génère OntoForge | Lot, relecteur neo4j |
| Nouvelle version de Curiosity.Library | Test de compilation, lot si échec, relecteur curiosity |
| Bibliothèque : majeure disponible | Dependabot ouvre déjà ; la veille signale si la montée touche une règle de transposition |
| Rien de nouveau | Aucune ouverture |

---

## 2. Dependabot (ou Renovate)

Choix : Dependabot, car le dépôt est sur GitHub (`github.com/XapedemakX/ontoforge`), sans compte ni hébergement à ajouter. Renovate est plus souple (regroupements, expressions pour des fichiers sur mesure), mais exige une application à installer. À reconsidérer si on veut suivre automatiquement les versions de `standards.json`.

Configuration prête : `.github/dependabot.yml` (créé par ce lot). Contenu :

- `pip` sur `/backend` : hebdomadaire. Les bibliothèques sémantiques (`rdflib`, `pyshacl`, `owlrl`, `pyoxigraph`, `owlready2`) sont regroupées dans une seule demande, parce qu'elles se tiennent entre elles (pyshacl 0.40 exige `rdflib>=7.3` et `owlrl>=7.6.1`).
- `npm` sur `/frontend` : hebdomadaire. Les montées majeures sont ignorées par Dependabot sur tous les écosystèmes (D-L21-02) : React, Vite, TypeScript et le plugin React passeraient par un lot dédié, non ouvert. Chaque écosystème est limité à 1 ou 2 demandes ouvertes.
- `docker` sur `/backend` et `/frontend` : mensuel.
- Pas d'écosystème `nuget` : le dépôt ne contient aucun `.csproj`. Le code C# est généré et compilé hors dépôt. La veille mensuelle couvre Curiosity.Library.
- `github-actions` à la racine : mensuel, car le workflow `.github/workflows/ci.yml` existe depuis L24.

Limite connue : Dependabot ne voit que les versions épinglées dans `pyproject.toml` (formes `==x.y.z`). C'est le cas ici.

À activer côté GitHub par l'agent `git` ou par Jerem : Paramètres, Sécurité, « Dependabot alerts » et « Dependabot security updates ». Le fichier de configuration ne suffit pas pour les alertes de sécurité.

Circuit d'une demande : Dependabot ouvre une PR et la CI passe ou casse. L'agent `git` ne fusionne que si Jerem a donné son accord (D-L21-02), si la CI est verte et si le relecteur du domaine a mis un verdict OK dans `journal/` quand la bibliothèque touche l'une de ces zones :

| Bibliothèque | Relecteur |
|---|---|
| rdflib, owlrl, pyoxigraph | w3c + query |
| pyshacl | shacl + w3c |
| fastapi, pydantic, httpx | lead |
| React, Vite, @xyflow/react, cytoscape | scout |

---

## 3. Tests de conformité qui cassent quand une norme change

Principe : au lieu de lire les normes, on exécute leurs tests officiels contre ce que fait OntoForge. Une régression de bibliothèque ou un changement de norme devient une CI rouge.

### 3.1 Suites W3C

Statut : proposition, hors CI tant qu'aucune décision ne rouvre D-L21-03 (la CI se limite aux tests backend, au build front et aux recettes).

État vérifié le 7/11/2026 (clones locaux, `git clone --depth 1`) :

| Suite | Dépôt | Contenu utile | Taille | Licence |
|---|---|---|---|---|
| RDF | [w3c/rdf-tests](https://github.com/w3c/rdf-tests) | `rdf/rdf11`, `rdf/rdf12` (Turtle, N-Triples, TriG, N-Quads, XML, semantics) ; `sparql/sparql11`, `sparql/sparql12` | 44 Mo | « LICENSES FOR W3C TEST SUITES » (double licence) |
| SHACL | [w3c/data-shapes](https://github.com/w3c/data-shapes) | `data-shapes-test-suite/tests/core` et `sparql` (SHACL 1.0) ; `shacl12-test-suite/tests` (1.2) | 26 Mo | dépôt W3C (`LICENSE.md`) |

Les tests sont décrits par des fichiers `manifest.ttl` (convention W3C pour Turtle et SPARQL). Un lanceur lit le manifeste, exécute chaque cas avec la bibliothèque et compare au résultat attendu.

Plan d'intégration (à réaliser dans un lot, pas ici) :

1. Récupération : une étape CI fait `git clone --depth 1 --branch <commit épinglé>` des deux dépôts dans `backend/tests/w3c/_suites/` (dossier ignoré par git). Le commit est épinglé dans `docs/veille/standards.json` ; la veille propose de le changer chaque mois.
2. Lanceur : `backend/tests/w3c/test_suites.py`, qui parcourt les manifestes avec rdflib. Marqueur `@pytest.mark.w3c`.
3. Ce qu'on teste, par ordre de valeur :
   - Syntaxes RDF 1.1 que l'import d'OntoForge accepte : Turtle, N-Triples, RDF/XML, JSON-LD (rdflib fait le travail ; on mesure notre sélecteur de format dans `io/rdf_import.py`).
   - Validation SHACL 1.0 : `data-shapes-test-suite/tests/core` contre `shacl/validate.py` (pyshacl).
   - RDF 1.2 et SHACL 1.2 : en lecture seule, hors CI bloquante. Les cas sont lancés, le taux de réussite est enregistré dans `docs/veille/conformite.json`, rien ne casse. Quand le taux monte, c'est le signal qu'il devient possible de coder la 1.2.
4. Liste d'attentes connues : `backend/tests/w3c/xfail.txt` (cas qu'on sait échouer, avec raison). Une CI qui se met à réussir un cas listé échoue aussi : on retire alors la ligne (c'est le signal de rattrapage).
5. Fréquence : à chaque PR pour 1.1 (rapide, quelques minutes à mesurer) ; chaque nuit pour 1.2.

Ce qu'on ne teste pas : OWL 2. Les cas de test OWL 2 sont définis par la recommandation *OWL 2 Conformance* (2e édition, REC du 11/12/2012) et ne couvrent pas notre usage (conversion), à revoir avec l'expert W3C. Les tests de conformité OWL d'OntoForge restent ceux de `samples/trap`.

### 3.2 Matrice Neo4j

Statut : non retenue pour l'instant (D-L21-03). Jerem valide à la main le Cypher généré en l'important dans Neo4j ; pas de testcontainers en CI. Ce qui suit décrit la cible si la décision est rouverte.

Objectif : vérifier que `schema.cypher`, `ingest.cypher` et `validation.cypher` s'exécutent sur plusieurs versions et deux modes de Cypher.

| Axe | Valeurs proposées |
|---|---|
| Version | `5.26` (LTS), dernière 2026.x |
| Cypher | `CYPHER 5`, `CYPHER 25` (préfixe, ou défaut de la base) |
| Édition | Community et Enterprise (le code sépare déjà les deux sections ; l'Enterprise exige d'accepter la licence) |

Moyen : `testcontainers` (Python, 4.15.0 au 7/11/2026) avec son module Neo4j ; images Docker `neo4j:<tag>`. Les noms exacts d'étiquettes pour les versions 2026.x et la prise en charge de la licence Enterprise dans testcontainers sont À VÉRIFIER avant le lot.

Scénario : générer le DDL du jeu `automaint`, le jouer sur chaque cellule de la matrice, interroger `SHOW CONSTRAINTS`, comparer au nombre attendu. Casser la CI si une instruction échoue. C'est l'idée P-09 de `docs/IDEES.md`, déjà demandée.

### 3.3 Compilation Curiosity

Statut : manuelle (D-L21-03). Jerem importe le C# généré dans Curiosity ; l'étape CI sous Linux n'est pas retenue.

`tools/dotnet/check-curiosity.ps1` sait déjà compiler le C# généré. Il tourne sous Windows avec le SDK .NET 8. Deux étapes : l'exécuter une première fois à la main avec `-Version 26.11.7740`, puis, si on veut de la CI, un conteneur `mcr.microsoft.com/dotnet/sdk` sous Linux avec un script équivalent en bash (image à vérifier). Le paquet est téléchargé depuis nuget.org ; le script n'envoie rien d'autre.

### 3.4 Tests déjà présents à étendre

- `backend/tests/test_mapping_oracle.py` : oracle des constats. Ajouter une ligne par écart de norme traité.
- `backend/tests/test_target_neo4j.py`, `test_target_curiosity.py` : valeurs figées. Une montée de syntaxe passe par la mise à jour des valeurs de référence, relue par l'expert.

---

## 4. Proposition : « Krakie, mets-toi à jour » (non codée)

Présentation : un cheat code dans l'application. Un geste caché (à choisir : les déclencheurs clavier de l'easter egg Krakie sont déjà pris depuis L20) ouvre un panneau sobre où la mascotte Krakie affiche l'état des normes. Rien n'est installé ni mis à jour par ce panneau.

### Ce que montre le panneau

| Bloc | Contenu |
|---|---|
| Normes | Pour chaque norme : version utilisée par OntoForge, dernière version connue, statut (REC / CR / WD), pastille verte, orange ou rouge |
| Bibliothèques | Versions réellement chargées (`importlib.metadata`) contre la dernière connue |
| Cibles | Neo4j : versions et mode Cypher pour lesquels le DDL a été testé. Curiosity : version du paquet testée |
| Écarts connus | Liste courte : « SHACL 1.2 : brouillon, non codé », « pyshacl 0.40 disponible, 0.29.1 utilisé » |
| Fraîcheur | Date de la dernière veille. Au-delà de 45 jours, le panneau dit « informations anciennes » |

### D'où viennent les données : `standards.json`

Un fichier maintenu par l'agent veille, versionné dans `docs/veille/standards.json`, livré avec l'image (copié dans le conteneur). Le panneau le lit en local : aucun appel réseau. Les versions réellement chargées se lisent à l'exécution.

Forme proposée :

```json
{
  "schema": 1,
  "checked_on": "2026-11-07",
  "w3c": [
    {"id": "rdf", "name": "RDF Concepts", "used": "1.1", "latest": "1.2",
     "status": "CR", "status_date": "2026-04-07",
     "url": "https://www.w3.org/TR/rdf12-concepts/",
     "gap": "RDF 1.2 non supporté", "action": "surveiller", "files": ["backend/ontoforge/io/rdf_import.py"]}
  ],
  "neo4j": {"tested": [{"version": "5.26", "cypher": ["5"]}], "latest": "2026.10.1", "lts": "5.26"},
  "curiosity": {"package": "Curiosity.Library", "tested": null, "latest": "26.11.7740"},
  "libraries": [
    {"name": "pyshacl", "ecosystem": "pypi", "pinned": "0.29.1", "latest": "0.40.2", "action": "lot"}
  ]
}
```

Règles : la veille remplit `latest`, `status`, `gap`, `action`. Le code remplit `used` et `pinned` au moment du test (script de contrôle qui lit `pyproject.toml` et `package.json`). Une CI vérifie que `pinned` du fichier est égal à ce qui est réellement épinglé.

### Pourquoi « cheat code » et pas un écran visible

- La plupart des utilisateurs n'en ont pas besoin, et un indicateur d'écarts permanent les inquiéterait pour rien.
- Le panneau est un outil de l'ingénieur-référent : savoir quoi répondre à un client qui demande « votre outil est-il à jour de SHACL 1.2 ? ».
- Il reste honnête : il affiche la date de la dernière veille, il ne prétend pas surveiller en direct.

### Coût et risques

| Point | Évaluation |
|---|---|
| Effort | S : lecture du fichier + un écran + test. La mécanique `standards.json` demande M pour le script de contrôle de cohérence |
| Risque | Données périmées présentées comme fiables : parade par la date visible et le seuil de 45 jours |
| À ne pas faire | Lancer une mise à jour depuis l'appli, ni interroger des sites tiers depuis le navigateur de l'utilisateur |
| Relecteurs | scout (écran), w3c, neo4j et curiosity (contenu) |

Statut : proposée, non codée. À décider par Jerem. Entrée dans `docs/IDEES.md`, section « Veille 7/11 » (V-11).

---

## 5. Circuit de relecture croisée

Étapes, avec le propriétaire de chacune.

| Étape | Qui | Livrable |
|---|---|---|
| 1. Détection | veille (tâche mensuelle) ou Dependabot | `normes.md` à jour, PR de bibliothèque |
| 2. Proposition | veille | Ligne d'action dans `normes.md` avec fichiers touchés ; `lots/Lx-veille-<mois>.md` si écart |
| 3. Relecture du fond | Expert du domaine : w3c (normes), shacl (SHACL), neo4j, curiosity, query (SPARQL) | `journal/Lx/review-<expert>-it1.md` au format de `docs/TEAM.md` |
| 4. Décision d'ouvrir | chef | Contrat de lot `lots/Lx.md` ou « sans suite » dans `journal/decisions.md` |
| 5. Production | pilote du lot | Code, tests, skill mis à jour |
| 6. Validation machine | CI : pytest, suites W3C, matrice Neo4j | CI verte |
| 7. Style | humain (humaniseur), puis doc vérifie que le sens n'a pas bougé | `journal/<lot>/doc-ok.md` |
| 8. Livraison | git | Fusion et étiquette |

Règles :

- La veille ne modifie pas le code produit. Elle propose.
- Une fiche de veille est relue par l'expert du domaine, puis par l'humaniseur (matrice de `docs/TEAM.md`).
- Une incertitude reste marquée « À VÉRIFIER » dans la fiche jusqu'à preuve.
- Une CI rouge sur un changement de norme ne se contourne pas : soit on corrige, soit on inscrit un `xfail` argumenté, relu par l'expert.

---

## 6. Ce qui reste à faire pour que ce processus tourne

| # | Tâche | Qui | Effort | État |
|---|---|---|---|---|
| 1 | Activer les alertes Dependabot dans GitHub | git / Jerem | S | À faire ; les mises à jour restent à arbitrer (D-L21-02) |
| 2 | Programmer la tâche mensuelle (§1) | lead | S | Écartée (D-L21-01) |
| 3 | Créer `standards.json` à partir de `normes.md` | veille | S | Non fait, utile seulement avec le panneau (8) |
| 4 | Créer le workflow CI (pytest, puis suites W3C) | git | M | Fait par L24 pour pytest, build et recettes ; suites W3C hors périmètre (D-L21-03) |
| 5 | Lanceur de manifestes W3C | w3c + query | M | Non fait |
| 6 | Matrice Neo4j avec testcontainers | neo4j | M | Écartée (D-L21-03) |
| 7 | Exécuter une première fois `check-curiosity.ps1` | Jerem (Windows) | S | Manuel, à la discrétion de Jerem (D-L21-03) |
| 8 | Panneau « Krakie, mets-toi à jour » | lead + scout | S à M | Proposé, à décider par Jerem |

## 7. Limites

- Aucune suite de tests n'a été exécutée dans ce lot. Les tailles et dossiers viennent de clones peu profonds faits le 7/11/2026.
- Je n'ai pas vérifié que Dependabot accepte `pyproject.toml` à dépendances épinglées dans toutes les configurations. C'est son comportement documenté, la première exécution le confirmera.
- Les temps de CI sont des hypothèses, à mesurer.

## Sources

- Dependabot, options de configuration : https://docs.github.com/en/code-security/dependabot/working-with-dependabot/dependabot-options-reference (connu, non rechargé dans ce lot : à revérifier avant activation)
- W3C rdf-tests : https://github.com/w3c/rdf-tests ; W3C data-shapes : https://github.com/w3c/data-shapes (clones du 7/11/2026)
- testcontainers (PyPI) : https://pypi.org/project/testcontainers/
- Autres sources : `docs/veille/normes.md` §7.
