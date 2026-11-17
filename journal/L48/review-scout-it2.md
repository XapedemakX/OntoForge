verdict: OK
bloquants: []
non-bloquants:
  - Recette Playwright non rejouée : le changement front se limite à `c.key` (SchemaImport.tsx:102-104, api.ts:196) ; relu, `tsc --noEmit` sans erreur, rejoué côté service avec deux paires homonymes (voir ci-dessous). À reprendre en recette finale du lot.
  - [SchemaImport.tsx:141] `pv.classes.length - opts.exclude.length` suppose que chaque clé exclue existe dans l'aperçu courant ; si l'on change de fichiers après avoir décoché une classe, une clé obsolète pourrait fausser le compte. À vérifier lors de la recette (réinitialiser `exclude` au changement de fichiers).
  - Exclure le premier membre d'une union (`oneOf [A, B]`, A décoché) retire toute la relation (avertissement `relation_dropped`) alors que B reste : voir review-w3c-it2. L'utilisateur est prévenu.
  - Non repris, à arbitrer (inchangés, déjà listés dans fix-it1) : vocabulaire « 3 à vérifier » / « perte », pluriels « 1 relations », aperçu en demi-colonne et mascotte, regroupement des avis par code, ligne de conséquence par décision, défaut « classe » pour l'auto-association, compteur « 29 shapes », message d'aiguillage Projets.
vérifié:
  - Service : `a.orders` + `b.orders` + `customers` + `customer` donnent `Order`/`Order2`/`Customer`/`Customer2` avec clés `a.orders`, `b.orders`, `customers`, `customer` (stables avec ou sans `singularize`) ; exclure `b.orders` retire `Order2` seule, exclure `customer` retire `Customer2` seule, exclure `customers` retire `Customer` et la relation de `Customer2` (avis `relation_dropped`). Une exclusion par nom (`Orders2`, `Customer`) n'exclut plus rien : cohérent avec le contrat (clés).
  - JSON Schema : clés `0:#`, `0:#/definitions/A` ; exclusion par clé de B ou de A juste.
  - Contrat, guide et front cohérents sur `expect_digest` obligatoire (le front l'envoie toujours) et le plafond de 10 Mo (message localisé).
skill: product-discovery : confirmé (identifiant stable, jamais le nom affiché). Ajouter : réinitialiser les exclusions quand les fichiers changent.
