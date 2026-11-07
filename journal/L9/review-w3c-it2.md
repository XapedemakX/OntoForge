# L9 — revue W3C (itération 2, contrôle)

Agent : w3c (relecteur). J'ai rejoué les scripts de reproduction de l'it1 sur le code actuel et lancé les tests `-k w3c` : 16 verts. La suite complète annoncée compte 545 tests verts.

verdict: KO (les 5 bloquants « avant jeudi » sont levés et la démo peut se faire ; les 3 bloquants « vendredi » restent ouverts)

## Bloquants « jeudi » : contrôle
- §11.2 dans les ClassExpr : levé. `C ≡ ≥2 p.B`, puis p transitive, est refusé.
- Disjonction avec une propriété non simple : levé. `add_disjoint p q` avec q transitive est refusé, et l'opération ne laisse rien appliqué.
- Vocabulaire réservé : levé. owl:Thing, xsd:string et rdf:type sont refusés, en ajout comme en renommage.
- Suppression : levé. L'union, l'intersection et le `not` qui mentionnent A sont retirés entiers (« 3 axiome(s) entier(s) retiré(s) »), et il ne reste plus d'expression n-aire tronquée.
- P01 pour une propriété héritée : levé. Le périmètre {Car, G} produit maintenant `P01:d` et `P01:s`.

## Bloquants — vendredi (toujours ouverts, non traités selon le fix)
- [backend/ontoforge/editing/perimeter.py] Projeter domaine et portée sur les classes du périmètre qui en descendent : V→G doit devenir Car→G au lieu d'une exclusion. Aujourd'hui l'exclusion est signalée par P01, mais la propriété reste perdue pour l'analyse.
- [backend/ontoforge/editing/ops.py `_op_set_restriction`] Un littéral `hasValue` mal typé (`"abc"^^xsd:integer`) est toujours accepté. Il rend l'ontologie incohérente (OWL 2 Direct Semantics).
- [backend/ontoforge/editing/ops.py `integrity_errors`] Une disjonction entre classes équivalentes nommées (A ≡ B) n'est toujours pas détectée.

## non-bloquants
- Les non-bloquants de l'it1 restent valables : avertissement xsd:date à remonter dans l'analyse, `_replace` qui touche aussi les littéraux, empreinte d'état pour annuler, shapes `sh:path`/`sh:class` hors périmètre.
- D-L9-02 (sévérité `info` pour P00–P03) : rien à redire sous l'angle W3C.

skill: rien de nouveau. Les checklists proposées à l'it1 restent à intégrer.

## it3 — contrôle des points « vendredi »

verdict: OK

Les 3 cas ont été rejoués, et les tests `test_w3c_it2_*` sont verts.
- Projection dans le périmètre : levé. Avec le périmètre {Car, G}, `s` V→G devient Car→G et `d` reçoit le domaine Car. Le constat P01 explique la restriction.
- `hasValue` mal typé : levé. `"abc"^^xsd:integer` est refusé, alors que `"12"^^xsd:integer` est accepté.
- Disjonction entre classes équivalentes : levé. Avec A ≡ B, `add_disjoint A B` est refusé.

Les non-bloquants de l'it1 restent ouverts. Ils ne bloquent pas la clôture.
