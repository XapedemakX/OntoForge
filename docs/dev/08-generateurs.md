# 08. Générateurs {#generateurs}

Les générateurs transforment un `PGModel` (chapitre [07](07-moteur-analyse.md)) en fichiers prêts à l'emploi : code C# Curiosity, scripts Cypher Neo4j, schéma GraphQL, rapport de transposition et dossier de justification. Ils ne relisent jamais l'ontologie pour décider : toutes les décisions sont déjà dans le `PGModel`. L'ontologie n'est passée que pour des libellés et des détails d'affichage.

Sources lues : `backend/ontoforge/targets/curiosity.py`, `backend/ontoforge/targets/neo4j.py`, `backend/ontoforge/targets/graphql.py`, `backend/ontoforge/targets/report.py`, `backend/ontoforge/targets/justification.py`, `backend/ontoforge/localize/gen.py`, `backend/ontoforge/standards/__init__.py`, `backend/ontoforge/projects/generations.py`, `backend/ontoforge/api/analysis.py`, `tools/dotnet/README.md`. Génération exécutée sur `samples/automaint/automaint.ttl` pour les deux cibles.

## Rôle et contrat {#contrat}

Chaque générateur de cible expose `generate(pg, onto=None, lang=None) -> dict[str, str]` (nom de fichier → contenu, D-028 qui remplace D-017). La sortie est déterministe (tri par nom ou par id), donc les tests n'ont pas besoin de fichiers de référence (D-038).

| Module | Fichiers produits |
|---|---|
| `backend/ontoforge/targets/curiosity.py::generate` | `Schema.cs`, `Edges.cs`, `RegisterSchema.cs`, `Connector.cs`, `README-curiosity.md` |
| `backend/ontoforge/targets/neo4j.py::generate` | `schema.cypher`, `ingest.cypher`, `validation.cypher`, `model.mmd` (Mermaid), `README-neo4j.md` |
| `backend/ontoforge/targets/graphql.py::generate` | `schema.graphql`, `README-graphql.md` (pour les deux cibles) |
| `backend/ontoforge/targets/report.py::generate` | `rapport-transposition.md` (pour les deux cibles) |
| `backend/ontoforge/targets/justification.py::generate` | dossier de justification, HTML autonome ou Markdown (route à part) |

## Flux {#flux}

```mermaid
sequenceDiagram
  participant F as Front
  participant A as api/analysis.py
  participant E as run_analysis
  participant G as targets/<cible>, graphql, report
  participant H as projects/generations.py
  F->>A: GET /generate/{target}?perimeter=&lang=
  A->>A: _gen_lang (fr|en, sinon langue de l'interface ; 422 si inconnue)
  A->>E: PGModel (décisions rejouées)
  A->>A: lang=en → localize_pg_for_export (textes du moteur traduits)
  loop targets.{target}, targets.graphql, targets.report
    A->>G: with gen.using_lang(gl) : generate(pg, onto)
    G-->>A: {nom: contenu}
  end
  A->>H: append(GenerationRecord) sous verrou → generations.json
  A-->>F: {files, missing}
```

- `backend/ontoforge/api/analysis.py::_generate` résout chaque module avec `optional_service` : un module absent est listé dans `missing` ; si les trois manquent, 501.
- `GET /generate/{target}/zip` produit la même chose en archive (`<pid>-<target>/<fichier>`), sans entrée d'historique.
- Droits : la génération et son zip sont classés en **écriture** (éditeur, propriétaire) depuis D-L42-01 : le lecteur ne génère pas. La route reste un `GET` ; le jeton CSRF est exigé (chapitre [12](12-comptes-partage-admin.md)).
- Historique : `backend/ontoforge/projects/generations.py` tient `generations.json` à côté du projet (50 entrées au plus, `MAX_GENERATIONS`), sous un verrou, en remplacement atomique. Depuis L41, une génération n'écrit plus jamais `project.json` (avant, elle pouvait écraser une modification concurrente). `GET /generations` le lit, le plus récent d'abord.

## Langue des fichiers {#langue}

