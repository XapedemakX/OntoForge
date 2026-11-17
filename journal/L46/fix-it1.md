# L46 : correctifs de l'itération 1 (revue deploy KO)

Date : 17/11/2026. Réponse à `journal/L46/review-deploy-it1.md`.

## Bloquants
1. `annotated-doc` 0.0.6 (10/11/2026) remplacée par 0.0.5 (28/07/2026) dans `backend/constraints.txt`.
2. `typing-inspection` 0.4.5 (04/11/2026) remplacée par 0.4.4 (12/08/2026). Les deux restent compatibles avec fastapi 0.133.0 et pydantic 2.10.3.
3. `journal/L46/rapport.md` : la colonne « Publication » porte maintenant la date PyPI de chaque ligne ; la phrase sur les deux semaines est corrigée.

## Non-bloquants traités
- En-tête de `constraints.txt` remis sur plusieurs lignes ; la référence au test de cohérence pointe vers `tests/test_sec_network.py`.
- Job CI `backend` : `pip install -c backend/constraints.txt -e "backend[dev]"` (tests sur les versions transitives des images).
- `docs/veille/normes.md` : fastapi 0.133.0 et python-multipart 0.0.31 indiqués comme versions en usage (colonnes « dernière version » inchangées).
- Rapport : mention Python 3.13 (venv) contre 3.12 (images).

## Non traités
- Étape CI informative dans un venv séparé pour pip-audit : sans conséquence, laissée telle quelle.
- Avertissements de dépréciation (anyio, pyparsing) : à surveiller.
- Ajout de la vérification des dates de publication au skill `deploiement-cloud-run-powershell` : fichier hors périmètre de secu ; la règle est déjà dans le skill `audit-securite-cve-cwe` (§6), à compléter avec la mention « transitives comprises ».

## Preuves (venv `.venv-l46`)
`pip check` propre ; `pytest -q` : 1307 réussis ; `pip-audit -r backend/constraints.txt --no-deps --disable-pip` : aucune vulnérabilité ; `pip install --dry-run -c backend/constraints.txt -e "backend[dev]"` résout sans conflit.
