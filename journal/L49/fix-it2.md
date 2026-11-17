# L49 : corrections de l'itération 2 (pilote w3c)

Revues : `review-*-it2.md` (query et shacl OK ; curiosity, neo4j, doc KO). Tests : `cd backend && PYTHONPATH=$PWD /home/claude/venv/bin/python -m pytest -q` : **1337 réussis, 0 échec** ; `npm run build` OK ; recette `BACKEND_PORT=9149 FRONT_PORT=5149 node tools/recette/l49_bonnes_pratiques.mjs` : 14/14.

## Bloquants

| Revue | Bloquant | Fait |
|---|---|---|
| curiosity, neo4j | `exclusion_losses` ne lit que domaine et portée déclarés : une relation résolue par restriction (O02) disparaît sans constat | `annotations._endpoints` reprend la résolution de la construction : `objects.resolve` (domaine, portée, union, inverse, restrictions, shapes, faits) pour une relation, classes porteuses de `data.build_props` (union, domaine, utilisateurs D02) pour un attribut. Perte totale si, d'un côté, toutes les extrémités résolues sont exclues : listée dans A03, constat de base (O01, O02, O03, D01, D02, D03…) en `lost` avec la raison. Test `test_losses_follow_resolution_o02_and_partial_union` sur les deux cibles (`Car ⊑ ∃locatedNear.Garage`, Garage exclue : A03 liste locatedNear, O02 en `lost`, aucune arête). |
| doc | `api.md` / `api.en.md` : `level` nul, `unchanged`, `downgraded`, effet de l'annulation sur `GET /releases` | Les deux tableaux disent maintenant `level: …\|null` + `unchanged`, `release.downgraded`, et que `POST /ops/undo` sur `version <x>` retire la version de `GET /releases` (rétablir la remet). |
| doc | Guide : phrase sur les pertes induites inexacte (O02, union partielle) | Réécrite (fr/en) : extrémités déclarées ou déduites (O02), perte partielle notée « En partie », reste généré, niveau inchangé. CONTRACTS §18 aligné. |

## Non-bloquants
- Union partielle (`bookletOrPlan`) : traitée. Perte partielle = « En partie : … » dans A03, note « Générée en partie » sur le constat de base (niveau inchangé), « en partie : … » dans la colonne du rapport ; plus listée comme perdue. Testé.
- Test des chaînes rendu probant : deux axiomes permutés (aucun changement), un axiome retiré (majeur), ordre intérieur inversé (changement).
- `frontend/src/api.ts` : `level: ReleaseLevel | null` et `unchanged?` (fait en it1, vérifié).
- Guide : demi-phrase ajoutée, les shapes sont désactivées même quand l'entité est gardée avec drapeau (génération indépendante de la cible), avec le moyen de les réactiver.
- `[Obsolete]` : non posé (CS0618 avec `TreatWarningsAsErrors`), comme décidé en it1.
- Non retenu : lien annulation ↔ version par identifiant d'opération. Le journal d'opérations régénère l'identifiant à chaque passage annuler/rétablir (`history._swap`) ; un identifiant stable demanderait de changer le format de `ops-history.json` (fichier du lead). Le libellé `version <x>` est produit par le seul `POST /releases`, et `on_history` vérifie que la version déplacée est bien la dernière (ou la dernière annulée) avant d'agir. À reprendre si le journal gagne des identifiants stables.
