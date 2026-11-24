verdict: OK
bloquants:
  - aucun. Chapitres 08 à 14, 16 et la section « Côté serveur » du 02 relus ; `backend/tests/test_dev_docs.py` et `test_docs_bilingual.py` verts (203 passés) ; EXPECTED_MISSING vidé ; plan du contrat respecté partout.
non-bloquants:
  - [docs/dev/16-securite.md, ligne « En-têtes », l.33] la CSP existe en deux copies (`frontend/security-headers.conf`, servie par nginx en local, et `backend/ontoforge/security.py::CSP`, comparées par `test_sec_network.py`). Le chapitre ne parle que de la seconde : ajouter une phrase et un renvoi vers le chapitre 17 (§9, Pièges).
  - [docs/dev/11-assistant-krakie.md, tableau des genres d'action, l.46-54] le front connaît 9 genres (`frontend/src/assistant-global/store.ts::ActionKind` : ops, proposal, shapes, guided_query, navigate, versions, help, settings_goto, settings_test) ; le tableau n'en liste que 7 (les deux de l'écran Paramètres sont cités plus bas, l.83). Ajouter « voir plus bas » dans le tableau, ou les deux lignes.
  - [docs/dev/11-assistant-krakie.md, l.118] « le rendu et l'application dans le front » : préciser les fichiers (`frontend/src/assistant-global/run.ts`, `ActionCards.tsx`) pour que « comment ajouter un genre d'action » soit complet côté front.
  - [docs/dev/14-imports-schemas.md, l.94] « Rejeu exact : le front doit renvoyer les mêmes fichiers et options, sinon 409 » : exact (`frontend/src/api.ts::api.schemaApply` renvoie fichiers, options, base et `digest` via `schemaForm`) ; ajouter ce renvoi au front.
  - [docs/dev/12-comptes-partage-admin.md, l.67-71] cohérent avec le chapitre 02 §4.2 et §4.3 (version, 409 / 428, battement de 20 s, expiration de 60 s) : un renvoi croisé vers `02-communication-front-back.md#if-match` éviterait la double description.
  - [docs/dev/02-communication-front-back.md, §6.1] « seize routeurs » : compté, c'est exact (`ROUTERS`). Rien à changer.
  - [docs/dev/08-generateurs.md, l.41-42] zip classé écriture sans historique : cohérent avec `frontend/src/api.ts::api.zip` et le chapitre 02 §4.6. Rien à changer.
skill: technical-documentation : un chapitre qui décrit une liste fermée partagée avec le front (genres d'action, codes d'erreur, événements) la compare à la liste du front par grep avant de la déclarer complète.
