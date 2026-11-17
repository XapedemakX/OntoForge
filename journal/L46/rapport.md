# L46 : montée de FastAPI, Starlette et python-multipart, pip-audit en CI

Pilote : secu. Décision : D-L46-01 (Jerem, 16/11/2026). Date : 17/11/2026. Branche `lot/L46`.

## Versions avant et après

| Paquet | Avant | Après | Publication (PyPI) | Remarque |
|---|---|---|---|---|
| fastapi | 0.115.6 | 0.133.0 | 24/02/2026 | première version dont la dépendance `starlette` n'a plus de borne haute (0.128.3 : `<1.0.0`) |
| starlette | 0.41.3 (transitive) | 1.3.1, désormais épinglée en direct | 12/06/2026 | corrige en dernier la CVE-2026-54283 |
| python-multipart | 0.0.19 | 0.0.31 | 04/06/2026 | corrige en dernier la CVE-2026-53540 |
| annotated-doc | absente | 0.0.5 | 28/07/2026 | transitive de FastAPI (`>=0.0.2`) ; la 0.0.6 (10/11/2026) a moins de deux semaines |
| typing-inspection | absente | 0.4.4 | 12/08/2026 | transitive de FastAPI (`>=0.4.2`) ; la 0.4.5 (04/11/2026) a moins de deux semaines |
| html5rdf | non relevée | 1.2.1 | 30/10/2024 | déjà installée (transitive de rdflib), ajoutée aux contraintes, aucune montée |
| pip-audit (CI) | n/a | 2.10.1 | 10/06/2026 | outil de CI |

Au 17/11/2026, chaque ligne ci-dessus a plus de deux semaines (dates PyPI, champ `upload_time`) et est épinglée par `==`. Aucune autre dépendance n'a changé (D-L21-02 reste en vigueur : graphql-core et pytest, dev seulement, non montés). `pip check` : aucune incompatibilité.

## CVE corrigées (13, production)

- starlette : CVE-2025-54121, CVE-2025-62727, CVE-2026-48710, CVE-2026-54282, CVE-2026-54283, CVE-2026-48818, CVE-2026-48817.
- python-multipart : CVE-2026-24486, CVE-2026-40347, CVE-2026-42561, CVE-2026-53540, CVE-2026-53539, CVE-2026-53538.

`pip-audit -r backend/constraints.txt --no-deps --disable-pip` : « No known vulnerabilities found ». Sur le gel complet de l'environnement de test (avec l'extra `dev`) restent 3 CVE hors production : graphql-core 3.2.5 (CVE-2026-75507, CVE-2026-75508) et pytest 8.3.4 (PYSEC-2026-1845), signalées en CI sans bloquer.

## Changements de code

Aucun changement dans `backend/ontoforge` : le code (`main.py`, `security.py`, `collab/middleware.py`, `api/analysis.py`) s'exécute tel quel avec Starlette 1.3.1 et FastAPI 0.133.0 (middlewares, `UploadFile`, `FileResponse`, `TestClient`, gestionnaires d'erreurs, `SpaStatic`). Contrats `docs/CONTRACTS.md` inchangés.

Fichiers modifiés : `backend/pyproject.toml`, `backend/constraints.txt`, `backend/tests/test_sec_network.py` (nouveau test `test_sec09_server_dependencies_at_or_above_fixed_versions`), `.github/workflows/ci.yml` (job `audit-dependances` : production bloquant, développement informatif), `.gitignore` (`.venv-l46/`), `tools/recette/e2e_ui.mjs` (interpréteur lisible via `PYTHON`, comme `l40_partage.mjs`), `skills/audit-securite-cve-cwe/SKILL.md`, `docs/guide/contribuer*.md`, `docs/guide/CHANGELOG*.md`, `journal/securite/audit-2026-11-15.md` (non publié).

## Résultats

- Venv dédié `.venv-l46` (Python 3.13 ; les images utilisent Python 3.12, installation rejouée en 3.12 par la revue deploy). Environnement global non touché.
- Avant montée : `pytest -q` 1306 réussis. Après : 1306 réussis, puis 1307 avec le nouveau test (5 min), y compris après le correctif de l'itération 1.
- Recette `e2e_ui.mjs` (ports 9146 / 5146, interpréteur du venv L46) : 30/30.
- Recette `l40_partage.mjs` (mêmes ports) : verte à deux reprises sur trois. L'échec observé est un délai d'attente de `.page` après un changement de hash côté navigateur ; le même échec intermittent se produit sur les versions d'origine (1 échec sur 5 passes de contrôle), donc non lié à la montée.
- `docker compose build` : non exécuté, aucun démon Docker dans cet environnement. Substitut : installation `pip install -c backend/constraints.txt ".[reasoner]"` dans un venv neuf, gel comparé au fichier de contraintes (identique, hors `html5rdf` qui y manquait déjà et a été ajouté). À rejouer par Jerem ou par deploy sous Docker.

## Points à relire

- query : `netguard` et la couche SSRF sont inchangés (aucun fichier de `backend/ontoforge` modifié) ; httpx 0.28.1 inchangé.
- deploy : `backend/Dockerfile` et `deploy/cloudrun/Dockerfile` installent avec `-c constraints.txt` (fichier mis à jour, pas de changement de Dockerfile) ; reconstruire l'image et vérifier le démarrage non root et les envois de fichiers.
