verdict: OK (après corrections ci-dessous)
vérifié :
  - Vérifié le 17/11 sur master (3ab285f) : test_docs_bilingual, test_help_map et test_english verts (55 réussis) ; ancres {#id} et parité fr/en des guides (test) ; captures citées présentes dans docs/guide/img/fr et img/en (script).
  - CONTRACTS §19 (= L49) : règles BP08 à BP16 et leurs niveaux relus contre conformance/practices.py ; 30 versions (MAX_RELEASES) ; opérations set_deprecated, set_annotations, set_version_iri ; routes /releases et /metadata conformes à api.md / api.en.md (section {#versions-publiees-api}, relue en it4).
  - Guide fr/en, section {#bonnes-pratiques-fiche-versions} : libellés « Fiche » / « Entity card », « Déprécier » / « Deprecate », « Ne plus déprécier » / « Undeprecate », « Enregistrer la version » / « Record the version » identiques à fr.json / en.json ; « Garder avec drapeau » et « Entités dépréciées » identiques au code (catalog.py, report.py).
  - RULES.md et regles fr/en : A03 en review. architecture fr/en : practices.py cité.
  - help_map : entrée best-practices (ancre bonnes-pratiques-fiche-versions).
corrections faites :
  - BP10 : le guide ne citait que le statut « stable » pour une entité dépréciée ; le code (et CONTRACTS) signale « stable » et « testing ». Texte corrigé, fr et en.
  - Aperçu sans changement : le guide disait qu'aucune version n'est proposée ; le comportement réel (CONTRACTS, api.md) est : pas de niveau, enregistrement désactivé tant qu'aucun numéro n'est saisi. Texte recalé, fr et en.
humaniseur : fait (docs/guide/utilisateur.md et utilisateur.en.md : section « Bonnes pratiques : fiche, dépréciation, versions » ; docs/guide/CHANGELOG.md et CHANGELOG.en.md : entrée L49). Le long paragraphe sur la dépréciation est découpé en phrases courtes, sans changer un fait.
