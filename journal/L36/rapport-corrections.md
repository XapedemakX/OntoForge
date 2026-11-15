# L36c : corrections de la carte métier (suite aux revues scout, doc, W3C)

## 1. Zones vides perdues (scout 1, W3C C, doc 2)
- `businessmap/service.py` : tailles de zone calculées sur toutes les zones (plus de filtre `if z.members`) ; la zone vide revient au GET avec un rectangle.
- Test `test_empty_zone_survives_put_get` (PUT, GET, second PUT calqué sur la réponse, pas de chevauchement). Recette 5c2 et 5c3 (rechargement de page).
- Contournement retiré de `useBMap.ts` ; phrase retirée de `utilisateur(.en).md`.

## 2. Sémantique (W3C 1 à 6)
- `bm.style.both` : « relation déclarée dans les deux sens (propriété inverse) » ; nouveau style dessiné `symmetric` (propriété symétrique, teinte à part, `edge.link = inverse|symmetric`) ; `bm.style.oneway` : « un seul sens retenu pour ce scénario » (aucune négation de l'inverse, style resté manuel).
- `disjointUnionOf` ne pose plus `abstract` (reste réservé au PGModel). Test dédié.
- « subClassOf » : arêtes de hiérarchie libellées via i18n (`bm.edge.subclass` : « est un » / « is a »).
- Propriétés ignorées (`g.skipped`) : `meta.skipped` [{id,label}], bandeau avec compteur et liste dépliable.
- Unions de classes : arêtes marquées `union: true`, `meta.n_union`, bandeau, mention dans l'inspecteur (« une possibilité, pas un fait »). Les arêtes sont conservées, signalées plutôt que supprimées.
- Inspecteur : rôle « déduit de la structure » ou « choisi à la main » (W3C 9).

## 3. Volumes (W3C 3)
- `counts.py` : fermeture `rdfs:subClassOf`, individus distincts (SPARQL `COUNT(DISTINCT)` sur `VALUES` quand plusieurs classes d'une même fermeture ont des individus ; ensembles côté ontologie) ; cible : sources fusionnées sans double compte. Tests : ontologie, triplestore, cible.

## 4. Rôles par défaut (W3C B)
- `BUILTIN_ROLES` = main, component, hub, lookup, context, reference, document, settings ; libellés fr/en ; teintes nouvelles tirées de tokens.css (lagon, info, orange brûlé, moutarde, bleu acier, vert forêt, prune, brun).
- Motifs métier retirés (recall|rappel|warranty|garantie|bulletin ; reading|operation|line) ; heuristiques structurelles ajoutées (nombre de liens, énuméré, nombre de propriétés littérales `n_data`, référencé par au moins 2 types).
- Migration : `LEGACY_ROLES` / `canonical_role` (anciens ids relus, PUT canonicalisé). Un rôle libre saisi par l'humain reste accepté (choix : ne pas écraser une décision explicite). Test dédié.

## 5. Mobile (scout 2)
- Ouverture sur zoom >= 45 % cadré sur la zone la plus peuplée si l'ajustement total est plus petit ; bouton « Tout voir » (ancien « Ajuster ») ; le redimensionnement en hauteur ne défait plus le déplacement. Recette 11b, 11c. Non traité : doublon du bandeau « consultation » (hors liste).

## 6. Recette instable (scout 7)
- `l36_business_map.mjs` : analyse du modèle cible lancée et attendue côté API avant l'écran Modèle, attente du bouton portée à 120 s. Deux lancements successifs : 32/32 et 32/32.

## 7. Documentation (doc 1 à 4, 6 à 8)
- `utilisateur(.en).md` : texte des cadres aligné sur le code, volumes, rôles, bandeaux, mobile, styles. `api`, `architecture`, `limites`, `glossaire` (fr et en) : `/business-map`, paquet, limites, termes. CHANGELOG fr/en (L36c). Captures `carte-metier*` fr/en régénérées (autres images restaurées). Restent à faire par le chef : `doc-ok.md`, passage de l'humaniseur, `lots/L36.md`.

## Vérifications
pytest 1018 verts ; `npm run build` ; recette l36 32/32 deux fois ; e2e_ui 30/30 ; english_scan 0 suspect ; test_help_map et test_docs_bilingual verts.

## Non traité (non bloquants de revue hors liste)
Scout 4 (note de cadre répétée sur chaque flèche), 5 (bouton « Créer un scénario »), 6 (infobulle Réorganiser), 8 (« — » pour volume 0), W3C 7 (nom de l'inverse sur la carte).
