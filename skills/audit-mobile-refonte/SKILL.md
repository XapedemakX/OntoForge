---
name: audit-mobile-refonte
description: Auditer une application web sur téléphone et tablette (appareils émulés, mesures de cibles tactiles, débordements, gestes) puis cadrer une refonte mobile avec maquette avant implémentation ; à utiliser quand un utilisateur dit que l'appli est « inutilisable sur mobile » ou avant de toucher au gabarit, à la navigation ou aux feuilles du bas.
---

# Audit et refonte mobile

Retour d'expérience L44 (OntoForge). Références : `tools/recette/mobile_audit.mjs`, `journal/L44/plan.md`.

## 1. Décider d'abord ce que le mobile sert
Lister les usages réels (consulter, chercher, lire une fiche, regarder un graphe, valider une recommandation, partager, petite modification) et ce qui reste confortable seulement sur grand écran (édition lourde, éditeur de fichiers) : accessible mais simplifié, avec un renvoi clair (« plus confortable sur ordinateur », bouton « m'envoyer le lien »). Une décision de seuil est tracée (ici : 700 px de large ou paysage sous 500 px de haut ; les tablettes en version ordinateur).

## 2. Audit mesuré
Script qui **mesure sans échouer**, sur iPhone, Android, iPad mini, portrait et paysage, clair et sombre, avec chaque rôle :
- éléments interactifs visibles, cibles < 44 px, champs < 16 px (zoom automatique iOS) ;
- débordement horizontal de la page, textes coupés ;
- éléments masqués par un bouton flottant, la barre d'onglets ou le clavier ;
- erreurs de console et violations de CSP ;
- captures (réduites ensuite à ~480 px et quantifiées avant commit) regardées soi-même.
Faire l'audit en local **et** sur la reproduction de la version déployée (authentification, CSP, latence ; voir `recette-playwright-par-lot` §4). Sortie : `audit-mobile.md` (constats numérotés P1…, captures avant).

## 3. Principes de refonte
- Barre d'onglets en bas (4 à 5 destinations, pouce) + menu « Plus » ; en-tête court avec retour ; pas de bandeau latéral sur téléphone.
- Information progressive : un écran = une tâche ; cartes et listes plutôt que tableaux larges ; détails dans une feuille du bas (aperçu / moitié / plein écran, Échap, focus piégé, `inert` sur le fond, mouvement réduit, suivi du clavier par `visualViewport`).
- Graphe au doigt : glisser, pincer (table des pointeurs actifs, `zoomAt`), toucher = fiche, appui long (500 ms, annulé au-delà de 8 px) = actions, recherche qui centre le nœud, « tout voir ». Ne pas rendre React à chaque image : appliquer la vue au DOM.
- Cibles ≥ 44 px sous `(pointer: coarse)`, champs 16 px, zones sûres (`viewport-fit=cover`, `env(safe-area-inset-*)`), `prefers-reduced-motion`, pas de défilement horizontal.
- Un seul arbre d'écrans avec variante compacte (`useMobile()`), pas une seconde application ; aucune dépendance nouvelle sans décision.

## 4. Méthode
1. Audit (mesures + captures) → 2. **maquette courte avant/après** soumise à la personne quand la navigation change → 3. plan par étapes autonomes (socle, navigation, écran par écran) → 4. implémentation → 5. recette `mobile_*.mjs` (gestes via CDP `Input.dispatchTouchEvent`, absence de débordement, cibles, console propre) → 6. guide fr/en avec section « Sur téléphone et tablette » et captures.
Relectures : UX, humaniseur (pluriels, registre), doc, sécurité si CSP ou cookies changent.

## 5. Pièges
- L'ellipse CSS sur des nœuds de largeur fixe coupe les noms : mesurer le texte (`canvas.measureText`) et plafonner.
- Un nœud déplaçable au doigt se déplace par accident : `nodesDraggable` faux en tactile, déplacement activé par appui long.
- Le bouton flottant d'un assistant cache la barre d'onglets : le placer au-dessus (`calc(var(--tabbar-h) + var(--safe-bottom) + 14px)`) et le ranger quand une feuille ou le clavier est présent.
- Deux paliers de seuil (largeur et pointeur grossier) : ne pas confondre « petit écran » et « tactile ».
