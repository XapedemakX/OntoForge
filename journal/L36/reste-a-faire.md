# L36 : reste à faire (non bloquant)

Non-bloquants des revues scout et W3C non traités par L36c (`rapport-corrections.md`), repris ici après la contre-relecture du 15 nov. 2026. Aucun ne bloque la clôture.

- Scout 4 : la note du cadre (« Partagent : r1 → T1, … ») est répétée sur chaque flèche de cadre (`render.ts:51`). La mettre une seule fois (titre du cadre ou inspecteur).
- Scout 5 : pour styler une relation il faut d'abord créer un scénario ; l'inspecteur le dit sans proposer de bouton « Créer un scénario ».
- Scout 6 : « Réorganiser » applique directement (annulable) alors que zones et cadres passent par un aperçu ; au minimum signaler dans l'infobulle que les positions non épinglées sont recalculées.
- Scout 8 : volume « 0 » affiché partout sur l'exemple automaint (lecture ambiguë) ; afficher « — » quand la source est l'ontologie sans individus.
- Scout 2 (reliquat) : le bandeau « consultation » apparaît deux fois sur mobile (haut de page et inspecteur) ; pas de pincement pour zoomer.
- Scout 3 (reliquat) : à l'ajustement, libellés d'arête et sous-titres de zone peu lisibles ; facteur de taille minimale de police ou zoom initial par zone.
- W3C 7 : une relation fusionnée en `both` n'affiche que le premier nom sur la carte ; le nom de l'inverse n'est visible que dans l'inspecteur.
- Skills à mettre à jour (remarques des revues) : `product-discovery` (« un élément créé mais vide doit survivre à un rechargement ») ; `technical-documentation` (« chaque comportement visible cité dans la doc se retrouve par grep dans le code »).
