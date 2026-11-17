# L48 : correctifs de l'itération 1

| Bloquant | Rôle | Traitement |
|---|---|---|
| Union à un seul membre après exclusion (builder) | w3c | **Fait.** `builder.py` : au moins deux membres pour `range_union` ; un seul : portée simple + avis `union_reduced` ; aucun : avis `union_empty`. `conformance/profiles.py` (`_malformed`) signale désormais toute `owl:unionOf` / `owl:intersectionOf` de moins de deux membres (W02, SS §8.1.1). Tests : `test_union_reduced_to_one_member_is_not_emitted_as_unionof`, `test_conformance_flags_union_with_one_member`. |
| IRI de base avec plusieurs `#` | w3c | **Fait.** `check_base` refuse (`bad_base_iri`) tout `#` hors dernier caractère. Test paramétré. |
| Bornes de BETWEEN non typées | shacl | **Fait.** `_typed_bound` : littéral N-Triples typé comme la colonne (entiers, décimaux, dateTime ; une date seule devient `…T00:00:00`) ; valeur invalide pour le type : borne non importée, avis `bound_dropped`. Test : `test_between_bounds_typed_like_the_column` (méta-validation shacl-shacl comprise). |
| Plusieurs CHECK fusionnés par union | shacl | **Fait.** `sql_check.merge_enum` / `merge_facets` : intersection des listes, borne la plus stricte ; intersection vide : plus d'énumération et avis `check_contradiction` ; avis `check_intersected`. Vaut pour `AND` dans une expression et pour des `CHECK` successifs (`sql_ddl.apply_check`). Test : `test_successive_checks_are_intersected`. |
| Regex `sniff_kind` quadratique | secu | **Fait.** Regex linéaire à liste fermée de mots entre `CREATE` et `TABLE`, répétition bornée. Test de temps (210 Ko de `create ` : moins d'une seconde). |
| OR sans `MAX_ENUM`, budget ni déduplication linéaire | secu | **Fait.** Plus de 500 branches : non traité (`check_complex`) ; `budget.tick` par branche (budget transmis à `analyze_check`) ; déduplication par `dict.fromkeys`. Test : 20 000 branches en moins de 5 s, 400 doublons. |
| Exclusion par nom affiché | scout | **Fait.** `exclude` porte des clés de classes (`key` dans l'aperçu) ; le front envoie `c.key`. Test avec deux tables homonymes (`a.orders`, `b.orders`). |
| Options fausses dans CONTRACTS | doc | **Fait, code inchangé** : le contrat est aligné sur le code (`postgresql`, `generic`, `choices`, clés inconnues ignorées et valeurs invalides ramenées au défaut, choix documenté). |
| Libellés du guide | doc | **Fait.** Libellés copiés de `fr.json` et `en.json`. |
| « 2 Mo par import » | doc | **Fait.** 2 Mo par fichier ; en plus, plafond cumulé de 10 Mo par requête dans le code (413 `too_big_total`, test) et dans CONTRACTS et le guide. |

Non-bloquants repris : `expect_digest` obligatoire (422 `missing_digest`, test), plafond cumulé, `anyOf` et `year` cités dans le guide, phrase sur la complétion des dates, §18 de CONTRACTS inchangé (la renumérotation à la fusion revient au lead).
Non repris (à arbitrer) : défaut « classe » pour l'auto-association à deux clés étrangères, regroupement des avis par code, compteur de formes de nœud et de propriété, vocabulaire des niveaux et pluriels de l'aperçu, avis `pattern_dialect` et `union_exclusive_lost`, libellés `fr`/`en` identiques, aperçu pleine largeur dans le tableau de bord.

Vérifications : tests L48 (43 + collab), docs, help_map, anglais, build du front, recette 18/18 (9148 / 5148).
