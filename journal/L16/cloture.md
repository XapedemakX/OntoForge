# L16 - Clôture : assistant global Krakie

## Livré
- Backend : `assistant/agent.py` (contexte, validation stricte des actions, repli sans LLM), `context` sur `/assistant/chat`, `POST /assistant/shapes/apply`. Actions : `ops`, `proposal`, `shapes`, `guided_query`, `navigate`. CONTRACTS §4.
- Frontend : `frontend/src/assistant-global/` (bouton flottant, Ctrl+K, panneau redimensionnable, contexte retirable, suggestions, cartes d'actions Appliquer / Annuler, conversation partagée avec l'écran Assistant).
- Intégration L17 : l'écran Requêtes charge la requête guidée reçue de Krakie ; contexte déclaré par l'éditeur, le tableau de bord, la Vue liste, Shapes et Requêtes.
- Documentation : `docs/guide/utilisateur.md` (Krakie, l'assistant global), `limites.md`, `CHANGELOG.md`, README.

## Tests
- Backend : 567 verts.
- Recette API : 38/38.
- Recette UI (Playwright) : 30/30. Script `tools/recette/l16_assistant.mjs`, captures `journal/L16/screens/`.

## Limites connues
- Prompt LLM non éprouvé sur un vrai fournisseur (pas de réseau) ; réponse non JSON affichée comme texte.
- Annulation linéaire : « Annuler » seulement pour la dernière modification.
- Repli sans LLM limité aux tournures documentées.
- Le panneau recouvre la partie droite de l'en-tête quand il est ouvert.
