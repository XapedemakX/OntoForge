# Veille : état des normes et des bibliothèques

Auteur : agent `veille`. Lot L21. État vérifié en ligne le 7 nov. 2026.
Relectures faites le 7/11/2026 : expert W3C (partie 1), expert Neo4j (partie 2), expert Curiosity (partie 3), verdicts OK dans `journal/L21/review-*-it1.md`. Restent à faire : les relectures shacl et query (voir `journal/L21/rapport.md`). L'humaniseur est passé (L23).

Légende des statuts : REC = recommandation W3C (stable) ; CR = candidate à la recommandation ; WD = brouillon de travail ; Note = note non normative ; CG = rapport d'un groupe communautaire.
Légende des actions : Rien (suivre), Surveiller, Lot (ouvrir un lot), Tester (ajouter un test avant de décider).

## Décisions de Jerem du 7/11 (journal/decisions.md)

Cette fiche décrit des écarts. Les actions « Lot » et « Tester » ci-dessous sont des propositions de la veille. Trois décisions en écartent plusieurs :

- D-L21-01 : pas de veille mensuelle planifiée. La veille se fait à la demande.
- D-L21-02 : pas de montée de version, on reste sur une base stable (rdflib 7.1.1, pyshacl 0.29.1, owlrl, React 18, Vite 5). Dependabot signale ; rien n'est fusionné sans l'accord de Jerem, mises à jour de sécurité comprises.
- D-L21-03 : les fichiers Neo4j et Curiosity générés sont validés à la main par Jerem. Pas de testcontainers Neo4j ni de compilation Curiosity en CI. La CI se limite aux tests backend, au build front et aux recettes.

Effet sur les actions A1 à A8 : voir la note sous le tableau de la section 5.

## Synthèse : les cinq écarts qui comptent

1. pyshacl 0.29.1 → 0.40.2 et rdflib 7.1.1 → 7.6.0 : onze versions mineures d'écart pour pyshacl, cinq pour rdflib, sur le cœur de la validation. La 0.40 casse des choses (voir 4.1). Action proposée : lot de montée de version avec relance de `backend/tests/test_shacl_*.py`. Écartée par D-L21-02 : l'écart est suivi, pas traité.
2. RDF 1.2, SPARQL 1.2, SHACL 1.2 ne sont pas encore des recommandations. RDF 1.2 Concepts est CR depuis le 7 avril 2026 ; SPARQL 1.2 Query est un brouillon de travail du 01/11/2026 et SHACL 1.2 Core un brouillon du 02/11/2026. Ne pas coder dessus. Surveiller.
3. Neo4j a changé de cadre : versions calendaires (2026.10.0 sortie le 20 oct. 2026, suivie de 2026.10.1), Cypher 25 distinct de Cypher 5, « graph types » disponibles en version générale depuis 2026.06. Le code d'OntoForge parle encore de « Neo4j 5.x ». Action proposée : tester le DDL généré sur 5.26 (LTS) et 2026.10, avec `CYPHER 5` et `CYPHER 25`. Par D-L21-03, ce test est manuel (Jerem), sans matrice automatique.
4. Curiosity.Library n'est pas épinglé (« version à aligner »). Dernière version NuGet : 26.11.7740 du 5 nov. 2026 (corrigé par la relecture curiosity, page NuGet relue le 7/11/2026 ; la veille avait relevé 26.10.6546 du 9 oct.). Le script `tools/dotnet/check-curiosity.ps1` n'a jamais été exécuté (D-L21-03 : validation manuelle par Jerem). Les appels `AddOrUpdate`, `Link` (y compris la surcharge `Link(a, b, edgeAtoB, edgeBtoA, …)`), `CommitPendingAsync`, `CreateNodeSchemaAsync` et `CreateEdgeSchemaAsync` figurent maintenant dans la documentation du SDK, mais leurs types de retour n'y sont pas.
5. Frontend en retard de deux majeures : React 18.3.1 (dernière 19.3.1), Vite 5.4.11 (dernière 8.3.6), TypeScript 5.6.3 (dernière 7.0.2). Pas urgent, mais plus le retard grandit, plus la montée coûte. D-L21-02 : React 18 et Vite 5 restent en place.

