# L22 — revue w3c, itération 2

Relecteur : expert W3C (agent `w3c`). Périmètre : correctifs de `fix-it1.md` (texte saisi conservé, préfixe de repli, ordre des exemples). Tests ajoutés : `backend/tests/test_files_editor_review_it2.py` (15 cas, verts). Recette `node tools/recette/l22_files.mjs` relancée : 23/23.

## Bloquants de l'itération 1
- **Commentaires / réécritures visibles** : corrigé pour de bon. Le texte saisi n'est gardé que si `graph_diff(texte, résultat)` est vide ; sinon le canonique est écrit et l'aperçu chiffre les lignes supprimées (« supprimées », `role=alert`) et les triplets réécrits (déplié d'office). Vérifié par test et dans l'éditeur (recette).
- **Préfixe de l'exemple** : corrigé (cause réelle : `.owl` servi avant `.ttl`), plus un repli générique.

## Points demandés
- **Texte conservé après modification venue d'ailleurs** : l'invariant (même etag canonique, donc canonique déterministe, donc graphe isomorphe) tient. Testé avec `/ops` (ajout de classe), annulation, rétablissement, et application avec changement de modèle puis annulation : modification externe → canonique + note chiffrée (`comment_lines`) ; annulation qui ramène le même graphe → le texte saisi revient, et le texte servi est isomorphe au graphe du projet à chaque étape (`rdflib.compare.isomorphic`). Réenregistrer le canonique depuis l'éditeur ne ressuscite pas l'ancien texte.
- **Préfixe de repli** : correct pour une IRI d'ontologie en `#` ou en `/`, avec ou sans séparateur final (`garage`, `garage#`, `garage/`) ; IRI à dernier segment non alphabétique (`1.0`) → `onto`. Ne masque jamais un préfixe déclaré (le préfixe d'origine est gardé, `garage` déjà pris par un autre espace de noms donne `garage2`).
- **Ordre `.ttl` avant `.owl`** : le modèle chargé depuis `automaint.ttl` est isomorphe à celui chargé depuis `automaint.owl` (ancien ordre) ; seuls les préfixes déclarés s'ajoutent (sur-ensemble). Trap et les shapes inchangés (un seul fichier). Test : `test_sample_ttl_first_is_isomorphic_to_former_owl_first`.

## Verdict
```
verdict: OK
bloquants: []
non-bloquants:
  - [frontend/src/i18n/fr.json fx.note.canonicalN] après annulation de sa propre application, la note dit « modifié depuis un autre écran » et « ont été supprimées » alors que le texte reviendra au rétablissement. Reformuler : « …remplacé par la forme normalisée ; vos N lignes de commentaire ne sont plus affichées ».
  - [files.py _fallback_prefixes] le slug retire les tirets et points (`my-onto` -> `myonto`) ; correct, simplement peu lisible.
  - Reste ouvert de l'it1 : position du « point attendu », jeton fautif des étiquettes de langue, IRI relative résolue par `@base` dans `Locator`.
skill: w3c-ontology-conformance -> « Un texte source conservé est valide tant que l'etag du canonique est inchangé : l'égalité d'etag d'un canonique déterministe vaut isomorphisme. Un préfixe de repli se dérive de l'IRI d'ontologie, jamais d'un préfixe déjà lié. »
```
