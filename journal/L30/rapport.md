# L30 : Krakie vivante dans « Krakie's Triple Catch »

Demande de Jerem : « dans l'easter egg, Krakie est sans expression, elle n'a aucune animation ».

## Ce qui change
- Nage : pose `nage`, 6 images de 95 ms (onde progressive des 7 tentacules, rebond d'un pixel, clignement). Le cycle accélère quand elle se déplace. Elle s'incline dans le sens du déplacement : cisaillement par rangées fait par le moteur (tête vers l'avant, tentacules qui traînent), donc des pixels toujours nets, jusqu'à 3 px.
- Expressions brèves, toutes en 6 images, même palette et même contour 32 px :

| Événement | Pose | Durée |
|---|---|---|
| élément bien attrapé | `nage_clin` (clin d'œil + étincelle) | 0,45 s |
| triplet complet | `nage_ravie` (grand sourire, étincelles, gerbe dorée, « +gain ») | 0,8 s |
| bonus (INF ou SHACL), danger absorbé | `nage_surprise` (yeux ronds, bouche en O, traits) | 0,7 / 0,4 s |
| constat perdu, IRI cassée | `nage_grimace` (yeux > <, bouche ondulée) + tremblement de 1 px | 0,6 s |
| une seule vie | `nage_inquiete` (sourcils, goutte), en continu | tant qu'il reste une vie |

- Bouclier SHACL : disque de verre translucide + anneau pointillé avec reflet qui glisse, tant que le bouclier est actif.
- Inférence : disque violet qui grandit et 8 étincelles en orbite pendant 1,5 s.
- Écran de fin : pose `trophee` (L29) si le score dépasse le meilleur score ou 400 points, `inquiete` sinon. Dans la partie, Krakie est inquiète à la fin.
- Mouvement réduit : image 1 fixe, pas de rebond, d'inclinaison, de tremblement, de secousse d'écran ni de flash ; les expressions changent mais restent fixes ; halo de bouclier et d'inférence statiques.
- Non-bloquants L20 : (1) le mot attrapé s'affiche dans chaque case S, P, O (déjà le cas dans le code, vérifié sur les captures 03 à 07) ; (2) un distracteur ne reprend plus le mot d'une cible d'une autre catégorie ni celui d'un élément déjà à l'écran sous une autre catégorie (600 apparitions testées, 0 conflit) ; (3) le graphe de fond est cantonné sous le bandeau de score (haut à 46 px, étiquettes d'arêtes minimum 37 px) ; le « +gain » du triplet est remonté pour ne plus recouvrir Krakie.

## Fichiers
- Sprites : `design/krakie/game_poses.py` (ajout seul : n'écrit que les poses `nage*` dans `krakie-32-anim.json`, leurs SVG et le manifeste ; forge et trophee intacts, jamais de `--redraw`). Planche de contrôle : `python design/krakie/game_poses.py --sheet fichier.png`.
- Moteur : `frontend/src/game/engine.ts` (`state()`, pose courante, cisaillement, halos), `sprites.ts`, `GameOverlay.tsx` (poses, trophée, `window.__krakieGame`).
- Recette : `tools/recette/l30_game.mjs` (25 contrôles), `tools/recette/l30_gif.mjs` (GIF).
- État de test : `window.__krakieGame.state()` (actif avec `localStorage['ontoforge.game.debug']='1'`) renvoie `{expression, pose, phase, shield, inference, lean, lives, score, reduced}` ; `expression` vaut `neutral`, `wink`, `delight`, `surprise`, `grimace` ou `worried`.
- Captures : `journal/L30/screens/` (nage droite et gauche, clin, triplet complet, inférence, bouclier, grimace, une vie, fin trophée, fin inquiète, mouvement réduit ; `zoom-*.png` en gros plan). GIF de 7,8 s : `journal/L30/krakie-en-action.gif`.

## Gardes
Build vert ; chunk du jeu 33,8 ko (12,8 ko gzip) contre 31 ko avant, bundle principal inchangé ; `l30_game.mjs` 25/25 ; `l20_game.mjs` tout OK ; `e2e_ui.mjs` 30/30 ; `english_scan.mjs` 68 vues, 0 texte suspect.

## Relecture scout (demandée)
À faire par l'éclaireur produit, en jouant 5 minutes puis en regardant le GIF :
1. Krakie est-elle lisible et mignonne à l'échelle ×3 et ×2 (mobile) ? Le clin d'œil et la grimace se distinguent-ils sans lire les captures ?
2. Les expressions brèves sont-elles trop fréquentes ? Un clin à chaque élément (toutes les 1 à 2 s au début) peut fatiguer : à ajuster.
3. L'inquiétude continue à une vie est-elle assez visible malgré la goutte de 3 px ?
4. Bouclier et inférence : le halo se voit-il sur toute la durée sans masquer les éléments qui tombent ?
5. Mouvement réduit : les expressions fixes suffisent-elles à comprendre ce qui se passe ?
6. Constat de l'auteur : l'étiquette d'une arête du graphe peut encore chevaucher l'étiquette d'un nœud proche (cosmétique, antérieur à L30).
