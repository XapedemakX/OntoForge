# L20 : vérification documentaire (doc)

verdict: OK, aucun écart à corriger.

Vérifié contre `frontend/src/game/` (Launcher.tsx, GameOverlay.tsx, strings.ts), `frontend/src/shell/Logo.tsx`, `journal/L20/rapport.md` et `review-scout-it1.md` :

- `docs/guide/utilisateur.md`, section « Easter egg » : dit que le jeu existe, qu'il ne touche à aucune donnée de projet et qu'un indice est caché dans Paramètres. Elle ne donne aucun déclencheur. Les affirmations (clavier ou doigt, pause quand l'onglet est masqué, mouvement réduit, Échap) correspondent au code (`visibilitychange`, `prefers-reduced-motion`, `Escape`).
- Recherche du code Konami, du mot déclencheur et du nombre de clics dans `docs/`, `skills/`, `README.md`, `CLAUDE.md`, `lots/` : aucune occurrence. Le code n'apparaît que dans `Launcher.tsx` et dans le rapport de lot, ce qui est accepté.
- Commandes affichées (`game.keys`, fr et en) : flèches ou A / D, glisser, P, M, Échap. Elles correspondent aux touches gérées (Q accepté, Entrée ou Espace pour commencer, non listés à l'écran, sans conséquence).
- Texte d'intro corrigé par le scout (ordre S, P, O) : présent dans `strings.ts`, fr et en.

Remarque : la section n'a pas été modifiée, car `docs/guide/utilisateur.md` est en cours de modification par L19 (§11) et L25 (§9).
