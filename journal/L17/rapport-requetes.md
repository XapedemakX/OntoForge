# L17 — rapport requêtes (agent query)

Tests backend : tous verts (8 nouveaux dans `tests/test_query_options.py`). Build : mes fichiers compilent ; `tsc -b` rouge uniquement à cause de `screens/ontology-list/index.tsx` (`kindName`, autre lot) au moment du build.

## Livré
- (a) Endpoint temporaire : option « + Endpoint temporaire… » dans le sélecteur de l'écran Requêtes -> formulaire en ligne (URL, auth none/basic/bearer, secret, graphe par défaut, Tester, Utiliser, case « Enregistrer dans les paramètres » via POST /settings/endpoints). État en mémoire (`tempEndpoint.ts`), ni localStorage ni serveur ; vérifié. Backend : `endpoint` en ligne pour `/query/run` et `POST /query/values`, `POST /query/endpoint-test`, mêmes garde-fous (UPDATE 403, URL invalide 422, secret jamais renvoyé).
- (b) Valeurs possibles : `GET /query/options` (ontologie seule), `known` dans `/query/suggest`. Phrase guidée : étape vers une classe énumérée/peuplée (<= 40) ajoute un filtre « est l'un de » à cocher (Diesel, Essence, Hydrogène, Électricité) ; bouton « est l'un de… » sinon ; complété par `/query/values` si endpoint ; autocomplétion des filtres texte (ontologie puis endpoint) ; liste à cocher aussi pour les « parmi » de propriétés ; la classe racine affiche « N connu(s) ».
- (c) Logo : `shell/Logo.tsx` (tête de Krakie recadrée du sprite accueil, animée au survol/focus seulement, wordmark IBM Plex Sans 600 « Onto » clair / « Forge » pieuvre), variante `mark` dans l'en-tête mobile.
- CONTRACTS §6 complété.

## Vérification Playwright (automaint, port 5177/8017, endpoint rdflib du scratchpad)
Sans endpoint : liste à cocher et autocomplétion présentes ; avec endpoint temporaire : Tester OK, 10 lignes (Diesel), aucune trace dans localStorage ni /settings/endpoints. Captures : `journal/L17/screens/requetes-*.png`, `logo-*.png`.

## Limites
- Pas de version « tête seule » du sprite : recadrage CSS (taille entière en pixel art, léger flou possible hors multiples).
- Pas de barre latérale repliée dans le shell : la variante `mark` sert en-tête mobile.
- Autocomplétion de libellé : libellés de toutes les langues (fr et en mélangés).
- `i18n/*.json` réécrits en entier (même format, clés `q.tmp.*`, `q.f.oneof*`, `q.known`).
