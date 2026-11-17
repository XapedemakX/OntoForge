verdict: OK
bloquants:
non-bloquants:
  - Recette A3b relue et rejouée (ports 9447 / 5447) : le champ « pourquoi » est vide après changement d'option et l'ancienne raison n'est attribuée à aucune décision. Recette complète 10/10 OK (A1 31 / 19 constats, 8 groupes ; A2, A3, A3b, A4, E1-E3, L1-L2). Captures versionnées restaurées après la recette.
  - FindingCard (Analysis.tsx) : une raison saisie avant le premier choix est conservée, vidée seulement si l'option change : bon comportement.
  - Ligne « Option recommandée : C04 : Fusionner dans les feuilles · C02 : Aplatir sur la racine concrète » sous chaque groupe : lisible sur la capture 02, le bouton « Appliquer la recommandation à toute la branche (3) » est désormais sans ambiguïté. Le texte d'aide n'apparaît qu'une fois au-dessus des groupes (sur automaint). Il est rendu une fois par section de sévérité (Analysis.tsx, `byRoot(g).length > 0` dans la boucle lost/review) : il s'affichera deux fois si des constats d'héritage « perdus » existent aussi ; à sortir de la boucle.
  - Reste (déjà signalé, renvoyé à L50) : champ « raison » replié, raison sur mobile, indicateur « N à arbitrer encore » sur la carte du dossier.
  - journal/L47/screens/ko-A1-*, ko-A2-*, ko-A3-*, ko-A3b-*, ko-E1-* : captures d'échec de la recette (3 identiques, 22610 octets, pages vides) versionnées dans le commit it1. Ce sont des traces de run raté, pas des preuves ; à supprimer du dépôt (et ignorer `ko-*`).
  - Rappel : avec le bloquant curiosity (O09 / D09), les groupes et compteurs de l'écran changeront ; rejouer la recette et régénérer les captures après la correction.
skill: product-discovery : un champ de justification se vide quand la décision qu'il justifie change (déjà noté) ; un texte d'aide commun se place hors des boucles de sections.
