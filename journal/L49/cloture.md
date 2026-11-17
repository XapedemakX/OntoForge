# L49 : clôture (17/11/2026)

**Livré.** Bonnes pratiques : règles BP08–BP16 et complétude, dépréciation de bout en bout, versions SemVer calculées par diff, en-tête d'ontologie.

**Relectures.** w3c, scout OK it1 ; query, shacl OK it2 ; curiosity, neo4j OK it3 ; doc OK it4 après escalade chef.

## Vérification sur la version fusionnée (branche d'intégration, 17/11)
- Suite backend : 1412 réussis, 0 échec (`/home/claude/venv/bin/python -m pytest -q`).
- Front : `tsc --noEmit` et `npm run build` OK.
- Recettes : e2e_ui 30/30, l47_justification 10/10, l48_import vert, l49_bonnes_pratiques 14/14, mobile_l50 9/9, l40_partage vert.
- Fusion : CONTRACTS §18 = L48, §19 = L49, §20 = L47 ; i18n fr/en à parité (2201 clés).

**Reste ouvert.** Question ouverte à Jerem (Q-L49-1) : l'ajout d'une classe est-il une version majeure ?
