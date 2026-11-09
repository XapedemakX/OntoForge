# L23 : humanisation, étape 1

Agent : humain. Skill créé : `skills/humanizer/SKILL.md` (adapté de blader/humanizer, MIT, licence copiée dans `skills/humanizer/LICENSE-humanizer`, règles de Jerem reprises mot pour mot).

Contrôle automatique après chaque fichier : blocs de code, code en ligne, liens, nombres, nombre de lignes de tableau et occurrences de `À VÉRIFIER` identiques à la version précédente. Aucun écart sur les 25 fichiers.

## Fichiers traités

| Fichier | Lignes modifiées | Doutes |
|---|---|---|
| README.md | 17 | Aucun. Titre « Ce qu'il faut savoir » conservé (cité par journal/L14/doc-ok.md). |
| docs/ARCHITECTURE.md | 22 | Aucun. Tableaux du catalogue de règles non touchés, gras de la ligne R01 laissé. |
| docs/PLAN-IT2.md | 45 | Aucun. |
| docs/guide/limites.md | 19 | Questions de la FAQ laissées en gras (structure). |
| docs/guide/contribuer.md | 32 | Cellule de tableau « - » (tiret long, valeur vide) laissée. |
| docs/guide/CHANGELOG.md | 48 | Titres de versions : « 0.1.0 — » devient « 0.1.0 : » (ancres éventuelles à revoir). Cellules « - » de tableau laissées. |
| docs/veille/neonto.md | 19 | Aucun. |
| docs/veille/normes.md | 33 | Cellules « - » de tableau laissées. |
| docs/veille/nvidia-auto-ontology.md | 26 | Aucun. |
| docs/veille/processus-mise-a-jour.md | 35 | Incohérence d'origine non corrigée : « On automatise trois choses » suivi de quatre points numérotés. À signaler au doc ou à veille. |
| docs/veille/triplestore-embarque.md | 12 | Aucun. |
| skills/curiosity-schema-design/SKILL.md | 8 | Aucun. |
| skills/graph-query-translation/SKILL.md | 7 | Aucun. |
| skills/neo4j-schema-design/SKILL.md | 24 | Aucun. |
| skills/ontoforge-delivery/SKILL.md | 34 | Gabarits dans les blocs de code (titres avec tiret long) laissés tels quels. |
| skills/ontology-rapid-design/SKILL.md | 19 | Description du frontmatter reformulée (YAML vérifié valide). |
| skills/owl-to-property-graph/SKILL.md | 33 | Gabarit de rapport en bloc de code laissé tel quel. |
| skills/product-discovery/SKILL.md | 0 | Non modifié. Le frontmatter d'origine n'est pas du YAML valide (deux-points dans la description non entre guillemets). À corriger par son propriétaire (scout). |
| skills/shacl-modeling/SKILL.md | 5 | Aucun. |
| skills/tech-watch/SKILL.md | 9 | Aucun. |
| skills/technical-documentation/SKILL.md | 23 | Description du frontmatter reformulée (YAML valide). |
| skills/w3c-ontology-conformance/SKILL.md | 33 | Aucun. |

## Nature des changements

Retrait du gras décoratif et des tirets longs (hors code et cellules vides de tableau), fin de liste sans point final, phrases longues coupées, enchaînements par point-virgule remplacés par des phrases courtes. Peu de vocabulaire LLM trouvé : ces documents étaient déjà directs.

# L23, seconde passe

Agent : humain. Lots relus : L19 à L22 et L25 (doc-ok.md présents). Même contrôle automatique avant/après : blocs de code, code en ligne, liens, nombres, nombre de lignes de tableau, `À VÉRIFIER`. Aucun écart sur les 12 fichiers. Pour CONTRACTS.md, les lignes de tableau sont en plus identiques caractère pour caractère. Un commit par série.

| Fichier | Lignes modifiées | Doutes |
|---|---|---|
| docs/guide/utilisateur.md | 112 | Gras décoratif retiré (deux avertissements gardés : saisie rapide non annulable, C# non compilé / Cypher non exécuté). Titre H1 et cellule « - » de tableau laissés. Codes W01–W07 et BP01–BP07 laissés. Section « Easter egg » inchangée, elle ne révèle pas le code. |
| docs/CONTRACTS.md | 13 | Prose seulement : gras en milieu de phrase retiré, quatre tirets longs remplacés. Étiquettes en gras en début de ligne gardées (structure du contrat), titre du §3 « PGModel — conventions » laissé. Schémas, exemples et tableaux intacts. |
| docs/guide/api.md | 12 | Première humanisation de ce fichier : il n'a reçu aucune section depuis la première passe (aucune route L19, L22, L25 n'y est décrite, voir doc-ok). Étiquettes « Requête » / « Réponse 200 » gardées en gras. Titres avec tiret long laissés. |
| docs/guide/CHANGELOG.md | 2 | Section 0.3.0 : deux enchaînements par point-virgule scindés. |
| docs/veille/normes.md | 4 | Partie ajoutée (décisions du 7/11) seulement. Tableaux non touchés. |
| docs/veille/processus-mise-a-jour.md | 4 | Idem. Incohérence « trois choses / quatre points » déjà corrigée par veille. |
| docs/veille/triplestore-embarque.md | 2 | Paragraphe de l'union scindé, ligne vide ajoutée sous le titre « Limites assumées ». |
| docs/veille/neonto.md, nvidia-auto-ontology.md | 0 | Non modifiés depuis la première passe. |
| journal/L19, L20, L21, L22, L25 / rapport.md | 5, 7, 0, 7, 12 | Gras de début de puce retiré hors tableaux. Étiquettes en gras des tableaux laissées. L22 : gras gardé sur la normalisation des commentaires. |

