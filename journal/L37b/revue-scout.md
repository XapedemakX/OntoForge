# L37b : revue scout (aquarium de Krakie, piste A)

verdict: OK (aucun bloquant ; réserves non bloquantes ci-dessous)

Vérifié : captures de `journal/L37b/screens/` relues (bureau clair et sombre : ontologie, exports ; mobile 390 clair et sombre ; zoom clair) ; code de `frontend/src/assistant-global/` (`Aquarium.tsx`, `AssistantDock.tsx`, `dock.css`) ; `npm run build` OK ; `node tools/recette/l37_aquarium.mjs` (ports 8975/4975) sortie 0.

## Clavier
- Le bouton `.ag-fab` reste un vrai `<button>` focusable (Tab, Entrée, Espace) même avec `pointer-events: none` ; `aria-label` et `title` inchangés ; Ctrl+K ouvre le panneau.
- Focus visible : anneau `.aq-ring` posé sur Krakie par `transform` à chaque image, `outline: none` sur le bouton. Présent et discret, mais voir réserve 1.

## Mouvement réduit
- `prefers-reduced-motion` : plus de boucle `requestAnimationFrame`, Krakie immobile au centre, bulles figées, pas de ballottement ni d'inclinaison ; le changement de préférence en cours de session est écouté (`onMq`). L'animation d'entrée du panneau et les points de réflexion sont aussi neutralisés dans `dock.css`.
- Onglet caché : la boucle est arrêtée.

## Rien de masqué
- Le récif ne fait qu'environ 30 px de haut sur 180 px de large collé au bord bas ; sur l'éditeur il tombe sur la barre « Saisie rapide » à un endroit sans contenu, la mini-carte a été remontée. Aucun bouton de pied de page recouvert dans les captures.
- Krakie nage au-dessus du contenu (201 x 150 px) et peut passer sur du texte (capture exports : elle recouvre un bout de la ligne 34 du code). Comportement normal d'un bouton flottant, mais voir réserve 3.
- Les clics ne sont captés que sur Krakie et le récif (`hit`, classe `aq-hit`) ; le reste de la zone laisse passer la souris, ce qui supprime l'ancien rectangle mort.

## Mobile
- Version réduite 120 x 90 px, échelle 1, récif de 22 px ; sur la capture 390 px le récif est à peine visible et ne masque que le coin bas droit. Pas de débordement horizontal. Le relais du clic (`onClick` en capture sur `window`) couvre le toucher sans mouvement préalable.

## Réserves non bloquantes (à planifier, pas des KO)
1. Contraste de l'anneau de focus : `box-shadow` de 2 px en accent à 55 % d'opacité, sur un fond variable (contenu de la page) ; il peut tomber sous 3:1. Passer à l'accent plein avec un liseré de la couleur du panneau.
2. La pastille `.ag-badge` (nombre de propositions en attente) n'est pas annoncée : l'`aria-label` du bouton la remplace. Ajouter le nombre à l'étiquette (« Ouvrir l'assistant, 2 propositions »).
3. Un clic sur du contenu placé sous la zone récif ou sous Krakie ouvre l'assistant à la place (le relais en capture appelle `stopPropagation`). Aucun cas constaté, noté dans le rapport du lot ; à garder en tête pour tout futur bouton de pied de page.
4. Après la fermeture du panneau, le focus ne revient pas sur Krakie (le bouton est recréé). Comportement antérieur à L37b.
5. En mouvement réduit, un intervalle de 400 ms continue de redessiner (utile le temps que les images chargent) ; il pourrait s'arrêter une fois les images prêtes.
