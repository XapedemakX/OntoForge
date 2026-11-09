# L30 : correctif « Krakie toute déformée en déplacement »

## Cause
Reproduite par captures image par image (`tools/recette/l30_frames.mjs`, touche → maintenue, une capture du canvas à chaque image). L'« inclinaison » du moteur était un cisaillement par rangées : chaque ligne du sprite 32 px était décalée de `round(lean × (1 − 1,5 r/31))`, jusqu'à 3 px. La tête devenait un parallélogramme et les tentacules se découpaient en escalier, avec un décalage qui changeait d'une image à l'autre pendant l'accélération. Le reste est sain : échelle entière, positions arrondies, `imageSmoothingEnabled = false`, rebond entier, images de nage alignées sur la même ancre (tête x 4 à 27 sur les 6 images).

## Correction (`frontend/src/game/engine.ts`)
- Plus de cisaillement : la tête et le corps (rangées 0 à 19) sont dessinés intacts à une position entière.
- L'inclinaison devient un décalage d'un pixel des tentacules (rangées 20 à 31), qui traînent à l'opposé du déplacement ; état discret avec hystérésis (seuils 1,4 / 0,6), donc sans scintillement.
- Ondulation des tentacules, rebond, expressions, mouvement réduit : inchangés.

## Preuves
`journal/L30/fix-deformation/avant.png` et `apres.png` : 8 images consécutives, ×4. Nouveau GIF : `journal/L30/krakie-en-action-v2.gif`. `l30_game` tout OK, `l20_game` tout OK, `e2e_ui` 30/30, build vert.
