# L48 : clôture (17/11/2026)

**Livré.** Import déterministe SQL DDL / CSV / JSON Schema, aperçu obligatoire avec empreinte, plafonds par fichier et par requête.

**Relectures.** w3c, secu, scout, doc KO it1 → OK it2 ; shacl KO it1 et it2 → OK it3 (relecture lead).

## Vérification sur la version fusionnée (branche d'intégration, 17/11)
- Suite backend : 1412 réussis, 0 échec (`/home/claude/venv/bin/python -m pytest -q`).
- Front : `tsc --noEmit` et `npm run build` OK.
- Recettes : e2e_ui 30/30, l47_justification 10/10, l48_import vert, l49_bonnes_pratiques 14/14, mobile_l50 9/9, l40_partage vert.
- Fusion : CONTRACTS §18 = L48, §19 = L49, §20 = L47 ; i18n fr/en à parité (2201 clés).

**Reste ouvert.** Choix non repris listés dans fix-it1 (défaut d'association, regroupement des avis…) : à arbitrer par Jerem si utile.
