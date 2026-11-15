# L41 : corrections de la relecture de sécurité L39/L40 : rapport

Tous les constats de `journal/L39-secu/revue-securite.md` et `journal/L40/revue-securite.md` sont corrigés, chacun avec un test (voir le tableau). Le détail de reproduction et le statut par constat sont dans `journal/securite/revue-L39-L40-2026-11-15.md` (non publié).

## Choix (D-L41-01, à confirmer par Jerem)
Contrôle des adresses sortantes actif dès que l'authentification est activée, pas seulement en mode public ; inactif en local sans authentification. Pour un endpoint ou un fournisseur interne : `ONTOFORGE_EGRESS_ALLOW_INTERNAL`. Variable distincte de `ONTOFORGE_EGRESS_ALLOW` pour ne pas changer le sens de cette dernière. Voir `journal/decisions.md`.

## Corrections
| Constat | Correction | Test |
|---|---|---|
| L40-01 | instantané sans adresse pour un non-administrateur, réponse du LLM et cartes d'actions masquées ; erreur d'un endpoint enregistré générique (identifiant et nom) | `test_collab.py::test_l40_01_*`, `test_l41_securite.py::test_registered_endpoint_refusal_is_generic` |
| L40-02 | historique dans `generations.json` sous verrou ; la carte métier initiale n'est plus enregistrée par une lecture | `test_l40_02_*` (empreinte du dossier avec toutes les routes de lecture, modification d'un éditeur pendant une génération, historique hérité) |
| L40-03 | `netguard.enabled()` avec l'authentification, liste interne nommée, plus de début de réponse | `test_l41_securite.py` (netguard, liste interne, erreurs), `test_l40_03_auth_enables_netguard_for_any_account` |
| L40-04 | réponse unique `share_refused`, même travail côté serveur, limiteur conservé | `test_l40_04_*`, `test_share_with_self_and_bad_role` |
| L40-05 | `collab.json` illisible : verrouillé, administrateur seul, journalisé, jamais écrasé | `test_l40_05_*` (5 formes de corruption) |
| L40-06 | limites fr et en corrigées | `test_docs_bilingual` |
| L39-01 | sémaphore `ONTOFORGE_SHACL_SLOTS`, 503 `Retry-After` | `test_l39_01_*` |
| L39-02, 03 | `childproc.run_limited` (plafonds posés par le fils, `start_new_session`, environnement minimal), valable aussi pour le triplestore local | `test_l39_02_*`, `test_l39_03_*` |
| L39-04 | règle « lourd » élargie, `.env.example` à 120 | `test_l39_04_*` |
| L39-05 | clé préexistante signalée et resserrée à 600 | `test_l39_05_*` |
| L39-06 | identifiants retirés si schéma, hôte ou port change | `test_l39_06_*` |
| L39-07 | `proxy_set_header Host $http_host` | `test_l39_07_*`, `test_l39_07_origin_check_with_port_behind_the_proxy` |

Le test demandé (toutes les routes de lecture, un lecteur, vraie application, empreinte du dossier) a trouvé une écriture que la relecture n'avait pas listée : `GET …/business-map` enregistrait la proposition initiale. Corrigé (proposition gardée en mémoire par état du projet, enregistrée à la première écriture de la carte).

## Recettes
`pytest` 1255 réussis (dont 39 de `test_l41_securite.py` et 13 ajoutés à `test_collab.py`) ; `npm run build` OK ; `l40_partage.mjs` vert ; `e2e_ui.mjs` 30/30 avec le limiteur actif ; scripts d'attaque rejoués.

## Comportements à connaître
- Avec l'authentification, un endpoint ou un fournisseur interne (Ollama local, Fuseki du réseau) est refusé tant qu'il n'est pas dans `ONTOFORGE_EGRESS_ALLOW_INTERNAL`.
- Après un redémarrage, la disposition initiale d'une carte métier jamais modifiée peut légèrement changer (elle n'est plus écrite par la lecture).
- Une validation SHACL au-delà de 2 simultanées reçoit 503 ; le front affiche l'erreur ordinaire.

## À vérifier par Jerem
Sous Docker : nginx avec `$http_host` et l'authentification sur le port 8088 (écriture depuis le navigateur) ; Ollama ou Fuseki internes avec la nouvelle variable.
