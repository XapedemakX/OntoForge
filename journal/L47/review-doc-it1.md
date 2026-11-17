verdict: OK
bloquants:
non-bloquants:
  - Exactitude vérifiée contre le code : mesures 48 -> 19 / 42 -> 13 (reproduites), codes D13 / O09 / O10 / D09, 280 caractères, rôles (lecteur lit le dossier, n'écrit pas), `lost` jamais reclassé, D10 et K02 laissés à revoir, routes et anchors help_map (`dossier-de-justification`, `constats-sans-choix`, `arbitrer-par-branche` présents en fr et en), parité fr/en des guides et du CHANGELOG, `lang` du dossier. « Imposer à toute la branche … y compris sur les constats déjà décidés » : exact (route /branch).
  - Captures non régénérées : `docs/guide/img/fr/analyse-synthese.png` (légende « un groupe de constats par règle »), `analyse-regle-appliquee.png`, `analyse-neo4j.png` et `exports-*.png` ne montrent ni les groupes de branche, ni le champ « pourquoi », ni la carte Dossier, ni les compteurs 13/19. Légende de analyse-synthese désormais inexacte pour l'héritage. Relancer `tools/docs/captures.mjs` avant clôture (règle du lot : doc-ok sans captures périmées).
  - Après la correction curiosity (O10 / D13), reprendre la liste « D13, O09, O10, D09 » du guide, du CHANGELOG, de RULES.md et de help_map, et les chiffres 19 / 13.
  - Rapport : « 14 nouveaux tests / 1320 passed » : `test_l47_justification.py` compte 11 fonctions et 12 cas collectés ; corriger le chiffre ou le décompte.
  - Guide : dire que la raison saisie avant le choix est conservée mais qu'elle est effacée quand l'option change (après correction scout) ; dire que les décisions prises sur téléphone n'ont pas de raison.
  - Guide : le dossier prétend que « ne perd rien » ; rappeler dans la section constats sans choix que « validation » reste un renforcement du monde ouvert (le dossier le dit déjà en introduction).
  - Humaniseur non passé, doc-ok.md absent : normal à ce stade.
skill: doc-bilingue-captures : ajouter « légende de capture à relire quand le regroupement d'un écran change, même sans nouvelle capture ».
