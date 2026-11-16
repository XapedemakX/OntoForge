# L44 — Plan d'implémentation mobile (phase 2, après validation de la maquette)

Agent : mobile. Ce plan découle de `audit-mobile.md` et de `maquette/index.html`. Il ne s'applique qu'après accord de Jerem.

## Principes de mise en œuvre

- **Point de bascule** : la mise en page « téléphone » s'applique sous 700 px de large, ou en paysage sous 500 px de haut. Le support d'un pointeur grossier (`(pointer: coarse)`), indépendant de la largeur, déclenche les tailles tactiles : cibles de 44 px au moins, champs en 16 px. L'iPad mini en portrait (768 px) garde donc le bandeau latéral replié et l'édition (constat P1), mais avec des cibles tactiles. Le seuil actuel de 900 px reste celui du tiroir sur ordinateur étroit.
- **Pas de nouvelle dépendance ni de montée de version** (D-L21-02). Les gestes reposent sur @xyflow/react 12.8.4, déjà installé, et sur les pointer events. Les feuilles du bas sont écrites à la main : pointer events, `transform`, `prefers-reduced-motion`.
- **Un seul arbre d'écrans.** Les écrans existants reçoivent une variante compacte (`useMobile()`). On ne crée pas une seconde application. Le routage par hash ne change pas, à une route près : `#/projet/<id>/plus`.
- **Contenu des textes** : français et anglais dans `i18n/fr.json` et `i18n/en.json`, écrits par fichier temporaire puis `os.replace`.

## Étapes

