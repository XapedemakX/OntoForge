# L39-secu : corrections de sécurité de l'audit du 15/11

Pilote : secu (corrections, sur demande de Jerem). Relecteurs : secu (revue-securite.md) + experts du domaine (w3c, query, shacl, deploy), doc puis humain.
Origine : audit de sécurité complet du 15/11 (décisions de Jerem du 15/11 : lancer les corrections ; montées de version reportées, D-L21-02).

## Objectif
Corriger les défauts relevés par l'audit qui ne demandent aucune montée de version : exposition locale, parseurs RDF, secrets, débit, conteneurs, constructions, assistant, rendu Markdown, brouillon Cloud Run.

## Périmètre
Traités : SEC-01, 02, 03 (partie service), 04, 05, 06, 07, 08, 10, 11, 12, 13, 14, 16, 17, 21.
Hors lot : SEC-09 et SEC-18 (montées de version reportées), SEC-19 et SEC-20 (lot L40 en cours, décision de Jerem), SEC-15 et SEC-22 (acceptés).

## Livrables
1. Instance locale : compose lié à `127.0.0.1` (`ONTOFORGE_BIND`, `ONTOFORGE_PORT`), CORS fermé par défaut (`ONTOFORGE_CORS_ORIGINS`), en-têtes et CSP dans nginx, avertissements de démarrage (écoute hors boucle locale sans authentification, `.env` lisible, liste de sorties absente en mode public).
2. Imports : refus des `DOCTYPE` en RDF/XML, des contextes JSON-LD distants, plafonds sur les triplets non reconnus et sur la canonisation, validation SHACL en processus fils (délai, mémoire, CPU) avec message clair.
3. Secrets : liés à l'origine de l'adresse saisie (couche `settings/`), clé maître hors du volume des données (`ONTOFORGE_SECRET_FILE`, volume `ontoforge-keys`).
4. Débit : module `ratelimit.py` (par adresse et par session, plafonds plus bas pour l'assistant et les routes coûteuses, `429` + `Retry-After`).
5. Conteneurs sans root (backend, front nginx sans privilèges, brouillon Cloud Run), constructions reproductibles (`npm ci` strict, `backend/constraints.txt`).
6. Assistant : contenus importés balisés `<donnees>` + règle dans chaque invite ; Markdown des explications limité à `http(s)` et `mailto`, sans image.
7. Brouillon Cloud Run : liste de sorties exigée, `--forwarded-allow-ips` restreint ; code mort `_hermit` supprimé.
8. Tests de non-régression (un fichier par thème : `test_sec_rdf.py`, `test_sec_settings.py`, `test_sec_network.py`, `test_sec_ratelimit.py`, `test_sec_assistant.py`, `test_sec_front.py`, `frontend/tests/safe_markdown.test.mjs`), guide fr/en, limites fr/en, CHANGELOG fr/en, CONTRACTS §15, journal.

## Critères d'acceptation
- `cd backend && pytest -q` : tout vert, dont les tests `test_sec_*`.
- `cd frontend && npm run build` et `npm test` : OK.
- Recette `BACKEND_PORT=… FRONT_PORT=… node tools/recette/e2e_ui.mjs` : 30/30.
- Les scripts d'attaque de l'audit rejoués : plus aucun constat « VULN » sur les points traités (contre-audit dans `journal/securite/audit-2026-11-15.md`, dossier non publié).
- Docker : `docker compose up --build` démarre ; `docker compose exec backend id -u` ≠ 0 ; recette d'import et de requête sous cet utilisateur (à faire par Jerem, Docker n'étant pas disponible dans l'environnement de construction).

## Hors périmètre et suites
- Après L40 : voir le rapport (route PUT et cloisonnement des comptes ; `SEC-03` côté API).
- Épingler les images de base par condensat (À VÉRIFIER, besoin d'un accès réseau).
