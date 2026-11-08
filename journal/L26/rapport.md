# L26 : lire le graphe, légende et notation VOWL

Pilote : lead front. Demande de Jerem : « il manque une légende sur le graphe de l'ontologie, difficile de savoir à quoi correspond quoi ».

## Livré

| Zone | Contenu |
|---|---|
| Légende | `Legend.tsx`, `legendDefs.ts`, `glyphs.ts`. Bouton « Légende » sur le canevas, panneau flottant repliable, état mémorisé (`ontoforge.ed.legend`, try/catch). Une entrée par encodage, avec un mini-dessin SVG qui utilise les variables CSS de l'éditeur, donc les mêmes jetons que le graphe. Seuls les éléments présents dans la vue sont listés ; la sélection et l'erreur sont toujours expliquées. La légende suit le mode actif |
| Notation VOWL | `vowl.tsx`, `view.ts`, `geom.ts`, styles `.of-vn` / `.of-vl` dans `editor.css`. Sélecteur Classique / VOWL (`ontoforge.ed.mode`). Classes en cercles, externes, dépréciées, équivalentes fusionnées en double cercle, `owl:Thing` dupliqué, classes anonymes ∪ ∩ ¬, types de données (rectangle jaune, `Literal` en pointillé), propriétés de données, propriétés objet avec caractéristiques entre crochets, inverses fusionnées en double pointe, sous-classe en pointillé « Sous-classe de », disjonction avec deux disques |
| Filtres | `ShowMenu.tsx` : menu « Afficher » (propriétés de données, sous-classes, relations, disjonctions et équivalences, classes dépréciées, propositions de Krakie), curseur de densité (replie les classes de degré ≤ N, badge « +n » sur les voisines), compteur « N nœuds / M arêtes affichés sur X / Y ». Préférences mémorisées (`ontoforge.ed.show`). Hiérarchie / Relations / Tout règlent les cases sous-classes, relations, disjonctions |
| Export | `exporter.ts` : SVG autonome refait à partir des nœuds et arêtes affichés (même géométrie que l'écran), styles en ligne, couleurs résolues du thème courant, polices de secours, légende en option ; PNG tiré du SVG (double résolution). Téléchargement navigateur normal |
| Visite guidée | étape `legend` (après la saisie rapide) ; 18 → 19 étapes ; borne de `tools/recette/tour.mjs` relevée à 19 (`MAX_STEPS`) |
| Backend | `GET /graph` enrichi sans rien casser : `external`, `equivalent` sur chaque nœud, `characteristics` / `deprecated` / `functional` sur les arêtes, `include=external,anonymous,thing` ; test `test_graph_l26_additive_flags_and_includes` ; `docs/CONTRACTS.md` §5 |
| Docs | `docs/guide/utilisateur.md` (section « Lire le graphe : légende et notation VOWL », deux tableaux), `docs/guide/CHANGELOG.md` (0.3.0, ligne L26), visite en 19 étapes |
| Recette | `tools/recette/l26_legend.mjs` (23 contrôles), captures dans `journal/L26/screens/` |

## Source de la notation VOWL

La spécification officielle (`vowl.visualdataweb.org/v2/`) redirige vers `lgean.net`, un domaine sans rapport avec VOWL : je ne l'ai pas suivi. Sources lues avec WebFetch :

1. Copie de la page « VOWL: Visual Notation for OWL Ontologies » (tableaux de formes, traits et couleurs, avec valeurs hexadécimales) : https://s3.amazonaws.com/benetta/16418920171000000061/reference/riddle-vowl/index.html. Copie tierce.
2. Résumé de l'article « VOWL 2: User-Oriented Visualization of Ontologies » (Lohmann et al., EKAW 2014) : https://semantic-web-journal.net/content/vowl-2-user-oriented-visualization-ontologies, utilisé pour recouper rôles des couleurs et formes.
3. Dépôt github.com/VisualDataWeb/WebVOWL : seule la liste des fichiers a été lue (aucun code repris).

Vérifié (revue w3c it1) : les valeurs hexadécimales (#acf classe, #36c externe, #ccc dépréciée, #fc3 type de données, #9c6 propriété de données, #69c pictogrammes) sont celles de `src/webvowl/css/vowl.css` et de `colorExternalsSwitch.js` du dépôt WebVOWL. Voir `review-w3c-it1.md`.

## Écarts assumés avec VOWL (à valider par le relecteur W3C)

- Sélection en teal : le rouge est déjà celui des erreurs dans l'éditeur.
- Classe abstraite : italique et anneau pointillé intérieur (VOWL n'a pas d'équivalent).
- Couleurs adaptées au thème sombre (même rôle, valeurs plus foncées, texte clair).
- Caractéristiques entre crochets dans la langue de l'interface.
- Inverses : un seul libellé « a ⇄ b » au milieu, au lieu d'un libellé près de chaque pointe.
- Disjonction : rectangle bleu avec deux disques sur l'arête, pas dans une barre latérale.
- Non dessinés : cardinalités, sous-propriétés, `owl:Nothing`, `rdfs:Resource`, individus, propriétés externes ou dépréciées autrement que par la couleur de leur libellé. Le complément ¬ n'affiche pas le petit cercle intérieur.
- Équivalentes : fusion seulement entre classes nommées. Une équivalence avec une expression est une classe anonyme reliée à la classe.
- Les types de données et `owl:Thing` sont dessinés en éventail sous leur classe (position calculée, non mémorisée).

## Interaction en VOWL

Sélection, inspecteur, création par glisser depuis la poignée (menu sous-classe / propriété / disjonction), renommage et suppression fonctionnent sur les classes déclarées. Lecture seule, dit dans la légende : types de données et leurs propriétés, classes externes, classes anonymes, nœuds Thing. Une classe fusionnée (double cercle) se sélectionne par sa classe principale.

## Décisions prises sans Jerem

1. Sans préférence mémorisée, les types de données s'affichent d'emblée seulement si le graphe a 16 classes ou moins. Automaint en a 24, et ses 25 rectangles jaunes noieraient les classes. La case « Propriétés de données » du menu les active.
2. VOWL élargit l'espacement vertical de la disposition (x 1,0 ; y 1,65) sans changer les positions mémorisées : les coordonnées restent celles du mode classique, converties à l'affichage et au déplacement.
3. Légende fermée par défaut, pour ne pas masquer le graphe au premier lancement. Modifié à la relecture scout : elle s'ouvre au premier usage (repliée sous 900 px).

## Vérifications

- `cd backend && pytest -q` : 823 passés.
- `npm run build` : OK.
- `node tools/recette/l26_legend.mjs` : 23 / 23 (légende classique et VOWL, mémorisation, filtres, densité, proposition de Krakie, export SVG et PNG vérifiés, thème sombre, anglais sans français dans la légende, le menu et le SVG, mobile 390 px).
- Gardes (`tour.mjs`, `e2e_ui.mjs`, `english_scan.mjs`, `l22_files.mjs`) : pytest 823 OK, build OK, l26_legend 23/23, tour 45/0, e2e_ui 30/30, english_scan 0 suspect, l22_files 23/23.

## Limites connues

- Sur un graphe de 25 classes dans un canevas de 960 px, la vue d'ensemble se règle à 42 % de zoom : les noms ne sont pas lisibles, les cercles se distinguent par leur forme et leur couleur. Replier l'arbre et la légende donne environ 56 %. Un zoom à 60 % ou plus montre les libellés des relations.
- Le PNG dépend du rendu SVG du navigateur (polices de secours si IBM Plex n'est pas installée).
- L'export dessine les nœuds sans pictogramme Font Awesome (un petit graphe générique à la place).

## Relectures (TEAM.md : écran = scout + expert du domaine, puis doc, puis humain)

Faites après la production : `review-w3c-it1.md` (OK, 4 écarts OWL corrigés), `review-scout-it1.md` (OK, légende ouverte au premier usage, lisibilité au zoom), `doc-ok.md`, puis passage de l'humaniseur. Lot clos. Questions de départ : `journal/L26/demande-relectures.md`.
