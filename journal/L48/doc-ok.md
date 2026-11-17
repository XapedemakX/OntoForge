verdict: OK (après corrections ci-dessous)
vérifié :
  - Vérifié le 17/11 sur master (3ab285f) : test_docs_bilingual, test_help_map et test_english verts (55 réussis) ; ancres {#id} et parité fr/en des guides (test) ; captures citées présentes dans docs/guide/img/fr et img/en (script).
  - CONTRACTS §18 (= L48) : limites (2 Mo par fichier, 10 Mo cumulés, 50 fichiers, 400 tables, 1 024 colonnes, 8 s) conformes à importers/limits.py ; options, routes et codes 409 stale_preview / 422 missing_digest relus contre api/schema_import.py.
  - Guide fr/en, section {#import-schema} : libellés « Voir l'aperçu de l'import (sans IA) » et « Importer depuis une base ou un schéma » identiques à fr.json / en.json ; limites identiques au code.
  - help_map : entrée schema-import, ancre présente.
corrections faites :
  - CONTRACTS §18 : « bad_options » précisé (422 si ce n'est pas un objet, 413 au-delà de 200 000 caractères, api/schema_import.py).
  - api.md et api.en.md : routes d'import absentes ; ajout au récapitulatif et d'une section {#import-schema-api}, fr et en.
non repris (déjà signalés, non bloquants) : le message d'avis degraded_type (« la précision est perdue ») nuance la phrase du guide sur la complétion des dates ; « bornes typées comme la colonne » (CONTRACTS) à relire avec review-shacl-it2.
humaniseur : fait (docs/guide/utilisateur.md et utilisateur.en.md : section « Importer un schéma SQL, CSV ou JSON Schema » ; docs/guide/CHANGELOG.md et CHANGELOG.en.md : entrée L48). Contrôle avant/après identique pour code, nombres et libellés.
