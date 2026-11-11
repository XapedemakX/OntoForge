# Journal des versions {#journal-des-versions}

Format : par version, ce qui change pour l'utilisateur, puis le détail par lot. Sources : rapports `journal/L*/rapport*.md`, revues, `journal/decisions.md`. Les lots sont décrits dans `lots/`.

## L35 : bandeau latéral repliable en icônes (11 nov. 2026) {#l35-bandeau-lateral-repliable-en-icones-11-nov-2026}

- Le menu de gauche se replie en une bande d'environ 56 px (icônes seules, logo réduit à la tête de Krakie, étapes en pastilles 1 à 4, infobulles au survol et au clavier, nombre de constats à arbitrer en pastille sur l'icône). Bouton en bas du bandeau ou Ctrl+B ; choix mémorisé dans le navigateur.
- Repli automatique sur les écrans de plein canevas (éditeur graphique, vue liste, fichiers, documentation), sauf si le bandeau a été gardé ouvert. Paramètres, onglet Affichage : Automatique, Ouvert ou Replié. Le canevas de l'éditeur est recadré à la fin de la transition ; `prefers-reduced-motion` supprime l'animation. Mobile inchangé.

## L30 : Krakie vivante dans le jeu caché (8 nov. 2026) {#l30-krakie-vivante-dans-le-jeu-cache-8-nov-2026}

