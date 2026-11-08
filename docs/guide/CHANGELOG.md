# Journal des versions

Format : par version, ce qui change pour l'utilisateur, puis le détail par lot. Sources : rapports `journal/L*/rapport*.md`, revues, `journal/decisions.md`. Les lots sont décrits dans `lots/`.

## 0.1.0 : Itération 1 (livraison prévue le mardi 3 novembre 2026, ~19 h, Paris, D-022)

> Statut au premier passage de L12 : la recette chez Jerem (`docker compose up --build`, lot L7) n'a pas encore eu lieu et aucun lot n'a de fichier `cloture.md`. Cette version reflète l'état du dépôt le 3 novembre 2026 au soir.

### Nouveautés

- Concevoir : projets (vides, depuis les exemples `automaint` et `trap`, ou par dépôt de fichier) ; éditeur d'ontologie façon Protégé ; Saisie rapide (DSL, une ligne = un axiome) ; import Turtle, RDF/XML, JSON-LD, N-Triples, N3, TriG ; export Turtle, RDF/XML, JSON-LD, N-Triples, N3.
- Vérifier : conformité OWL 2 DL / EL / QL / RL avec références de spécification (W01 à W07) et bonnes pratiques (BP01 à BP07).
- SHACL : import, génération depuis l'ontologie, validation d'un fichier de données (sans inférence par défaut).
- Transposer : moteur de 66 règles (+ S01, S02, G02) avec constats *auto / à arbitrer / perdus*, options par cible, recommandation par cible, décisions mémorisées et rejouées, décisions groupées par règle, « Accepter toutes les recommandations ».
- Générer : Curiosity (`Schema.cs`, `Edges.cs`, `RegisterSchema.cs`, `Connector.cs`), Neo4j (`schema.cypher`, `ingest.cypher`, `validation.cypher`, `model.mmd`), `schema.graphql`, rapport de transposition, zip.
- Requêtes : traduction SPARQL → Cypher / Curiosity / GraphQL avec notes de perte ; questions de compétence.
- Assistant IA : brouillon d'ontologie depuis texte, CSV ou SQL, acceptation élément par élément ; shapes proposées ; explication d'un constat ; fournisseurs `anthropic`, `openai_compat`, `ollama`, `mock`.
- Docker : `docker compose up --build` (backend FastAPI + frontend nginx), projets persistés dans le volume `ontoforge-data`.

### Par lot