### Étape 1 — Socle (fin de lot possible en soi)
- `frontend/index.html` : `viewport-fit=cover` pour les zones sûres (encoche, barre d'accueil) ; `theme-color` clair et sombre.
- `frontend/src/design/tokens.css` : jetons `--tap: 44px`, `--tabbar-h: 56px`, `--ahead-h: 52px`, `--r-sheet: 18px`, `--safe-top` / `--safe-bottom` (`env(safe-area-inset-*)`), `--canvas`.
- `frontend/src/shell/kit.css` et `styles.css` : sous `(pointer: coarse)`, hauteur minimale de 44 px pour `.btn`, `.icon-btn`, les lignes de liste et les onglets ; `font-size: 16px` pour `input`, `select`, `textarea`.
- `frontend/src/shell/sidePref.ts` : `useMobile()` (`useMedia('(max-width: 700px), (max-height: 500px) and (orientation: landscape)')`) et `useCoarse()`.
- **Nouveau** `frontend/src/kit/BottomSheet.tsx` (+ `kit/sheet.css`) : positions « aperçu / moitié / plein écran », poignée glissable, voile, Échap, focus piégé et rendu à l'élément d'origine, `aria-modal`, `inert` sur le fond, mouvement réduit sans animation, suivi du clavier par `visualViewport`. Exporté par `kit/index.tsx`.
- **Nouveau** `frontend/src/kit/useLongPress.ts` : minuterie de 500 ms annulée si le doigt bouge de plus de 8 px ; menu contextuel natif bloqué sur la cible.

### Étape 2 — Navigation (le changement structurant)
- **Nouveau** `frontend/src/shell/MobileTabBar.tsx` : Accueil (`tableau`), Ontologie (`ontologie` ou `ontologie-liste`, dernière vue mémorisée), Carte (`carte-metier`), Arbitrer (`analyse`, pastille `pending`), Plus (`plus`). Rôle `navigation`, `aria-current`. Masquée quand le clavier est ouvert.
- **Nouveau** `frontend/src/shell/MobileHeader.tsx` : retour (vers la liste des projets depuis un onglet racine, vers l'écran parent sinon), titre, sous-titre « cible · périmètre » qui ouvre une feuille, une action à droite selon l'écran.
- **Nouveau** `frontend/src/screens/More.tsx` (route `plus`) : liste groupée tirée de `SCREENS`. L'étiquette « Sur ordinateur » vient d'un nouveau champ `desktop?: 'read' | 'full'` dans `registry.tsx`. On y trouve aussi le compte, les paramètres, l'aide, la visite guidée et l'administration.
- **Nouveau** `frontend/src/shell/ContextSheet.tsx` : cible Curiosity/Neo4j et périmètre, en remplacement du `Segmented` et du `select` de l'en-tête sur téléphone.
- `frontend/src/shell/Shell.tsx` : sur téléphone, plus de tiroir latéral ni d'en-tête dense. On rend `MobileHeader`, le contenu et `MobileTabBar`. Le bandeau `head.mobileReadOnly` est retiré. Il est remplacé par **`frontend/src/shell/DesktopHint.tsx`** : une bande basse, refermable, affichée sur les écrans `desktop`, avec « M'envoyer le lien » (copie du lien ou partage natif `navigator.share` si disponible). `CollabBar`, l'endpoint, l'aide, le thème, la visite et la déconnexion passent dans Plus ou dans le menu du compte.
- `frontend/src/shell/registry.tsx` : champs `mobileTab?` et `desktop?` ; aucun changement de clé de route.

### Étape 3 — Ontologie au doigt
- `frontend/src/screens/editor/Editor.tsx`, sur téléphone :
  - barre d'outils remplacée par **`editor/MobileGraphBar.tsx`** : bascule Graphe/Liste, bouton de filtres qui ouvre une feuille (vue Hiérarchie/Relations/Tout, périmètre, propriétés affichées, notation) ;
  - **recherche flottante** (`QuickInput`/`Tree` réutilisés) qui sélectionne puis centre le nœud avec `rf.setCenter(x, y, { zoom: 1, duration })` (durée 0 en mouvement réduit) ;
  - « Tout voir » (`rf.fitView`) et « Centrer » (`rf.setCenter` sur la sélection), à la place de `<Controls>` ; `<MiniMap>` masquée ;
  - props ReactFlow : `panOnDrag` (défaut), `zoomOnPinch` (défaut, vérifié à l'audit), `nodesDraggable={!readOnly && !coarse}` pour ne plus déplacer un nœud par accident, `selectNodesOnDrag={false}`, `zoomOnDoubleClick={false}` (déjà en place) ;
  - **appui long** : `useLongPress` posé sur le conteneur `.of-canvas` ; le nœud visé est retrouvé par `elementFromPoint(...).closest('.react-flow__node')` (attribut `data-id`). Il ouvre un menu dans une feuille : ajouter une sous-classe, ajouter une propriété, déplacer, masquer, centrer. « Déplacer » active `draggable` pour ce seul nœud jusqu'au relâchement ;
  - toucher le fond désélectionne et réduit la feuille ;
  - **libellés** : sur téléphone, le nom ne doit plus être coupé (aujourd'hui, ellipse CSS `.of-txt b` sur des nœuds de largeur fixe, voir `editor.css` et `layout.ts`) ; largeur du nœud calculée sur le libellé (mesure par `canvas.measureText`, à ajouter dans `geom.ts`), avec un plafond et un retour à la ligne au-delà.
- `frontend/src/screens/editor/Inspector.tsx` : rendu dans une `BottomSheet`. L'aperçu (nom, IRI, description, compteurs, « Fiche complète », « + Sous-classe ») est extrait dans **`editor/ClassPeek.tsx`**. La feuille entière garde l'inspecteur actuel.
- `frontend/src/screens/editor/Legend.tsx` : repliée par défaut sur téléphone, sous forme de puce « Légende ». La règle « ouverte au premier usage » (L26) reste valable sur ordinateur.
- `frontend/src/screens/ontology-list/*` : `ListPane` et `ClassSheet` en plein écran, avec les onglets Propriétés / Entrants / Analyse. Les pastilles de compteur deviennent des lignes de 52 px. Le bouton « Ajouter une propriété » est collé en bas. Les fiches de propriété (`PropSheets.tsx`) s'ouvrent dans une `BottomSheet`.

### Étape 4 — Carte métier au doigt
- `frontend/src/screens/bmap/BusinessMap.tsx` (le code des gestes est aujourd'hui dans ce fichier, pas dans `useBMap.ts`) :
  - **pincer** : table des pointeurs actifs (`Map<pointerId, {x, y}>`). À deux pointeurs, rapport des distances et appel à `zoomAt(f, milieu)`. Le glissement d'un nœud est annulé dès le second pointeur. Pas de rendu React par image : la vue est déjà appliquée au DOM (`applyView`) ;
  - appui long sur un type : mode « déplacer » (le glisser actuel). Sans appui long, glisser déplace toujours la vue ;
  - recherche flottante qui centre le type, « Tout voir » (`fitStart`).
- `frontend/src/screens/bmap/Panels.tsx` : panneaux dans une `BottomSheet`. Le scénario passe dans la feuille de recherche. L'export passe par le partage de l'en-tête.

### Étape 5 — Arbitrer
- **Nouveau** `frontend/src/screens/analysis/Deck.tsx` (et `deck.css`) : une carte par constat non arbitré, triée perdus d'abord puis par règle. Options en boutons radio, recommandée présélectionnée, « Pourquoi ? » dépliable (`rationale`, impact par cible). « Valider ce choix » et « Passer ». Quand la règle a plusieurs constats, « Appliquer aux N de la règle », avec annulation possible pendant 5 s (toast). Balayage horizontal pour naviguer seulement. Pastilles « À arbitrer / Perdus / Faits », recherche.
- `frontend/src/screens/Analysis.tsx` : sur téléphone, rend `Deck` ; le bilan chiffré se replie en une barre de progression. Même API (`api.analyze`, décisions existantes) : pas de changement de contrat backend.

### Étape 6 — Accueil, Projets, Krakie, autres écrans
- `frontend/src/screens/Dashboard.tsx` : carte « À faire maintenant » (une action), parcours en liste, activité. Le Krakie du tableau passe en petit.
- `frontend/src/screens/Projects.tsx` : liste d'abord ; le formulaire de création passe dans une `BottomSheet` ouverte par « + ». L'appui long sur une carte ouvre ses actions.
- `frontend/src/assistant-global/AssistantDock.tsx`, `Aquarium.tsx`, `dock.css`, sur téléphone :
  - **pas d'aquarium** ; bouton fixe de 56 px au-dessus de la barre d'onglets (`bottom: calc(var(--tabbar-h) + var(--safe-bottom) + 14px)`) ;
  - le bouton se range quand une feuille, un bouton collé ou le clavier est présent ;
  - le panneau devient une `BottomSheet` haute avec une puce de contexte ;
  - le choix du modèle part dans les Paramètres, le rappel clavier n'est plus affiché, le champ passe en 16 px.

  Sur ordinateur, l'aquarium reste tel quel. Le relais du clic (`hit()`) est revu pour que le récif ne capte plus un toucher destiné à un bouton visible.
- `frontend/src/screens/Model.tsx` (Cytoscape) : mise en page `fit` avec rembourrage et taille de police bornée ; boutons + / − / Ajuster de 44 px. Pas de changement de bibliothèque.
- `Exports`, `Queries`, `Versions`, `Shacl`, `Conformance`, `Settings`, `admin/Admin` : cibles et champs (étape 1), tableaux larges rendus en cartes sous 700 px. Les écrans marqués `desktop` (Fichiers, édition des Shapes, éditeur de requêtes) s'ouvrent en lecture avec `DesktopHint`.
- `frontend/src/collab/SharePanel.tsx` : rendu dans une `BottomSheet`, champs en 16 px.

## Recette mobile prévue (`tools/recette/`)

S'appuie sur `web_server.mjs` (version web avec authentification et CSP, plus `--local`) et réutilise la mesure de `mobile_audit.mjs`. Appareils : iPhone 15, iPhone SE (petit écran), Pixel 7, iPad mini en portrait et en paysage, iPhone 15 en paysage. Thèmes clair et sombre, fr et en, rôles administrateur, éditeur et lecteur.

| Script | Vérifie (critères bloquants) |
|---|---|
| `mobile_nav.mjs` | barre d'onglets présente sur les 5 destinations, `aria-current` juste, retour qui ramène au bon écran, pastille d'arbitrage = nombre de constats restants, Plus qui liste tous les écrans du registre, aucun tiroir latéral sous 700 px |
| `mobile_targets.mjs` | sur chaque écran : 0 cible interactive sous 44 × 44 px (liste d'exceptions justifiées), 0 champ sous 16 px, 0 débordement horizontal, en-tête ≤ 52 px, aucun élément interactif recouvert par le bouton Krakie, la barre d'onglets ou une feuille fermée |
| `mobile_graph.mjs` | éditeur : glisser change la translation sans déplacer de nœud ; pincer change l'échelle ; toucher ouvre l'aperçu ; appui long ouvre le menu ; « Tout voir » englobe tous les nœuds ; la recherche centre le nœud. Carte métier : les mêmes gestes, pincer compris. Pas de rendu React par image pendant un glissement (compteur de rendus instrumenté) |
| `mobile_arbitrage.mjs` | valider un constat depuis l'onglet en 2 touchers ; « Appliquer aux N » puis annuler ; balayage = navigation sans décision ; la décision est bien enregistrée par l'API ; le lecteur voit les cartes sans pouvoir valider |
| `mobile_krakie.mjs` | ouverture et fermeture (glisser vers le bas, voile, Échap), puce de contexte, champ en 16 px, feuille qui suit le clavier émulé (`visualViewport`), pas d'aquarium sous 700 px |
| commun | aucune erreur de console ni violation de CSP ; `prefers-reduced-motion` respecté (pas d'animation de centrage) ; captures regardées et rangées dans `journal/L44/apres/` |

Les gestes sont envoyés par CDP (`Input.dispatchTouchEvent`), comme à l'audit. Les captures suivies que réécrivent les recettes font l'objet d'un commit séparé : « recettes : captures régénérées ».

## Risques

- **Conflits entre gestes** sur le canevas : feuille du bas, glissement de la vue, balayage depuis le bord (retour iOS). Parade : la poignée de la feuille a sa propre zone ; `touch-action: none` est limité au canevas ; une marge de 20 px au bord gauche est laissée au navigateur.
- **Safari iOS** : les tests Playwright tournent sur Chromium. Le zoom des champs, `visualViewport`, `env(safe-area-inset-*)` et l'absence de `contextmenu` à l'appui long (d'où `useLongPress` plutôt que `onNodeContextMenu`) doivent être vérifiés sur un vrai iPhone, avec Jerem, sur https://ontoforge.ajlx.fr. À noter comme `À VÉRIFIER` dans le rapport.
- **Performance** : 24 classes passent sans difficulté, une ontologie de plusieurs centaines de nœuds beaucoup moins. Parades : `onlyRenderVisibleElements` de @xyflow/react, libellés masqués sous un certain zoom, aucun `setState` pendant les gestes de la carte métier.
- **Régressions sur ordinateur** : tout le comportement mobile est gardé derrière `useMobile()` / `useCoarse()`. On relance les recettes existantes (`e2e_ui.mjs`, `l35_sidebar.mjs`, `l36_business_map.mjs`, `l37_aquarium.mjs`, `l38_settings_krakie.mjs`, `l40_partage.mjs`).
- **Visite guidée** (`tour/`) : ses étapes visent le tiroir et l'en-tête. Il faut une variante mobile, ou la désactiver sur téléphone dans un premier temps (décision à noter).
- **Lecture seule mobile** : aujourd'hui, l'édition est désactivée sous 900 px. La maquette autorise de petites modifications (propriété, sous-classe, libellé, arbitrage). C'est un changement de règle à tracer dans `journal/decisions.md`, avec un avis de secu si l'authentification ou les rôles sont touchés (ils ne devraient pas l'être).
- **Textes** : pluriels « constat(s) » à reprendre (passe de l'humaniseur) ; nouvelles clés i18n fr et en en miroir.

## Ce qui reste volontairement « sur ordinateur »

| Fonction | Sur téléphone | Signalé par |
|---|---|---|
| Éditeur de fichiers (Turtle, code généré, CodeMirror) | lecture, copier, partager | étiquette « Sur ordinateur » dans Plus, bande `DesktopHint` |
| Édition des shapes SHACL | lecture des shapes et des résultats de validation | idem |
| Éditeur de requêtes SPARQL/Cypher | lancer les requêtes enregistrées et les questions de compétence, lire les résultats | « Écriture sur ordinateur » dans Plus |
| Réorganiser le graphe, créer un périmètre, notation VOWL, saisie rapide d'axiomes | absent ; le périmètre se choisit, il ne se crée pas | entrées absentes de la feuille de filtres, mention en pied de feuille |
| Import de gros fichiers, glisser-déposer | import par le sélecteur de fichiers du système | — |
| Administration des comptes | liste, désactivation, réinitialisation du mot de passe | création de compte avec la mention « plus confortable sur ordinateur » |
| Jeu (L20/L30) | inchangé (il a déjà ses commandes tactiles) | — |

## Relectures prévues (docs/TEAM.md)

scout (UX) et l'expert du domaine selon l'écran (w3c pour l'ontologie, curiosity/neo4j pour l'arbitrage) ; secu si la CSP, les cookies ou le partage natif changent ; doc pour le guide fr/en (section « Sur téléphone et tablette », avec captures) et le CHANGELOG fr/en ; humain en dernière passe sur les textes.
