# L45 : relectures croisées

## Scout (UX) : OK
- Sélecteur « Modèle de Krakie » : lisible, 44 px, fixe au-dessus de la saisie, pas coupé (captures guide et recette, iPhone et Pixel). Le libellé « Mock (démonstration) · mock » répète « mock » : cosmétique, à nettoyer plus tard.
- Panneaux : replié = titre + description grise, ouvert = titre seul, comme annoncé. Chevrons clairs. Les descriptions sont utiles, pas du remplissage.
- Raccourcis : absents sous 700 px (accueil, bouton Krakie), la barre d'onglets suffit.
- Réserve : les légendes du guide citent des repères « 1 », « 2 » absents des captures (mobile-krakie, mobile-panneaux).
- `mobile_l45.mjs` (ports 9061/5071, mode local, iPhone 15) : tout vert.

## Doc : OK
Guide fr/en, CHANGELOG fr/en et help_map concordent avec le code et le rapport ; ancres intactes. `test_help_map` et `test_docs_bilingual` : 44 passés.

## Humaniseur : OK
Textes fold.* et mob.* et sections de doc relus : pas de tic à corriger, aucun texte modifié. Clé `mob.dash.more` supprimée (fr et en) : plus aucune référence ; JSON valide.

## Vérifications
`npm run build` OK.
