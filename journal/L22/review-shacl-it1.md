# L22 — revue shacl, itération 1

Relecteur : expert SHACL (agent `shacl`). Date : 7/11/2026. Périmètre : méta-validation `_shacl_shacl` (`backend/ontoforge/editing/files.py`), diagnostics de `shapes.ttl`, application des shapes.

## Ce qui a été vérifié
La méta-validation contre shacl-shacl (SHACL §C, copie embarquée par pySHACL) **fonctionne**, en environ 20 ms par passage, ce qui convient à la validation en direct. Cas essayés :

| Cas | Constat |
|---|---|
| shapes valides | aucun constat |
| `sh:minCount "x"` | méta-shape : « Value is not Literal with datatype xsd:integer », ligne et colonne exactes ; import en échec |
| `sh:datatype "string"` | « not of Node Kind sh:IRI » sur la bonne ligne |
| propriété sans `sh:path` | méta-shape (xone NodeShape / PropertyShape) et import : « sans sh:path, ignorée » |
| deux `sh:path` | « More than 1 values », colonne exacte |
| `sh:severity "Violation"` (littéral) | nodeKind IRI signalé |
| `sh:in ex:a` (pas une liste) | ListShape signalé, mais en quatre constats redondants |
| `sh:maxCount -1` | rien : conforme à SHACL §4.2 (seul le datatype xsd:integer est exigé) |
| `ex:S a sh:NodeShape ; sh:path ex:p` | rien : shacl-shacl ne cible pas les instances de `sh:NodeShape` porteuses de `sh:path` |

pyshacl 0.40.2 : `pyshacl/assets/shacl-shacl.ttl` est toujours présent dans la roue (vérifié) et `validate(..., shacl_graph=, inference=, advanced=, inplace=)` est toujours exposée. Le À VÉRIFIER peut être réduit à « option `meta_shacl` à préférer ».

## Verdict

```
verdict: OK
bloquants:
  (aucun après correction)
non-bloquants:
  - [backend/ontoforge/editing/files.py:401] `ex:S a sh:NodeShape ; sh:path ex:p` est mal formé (SHACL §2.3 : une instance SHACL de sh:NodeShape ne peut pas avoir de valeur pour sh:path), mais ni la méta-shape ni l'import ne le signalent. Ajouter un contrôle maison (`shacl-nodeshape-path`, avertissement).
  - [backend/ontoforge/editing/files.py:437] les messages de pySHACL restent en anglais brut dans l'interface française (« Node [ sh:minCount Literal(…) ] must conform to exactly one shape in shsh:NodeShapeShape… »). Traduire les familles fréquentes (datatype, nodeKind, maxCount, xone NodeShape/PropertyShape, ListShape) et dédoublonner : un `sh:in` mal formé produit quatre lignes pour une seule cause.
  - [backend/ontoforge/editing/files.py:407] préférer `pyshacl.validate(g, meta_shacl=True, …)` ou l'API dédiée à la lecture d'un fichier interne de la bibliothèque.
  - [backend/ontoforge/shacl/import_shapes.py] message « sévérité personnalisée Violation ramenée à Violation » quand la sévérité est un littéral : préciser « littéral "Violation" au lieu de l'IRI sh:Violation ».
  - [backend/ontoforge/shacl/import_shapes.py] `sh:maxCount -1` est accepté. Avertissement de bonne pratique suggéré (valeur négative sans sens).
corrigé par le relecteur (backend/ontoforge/editing/files.py) :
  - Cas signalé par le pilote (`sh:minCount "x"`) : l'import échouait avec une erreur bloquante en **1:1** et un message Python brut (« invalid literal for int() with base 10: rdflib.term.Literal('x') »), alors que la méta-shape avait déjà localisé la cause. Désormais, quand l'import échoue et que la méta-shape a des constats, ceux-ci passent en **erreur**, et l'erreur `shapes-import` se place sur la même ligne avec un texte clair. Le message technique va dans `detail`. Le PUT renvoie les mêmes diagnostics localisés en 422 (`prepare`).
  - Les littéraux mal typés sont aussi signalés dans shapes.ttl (`ill-typed-literal`).
  - Tests : `test_shacl_meta_shape_flags_datatype_literal_on_its_line`, `test_shacl_unappliable_shape_error_is_located_not_line_one`, `test_valid_shapes_have_no_meta_shape_finding`, aller-retour sans perte de automaint-shapes et trap-shapes.
skill: shacl-modeling → « La méta-shape shacl-shacl ne couvre pas tout §2 (NodeShape + sh:path, valeurs négatives de cardinalité) : la compléter par des contrôles maison. Quand l'import d'un graphe de shapes échoue, montrer les constats de la méta-shape comme cause. »
```