`backend/ontoforge/localize/gen.py` porte la variable de contexte `GEN_LANG`. Les générateurs écrivent leurs textes (commentaires, en-têtes, README, rapport) par `T(fr, en)` ; `using_lang(lang)` fixe la langue pendant un appel. Les identifiants (types, arêtes, propriétés) et les libellés de l'ontologie sont des données et ne passent jamais par `T`. Hors API, la langue est `fr`.

## Versions des cibles {#versions}

Les en-têtes et le rapport affichent les versions utilisées, prises dans `PGMeta.target_versions` (posées par `run_analysis` depuis `backend/ontoforge/standards/__init__.py::for_project` : valeurs d'usine de `standards.json` < défaut global des paramètres < valeurs du projet). État du 23/11 : Neo4j 5.26, Cypher 5, Curiosity.Library 26.11.7740, SHACL 1.0, SPARQL 1.1, RDF 1.1 (`standards.json` du 08/11). Le générateur Neo4j adapte sa syntaxe à la version par `standards.neo4j_caps` (ancienne forme `ASSERT`, contraintes de type, d'unicité de relation…) et peut préfixer les requêtes par `CYPHER n` (`cypher_prefix`).

## Curiosity {#curiosity}

`backend/ontoforge/targets/curiosity.py` : un plan intermédiaire (`_Plan`) calcule les noms C# (identifiants échappés par `@` pour les mots réservés, `cs_ident`, collision avec les classes générées `GENERATED_CLASSES` résolue en ajoutant `Node`), les noms d'arêtes uniques, les types abstraits ignorés. Puis un rendu par fichier : `Schema.cs` (classes `[Node]` avec `[Key]`, `[Property]`), `Edges.cs` (constantes de paires aller / retour), `RegisterSchema.cs`, `Connector.cs` (squelette d'ingestion avec les validations, code de sortie 2 sur violation), `README-curiosity.md`.

Les appels à l'API Curiosity.Library qui n'ont pas été confirmés dans une documentation lue sont listés dans `TO_VERIFY` (et `TO_VERIFY_EN`) et portent `// À VÉRIFIER` dans le code : type de retour de `Graph.Connect`, valeur de retour de `AddOrUpdate` / `TryAdd`, `Link` symétrique, tableaux `T[]`, alignement du paquet NuGet sur le serveur… Sur `automaint`, les fichiers générés contiennent 36 occurrences de `À VÉRIFIER`.

La compilation réelle n'est pas faite en CI (D-L21-03) : `tools/dotnet/check-curiosity.ps1` (Windows, SDK .NET 8, accès nuget.org) compile un export zip contre le vrai paquet `Curiosity.Library` et liste les erreurs, qui servent à lever les `À VÉRIFIER`.

## Neo4j {#neo4j}

