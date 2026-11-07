# L0 — réponse du chef à la revue w3c it1 (`journal/L0/review-w3c-it1.md`)

Pilote : chef — 2 nov. 2026, ~23 h 15. Contrats corrigés : `lots/L1.md` … `lots/L7.md`, `docs/BACKLOG.md`, `journal/decisions.md` (D-031bis, D-034 à D-036).
Contexte : une partie des bloquants visait la version 22 h 37–22 h 42 des lots ; les contrats avaient été réécrits entre-temps (alignement D-028 → D-033). Chaque point ci-dessous a été revérifié sur la version courante.

## Bloquants

| # | Bloquant | Traitement |
|---|---|---|
| B1 | Préfixe `auto:` / `example.org` / `samples/auto/` | **Fait.** Partout `am: <https://w3id.org/ontoforge/automaint#>` et `samples/automaint/` (D-030). Vérifié : `grep -nE "auto:\|example\.org/auto\|samples/auto/" lots/*.md docs/BACKLOG.md` → aucune sortie. |
| B2 | L7 A7 rejette `w3id.org` | **Fait**, avec la regex proposée (chemin inclus) + `creativecommons.org` (licence du piège). Rejouée sur `samples/` : aucune sortie. |
| B3 | L1 : 36 endpoints, snapshot OpenAPI, `GeneratedFile`, fixture `pg_auto.json` | **Fait.** L1 renvoie à CONTRACTS.md §2 : A12 = « chaque ligne de CONTRACTS §2 existe dans `app.openapi()` » ; fixture supprimée (D-028) ; plus aucune redéfinition de modèle (« exactement `core/*.py` »). |
| B4 | Inférence SHACL par défaut `rdfs` dans CONTRACTS | **Fait côté contrats, reste une action lead.** Décision **D-034** (`inference="none"` par défaut) ; L2 A6bis vérifie la valeur par défaut ; A2 (8 violations, `none`) et A3 (1 violation, `rdfs` explicite) séparés. CONTRACTS.md (propriété du lead) est à corriger : demandé au lead. |
| B5 | L2 : piège non-DL | **Fait.** A5 : `profiles["DL"] is True` sur `trap.ttl` ; A6 : `samples/trap/trap-nondl.ttl` (w3c, L2, D-036) → une issue `error` par règle W01…W05 avec `spec_ref` SS §4/§5.2, §5.8, §11.2, §5.9, §9.3. W06 (raisonneur) en It2, W07 (avertissements) en It1. |
| B6 | Nombre de règles (25 / 36 / 11) | **Fait.** 66 règles (D-031, confirmée D-031bis), 28 en It1 (D-032), 38 en `X00` puis It2. **Écart à la correction proposée** : CONTRACTS §2 n'a pas d'endpoint `GET /api/rules` ; A2a vérifie donc le **registre `mapping.rules`** (66 ids = ceux du YAML, `implemented` vrai pour les 28). L'endpoint est en Could (US-43). |
| B7 | L3 A3 : « listés sinon » invérifiable | **Fait.** A3 : findings hors YAML tolérés ; **échec** si un finding correspond à une entrée `must_not` (rule + subject [+ severity]), pour les deux cibles, dès l'It1. |
| B8 | Vocabulaire d'options / `multilabel` | **Fait.** L3 Périmètre : vocabulaire normatif = `expected-findings.yaml` (D-031) ; A5 et L7 A3 utilisent `multi_label`. |
| B9 | Format des ids de constats | **Fait.** Décision **D-035** : `f"{rule}:{subject_iri}"`, suffixe `:{property_iri}` (O09–O17, D13, I04), `:{sha1[:8]}` pour l'anonyme ; exemples à IRI absolue dans L3 ; A5 vérifie la conformité des ids. (Note : le message de synthèse évoquait `[#suffixe]` ; j'applique la forme `:` de la revue écrite, `#` étant déjà présent dans les IRIs.) |

## Non-bloquants

| Point | Traitement |
|---|---|
| L3 exemples : RepairOrder → R02, K02 « NODE KEY ajoute l'existence » | Fait : exemples R01 = `am:PartInstallation`, R02 = `am:WarrantyClaim` ; K02 en review avec `node_key` « renforcement ». |
| `hasPart` non simple si inverse d'une transitive | Fait : contrainte de modélisation ajoutée à L1 pour `samples/automaint/automaint.ttl`. |
| L2 A11 owlrl `consistent: true` | Fait (It2, contournement prp-key). |
| L2 relecture : `only` ≠ `sh:class`, `rdfs:domain` ≠ `sh:targetSubjectsOf` + `sh:class` | Fait. |
| L6 A2 : `labels.fr`, IRI sous le namespace, 0 `error` ; A8 note hasKey + `sh:minCount 1` | Fait. |
| L4 A5 : Enterprise pour NODE KEY / NOT NULL, traçabilité K02 | Fait (À VÉRIFIER par neo4j). |
| L1 A4 sur trap : sortie ⊆ source, (source − sortie) ⊆ `unmapped` | Fait (A4 réécrit, A5 round-trip strict limité à automaint). |
| BACKLOG US-06 → « DL en it1 » | Fait (US-04 : DL seul en It1, EL/QL/RL en US-23). |
| §2 écarts `core/onto_model.py` (inverse_of liste, AllDisjoint, individus anonymes, langString, data_range) | Transmis au lead (propriétaire de core, D-028) ; aucun changement de contrat sans décision. Les formes réécrites sont admises par L1 A4 ; individus anonymes : convention à fixer par lead + w3c avant L3 (K04 est hors It1, donc non bloquant mardi). |