---

## 1. Normes W3C

Source de l'état : pages `www.w3.org/TR/...` et listes de publications des groupes de travail, lues le 7/11/2026.

| Norme | Version suivie par OntoForge | Dernière publiée | Statut (date) | Écart | Fichiers touchés | Action |
|---|---|---|---|---|---|---|
| RDF Concepts | 1.1 | 1.2 | 1.1 : REC 25/02/2014 ([TR](https://www.w3.org/TR/rdf11-concepts/)). 1.2 : CR snapshot 07/04/2026 ([TR](https://www.w3.org/TR/rdf12-concepts/)) | Aucun support de 1.2 (triples imbriqués, direction de texte). Rien ne l'exige encore | `io/rdf_import.py`, `io/rdf_export.py` | Surveiller. Passage en REC attendu (la page cite « 5 mai 2026 » au plus tôt, toujours CR le 7/11) |
| RDF Semantics | 1.1 (implicite via owlrl) | 1.2 | CR (brouillon du 24/09/2026, snapshot du 07/04/2026) ([liste](https://www.w3.org/groups/wg/rdf-star/publications/)) | Aucun | `conformance/reasoner.py` | Surveiller |
| Turtle / N-Triples / TriG / N-Quads / RDF-XML | 1.1 (rdflib) | 1.2 | WD (5/11/2026 pour Turtle, N-Triples, TriG, N-Quads ; 25/10/2026 pour RDF/XML) | Aucun. Syntaxes `<<( )>>` et `{| |}` non gérées | `io/rdf_import.py` | Surveiller |
| RDF-star | Non géré par le code de conversion. Seul `localstore/_worker.py` (L19) rend un triplet cité en texte dans les résultats de requête | Remplacé par RDF 1.2 | Rapport de groupe communautaire ; Oxigraph a retiré `rdf-star` « in favor of RDF 1.2 » ([changelog](https://raw.githubusercontent.com/oxigraph/oxigraph/main/CHANGELOG.md)). RDF 1.2 n'accepte plus les triples imbriqués en position de sujet (même source) | Aucun | — | Ne pas coder RDF-star. Si besoin d'annotations d'arêtes (P-29), viser RDF 1.2 |
| SPARQL Query | 1.1 (rdflib) | 1.2 | 1.1 : REC 21/03/2013 ([TR](https://www.w3.org/TR/sparql11-query/)). 1.2 : WD 01/11/2026 ([TR](https://www.w3.org/TR/sparql12-query/)) | Nouveautés 1.2 : triples imbriqués, `VERSION`, `LANGDIR`, `TRIPLE()`. Aucune n'est nécessaire à OntoForge | `queries/endpoint.py` (envoi aux points d'accès), `queries/` | Rien. Tests W3C SPARQL 1.2 en suivi (voir processus) |
| SPARQL Update, Protocol, Graph Store, Results | 1.1 | 1.2 | WD : Update 25/10/2026, Protocol 23/07/2026, Graph Store 24/09/2026, Results JSON 13/08/2026, CSV/TSV 22/10/2026, XML 27/12/2024 (corrigé par la relecture w3c) | OntoForge lit seulement (lecture seule) | `queries/endpoint.py` | Rien |
| SHACL | 1.0 (pyshacl) | 1.2 | 1.0 : REC 20/07/2017 ([TR](https://www.w3.org/TR/shacl/)). 1.2 Core : WD 02/11/2026 ([TR](https://www.w3.org/TR/shacl12-core/)) | Voir ci-dessous | `shacl/import_shapes.py`, `shacl/export_shapes.py`, `shacl/validate.py`, `shacl/shacl_to_pg.py`, `shacl/owl_to_shacl.py`, `core/shapes_model.py` | Surveiller, ne pas coder avant CR |
| SHACL 1.2 : parties | — | — | Core WD 02/11/2026 ; SPARQL-Related Features WD 22/10 ; Node Expressions WD 28/10 ; Inference Rules WD 28/10 ; User Interfaces WD 06/11 ; SPARQL 1.2 RL WD 05/11 ; Profiling WD (première publication) 02/07/2026 ([liste du groupe](https://www.w3.org/groups/wg/data-shapes/publications/)) | Nouveautés relevées dans Core : `sh:values`, `sh:defaultValue`, `sh:ShapeClass`, `sh:targetWhere`, `sh:entailment`, `sh:severity` et `sh:message` sur réificateurs ([Core §3](https://www.w3.org/TR/shacl12-core/)) | Aucun fichier ne les lit | Surveiller. `sh:ShapeClass` et `sh:values` toucheraient `import_shapes.py` |
| SHACL 1.0 : Advanced Features, JS | — | — | Notes de 2017 | pyshacl implémente SHACL-AF (règles, fonctions) | — | Rien |
| OWL 2 | OWL 2 DL, profils EL/QL/RL | OWL 2 (2e édition) | REC 11/12/2012, « stable document » ([TR](https://www.w3.org/TR/owl2-overview/)) | Aucun. Aucun travail OWL 3 annoncé dans le document | `conformance/*`, `io/*`, `mapping/*` | Rien |
| JSON-LD | 1.1 (rdflib) | 1.1 | REC 16/07/2020 ([groupe](https://www.w3.org/groups/wg/json-ld/publications/)) | Aucun. Pas de brouillon 1.2 listé. YAML-LD 1.0 et CBOR-LD 1.0 sont des WD | `io/rdf_import.py` (`.jsonld`) | Rien |
| RDFS | 1.1 | 1.2 | 1.2 Schema : WD 23/10/2026 | Aucun | `conformance/*` | Surveiller |

### À savoir sur SHACL 1.2

- La Core 1.2 reste un brouillon de travail : « inappropriate to cite » autrement ([TR](https://www.w3.org/TR/shacl12-core/)). Sa dernière version date du 02/11/2026, soit cinq jours avant cette veille.
- pyshacl (la bibliothèque qu'OntoForge utilise) ne se présente pas comme une implémentation de SHACL 1.2 : son journal parle de SHACL-AF 2017, d'« Expressions », de règles et de fonctions ([changelog](https://raw.githubusercontent.com/RDFLib/pySHACL/master/CHANGELOG.md)). Pas de preuve contraire lue.
- La suite de tests W3C existe déjà pour 1.2 : dossier `shacl12-test-suite/tests` dans `w3c/data-shapes` (sous-dossiers `sparql-rl`, etc.). C'est le moyen de savoir quand une bibliothèque rattrape la norme.

## 2. Neo4j et Cypher

Source de l'état : [notes de version 2026.10](https://neo4j.com/release-notes/database/neo4j-2026-10/), [Cypher 25 : ajouts, dépréciations](https://neo4j.com/docs/cypher-manual/25/deprecations-additions-removals-compatibility/), [versions prises en charge](https://support.neo4j.com/s/article/115013134648-Neo4j-Supported-Versions), [manuel des opérations](https://neo4j.com/docs/operations-manual/current/introduction/). La page du manuel sur les contraintes interdit la lecture automatique (robots) : la syntaxe des contraintes n'est donc pas revérifiée aujourd'hui sur cette page.

| Élément | Version suivie par OntoForge | Dernière publiée | Statut | Écart | Fichiers touchés | Action |
|---|---|---|---|---|---|---|
| Serveur | « 5.7+ » (Community), « 5.11+ » (Enterprise) dans l'en-tête de `schema.cypher` ; `CALL (row) { … }` « 5.23+ » | 2026.10.1 (date non affichée sur la page de notes de version, relue le 7/11 : À VÉRIFIER), 2026.10.0 le 20/10/2026 | Seule 5.26 (déc. 2024) est LTS avec correctifs jusqu'au 6/06/2028. 2026.10.1 : pas LTS, correctifs jusqu'à 2026.11. 4.4 hors support depuis 11/2025 | Numérotation calendaire depuis 2025 (`ANNÉE.MOIS.patch`). Le texte généré ne cite que « Neo4j 5 » | `targets/neo4j.py` (l. 309, 339, 610, 693), `docs/` | Lot : actualiser les en-têtes et le README généré. Tester 5.26 et 2026.10 |
| Langage | Cypher 5 (implicite) | Cypher 25 | Cypher 5 gelé (correctifs seulement). Cypher 25 reçoit toutes les nouveautés depuis 2025.06. À partir de 2026.02, le `neo4j.conf` fourni met Cypher 25 par défaut ; les nouvelles bases le fixent explicitement | Un script sans préfixe peut changer de version selon la base | `targets/neo4j.py` | Tester : exécuter `schema.cypher` et `ingest.cypher` avec `CYPHER 5` puis `CYPHER 25`. Le préfixe `CYPHER 25` ne vaut que pour la requête qu'il précède (manuel des opérations, « Configure the Cypher default version ») : il faut le répéter devant chaque instruction, ou fixer le défaut de la base (`db.query.default_language`, ou langage par défaut de la base) ; une seule ligne en tête de fichier ne suffit pas (corrigé par la relecture neo4j) |
| Contraintes (syntaxe `CREATE CONSTRAINT … REQUIRE … IS UNIQUE / IS NODE KEY / IS NOT NULL / IS :: type`) | Forme utilisée aux lignes 225 à 271 de `targets/neo4j.py` | Inchangée dans les notes lues | Aucune dépréciation de cette forme dans les entrées 2025.06 à 2026.07 de la page des ajouts | Seule dépréciation proche : l'option `indexProvider` supprimée en Cypher 25 (2025.06). OntoForge n'écrit pas `indexProvider` (recherche faite, aucune occurrence) | `targets/neo4j.py` | Rien. Tester (voir tests de matrice) |
| Nouvelles contraintes de schéma | Absentes | `NODE_LABEL_EXISTENCE`, `RELATIONSHIP_SOURCE_LABEL`, `RELATIONSHIP_TARGET_LABEL` (2026.02, via `ALTER CURRENT GRAPH TYPE SET`, en aperçu à l'époque) | « Graph types » en disponibilité générale depuis 2026.06 (set, alter, extend, drop, show) | OntoForge ne génère pas de graph type. C'est l'équivalent Neo4j de PG-Schema | `targets/neo4j.py` | Lot (idée P-20) : option de génération en graph type, à valider par l'expert Neo4j |
| Types de propriétés | `IS :: <TYPE>` pour les types scalaires et listes | Ajout de VECTOR (2025.10), contraintes `IS :: VECTOR<…>` | VECTOR stockable en Enterprise ou Aura seulement ([types](https://neo4j.com/docs/cypher-manual/current/values-and-types/property-structural-constructed/)) | `PGType` (`core/pg_model.py`) n'a pas de vecteur | `core/pg_model.py`, `targets/neo4j.py` | Surveiller. Utile si un client veut des plongements |
| Index vectoriel | Non généré | `SEARCH` (2026.01), quantification binaire hors aperçu en 2026.07 | `db.index.vector.queryNodes()` et `queryRelationships()` dépréciées (2026.04) | Sans effet : OntoForge n'appelle pas ces procédures | — | Rien |
| Nouveautés de syntaxe | — | `FOR … IN`, `IS [NOT] LABELED` (2026.04), `GROUP BY` dans `WITH`/`RETURN` (2026.07), addition de maps (2026.10) | Cypher 25 | Aucune obligation | `targets/neo4j.py` (requêtes générées) | Rien |
| GQL ISO/IEC 39075 | Aucun export GQL | Édition 2024 | La page de conformité de Cypher 25 couvre Neo4j 2025.08, mise à jour le 02/09/2025 ([page](https://neo4j.com/docs/cypher-manual/25/appendix/gql-conformance/)) : « a few mandatory features » encore absentes | La page de conformité a plus d'un an de retard sur le serveur | — | Surveiller. Idée P-20 (PG-Schema / GQL) |
| neosemantics (n10s) | Non utilisé | Étiquette `2025.06.1` (dépôt) | Projet Neo4j Labs, « experimental … not part of Neo4j's supported product lineup », Apache 2.0, absent d'Aura ([labs](https://neo4j.com/labs/neosemantics/)) | — | — | Rien. Voir comparaison dans `neonto.md` |

## 3. Curiosity

Source de l'état : [NuGet Curiosity.Library](https://www.nuget.org/packages/Curiosity.Library), [SDK C#](https://docs.curiosity.ai/workspace-api/sdk-csharp), [schémas de connecteur](https://docs.curiosity.ai/workspace-customization/data-connector/schemas), [bilan d'octobre 2026](https://blog.curiosity.ai/blog/2026-10-release-overview).

| Élément | Version suivie par OntoForge | Dernière publiée | Statut | Écart | Fichiers touchés | Action |
|---|---|---|---|---|---|---|
| Package NuGet `Curiosity.Library` | Aucune : « version à aligner sur l'espace de travail » (`targets/curiosity.py` l. 56, 857) | 26.11.7740 (05/11/2026). Cibles : netstandard2.1, net6.0 à net11.0. Titulaire : Curiosity GmbH. Licence non affichée | Rythme très élevé : 20 versions entre le 24/09 et le 05/11/2026 (dont plusieurs le même jour) | Schéma de version « année.mois.build ». Le script de contrôle crée un projet .NET 8 | `targets/curiosity.py`, `tools/dotnet/check-curiosity.ps1`, `tools/dotnet/README.md` | Tester : exécuter `check-curiosity.ps1 -Version 26.11.7740`. Épingler la version dans le README généré |
| Attributs `[Node]`, `[Key]`, `[Property]` | Utilisés par le code généré | Confirmés dans la doc des schémas, plus `[Timestamp]` (exemple : un champ `DateTimeOffset`) | Documentés | `[Timestamp]` déjà généré : au plus un par type, premier `DateTime` scalaire obligatoire sinon premier (`targets/curiosity.py` l. 262-266) ; la règle « au plus un » n'est pas écrite dans la page lue | `targets/curiosity.py` | Rien (corrigé par la relecture curiosity : la veille le disait non généré) |
| `CreateNodeSchemaAsync<T>()`, `CreateEdgeSchemaAsync(typeof(Edges))` | Utilisés (l. 470-471) | Confirmés dans la liste des méthodes du SDK | Documentés | — | `targets/curiosity.py` | Rien |
| `AddOrUpdate`, `Link`, `CommitPendingAsync` | Utilisés (l. 752, 776, 804), marqués À VÉRIFIER pour le type de retour | Confirmés ; la page du SDK donne `Link(from, to, edgeType, unique=true, ignoreMissingNodes=false, edgeTimestamp=null)` et la surcharge `Link(a, b, edgeAtoB, edgeBtoA, …)`, ce qui confirme l'ordre (source, cible, aller, retour) généré. Types de retour non donnés | Documentés | Reste du À VÉRIFIER : type de retour `Node` de `AddOrUpdate` ; paramètre `overwrite` de `CreateNodeSchemaAsync<T>(overwrite)` (OntoForge l'appelle sans argument : valeur par défaut À VÉRIFIER) | `targets/curiosity.py` | Tester par compilation |
| Fabrique `Schema` et `FieldType` | Non utilisée | Présentes dans l'espace de noms `Curiosity.Library` | Documentées ([espace de noms](https://docs.curiosity.ai/workspace-api/curiosity-library/)) | Voie alternative, sans attributs | — | Surveiller |
| Notes de version de l'espace de travail | — | Bilans mensuels (build `26.10.72149` à `26.10.72602` en octobre) | Octobre : retrait de moteurs OCR, migration des fournisseurs OpenAI, réponses d'API en `Cache-Control: no-store`. Rien sur la bibliothèque, les schémas ou les connecteurs | Le bilan renvoie au journal des modifications pour ces sujets, que je n'ai pas lu | — | Surveiller ; lire le journal des modifications lors de la veille mensuelle |
| Page « release notes » du manuel | — | Affiche « 2.5.0 (Latest) » sans date | Douteuse : incohérente avec le rythme 26.x | — | — | Ne pas s'y fier |

Point de prudence : la compatibilité entre la version du paquet NuGet et celle du serveur Curiosity n'est écrite nulle part dans les pages lues (la page du SDK dit : version « not stated »). À demander à Curiosity ou à vérifier sur l'espace de travail de Jerem.

## 4. Bibliothèques du projet

Versions suivies : `backend/pyproject.toml` et `frontend/package.json`. D-L21-02 : les colonnes « Action » `Lot` et `Tester` de cette partie sont des propositions écartées pour l'instant ; Dependabot signale seulement. Dernières versions : PyPI et registre npm, interrogés le 7/11/2026. La colonne « Écart » compte les majeures et mineures d'avance.

### 4.1 Python (backend)

| Bibliothèque | Suivie | Dernière (date) | Écart | Remarque | Fichiers | Action |
|---|---|---|---|---|---|---|
| rdflib | 7.1.1 | 7.6.0 (13/02/2026) | 5 mineures | 7.3 a déprécié des méthodes de `Dataset` (`default_context`, `contexts()`). 7.5 et 7.6 ajoutent des clients RDF4J et GraphDB, sans rapport. Pas de support RDF 1.2 annoncé dans le journal lu ([changelog](https://raw.githubusercontent.com/RDFLib/rdflib/main/CHANGELOG.md)) | `io/*`, `shacl/*`, `conformance/*`, `queries/*`, `editing/files.py` | Lot : montée groupée avec pyshacl et owlrl |
| pyshacl | 0.29.1 | 0.40.2 (28/10/2026 sur PyPI ; 28/07/2026 d'après le journal) | 11 mineures | 0.40.0 est cassante : suppression de `ConjunctiveGraph` ; exige `rdflib>=7.3,<8` et `owlrl>=7.6.1` ; `validate_each()` change de clé. Nouveau : extra `pyshacl[oxigraph]` ([changelog](https://raw.githubusercontent.com/RDFLib/pySHACL/master/CHANGELOG.md)). Recherche faite : OntoForge n'utilise pas `ConjunctiveGraph` | `shacl/validate.py`, `editing/files.py` | Lot (avec rdflib) |
| owlrl | 7.1.2 | 7.6.2 (08/07/2026) | 5 mineures | Utilisé pour la fermeture OWL 2 RL | `conformance/reasoner.py` | Lot (avec rdflib) |
| pyoxigraph | 0.5.13 (ajouté par L19, `backend/pyproject.toml`) | 0.5.13 (22/10/2026) | 0 | Magasin RDF en Rust, moteur du triplestore local. Le support RDF 1.2 et SPARQL 1.2 est derrière des options de compilation (`rdf-12`, `sparql-12`) d'après son journal | `localstore/*` | Rien. Voir `triplestore-embarque.md` |
| pypdf | 7.0.0 (ajouté par L25) | Non relevée | — | Lecture des PDF du brouillon depuis un document | `assistant/document.py` | Dependabot |
| owlready2 (extra `reasoner`) | 0.47 | 0.51 (22/06/2026) | 4 mineures | Pilote HermiT | `conformance/reasoner.py` | Tester |
| fastapi | 0.115.6 | 0.162.2 (07/11/2026) | 47 mineures (0.x) | Écart important mais l'API publique d'OntoForge est mince | `api/*`, `main.py` | Dependabot |
| uvicorn | 0.32.1 | 0.54.0 (25/09/2026) | — | — | — | Dependabot |
| pydantic | 2.10.3 | 2.14.3 (05/11/2026) | 4 mineures | Même majeure | `core/*` | Dependabot |
| httpx | 0.28.1 | 0.28.1 (06/12/2024) | 0 | À jour | `queries/endpoint.py`, `assistant/providers/*` | Rien |
| python-multipart | 0.0.19 | 0.0.33 (31/10/2026) | — | Dépendance de téléversement de fichiers | `api/*` | Dependabot |
| pyyaml | 6.0.2 | 6.0.3 | 0 majeure | — | — | Dependabot |
| cryptography | 50.0.2 | 50.0.2 (30/09/2026) | 0 | À jour | `settings/*` | Rien |
| pytest (dev) | 8.3.4 | 9.2.0 (27/10/2026) | 1 majeure | — | `backend/tests/` | Dependabot |
| graphql-core (dev) | 3.2.5 | 3.3.2 (06/11/2026) | 1 mineure | — | `tests/test_graphql.py` | Dependabot |
| testcontainers (dev) | Non ajouté | 4.15.0 (24/07/2026) | — | Aurait servi à la matrice Neo4j | — | Écarté par D-L21-03 |
| Python (image) | 3.12-slim | — | — | `requires-python >=3.11`. pyshacl 0.40 garde 3.9 | `backend/Dockerfile` | Rien |

### 4.2 JavaScript (frontend)

| Bibliothèque | Suivie | Dernière | Écart | Remarque | Fichiers | Action |
|---|---|---|---|---|---|---|
| react, react-dom | 18.3.1 | 19.3.1 | 1 majeure | Les types suivent (`@types/react` 18.3.12 → 19.3.0) | `frontend/src/**` | Lot dédié, à planifier hors période de livraison |
| @xyflow/react | 12.8.4 | 12.12.1 | 4 mineures | Même majeure. Utilisé dans l'éditeur graphique | `screens/editor/Editor.tsx`, `screens/editor/parts.tsx` | Dependabot |
| @dagrejs/dagre | 1.1.5 | 3.1.3 | 2 majeures | Disposition automatique | `screens/editor/layout.ts` | Tester avant de monter |
| cytoscape | 3.30.2 | 3.34.4 | 4 mineures | Diagramme du modèle | `screens/Model.tsx` | Dependabot |
| marked | 18.1.1 | 18.1.3 | 2 correctifs | — | — | Dependabot |
| vite | 5.4.11 | 8.3.6 | 3 majeures | Compilation | `frontend/vite.config.ts` | Lot dédié |
| typescript | 5.6.3 | 7.0.2 | 1 majeure | — | `frontend/tsconfig.json` | Lot dédié |
| @vitejs/plugin-react | 4.3.4 | 6.2.1 | 2 majeures | Va avec Vite | — | Avec Vite |
| @codemirror/* | 6.43.14 (view) | 6.43.15 | 1 correctif | Éditeur de code | `CodeEditor.tsx` | Dependabot |
| @fortawesome/fontawesome-free | 7.3.1 | 7.3.1 | 0 | À jour | — | Rien |
| Images Docker | `node:22-alpine`, `nginx:1.27-alpine` | non vérifié | — | Je n'ai pas interrogé les registres d'images | `frontend/Dockerfile` | Dependabot (écosystème `docker`) |

---

## 5. Actions proposées, par ordre

| # | Action | Type | Gain | Effort | Relecteur |
|---|---|---|---|---|---|
| A1 | Monter rdflib, pyshacl, owlrl ensemble, relancer toute la suite | Lot | 4 | S | w3c, shacl |
| A2 | Exécuter `check-curiosity.ps1` sur 26.11.7740 (dernière au 7/11), lever les À VÉRIFIER | Test | 5 | S | curiosity |
| A3 | Tester le DDL sur Neo4j 5.26 et 2026.10, `CYPHER 5` et `CYPHER 25` | Test | 5 | M | neo4j |
| A4 | Actualiser les en-têtes « Neo4j 5.x » et épingler Curiosity.Library dans les sorties | Lot | 3 | S | neo4j, curiosity |
| A5 | Brancher les suites de tests W3C (voir `processus-mise-a-jour.md`) | Lot | 4 | M | w3c, query |
| A6 | Option « graph type » dans la cible Neo4j (P-20) | Lot | 3 | M | neo4j |
| A7 | Montée React 19, Vite 8, TypeScript 7 | Lot | 2 | L | scout |
| A8 | Surveiller RDF 1.2 (passage REC), SHACL 1.2 (passage CR) | Veille | 3 | S | w3c |

Suite donnée aux actions par les décisions du 7/11 :

| Action | Suite |
|---|---|
| A1, A7 | Écartées (D-L21-02) : pas de montée de version |
| A2, A3 | Manuelles (D-L21-03) : Jerem importe les fichiers générés dans Curiosity et Neo4j, `check-curiosity.ps1` reste un outil local |
| A5 | Suites W3C hors CI pour l'instant (D-L21-03 limite la CI aux tests backend, au build front et aux recettes) ; à rouvrir par une décision |
| A4, A6, A8 | Non concernées par les décisions |

## 6. Limites de cette vérification

- Je n'ai pas lu les publications de chaque spécification en entier : le statut et la date viennent de l'en-tête de chaque document et des listes de publications des groupes.
- Le statut CR de RDF 1.2 Concepts date du 7/04/2026. Je n'ai pas trouvé de recommandation publiée depuis. Un lecteur humain peut le confirmer sur [w3.org/TR/rdf12-concepts](https://www.w3.org/TR/rdf12-concepts/).
- Dates PyPI et npm : celles du paquet à l'instant de la requête. La date de pyshacl 0.40.2 diffère entre PyPI (28/10/2026) et son journal (28/07/2026) ; je garde les deux.
- Manuel Cypher, page des contraintes : lecture bloquée (robots). Syntaxe des contraintes non recontrôlée en ligne aujourd'hui.
- NuGet : l'API JSON a été refusée par notre proxy ; les versions viennent de la page web du paquet.
- Pas de relevé des versions d'images Docker, ni de `Protégé` au-delà de la liste des étiquettes.
- Aucun test n'a été exécuté. Ce document décrit des écarts, il ne prouve pas qu'ils cassent quelque chose.

## 7. Sources principales

W3C : [RDF 1.2 Concepts](https://www.w3.org/TR/rdf12-concepts/) · [SPARQL 1.2 Query](https://www.w3.org/TR/sparql12-query/) · [SHACL 1.2 Core](https://www.w3.org/TR/shacl12-core/) · [SHACL 1.2 SPARQL](https://www.w3.org/TR/shacl12-sparql/) · [SHACL 1.2 Node Expressions](https://www.w3.org/TR/shacl12-node-expr/) · [OWL 2](https://www.w3.org/TR/owl2-overview/) · [RDF 1.1](https://www.w3.org/TR/rdf11-concepts/) · [SPARQL 1.1](https://www.w3.org/TR/sparql11-query/) · [groupe RDF & SPARQL](https://www.w3.org/groups/wg/rdf-star/publications/) · [groupe Data Shapes](https://www.w3.org/groups/wg/data-shapes/publications/) · [groupe JSON-LD](https://www.w3.org/groups/wg/json-ld/publications/)
Neo4j : liens de la partie 2. Curiosity : liens de la partie 3.
Bibliothèques : PyPI (`https://pypi.org/pypi/<paquet>/json`), npm (`https://registry.npmjs.org/<paquet>/latest`), journaux [rdflib](https://raw.githubusercontent.com/RDFLib/rdflib/main/CHANGELOG.md), [pySHACL](https://raw.githubusercontent.com/RDFLib/pySHACL/master/CHANGELOG.md), [Oxigraph](https://raw.githubusercontent.com/oxigraph/oxigraph/main/CHANGELOG.md).
