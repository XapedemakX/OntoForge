# M0 - Rapport maquettes (lead design)

Maquettes : https://claude.ai/artifact/XSYGRoaB1zgu9HpwMiBiNs (canvas Design, 7 artboards : identité, tableau de bord desktop + mobile, éditeur graphique, assistant, paramètres, analyse & arbitrage). Chaque écran a un réglage « thème clair / sombre » (bouton Tweaks).

## Choix de design (10 lignes)
1. Identité « Abysse » : Encre #14213D, Lagon #0B6E6E (action), Pieuvre #12A39A (mascotte), Lanterne #F2A900 (nœuds), Écume #F2F4F7 (fond), Alerte #B42318 ; variante sombre complète.
2. Pieuvre pixel art 34×34 (sprites SVG générés, contour encre, ventouses-nœuds lanterne reliés en pointillé = le graphe), 5 états, affichée en ×1/×2/×4 uniquement.
3. Règles mascotte : une seule par écran, jamais sur le canvas d'édition, la bulle dit le chiffre + la cause, un vrai bouton porte l'action.
4. Typo : Silkscreen (logo, titres courts, chiffres-clés), IBM Plex Sans (interface), IBM Plex Mono (IRI, règles, DSL).
5. Statuts auto / à arbitrer / perdu : teal / ambre / rouge, toujours avec icône + libellé (pas la couleur seule).
6. Navigation par le parcours Concevoir → Vérifier → Transposer → Générer (rail groupé) ; rail réduit à des icônes dans l'éditeur, l'assistant, l'analyse.
7. Tableau de bord : carte « prochaine action » de la pieuvre, 4 cartes d'étape, constats restants par cible (barres empilées), dernières générations (obsolète / à jour), périmètres.
8. Éditeur : arbre 232 px / canvas / inspecteur 320 px ; nœud = icône de classe + label fr + CURIE ; is-a en tirets teal à flèche creuse, relations pleines, disjonctions pointillé rouge avec pastille ⟂ ; saisie rapide repliable synchronisée (lignes surlignées = sélection).
9. Assistant : conversations par projet, fournisseur choisi dans l'en-tête, fichier joint avec aperçu (colonne nouvelle surlignée), proposition sur mini-graphe (vert = ajout, orange = modification) acceptée/rejetée par élément.
10. Analyse : pieuvre inquiète qui explique les perdus, synthèse chiffrée + mini-barres par catégorie, groupes perdus → à arbitrer → terminés, une règle dépliée avec options en cartes radio et « Appliquer aux N ».

## Questions ouvertes pour Jerem
- La pieuvre : couleur lagon OK, ou une teinte plus marquée (corail, violet) ? Lui donner un nom (proposition : « Octave ») ?
- Silkscreen pour les chiffres-clés : trop « jeu vidéo » pour un outil pro, ou à garder seulement pour le logo ?
- Éditeur : inspecteur toujours ouvert, ou panneau rabattable quand rien n'est sélectionné ?
- Mobile : consultation + arbitrage seulement (pas d'édition graphique) - confirmé ?
- Assistant : la proposition doit-elle aussi s'afficher en surbrillance dans l'éditeur principal (bouton « Voir dans l'éditeur ») ou rester dans le panneau ?
- Conventions de nommage des arêtes Curiosity (PascalCase proposé) : à valider avec l'expert Curiosity (À VÉRIFIER).
- Chiffres affichés (68 arbitrés, Neo4j 64 à arbitrer, etc.) : illustratifs, cohérents avec la capture réelle (93 auto / 80 non-auto) mais pas recalculés.

## v2 (4 nov.) — Krakie et arbitrages du 3/11

Maquettes mises à jour dans le même canvas (9 artboards). Sprites : `design/krakie/krakie-32.json` (palette + 8 poses, 32×32) → `python design/krakie/build.py` → SVG dans `design/krakie/` et `frontend/public/krakie/` (un rect par segment horizontal, `crispEdges`). `--redraw` régénère le JSON depuis le dessin procédural ; à ne plus utiliser après une retouche manuelle du JSON.

### Changements
1. **Krakie** remplace la pieuvre partout (logo du rail, cartes « prochaine étape », avatar de l'assistant, analyse). 8 poses : accueil (coucou), réfléchit (« ? »), lit (doc), loupe (conformité), graphe (fils entre nœuds lanterne), contente, inquiète (goutte), bolide (génération). Tailles ×1/×2/×3/×4 (32 → 128 px) uniquement.
2. **Typographie** : Silkscreen retirée de tous les écrans ; titres et chiffres-clés en IBM Plex Sans 700 (chiffres tabulaires), IRI et code en Plex Mono. Le pixel est réservé à Krakie.
3. **Éditeur** : inspecteur rabattable (réglage « inspecteur ouvert / rabattu » ; une fois rabattu, il devient un rail de 52 px). La proposition de l'assistant est visible sur le graphe principal (réglage « proposition affichée / masquée ») : bandeau avec compteur, « Tout accepter / Tout rejeter », lien vers la conversation, éléments en tirets verts (ajout : classe Rappel constructeur, relation certifiedFor) ou orange (modification : Technicien + evQualification), avec boutons ✓ / ✕ sur chaque élément.
4. **Mobile** : nouvel artboard « 1c · Graphe — mobile », en lecture seule (recherche, filtres is-a/relations, fil d'Ariane, zoom/recentrage, fiche de la classe avec relations cliquables, renvoi vers l'arbitrage). Le tableau de bord mobile y donne accès.
5. **Paramètres** : section **Endpoints SPARQL** avec plusieurs endpoints (GraphDB local actif, Fuseki de recette, référentiel pièces en échec), choix de l'endpoint actif par bouton radio, formulaire (auth chiffrée, délai, limite), test.
6. **Nouvel artboard « 6 · Requêtes interactives »** (dans l'esprit de Sparnatural, avec notre propre constructeur) : phrase guidée Véhicule → a pour ordre de réparation → Ordre de réparation → réalisé par → Technicien [nom contient « Mart… »], autocomplétion depuis l'endpoint actif, filtres (date, sous-classe), sélecteur d'endpoint, requêtes sauvegardées, résultats en tableau et en mini-graphe synchronisés, puis SPARQL / Cypher / Curiosity côte à côte, avec leurs notes (✓ / ⚠ / ✕ perte).

### Questions pour Jerem
- Krakie : poses et proportions OK ? Faut-il d'autres poses (dort = tâche longue, salue en partant = déconnexion) ?
- Requêtes : la colonne « Opération » est jointe automatiquement par le libellé (`rdfs:label`). Faut-il plutôt laisser l'utilisateur choisir explicitement les colonnes à projeter ?
- La syntaxe de requête Curiosity affichée (`Q().StartAt…Out…`) est **À VÉRIFIER** avec l'expert Curiosity, de même que la paire d'arêtes `HasRepairOrder` / `RepairOrderOf`.
- Le mobile reste en lecture seule pour le graphe : faut-il quand même pouvoir accepter ou rejeter une proposition de l'assistant depuis le mobile (ce qui reste de l'arbitrage, pas de l'édition) ?
