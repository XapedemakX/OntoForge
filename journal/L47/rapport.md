# Rapport L47 : dossier de justification et arbitrage par racine

Pilote : lead. Branche `lot/L47`. Décisions : D-L47-01 à D-L47-03 (`journal/decisions.md`). Contrat : `docs/CONTRACTS.md` §20.

## Mesure : décisions humaines nécessaires sur automaint (cible < 25) — recalculée après la revue curiosity (it2)
Définition : constats `review` + `lost` sans décision (même définition que le badge « restants » de l'écran Arbitrer), mesurés par `analyze(automaint.ttl, automaint-shapes.ttl, cible, {})`. « Groupes » = une décision par racine de hiérarchie ou par règle (un clic de l'écran Arbitrer).

| Cible | Avant L47 | Après L47 (constats) | Groupes de décision | dont perdus (toujours humains) |
|---|---|---|---|---|
| Neo4j | 48 | **19** (< 25) | 8 | 4 (C07 ×3, O06) |
| Curiosity | 42 | **41** (≥ 25) | 9 | 1 (O06) |

Écart à la cible : après correction (D13, O10 et les O09 `exactly 1` reviennent à arbitrer pour Curiosity), Curiosity compte 41 constats, au-dessus de 25 ; la cible n'est tenue en constats que pour Neo4j. Elle est tenue pour les deux cibles si on compte des décisions groupées (8 pour Neo4j, 9 pour Curiosity). Question posée à Jerem dans D-L47-01.

Reclassés en `auto` : Neo4j D13 ×13, O09 ×10, O10 ×5, D09 ×1 (29) ; Curiosity O09 ×10, D09 ×1 (11).

## Livré
- Moteur : `catalog.NO_CHOICE` (O09 et D09 : deux cibles ; D13 et O10 : Neo4j seulement), `engine._reclassify` (`Finding.auto_reason`), `engine._attach_roots` (`Finding.root`). Jamais un `lost`.
- Trace : `Project.decision_notes`, `mapping/notes.py` (raison en une ligne, 280 car., compte, date, via). `PUT /decisions` accepte l'ancien et le nouveau corps ; `POST /decisions/{cible}/branch`.
- Dossier : `targets/justification.py`, `GET /justification/{cible}?format=html|md&lang=`, lecture seule (droits lecteur).
- Front : Arbitrer (groupes de branche, champ pourquoi, « décidé par », motif des auto, compteur de reclassés), Exports (carte du dossier).
- Doc fr/en (guide §9 et §11, CHANGELOG), help_map (analysis, exports, nouvelle entrée justification), RULES.md, CONTRACTS §18.

## Vérifications (après it1)
- `cd backend && /home/claude/venv/bin/python -m pytest -q` : **1319 passed**. `tests/test_l47_justification.py` : 11 fonctions de test, 11 cas collectés (reclassement par cible, lost jamais reclassé, hook mono-option, ancien format et raison, 422, projet sans notes, branche et protection des décisions d'un autre compte, dossier html/md échappés, anglais et lecture seule, droits lecteur, routes classées).
- Note d'environnement : le Python global sans fastapi ne lance pas les tests API ; `/home/claude/venv/bin/python` (rien installé).
- `npm run build` OK ; `l47_justification.mjs` (9147/5147) : **10/10** (A3b : changer l'option vide la raison) ; `e2e_ui.mjs` (9247/5247) : **30/30**.
- `mobile_l44.mjs` : seul KO « barre d'onglets présente (web) », présent aussi sur la base du lot (flake de premier chargement, voir it0).
- Captures du guide régénérées : analyse-synthese, analyse-constat, analyse-neo4j, analyse-regle-appliquee, exports-curiosity, exports-neo4j, exports-rapport (fr et en) et nouvelle `analyse-branche` ; les autres images, réécrites par l'optimiseur, sont restaurées. `docs/guide/img/sizes.json` mis à jour.

## Écarts d'oracle (samples/trap/expected-findings.yaml)
f-D09a, f-D09b, f-O09a, f-O09b : `review` → `auto` (deux cibles) ; f-D13, f-O10, f-O10b : `auto` pour Neo4j, `review` pour Curiosity (`severity` par cible). Rien d'autre.

## Points à relire
- neo4j / curiosity : `NO_CHOICE` revu (D13 et O10 : Neo4j seulement, motif nuancé) ; K02 volontairement non reclassé.
- secu : échappement HTML (`_h`, `html.escape` quote=True), Markdown (`_md`), CSP `default-src 'none'` en meta ET en en-tête, changement de `security.py` (conserve une CSP stricte posée par la route), route de lecture ouverte au lecteur (logins des décideurs visibles des membres du projet).
- scout / mobile : l'écran mobile (Deck) n'a pas de champ « pourquoi » (dit dans le guide) ; à décider pour L50.
- doc : humaniseur non passé.
- La raison est du texte libre d'un utilisateur affiché aux autres membres : échappée partout (HTML, Markdown, React).
