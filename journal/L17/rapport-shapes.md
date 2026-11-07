# L17 - Écran Shapes (agent shacl)

## Livré
- `frontend/src/screens/shacl/` (index, ShapeList, ShapeDetail, Validation, helpers, shacl.css) remplace `screens/Shacl.tsx` ; `shell/registry.tsx` : seul le chemin d'import change. Clés i18n `sh.*` (fr + en).
- **Liste** : recherche, groupes par classe cible (icône de la classe via `/graph`, repli `cube`), badge du nombre de contraintes, état de validation (pas validée / OK / n violations).
- **Détail** : titre lisible, IRI compacte, « S'applique à chaque « Ordre de réparation » », fermée/ouverte, sévérité de la shape. Grille `table-layout: fixed` avec `colgroup` commun : propriété (libellé + CURIE), cardinalité en clair, type ou classe, autres contraintes en puces (motif, plage, longueur, liste, nodeKind…), sévérité, message.
- **Édition en ligne** : cardinalité (préréglages + personnalisée), type/classe, sévérité, message, fermée, suppression, ajout (propriétés de la classe d'abord). Barre « Modifications non enregistrées » -> `PUT /shapes`.
- **Génération** : diff des ajouts (nouvelles shapes, contraintes ajoutées aux shapes existantes) avant application ; les shapes sans contrainte (types, collections) sont écartées et comptées. « Appliquer » intègre au brouillon, puis Enregistrer.
- **Validation** : onglet dédié (dépôt ou choix de fichier), violations groupées par shape puis par nœud, bouton « Ouvrir la shape » (sélectionne la shape et surligne la contrainte), type de contrainte en clair.
- **Krakie** : `useAssistantContext({screen:'shapes'|'shacl', selection:{kind:'shape'}, suggestions})` ; bouton dans l'en-tête de la shape, puces « Ajoute une contrainte… » / « Explique cette shape », « Pourquoi cette violation ? » par ligne de violation, état vide avec Krakie + bouton.

## Vérifié (Playwright, automaint, automaint-data.ttl)
4 violations en 3 shapes (RepairOrder, Technician, Vehicle x2), lien vers la shape OK, édition + enregistrement OK, diff de génération OK, état vide OK, aucune erreur console. `npm run build` vert. Captures : `journal/L17/screens/shapes-01..08*.png`. Corrigé après regard : colonnes qui débordaient (largeurs fixes, selects sans flèche native, message en textarea), en-tête redistribué, noms de liste tronqués (suffixe Shape retiré), état de validation qui fuyait d'un projet à l'autre.

## Points à connaître
- Pas d'endpoint d'aperçu pour la génération : l'écran appelle `POST /shacl/generate` puis restaure aussitôt les shapes d'origine par `PUT /shapes` (fenêtre transitoire de quelques centaines de ms). Un `dry_run` côté backend serait plus propre.
- Les messages sont édités dans la langue de l'interface (`messages[lang]`).
- Les autres contraintes (motif, plage, liste) sont lisibles mais pas encore éditables en ligne.
- `tsc` signale des erreurs dans `screens/queries/` (hors périmètre).
