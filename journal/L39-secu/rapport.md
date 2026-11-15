# L39-secu : rapport

Lot de corrections des constats de `journal/securite/audit-2026-11-15.md` (statuts en §8, contre-audit en §9).

## Fait
SEC-01, 02, 04, 05, 06, 07, 08, 10, 11, 12, 13, 16, 17, 21 corrigés ; SEC-03 (couche service) et SEC-14 partiels. Un fichier de tests par thème : `test_sec_rdf.py`, `test_sec_settings.py`, `test_sec_network.py`, `test_sec_ratelimit.py`, `test_sec_assistant.py`, `test_sec_front.py`, `frontend/tests/safe_markdown.test.mjs`.

## Recettes
`pytest` 1198 réussis (après L40 : plus aucun test ignoré, voir L41) ; `npm run build`, `npm test` OK ; `e2e_ui.mjs` 30/30.

## Comportements à connaître
- Un RDF/XML avec `DOCTYPE` (certains exports d'éditeurs d'ontologies) est refusé avec un message ; Turtle ou RDF/XML sans entités passent.
- Au-delà de 1 500 triplets non reconnus, le texte canonique n'est plus stable ; au-delà de 10 000, l'import est refusé (réglable).
- Plafonds de débit par minute : global 900, assistant 20, routes coûteuses 120, raisonneur 10 (réglables).

## Suites (mis à jour en L41)
- Les 2 tests SEC-03 ne sont plus ignorés : ils tournent depuis L40 (routes `PUT` de réglages classées) et SEC-03 a été rejoué par la relecture de sécurité du 15/11 (un compte non administrateur n'écrit rien dans les réglages ; le secret est lié à l'origine). SEC-19 et SEC-20 : traités par L40.
- Reste hors périmètre : `store.save` lent sur de très gros ensembles non reconnus (`projects/`) ; SEC-09 et SEC-18 reportés.
- Corrections de la relecture L39/L40 : `journal/L41/rapport.md`.

## À vérifier par Jerem (Docker indisponible ici)
1. `docker compose up --build` : démarrage, service `init-perms`, volume `ontoforge-keys` (migration de la clé existante).
2. `docker compose exec backend id -u` différent de 0 ; import et requête depuis l'interface.
3. Étiquette `nginx-unprivileged:1.27-alpine` existante ; épingler les images par condensat.
4. Cloud Run : uid du montage GCS, `FORWARDED_ALLOW_IPS`, `ONTOFORGE_EGRESS_ALLOW`.
5. Scan d'images (Trivy ou Grype) ; `chmod 600 .env`.