`backend/ontoforge/targets/neo4j.py` : un modèle intermédiaire `_Model` (versions, capacités, préfixe Cypher), puis `schema.cypher` (contraintes d'unicité, de clé, d'existence, de type, index ; ce qui demande l'édition Enterprise est commenté), `ingest.cypher` (modèles `MERGE` par type et par relation, conversions de type par `PG_TO_CYPHER_CAST` du profil), `validation.cypher` (une requête de détection par `Validation`, `_validation`), les matérialisations (`_materialization` : fermeture transitive, chaîne, super-propriété…), `model.mmd` et le README. `quote` échappe un identifiant par accents graves s'il n'est pas un identifiant simple ou s'il est réservé (`_RESERVED`) ; `literal` écrit une valeur Cypher. La propriété IRI est retrouvée par le marqueur `IRI_MARKER` (`urn:ontoforge:iri`, D-L4-02), jamais par son nom.

La validation réelle se fait par import manuel dans Neo4j (D-L21-03) ; pas de testcontainers.

## GraphQL {#graphql}

`backend/ontoforge/targets/graphql.py` : un type objet par `NodeType`, scalaires (`SCALAR_MAP`, scalaires personnalisés `Date`, `DateTime`, `Decimal`…), listes, non-null pour `required`, enums pour les propriétés à valeurs énumérées ; héritage aplati → `interface` + types concrets ; relations dans les deux sens (champ retour nommé d'après `reverse`) ; pour Neo4j, directives `@relationship` de la Neo4j GraphQL Library (`À VÉRIFIER` dans le code) ; `type Query` avec recherche par clé et liste paginée.

## Rapport de transposition {#rapport}

`backend/ontoforge/targets/report.py` écrit `rapport-transposition.md` : synthèse chiffrée, rappel unique de l'hypothèse de monde clos, nœuds, relations, ce qui est perdu ou à risque (option retenue, ou recommandée marquée « non arbitré », impact, compensation), ce qui est transposé automatiquement, validations à implémenter, matérialisations, constats non transposés, versions (`_versions_section`).

## Dossier de justification {#justification}

`backend/ontoforge/targets/justification.py` (L47) produit un document pour un client ou un relecteur : modèle retenu, perdu, compensé, décisions humaines (qui, quand, pourquoi, via `PGModel.decision_notes`), recommandations non suivies, reste à arbitrer, reclassements en `auto`. Un seul plan (`build_blocks`) est rendu deux fois (`render_md`, `render_html`). Tout texte venant de l'ontologie, d'un compte ou d'une raison saisie est **échappé** (`html.escape` ; caractères Markdown neutralisés par `_md`). Le HTML n'a ni script, ni ressource distante, ni gestionnaire d'événement, et la route lui ajoute l'en-tête `Content-Security-Policy` du module (`CSP`) et `X-Content-Type-Options: nosniff`.

Route : `GET /justification/{target}?format=html|md&lang=` ; lecture seule (accessible au lecteur), n'écrit ni projet ni historique.

## Librairies {#librairies}

Aucune dépendance : les générateurs sont du Python pur qui écrit du texte. Les versions de syntaxe viennent de `backend/ontoforge/standards/standards.json`.

## Décisions {#decisions}

- D-005 : Curiosity est la cible prioritaire.
- D-028 : contrat `generate(pg, onto) -> dict[str, str]`.
- D-038 : pas de fichiers de référence (golden) ; déterminisme, invariants et formes autorisées.
- D-L4-02 : propriété IRI par marqueur, clé de repli.
- D-L13-01 : `Decimal` (C# `decimal`, scalaire GraphQL `Decimal`, Neo4j `Float` avec perte signalée).
- D-L21-03 : validation Neo4j et Curiosity manuelle.
- D-L42-01, D-L42-02 : génération réservée à l'éditeur et au propriétaire, zip compris.
- D-L47-02 : dossier de justification et trace des décisions.

## Pièges et limites {#pieges}

- Code non compilé en CI : le C# généré peut ne pas compiler contre une version de Curiosity.Library ; les `À VÉRIFIER` sont la liste des risques connus.
- Édition Neo4j : les contraintes d'existence et de type demandent Enterprise ; elles sont émises commentées, à décommenter.
- `onto` facultatif : un générateur doit fonctionner avec `onto=None` (contrat) ; ce qui en dépend (sous-types GraphQL, libellés du rapport) doit avoir un repli.
- Traduction : en `lang=en`, les textes du moteur sont traduits par `localize_pg_for_export` ; un texte sans traduction reste en français dans un fichier anglais.

## Comment ajouter une cible ou un fichier {#comment-ajouter}

**…un fichier à une cible existante.** Ajouter une fonction de rendu dans le module et la clé dans le dictionnaire renvoyé par `generate` ; garder un ordre déterministe ; textes par `T(fr, en)` ; tests de forme et de déterminisme dans `backend/tests/test_target_<cible>.py`.

**…une nouvelle cible** (exemple : Memgraph). Un générateur ne suffit pas : `Target` est un `Literal` de `backend/ontoforge/core/pg_model.py` (contrat normatif, décision tracée), le moteur a besoin d'un profil `backend/ontoforge/mapping/profiles/<cible>.py` et de son adaptateur dans `profile_api.py`, le catalogue de règles a des recommandations par cible (`reco`), `TARGETS` de `backend/ontoforge/api/_common.py` liste les cibles acceptées, `Project.decisions` a une clé par cible, et le front a ses propres listes. Le générateur `targets/<cible>.py` est trouvé par son nom (`targets.{target}`).
