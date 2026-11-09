# Rapport L28 : documentation intégrée et aide en contexte

Pilote : lead front. Statut : livré, relectures demandées.

## Livré
- Écran Documentation (`frontend/src/screens/documentation/`, `frontend/src/lib/docs.ts`, `codeHighlight.ts`) : `docs/guide/*.md` embarqués par import Vite `?raw` (un chunk par fichier), rendu `marked` 18.1.1 (déjà épinglé) et coloration maison. Sommaire, recherche (insensible casse et accents), ancres stables, liens `.md` internes, mobile. Version `.en.md` si elle existe, sinon bandeau « Documentation available in French only ».
- Bouton « ? » de l'en-tête ; table écran vers page#ancre dans un seul fichier `backend/ontoforge/assistant/help_map.json` (lu par le front et par Krakie), testée par `backend/tests/test_help_map.py`.
- Krakie : intention « aide » (fr/en) dans le repli déterministe et dans le prompt LLM ; action `kind: "help"` ; bouton « Ouvrir l'aide ». CONTRACTS mis à jour.
- Visite : étape `docs` (20 étapes, borne de `tour.mjs` relevée).
- Build : Dockerfiles (frontend et Cloud Run) copient `docs/guide` et `help_map.json` ; compose passe le contexte à la racine ; `.dockerignore` laisse passer `docs/guide`.

## Vérifications
pytest 877 OK ; build OK ; `l28_docs.mjs` 45/45 ; `e2e_ui.mjs` 30/30 ; `tour.mjs` 47/47 ; `english_scan.mjs` 0 suspect. Captures : `journal/L28/screens/`.
Exception déclarée dans `english_scan.mjs` : contenu marqué `data-doc-fallback` (doc française en mode en) ; le bandeau reste scanné.

## Points d'attention
- Clés i18n `docs.*` (le préfixe `doc.*` appartient à l'import de document). J'avais d'abord écrasé `doc.pages` ; restauré avant toute écriture suivante.
- Le dépôt contient des modifications d'autres agents non liées à ce lot ; seuls les fichiers L28 sont commités.
- Aucune version anglaise de la doc n'existe : le mode en affiche le français.

## Relectures demandées
- scout (UX : écran, bouton « ? », carte d'aide, mobile)
- doc (exactitude de la section « Documentation intégrée et aide », résumés de `help_map.json`)
- humain (style de la section et des résumés), puis doc vérifie le sens
