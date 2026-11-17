verdict: OK
vérifié :
  - Vérifié le 17/11 sur master (3ab285f) : test_docs_bilingual, test_help_map et test_english verts (55 réussis) ; ancres {#id} et parité fr/en des guides (test) ; captures citées présentes dans docs/guide/img/fr et img/en (script).
  - Versions : fastapi 0.133.0, starlette 1.3.1, python-multipart 0.0.31 dans backend/constraints.txt, conformes au rapport.
  - docs/guide/contribuer.md et contribuer.en.md : la phrase sur pip-audit en CI est exacte (job « Audit des dépendances » de .github/workflows/ci.yml) ; CHANGELOG fr/en (entrée L46, sans changement visible pour l'utilisateur) conforme.
  - Aucun changement de contrat (CONTRACTS inchangé par ce lot).
corrections faites : aucune.
humaniseur : fait (docs/guide/CHANGELOG.md et CHANGELOG.en.md, entrée L46 relue : déjà directe, aucun changement).