Tests : sans objet (L0 ne livre pas de code). Contrôles rejoués : pyshacl trap-data (8 violations V1–V8, `none`), trap.ttl en `rdfs` (1 violation), couverture YAML (66 règles, 79 entrées, ids uniques, sujets présents), regex L7 A7.

---

# Itération 2 (chef, mar. 3 nov. 03 h) — contrats réalignés sur l'état réel

Contexte : entre-temps 14 commits (L1 io+API, L2 shacl, L4 Curiosity/Neo4j/requêtes). Relecture des rapports `journal/L1`, `L2`, `L4`, de `git log`, de `CONTRACTS.md` et rejeu de la suite (`186 verts / 3 rouges`, `npm run build` rouge). Les 9 bloquants de la revue w3c it1 sont **tous traités** (tableau ci-dessus), et leur état a été **revérifié sur les fichiers courants** :

| # | Bloquant | Vérification it2 |
|---|---|---|
| B1 | `auto:` / `samples/auto/` | `grep -nE "auto:\|example\.org/auto\|samples/auto/" lots/*.md docs/BACKLOG.md` → vide ; samples réels dans `samples/automaint/` et `samples/trap/`. |
| B2 | regex L7 A7 | conservée. |
| B3 | 36 endpoints / snapshot / `GeneratedFile` | L1 A12 = `tests/test_api_contract.py` (27 routes de CONTRACTS §2 vérifiées, vert). `GeneratedFile` absent de `pg_model.py` comme attendu. |
| B4 | inférence SHACL | **Clos** : CONTRACTS §1 porte `inference: str = "none"`, `validate.py` aussi, `test_default_inference_is_none` vert (L2 A6bis). L'action « lead » est faite. |
| B5 | non-DL | `trap-nondl.ttl` existe ; `test_trap_nondl_triggers_each_rule` vert pour W01–W05 ; **W06/W07 rouges** (attente du test inversée, w3c). |
| B6 | 66 règles | profils Curiosity (66) et Neo4j (66 + X00) alignés sur le YAML (`test_recommendations_cover_66_rules_with_oracle_vocabulary`). Registre `mapping.rules` : à créer par le lead (L3 A2a). |
| B7 | `must_not` | exigé L3 A3, inchangé. |
| B8 | `multi_label` | inchangé ; les profils utilisent le vocabulaire du YAML (rapports curiosity/neo4j). |
| B9 | ids de constats | D-035 ; à implémenter dans `engine.py` (L3 A5). |

## Corrections apportées aux contrats en it2
1. **Noms de fichiers de tests** alignés sur la réalité (`test_io_import_export.py`, `test_io_dsl.py`, `test_shacl_{io,validate,owl_to_shacl,to_pg}.py`, `test_conformance_profiles.py`, `test_api_projects.py`, `test_api_contract.py`) : les commandes `-k` des critères sont désormais exécutables telles quelles pour tout ce qui est livré ; les tests encore à écrire sont marqués « à ajouter par <agent> ».
2. **Goldens supprimés** (D-038) ; **tree-sitter** conservé mais explicitement rouge tant que `tree_sitter` n'est pas installé (paquets absents de `pyproject.toml`, action lead).
3. **Avance It2** (D-041) reconnue dans L1 (DSL), L2 (EL/QL/RL, reasoner, generate), L4 (ingestion, GraphQL, traduction), BACKLOG (section « État réel »).
4. **Chemin critique L3** (D-039), jalons horaires et seuil de coupe ; **heures de clôture** mises à jour : L1 09 h, L2 08 h, L3 11 h, L4 13 h, L5 16 h, L6 16 h, L7 19 h.
5. **Nouveaux écarts détectés** : Dockerfile encore Java (D-040) ; `trap-nondl.ttl` pollue l'exemple `trap` (D-037) ; build front rouge et `frontend/scripts/*` absents (L5) ; `assistant/service.py` + mock absents (L6) ; `README.md`, `docs/RECETTE.md`, `test_e2e.py` absents (L7).

## Demandes aux propriétaires (non bloquantes pour le contrat, bloquantes pour la clôture)
- **lead** : Dockerfile sans Java ; `samples.py` ignore `*-nondl.*` ; `pyproject` dev += tree-sitter, tree-sitter-c-sharp, graphql-core ; moteur selon jalons ; build front ; `service.py` + mock ; `README.md`, `test_e2e.py`.
- **w3c** : corriger l'attente W06/W07 (ou le code), ajouter `test_automaint_no_error` et `test_trap_no_invented_triple` ; revue de `core/onto_model.py` §2 de la revue it1 (à tracer).
- **curiosity** : `test_treesitter` après installation des paquets ; décision `Decimal` en D-L4-01 (déjà).

Tests rejoués par le chef : `cd backend && /home/claude/venv/bin/python -m pytest -q` → 186 passed, 3 failed (liste ci-dessus) ; `cd frontend && npm run build` → 3 erreurs TS.
