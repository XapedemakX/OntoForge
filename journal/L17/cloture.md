# L17 - Clôture : Vue liste, Shapes, Requêtes

## Livré
- **Vue liste** (`screens/ontology-list/`) : arbre et onglets, fiches classe, propriétés et individu, saisie rapide, Krakie contextuelle, mobile < 900 px.
- **Shapes** (`screens/shacl/`) : liste groupée, grille alignée, édition en ligne, diff de génération, validation avec lien vers la shape, Krakie. Aperçu par `dry_run` sur `POST /shacl/generate` (remplace l'ancien aller-retour PUT /shapes).
- **Requêtes** : endpoint temporaire en mémoire (`POST /query/endpoint-test`, `endpoint` en ligne pour `/query/run` et `/query/values`), valeurs possibles sans endpoint (`GET /query/options`, `known` dans `/query/suggest`), filtre « est l'un de », autocomplétion. Nouveau logo (`shell/Logo.tsx`).
- Documentation : guide utilisateur (Vue liste, SHACL, Requêtes), CONTRACTS §2 et §6, `api.md`, `limites.md`, `CHANGELOG.md`, README.

## Tests
- Backend : 567 verts (dont 8 nouveaux dans `test_query_options.py`).
- Recette API : 38/38.
- Recette UI (Playwright) : 30/30. Captures `journal/L17/screens/`.

## Limites connues
- Vue liste : faits d'individus, équivalences et expressions complexes en lecture seule.
- Shapes : contraintes motif, plage et liste lisibles mais non éditables en ligne.
- Requêtes : autocomplétion de libellés mélangeant français et anglais.
- Prompt LLM non éprouvé sur un vrai fournisseur (voir L16).
- Logo : recadrage CSS du sprite, léger flou possible hors multiples entiers.
