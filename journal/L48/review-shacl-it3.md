verdict: OK
bloquants:
  - aucun
non-bloquants:
  - Suite complète et recette non rejouées après eb8d4e9 (changements limités à importers/ ; la suite sera rejouée sur master après fusion).
skill: shacl-modeling — valider une borne typée sur sa valeur (calendrier), pas sur sa forme ; borne datée sur colonne avec fuseau : UTC explicite + avis.
Vérification (lead pour shacl, it3) : bornes '2020-13-45T99:99:99' et '2021-02-30' écartées (bound_dropped), '2020-02-29T23:59:59' gardée, bound_tz_assumed sur timestamptz (tests test_l48_import.py:573-587) ; 7 tests ciblés et 124 tests L48 / conformance / doc verts (fix-it2).
