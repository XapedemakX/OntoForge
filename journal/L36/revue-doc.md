# L36 Carte métier : revue documentaliste

verdict: KO

Sources comparées : docs/guide/utilisateur.md (+ .en), CHANGELOG(.en), docs/CONTRACTS.md §13, code backend et front.

bloquants:
  1. [docs/guide/utilisateur.md:209 et .en.md:209] La doc promet une flèche de cadre « avec sa mention (« tous les cinq ») ». Le code ne produit rien de tel : le libellé est `relation · Partagent : r1 → T1…` (backend/ontoforge/businessmap/frames.py:62-63 ; frontend/src/screens/bmap/render.ts:50). Reproduction : « Proposer des cadres » sur automaint, lire le libellé de la flèche. Corriger la phrase (ou le code, mais pas les deux divergents).
  2. [docs/guide/utilisateur.md:212 (+ .en)] « Une zone vide n'est conservée qu'après y avoir rangé un type » décrit un bug comme une règle. Si le correctif de revue-w3c.md est appliqué, supprimer la phrase ; sinon la déplacer dans limites.md.
  3. [docs/guide/utilisateur.md:213] « Styles : … inverse stockée aussi, … sens unique » : formulation inexacte pour une ontologie (voir revue-w3c.md points 1-2) : `owl:inverseOf` ne dit rien du stockage et « sens unique » n'est jamais posé automatiquement (types.ts:81-87), seulement par l'utilisateur. Dire que « sens unique » est un style manuel.
  4. [docs/guide/api.md, docs/guide/architecture.md, docs/guide/limites.md, docs/guide/glossaire.md] Aucune mention de `/business-map` ni du paquet `businessmap` (grep vide), alors que le contrat existe dans CONTRACTS.md §13 (rapport backend). La règle « aucune clôture sans le passage du documentaliste » impose : 5 routes dans api.md, le paquet et le flux dans architecture.md, et une entrée limites.md (volumes = types affirmés seulement, rôles déduits par heuristique, recuit non déterministe en temps, zones par hiérarchie sur cible Curiosity).
  5. [journal/L36/] `doc-ok.md` absent (comme `review-*-it1.md` au format docs/TEAM.md : les trois fichiers de cette revue sont au format demandé, pas au nom attendu par le protocole ; le chef décidera).

non-bloquants:
  6. [docs/guide/utilisateur.md:209-210] Aucune explication de l'origine des rôles : la couleur est déduite par heuristique (backend/ontoforge/businessmap/roles.py:1-14) et peut être corrigée ; le glossaire devrait définir « rôle », « cadre », « zone », « scénario ». Dire aussi que les volumes viennent du triplestore local sinon des individus de l'ontologie (counts.py:128-141), et qu'ils ne comptent que les individus typés directement.
  7. [docs/guide/utilisateur.md:212] Préciser que « Proposer des zones » (apply) remplace les zones et libère les positions non épinglées (service.py:337-340).
  8. [docs/guide/CHANGELOG.md:11] Le CHANGELOG parle d'« écran » mais pas de l'API ni de `Project.business_maps` (champ optionnel rétrocompatible) ; ajouter une ligne « API ».
  9. [docs/guide/utilisateur.md:506 et visite] « 21 étapes » : cohérent avec tour/steps.ts (vérifié), OK.
  10. Captures docs/guide/img/fr|en/carte-metier*.png présentes en fr et en ; légendes de figures cohérentes avec le texte. OK. Texte à repasser par l'humaniseur (demandé par le lead front).
skill: technical-documentation : exiger « chaque comportement visible cité dans la doc se retrouve par grep dans le code » (ici « tous les cinq »).

## Contre-relecture (15 nov. 2026)

verdict: KO (un bloquant résiduel : `docs/CONTRACTS.md` §13 périmé ; les cinq bloquants listés ci-dessus sont, eux, corrigés)

Bloquants listés, vérifiés dans les fichiers :
1. Flèche de cadre « tous les cinq » : disparu des deux guides. Le texte dit désormais « nom de la relation suivi de la note du cadre (« Partagent : relation → type, … »)», conforme à `render.ts:51`.
2. Zone vide : la phrase décrivant le bug est remplacée par « Une zone vide est conservée telle quelle, avec sa place sur la carte » (vrai depuis le correctif).
3. Styles : « inverse stockée aussi » et « sens unique » corrigés ; « un seul sens » est dit manuel, la symétrique dessinée à part.
4. `api.md`, `architecture.md`, `limites.md`, `glossaire.md` (fr et en) : `/business-map` (5 routes), paquet `businessmap`, entrée « Que dit la carte métier… », termes Carte métier, Zone, Cadre, Rôle, Scénario. Présents.
5. `doc-ok.md` : non écrit pour L36, voir ci-dessous.
Non-bloquants 6, 7, 8 : traités (origine des rôles, volumes, « Proposer des zones » qui remplace et libère les positions, ligne API du CHANGELOG L36c). Test `test_help_map` et `test_docs_bilingual` verts après la passe humaniseur (44 réussis).

Bloquant résiduel :
- [docs/CONTRACTS.md:278-320, §13] Le contrat normatif cité par `api.md` n'a pas suivi L36c : exemple JSON avec `"role": "classifier"` et légende `"key"` ; légende « couleurs par défaut : `issue` #2e9e6b, `detail`, `key`, `classifier`, `catalogue`, `knowledge`, `config` » (jeu abandonné) ; « Rôles déduits » décrits avec les anciens ids et les motifs métier retirés (rappel, garantie…) ; définition de `count` sans fermeture `rdfs:subClassOf` ni individus distincts ; ni `link`, `union`, `meta.skipped`, `meta.n_union`, ni zones vides avec rectangle. Correction attendue : réécrire §13 (rôles génériques et `LEGACY_ROLES`, nouvelles teintes de `roles.py`, comptage, champs d'arête et de `meta`) avec une entrée dans `journal/decisions.md` (les contrats ne changent que par décision tracée, docs/TEAM.md). Je ne l'ai pas modifié moi-même pour respecter cette règle.
