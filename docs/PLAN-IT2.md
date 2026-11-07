# Plan OntoForge — itération 2 (vendredi 6 novembre 2026)

## Décisions de Jerem (3 nov., 22h)
- L'interface est remaniée autour du parcours **Concevoir → Vérifier → Transposer → Générer**, avec un tableau de bord par projet. Les **maquettes sont validées par Jerem** avant qu'on code.
- **Éditeur graphique interactif** de type canvas + inspecteur (graphe au centre, inspecteur à droite, arbre repliable à gauche), synchronisé avec l'arbre et la saisie rapide.
- **Panneau Paramètres** :
  - plusieurs fournisseurs LLM (type, URL, modèle, clé), un fournisseur par défaut, un test de connexion ;
  - clés **chiffrées côté serveur** (clé maître `ONTOFORGE_SECRET_KEY` dans `.env`), jamais renvoyées au navigateur ;
  - langue de l'interface (fr/en), langue des labels, langue de l'assistant ;
  - IRI de base, préfixes, cible par défaut, conventions de nommage ;
  - endpoint SPARQL.
- **Assistant plein écran** :
  - conversation par projet, choix du fournisseur dans la conversation ;
  - import de fichiers (CSV, SQL, texte, Markdown) avec aperçu ;
  - proposition affichée en surbrillance sur le graphe, acceptée ou rejetée élément par élément ;
  - actions rapides.
- **Mascotte : une pieuvre en pixel art**, nouvelle identité visuelle OntoForge (hors palette ontoSparq). Ses rôles :
  - accueil et premiers pas ;
  - états vides ;
  - réactions aux résultats (conformité, constats perdus) ;
  - avatar de l'assistant.
  
  Inspiration : le principe du compagnon de curiosity.ai, sans en copier le chat.
- **Repris d'ontoSparq** :
  - icône par classe ;
  - rendu de graphe personnalisé (icônes, bascule is-a, disjonctions) ;
  - constructeur visuel de requêtes (SPARQL + Cypher + Curiosity, exécution sur un endpoint SPARQL) ;
  - **périmètres** (sous-ensembles de l'ontologie à transposer, plusieurs par projet).
- **Deux nouveaux agents** :
  - **documentaliste** : documente tout, et la doc à jour fait partie de la définition de « terminé » ;
  - **éclaireur produit** : carnet d'idées et de fonctionnalités pour les ingénieurs en modélisation, priorisé.

## Lots
| Lot | Contenu | Pilote | Relecteurs | Quand |
|---|---|---|---|---|
| M0 | Identité (pieuvre pixel art, palette, typo) + maquettes : tableau de bord, éditeur graphique, assistant plein écran, paramètres, arbitrage | lead-design (Opus) | chef, éclaireur | mer. matin → **validation Jerem** |
| L8 | Paramètres + multi-fournisseurs LLM chiffrés + i18n fr/en + endpoint SPARQL | lead | w3c (sécurité), chef | mer. |
| L9 | Éditeur graphique interactif + icônes par classe + périmètres | lead | w3c (validité OWL de chaque geste) | mer. → jeu. |
| L10 | Assistant plein écran + imports + proposition sur graphe | lead | shacl, w3c | jeu. |
| L11 | Refonte du shell et des écrans + mascotte + constructeur visuel de requêtes | lead | chef, query | jeu. |
| L12 | Documentation complète (guide, architecture, API, règles expliquées, glossaire, FAQ des limites) | documentaliste | tous | mer. → ven. |
| L13 | Reliquats de l'itération 1 : diagramme, Decimal, noms de reverse, I01/C08, script `dotnet build`, revue W3C du moteur it2 | experts | w3c | mer. |
| L14 | Recette, revue en aveugle, livraison dans DM | chef | relecteur Opus | ven. (démo intermédiaire jeu. soir) |

## Fonctionnement
- **Modèles** : Sonnet par défaut, Opus pour le design et les revues sémantiques, Haiku pour exécuter la recette.
- **Parallélisme** : 4 agents au maximum.
- **Limite d'usage** : au premier refus (429), reprise programmée à l'heure exacte de remise à zéro.

## Arbitrages du 3/11 (22h50–23h)
- Mascotte : **Krakie** (référence au kraken), petite pieuvre chibi en pixel art, couleur lagon ; ébauche validée dans `design/krakie/krakie-draft-20px.json`, à redessiner en ~32 px dans l'esprit des exemples fournis par Jerem : contour sombre, ombrage, poses à accessoires (livre = doc, loupe = conformité, fils entre nœuds = graphe, petit bolide = génération).
- Typographie : **pas de police pixel** pour les textes et les chiffres (IBM Plex Sans + Plex Mono) ; le pixel reste réservé à Krakie.
- Inspecteur rabattable quand rien n'est sélectionné ; mobile = consultation + arbitrage + navigation dans le graphe sans édition ; proposition de l'assistant affichée aussi dans l'éditeur principal ; arêtes Curiosity en PascalCase.
- **Plusieurs endpoints SPARQL**, un actif à la fois (L8).
- **Requêtage interactif façon Sparnatural, avec notre propre constructeur** (L15) : phrase guidée pilotée par l'ontologie et les shapes, autocomplétion depuis l'endpoint actif, filtres, exécution, résultats en tableau et en graphe, traduction SPARQL / Cypher / Curiosity côte à côte, requêtes sauvegardées.

## Arbitrages du 4/11 (7h50)
- **Krakie animée** : frames par pose (idle : clignement, tentacules, respiration ; animation propre à chaque pose), pause hors écran, statique si prefers-reduced-motion.
- Requêtes : le **choix des colonnes** est utile, on le garde.
- Requêtes : **question en langage naturel → requête guidée modifiable** (POST /query/nl : correspondance déterministe avec les labels de l'ontologie + LLM du fournisseur choisi, validation stricte contre l'ontologie, repli sans LLM).

## Retours de Jerem après la démo (4/11, 17h30)
- **Assistant Krakie global** : accessible partout (Krakie flottante), il CONNAÎT l'écran et la sélection courante et agit (« ajoute la classe Pneu sous Pièce »). Sur l'ontologie, la vue liste et les shapes, Krakie est actionnable en contexte. Contrat : `frontend/src/lib/assistantContext.ts`.
- **Vue liste de l'ontologie** : pas user friendly → refonte (fiche structurée et lisible, propriétés de la classe en tableau, restrictions en langage naturel, puces et recherche).
- **Tableau des shapes** : pas aligné, pas beau → refonte (grille cohérente, contraintes lisibles, édition) + Krakie.
- **Requêtes** : endpoint temporaire saisi directement dans l'écran, sans passer par les Paramètres ; **valeurs possibles proposées dans les listes** (ex. les carburants, individus des classes énumérées) même sans endpoint.
- **Logo en haut à gauche** à refaire (Krakie + wordmark OntoForge).
