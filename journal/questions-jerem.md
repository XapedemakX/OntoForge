# Questions pour Jerem

Règle (D-009) : seulement ce qui bloque réellement ; sinon on avance avec l'hypothèse notée. Jerem répond quand il veut, ici ou dans la Salle des agents. Une réponse qui contredit l'hypothèse = nouvelle décision dans `journal/decisions.md`.

## Ouvertes

| ID | Date | Question | Bloquant ? | Hypothèse retenue en attendant | Lot |
|---|---|---|---|---|---|
| Q-01 | 2026-11-02 | Pour la recette de mardi 19 h, disposes-tu d'une clé Anthropic à mettre dans ton `.env` local pour essayer l'assistant (J4) ? | Non | Sans clé, l'assistant affiche « non configuré » et la recette J4 est sautée ; tous nos tests utilisent le fournisseur `mock`. | L6, L7 |
| Q-02 | 2026-11-02 | Veux-tu qu'on exécute les sorties générées sur une vraie instance (Neo4j Desktop, ou un environnement Curiosity) de ton côté ? | Non | Non : on vérifie la syntaxe ici (tree-sitter pour le C#, formes Cypher 5) ; les points d'API Curiosity incertains sont marqués « À VÉRIFIER » dans le rapport de clôture. | L4, L7 |
| Q-L26-1 | 2026-11-08 | Graphe en notation VOWL : au-delà de 16 classes, les propriétés de données (rectangles jaunes) sont masquées d'emblée ; la légende s'ouvre maintenant au premier usage ; la sélection reste en teal plutôt qu'en rouge VOWL. Ces trois choix te vont-ils ? | Non | Oui pour les trois (revue scout L26 it1) ; la case « Propriétés de données » du menu « Afficher » les rétablit. | L26 |
| Q-L40-1 | 2026-11-15 | Partage (L40, D-L40-01) : quatre choix par défaut à confirmer. (a) Un administrateur voit-il aussi les projets des autres comptes ? (b) Faut-il pouvoir créer des comptes depuis l'interface (aujourd'hui : `ONTOFORGE_AUTH_USERS`, on partage avec un identifiant existant) ? (c) Un lecteur peut-il lancer une génération (elle écrit l'historique dans le projet) ? (d) La langue de l'interface reste un réglage global, donc réservé aux administrateurs : ok ? | Non | (a) Non : l'administrateur ne gère que les réglages globaux. (b) Non. (c) Oui. (d) Oui. | L40 |

## Fermées

| ID | Date | Question | Réponse | Décision |
|---|---|---|---|---|
| — | 2026-11-02 | Domaine de l'exercice de base ? | Maintenance automobile | D-011, D-030 |
| — | 2026-11-02 | Date de première livraison ? | Itération 1 mardi 3 nov. au soir ; vendredi = itération 2 | D-022 |
