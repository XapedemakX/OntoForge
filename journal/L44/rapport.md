# L44 : rapport de la phase 2 (implémentation) — application sur téléphone

Agent : mobile. Décision : D-L44-01 (`journal/decisions.md`). Plan : `plan.md`. Mesures : `avant/` (phase 1) et `apres/` (`mobile_audit.mjs --out=apres`, mêmes écrans, mêmes appareils). Recette : `tools/recette/mobile_l44.mjs`.

## Ce qui est fait
- Barre d'onglets Accueil · Ontologie · Requêtes · Arbitrer (badge) · Plus (carte métier en tête, « Sur ordinateur », « M'envoyer le lien »), en-tête court, plus de tiroir ni de bandeau « consultation ».
- Feuille du bas écrite à la main (aperçu, moitié, plein ; poignée, croix, clavier, lecteur d'écran), appui long, fiches de classe et de propriété.
- Graphe et carte métier au doigt (pincer, glisser, toucher, appui long, « Tout voir », recherche qui centre, légende repliée, nœuds non déplaçables par accident). @xyflow/react reste en 12.8.4.
- Modification limitée depuis la fiche : sous-classe, propriété (attribut ou relation), renommer et décrire ; mêmes opérations `ops`, verrou `If-Match` et journal inchangés ; lecteur sans aucun bouton de modification.
- Arbitrage en cartes (un toucher pour valider la recommandation, application à la règle avec annulation de 5 s), requêtes en cartes, Krakie en bouton fixe de 56 px et panneau plein écran, accueil « À faire maintenant », projets en liste puis création en feuille.
- Cibles de 44 px et champs de 16 px sous pointeur grossier (tablettes comprises), clair et sombre, fr et en, `prefers-reduced-motion`.
- Docs : guide fr / en « Sur téléphone et tablette » (5 captures par langue), CHANGELOG fr / en, aide de Krakie (`help_map` : `mobile`, route `plus`), `lots/L44.md`, D-L44-01.
- Aucun changement de backend (hors `help_map.json`), aucune dépendance ajoutée.

## Avant / après (version web, comme Cloud Run, parcours Automaint, mêmes 17 à 19 écrans)
| Mesure | iPhone 15 avant | après | Pixel 7 avant | après | iPad mini avant | après |
|---|---|---|---|---|---|---|
| Cibles interactives < 44 px | 359 / 407 (88 %) | 22 / 302 (7 %) | 415 / 466 (89 %) | 22 / 324 (7 %) | 493 / 542 (91 %) | 63 / 531 (12 %) |
| Hauteur de l'en-tête (écrans de projet) | 115 px | 52 px | 115 px | 52 px | 82 px | 55 px |
| Textes coupés | 26 | 1 | 26 | 1 | 33 | 33 |
| Champs de saisie < 16 px | 32 | 0 | 47 | 0 | 36 | 2 |
| Éléments recouverts par Krakie | 19 | 8 | 9 | 9 | 16 | 14 |
| Débordement horizontal | 0 | 0 | 0 | 0 | 0 | 0 |

Les « après » restants sont presque tous des arêtes et nœuds du graphe (contenu de canevas, qui se zoome) : la recette `mobile_l44.mjs`, qui les dispense, mesure 100 % de cibles ≥ 44 px sur 13 écrans, sur les trois appareils, en local et en web (seuil demandé : 95 %). Ce qui reste recouvert par Krakie est le bouton fixe qui flotte au-dessus du contenu (le défilement le dégage ; fin de page avec 84 px de marge). Les 33 textes coupés de l'iPad sont les étiquettes tronquées du graphe large, inchangées.

## Recette mobile_l44.mjs (local et web ; iPhone 15, Pixel 7, iPad mini)
Onglets et retour, mise en page large conservée sur iPad, glisser et pincer (l'échelle change : graphe ×3, carte ×3), toucher qui ouvre la fiche, appui long, pas de déplacement accidentel, recherche, ajout d'une sous-classe puis présence dans le modèle (24 → 25), renommer, arbitrage en un toucher, Krakie (56 px au-dessus de la barre, feuille), cibles, champs, débordement, console et CSP, lecteur (compte `bob`, version web) sans modification et refusé par l'API. Résultat : tout vert (une échéance de chargement du lecteur a été fiabilisée).

## Autres vérifications
`npm run build` ; `e2e_ui.mjs` 30/30 ; `l35_sidebar` 43/43, `l36_business_map` 32/32, `l37_aquarium`, `l38_settings_krakie` 37/37, `tour` 50/50, `english_scan` 0 suspect, `l40_partage`, `l42_admin`, `l43_password` verts ; `test_help_map`, `test_docs_bilingual`, `test_assistant_context` (52 tests) verts. Recettes adaptées parce que D-L44-01 change le comportement du téléphone : `l35_sidebar` (section 6 : plus de tiroir), `l38_settings_krakie` (bouton fixe et panneau plein écran), `tour` (visite à 800 px ; sur téléphone elle n'est ni lancée ni proposée).

## Corrigés en cours de route
Libellés manquants (clés i18n), bouton Krakie vide puis masquant « Valider ce choix » (remontée `data-ag-lift`), libellés coupés au milieu d'un mot, liste de projets sous le formulaire, premier bloc de « Plus » écrasé à 0 px, arbitrage resté sur « Perdus » vide après la dernière décision, barre du haut de l'iPad passée sur deux lignes par les cibles de 44 px.

## Ce qui reste
- **À VÉRIFIER sur un vrai iPhone (Safari)** : clavier virtuel (`visualViewport`), zones sûres, appui long sans menu natif (les émulations Playwright ne les reproduisent pas fidèlement).
- Pluriels « constat(s) » laissés pour le passage de l'humaniseur ; badge d'Arbitrer (42) compte aussi un point sans option que la pile n'affiche pas (41).
- Exports, Versions, Modèle (Cytoscape), Paramètres, Administration, Conformité : lisibles et sans débordement, cibles de 44 px, mais pas encore recomposés en cartes comme l'arbitrage et les requêtes.
- Cadrage initial du graphe : l'étiquette de gauche peut être rognée avant « Tout voir ». Notice de génération de la carte métier masquée sur téléphone. Visite guidée absente du téléphone.
- Seuil : 700 px retenu au lieu de 760 px (à confirmer par Jerem, voir D-L44-01).
- Le relais local des recettes renvoie parfois un 502 quand une navigation interrompt une requête : sans effet sur l'application.
