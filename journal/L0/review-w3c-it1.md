# Revue W3C — contrats de lot L1…L7 + BACKLOG (itération 1)

Relecteur : w3c — 2 nov. 2026, 23 h. Fichiers relus : `lots/L1.md`…`lots/L7.md` (22 h 37–22 h 42), `docs/BACKLOG.md`, `docs/CONTRACTS.md`, `journal/decisions.md` (jusqu'à D-033), `backend/ontoforge/core/onto_model.py`.
Constat transversal : les lots ont été écrits **avant** D-028…D-033. Ils contredisent donc les décisions qui les remplacent (API à 36 endpoints, fixture `pg_auto.json`, `auto:`/`example.org`, `samples/auto/`, 25 règles, D-027). Les critères qui en dépendent ne sont pas exécutables tels quels.

```
verdict: KO
bloquants:
  - [lots/L1.md:9,93-97,116 ; L2.md:A2-A10 ; L3.md:28-35,A5 ; L4.md ; L6.md:A2,A8 ; L7.md:A3 ; BACKLOG.md:US-01]
    préfixe `auto: <https://example.org/auto#>` et chemins `samples/auto/` → contraire à D-030.
    Correction : remplacer partout par `am: <https://w3id.org/ontoforge/automaint#>` et `samples/automaint/`
    (ex. L1 A8 : `classes` contient `https://w3id.org/ontoforge/automaint#Vehicle`).
  - [lots/L7.md:A7] la regex d'exclusion rejette `w3id.org` → A7 échoue sur tous les samples dès D-030.
    Correction : `grep -rnoE "https?://[a-z0-9.-]+[^ \"'>]*" samples backend/tests | grep -vE "example\.(org|com)|w3\.org|w3id\.org/ontoforge|xmlns\.com|purl\.org|schema\.org|localhost"`
  - [lots/L1.md:A3,A13 + §« Contrat d'API »] 36 endpoints, `openapi.snapshot.json`, `GenerateOptions`/`GeneratedFile`,
    fixture `pg_auto.json` → remplacés par D-028 (CONTRACTS.md normatif, générateurs `dict[str,str]`, pas de fixture imposée).
    Correction : L1 A3 = « chaque ligne de docs/CONTRACTS.md §2 existe dans `app.openapi()` » ; supprimer A13 ;
    remplacer « exactement comme ARCHITECTURE §3.1 » (l. 39) par « exactement `core/onto_model.py` ».
  - [docs/CONTRACTS.md §1 shacl/validate.py] `inference: str = "rdfs"` par défaut ↔ L2 (« `inference:"none"` par défaut ») et oracle.
    Écart sémantique : en RDFS, `sh:closed` voit les super-propriétés entaillées. Démonstration : trap-shapes × trap.ttl,
    1 violation en `rdfs`. Les violations de trap-data ne sont garanties qu'en `none`.
    Correction : `inference: str = "none"` (décision à tracer), RDFS en option explicite.
  - [lots/L2.md:A2] « profil DL non conforme sur trap.ttl si le YAML le prévoit (ex. `auto:isPartOf` transitive … cardinalité) » :
    trap.ttl est OWL 2 DL par construction (`conformance.owl2_dl: true` dans le YAML). Le non-DL relève d'un fixture séparé.
    Correction : « A2 : `check_dl(trap.ttl)` → conforme ; issues == `conformance.issues` du YAML (code, subject, severity),
    aucune issue `error` ; A2bis : `samples/trap/trap-nondl.ttl` (w3c, L2) → une issue `error` par règle W3C-001…005,
    avec `specRef` = SS §4/§5.2/§5.8/§11.2/§9.3 ».
  - [lots/L3.md:24-25,A2,A10 ; BACKLOG.md:US-09] « 25 règles / 36 règles / 11 restantes » → D-031 (66 règles) et D-032 (28 règles it1, 38 en X00).
    Correction : A2 « `GET /api/rules` renvoie les 66 règles, `implemented: true` pour les 28 de D-032 » ; A10 « les 38 restantes ».
  - [lots/L3.md:A3] « findings produits absents du YAML : tolérés si auto, listés sinon » : la seconde branche n'est ni vraie
    ni fausse, donc non vérifiable. Correction : « … tolérés ; **échec** si un finding correspond à une entrée `must_not`
    du YAML (rule + subject [+ severity]) — exigé dès l'it1 (D-032) ».
  - [lots/L3.md:A3, A5] l'oracle compare `recommended` à des ids d'options. D-031 rend normatif le vocabulaire du YAML, mais L3
    ne le cite pas, et l'exemple A5 utilise `"multilabel"` (YAML : `multi_label`).
    Correction : « ids d'options = vocabulaire de `samples/trap/expected-findings.yaml` (D-031) » ; A5 : `{"C02:<iri am:Car>": "multi_label"}`.
  - [lots/L3.md:A5, D-020→D-028] le format d'id de constat n'est plus défini (D-028 remplace D-020 par `f"{rule}:{subject}"` + suffixe),
    mais les exemples gardent la CURIE `auto:Car`. Or CONTRACTS §3 impose des IRIs absolues. Pour A5 il faut un id
    déterministe. Correction : `id = f"{rule}:{subject_iri}"` (IRI absolue), suffixe `:{property_iri}` pour les constats de
    restriction (O09–O17, D13, I04), et pour les nœuds blancs `:{sha1 du triplet canonique}[:8]`.
blocking_rationale: chaque point ci-dessus fait échouer un critère, ou le rend non vérifiable, avec les décisions déjà actées.
```

## 1. Cohérence sémantique — non-bloquants
- **L3 exemples** : `RepairOrder` (≥ 3 rôles) relève désormais de **R02** (D-031). Les exemples K02 doivent mentionner « review : NODE KEY ajoute l'existence » (catalogue B2).
- **L3 O06 / samples/automaint** : si `am:isPartOf` est transitive **et** `owl:inverseOf am:hasPart`, alors `hasPart` est aussi non simple (SS §11.2). Aucune restriction de cardinalité sur `hasPart` dans `samples/automaint/*.ttl` (ex. « Car min 4 Wheel »), sinon L2 A3 (0 `error`) échoue. C'est pourquoi le piège sépare `hasPart` (simple) et `isComponentOf` (transitive).
- **L2 A9 (it2)** : bug owlrl 7.1.2 `prp-key` (dernière propriété de clé ignorée → tous les véhicules `sameAs`). Ajouter : « `reason(trap.ttl, engine="owlrl")` → `consistent: true` », ce qui impose le contournement documenté dans le skill.
- **L2 relecture** : ajouter « `only` ≠ `sh:class` » et « `rdfs:domain` ≠ `sh:targetSubjectsOf` + `sh:class` » (inférence vs validation) dans les deux skills.
- **L6 A2** : ajouter « chaque entité proposée a `labels.fr` et une IRI sous le namespace du projet ; `lint()` → 0 `error` sur le patch appliqué ». A8 : `PRIMARY KEY vin → hasKey` est correct, mais la proposition doit dire que hasKey n'impose ni existence ni unicité (→ shape `sh:minCount 1` proposée en parallèle).
- **L4 A4** : `IS NODE KEY` et `IS NOT NULL` exigent Neo4j **Enterprise**. Le DDL doit l'indiquer en commentaire ou proposer `IS UNIQUE` en Community (À VÉRIFIER, expert neo4j). « Aucune contrainte générée sans source » : un NODE KEY issu de K02 doit tracer la décision d'arbitrage (renforcement).
- **L1 A4** : le round-trip est exigé sur automaint. Sur trap, exiger au minimum « `graph_to_model(trap)` puis `model_to_graph` ⊆ graphe source (aucun triplet inventé), et (source − sortie) ⊆ triplets listés dans `unmapped` ».
- **BACKLOG US-06** : « profils DL/EL/QL/RL » en Must, mais L2 met EL/QL/RL en it2. Préciser « DL en it1 ».

## 2. `core/onto_model.py` (normatif, D-028) — écarts W3C restants (non-bloquants, à tracer)
- `ObjectProperty.inverse_of: Optional[str]` : plusieurs `owl:inverseOf` sont légaux → `list[str]` (sinon → `unmapped`).
- `owl:AllDisjointClasses` / `AllDisjointProperties` : seulement en `disjoint_with` par paires. Sémantiquement équivalent, mais le round-trip change la forme : accepter l'expansion et le documenter.
- Individus anonymes (nœuds blancs, SS §5.6.2) : `Individual.iri` sans drapeau `anonymous` → règle K04 non détectable sans convention. Proposer `iri="_:<id skolem>"` + `anonymous: bool`.
- `DatatypeProperty.range` (commentaire) cite `rdf:langString` : préciser « hors carte OWL 2, cf. W3C-001 ; préférer rdf:PlainLiteral ».
- `ClassExpr.data_range: str` : un DataOneOf/facette **à l'intérieur** d'une restriction part en `unmapped`. Acceptable en it1 (G01).
- GCI et annotations d'axiomes : pas de champ → `unmapped` (G01/C13/A02) : conforme à la règle « aucune perte silencieuse ».

```
non-bloquants: §1 et §2 ci-dessus
skill: skills/w3c-ontology-conformance/SKILL.md — ajout des pièges « inference par défaut de la validation SHACL » et « propriété non simple par inverse ».
```
