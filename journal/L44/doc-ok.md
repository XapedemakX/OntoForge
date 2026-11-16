# L44 : capture du graphe mobile validée

Après la correction « il manque les liens dans le graphe » (16/11) :
- Cause : en lecture seule (téléphone), la poignée source des nœuds n'était pas rendue ; React Flow ne trace aucune arête sans poignée mesurée. Elle est maintenant toujours rendue, inerte et invisible en lecture seule (`parts.tsx`, `editor.css`).
- Cadrage initial lisible : zoom 0,7, centré sur la classe la plus connectée (nœuds de 36 px de haut au moins) ; « Tout voir » montre l'ensemble. Nœud sélectionné : voisinage en évidence, reste estompé.
- Captures `docs/guide/img/{fr,en}/mobile-graphe.png` regardées : sous-classes (flèches creuses) et relations avec libellés lisibles, nœuds et étiquettes entiers. Capture d'arbitrage régénérée (rien sous le bouton Krakie, accents graves rendus en code).
- Garde-fous : `tools/recette/mobile_l44.mjs` échoue si aucune arête n'est visible au chargement ou si un nœud fait moins de 32 px de haut.
