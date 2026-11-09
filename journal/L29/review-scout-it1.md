# L29 : revue scout, itération 1 (Krakie forgeronne)

verdict: OK

Relu : rapport, `final/` (planches, GIF), `screens/01` à `07`, et `node tools/recette/l29_forge.mjs` relancé : 16/16.

Lisibilité : à 64 px (taille d'usage) l'enclume, le marteau et le trophée en graphe se lisent, y compris sur fond sombre (planche ×2). À 32 px le marteau devient un trait ; sans conséquence, la carte porte toujours un texte (« Krakie forge tes exports… »).
Charme : fort. Krakie forgeronne dit le nom « OntoForge » sans explication, et le trophée en graphe boucle bien l'histoire. Identité cohérente : même palette teal, contour sombre, cartes sobres.
Gêne : aucune. La forge ne dure que le temps du traitement, le trophée 2 s, puis la carte disparaît ; elle n'est jamais affichée en continu. Mouvement réduit : image fixe `forge.svg` / `trophee.svg`, vérifié (4a, 4b). Pas de défilement horizontal sur mobile.

bloquants: aucun

non-bloquants :
  - La carte forge apparaît à gauche, au-dessus du contenu, sans réserver sa place : quand elle disparaît le contenu remonte de 80 px (Exports, 01 → 02). Réserver la hauteur serait plus calme ; à traiter si les exports deviennent plus rapides que la carte.
  - Pour un traitement quasi instantané (< 300 ms), la forge ne fait que clignoter. Un délai d'apparition de 250 ms éviterait le flash.
  - Les 3 premières captures n'ont pas de trophée à 1× : le triangle du trophée n'est lisible qu'à partir de ×2, déjà noté par l'auteur.

Corrections faites par le scout : `KrakieStatus` accepte désormais une pose de fin (`donePose`, `trophee` par défaut ou `inquiete`), ce qui sert à la carte HermiT (voir L32). Aucun changement de comportement pour les usages L29.

skill: rien
