# L37b : intégration de l'aquarium de Krakie (piste A)

Retour de Jerem sur L37 : « le design de son aquarium ne me plaît pas, on dirait pas intégré ». Piste A appliquée.

## Fait
- Halo d'eau (.aq-water) supprimé. Récif en pixel art collé à `bottom: env(safe-area-inset-bottom)`, ~180 px (120 sur mobile), fondu sur les côtés gauche et droit seulement, lit de roches continu sans ligne de sol, corail et étoile adoucis.
- Couleurs lues dans design/tokens.css (--accent, --panel, --ink, --lost, --review-edge, --line-strong), relues si le thème change. Pixel art sans rotation ni cisaillement (L30).
- Krakie nage dans 201×150 px (120×90 mobile), au-dessus du récif ; 3 micro-bulles au plus, rares, montent ~120 px en s'estompant.
- Zone cliquable = Krakie + récif (bouton en pointer-events:none, activé par un test de zone ; relais du clic pour le tactile). Focus clavier : anneau discret qui suit Krakie. aria-label inchangé, pastille décalée (top 2 px, right 10 px) hors du chemin de nage.
- Une seule boucle rAF, pause onglet caché, image fixe si prefers-reduced-motion.
- Mini-carte de l'éditeur remontée de 72 à 112 px (editor.css, seul fichier hors assistant-global).

## Vérifié
- `npm run build` OK ; `node tools/recette/l37_aquarium.mjs` (ports 8975/4975) OK ; e2e_ui.mjs 30/30.
- Captures (avant dans `avant/`, après dans `screens/`) : desktop clair/sombre sur tableau, ontologie, requêtes, exports, documentation ; panneau ouvert ; mobile 390 clair/sombre ; zoom clair/sombre. Rien d'important masqué : le récif n'occupe que ~30 px en bas à droite, pied de page de l'éditeur sans contenu à cet endroit.

## Points d'attention
- Les clics sur la zone récif (~30 px de haut, 180 px de large) sont captés par Krakie ; les boutons de pied de page placés exactement là seraient masqués (aucun constaté).
- Le GIF de L37 est régénéré dans journal/L37b/aquarium.gif.
