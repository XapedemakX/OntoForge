# Revue scout L20 : Krakie's Triple Catch (it1)

verdict: OK

Lu : rapport, `frontend/src/game/`, 5 captures. Rejoué : `node tools/recette/l20_game.mjs` (tout OK) et `npm run build` (vert).
Je n'ai pas joué à la main : le jugement sur le rythme vient du code (vitesse de départ 49 px/s, apparition ~1 s, un élément attendu garanti à l'écran) et des captures.

bloquants:
  - aucun.

non-bloquants:
  - [GameOverlay.tsx / strings.ts] Lisibilité des 10 premières secondes : la carte de départ ne disait pas que l'ordre S puis P puis O est imposé, ni à quoi sert le suivi S/P/O en haut. **Corrigé par moi** : texte d'intro fr/en (« S, puis P, puis O, dans cet ordre : le suivi en haut indique le prochain. Les autres éléments se dissolvent sans effet »).
  - [engine.ts spawn] Des distracteurs portent le même mot que l'attendu (« Mechanic » est à la fois sujet ambre et objet lavande, visible sur 02-partie.png). Seules la couleur et la forme les distinguent. Piste : retirer des distracteurs les libellés présents dans une autre catégorie, ou garder la même catégorie pour un même mot.
  - [engine.ts HUD] Les trois cases S/P/O montrent seulement la case attendue (pointillé), pas le mot déjà attrapé. Afficher le maillon attrapé dans sa case rendrait la chaîne lisible d'un coup d'œil, et sert la démo.
  - [engine.ts rendu] Le libellé d'une arête du graphe de fond passe sous le HUD (« GARAGE » écrasé par le score sur 02-partie.png) et le « +125 » chevauche le sprite attrapé. Cosmétique : cantonner le graphe sous la barre S/P/O.
  - Mobile : jouable (boutons ← → de 56 px, glisser au doigt, pas de débordement, recette mobile + mouvement réduit verte). Les étiquettes en police 3×5 à l'échelle ×2 restent petites sur 05-mobile-partie.png mais lisibles. Chaque pilule a un contraste sombre sur fond clair très suffisant.
  - Accessibilité : correcte. Dialogue modal, app `inert`, focus rendu à la fermeture, annonces `aria-live`, boutons étiquetés, pause quand l'onglet est masqué, Échap. Mouvement réduit : ×0,6, ni secousse ni flash. Manque : aucun mode de jeu sans glissement ou réflexe (on joue à l'ouïe seule d'aucune façon), acceptable pour un easter egg.
  - Déclencheurs : sans gêne. Aucun `preventDefault`, ignorés dans les champs de saisie, donc taper « krakie » dans les textareas de l'assistant (global et écran) ne l'ouvre pas, vérifié par la recette. Hors champ, les seuls raccourcis de l'appli sont Suppr, F2 et Échap : pas de collision. Réserve : « krakie » tapé hors champ ouvre le jeu, ce qui est voulu mais peut surprendre en démo si l'on tape sans focus.
  - Indice : la ligne en bas de Paramètres est discrète mais suffisante. Konami ignoré dans les champs : acceptable.
  - Démo en 30 secondes : réaliste. Cinq clics sur le logo, Entrée, premier triplet vers 8-10 s, niveau 2 vers 20 s. Prévoir de dire le but en une phrase (« les triplets RDF, version jeu »). Le son coupé par défaut est le bon choix en salle.
  - Son : persister le choix est cohérent, rien à changer.
  - Ton de fin : drôle et accessible (« un graphe sans arêtes, c'est juste une liste »). Deux phrases supposent une connaissance OWL/SHACL (« owl:Nothing », « cardinalité minimale ») ; acceptable pour le public cible.

corrections faites par le scout:
  - `frontend/src/game/strings.ts` : texte d'intro `game.intro` (fr et en). Gardes : `npm run build` vert, `l20_game.mjs` vert.

skill: Revue d'un jeu ou d'un easter egg : vérifier d'abord que l'objectif s'énonce en une phrase sur la carte de départ et que l'état de la tâche (ici la chaîne S/P/O) est visible en permanence ; vérifier qu'aucun distracteur ne partage un libellé avec une cible de catégorie différente.
