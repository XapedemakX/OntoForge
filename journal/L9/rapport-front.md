# L9 — rapport front : éditeur graphique d'ontologie (lead)

## Livré
`frontend/src/screens/editor/` : `Editor.tsx` (canvas, gestes, état), `parts.tsx` (nœud de classe, arête flottante, marqueurs), `Inspector.tsx`, `Tree.tsx`, `QuickInput.tsx`, `IconPicker.tsx`, `layout.ts` (dagre + repli des rangs larges), `types.ts` (API /ops, /graph, /icons, /perimeters), `editor.css`.
Registre : « Ontologie » = éditeur (`fullBleed`), l'ancien écran reste accessible en « Vue liste » (`ontologie-liste`). i18n fr/en : préfixe `ed.*` et `nav.liste`. Dépendances exactes : `@xyflow/react 12.8.4`, `@dagrejs/dagre 1.1.5`.

- **Canvas** : nœuds (icône FA, label dans la langue des labels des paramètres, badges abstrait/déprécié), arêtes flottantes : sous-classe plein + flèche creuse, propriété objet nommée (inverse affiché « ⇄ », une seule arête par paire inverse), disjonction pointillé rouge + pastille ⟂, équivalence tirets-points ; filtres Hiérarchie / Relations / Tout ; disposition auto + positions mémorisées (`move_node`, débounce 600 ms), « Réorganiser » ; zoom, mini-carte, recherche (centre + sélection), sélection multiple (Ctrl/Cmd-clic, Maj-glisser).
- **Zoom sémantique** (retour éclaireur B1) : cadrage automatique au chargement et après « Réorganiser » (zoom mini 0,42) ; sous 0,6 les nœuds deviennent compacts (icône + libellé, police agrandie pour rester lisible), libellés d'arêtes masqués sous 0,7 sauf sélection ; une classe créée ou choisie est centrée à zoom ≥ 0,9.
- **Gestes** : double-clic fond = nouvelle classe (saisie en place, nom local PascalCase, label = texte saisi) ; glisser la poignée vers une classe = menu sous-classe / nouvelle propriété objet / disjointes ; double-clic ou F2 = renommer (label) ; Suppr = confirmation dans la page ; Ctrl+Z / Ctrl+Y (ou Maj+Ctrl+Z) = `/ops/undo|redo` ; erreurs de validation OWL : toast + bandeau persistant + nœuds fautifs surlignés en rouge 6 s.
- **Inspecteur rabattable** (fermé si rien n'est sélectionné, bouton de bascule) : classe (IRI renommable partout, labels fr/en, commentaire, parents/enfants, icône via `/icons`, propriétés de données avec type + cardinalité ajoutables en ligne, relations, restrictions, clés, disjonctions) ; propriété objet (domaine, portée, inverse, caractéristiques).
- **Arbre** gauche repliable, filtre, synchronisé avec la sélection (déplie les ancêtres) ; liste des propriétés objet.
- **Saisie rapide** (`/dsl` merge) : panneau bas repliable, Ctrl+Entrée, erreurs par ligne (les lignes refusées restent), exemples et raccourci « Ajouter une propriété à X ».
- **Périmètre** : lit `?perimeter` (état actif du Shell via événement `of:perimeter`) ; « Créer un périmètre » depuis la sélection (POST puis activation).
- **Mobile < 768 px** : navigation, sélection, inspecteur en lecture (fieldset désactivé), pas d'édition ni de saisie rapide.
- **Krakie** en état vide avec les deux actions (créer / assistant).
- **Proposition de l'assistant** : l'éditeur consomme `lib/proposal.ts` (L10) via `useProposal()` ; nœuds ajoutés en vert (fantômes pointillés), modifiés en orange, arêtes vertes, ✓ / ✕ sur le nœud et dans le panneau « Proposition de l'assistant », Tout accepter / Tout rejeter ; `bindProjectSetter(setP)` rafraîchit le projet après acceptation. (Ma première version avec prop `proposal` + `diffProposal` a été supprimée au profit du store.)

## Vérifié (Playwright sur automaint, `journal/L9/screens/`)
01 vue d'ensemble cadrée · 02 inspecteur · 03 classe créée par double-clic · 04 menu de glisser-déposer · 06 saisie rapide (ligne fautive signalée) · 07 mobile · 08/09 proposition (1 ajout, 1 modif, 1 propriété ; acceptation d'un élément) · 10 erreur de validation (cycle) · 11 périmètre créé depuis 2 classes (graphe réduit, pastille) · 12 confirmation de suppression. Parcours chiffrés : création de classe, sous-classe par glisser, propriété de données, undo, redo, suppression + undo/redo, DSL. `npm run build` vert. Captures regardées et corrigées une fois (menu rogné en bas, cadrage trop petit/illisible, raccourcis clavier perdus quand le focus quitte le canevas -> écouteur global).

## Fichiers hors périmètre touchés (petits)
- `shell/Shell.tsx` : événements `of:perimeter` / `of:perimeters` (sélecteur d'en-tête synchronisé avec l'éditeur).
- `vite.config.ts` : cible du proxy via `ONTOFORGE_API` (défaut inchangé ; j'ai dû utiliser le port 8010 car le 8000 était pris par un autre backend).

## Limites / À VÉRIFIER
- Déplacer un nœud crée une entrée d'annulation (`move_node` est journalisé) ; la saisie rapide (/dsl) n'est pas annulable (hors /ops).
- Nouvelle classe créée avec un périmètre actif : elle n'y est pas ajoutée (invisible tant qu'on ne l'inclut pas).
- Arêtes `equivalentClass` et propriétés de données non dessinées comme arêtes (les secondes sont dans l'inspecteur) ; propriété objet à plusieurs domaines/portées = une arête par couple (suppression = la propriété entière).
- Vue « sélection du Shell » : si le périmètre est changé hors éditeur avant montage, l'éditeur le lit via `project.active_perimeter` (état de chargement du projet).
- Pas de test automatisé front (vérification Playwright manuelle, scripts dans le scratchpad).
