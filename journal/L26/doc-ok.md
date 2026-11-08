# L26 : vérification documentaire (documentaliste)

Sections vérifiées contre le code : « Lire le graphe : légende et notation VOWL » (docs/guide/utilisateur.md) et docs/CONTRACTS.md §5 (« Graphe enrichi »), après les corrections des revues w3c et scout it1.

Écarts trouvés et corrigés :
- Légende : le guide disait seulement « son état est mémorisé ». Depuis la revue scout, elle s'ouvre au premier usage (repliée sous 900 px, `Editor.tsx`, initialisation de `legend`) et la vue se cadre à côté (`fitPad`). Écrit.
- Types de données : le masquage d'emblée au-delà de 16 classes (`Editor.tsx`, `show.dt = nClasses <= 16` sans choix mémorisé) et `Literal` en pointillé (`.of-vn.lit`) n'étaient pas dans le guide. Ajoutés.
- owl:Thing : le guide disait « domaine ou image libre ». Règle exacte depuis la revue w3c : absent ou owl:Thing dans l'ontologie ; une propriété libre des deux côtés, ou de données sans domaine, n'est pas dessinée (`graph.py`). Écrit.
- Inverses : fusion seulement si les extrémités se répondent (`view.ts`), inverse sans domaine ni image portée par l'autre arête (`inverse_label`, `graph.py`). Écrit au guide et à CONTRACTS §5.
- Externe : repli sur l'espace de noms majoritaire (`_namespaces`, `graph.py`). Écrit au guide et à CONTRACTS §5.
- Zoom : comportement des noms en vue d'ensemble (11 px minimum à l'écran, masqués sous 30 %, `vowl.tsx`) et seuil d'apparition des libellés de propriétés (55 %, `parts.tsx`). Ajoutés.
- CONTRACTS §5 : `thing` précisé (« dans l'ontologie, et non simplement absent de la vue ») ; deuxième test cité (`test_graph_l26_w3c_it1_thing_inverse_namespace`).

Points confirmés sans changement : tableau classique (encodages de `parts.tsx` et `legendDefs.ts`), menu « Afficher » et curseur de densité (`ShowMenu.tsx`, `view.ts`), compteur, export SVG/PNG (`exporter.ts` : styles en ligne, couleurs résolues, légende en option, PNG en double résolution), visite en 19 étapes, ligne L26 du CHANGELOG, paramètres `include` de CONTRACTS §5.

Reste avant clôture : passage de l'humaniseur sur la section du guide et sur les deux revues ; la question Q-L26-1 (journal/questions-jerem.md) est ouverte, non bloquante.

Humanisé, sens vérifié : passe de l'humaniseur sur la section du guide, CONTRACTS §5, la ligne L26 du CHANGELOG et le rapport. Diff relu mot à mot par le documentaliste : seules des phrases ont été scindées ou allégées, aucun fait, nombre, seuil, nom de fichier ou champ modifié. Les deux écarts du rapport L26 (légende « fermée par défaut », section « Relectures » non à jour) sont signalés dans journal/L23/rapport.md.
