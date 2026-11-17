# L50 — revue scout (UX), itération 1

verdict: OK

Vérifié : libellé du sélecteur Krakie, cartes Paramètres › Fournisseurs LLM / Endpoints à 393 px, légendes du guide, liste des écrans non recomposés. Recette `mobile_l50.mjs` rejouée (ports 9450 / 5450) : 6/6. Capture de Paramètres › Fournisseurs à 393 px relue (iPhone 15, web, administrateur) ; rien d'écrit dans le dépôt, captures versionnées intactes (`git status` propre).

bloquants:
  - aucun

non-bloquants:
  - Libellé Krakie : « Mock (démonstration) » une fois (capture fr relue, recette OK) ; fournisseur réel inchangé « Claude (test) · claude-sonnet-5-5 ». Le test `!name.includes(model)` couvre aussi un fournisseur dont le nom contient déjà le modèle. OK.
  - Cartes Fournisseurs : ordre Nom, Type, Modèle, URL de base, Clé d'API, Par défaut, puis boutons = ordre des colonnes ; les cellules vides (mock : modèle, URL, clé) sont masquées, le mock n'affiche que Nom / Type / Par défaut. Lisible. Deux redondances : « Par défaut : ★ Par défaut » (libellé + pastille identiques) et « Délai (s) : 30 s » côté endpoints (unité en double). Proposition : pas de `data-l` sur la cellule « Par défaut » quand c'est la pastille, et libellé « Délai » sans « (s) ».
  - Endpoints : la première cellule (bouton radio « Actif ») n'a pas de `data-l` ; sur une carte, un endpoint non actif n'affiche qu'une pastille radio sans mot. Ajouter `data-l={t('settings.ep.active')}` à cette cellule.
  - Trou de recette : `mobile_l50` ne crée aucun endpoint SPARQL, donc les cartes Endpoints (`EndpointsSection.tsx`) ne sont jamais rendues dans la recette ni dans ma capture (liste vide, « Aucun endpoint SPARQL »). Le code est symétrique à celui des fournisseurs et je ne vois pas d'erreur de lecture, mais la revendication « cartes étiquetées » du rapport n'est prouvée que pour les fournisseurs. Ajouter un `POST` d'endpoint dans la recette lors d'un prochain lot.
  - Page Paramètres : en cliquant (Playwright) l'onglet « Endpoints SPARQL », partiellement rogné à droite, le contenu de la page s'est décalé vers la gauche (bandeau d'onglets scrollé, carte coupée dans la capture). Probablement un effet de `scrollIntoView` automatique de Playwright, non démontré pour un vrai toucher ; à contrôler sur appareil.
  - Écrans non recomposés : la liste du rapport est complète et honnête. Aucun écran inutilisable oublié (aucun débordement de page, 20 écrans). Incohérence à signaler : les tableaux `ver-table` (Paramètres › Versions, écran Versions) sont décrits comme « empilés sans libellés » alors que le même défaut (valeurs nues) a fait recomposer les Fournisseurs LLM. Lisibles, donc non bloquant ; à ranger en tête d'un lot ultérieur. Conformité et Modèle cible : défilement interne (413/497 px dans 367 px), acceptable pour des tableaux de lecture.
  - Administration › Journal d'administration : « non revérifié en détail » reste un trou de preuve (pas de débordement uniquement).
  - Légendes du guide : 7 légendes `mobile-*.png` réécrites sans numéros, fr et en, cohérentes avec les images (aucune pastille). `limites-mobile.png` n'avait pas de numéro. Attention aux guillemets droits dans les légendes anglaises : voir revue doc (bloquant côté doc).

skill: product-discovery : ajouter « une recomposition en cartes mobile se prouve en rendant un jeu de données qui exerce tous les tableaux (liste non vide), pas seulement l'écran vide ».
