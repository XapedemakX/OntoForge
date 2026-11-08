# L21 — revue w3c, itération 1

Relecteur : expert W3C (agent `w3c`). Date : 7/11/2026. Périmètre : `docs/veille/normes.md` partie 1 et §4.1 (bibliothèques sémantiques), `docs/veille/processus-mise-a-jour.md` §2 et §3.1, `.github/dependabot.yml`, `skills/tech-watch/SKILL.md`.
Sources relues le 7/11/2026 : en-têtes de www.w3.org/TR/rdf12-concepts, sparql12-query, shacl12-core, owl2-overview, json-ld11 ; listes de publications des groupes rdf-star et data-shapes ; PyPI (rdflib, pyshacl, owlrl) ; roue pyshacl 0.40.2 téléchargée et inspectée.

```
verdict: OK
bloquants:
  (aucun après correction ; voir « corrigé par le relecteur »)
non-bloquants:
  - [docs/veille/normes.md:12] « SPARQL 1.2 et SHACL 1.2 sont des brouillons publiés cette semaine » : SPARQL 1.2 Query date du 01/11, SHACL 1.2 Core du 02/11. Écrire les dates plutôt que « cette semaine », qui vieillit mal.
  - [docs/veille/normes.md:28] « aucune occurrence dans backend/ontoforge » de RDF-star : vrai pour le code suivi, mais `localstore/_worker.py` (L19, non encore commité) traite déjà les triplets cités. À reprendre à la veille suivante, une fois L19 livré.
  - [docs/veille/normes.md:85] pyshacl 0.40 : la méta-shape `pyshacl/assets/shacl-shacl.ttl`, chemin lu par `editing/files.py`, existe toujours dans la roue 0.40.2 (vérifié). Le lot de montée doit quand même passer `editing/files.py` à l'option documentée `meta_shacl=True` plutôt qu'au chemin d'un fichier interne.
  - [.github/dependabot.yml:18] le commentaire dit « Ces quatre bibliothèques » alors que le groupe `semantique` en liste cinq (owlready2 en plus). `processus-mise-a-jour.md` §2 en cite quatre aussi. Harmoniser.
  - [.github/dependabot.yml] syntaxe v2 valide : `groups.*.patterns`, `ignore[].update-types` au format `version-update:semver-major`, `schedule.day/time/timezone` sur `weekly`. Chemins réels : `/backend` (pyproject.toml, Dockerfile), `/frontend` (package.json, Dockerfile). Le Dockerfile backend se construit depuis la racine (`docker-compose.yml`), mais Dependabot lit seulement la ligne `FROM` dans `/backend/Dockerfile`, donc pas de problème. Les étiquettes `dependencies` et `veille` doivent exister dans le dépôt GitHub (à créer par l'agent git). Les motifs `pyoxigraph`, `starlette` et `testcontainers*` ne correspondent à aucune dépendance actuelle : c'est sans effet, mais à savoir.
  - [docs/veille/processus-mise-a-jour.md:121] « Les cas de test OWL 2 du W3C sont sur le wiki » : citer la recommandation *OWL 2 Conformance (Second Edition)*, REC du 11/12/2012, qui définit ces cas.
  - Hors périmètre veille, relevé en relisant L22 : `io/rdf_import.py:165` analyse sans `publicID`. Une IRI relative sans `@base`, dans un fichier importé, devient donc `file:///<répertoire du serveur>/…`. Même défaut que celui corrigé dans l'éditeur (revue w3c L22). À traiter dans un lot d'import.
corrigé par le relecteur (dans normes.md) :
  - l. 30 : dates des WD SPARQL 1.2 Update / Protocol / Graph Store / Results. La plage « 24/09 à 25/10 » était fausse : Protocol 23/07, Results JSON 13/08, Results XML 27/12/2024.
  - Vérifiées exactes : RDF 1.2 Concepts CR 07/04/2026, REC au plus tôt le 05/05/2026 ; RDF 1.2 Semantics CR Draft 24/09 ; Turtle, N-Triples, TriG et N-Quads 1.2 WD 05/11 ; RDF/XML 1.2 WD 25/10 ; RDF 1.2 Schema WD 23/10 ; SPARQL 1.2 Query WD 01/11 (VERSION, LANGDIR, TRIPLE() confirmés) ; SHACL 1.0 REC 20/07/2017 ; SHACL 1.2 Core WD 02/11 ; parties 1.2 (UI 06/11, SPARQL RL 05/11, Rules et Node Expr. 28/10, SPARQL-Related 22/10, Profiling FPWD 02/07) ; nouveautés Core (`sh:values`, `sh:defaultValue`, `sh:ShapeClass`, `sh:targetWhere`, `sh:entailment`) présentes ; OWL 2 REC 11/12/2012 (2e édition) ; JSON-LD 1.1 REC 16/07/2020 ; RDF 1.1 REC 25/02/2014 ; SPARQL 1.1 REC 21/03/2013. rdflib 7.6.0 (13/02/2026), pyshacl 0.40.2 (28/10/2026 sur PyPI), owlrl 7.6.2 (08/07/2026), versions épinglées (pyproject) exactes.
skill: w3c-ontology-conformance → ajouter « une IRI relative sans @base est résolue par rdflib contre le répertoire courant du processus : toujours analyser avec un publicID sentinelle et refuser les IRI qui en héritent ». tech-watch → dater chaque WD au jour près, ne jamais regrouper des dates en plage.
```