Non touchés : revues, fix-it*.md, lots/.


# L26, passe d'humanisation

Agent : humain. Périmètre : section « Lire le graphe : légende et notation VOWL » de docs/guide/utilisateur.md, prose de docs/CONTRACTS.md §5 (paragraphe « Graphe enrichi »), section L26 de docs/guide/CHANGELOG.md, journal/L26/rapport.md. Même contrôle automatique avant/après (HEAD contre fichier) : blocs de code, code en ligne, liens, nombres, lignes de tableau, `À VÉRIFIER`. Aucun écart sur les quatre fichiers.

| Fichier | Lignes modifiées | Doutes |
|---|---|---|
| docs/guide/utilisateur.md | 3 | Points-virgules scindés, énumération du menu « Afficher » allégée (la précision sur les équivalences en VOWL passe dans une phrase séparée). Tableaux, couleurs et seuils intacts. |
| docs/CONTRACTS.md | 1 | Paragraphe « Graphe enrichi » : trois enchaînements par point-virgule ou deux-points scindés. Spécification, noms de champs et tests intacts. |
| docs/guide/CHANGELOG.md | 1 | Ligne L26 : « enrichi de façon rétrocompatible » devient « reste rétrocompatible et gagne ». |
| journal/L26/rapport.md | 6 | Contrastes « pas X » retirés (sélection en teal, caractéristiques, limite de zoom), points-virgules scindés. Tableau « Livré » intact. |

Questions laissées sans réponse, hors périmètre de l'humanisation :
- Le rapport L26 dit en décision 3 « Légende fermée par défaut », alors que doc-ok.md et le guide décrivent une légende ouverte au premier usage depuis la revue scout.
- La section « Relectures » du rapport L26 dit que les relectures ne sont pas faites, alors que review-w3c-it1.md, review-scout-it1.md et doc-ok.md existent.


# L28 à L32, passe d'humanisation

Agent : humain. Base de comparaison : d2aa081 (le commit e5399ee n'existe pas dans ce dépôt). Périmètre : sections « Raisonner avec HermiT », « Versions des normes et des cibles » et « Documentation intégrée et aide » de docs/guide/utilisateur.md, paragraphe HermiT de docs/guide/limites.md, prose de docs/CONTRACTS.md (§11 seulement), encadré L31 de docs/veille/processus-mise-a-jour.md, journal/L28 à L32/rapport.md. Même contrôle automatique avant/après (HEAD contre fichier) : blocs de code, code en ligne, liens, nombres, lignes de tableau, `À VÉRIFIER`, titres. Aucun écart. `backend/tests/test_help_map.py` : 30 passed.

| Fichier | Lignes modifiées | Doutes |
|---|---|---|
| docs/guide/utilisateur.md | 18 | Gras de début de puce retiré (HermiT, Versions, Documentation). Deux longs paragraphes scindés. « Ce n'est pas une validation de données » devient « Il ne valide pas des données comme le fait SHACL ». Section « Easter egg » : non modifiée par L30, non touchée. |
| docs/guide/limites.md | 1 | Paragraphe HermiT scindé en trois. |
| docs/CONTRACTS.md | 1 | §11, puce Krakie. §12 et §4 sans tic. |
| docs/veille/processus-mise-a-jour.md | 2 | Encadré L31 : gras du libellé retiré, parenthèse transformée en proposition. |
| journal/L28/rapport.md | 1 | Première puce de « Livré » scindée. |
| journal/L29/rapport.md | 18 | Étiquettes en gras de début de puce remplacées par « Étiquette : ». |
| journal/L30/rapport.md | 7 | Idem. |
| journal/L31/rapport.md, L32/rapport.md | 0 | Pas de tic notable. Titre « Limites honnêtes » de L32 laissé tel quel (titre). |

Non touchés : architecture.md et glossaire.md (lignes de tableau), CHANGELOG.md (autre agent), revues, doc-ok existants hors la ligne ajoutée.
Question laissée : la ligne CHANGELOG et le rapport L28 évoquent encore « humain : à faire » alors que cette passe est faite.
