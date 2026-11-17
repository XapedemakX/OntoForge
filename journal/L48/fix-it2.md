# L48 : correctifs de l'itération 2

| Point | Traitement |
|---|---|
| shacl, bloquant : bornes de date validées seulement sur la forme | **Fait.** `_valid_date` (calendrier via `datetime.date.fromisoformat`) et `_valid_dt` (heure 00-24, minute, seconde jusqu'à 60, décalage jusqu'à ±14:59) ; sinon borne écartée et avis `bound_dropped`. Test : `test_it2_calendar_validation_of_bounds` (`2020-13-45T99:99:99`, `2021-02-30`). |
| Borne complétée en `T00:00:00` sur `timestamptz` | **Fait.** Colonne avec fuseau : borne complétée en UTC (`Z`) et avis `bound_tz_assumed` ; colonne sans fuseau inchangée. Test dédié. |
| `=` imbriqués combinés par intersection | **Vérifié.** `((k='a' OR k='b') AND (k='b' OR k='c'))` et `m='a' AND (m='a' OR m='b')` donnent bien l'intersection (déjà vrai via `merge_enum`) ; test ajouté. |
| Exclure le premier membre d'une union | **Fait.** La relation survit tant qu'un membre reste (nommage, portée et listing utilisent le premier membre restant) ; plus d'avis `relation_dropped` à tort. Test avec `anyOf` de trois classes. |
| Message `degraded_type` pour `date` | **Fait.** Nouveau code `degraded_date` (fr/en) : pas de perte de précision, valeurs à compléter en date-heure à l'ingestion. |

Vérifications : `test_l48_*` (53 tests) et `test_conformance_profiles` verts, avec test_docs_bilingual et test_help_map (124 passed au total).
