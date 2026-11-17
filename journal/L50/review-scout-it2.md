# L50 — revue scout (UX), itération 2

verdict: OK

Relu : `LlmSection.tsx`, `EndpointsSection.tsx` (diff 914cbf7), `tools/recette/mobile_l50.mjs`. Recette rejouée sur les ports 9550 / 5550 (jamais 5061), sans `pkill` global, sans rien installer : 9/9 OK, dont les trois nouvelles vérifications (endpoint de test créé, 201 ; cartes Endpoints ; pas de doublon « Par défaut »). Le `dist` du front est plus récent que les sources modifiées. Après la recette : aucun processus restant sur ces ports, `git status` propre (la recette n'écrit aucune capture, rien à restaurer).

bloquants:
  - aucun

Points levés depuis l'it1 :
- Doublons retirés : la cellule « Par défaut » n'a plus de `data-l` quand elle porte la pastille (`LlmSection.tsx`) ; la recette compte 0 cellule avec pastille et libellé.
- Libellés : « Délai » sans « (s) » (la recette lit `["Nom","URL","Authentification","Graphe par défaut","Délai"]`) ; la cellule radio reçoit `Actif` quand l'endpoint n'est pas actif.
- Cartes Endpoints enfin rendues par la recette : thead masqué, 5 cellules étiquetées, libellés attendus présents. Le trou signalé à l'it1 est comblé. L'hôte de l'endpoint de test est dans la liste d'egress, aucune requête n'est émise.

non-bloquants:
  - [tools/recette/mobile_l50.mjs, étape 3b] L'unique endpoint créé est actif, donc la cellule radio n'a pas de libellé et le libellé « Actif » (non actif) n'est pas exercé : la recette ne le prouve pas. Créer un second endpoint dans un prochain lot (le premier reste actif) et ajouter `Actif` à la liste attendue.
  - Restent ouverts, déjà notés à l'it1 : tableaux `ver-table` à recomposer, onglet « Endpoints SPARQL » rogné à contrôler sur appareil, Journal d'administration non revérifié en détail.

skill: product-discovery : une recomposition en cartes se prouve en rendant un jeu de données qui exerce chaque variante de cellule (actif et non actif, par défaut et non par défaut), pas seulement une liste non vide.
