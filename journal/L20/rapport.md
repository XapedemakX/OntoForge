# L20 : easter egg « Krakie's Triple Catch »

Demande de Jerem : « easter egg : un jeu avec Krakie ».

## Concept
Krakie nage au fond d'un lagon pixel art. Des sujets (ambre, coins arrondis), prédicats (menthe, en flèche) et objets (lavande, carrés) tombent. Il faut les attraper dans l'ordre sujet, prédicat, objet pour former un triplet valide (petit domaine « garage » : `Mechanic fixes Car`, `Car hasPart Engine`…). Chaque triplet rejoint un graphe dessiné en fond, avec ses nœuds et son arête étiquetée.

- Dangers : « constat perdu » (bulle rouge, −1 vie) et « IRI cassée » (pilule grise fissurée, −1 vie et chaîne perdue). 3 vies, invulnérabilité brève après un coup.
- Bonus : INF (inférence : attrape le prochain élément à ta place) et SHACL (bouclier contre un coup).
- Règles de chaîne : un élément incohérent se dissout sans effet ; un sujet attrapé en cours de chaîne la relance.
- Difficulté : la vitesse de chute augmente tous les 2 triplets (niveau), la part de dangers aussi. Mouvement réduit : vitesse ×0,6, pas de secousse ni de flash, bulles et animations figées.
- Fin : Krakie content (≥ 400 points ou record) ou inquiet, avec une phrase du métier (« owl:sameAs ton meilleur score ! » si égalité, « owl:differentFrom » si record). Score et meilleur score en localStorage (try/catch), préférence de son aussi.

## Commandes
- Ouvrir : code Konami n'importe où (hors champ de saisie), ou taper « krakie » hors champ, ou 5 clics rapides sur Krakie dans le logo. Indice : « Krakie aime les codes rétro. » en bas de Paramètres.
- Jouer : ← → ou A/D (Q accepté), glisser sur le terrain au doigt ou à la souris, boutons ← → sur écran tactile ou étroit. Entrée ou Espace pour commencer, P pause, M son (coupé par défaut), Échap quitter.
- Pause automatique quand l'onglet est masqué. Le clavier n'est écouté que pendant que le jeu est ouvert ; le déclencheur reste passif (aucun `preventDefault`). Pendant le jeu, l'appli derrière est rendue `inert`.

## Technique
Tout est dans `frontend/src/game/` : `Launcher.tsx` (seul morceau dans le bundle principal, ~1,5 ko), `GameOverlay.tsx` (surcouche plein écran, portail, aria), `engine.ts` (canvas 2D logique, boucle requestAnimationFrame, échelle entière + `image-rendering: pixelated`), `font.ts` (police 3×5), `sprites.ts` (réutilise les SVG animés de Krakie : accueil, graphe, content, inquiet), `audio.ts` (WebAudio), `content.ts`, `strings.ts` (chaînes fr/en injectées dans l'i18n via `extendDicts` au chargement du chunk, donc hors bundle principal). Seules additions hors dossier : indice i18n (2 clés), `extendDicts` dans `i18n/index.tsx`, compteur de clics dans `Logo.tsx`, monture dans `App.tsx`, ligne d'indice dans `Settings.tsx`.

## Vérification
- `node tools/recette/l20_game.mjs` : Konami, indice, champ de saisie sans déclenchement, clavier libre jeu fermé, partie jouée par un pilote (lit `window.__ontoforgeGame`, actif seulement si `localStorage['ontoforge.game.debug']='1'`), pause, fin de partie, Échap, variantes « krakie » et 5 clics, mobile tactile + mouvement réduit.
- Captures : `journal/L20/screens/` : `01-depart.png`, `02-partie.png`, `03-fin.png` (desktop), `04-mobile-depart.png`, `05-mobile-partie.png`.
- Taille : le jeu est un chunk à part (~31 ko, 12 ko gzip). Le bundle principal grandit d'environ 1,5 ko à cause de mon lot ; le reste de l'écart avec la base vient du lot « éditeur de fichiers » mené en parallèle.

## Demande de relecture UX à l'éclaireur produit
Merci de relire, en jouant 5 minutes :
1. Difficulté et rythme : trop dur, trop facile ? Un élément incohérent sans effet (sauf sujet) est-il assez lisible ?
2. Lisibilité sur mobile (échelle ×2) : étiquettes en police 3×5, boutons ← →, contraste des pilules.
3. Découvrabilité : l'indice dans Paramètres est-il trop discret ou trop évident ? Le Konami est ignoré dans les champs de saisie : acceptable ?
4. Ton des phrases de fin (fr et en) : drôles sans exclure un lecteur non spécialiste ?
5. Faut-il persister le choix du son (c'est le cas) ou repartir muet à chaque partie ?
