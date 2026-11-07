# Rapport L4 — expert Curiosity

## État repris
Un agent précédent avait écrit `mapping/profiles/curiosity.py` (capacités, types, nommage, 41 recommandations), `targets/curiosity.py` (Schema/Edges/RegisterSchema/Connector/README) et la fixture. Il manquait : tests, skill, rapport, option ids de l'oracle, règles C10-C13, K04-K05, D08-D13, O14-O21, R02, A02-A03, M01-M02, I02-I05, G01. Sources S1-S7 déjà vérifiées (listées dans le profil et le skill), non re-cherchées.

## Livré
- Profil : `RECOMMENDATIONS` couvre les 66 règles de transposition (W01-W07 = conformité L2, exclues) ; chaque entrée porte `option` (vocabulaire de `samples/trap/expected-findings.yaml`) et `alternatives`. Accord avec l'oracle testé (hors D05/O13 à deux options). `CATALOGUE_RULES` exposé.
- Tests : `test_profile_curiosity.py` et `test_target_curiosity.py` (20 tests) ; suite complète 61 verts.
- Skill `skills/curiosity-schema-design/SKILL.md`.

## Points ouverts
- À VÉRIFIER sur une instance : retour de `AddOrUpdate`, `Link(a,b,X,X)` symétrique, `T[]` par classe attribuée, indexation des dictionnaires.
- Demande de contrat (non déposée, PGType figé) : `Decimal` et `Language` n'existent pas dans PGType alors que Curiosity les connaît ; decimal -> double avec perte signalée.
- K02 : l'oracle recommande `uri_key` pour hasKey (concaténation en alternative `key_concat`).
- Les tests de fumée C# ne compilent pas le code (pas de SDK .NET) : vérification syntaxique par équilibrage seulement.
