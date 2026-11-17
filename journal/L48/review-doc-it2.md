verdict: OK
bloquants: []
non-bloquants:
  - [docs/CONTRACTS.md:408] La §18 reste doublée avec L49 (`## 18. Bonnes pratiques d'ontologie…`) : renumérotation à la fusion, déjà notée par le lead dans fix-it1 ; garder en tête pour le lot fusionné en second (rapport, CHANGELOG, help_map, D-L49-01).
  - [docs/CONTRACTS.md:413] « `bad_options` 422 » : le code renvoie aussi 413 si la chaîne dépasse 200 000 caractères (`api/schema_import.py:35`). Détail, à ajouter si l'on veut l'exactitude complète.
  - Le message d'avis `degraded_type` (« la précision est perdue ») contredit la phrase du guide sur la complétion des dates pour `date → dateTime` ; non repris, signalé en it1 (w3c).
  - Le guide ne dit pas que l'aperçu doit précéder l'application côté API (`expect_digest` obligatoire) : suffisant dans CONTRACTS, c'est un détail d'API.
vérifié (texte contre code et `fr.json` / `en.json`) :
  - CONTRACTS §18 Options : dialectes `auto|postgresql|mysql|sqlserver|generic` (service.py:21) ; `choices` avec `association:<table>` = `property|class`, `subclass:<table>` = `property|subclass`, `reference:<clé de classe>.<colonne>` = `property|relation` (sql_to_entities.py:91-101, csv_import.py:196-202) ; `exclude` = clés (`key` de l'aperçu) ; `singularize` vrai par défaut ; `required_from_sample`, `delimiter` ; clés inconnues ignorées et valeur invalide ramenée au défaut (`clean_options`) ; `bad_options` 422 si non-objet. Exact.
  - Limites : « 2 Mo par fichier et 10 Mo cumulés par requête (413 `too_big_total`) » conforme à `limits.MAX_TOTAL_MB` et à la route (rejoué : 413 avec message localisé). `expect_digest` obligatoire, 422 `missing_digest` : conforme (test et rejeu).
  - Guide fr/en : libellés « Voir l'aperçu de l'import (sans IA) » / « See the import preview (no AI) » (`proj.staged.schema`) et « Importer depuis une base ou un schéma » / « Import from a database or schema » (`dash.import.title`) identiques aux fichiers i18n ; `anyOf`, `year`, complétion des dates, intersection des CHECK, limites par fichier / au total présents dans les deux langues, sens équivalents.
  - Sortie §18 : « bornes typées comme la colonne » est vrai pour les cas courants ; voir review-shacl-it2 (borne `dateTime` impossible, fuseau) avant de laisser cette phrase telle quelle.
skill: technical-documentation : confirmé (libellés copiés des fichiers i18n, unité de chaque limite). Ajouter : rejouer chaque phrase de contrat « jamais » ou « toujours » contre un cas hostile avant de l'écrire.
