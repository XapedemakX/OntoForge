verdict: OK (après corrections ci-dessous)
vérifié :
  - Vérifié le 17/11 sur master (3ab285f) : test_docs_bilingual, test_help_map et test_english verts (55 réussis) ; ancres {#id} et parité fr/en des guides (test) ; captures citées présentes dans docs/guide/img/fr et img/en (script).
  - Chiffres automaint rejoués sur le code fusionné (analyze) : Neo4j 48 -> 19 constats à arbitrer, 8 groupes, dont 4 perdus ; Curiosity 41, 9 groupes, 1 perdu ; reclassés : Neo4j D13 x13, O09 x10, O10 x5, D09 x1 ; Curiosity D09 x1 seulement (les 10 O09 d'automaint restent à arbitrer). Guide, CHANGELOG, RULES.md §2 et CONTRACTS §20 concordent.
  - CONTRACTS §20 (= L47) : NO_CHOICE, HIERARCHY_RULES (C02 C03 C04 C10), MAX_REASON 280, routes decisions / branch / justification relus contre catalog.py, engine.py, notes.py.
  - Libellés du guide fr/en (« Appliquer la recommandation à toute la branche », « Imposer à toute la branche », « Enregistrer la raison » / « Save reason », « Sans choix à faire : … », « Dossier de justification » / « Justification file ») identiques à fr.json et en.json.
  - RULES.md et regles.md/regles.en.md : A03 en review, étape « Reclassement » cohérente.
  - help_map : entrées analysis, exports, justification ; ancres présentes dans les guides.
corrections faites :
  - docs/guide/api.md et api.en.md : les routes du lot manquaient (corps étendu de PUT /decisions, POST /decisions/{cible}/branch, GET /justification/{cible}). Ajout au récapitulatif et d'une section {#arbitrage-justification-api}, fr et en.
  - Légende et alt de mobile-accueil (hors lot, relevé ici) : « À faire maintenant » n'existe plus dans l'interface (la capture montre la carte des constats perdus) ; texte recalé, fr et en.
humaniseur : fait (docs/guide/utilisateur.md et utilisateur.en.md : sections « Constats sans choix à faire », « Arbitrer par branche et dire pourquoi », « Dossier de justification » ; docs/guide/CHANGELOG.md et CHANGELOG.en.md : entrée L47). Ni fait, ni chiffre, ni libellé de bouton, ni ancre modifiés (contrôle des blocs de code, nombres et libellés avant/après).
