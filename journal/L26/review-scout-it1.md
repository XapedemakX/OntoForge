verdict: OK
bloquants:
  - aucun restant. Deux défauts d'usage ont été corrigés pendant la relecture (légende au premier usage, lisibilité au zoom) ; le pilote les relit dans fix-it1.
non-bloquants:
  - [Editor.tsx, barre] deux lignes à 1440 px (mode, Afficher, compteur, Réorganiser). Le compteur « 52 nœuds / 67 arêtes affichés sur 52 / 67 » est long pour une information secondaire : n'afficher « sur X / Y » que si un filtre masque quelque chose, ou le passer en info-bulle du bouton « Afficher ».
  - [exporter.ts, VOWL] avec les 25 propriétés de données, les libellés verts et les rectangles jaunes se chevauchent dans le SVG (vérifié à l'œil, rendu librsvg). Propositions : décaler le libellé d'une propriété de données vers le rectangle, ou exporter par défaut sans propriétés de données au-delà de 16 classes, comme l'écran.
  - [exporter.ts] légende incluse par défaut : bon choix pour un livrable client (le SVG se lit seul). Absence de pictogrammes dans les nœuds classiques : acceptable, le nom porte l'information.
  - [vowl.tsx] en compact, un nom long qui déborde du cercle peut chevaucher un voisin quand les cercles sont serrés (Véhicule thermique / Véhicule électrique). « Réorganiser » règle le cas ; un anti-chevauchement des libellés serait un plus (WebVOWL ne le fait pas non plus).
  - [legend] à 1440 px la légende ouverte prend 330 px ; la vue se cadre maintenant à côté (voir corrections). Un raccourci clavier (L) pour l'ouvrir et la fermer aiderait les habitués.
skill: ajouté à skills/product-discovery/SKILL.md, « Pièges » : un panneau d'aide demandé parce qu'on ne le trouvait pas s'ouvre au premier usage, puis respecte le dernier choix ; et une vue d'ensemble se mesure en pixels à l'écran (≥ 10-11 px), pas en pourcentage de zoom.

## Méthode

`node tools/recette/l26_legend.mjs` lancé dans une copie propre du dépôt (worktree sur HEAD, sans les fichiers non commités du lot de déploiement). Captures relues : 01, 02, 02a, 03c (nouvelle), 10, 14. Export SVG ouvert hors application : `xmllint --noout` valide, rendu `rsvg-convert` (librsvg, le moteur des aperçus GNOME et proche d'Inkscape) identique au navigateur. Inkscape n'est pas installé ici : À VÉRIFIER à la main, mais le fichier n'utilise ni `<style>`, ni classes, ni `var()`, ni `foreignObject`, ni `color-mix` : uniquement des attributs et `style=""` en ligne avec des couleurs hexadécimales et des polices de secours (`'IBM Plex Sans', 'Segoe UI', Helvetica, Arial, sans-serif`), ce qu'Inkscape lit.

## La légende répond-elle à « difficile de savoir à quoi correspond quoi » ?

Oui, sur le fond : chaque encodage visible a un mini-dessin aux mêmes couleurs que le graphe et une phrase, et seuls les encodages présents sont listés, ce qui garde le panneau court (10 entrées en classique sur automaint, 17 en VOWL). La note « lecture seule » pour les types de données évite une frustration. Non, sur la forme, tant qu'elle était fermée par défaut : Jerem a demandé une légende parce qu'il ne voyait pas comment lire le graphe, la laisser derrière un bouton reproduisait le problème. Corrigé (voir plus bas).

## Décisions prises sans Jerem

| Décision | Avis | Suite |
|---|---|---|
| Propriétés de données masquées au-delà de 16 classes | Confirmée : à 25 classes, 25 rectangles jaunes doublent le nombre de nœuds et noient le graphe (capture 02 contre 02a). Le compteur et la case « Propriétés de données » rendent le masquage visible. Le guide le dit maintenant | à confirmer par Jerem (`journal/questions-jerem.md`) |
| Légende fermée par défaut | Modifiée : ouverte au premier usage (repliée sous 900 px), le choix suivant est mémorisé | corrigé |
| Sélection en teal | Confirmée : le rouge VOWL entrerait en conflit avec les erreurs, et le teal est la couleur de sélection du reste de l'application. Un ingénieur habitué à WebVOWL ne sera pas dérouté, la légende l'explique | rien |

## Corrigé par le relecteur

1. **Légende ouverte au premier usage** (`Editor.tsx`) : sans valeur mémorisée, état `open` (ou `folded` sous 900 px pour ne pas couvrir le graphe sur mobile) ; une fermeture est mémorisée. Le cadrage initial, « Réorganiser » et le bouton « ajuster la vue » réservent 350 px à droite quand la légende est ouverte, pour qu'elle ne cache aucun nœud (`fitPad`). Recette : L1 vérifie l'ouverture puis la mémorisation de la fermeture, M1 le repli sur mobile.
2. **Lisibilité VOWL en vue d'ensemble** (`vowl.tsx`, `editor.css`) : à 42 % de zoom, le nom d'une classe faisait 5 à 6 px à l'écran (police plafonnée à 13 px dans le graphe). Désormais, sous 60 % : police calculée pour garder 11 px à l'écran (plafond 37), nom sur deux lignes au plus, autorisé à déborder du cercle (230 % de sa largeur) avec un halo couleur de fond ; sous 30 %, noms masqués, l'info-bulle du cercle les donne. Le zoom minimal du cadrage initial passe de 42 % à 30 % : le graphe entier tient à l'écran et reste lisible. Recette : nouveau contrôle V6 (police minimale mesurée à l'écran ≥ 10 px, masquage sous 30 %), capture `03c-vowl-ensemble-lisible.png`.
3. Recette F2 : comptait les libellés de disjonction, invisibles sous 55 % de zoom ; elle compte maintenant les arêtes de disjonction (le contrôle ne dépend plus du zoom).

## Gardes (worktree propre)

pytest 757 passés, dont le nouveau test w3c (l’écart avec les 823 du rapport L26 vient des tests non commités du lot de déploiement, test_auth, test_fsutil, test_netguard, test_security, absents de la copie propre) ; `npm run build` OK ; l26_legend 24/24 ; tour 45/0 ; e2e_ui 30/30 ; english_scan 0 suspect.
