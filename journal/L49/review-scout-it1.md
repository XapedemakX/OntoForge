verdict: OK
bloquants:
  - (aucun)
non-bloquants:
  - Testé à 390 × 844 (contexte mobile Playwright, ports 9249/5249, exemple automaint, une version enregistrée) : aucun débordement horizontal (`scrollWidth = 390`). Les trois cartes Complétude, En-tête et Versions passent sur une colonne ; la grille `auto-fit minmax(240px, 1fr)` se comporte bien. Captures dans le scratchpad du relecteur, non versionnées.
  - Carte Complétude : les pastilles de critères incomplets sont **barrées** (`pill off`). Or le barré signifie déjà « déprécié » dans l'arbre, la vue liste et le graphe (`dep-name`, L49). Lire « ~~définition 12/74~~ » comme « critère abandonné » est tentant. → couleur ou icône pour « incomplet », barré réservé à la dépréciation.
  - « Fiches les moins complètes » : le clic sur une entité mène à l'écran Ontologie sans la sélectionner (`go(p.id, 'ontologie')`). L'utilisateur doit la rechercher à nouveau. → ouvrir la vue liste sur l'IRI (`ontologie-liste?iri=…` ou équivalent). À 390 px, la liste alterne en plus « manque » sur la même ligne et sur la ligne suivante selon la longueur du nom ; un bloc par entité (nom, puis manques) serait plus régulier.
  - Carte Versions : sans aucun changement, elle propose quand même « correctif — 1.0.1 » avec des compteurs à 0 et un bouton actif. → « Aucun changement depuis 1.0.0 », bouton désactivé (voir revue query).
  - En-tête sur téléphone : 14 champs à la suite. Regrouper en « Identité » (titre, objectif, version), « Personnes » et « Références » (vocabulaires, sources, licence), repliables, rendrait la carte lisible ; les dates de création et de modification n'ont pas besoin d'être éditables en premier plan.
  - Fiche dans la vue liste : « Description » (`rdfs:comment`, en haut) et « Définition (skos:definition) » (dans la fiche) se suivent à quelques centimètres, et un utilisateur ne voit pas la différence. → une phrase d'aide (« la définition dit ce qu'est le terme ; la description, comment l'utiliser »), ou ne proposer la définition que si la description est vide.
  - Dépréciation dans la liste et l'éditeur : barré + étiquette « déprécié » + « Remplacée par Véhicule » et « Ne plus déprécier » : clair et réversible. Le texte d'aide sur l'arbitrage A03 est utile.
  - Date « Modifiée le » affichée en UTC (la veille entre minuit et 1 h en France).
  - Recette rejouée (9249/5249) : 12/12 vertes ; captures restaurées après coup.
skill: product-discovery : un même code visuel (barré) ne doit porter qu'un sens dans tout le produit ; un lien vers une entité depuis un tableau de bord doit l'ouvrir, pas seulement l'écran qui la contient.
