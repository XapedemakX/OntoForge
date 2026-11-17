# L47 fix it1

Réponse aux revues it1 (curiosity KO, scout KO ; neo4j, secu, doc OK).

## Bloquants
1. **curiosity** : D13 et O10 sortent de `NO_CHOICE` pour Curiosity (connecteur en code 2 sur violation, renforcement sous OWA : vrai choix). Gardés pour Neo4j avec un motif nuancé (requête Cypher de détection non bloquante, `IS NOT NULL` Enterprise à décommenter). O09 et D09 restent auto pour les deux cibles. Oracle : f-D13, f-O10, f-O10b repassent `review` pour Curiosity (`severity` par cible). D-L47-01 mis à jour (points 1, 2, 4, 5). **Mesure recalculée : Neo4j 19, Curiosity 31 constats ; la cible < 25 n'est plus tenue en constats pour Curiosity**, elle l'est en groupes de décision (8 par cible). Pas d'astuce pour la sauver : question posée à Jerem dans D-L47-01 (lecture en constats ou en décisions groupées).
2. **scout** : `FindingCard` vide le champ « pourquoi » et n'envoie aucune raison quand l'option choisie diffère de celle d'un constat déjà décidé (une raison saisie avant le premier choix est conservée). Recette A3b ajoutée, guide mis à jour.

## Non-bloquants traités
- `security.py` : égalité avec `STRICT_CSP` (source unique, reprise par `justification.CSP`), plus de préfixe.
- `POST /branch` : `overwrite` (défaut faux) ; avec `option`, une décision d'un autre compte ou sans auteur connu n'est remplacée que sur « Imposer » (le front envoie `overwrite: true`) ; sinon elle va dans `skipped`. Test ajouté.
- « Appliquer à toute la branche » : la ligne « Option recommandée : C04 : …, C02 : … » indique l'option appliquée.
- Texte d'aide des branches : une seule fois au-dessus des groupes.
- Markdown : `://` échappé (URL nues non cliquables) ; `via` déclaré informatif dans CONTRACTS §18.
- Captures du guide régénérées (voir rapport), légendes recalées (analyse-synthese : groupes par racine), `analyse-branche` ajoutée fr et en.
- Doc recalée sur les nouveaux chiffres et les règles reclassées par cible : guide fr/en, CHANGELOG fr/en, RULES.md, CONTRACTS §18, D-L47-01 ; mention que les décisions sur téléphone n'ont pas de raison ; rappel que « validation » reste un renforcement. `help_map` : résumés inchangés (ils ne citent ni règle ni chiffre), test_help_map vert.
- Skill `owl-to-property-graph` : §9 (reclassement, connecteur bloquant, K02).
- Décompte des tests corrigé dans le rapport (11 tests, 1319 passed au total).

## Non traité
- Champ « pourquoi » replié sur l'écran de bureau (« Ajouter une raison ») et sur mobile : à voir en L50.
- Indicateur « N à arbitrer encore » sur la carte du dossier : non fait.
- Login d'un administrateur `as_admin` visible des lecteurs dans les traces : non masqué, à décider (signalé).
- Skills `curiosity-schema-design`, `neo4j-schema-design`, `product-discovery`, `audit-securite-cve-cwe`, `doc-bilingue-captures` : remarques des relecteurs à reprendre par leurs propriétaires.
