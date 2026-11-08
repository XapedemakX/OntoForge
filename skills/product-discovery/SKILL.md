---
name: product-discovery
description: Méthode de découverte produit pour des outils d'ingénierie (modélisation de données, ontologies, générateurs de code). Partir des irritants d'un ingénieur en ESN, faire une veille ciblée, recueillir les frustrations des autres agents, produire un carnet d'idées priorisé (valeur, effort, risque, lot) et un benchmark. À utiliser quand on doit décider quoi construire ensuite.
---
# Découverte produit pour outils d'ingénierie

## 1. Cadrer l'utilisateur
- Une personne, un contexte : p. ex. architecte données en ESN (appel d'offres, POC en quelques jours, justification au client, évolution du modèle).
- Lister ses 6-8 irritants en verbes : modéliser vite, importer l'existant, justifier, comparer deux versions, documenter, tester, aligner sur un référentiel, collaborer.

## 2. Récolter en interne (avant tout web)
- Lire les rapports de lot (section « limites »), les revues (`non-bloquants`, `skill:`), les décisions, les questions ouvertes, les captures d'écran.
- Chaque frustration d'agent devient une idée candidate avec sa source (fichier). Mesurer quand c'est possible (ex. « 80 constats à arbitrer sur un exemple propre »).

## 3. Veille ciblée (10-15 recherches maximum)
- Outils voisins + standards montants. Pour chacun : ce qu'il fait bien, ce qu'on peut faire mieux pour NOTRE utilisateur.
- Citer l'URL ; marquer « à revérifier » toute affirmation non confirmée par une page lue. Ne jamais attribuer à un outil une fonction sur la foi de sa seule réputation.

## 4. Formuler les idées
Pour chaque idée : problème, proposition (maquette en une phrase), valeur 1-5 pour l'ingénieur, effort S/M/L, risque, lot suggéré, inspiration + source. Ne pas dépasser une idée = un problème.

## 5. Prioriser
- Horizons : maintenant (itération en cours), bientôt (2 itérations suivantes), plus tard.
- Tri : valeur élevée + effort faible + appui sur l'existant d'abord ; écarter ce qui dépend d'un standard instable.
- Top 5 argumenté en tête de carnet, avec une preuve de valeur mesurable pour chacun.

## 6. Ateliers (revues d'usage)
- Relire maquettes et écrans en tant qu'utilisateur : « puis-je faire mon travail sans explication ? »
- Produire `journal/<lot>/review-scout.md` au format du protocole d'équipe (verdict, bloquants, non-bloquants, skill).

## Pièges
- Proposer sans coder : pas de fichiers hors carnet et skill.
- Ne pas confondre fonctionnalité d'un concurrent et besoin de l'utilisateur.
- Garder le carnet vivant : dater, numéroter (P-xx), marquer les idées réalisées ou abandonnées.
