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

