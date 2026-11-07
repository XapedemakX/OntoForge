# L18 : visite guidée « Découvrir OntoForge »

Demande de Jerem : un tutoriel de l'outil façon tour guidé, éléments en surbrillance. Moteur maison, sans librairie.

## Ce qui est livré
- `frontend/src/tour/` : `controller.ts` (état, navigation, attente des cibles, `window.ontoforgeTour`), `Overlay.tsx` (voile + découpe box-shadow, halo teal animé, bulle avec Krakie), `steps.ts` (18 étapes), `TourHost.tsx` (monté dans la coque : `?tour=1`, proposition au premier projet, création de la démo), `TourCard.tsx` (carte du tableau de bord), `tour.css`.
- Moteur : positionnement auto haut/bas/gauche/droite avec repli dans l'angle de la cible si elle est trop grande, suivi de la cible à chaque image (resize, scroll, animations), `scrollIntoView` avec zone libre (bulle mobile), attente de la cible 4 s puis étape centrée sans découpe, clavier ← → Échap, focus piégé dans la bulle, région `aria-live`, retour du focus à la fin, mouvement réduit respecté. Une cible peut être une liste de sélecteurs : union du premier élément visible de chacun.
- Étape : `{id, route, target, title, body, placement, action, waitFor}` + extensions `pose`, `drawer` (ouvre le tiroir de menu sur mobile), `leave` (remise en état).
- Écrans : uniquement des attributs `data-tour` (Dashboard, Editor, ontology-list, shacl, Validation, Conformance, Analysis, Model, Exports, queries/*, AssistantDock). Exceptions assumées : Shell (bouton, enveloppe du sélecteur de cible, écoute de l'ouverture du tiroir) et Dashboard (carte `TourCard`).
- i18n : clés `tour.*` et `tour.s.<id>.t/.b` en fr et en.
- Recette : `node tools/recette/tour.mjs` (43 contrôles : desktop 1440x900 clavier, sans projet, mobile 390 px) ; captures dans `journal/L18/screens/`.

## Corrections issues des captures
- Cible « un constat » : l'union de tous les constats ouverts couvrait l'écran, la cible est maintenant le premier élément visible par sélecteur.
- En-tête de bulle : « Étape n/N » et « Passer la visite » passaient à la ligne ; mise en page refaite (ligne de méta, points de progression en dessous).

## Non vérifié
- Mode sombre et langue anglaise (pas de capture) ; lecteur d'écran réel ; Firefox/Safari.
- Éditeur sur mobile (< 768 px, lecture seule) : la saisie rapide n'existe pas, l'étape est centrée.
- Proposition automatique au premier projet : testée par le build et e2e_ui (30/30), pas de capture dédiée.
