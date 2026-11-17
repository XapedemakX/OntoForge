# L47 : clôture (17/11/2026)

**Livré.** Dossier de justification (HTML / Markdown) et arbitrage par racine, raison par décision ; générateur Curiosity corrigé (cardinalités {kind, n}, garde de présence des plages, max 0).

**Relectures.** neo4j, secu, doc OK it1 ; curiosity KO it1 et it2, OK it3 ; scout KO it1, OK it2 ; non-bloquant curiosity it3 (max 0) corrigé par le chef.

## Vérification sur la version fusionnée (branche d'intégration, 17/11)
- Suite backend : 1412 réussis, 0 échec (`/home/claude/venv/bin/python -m pytest -q`).
- Front : `tsc --noEmit` et `npm run build` OK.
- Recettes : e2e_ui 30/30, l47_justification 10/10, l48_import vert, l49_bonnes_pratiques 14/14, mobile_l50 9/9, l40_partage vert.
- Fusion : CONTRACTS §18 = L48, §19 = L49, §20 = L47 ; i18n fr/en à parité (2201 clés).

**Reste ouvert.** Mesure automaint : Neo4j 48 → 19 constats (8 décisions groupées) ; Curiosity 42 → 41 constats (9 groupes). Question ouverte à Jerem (D-L47-01) : la cible « < 25 » se lit-elle en constats ou en groupes de décision ?