| Lot | Contenu | Revues (verdicts) |
|---|---|---|
| L0 | Cadrage : catalogue étendu à 66 règles (36 + 30 ajoutées), sévérités K02 et C05 corrigées en `review`, oracle `samples/trap/expected-findings.yaml`, vocabulaire d'options normatif (D-031) | w3c : KO puis corrections |
| L1 | Socle : `core/*` (contrats pydantic), API REST (27 routes d'itération 1), stockage projets, imports/exports RDF, DSL, Dockerfile / compose | w3c it1 : OK |
| L2 | Conformité (profils DL/EL/QL/RL, W01 à W07, BP01 à BP07, raisonneur optionnel), SHACL (import/export/génération/validation/traduction vers contraintes PG) ; `validate` sans inférence par défaut (D-034, D-L2-01) | w3c it1 : KO → it2 : OK |
| L3 | Moteur de mapping : 66 règles implémentées dès l'itération 1 (aucun `X00`), oracle 6/6 `must_not`, 66 constats attendus, rapport de transposition, groupement par règle, décisions groupées | w3c it1 : KO → it2 : OK |
| L4 | Générateurs Curiosity, Neo4j, GraphQL ; traducteur SPARQL ; questions de compétence ; cartes de types xsd par cible | curiosity/neo4j croisées it1 : KO → it2 : OK ; w3c it1 : KO, it2 : KO |
| L5 | Interface React : 7 écrans + panneau assistant, thème clair/sombre, captures `journal/L5/screens/` | — |
| L6 | Assistant IA : service, analyseurs CSV/SQL, conversion JSON → `OntoModel`, 4 fournisseurs | — |
| L7 | Plan de recette (`journal/L7/plan-recette.md`) | recette chez Jerem à venir |
| L13 (reliquats, itération 2 anticipée) | `Decimal` (Curiosity sans perte), noms de reverse (`mapping/reverse_names.py`), I01/C08 (nœuds de référence), diagramme lisible, script `tools/dotnet/check-curiosity.ps1` | w3c it1 : KO (collisions de noms de reverse) |

### L16 et L17 (4 novembre 2026)

- L16 : Krakie globale (bouton flottant, Ctrl+K, contexte de l'écran, cartes Appliquer / Annuler, intentions sans LLM).
- L17 : Vue liste refaite, écran Shapes refait (édition en ligne, diff de génération, validation), Requêtes : endpoint temporaire, valeurs possibles sans endpoint, nouveau logo. API : `dry_run` sur `/shacl/generate`, `GET /query/options`, `POST /query/endpoint-test`. Voir `journal/L16/cloture.md` et `journal/L17/cloture.md`.

### Corrections notables issues des revues

- Catalogue : `owl:hasKey` n'est jamais `auto` (K02, SS §9.5) ; `owl:equivalentClass` nommée = `review` (C05) ; deux `rdfs:domain` / `rdfs:range` = intersection (D12/O21), jamais union ; relation à ≥ 3 rôles = R02, jamais R01.
- Moteur : cardinalités `some` / `min n` jamais lues comme « exactement 1 » ; héritage aplati sans fausse obligation ; propriétés non simples sans cardinalité ; chaînes de propriétés conservées dans l'ordre ; domaine/portée complexes → G01 explicite.
- Générateurs : hexBinary / base64Binary et `rdf:langString` classés hors carte OWL 2 (perte) ; clé de repli = propriété IRI, jamais de motif de correspondance vide ; Neo4j : contraintes Enterprise séparées.
- Traducteur : classe ou propriété absente du modèle = motif vide + perte (jamais un motif non typé) ; types multiples sur un même discriminant = perte.
- Conformité : W07 ignore les vocabulaires réutilisés (dcterms, skos…) ; `DisjointUnion` classé hors EL/QL/RL (confirmé).

### Décisions structurantes

D-002 (FastAPI + React), D-003 (Docker uniquement), D-004 (SHACL dès la v0.1), D-005 (Curiosity prioritaire), D-006 (assistant soumis à revue humaine), D-028 (contrats `core/*` normatifs), D-031 (66 règles), D-034 (validation sans inférence), D-035 (format des identifiants de constat), D-038 (pas de fichiers golden), D-L13-01 (`Decimal`). Liste complète : `journal/decisions.md`.

### Limites connues à la livraison

C# Curiosity non compilé, Cypher non exécuté, API externes `À VÉRIFIER`, aucune authentification. Détail dans [`limites.md`](limites.md).

## 0.2.0 : Itération 2 (livraison prévue le vendredi 6 novembre 2026)

> Statut au 4 novembre 2026 : lots L8, L9, L10, L11, L13, L14 (données de démo, historique des générations) et L15 livrés côté code ; la recette (L14) et la validation de Jerem restent à faire. Tests backend : 528 verts d'après la revue L15 (non rejoués par le documentaliste). `npm run build` vert d'après les rapports.

### Nouveautés

- Parcours et tableau de bord : l'interface suit Concevoir → Vérifier → Transposer → Générer ; un tableau de bord par projet (prochaine action de Krakie, étapes, constats par cible, générations, périmètres) ; design system « Abysse » (clair / sombre), IBM Plex ; interface fr / en.
- Éditeur graphique interactif : canvas + inspecteur rabattable + arbre + saisie rapide ; gestes (double-clic = classe, glisser = sous-classe / propriété / disjonction, F2, Suppr) ; annuler / rétablir (200 niveaux) ; validation OWL 2 de chaque geste (tout ou rien) ; icônes par classe ; zoom sémantique.
- Périmètres : sous-ensembles de l'ontologie à transposer (plusieurs par projet), `?perimeter=` sur analyse et génération, constats P00 à P03.
- Paramètres : fournisseurs LLM multiples (type, URL, modèle, clé chiffrée côté serveur, test de connexion, défaut), langues, défauts (IRI de base, préfixes, cible, nommage), endpoints SPARQL multiples (un actif).
- Assistant plein écran : conversation par projet, choix du fournisseur, dépôt de fichiers (CSV, SQL, texte, Markdown, 2 Mo) avec aperçu, actions rapides, proposition acceptée ou rejetée élément par élément, affichée aussi dans l'éditeur.
- Requêtage interactif : phrase guidée pilotée par l'ontologie et les shapes, autocomplétion de valeurs depuis l'endpoint, filtres, colonnes, exécution lecture seule, résultats en tableau et graphe, SPARQL / Cypher / Curiosity / GraphQL côte à côte, requêtes sauvegardées, question en langage naturel (`POST /query/nl`, repli déterministe).
- Krakie, mascotte pixel art animée (8 poses).
- Historique des générations côté serveur (`GET /generations`) ; données de démo `samples/automaint/automaint-demo-data.ttl` et `tools/demo/generate_demo_data.py`.
- Documentation : ce guide mis à jour (utilisateur, architecture, API, limites, glossaire).

### Par lot

| Lot | Contenu | Revues |
|---|---|---|
| L8 | `settings/` (Fernet + HKDF, `ONTOFORGE_SECRET_KEY`, rotation), `api/settings.py`, multi-fournisseurs, `/assistant/chat` et `/upload`, écran Paramètres (CONTRACTS §4, D-L8-01) | — |
| L9 | `editing/` (opérations, historique, périmètres, graphe, icônes), `api/editing.py`, éditeur graphique (CONTRACTS §5, D-L9-01, D-L9-02) | — |
| L10 | Assistant plein écran, store `lib/proposal.ts` | — |
| L11 | Shell, kit, i18n, tokens « Abysse », Krakie, tableau de bord | — |
| L13 | Reliquats it. 1 : Decimal, noms de reverse (+ correctif de collision après revue W3C), I01 / C08, diagramme du modèle, `tools/dotnet/check-curiosity.ps1` | w3c it1 KO → corrigé (475 tests verts) |
| L14 | Historique des générations (§7), données de démo (524 tests verts) | — |
| L15 | Requêtage guidé, endpoints multiples, `/query/nl` (CONTRACTS §6) ; correctif du moteur (D-L15-01) | curiosity : approuvé sous réserve (1 bloquant corrigé) |

### Corrections notables

- Reverse : un nom de retour dérivé ne peut plus reprendre une propriété OWL existante (repli `<Arête>Of<Source>`).
- Héritage sous classe abstraite (D-L15-01) : propriétés recopiées dans chaque feuille concrète ; avant, `DisplayName` disparaissait du schéma C# de Technician / Garage / Customer / Brand. Relancez l'analyse des projets existants.
- Decimal : Curiosity sans perte ; Neo4j `Float` avec perte signalée.
- I01 / C08 : plus de constat I01 pour les membres d'`owl:oneOf`.
- Requêtes : filtre discriminant conservé par le traducteur ; garde-fous de lecture seule.

### Décisions structurantes

D-L2-01, D-L4-02, D-L8-01 (paramètres chiffrés), D-L9-01 (éditeur : `/ops` tout ou rien), D-L9-02 (`NodeType.icon`, sévérité `info` : acceptés, non encore implémentés), D-L13-01 (`Decimal`), D-L15-01 (recopie dans les feuilles). Plan : `docs/PLAN-IT2.md` (arbitrages des 3 et 4 novembre : Krakie, un endpoint actif, requêtage façon Sparnatural avec notre constructeur, langage naturel).

### Limites connues

C# Curiosity et Query API non vérifiés, Cypher non exécuté, API externes `À VÉRIFIER`, aucune authentification, pas de filtrage SSRF, fournisseurs LLM réels non éprouvés, pas de test automatisé du front. Détail : [`limites.md`](limites.md).

## 0.3.0 (en cours)

Lots L19 à L26, un par ligne. Les détails sont dans `journal/L<n>/rapport.md`.

- L19 : triplestore local embarqué par projet (pyoxigraph 0.5.13), requêtes, inférence RDFS / OWL RL, validation SHACL. Graphe par défaut = union dédupliquée (D-L19-01). Revues w3c et requêtage OK à l'itération 2, documentation vérifiée.
- L20 : easter egg avec Krakie, un petit jeu caché dans l'application (un indice se trouve dans Paramètres) ; revue scout it1 OK.
- L21 : veille normes et bibliothèques (`docs/veille/`), Dependabot en signalement seulement (D-L21-01 à D-L21-03 : pas de veille planifiée, pas de montée de version, validation Neo4j et Curiosity manuelle). Revues w3c, neo4j et curiosity OK.
- L22 : éditeur de fichiers intégré (écran « Fichiers », CodeMirror 6, validation, aperçu des différences, API `/files`) ; revues w3c et scout OK à l'itération 2.
- L23 : humanisation de la documentation et des skills, étape 1 (skill `humanizer`).
- L24 : publication, intégration continue (pytest, build front, recettes en manuel) et Dependabot encadré.
- L25 : amorcer une ontologie depuis un document (.txt, .md, .pdf) avec extrait source, badge « À confirmer » et contrôles W3C ; revues w3c et scout it1.
- L26 : lire le graphe de l'ontologie. Légende flottante qui ne montre que les encodages présents, mode « Notation VOWL » (VOWL 2 : classes en cercles, classes externes, équivalentes, anonymes, types de données, caractéristiques des propriétés), menu « Afficher » avec curseur de densité et compteur, export SVG et PNG du graphe tel qu'affiché, étape « legend » de la visite guidée (19 étapes). `GET /graph` reste rétrocompatible et gagne (`external`, `equivalent`, `include=external,anonymous,thing`). Revues w3c, scout, doc, humaniseur : voir `journal/L26/rapport.md`.
