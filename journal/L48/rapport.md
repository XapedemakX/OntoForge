# Rapport du lot L48 : import déterministe de schémas SQL, CSV et JSON Schema

## Livré
- Paquet `backend/ontoforge/importers/` : lexeur SQL maison (PostgreSQL, MySQL, SQL Server), analyseur DDL, lecteur CSV RFC 4180 borné, lecteur JSON Schema (`$ref` locaux, `allOf`, `oneOf`), constructeur (OntoModel + ShapesModel via `generate_shapes`), messages fr/en, service pur et déterministe (empreinte sha256).
- Routes : aperçu hors projet, aperçu et application dans un projet (écriture, annulable, 409 `stale_preview` si l'aperçu est périmé). Voir CONTRACTS §18.
- Interface : zone de dépôt de l'écran Projets (bouton « Voir l'aperçu de l'import (sans IA) ») et bloc « Importer » du tableau de bord ; aperçu avec décisions, classes exclusibles, avis, éléments ignorés.
- Docs fr/en (`{#import-schema}`), `help_map` (`schema-import`), CHANGELOG fr/en, CONTRACTS §18, D-L48-01.
- Recette `tools/recette/l48_import.mjs` (ports 9148 / 5148) : 18 vérifications OK ; captures dans `journal/L48/screens/`.

## Contraintes
- Aucune dépendance ajoutée ; aucun LLM ; aucune référence suivie (réseau ou disque) ; aucun SQL exécuté.
- Limites : 2 Mo, 50 fichiers, 400 tables, 1 024 colonnes par table, profondeur 32, 8 s. Entrées hostiles testées (tables géantes, imbrication profonde, binaire, UTF-16, `$ref` cyclique).
- Droits : lecteur 403, étranger 404, anonyme 401, If-Match 428 sur projet partagé, CSRF.
- Environnement : le `python3` global n'a pas fastapi ; les tests ont été lancés avec `/home/claude/venv/bin/python -m pytest` (rien installé).

## Tests
- `test_l48_import.py` (33) et `test_l48_collab.py` (5) ; `npm run build` et `tsc` propres ; `npm test` vert.

## À relire
- w3c : dégradation des types date, heure, durée, année (absents de la table OWL 2) ; `hasKey` sur `UNIQUE` non nul ; `range_union` pour `oneOf`.
- shacl : facettes issues de `CHECK` (longueur, bornes, énumération `sh:in` en littéraux simples pour `xsd:string`) ; formes validées par shacl-shacl.
- secu : lecture bornée, délai, refus des octets NUL, aucune suite de référence externe, validation de l'IRI de base, options filtrées, catégorie de limitation « heavy ».

## Points ouverts
- D-L48-01 à confirmer par Jerem (choix par défaut des décisions, option « obligatoire d'après l'échantillon » désactivée).