- Correctif : Krakie ne se déforme plus en se déplaçant (plus de cisaillement du sprite : corps intact, seuls les tentacules traînent d'un pixel).
- Dans « Krakie's Triple Catch », Krakie nage (6 images, tentacules en onde, léger rebond) et s'incline dans le sens du déplacement.
- Expressions brèves : clin d'œil à chaque élément attrapé, grand sourire et étincelles pour un triplet complet, surprise pour un bonus, grimace avec léger tremblement pour un constat perdu ou une IRI cassée, inquiète en continu à une seule vie. Halo de verre pendant le bouclier SHACL, effet violet pendant l'inférence. Fin de partie : trophée si record ou 400 points, inquiète sinon.
- Un mot n'est plus à la fois cible et distracteur d'une autre catégorie ; le graphe de fond reste sous le bandeau de score. Avec `prefers-reduced-motion` : expressions fixes, ni tremblement, ni rebond, ni inclinaison.
- Correctif : dans le jeu caché, Krakie n'apparaît plus comme un carré teal quand une image de pose ne se charge pas (manifeste en cache périmé, fichier absent) : toutes les poses sont préchargées avant de jouer, sinon une silhouette pixel art la remplace ; la zone de jeu reste centrée de 390 à 2560 px ; « doneBy » s'affiche « DONE BY ».

## L29 : Krakie forgeronne (8 nov. 2026) {#l29-krakie-forgeronne-8-nov-2026}

- Krakie forge (deux marteaux sur une enclume) pendant les exports, l'analyse, la génération de shapes et le brouillon depuis un document, à la place de Krakie au volant, puis brandit un trophée en forme de graphe pendant environ 2 s à la fin d'un traitement réussi. Images fixes avec `prefers-reduced-motion`.
- Nouvelles poses `forge` (8 images) et `trophee` (4 images) ; la pose « bolide » reste dans les sources de `design/krakie/` mais n'est plus affichée.

## L31 : versions des normes et des cibles (8 nov. 2026) {#l31-versions-des-normes-et-des-cibles-8-nov-2026}

- Référence `standards.json` embarquée (W3C, Neo4j, Cypher, Curiosity.Library, bibliothèques internes) ; `GET /api/standards`.
- Versions par projet avec défaut global dans les Paramètres ; contrôle local `versions/check` ; écran Versions.
- Neo4j : préfixe `CYPHER 25` / `CYPHER 5` requête par requête, contraintes selon la version ; Curiosity : version de Curiosity.Library dans les en-têtes et le README ; le rapport de transposition liste les versions ; fonctions SHACL 1.2 désactivées.
- Krakie : « quelles versions ? », « mets à jour les versions », bulle d'écart une fois par session.
- SHACL : la seule version publiée est la 1.0 (Recommandation du 20 juillet 2017) ; « SHACL 1.1 » n'existe pas officiellement et n'est lu que comme synonyme de 1.0. Neo4j 4.4 : seul `schema.cypher` a une variante (syntaxe ASSERT, À VÉRIFIER).
- Correctif Krakie : « help » seul reçoit désormais une réponse en anglais.

## 0.1.0 : Itération 1 (livraison prévue le mardi 3 novembre 2026, ~19 h, Paris, D-022) {#iteration-1-livraison-prevue-le-mardi-3-novembre-2026-19-h-paris-d-022}

> Statut au premier passage de L12 : la recette chez Jerem (`docker compose up --build`, lot L7) n'a pas encore eu lieu et aucun lot n'a de fichier `cloture.md`. Cette version reflète l'état du dépôt le 3 novembre 2026 au soir.

### Nouveautés {#nouveautes}

- Concevoir : projets (vides, depuis les exemples `automaint` et `trap`, ou par dépôt de fichier) ; éditeur d'ontologie façon Protégé ; Saisie rapide (DSL, une ligne = un axiome) ; import Turtle, RDF/XML, JSON-LD, N-Triples, N3, TriG ; export Turtle, RDF/XML, JSON-LD, N-Triples, N3.
- Vérifier : conformité OWL 2 DL / EL / QL / RL avec références de spécification (W01 à W07) et bonnes pratiques (BP01 à BP07).
- SHACL : import, génération depuis l'ontologie, validation d'un fichier de données (sans inférence par défaut).
- Transposer : moteur de 66 règles (+ S01, S02, G02) avec constats *auto / à arbitrer / perdus*, options par cible, recommandation par cible, décisions mémorisées et rejouées, décisions groupées par règle, « Accepter toutes les recommandations ».
- Générer : Curiosity (`Schema.cs`, `Edges.cs`, `RegisterSchema.cs`, `Connector.cs`), Neo4j (`schema.cypher`, `ingest.cypher`, `validation.cypher`, `model.mmd`), `schema.graphql`, rapport de transposition, zip.
- Requêtes : traduction SPARQL → Cypher / Curiosity / GraphQL avec notes de perte ; questions de compétence.
- Assistant IA : brouillon d'ontologie depuis texte, CSV ou SQL, acceptation élément par élément ; shapes proposées ; explication d'un constat ; fournisseurs `anthropic`, `openai_compat`, `ollama`, `mock`.
- Docker : `docker compose up --build` (backend FastAPI + frontend nginx), projets persistés dans le volume `ontoforge-data`.

### Par lot {#par-lot}

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

### L16 et L17 (4 novembre 2026) {#l16-et-l17-4-novembre-2026}

- L16 : Krakie globale (bouton flottant, Ctrl+K, contexte de l'écran, cartes Appliquer / Annuler, intentions sans LLM).
- L17 : Vue liste refaite, écran Shapes refait (édition en ligne, diff de génération, validation), Requêtes : endpoint temporaire, valeurs possibles sans endpoint, nouveau logo. API : `dry_run` sur `/shacl/generate`, `GET /query/options`, `POST /query/endpoint-test`. Voir `journal/L16/cloture.md` et `journal/L17/cloture.md`.

### Corrections notables issues des revues {#corrections-notables-issues-des-revues}

- Catalogue : `owl:hasKey` n'est jamais `auto` (K02, SS §9.5) ; `owl:equivalentClass` nommée = `review` (C05) ; deux `rdfs:domain` / `rdfs:range` = intersection (D12/O21), jamais union ; relation à ≥ 3 rôles = R02, jamais R01.
- Moteur : cardinalités `some` / `min n` jamais lues comme « exactement 1 » ; héritage aplati sans fausse obligation ; propriétés non simples sans cardinalité ; chaînes de propriétés conservées dans l'ordre ; domaine/portée complexes → G01 explicite.
- Générateurs : hexBinary / base64Binary et `rdf:langString` classés hors carte OWL 2 (perte) ; clé de repli = propriété IRI, jamais de motif de correspondance vide ; Neo4j : contraintes Enterprise séparées.
- Traducteur : classe ou propriété absente du modèle = motif vide + perte (jamais un motif non typé) ; types multiples sur un même discriminant = perte.
- Conformité : W07 ignore les vocabulaires réutilisés (dcterms, skos…) ; `DisjointUnion` classé hors EL/QL/RL (confirmé).

### Décisions structurantes {#decisions-structurantes}

D-002 (FastAPI + React), D-003 (Docker uniquement), D-004 (SHACL dès la v0.1), D-005 (Curiosity prioritaire), D-006 (assistant soumis à revue humaine), D-028 (contrats `core/*` normatifs), D-031 (66 règles), D-034 (validation sans inférence), D-035 (format des identifiants de constat), D-038 (pas de fichiers golden), D-L13-01 (`Decimal`). Liste complète : `journal/decisions.md`.

### Limites connues à la livraison {#limites-connues-a-la-livraison}

C# Curiosity non compilé, Cypher non exécuté, API externes `À VÉRIFIER`, aucune authentification. Détail dans [`limites.md`](limites.md).

## 0.2.0 : Itération 2 (livraison prévue le vendredi 6 novembre 2026) {#iteration-2-livraison-prevue-le-vendredi-6-novembre-2026}

> Statut au 4 novembre 2026 : lots L8, L9, L10, L11, L13, L14 (données de démo, historique des générations) et L15 livrés côté code ; la recette (L14) et la validation de Jerem restent à faire. Tests backend : 528 verts d'après la revue L15 (non rejoués par le documentaliste). `npm run build` vert d'après les rapports.

### Nouveautés {#nouveautes-2}

- Parcours et tableau de bord : l'interface suit Concevoir → Vérifier → Transposer → Générer ; un tableau de bord par projet (prochaine action de Krakie, étapes, constats par cible, générations, périmètres) ; design system « Abysse » (clair / sombre), IBM Plex ; interface fr / en.
- Éditeur graphique interactif : canvas + inspecteur rabattable + arbre + saisie rapide ; gestes (double-clic = classe, glisser = sous-classe / propriété / disjonction, F2, Suppr) ; annuler / rétablir (200 niveaux) ; validation OWL 2 de chaque geste (tout ou rien) ; icônes par classe ; zoom sémantique.
- Périmètres : sous-ensembles de l'ontologie à transposer (plusieurs par projet), `?perimeter=` sur analyse et génération, constats P00 à P03.
- Paramètres : fournisseurs LLM multiples (type, URL, modèle, clé chiffrée côté serveur, test de connexion, défaut), langues, défauts (IRI de base, préfixes, cible, nommage), endpoints SPARQL multiples (un actif).
- Assistant plein écran : conversation par projet, choix du fournisseur, dépôt de fichiers (CSV, SQL, texte, Markdown, 2 Mo) avec aperçu, actions rapides, proposition acceptée ou rejetée élément par élément, affichée aussi dans l'éditeur.
- Requêtage interactif : phrase guidée pilotée par l'ontologie et les shapes, autocomplétion de valeurs depuis l'endpoint, filtres, colonnes, exécution lecture seule, résultats en tableau et graphe, SPARQL / Cypher / Curiosity / GraphQL côte à côte, requêtes sauvegardées, question en langage naturel (`POST /query/nl`, repli déterministe).
- Krakie, mascotte pixel art animée (8 poses).
- Historique des générations côté serveur (`GET /generations`) ; données de démo `samples/automaint/automaint-demo-data.ttl` et `tools/demo/generate_demo_data.py`.
- Documentation : ce guide mis à jour (utilisateur, architecture, API, limites, glossaire).

### Par lot {#par-lot-2}

| Lot | Contenu | Revues |
|---|---|---|
| L8 | `settings/` (Fernet + HKDF, `ONTOFORGE_SECRET_KEY`, rotation), `api/settings.py`, multi-fournisseurs, `/assistant/chat` et `/upload`, écran Paramètres (CONTRACTS §4, D-L8-01) | — |
| L9 | `editing/` (opérations, historique, périmètres, graphe, icônes), `api/editing.py`, éditeur graphique (CONTRACTS §5, D-L9-01, D-L9-02) | — |
| L10 | Assistant plein écran, store `lib/proposal.ts` | — |
| L11 | Shell, kit, i18n, tokens « Abysse », Krakie, tableau de bord | — |
| L13 | Reliquats it. 1 : Decimal, noms de reverse (+ correctif de collision après revue W3C), I01 / C08, diagramme du modèle, `tools/dotnet/check-curiosity.ps1` | w3c it1 KO → corrigé (475 tests verts) |
| L14 | Historique des générations (§7), données de démo (524 tests verts) | — |
| L15 | Requêtage guidé, endpoints multiples, `/query/nl` (CONTRACTS §6) ; correctif du moteur (D-L15-01) | curiosity : approuvé sous réserve (1 bloquant corrigé) |

### Corrections notables {#corrections-notables}

- Reverse : un nom de retour dérivé ne peut plus reprendre une propriété OWL existante (repli `<Arête>Of<Source>`).
- Héritage sous classe abstraite (D-L15-01) : propriétés recopiées dans chaque feuille concrète ; avant, `DisplayName` disparaissait du schéma C# de Technician / Garage / Customer / Brand. Relancez l'analyse des projets existants.
- Decimal : Curiosity sans perte ; Neo4j `Float` avec perte signalée.
- I01 / C08 : plus de constat I01 pour les membres d'`owl:oneOf`.
- Requêtes : filtre discriminant conservé par le traducteur ; garde-fous de lecture seule.

### Décisions structurantes {#decisions-structurantes-2}

D-L2-01, D-L4-02, D-L8-01 (paramètres chiffrés), D-L9-01 (éditeur : `/ops` tout ou rien), D-L9-02 (`NodeType.icon`, sévérité `info` : acceptés, non encore implémentés), D-L13-01 (`Decimal`), D-L15-01 (recopie dans les feuilles). Plan : `docs/PLAN-IT2.md` (arbitrages des 3 et 4 novembre : Krakie, un endpoint actif, requêtage façon Sparnatural avec notre constructeur, langage naturel).

### Limites connues {#limites-connues}

C# Curiosity et Query API non vérifiés, Cypher non exécuté, API externes `À VÉRIFIER`, aucune authentification, pas de filtrage SSRF, fournisseurs LLM réels non éprouvés, pas de test automatisé du front. Détail : [`limites.md`](limites.md).

## 0.3.0 (en cours) {#en-cours}

Lots L19 à L26, un par ligne. Les détails sont dans `journal/L<n>/rapport.md`.

- L19 : triplestore local embarqué par projet (pyoxigraph 0.5.13), requêtes, inférence RDFS / OWL RL, validation SHACL. Graphe par défaut = union dédupliquée (D-L19-01). Revues w3c et requêtage OK à l'itération 2, documentation vérifiée.
- L20 : easter egg avec Krakie, un petit jeu caché dans l'application (un indice se trouve dans Paramètres) ; revue scout it1 OK.
- L21 : veille normes et bibliothèques (`docs/veille/`), Dependabot en signalement seulement (D-L21-01 à D-L21-03 : pas de veille planifiée, pas de montée de version, validation Neo4j et Curiosity manuelle). Revues w3c, neo4j et curiosity OK.
- L22 : éditeur de fichiers intégré (écran « Fichiers », CodeMirror 6, validation, aperçu des différences, API `/files`) ; revues w3c et scout OK à l'itération 2.
- L23 : humanisation de la documentation et des skills, étape 1 (skill `humanizer`).
- L24 : publication, intégration continue (pytest, build front, recettes en manuel) et Dependabot encadré.
- L25 : amorcer une ontologie depuis un document (.txt, .md, .pdf) avec extrait source, badge « À confirmer » et contrôles W3C ; revues w3c et scout it1.
- L32 : raisonner avec HermiT. Bouton « Raisonner avec HermiT » dans Conformité (cohérence, classes insatisfiables cliquables et mises en rouge dans l'éditeur, inférences ajoutables au modèle par `/ops`, individus reclassés ; pendant le calcul, Krakie forgeronne et « HermiT raisonne… (jusqu'à 30 s) », puis trophée si cohérente ou Krakie inquiète sinon), `POST /api/projects/{id}/reason`, intention Krakie « raisonne / vérifie la cohérence / run the reasoner », image Cloud Run avec Java par défaut (`WITH_REASONER=1`). Revues : voir `journal/L32/rapport.md`.
- L26 : lire le graphe de l'ontologie. Légende flottante qui ne montre que les encodages présents, mode « Notation VOWL » (VOWL 2 : classes en cercles, classes externes, équivalentes, anonymes, types de données, caractéristiques des propriétés), menu « Afficher » avec curseur de densité et compteur, export SVG et PNG du graphe tel qu'affiché, étape « legend » de la visite guidée (19 étapes). `GET /graph` reste rétrocompatible et gagne (`external`, `equivalent`, `include=external,anonymous,thing`). Revues w3c, scout, doc, humaniseur : voir `journal/L26/rapport.md`.
- L28 : documentation intégrée (entrée Documentation du bandeau, sommaire, recherche, liens entre fichiers, hors ligne), bouton « ? » par écran, action Krakie `help`, étape de visite (20 étapes). Voir « Documentation intégrée et aide » dans `utilisateur.md`.
- L33 : documentation en anglais. Les pages utilisateur, limites, contribuer, API et journal des versions existent en `.en.md` et s'affichent quand l'interface est en anglais ; le bandeau « French only » ne reste que sur les fichiers non traduits (architecture, règles, glossaire). Chaque titre de ces fichiers porte un identifiant explicite `{#id}`, identique en français et en anglais, pour que le bouton « ? » et Krakie ouvrent la bonne section dans les deux langues. Le test `test_help_map.py` vérifie les ancres dans les deux versions.
- L34 : captures d'écran dans la documentation. Une soixantaine d'images par langue (fr et en, mêmes données automaint) illustrent le guide, les limites et la contribution ; cliquer sur une image l'ouvre dans une visionneuse (Échap pour fermer). Elles sont générées par `node tools/docs/captures.mjs` et chargées à la demande, hors du code de l'application.
- L34d : exports bilingues et cycle de sous-classes. Les fichiers générés (commentaires et en-têtes de `Connector.cs`, `Schema.cs`, `Edges.cs`, `RegisterSchema.cs`, `schema.cypher`, `ingest.cypher`, `validation.cypher`, `schema.graphql`, README et rapport de transposition) suivent la langue de l'interface, ou le paramètre `?lang=fr|en` de l'export ; le code et les libellés de l'ontologie ne sont jamais traduits. Le document de démo de l'import et les questions du repli sans LLM suivent aussi la langue de l'interface (nouveau PDF `automaint-requirements.pdf`, généré par `make_cahier_des_charges.py --lang en`). Correctif : la saisie rapide et `/ops` refusent une sous-classe qui fermerait un cycle (message en fr et en, avec le chemin et la ligne en erreur), et `/analyze` ne répond plus 500 sur un cycle déjà présent : il le signale par un constat d'information BP03.
