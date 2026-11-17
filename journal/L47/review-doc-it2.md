verdict: OK
bloquants:
non-bloquants:
  - Chiffres vérifiés par le calcul sur automaint : 48 -> 19 (Neo4j) et 42 -> 31 (Curiosity) exacts (guide fr/en, CHANGELOG fr/en, rapport, fix-it1) ; 8 groupes de décision par cible exacts ; « dont 11 sans choix à faire » de l'écran : recette A1 OK.
  - Liste des règles reclassées par cible : conforme au code actuel (O09 et D09 : deux cibles ; D13 et O10 : Neo4j) dans guide fr/en, CHANGELOG, RULES.md §2, CONTRACTS §18 et D-L47-01.
  - Captures : analyse-branche fr/en ajoutée et déclarée dans sizes.json ; légendes recalées (groupes par racine). Les images ont été relues par la recette (écran 02 conforme au texte). Captures de journal/L47/screens restaurées après ma recette ; supprimer les `ko-*` (traces d'échec, voir review-scout-it2).
  - À reprendre après correction du bloquant curiosity : le guide (§ constats sans choix) et RULES.md disent que O09 est « conservé comme validation » et que le connecteur « échoue sur violation » pour D13 : le code généré ne contrôle ni O09 (forme restriction) ni D13 cardinalité (NotChecked). Recaler texte, chiffres éventuels et captures (analyse-synthese, analyse-regle-appliquee, exports-*) sur le nouveau classement.
skill: doc-bilingue-captures : régénérer les captures après tout changement de classement (les chiffres figurent dans l'image).
