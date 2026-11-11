# The 66 transposition rules, explained {#les-66-regles-de-transposition-expliquees}

This guide is the explanatory rendering of the normative rule catalog `backend/ontoforge/mapping/rules/catalog.py` (reference rendering: [`docs/RULES.md`](../RULES.md)). Each rule has an OWL example in Turtle, the recommended transposition to **Curiosity** and to **Neo4j**, what is lost, and the planned compensation.

## Reading a rule entry {#lire-une-fiche}

- **Severity**: `auto` (trivial, applied without asking), `review` (a loss is possible, you decide), `lost` (no native equivalent: the loss is certain until you pick a compensation).
- **Recommendation**: the option applied until you decide (`Finding.recommended`). Option identifiers (`validation`, `multi_label`…) come from the normative vocabulary of `samples/trap/expected-findings.yaml`.
- **Finding identifier**: `<rule>:<subject IRI>`, with a suffix for restrictions (`:<property IRI>`) or for an anonymous construct (`:<sha1[:8]>`). Grouped decision: `"<rule>:*": option`.
- **Trap example**: the rule's subject in `samples/trap/trap.ttl` (prefix `am:` = `https://w3id.org/ontoforge/automaint#`), the "trap" ontology that exercises all 66 rules.
- **Open world / closed world**: OWL *infers* (OWA, no UNA), the property graph *constrains* (closed world, UNA). Turning an axiom into a constraint is a **strengthening**, and the report says so.

All examples below share the following header (omitted afterwards) and were **verified by execution**: each snippet, run through `parse_ontology` then `analyze` (Curiosity and Neo4j targets), produces a finding for the announced rule. The class and property declarations needed for detection are included. S01 and S02 were verified with their shapes (`parse_shapes`); G02 is a JSON exchange with the API.

```turtle
@prefix ex: <http://example.org/doc#> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
```

Rules S01, S02 (OWL/SHACL conflicts) and G02 (invalid decision) are engine tooling, outside the 66.

## Index {#index}

| ID | Rule | Sev. | Curiosity | Neo4j | Compensation |
|---|---|---|---|---|---|
| **C01** | Class → node type | auto | `node_type` | `label` | none |
| **C02** | Single inheritance | review | `flatten_into_leaves` | `multi_label` | none |
| **C03** | Multiple inheritance | review | `primary_parent_discriminator` | `multi_label` | Human decision |
| **C04** | Probably abstract class | review | `merge_into_leaves` | `secondary_label` | Detection / classification query |
| **C05** | Equivalent named classes | review | `merge_types` | `merge_types` | Documentation |
| **C06** | Defined class (classification) | lost | `materialize_at_ingest` | `computed_label` | Materialization |
| **C07** | Class disjointness | lost | `validation` | `validation` | Validation |
| **C08** | Enumerated class | review | `reference_nodes` | `reference_nodes` | Validation |
| **C09** | Anonymous Boolean expression | lost | `doc_only` | `secondary_label` | Documentation |
| **C10** | Disjoint union (partition) | review | `primary_parent_discriminator` | `multi_label` | Validation |
| **C11** | Class complement | lost | `materialize_at_ingest` | `computed_label` | Materialization |
| **C12** | Class / individual punning | review | `reference_nodes` | `reference_nodes` | Documentation |
| **C13** | General class inclusion axiom | lost | `materialize_at_ingest` | `computed_label` | Materialization |
| **K01** | IRI identity | auto | `uri_key` | `unique_constraint` | none |
| **K02** | OWL key (hasKey) | review | `uri_key` | `node_key` | Validation |
| **K03** | No business key | review | `uri_key` | `uri_key` | Human decision |
| **K04** | Anonymous individual | review | `generated_key` | `generated_key` | Materialization |
| **K05** | Composite key with an object property | review | `key_concat` | `materialize_key` | Materialization |
| **D01** | Data property | auto | `property` | `property` | none |
| **D02** | Property without a domain | review | `attach_to_users` | `attach_to_users` | Human decision |
| **D03** | Union domain | review | `duplicate_per_type` | `duplicate_per_type` | none |
| **D04** | Non-functional property | review | `scalar` | `scalar` | none |
| **D05** | Lossy datatype | review | `native_type` | `native_type` | Validation |
| **D06** | Multilingual values | review | `per_language_property` | `per_language_property` | none |
| **D07** | Functional property | auto | `scalar` | `scalar` | none |
| **D08** | Literal enumeration | review | `enum_property` | `enum_property` | Validation |
| **D09** | Datatype with facets | review | `validation` | `validation` | Validation |
| **D10** | Untyped literal | review | `string_property` | `string_property` | none |
| **D11** | Data subproperty | lost | `most_specific_type` | `most_specific_type` | Materialization |
| **D12** | Domain / range intersection | review | `native_type` | `native_type` | Validation |
| **D13** | Restriction on a data property | review | `validation` | `validation` | Validation |
| **O01** | Object property → relationship | auto | `edge_pair` | `relationship` | none |
| **O02** | Missing domain / range | review | `edge_pair` | `relationship` | Human decision |
| **O03** | Union domain / range | review | `edge_pair` | `relationship` | Validation |
| **O04** | Inverse properties | auto | `edge_pair` | `single_direction` | none |
| **O05** | Symmetric property | review | `self_reverse` | `undirected_query` | none |
| **O06** | Transitive property | lost | `materialize_closure` | `var_length_query` | Materialization |
| **O07** | Object subproperty | lost | `most_specific_type` | `most_specific_type` | Materialization |
| **O08** | Property chain | lost | `materialize_closure` | `path_query` | Materialization |
| **O09** | Relationship cardinality ≤ 1 (max / exactly / functional) | review | `validation` | `validation` | Validation |
| **O10** | Relationship existence | review | `validation` | `validation` | Validation |
| **O11** | Universal restriction | lost | `validation` | `validation` | Validation |
| **O12** | Fixed value | review | `validation` | `validation` | Validation |
| **O13** | Property characteristics | lost | `validation` | `validation` | Validation |
| **O14** | Anonymous inverse property | review | `reverse_traversal` | `reverse_traversal` | Validation |
| **O15** | Inverse-functional property | review | `validation` | `validation` | Validation |
| **O16** | Qualified cardinality | review | `validation` | `validation` | Validation |
| **O17** | hasSelf restriction | lost | `materialize_at_ingest` | `validation` | Materialization |
| **O18** | Universal superproperty | auto | `ignore` | `ignore` | Documentation |
| **O19** | Equivalent properties | review | `merge_relationship_types` | `merge_relationship_types` | Documentation |
| **O20** | Disjoint properties | lost | `validation` | `validation` | Validation |
| **O21** | Domain / range intersection | review | `intersection_domain` | `intersection_domain` | Human decision |
| **R01** | Binary reification | review | `keep_node` | `dereify_relationship` | none |
| **R02** | N-ary relationship | review | `keep_node` | `keep_node` | none |
| **A01** | Annotations | auto | `schema_metadata` | `schema_metadata` | Documentation |
| **A02** | Axiom annotation | review | `report` | `report` | Documentation |
| **A03** | Deprecated entity | auto | `exclude` | `exclude` | none |
| **M01** | Ontology metadata | auto | `schema_metadata` | `schema_metadata` | Documentation |
| **M02** | Ontology import | review | `external_reference` | `external_reference` | Human decision |
| **G01** | Construct not transposed | lost | `report` | `report` | Documentation |
| **I01** | Individual | review | `reference_nodes` | `reference_nodes` | Human decision |
| **I02** | Identity (sameAs) | lost | `merge_nodes` | `merge_nodes` | Materialization |
| **I03** | Individual difference | auto | `noop_una` | `noop_una` | none |
| **I04** | Negative assertion | lost | `validation` | `validation` | Validation |
| **I05** | Multi-typed individual | review | `primary_parent_discriminator` | `multi_label` | Human decision |
| **N01** | Naming | auto | `rename` | `rename` | Renaming |
| **S01** | OWL / SHACL conflict | review | `shacl_wins` | `shacl_wins` | Human decision |
| **S02** | Property from the shapes | review | `property` | `property` | none |
| **G02** | Decision ignored | review | `report` | `report` | Human decision |

## Classes (C) {#classes-c}

### C01 — Class → node type *(Must, iteration 1)* {#c01-classe-type-de-noeud-must-it-1}

- **Construct**: Named owl:Class
- **Detection**: Any declared named class.
- **Severity**: auto (applied directly)
- **Example in trap**: `am:MotorVehicle`

**OWL example**

```turtle
ex:Vehicle a owl:Class .
```

**Curiosity** - Recommendation `node_type` - Node type: A [Node] node type (C# class).
  Rationale: Direct mapping.

**Neo4j** - Recommendation `label` - Label: A PascalCase label.
  Rationale: Direct mapping.

**What is lost**: Nothing: direct mapping.

**Compensation**: none

### C02 — Single inheritance *(Must, iteration 1)* {#c02-heritage-simple-must-it-1}

- **Construct**: rdfs:subClassOf (single named parent)
- **Detection**: Class with exactly one effective named parent.
- **Severity**: review (to decide)
- **Example in trap**: `am:Vehicle`

**OWL example**

```turtle
ex:Vehicle a owl:Class .
ex:Car   a owl:Class ; rdfs:subClassOf ex:Vehicle .
ex:Truck a owl:Class ; rdfs:subClassOf ex:Vehicle .
ex:veh_001 a ex:Vehicle .   # direct instance: the class is not abstract
```

**Curiosity** - Recommendation `flatten_into_leaves` - Flatten onto the concrete root: The subclasses of the hierarchy are folded into the root's node type (properties copied) with a `<root>Kind` discriminator; their restrictions become validations filtered by discriminator; subtype queries become filters.
  Rationale: Curiosity is single-type (one node = one C# class): the hierarchy is flattened and the discriminator stays filterable and usable as a facet.
  Other options: `multi_label` (Multi-labels), `node_type` (Separate node type).

**Neo4j** - Recommendation `multi_label` - Multi-labels: Neo4j: the node carries its label and those of its ancestors (parent queries stay natural). Curiosity: no multi-type, falls back to a `types` list (multi-valued property) on the concrete type.
  Rationale: Neo4j carries several labels per node: inheritance passes through with no loss of queryability.
  Other options: `flatten_into_leaves` (Flatten onto the concrete root), `node_type` (Separate node type).

**What is lost**: The `subClassOf` link can no longer be inferred. Under Curiosity (single-type) the subclass only survives as a discriminator value, and the query "all Vehicles" has to filter.

**Compensation**: none

### C03 — Multiple inheritance *(Must, iteration 1)* {#c03-heritage-multiple-must-it-1}

- **Construct**: Multiple inheritance
- **Detection**: Class with at least two effective named parents.
- **Severity**: review (to decide)
- **Example in trap**: `am:HybridVehicle`

**OWL example**

```turtle
ex:Petrol   a owl:Class .
ex:Electric a owl:Class .
ex:Hybrid   a owl:Class ; rdfs:subClassOf ex:Petrol, ex:Electric .
```

**Curiosity** - Recommendation `primary_parent_discriminator` - Main parent + discriminator: One main parent carries the type; the other memberships become `is<Parent>` booleans.
  Rationale: Single-type: only one ancestor can define the node type (the one richest in properties).
  Other options: `multi_label` (Multi-labels), `node_type` (Separate node type).

**Neo4j** - Recommendation `multi_label` - Multi-labels: All parents become labels (Neo4j); Curiosity: a list of types.
  Rationale: No limit on the number of labels.
  Other options: `primary_parent_discriminator` (Main parent + discriminator), `node_type` (Separate node type).

**What is lost**: Curiosity: membership of the secondary parents becomes an `is<Parent>` boolean (or a list), and the membership inference disappears.

**Compensation**: Human decision (no automatic compensation)

### C04 — Probably abstract class *(Must, iteration 1)* {#c04-classe-probablement-abstraite-must-it-1}

- **Construct**: Probably abstract class
- **Detection**: OWA heuristic: class with subclasses, no direct instance, no key, involved in at most one object property, outside a disjointUnion (C10).
- **Severity**: review (to decide)
- **Example in trap**: `am:MotorVehicle`

**OWL example**

```turtle
ex:Vehicle a owl:Class .
ex:Car   a owl:Class ; rdfs:subClassOf ex:Vehicle .
ex:Truck a owl:Class ; rdfs:subClassOf ex:Vehicle .
# no direct instance of ex:Vehicle, no key
```

**Curiosity** - Recommendation `merge_into_leaves` - Merge into the leaves: No node type: its properties and relations are copied into each concrete subtype.
  Rationale: Under OWA, the absence of a direct instance cannot be proven: this is a heuristic to confirm.
  Other options: `node_type` (Keep a node type).

**Neo4j** - Recommendation `secondary_label` - Secondary label only: Abstract type: the label is carried by the subclasses' nodes, never alone.
  Rationale: Under OWA, the absence of a direct instance cannot be proven: this is a heuristic to confirm.
  Other options: `merge_into_leaves` (Merge into the leaves), `node_type` (Keep a node type).

**What is lost**: The "abstract" heuristic is a hypothesis (open world: the absence of a direct instance cannot be proven). If it is wrong, instances of the parent class lose their type.

**Compensation**: Detection / classification query

### C05 — Equivalent named classes *(Must, iteration 1)* {#c05-classes-nommees-equivalentes-must-it-1}

- **Construct**: owl:equivalentClass between named classes
- **Detection**: equivalentClass whose argument is named.
- **Severity**: review (to decide)
- **Example in trap**: `am:Car`

**OWL example**

```turtle
ex:Car a owl:Class . ex:Automobile a owl:Class .
ex:Car owl:equivalentClass ex:Automobile .
```

**Curiosity** - Recommendation `merge_types` - Merge (canonical name + alias): A single type; the other IRI becomes a documented alias (same extension: no loss).
  Rationale: EquivalentClasses(A B) with named A and B: identical extensions, merging loses nothing.
  Other options: `node_type` (Two separate types).

**Neo4j** - Recommendation `merge_types` - Merge (canonical name + alias): A single type; the other IRI becomes a documented alias (same extension: no loss).
  Rationale: EquivalentClasses(A B) with named A and B: identical extensions, merging loses nothing.
  Other options: `node_type` (Two separate types).

**What is lost**: Nothing on the data if the classes are merged (same extensions). The alias IRI only survives in the documentation.

**Compensation**: Documentation (transposition report)

### C06 — Defined class (classification) {#c06-classe-definie-classification}

- **Construct**: Defined class (anonymous equivalentClass: restriction / intersection)
- **Detection**: Named class with a necessary and sufficient definition.
- **Severity**: lost (certain loss without compensation)
- **Example in trap**: `am:OverdueVehicle`

**OWL example**

```turtle
ex:OverdueVehicle a owl:Class . ex:Vehicle a owl:Class . ex:Defect a owl:Class .
ex:OverdueVehicle owl:equivalentClass [ owl:intersectionOf ( ex:Vehicle
    [ a owl:Restriction ; owl:onProperty ex:hasDefect ; owl:someValuesFrom ex:Defect ] ) ] .
```

**Curiosity** - Recommendation `materialize_at_ingest` - Materialize at ingestion: An `is<Class>` boolean computed by the connector.
  Rationale: No reasoner on the LPG side: defined membership must be computed and stored, or lost.
  Other options: `computed_label` (Computed label), `doc_only` (Document only).

**Neo4j** - Recommendation `computed_label` - Computed label: A classification job (query) replayed after each ingestion.
  Rationale: No reasoner on the LPG side: defined membership must be computed and stored, or lost.
  Other options: `materialize_at_ingest` (Materialize at ingestion), `doc_only` (Document only).

**What is lost**: The necessary and sufficient definition is no longer evaluated. Without a reasoner, membership has to be computed (a boolean at ingestion or a classification query).

**Compensation**: Materialization (derived property or edge recomputed after ingestion)

### C07 — Class disjointness *(Must, iteration 1)* {#c07-disjonction-de-classes-must-it-1}

- **Construct**: owl:disjointWith / owl:AllDisjointClasses
- **Detection**: Class declaring disjointness axioms.
- **Severity**: lost (certain loss without compensation)
- **Example in trap**: `am:Customer`

**OWL example**

```turtle
ex:Customer a owl:Class . ex:Garage a owl:Class .
ex:Customer owl:disjointWith ex:Garage .
```

**Curiosity** - Recommendation `validation` - Application-level validation: The constraint becomes a check run at ingestion (connector) or a detection query; nothing is blocked natively by the database.
  Rationale: Single-type: disjointness is guaranteed between distinct types; validate if classes are merged.
  Other options: `ignore` (Ignore).

**Neo4j** - Recommendation `validation` - Application-level validation: The constraint becomes a check run at ingestion (connector) or a detection query; nothing is blocked natively by the database.
  Rationale: No native constraint: a detection query for a node carrying both labels.
  Other options: `ignore` (Ignore).

**What is lost**: No database rejects a node carrying both types. Disjointness becomes an application-level check (or a detection query).

**Compensation**: Validation (check at ingestion or detection query)

### C08 — Enumerated class {#c08-classe-enumeree}

- **Construct**: owl:oneOf (enumerated class)
- **Detection**: Class defined as an enumeration of individuals.
- **Severity**: review (to decide)
- **Example in trap**: `am:FuelType`

**OWL example**

```turtle
ex:FuelType a owl:Class .
ex:FuelType owl:equivalentClass [ a owl:Class ; owl:oneOf ( ex:Petrol ex:Diesel ) ] .
ex:Petrol a ex:FuelType . ex:Diesel a ex:FuelType .
```

**Curiosity** - Recommendation `reference_nodes` - Reference nodes: One type, one node per value, linked by a relationship: linked facets, renaming without denormalization.
  Rationale: The values carry multilingual labels: reference nodes preserve them.
  Other options: `enum_property` (Enumerated property).

**Neo4j** - Recommendation `reference_nodes` - Reference nodes: One type, one node per value, linked by a relationship: linked facets, renaming without denormalization.
  Rationale: The values carry multilingual labels: reference nodes preserve them.
  Other options: `enum_property` (Enumerated property).

**What is lost**: The closed nature of the enumeration ("nothing but these values") is only enforced by a validation.

**Compensation**: Validation (check at ingestion or detection query)

### C09 — Anonymous Boolean expression {#c09-expression-booleenne-anonyme}

- **Construct**: Anonymous owl:unionOf / owl:intersectionOf
- **Detection**: Anonymous union/intersection in an equivalence or superclass position (outside the C06 definitions).
- **Severity**: lost (certain loss without compensation)
- **Example in trap**: `am:Owner`

**OWL example**

```turtle
ex:Owner a owl:Class . ex:Person a owl:Class . ex:Company a owl:Class .
ex:Owner owl:equivalentClass [ owl:unionOf ( ex:Person ex:Company ) ] .
```

**Curiosity** - Recommendation `doc_only` - Document only: Nothing is generated: the semantics are lost for the data and recorded in the report.
  Rationale: There is no anonymous type in an LPG; the set semantics are lost unless a grouping label is used.

**Neo4j** - Recommendation `secondary_label` - Computed label on the members: The union's name becomes a label carried by the member classes' nodes.
  Rationale: There is no anonymous type in an LPG; the set semantics are lost unless a grouping label is used.
  Other options: `doc_only` (Document only).

**What is lost**: The set semantics of the union have no equivalent. Owner is only "Person or Company" in the report (or through a grouping label in Neo4j).

**Compensation**: Documentation (transposition report)

### C10 — Disjoint union (partition) {#c10-union-disjointe-partition}

- **Construct**: owl:disjointUnionOf
- **Detection**: Class partitioned into disjoint subclasses.
- **Severity**: review (to decide)
- **Example in trap**: `am:MaintenanceOperation`

**OWL example**

```turtle
ex:Operation a owl:Class . ex:Inspection a owl:Class . ex:Repair a owl:Class .
ex:Operation owl:disjointUnionOf ( ex:Inspection ex:Repair ) .
```

**Curiosity** - Recommendation `primary_parent_discriminator` - Parent type + mandatory discriminator: A parent node type + a mandatory `<parent>Kind` enum (exactly one value).
  Rationale: The partition becomes a completeness and exclusivity constraint, to be validated.
  Other options: `multi_label` (Parent + child labels), `validation` (Application-level validation).

**Neo4j** - Recommendation `multi_label` - Parent + child labels: Parent and child labels + an "exactly one child label" validation.
  Rationale: The partition becomes a completeness and exclusivity constraint, to be validated.
  Other options: `primary_parent_discriminator` (Parent type + mandatory discriminator), `validation` (Application-level validation).

**What is lost**: Completeness and exclusivity become checks ("exactly one value of `operationKind`"). The database blocks nothing.

**Compensation**: Validation (check at ingestion or detection query)

### C11 — Class complement {#c11-complement-de-classe}

- **Construct**: owl:complementOf
- **Detection**: Complement in a definition or a superclass.
- **Severity**: lost (certain loss without compensation)
- **Example in trap**: `am:NonElectricVehicle`

**OWL example**

```turtle
ex:NonElectric a owl:Class . ex:Electric a owl:Class .
ex:NonElectric owl:equivalentClass [ a owl:Class ; owl:complementOf ex:Electric ] .
```

**Curiosity** - Recommendation `materialize_at_ingest` - Materialize at ingestion: A boolean computed by the connector.
  Rationale: The OWL complement (open world) becomes default negation (closed world): over-classification is possible.
  Other options: `computed_label` (Label computed by query (NOT)), `doc_only` (Document only).

**Neo4j** - Recommendation `computed_label` - Label computed by query (NOT): Classification by the absence of a label/property: closed world, to be replayed.
  Rationale: The OWL complement (open world) becomes default negation (closed world): over-classification is possible.
  Other options: `materialize_at_ingest` (Materialize at ingestion), `doc_only` (Document only).

**What is lost**: The OWL complement (open world) becomes default negation (closed world), so over-classification is possible: a vehicle not yet typed would be "NonElectric".

**Compensation**: Materialization (derived property or edge recomputed after ingestion)

### C12 — Class / individual punning {#c12-punning-classe-individu}

- **Construct**: Class / individual punning (SS §5.9)
- **Detection**: Same IRI declared as both a class and an individual.
- **Severity**: review (to decide)
- **Example in trap**: `am:TimingBelt`

**OWL example**

```turtle
ex:PartKind a owl:Class .
ex:TimingBelt a owl:Class, ex:PartKind .   # same IRI: class AND individual
```

**Curiosity** - Recommendation `reference_nodes` - Type + reference node, distinct names: The node type (class) and the reference node (individual) coexist under distinct names.
  Rationale: Legal metamodeling in OWL 2 DL; in an LPG, two distinct elements.
  Other options: `ignore` (Ignore the individual).

**Neo4j** - Recommendation `reference_nodes` - Type + reference node, distinct names: The node type (class) and the reference node (individual) coexist under distinct names.
  Rationale: Legal metamodeling in OWL 2 DL; in an LPG, two distinct elements.
  Other options: `ignore` (Ignore the individual).

**What is lost**: Punning does not exist in an LPG. The class and the individual become two distinct elements, and the identity link is only documented.

**Compensation**: Documentation (transposition report)

### C13 — General class inclusion axiom {#c13-axiome-general-d-inclusion}

- **Construct**: General class inclusion axiom (GCI)
- **Detection**: rdfs:subClassOf with an anonymous subject.
- **Severity**: lost (certain loss without compensation)
- **Example in trap**: `am:RequiresDPFCheck`

**OWL example**

```turtle
ex:Dpf a owl:Class . ex:RequiresDPFCheck a owl:Class .
[ a owl:Restriction ; owl:onProperty ex:hasDpf ; owl:someValuesFrom ex:Dpf ]
    rdfs:subClassOf ex:RequiresDPFCheck .
```

**Curiosity** - Recommendation `materialize_at_ingest` - Materialize at ingestion: A boolean computed by the connector.
  Rationale: An inference rule with no LPG equivalent.
  Other options: `computed_label` (Classification job), `doc_only` (Document only).

**Neo4j** - Recommendation `computed_label` - Classification job: A query that sets the concluded label.
  Rationale: An inference rule with no LPG equivalent.
  Other options: `materialize_at_ingest` (Materialize at ingestion), `doc_only` (Document only).

**What is lost**: An inference rule (GCI) with no equivalent. The conclusion is only asserted if you compute it (a boolean at ingestion or a query).

**Compensation**: Materialization (derived property or edge recomputed after ingestion)


## Identity and keys (K) {#identite-et-cles-k}

### K01 — IRI identity *(Must, iteration 1)* {#k01-identite-iri-must-it-1}

- **Construct**: IRI identity of a named individual
- **Detection**: Named individual (IRI).
- **Severity**: auto (applied directly)
- **Example in trap**: `am:veh_001`

**OWL example**

```turtle
ex:Vehicle a owl:Class .
ex:veh_001 a ex:Vehicle .
```

**Curiosity** - Recommendation `uri_key` - Key = uri: [Key] string = IRI (Curiosity).
  Rationale: The IRI is unique, stable and non-empty.

**Neo4j** - Recommendation `unique_constraint` - uri property + UNIQUE: RDF identity kept, idempotent MERGE.
  Rationale: The IRI is unique, stable and non-empty.

**What is lost**: Nothing: the IRI becomes the key (`Uri` / `uri`).

**Compensation**: none

### K02 — OWL key (hasKey) *(Must, iteration 1)* {#k02-cle-owl-haskey-must-it-1}

- **Construct**: owl:hasKey on data properties
- **Detection**: HasKey axiom over data properties only.
- **Severity**: review (to decide)
- **Example in trap**: `am:Vehicle`

**OWL example**

```turtle
ex:Vehicle a owl:Class .
ex:vin a owl:DatatypeProperty, owl:FunctionalProperty ; rdfs:domain ex:Vehicle ; rdfs:range xsd:string .
ex:Vehicle owl:hasKey ( ex:vin ) .
```

**Curiosity** - Recommendation `uri_key` - Key = uri, uniqueness validated: The key stays the IRI; uniqueness of the hasKey values becomes an application-level validation.
  Rationale: The Curiosity [Key] must be non-empty on every node: putting the key on a property the ontology does not make mandatory is a strengthening; uri stays safe and the business key is validated.
  Other options: `node_key` (Key = hasKey properties), `key_concat` (Concatenation).

**Neo4j** - Recommendation `node_key` - Key = hasKey properties: Neo4j: NODE KEY (existence + uniqueness, Enterprise; UNIQUE in Community). Curiosity: [Key] = the property. STRENGTHENING: hasKey enforces neither existence nor uniqueness.
  Rationale: hasKey (SS §9.5) infers sameAs between named individuals with the same values; NODE KEY adds mandatory existence: a strengthening to be validated.
  Other options: `unique_constraint` (UNIQUE only), `uri_key` (Key = uri, uniqueness validated).

**What is lost**: In OWL, `hasKey` imposes neither existence nor uniqueness, while the LPG key (NODE KEY / `[Key]`) imposes both. This is a strengthening, hence the cautious recommendation for Curiosity (key = IRI, uniqueness of `vin` validated).

**Compensation**: Validation (check at ingestion or detection query)

### K03 — No business key *(Must, iteration 1)* {#k03-pas-de-cle-metier-must-it-1}

- **Construct**: Class without a business key
- **Detection**: Concrete class with no hasKey (and no ancestor with a key).
- **Severity**: review (to decide)
- **Example in trap**: `am:MileageReading`

**OWL example**

```turtle
ex:MileageReading a owl:Class .   # no business key
```

**Curiosity** - Recommendation `uri_key` - Key = uri: Technical identifier (IRI).
  Rationale: uri if the instances have an IRI; generated key if they are anonymous (blank nodes).
  Other options: `generated_key` (Generated key), `property` (Choose a business property).

**Neo4j** - Recommendation `uri_key` - Key = uri: Technical identifier (IRI).
  Rationale: uri if the instances have an IRI; generated key if they are anonymous (blank nodes).
  Other options: `generated_key` (Generated key), `property` (Choose a business property).

**What is lost**: No business key: identity is technical (IRI) or generated, and there is no deduplication by values.

**Compensation**: Human decision (no automatic compensation)

### K04 — Anonymous individual {#k04-individu-anonyme}

- **Construct**: Anonymous individual (blank node, SS §5.6.2)
- **Detection**: Typed blank node as an object value.
- **Severity**: review (to decide)
- **Example in trap**: `am:veh_001`

**OWL example**

```turtle
ex:Vehicle a owl:Class . ex:MileageReading a owl:Class .
ex:veh_001 a ex:Vehicle ;
    ex:hasReading [ a ex:MileageReading ; ex:km 42000 ] .   # blank node
ex:hasReading a owl:ObjectProperty . ex:km a owl:DatatypeProperty .
```

**Curiosity** - Recommendation `generated_key` - Generated key: hash(owner + property + values) or skolem IRI.
  Rationale: A blank node has no IRI: no key can be derived (not K01).
  Other options: `ignore` (Ignore).

**Neo4j** - Recommendation `generated_key` - Generated key: hash(owner + property + values) or skolem IRI.
  Rationale: A blank node has no IRI: no key can be derived (not K01).
  Other options: `ignore` (Ignore).

**What is lost**: A blank node has no IRI. The key is derived (hash or skolem IRI) and changes when the values change.

**Compensation**: Materialization (derived property or edge recomputed after ingestion)

### K05 — Composite key with an object property {#k05-cle-composite-avec-propriete-objet}

- **Construct**: owl:hasKey including an object property
- **Detection**: HasKey axiom over at least one object property.
- **Severity**: review (to decide)
- **Example in trap**: `am:PartReference`

**OWL example**

```turtle
ex:PartReference a owl:Class . ex:Part a owl:Class .
ex:partOf a owl:ObjectProperty, owl:FunctionalProperty ; rdfs:domain ex:PartReference ; rdfs:range ex:Part .
ex:refCode a owl:DatatypeProperty ; rdfs:domain ex:PartReference ; rdfs:range xsd:string .
ex:PartReference owl:hasKey ( ex:partOf ex:refCode ) .
```

**Curiosity** - Recommendation `key_concat` - Concatenation with the target's key: Key = value | key of the target node.
  Rationale: An LPG key only carries properties of the node itself.
  Other options: `uri_key` (Key = uri).

**Neo4j** - Recommendation `materialize_key` - Copy the target's key + NODE KEY: A `<target>Key` property copied at ingestion, then a composite NODE KEY.
  Rationale: An LPG key only carries properties of the node itself.
  Other options: `uri_key` (Key = uri).

**What is lost**: An LPG key only carries properties of the node itself. The "relationship" part of the key is copied (concatenation / `<target>Key` property) and has to be kept up to date.

**Compensation**: Materialization (derived property or edge recomputed after ingestion)


## Data properties (D) {#proprietes-de-donnees-d}

### D01 — Data property *(Must, iteration 1)* {#d01-propriete-de-donnees-must-it-1}

- **Construct**: Data property with a single named domain
- **Detection**: A single named rdfs:domain.
- **Severity**: auto (applied directly)
- **Example in trap**: `am:vin`

**OWL example**

```turtle
ex:Vehicle a owl:Class .
ex:vin a owl:DatatypeProperty, owl:FunctionalProperty ;
    rdfs:domain ex:Vehicle ; rdfs:range xsd:string .
```

**Curiosity** - Recommendation `property` - Property: A typed property on the node.
  Rationale: Direct mapping (the RDFS domain infers; here it becomes a schema contract, closed world).

**Neo4j** - Recommendation `property` - Property: A typed property on the node.
  Rationale: Direct mapping (the RDFS domain infers; here it becomes a schema contract, closed world).

**What is lost**: The RDFS domain infers the type. It becomes a schema contract (closed world).

**Compensation**: none

### D02 — Property without a domain *(Must, iteration 1)* {#d02-propriete-sans-domaine-must-it-1}

- **Construct**: Data property without a domain
- **Detection**: No rdfs:domain.
- **Severity**: review (to decide)
- **Example in trap**: `am:mileageKm`

**OWL example**

```turtle
ex:mileageKm a owl:DatatypeProperty, owl:FunctionalProperty ; rdfs:range xsd:integer .   # no domain
```

**Curiosity** - Recommendation `attach_to_users` - Attach to its users: Placed on the types that use it (restrictions, shapes, assertions); not placed if it is only used through its subproperties.
  Rationale: An LPG property belongs to a node type.
  Other options: `ignore` (Ignore).

**Neo4j** - Recommendation `attach_to_users` - Attach to its users: Placed on the types that use it (restrictions, shapes, assertions); not placed if it is only used through its subproperties.
  Rationale: An LPG property belongs to a node type.
  Other options: `ignore` (Ignore).

**What is lost**: An LPG property belongs to a node type. Without a domain, the attachment comes from usage (restrictions, shapes), and a property with no usage is not placed.

**Compensation**: Human decision (no automatic compensation)

### D03 — Union domain {#d03-domaine-en-union}

- **Construct**: Domain = owl:unionOf (explicit union)
- **Detection**: rdfs:domain [owl:unionOf (…)].
- **Severity**: review (to decide)
- **Example in trap**: `am:phoneNumber`

**OWL example**

```turtle
ex:Customer a owl:Class . ex:Garage a owl:Class .
ex:phoneNumber a owl:DatatypeProperty ; rdfs:range xsd:string ;
    rdfs:domain [ a owl:Class ; owl:unionOf ( ex:Customer ex:Garage ) ] .
```

**Curiosity** - Recommendation `duplicate_per_type` - Duplicate on each type: The same name on each member of the union.
  Rationale: Only an explicit union allows duplication (≠ several rdfs:domain, D12).

**Neo4j** - Recommendation `duplicate_per_type` - Duplicate on each type: The same name on each member of the union.
  Rationale: Only an explicit union allows duplication (≠ several rdfs:domain, D12).

**What is lost**: The property is duplicated on each member. That it is "the same property" is only documented.

**Compensation**: none

### D04 — Non-functional property *(Must, iteration 1)* {#d04-propriete-non-fonctionnelle-must-it-1}

- **Construct**: Non-functional data property
- **Detection**: No FunctionalProperty, no max/exactly 1, no sh:maxCount 1.
- **Severity**: review (to decide)
- **Example in trap**: `am:commercialName`

**OWL example**

```turtle
ex:Vehicle a owl:Class .
ex:tag a owl:DatatypeProperty ; rdfs:domain ex:Vehicle ; rdfs:range xsd:string .   # non-functional
```

**Curiosity** - Recommendation `scalar` - Scalar: A single value; multiple values are lost at ingestion.
  Rationale: OWA: the absence of FunctionalProperty does not prove multi-valuedness: a list if several values are observed, a scalar otherwise.
  Other options: `list_property` (List).

**Neo4j** - Recommendation `scalar` - Scalar: A single value; multiple values are lost at ingestion.
  Rationale: OWA: the absence of FunctionalProperty does not prove multi-valuedness: a list if several values are observed, a scalar otherwise.
  Other options: `list_property` (List).

**What is lost**: A choice between a list (no loss) and a scalar (multiple values lost at ingestion). Under OWA, the absence of `Functional` does not prove multi-valuedness.

**Compensation**: none

### D05 — Lossy datatype *(Must, iteration 1)* {#d05-type-de-donnees-avec-perte-must-it-1}

- **Construct**: Lossy xsd datatype
- **Detection**: decimal, hexBinary/base64Binary, dateTimeStamp, owl:real/rational, types outside the OWL 2 datatype map (gYear, date, duration…; also W01).
- **Severity**: review (to decide)
- **Example in trap**: `am:mileageKm`

**OWL example**

```turtle
ex:Part a owl:Class .
ex:price a owl:DatatypeProperty, owl:FunctionalProperty ; rdfs:domain ex:Part ; rdfs:range xsd:decimal .
```

**Curiosity** - Recommendation `native_type` - Closest native type: decimal → float (precision), dateTimeStamp → timezone-aware datetime, gYear → integer…
  Rationale: No native decimal or binary in an LPG.
  Other options: `string_lexical` (Lexical form as text).

**Neo4j** - Recommendation `native_type` - Closest native type: decimal → float (precision), dateTimeStamp → timezone-aware datetime, gYear → integer…
  Rationale: No native decimal or binary in an LPG.
  Other options: `string_lexical` (Lexical form as text).

**What is lost**: **Neo4j**: no native exact decimal. `xsd:decimal` becomes a float (precision lost, D05 finding kept) or a string (exact but not numerically comparable). **Curiosity**: since L13 (D-L13-01), `xsd:decimal` becomes the C# `decimal` type without loss (28-29 significant digits) and no D05 finding is raised for this type. The catalog entry above predates this change and describes the float fallback.

**Compensation**: Validation (check at ingestion or detection query)

### D06 — Multilingual values *(Must, iteration 1)* {#d06-valeurs-multilingues-must-it-1}

- **Construct**: Multilingual values (rdf:PlainLiteral, @lang)
- **Detection**: Range rdf:PlainLiteral / rdf:langString (non-conformant, W01) or language-tagged literals observed.
- **Severity**: review (to decide)
- **Example in trap**: `am:operationDescription`

**OWL example**

```turtle
ex:Operation a owl:Class .
ex:description a owl:DatatypeProperty ; rdfs:domain ex:Operation ; rdfs:range rdf:PlainLiteral .
```

**Curiosity** - Recommendation `per_language_property` - One property per language: label_fr, label_en; languages outside the list are lost.
  Rationale: No language-tagged literal in an LPG.
  Other options: `string_property` (Text without a language).

**Neo4j** - Recommendation `per_language_property` - One property per language: label_fr, label_en; languages outside the list are lost.
  Rationale: No language-tagged literal in an LPG.
  Other options: `string_property` (Text without a language).

**What is lost**: The language tag (`@fr`) is lost, or split into one property per language (`description_fr`). Languages outside the list are lost.

**Compensation**: none

### D07 — Functional property *(Must, iteration 1)* {#d07-propriete-fonctionnelle-must-it-1}

- **Construct**: owl:FunctionalProperty (data)
- **Detection**: Functional data property.
- **Severity**: auto (applied directly)
- **Example in trap**: `am:vin`

**OWL example**

```turtle
ex:Vehicle a owl:Class .
ex:vin a owl:DatatypeProperty, owl:FunctionalProperty ; rdfs:domain ex:Vehicle ; rdfs:range xsd:string .
```

**Curiosity** - Recommendation `scalar` - Scalar: Single value (+ a type constraint if editing allows it).
  Rationale: Direct mapping.

**Neo4j** - Recommendation `scalar` - Scalar: Single value (+ a type constraint if editing allows it).
  Rationale: Direct mapping.

**What is lost**: Nothing: single value.

**Compensation**: none

### D08 — Literal enumeration {#d08-enumeration-de-litteraux}

- **Construct**: DataOneOf (literal enumeration)
- **Detection**: Range owl:oneOf of literals.
- **Severity**: review (to decide)
- **Example in trap**: `am:emissionStandard`

**OWL example**

```turtle
ex:Vehicle a owl:Class .
ex:emissionStandard a owl:DatatypeProperty ; rdfs:domain ex:Vehicle ;
    rdfs:range [ a rdfs:Datatype ; owl:oneOf ( "Euro5" "Euro6" ) ] .
```

**Curiosity** - Recommendation `enum_property` - Enumerated property + validation: Text + value check (no native enumeration constraint).
  Rationale: A small frozen set of literals.
  Other options: `reference_nodes` (Reference nodes).

**Neo4j** - Recommendation `enum_property` - Enumerated property + validation: Text + value check (no native enumeration constraint).
  Rationale: A small frozen set of literals.
  Other options: `reference_nodes` (Reference nodes).

**What is lost**: No native enumeration constraint. Values are checked by validation or become reference nodes.

**Compensation**: Validation (check at ingestion or detection query)

### D09 — Datatype with facets {#d09-datatype-a-facettes}

- **Construct**: Defined datatype / facets
- **Detection**: rdfs:Datatype defined by owl:withRestrictions (min/max, pattern, length).
- **Severity**: review (to decide)
- **Example in trap**: `am:ModelYear`

**OWL example**

```turtle
ex:VehicleModel a owl:Class .
ex:ModelYear a rdfs:Datatype ;
    owl:equivalentClass [ a rdfs:Datatype ; owl:onDatatype xsd:integer ;
        owl:withRestrictions ( [ xsd:minInclusive "1950"^^xsd:integer ] [ xsd:maxInclusive "2100"^^xsd:integer ] ) ] .
ex:modelYear a owl:DatatypeProperty, owl:FunctionalProperty ; rdfs:domain ex:VehicleModel ; rdfs:range ex:ModelYear .
```

**Curiosity** - Recommendation `validation` - Base type + validation: The native base type is used; bounds and patterns become validations.
  Rationale: No native facet in an LPG.
  Other options: `native_type` (Base type only).

**Neo4j** - Recommendation `validation` - Base type + validation: The native base type is used; bounds and patterns become validations.
  Rationale: No native facet in an LPG.
  Other options: `native_type` (Base type only).

**What is lost**: Bounds and patterns have no native equivalent. They become validations (or are lost with `native_type`).

**Compensation**: Validation (check at ingestion or detection query)

### D10 — Untyped literal {#d10-litteral-non-type}

- **Construct**: Range rdfs:Literal or missing
- **Detection**: Unconstrained range.
- **Severity**: review (to decide)
- **Example in trap**: `am:legacyCode`

**OWL example**

```turtle
ex:Part a owl:Class .
ex:legacyCode a owl:DatatypeProperty ; rdfs:domain ex:Part ; rdfs:range rdfs:Literal .
```

**Curiosity** - Recommendation `string_property` - Text: Original typing lost.
  Rationale: Unknown type: text by default.

**Neo4j** - Recommendation `string_property` - Text: Original typing lost.
  Rationale: Unknown type: text by default.

**What is lost**: The original type does not exist: text by default.

**Compensation**: none

### D11 — Data subproperty {#d11-sous-propriete-de-donnees}

- **Construct**: rdfs:subPropertyOf between data properties
- **Detection**: Data subproperty.
- **Severity**: lost (certain loss without compensation)
- **Example in trap**: `am:readingMileageKm`

**OWL example**

```turtle
ex:Vehicle a owl:Class . ex:MileageReading a owl:Class .
ex:mileageKm a owl:DatatypeProperty ; rdfs:domain ex:Vehicle ; rdfs:range xsd:integer .
ex:readingMileageKm a owl:DatatypeProperty ; rdfs:subPropertyOf ex:mileageKm ;
    rdfs:domain ex:MileageReading ; rdfs:range xsd:integer .
```

**Curiosity** - Recommendation `most_specific_type` - Most specific property: The superproperty is not stored: a query on the parent must list the subproperties.
  Rationale: No property hierarchy in an LPG.
  Other options: `materialize_closure` (Duplicate into the superproperty).

**Neo4j** - Recommendation `most_specific_type` - Most specific property: The superproperty is not stored: a query on the parent must list the subproperties.
  Rationale: No property hierarchy in an LPG.
  Other options: `materialize_closure` (Duplicate into the superproperty).

**What is lost**: The property hierarchy disappears. Querying the superproperty means listing the subproperties (or writing twice).

**Compensation**: Materialization (derived property or edge recomputed after ingestion)

### D12 — Domain / range intersection {#d12-intersection-de-domaines-portees}

- **Construct**: Several rdfs:domain / rdfs:range (data) = intersection
- **Detection**: At least two named domains or two ranges.
- **Severity**: review (to decide)
- **Example in trap**: `am:warrantyDurationMonths`

**OWL example**

```turtle
ex:Warranty a owl:Class . ex:Contract a owl:Class .
ex:warrantyMonths a owl:DatatypeProperty, owl:FunctionalProperty ; rdfs:range xsd:integer ;
    rdfs:domain ex:Warranty ; rdfs:domain ex:Contract .   # two domains = INTERSECTION
```

**Curiosity** - Recommendation `native_type` - Native type of the intersection: The most restrictive type + bounds validation.
  Rationale: Several domain/range axioms accumulate (RSEM rdfs2/rdfs3).
  Other options: `intersection_domain` (Domain = intersection), `duplicate_per_type` (Treat as a union).

**Neo4j** - Recommendation `native_type` - Native type of the intersection: The most restrictive type + bounds validation.
  Rationale: Several domain/range axioms accumulate (RSEM rdfs2/rdfs3).
  Other options: `intersection_domain` (Domain = intersection), `duplicate_per_type` (Treat as a union).

**What is lost**: Reading trap: two `rdfs:domain` axioms mean "instance of BOTH classes" (rdfs2). Most of the time this is a modeling error (the author wanted a union).

**Compensation**: Validation (check at ingestion or detection query)

### D13 — Restriction on a data property {#d13-restriction-sur-propriete-de-donnees}

- **Construct**: Restriction on a data property
- **Detection**: some / only / cardinality / onDataRange.
- **Severity**: review (to decide)
- **Example in trap**: `am:RepairOrder`

**OWL example**

```turtle
ex:RepairOrder a owl:Class .
ex:RepairOrder rdfs:subClassOf [ a owl:Restriction ; owl:onProperty ex:openedAt ; owl:cardinality "1"^^xsd:nonNegativeInteger ] .
ex:openedAt a owl:DatatypeProperty, owl:FunctionalProperty ; rdfs:domain ex:RepairOrder ; rdfs:range xsd:dateTime .
```

**Curiosity** - Recommendation `validation` - Validation: exactly 1 / min 1 → mandatory property + check.
  Rationale: OWL restrictions infer; in an LPG they become checks (closed world).
  Other options: `ignore` (Ignore).

**Neo4j** - Recommendation `validation` - Validation: exactly 1 / min 1 → mandatory property + check.
  Rationale: OWL restrictions infer; in an LPG they become checks (closed world).
  Other options: `ignore` (Ignore).

**What is lost**: In OWL the axiom infers. In an LPG it can only check: mandatory property plus validation, and the database blocks nothing.

**Compensation**: Validation (check at ingestion or detection query)


## Object properties (O) {#proprietes-objet-o}

### O01 — Object property → relationship *(Must, iteration 1)* {#o01-propriete-objet-relation-must-it-1}

- **Construct**: Object property with a single named domain and range
- **Detection**: One named domain and one named range.
- **Severity**: auto (applied directly)
- **Example in trap**: `am:worksAt`

**OWL example**

```turtle
ex:Technician a owl:Class . ex:Garage a owl:Class .
ex:worksAt a owl:ObjectProperty ; rdfs:domain ex:Technician ; rdfs:range ex:Garage .
```

**Curiosity** - Recommendation `edge_pair` - Forward / backward edge pair: Forward + backward constants, Link(a, b, forward, backward).
  Rationale: Direct mapping.

**Neo4j** - Recommendation `relationship` - Relationship type: UPPER_SNAKE, one direction stored.
  Rationale: Direct mapping.

**What is lost**: Nothing: direct mapping.

**Compensation**: none

### O02 — Missing domain / range *(Must, iteration 1)* {#o02-domaine-portee-manquants-must-it-1}

- **Construct**: Object property without a domain or without a range
- **Detection**: Missing domain or range.
- **Severity**: review (to decide)
- **Example in trap**: `am:interchangeableWith`

**OWL example**

```turtle
ex:interchangeableWith a owl:ObjectProperty .   # no domain, no range
```

**Curiosity** - Recommendation `edge_pair` - Resolve, then edge pair: Endpoints inferred from restrictions, shapes, assertions and the inverse.
  Rationale: The connector must know which types to link.
  Other options: `ignore` (Ignore).

**Neo4j** - Recommendation `relationship` - Resolve, then relationship: Endpoints inferred from restrictions, shapes, assertions and the inverse.
  Rationale: The connector must know which types to link.
  Other options: `ignore` (Ignore).

**What is lost**: The endpoints are deduced from usage. Without usage, the relationship is not transposed (the connector would not know which types to link).

**Compensation**: Human decision (no automatic compensation)

### O03 — Union domain / range *(Must, iteration 1)* {#o03-domaine-portee-en-union-must-it-1}

- **Construct**: Domain / range = owl:unionOf
- **Detection**: rdfs:domain or rdfs:range [owl:unionOf (…)].
- **Severity**: review (to decide)
- **Example in trap**: `am:hasOwner`

**OWL example**

```turtle
ex:Vehicle a owl:Class . ex:Person a owl:Class . ex:Company a owl:Class .
ex:hasOwner a owl:ObjectProperty ; rdfs:domain ex:Vehicle ;
    rdfs:range [ a owl:Class ; owl:unionOf ( ex:Person ex:Company ) ] .
```

**Curiosity** - Recommendation `edge_pair` - One edge per type pair: The same edge name for each pair.
  Rationale: Explicit unions only (≠ several rdfs:range: O21).

**Neo4j** - Recommendation `relationship` - One type, several label pairs: Validation of the allowed pairs.
  Rationale: Explicit unions only (≠ several rdfs:range: O21).

**What is lost**: The disjunctive range becomes several endpoint pairs (Curiosity) or a validation of the allowed pairs (Neo4j).

**Compensation**: Validation (check at ingestion or detection query)

### O04 — Inverse properties *(Must, iteration 1)* {#o04-proprietes-inverses-must-it-1}

- **Construct**: owl:inverseOf
- **Detection**: Pair of inverse properties.
- **Severity**: auto (applied directly)
- **Example in trap**: `am:hasPart`

**OWL example**

```turtle
ex:hasPart a owl:ObjectProperty ; owl:inverseOf ex:isPartOf .
ex:isPartOf a owl:ObjectProperty .
```

**Curiosity** - Recommendation `edge_pair` - Forward / backward pair: Curiosity: the backward link is free and native. Neo4j: both directions are stored (double write).
  Rationale: One fact, two names.

**Neo4j** - Recommendation `single_direction` - Only one direction stored: The other direction is traversed; the inverse name is documented.
  Rationale: One fact, two names.
  Other options: `edge_pair` (Forward / backward pair).

**What is lost**: Curiosity: nothing (the edge has a backward link). Neo4j: one stored direction is recommended and the other is traversed, with a double write if you choose to store both.

**Compensation**: none

### O05 — Symmetric property *(Must, iteration 1)* {#o05-propriete-symetrique-must-it-1}

- **Construct**: owl:SymmetricProperty
- **Detection**: Symmetric property.
- **Severity**: review (to decide)
- **Example in trap**: `am:interchangeableWith`

**OWL example**

```turtle
ex:Part a owl:Class .
ex:interchangeableWith a owl:ObjectProperty, owl:SymmetricProperty ; rdfs:domain ex:Part ; rdfs:range ex:Part .
```

**Curiosity** - Recommendation `self_reverse` - Edge = its own backward link: The same constant in both directions.
  Rationale: Avoids two facts for one symmetric relation.
  Other options: `edge_pair` (Store both directions).

**Neo4j** - Recommendation `undirected_query` - One direction stored, undirected queries: MATCH (a)-[:T]-(b); the stored direction is arbitrary.
  Rationale: Avoids two facts for one symmetric relation.
  Other options: `edge_pair` (Store both directions).

**What is lost**: The stored direction is arbitrary (Neo4j). Symmetry is no longer inferred and is read with an undirected query.

**Compensation**: none

### O06 — Transitive property *(Must, iteration 1)* {#o06-propriete-transitive-must-it-1}

- **Construct**: owl:TransitiveProperty
- **Detection**: Transitive property.
- **Severity**: lost (certain loss without compensation)
- **Example in trap**: `am:isComponentOf`

**OWL example**

```turtle
ex:Part a owl:Class .
ex:isComponentOf a owl:ObjectProperty, owl:TransitiveProperty ; rdfs:domain ex:Part ; rdfs:range ex:Part .
```

**Curiosity** - Recommendation `materialize_closure` - Materialize the closure: A derived `<name>Transitive` edge recomputed after ingestion.
  Rationale: No documented variable-length path: the closure is materialized.
  Other options: `ignore` (Ignore).

**Neo4j** - Recommendation `var_length_query` - Variable-length query: -[:T*1..]->: full compensation at read time, no constraint.
  Rationale: Variable-length paths are native in Cypher (full compensation at read time only).
  Other options: `materialize_closure` (Materialize the closure), `ignore` (Ignore).

**What is lost**: The transitive closure is no longer inferred. Curiosity needs a derived edge recomputed after ingestion; Neo4j uses a variable-length query, with no storage.

**Compensation**: Materialization (derived property or edge recomputed after ingestion)

### O07 — Object subproperty *(Must, iteration 1)* {#o07-sous-propriete-objet-must-it-1}

- **Construct**: rdfs:subPropertyOf (object)
- **Detection**: Object subproperty (excluding topObjectProperty).
- **Severity**: lost (certain loss without compensation)
- **Example in trap**: `am:hasEngine`

**OWL example**

```turtle
ex:Vehicle a owl:Class . ex:Part a owl:Class . ex:Engine a owl:Class .
ex:hasComponent a owl:ObjectProperty ; rdfs:domain ex:Vehicle ; rdfs:range ex:Part .
ex:hasEngine a owl:ObjectProperty ; rdfs:subPropertyOf ex:hasComponent ; rdfs:domain ex:Vehicle ; rdfs:range ex:Engine .
```

**Curiosity** - Recommendation `most_specific_type` - Most specific type: Only the subrelationship is stored; a parent query = a union of types.
  Rationale: No relationship-type hierarchy in an LPG.
  Other options: `materialize_closure` (Also materialize the parent).

**Neo4j** - Recommendation `most_specific_type` - Most specific type: Only the subrelationship is stored; a parent query = a union of types.
  Rationale: No relationship-type hierarchy in an LPG.
  Other options: `materialize_closure` (Also materialize the parent).

**What is lost**: Only the subrelationship is stored. Querying the parent means taking the union of the subrelationships (or writing twice).

**Compensation**: Materialization (derived property or edge recomputed after ingestion)

### O08 — Property chain {#o08-chaine-de-proprietes}

- **Construct**: owl:propertyChainAxiom
- **Detection**: Property defined by a chain.
- **Severity**: lost (certain loss without compensation)
- **Example in trap**: `am:vehicleBrand`

**OWL example**

```turtle
ex:VehicleModel a owl:Class . ex:Brand a owl:Class . ex:Vehicle a owl:Class .
ex:madeBy a owl:ObjectProperty ; rdfs:domain ex:VehicleModel ; rdfs:range ex:Brand .
ex:ofModel a owl:ObjectProperty ; rdfs:domain ex:Vehicle ; rdfs:range ex:VehicleModel .
ex:vehicleBrand a owl:ObjectProperty ; owl:propertyChainAxiom ( ex:ofModel ex:madeBy ) .
```

**Curiosity** - Recommendation `materialize_closure` - Materialize the shortcut: A derived edge recomputed after ingestion.
  Rationale: No inference on the LPG side.

**Neo4j** - Recommendation `path_query` - Path query: Not stored; computed at read time.
  Rationale: No inference on the LPG side.
  Other options: `materialize_closure` (Materialize the shortcut).

**What is lost**: The inclusion `ofModel ∘ madeBy ⊑ vehicleBrand` is no longer inferred. The edge is materialized after ingestion (Curiosity) or computed at read time (Neo4j).

**Compensation**: Materialization (derived property or edge recomputed after ingestion)

### O09 — Relationship cardinality ≤ 1 (max / exactly / functional) *(Must, iteration 1)* {#o09-cardinalite-1-d-une-relation-max-exactly-fonctionnelle-must-it-1}

- **Construct**: Functional / max 1 / exactly 1 (object)
- **Detection**: FunctionalProperty or a max/exactly ≤ 1 restriction.
- **Severity**: review (to decide)
- **Example in trap**: `am:ofModel`

**OWL example**

```turtle
ex:Vehicle a owl:Class . ex:VehicleModel a owl:Class .
ex:ofModel a owl:ObjectProperty, owl:FunctionalProperty ; rdfs:domain ex:Vehicle ; rdfs:range ex:VehicleModel .
```

**Curiosity** - Recommendation `validation` - Application-level validation: The constraint becomes a check run at ingestion (connector) or a detection query; nothing is blocked natively by the database.
  Rationale: No relationship-cardinality constraint in an LPG.
  Other options: `ignore` (Ignore).

**Neo4j** - Recommendation `validation` - Application-level validation: The constraint becomes a check run at ingestion (connector) or a detection query; nothing is blocked natively by the database.
  Rationale: No relationship-cardinality constraint in an LPG.
  Other options: `ignore` (Ignore).

**What is lost**: An LPG has no relationship cardinality. The check "at most one outgoing relationship" is done in the application.

**Compensation**: Validation (check at ingestion or detection query)

### O10 — Relationship existence *(Must, iteration 1)* {#o10-existence-d-une-relation-must-it-1}

- **Construct**: some / min n (object, unqualified)
- **Detection**: Existence restriction.
- **Severity**: review (to decide)
- **Example in trap**: `am:RepairOrder`

**OWL example**

```turtle
ex:RepairOrder a owl:Class . ex:Technician a owl:Class .
ex:RepairOrder rdfs:subClassOf [ a owl:Restriction ; owl:onProperty ex:performedBy ; owl:someValuesFrom ex:Technician ] .
ex:performedBy a owl:ObjectProperty .
```

**Curiosity** - Recommendation `validation` - Application-level validation: The constraint becomes a check run at ingestion (connector) or a detection query; nothing is blocked natively by the database.
  Rationale: OWA: some does not oblige us to know the value; in an LPG it is a completeness check.
  Other options: `ignore` (Ignore).

**Neo4j** - Recommendation `validation` - Application-level validation: The constraint becomes a check run at ingestion (connector) or a detection query; nothing is blocked natively by the database.
  Rationale: OWA: some does not oblige us to know the value; in an LPG it is a completeness check.
  Other options: `ignore` (Ignore).

**What is lost**: In OWL (OWA), `some` does not oblige us to know the value. In an LPG it is a completeness check (mandatory relationship).

**Compensation**: Validation (check at ingestion or detection query)

### O11 — Universal restriction {#o11-restriction-universelle}

- **Construct**: only (allValuesFrom)
- **Detection**: Universal restriction.
- **Severity**: lost (certain loss without compensation)
- **Example in trap**: `am:RepairOrder`

**OWL example**

```turtle
ex:RepairOrder a owl:Class . ex:Part a owl:Class .
ex:RepairOrder rdfs:subClassOf [ a owl:Restriction ; owl:onProperty ex:uses ; owl:allValuesFrom ex:Part ] .
ex:uses a owl:ObjectProperty .
```

**Curiosity** - Recommendation `validation` - Target type validation: A check that the target has the right type.
  Rationale: only infers the target's type (OWA); ≠ sh:class, which checks it.
  Other options: `ignore` (Ignore).

**Neo4j** - Recommendation `validation` - Target type validation: A check that the target has the right type.
  Rationale: only infers the target's type (OWA); ≠ sh:class, which checks it.
  Other options: `ignore` (Ignore).

**What is lost**: In OWL, `only` infers the type of the target. In an LPG only a check of the target's type remains (unlike sh:class, which verifies it).

**Compensation**: Validation (check at ingestion or detection query)

### O12 — Fixed value {#o12-valeur-imposee}

- **Construct**: hasValue
- **Detection**: Value restriction.
- **Severity**: review (to decide)
- **Example in trap**: `am:ElectricVehicle`

**OWL example**

```turtle
ex:ElectricVehicle a owl:Class .
ex:ElectricVehicle rdfs:subClassOf [ a owl:Restriction ; owl:onProperty ex:fuelType ; owl:hasValue ex:Electricity ] .
ex:fuelType a owl:ObjectProperty . ex:Electricity a owl:NamedIndividual .
```

**Curiosity** - Recommendation `validation` - Application-level validation: The constraint becomes a check run at ingestion (connector) or a detection query; nothing is blocked natively by the database.
  Rationale: No default value in an LPG schema.
  Other options: `materialize_at_ingest` (Set the value at ingestion).

**Neo4j** - Recommendation `validation` - Application-level validation: The constraint becomes a check run at ingestion (connector) or a detection query; nothing is blocked natively by the database.
  Rationale: No default value in an LPG schema.
  Other options: `materialize_at_ingest` (Set the value at ingestion).

**What is lost**: An LPG schema has no default value: use a validation, or let the connector create the relationship.

**Compensation**: Validation (check at ingestion or detection query)

### O13 — Property characteristics {#o13-caracteristiques-de-propriete}

- **Construct**: Reflexive / irreflexive / asymmetric
- **Detection**: Property characteristics.
- **Severity**: lost (certain loss without compensation)
- **Example in trap**: `am:interchangeableWith`

**OWL example**

```turtle
ex:interchangeableWith a owl:ObjectProperty, owl:IrreflexiveProperty, owl:AsymmetricProperty .
```

**Curiosity** - Recommendation `validation` - Application-level validation: The constraint becomes a check run at ingestion (connector) or a detection query; nothing is blocked natively by the database.
  Rationale: No native constraint; global reflexivity is often an error.
  Other options: `ignore` (Ignore).

**Neo4j** - Recommendation `validation` - Application-level validation: The constraint becomes a check run at ingestion (connector) or a detection query; nothing is blocked natively by the database.
  Rationale: No native constraint; global reflexivity is often an error.
  Other options: `ignore` (Ignore).

**What is lost**: No native constraint: use an application-level check ("no loop"). Reflexivity alone is never materialized, since that would add one loop per node.

**Compensation**: Validation (check at ingestion or detection query)

### O14 — Anonymous inverse property {#o14-propriete-inverse-anonyme}

- **Construct**: Anonymous ObjectInverseOf
- **Detection**: [owl:inverseOf :p] in a restriction or a chain.
- **Severity**: review (to decide)
- **Example in trap**: `am:Garage`

**OWL example**

```turtle
ex:Garage a owl:Class . ex:Technician a owl:Class .
ex:Garage rdfs:subClassOf [ a owl:Restriction ;
    owl:onProperty [ owl:inverseOf ex:worksAt ] ; owl:someValuesFrom ex:Technician ] .
ex:worksAt a owl:ObjectProperty .
```

**Curiosity** - Recommendation `reverse_traversal` - Reverse traversal: Read through the backward direction of the relationship.
  Rationale: No anonymous inverse in an LPG, but every relationship can be traversed in both directions.
  Other options: `resolve_named_inverse` (Named inverse).

**Neo4j** - Recommendation `reverse_traversal` - Reverse traversal: Read through the backward direction of the relationship.
  Rationale: No anonymous inverse in an LPG, but every relationship can be traversed in both directions.
  Other options: `resolve_named_inverse` (Named inverse).

**What is lost**: There is no anonymous inverse. The restriction is read through the backward direction of the relationship (or through the named inverse if there is one).

**Compensation**: Validation (check at ingestion or detection query)

### O15 — Inverse-functional property {#o15-propriete-inverse-fonctionnelle}

- **Construct**: owl:InverseFunctionalProperty
- **Detection**: Inverse-functional property.
- **Severity**: review (to decide)
- **Example in trap**: `am:hasRepairOrder`

**OWL example**

```turtle
ex:Vehicle a owl:Class . ex:RepairOrder a owl:Class .
ex:hasRepairOrder a owl:ObjectProperty, owl:InverseFunctionalProperty ; rdfs:domain ex:Vehicle ; rdfs:range ex:RepairOrder .
```

**Curiosity** - Recommendation `validation` - Application-level validation: The constraint becomes a check run at ingestion (connector) or a detection query; nothing is blocked natively by the database.
  Rationale: At most one incoming relationship per target: application-level check.
  Other options: `ignore` (Ignore).

**Neo4j** - Recommendation `validation` - Application-level validation: The constraint becomes a check run at ingestion (connector) or a detection query; nothing is blocked natively by the database.
  Rationale: At most one incoming relationship per target: application-level check.
  Other options: `ignore` (Ignore).

**What is lost**: "At most one incoming relationship per target" cannot be constrained: use an application-level check.

**Compensation**: Validation (check at ingestion or detection query)

### O16 — Qualified cardinality {#o16-cardinalite-qualifiee}

- **Construct**: Qualified cardinality (onClass)
- **Detection**: min/max/exactly with owl:onClass, simple property.
- **Severity**: review (to decide)
- **Example in trap**: `am:Car`

**OWL example**

```turtle
ex:Car a owl:Class . ex:Wheel a owl:Class .
ex:Car rdfs:subClassOf [ a owl:Restriction ; owl:onProperty ex:hasWheel ;
    owl:qualifiedCardinality "4"^^xsd:nonNegativeInteger ; owl:onClass ex:Wheel ] .
ex:hasWheel a owl:ObjectProperty .
```

**Curiosity** - Recommendation `validation` - Application-level validation: The constraint becomes a check run at ingestion (connector) or a detection query; nothing is blocked natively by the database.
  Rationale: Validation filtered by target type.
  Other options: `ignore` (Ignore).

**Neo4j** - Recommendation `validation` - Application-level validation: The constraint becomes a check run at ingestion (connector) or a detection query; nothing is blocked natively by the database.
  Rationale: Validation filtered by target type.
  Other options: `ignore` (Ignore).

**What is lost**: Qualified cardinality: a check filtered by target type. Nothing is blocked natively.

**Compensation**: Validation (check at ingestion or detection query)

### O17 — hasSelf restriction {#o17-restriction-hasself}

- **Construct**: owl:hasSelf
- **Detection**: ObjectHasSelf restriction.
- **Severity**: lost (certain loss without compensation)
- **Example in trap**: `am:SelfEmployedTechnician`

**OWL example**

```turtle
ex:SelfEmployedTechnician a owl:Class .
ex:SelfEmployedTechnician rdfs:subClassOf [ a owl:Restriction ; owl:onProperty ex:employs ; owl:hasSelf true ] .
ex:employs a owl:ObjectProperty .
```

**Curiosity** - Recommendation `materialize_at_ingest` - Materialized boolean: A boolean computed at ingestion (loop detected).
  Rationale: A loop is not an LPG schema concept.
  Other options: `validation` (Application-level validation).

**Neo4j** - Recommendation `validation` - Application-level validation: The constraint becomes a check run at ingestion (connector) or a detection query; nothing is blocked natively by the database.
  Rationale: A loop is not an LPG schema concept.
  Other options: `materialize_at_ingest` (Materialized boolean).

**What is lost**: A loop is not an LPG schema concept: use a boolean computed at ingestion, or a validation.

**Compensation**: Materialization (derived property or edge recomputed after ingestion)

### O18 — Universal superproperty {#o18-super-propriete-universelle}

- **Construct**: owl:topObjectProperty / topDataProperty as superproperty
- **Detection**: subPropertyOf top.
- **Severity**: auto (applied directly)
- **Example in trap**: `am:relatedTo`

**OWL example**

```turtle
ex:relatedTo a owl:ObjectProperty ; rdfs:subPropertyOf owl:topObjectProperty .
```

**Curiosity** - Recommendation `ignore` - Ignore (documented): No effect in an LPG.
  Rationale: The universal property links everything to everything: nothing transposable.

**Neo4j** - Recommendation `ignore` - Ignore (documented): No effect in an LPG.
  Rationale: The universal property links everything to everything: nothing transposable.

**What is lost**: No effect: the universal property carries nothing transposable (recorded in the report).

**Compensation**: Documentation (transposition report)

### O19 — Equivalent properties {#o19-proprietes-equivalentes}

- **Construct**: owl:equivalentProperty
- **Detection**: Equivalent object properties.
- **Severity**: review (to decide)
- **Example in trap**: `am:ownedBy`

**OWL example**

```turtle
ex:ownedBy a owl:ObjectProperty ; owl:equivalentProperty ex:hasOwner .
```

**Curiosity** - Recommendation `merge_relationship_types` - Merge the relationship types: Canonical name + documented alias.
  Rationale: Same extension: lossless merge.
  Other options: `doc_only` (Keep separate).

**Neo4j** - Recommendation `merge_relationship_types` - Merge the relationship types: Canonical name + documented alias.
  Rationale: Same extension: lossless merge.
  Other options: `doc_only` (Keep separate).

**What is lost**: Lossless if merged (canonical name plus documented alias). With two relationships, they have to be kept in sync.

**Compensation**: Documentation (transposition report)

### O20 — Disjoint properties {#o20-proprietes-disjointes}

- **Construct**: owl:propertyDisjointWith / AllDisjointProperties
- **Detection**: Disjoint properties.
- **Severity**: lost (certain loss without compensation)
- **Example in trap**: `am:performedBy`

**OWL example**

```turtle
ex:performedBy a owl:ObjectProperty ; owl:propertyDisjointWith ex:validatedBy .
```

**Curiosity** - Recommendation `validation` - Application-level validation: The constraint becomes a check run at ingestion (connector) or a detection query; nothing is blocked natively by the database.
  Rationale: Two relationships cannot link the same pair: application-level check.
  Other options: `ignore` (Ignore).

**Neo4j** - Recommendation `validation` - Application-level validation: The constraint becomes a check run at ingestion (connector) or a detection query; nothing is blocked natively by the database.
  Rationale: Two relationships cannot link the same pair: application-level check.
  Other options: `ignore` (Ignore).

**What is lost**: Two relationships cannot link the same pair: application-level check only.

**Compensation**: Validation (check at ingestion or detection query)

### O21 — Domain / range intersection {#o21-intersection-de-domaines-portees}

- **Construct**: Several rdfs:domain / rdfs:range (object) = intersection
- **Detection**: At least two named domains or ranges.
- **Severity**: review (to decide)
- **Example in trap**: `am:reportsFaultCode`

**OWL example**

```turtle
ex:FaultCode a owl:Class . ex:Diagnostic a owl:Class . ex:Report a owl:Class .
ex:reportsFaultCode a owl:ObjectProperty ; rdfs:range ex:FaultCode ;
    rdfs:domain ex:Diagnostic ; rdfs:domain ex:Report .   # INTERSECTION
```

**Curiosity** - Recommendation `intersection_domain` - Domain = intersection: A relationship from each domain + a "belongs to all" validation (often a modeling error).
  Rationale: rdfs2/rdfs3: the subject is an instance of BOTH classes; to be decided.
  Other options: `most_specific_type` (Most specific class), `duplicate_per_type` (Treat as a union).

**Neo4j** - Recommendation `intersection_domain` - Domain = intersection: A relationship from each domain + a "belongs to all" validation (often a modeling error).
  Rationale: rdfs2/rdfs3: the subject is an instance of BOTH classes; to be decided.
  Other options: `most_specific_type` (Most specific class), `duplicate_per_type` (Treat as a union).

**What is lost**: Same trap as D12: the subject is an instance of both classes (rdfs2). It needs a decision, because it is often a modeling fault.

**Compensation**: Human decision (no automatic compensation)


## Reification (R) {#reification-r}

### R01 — Binary reification *(Must, iteration 1)* {#r01-reification-binaire-must-it-1}

- **Construct**: Binary reification class
- **Detection**: Exactly 2 functional object roles (or max/exactly 1) plus data properties, and the class is not the target of other relationships.
- **Severity**: review (to decide)
- **Example in trap**: `am:PartInstallation`

**OWL example**

```turtle
ex:Part a owl:Class . ex:Vehicle a owl:Class .
ex:PartInstallation a owl:Class .
ex:installedPart a owl:ObjectProperty, owl:FunctionalProperty ; rdfs:domain ex:PartInstallation ; rdfs:range ex:Part .
ex:installedOn   a owl:ObjectProperty, owl:FunctionalProperty ; rdfs:domain ex:PartInstallation ; rdfs:range ex:Vehicle .
ex:installedAt   a owl:DatatypeProperty, owl:FunctionalProperty ; rdfs:domain ex:PartInstallation ; rdfs:range xsd:date .
```

**Curiosity** - Recommendation `keep_node` - Keep a node: One more hop, extensible.
  Rationale: Curiosity edges do not carry properties: de-reifying would lose the attributes.

**Neo4j** - Recommendation `dereify_relationship` - Relationship carrying properties: No more intermediate node; the relationship carries the properties and cannot be the target of other relationships.
  Rationale: Neo4j: relationships carry properties, so binary reification is de-reified.
  Other options: `keep_node` (Keep a node).

**What is lost**: Neo4j: de-reifying removes the node, and the relationship can no longer be the target of other relationships. Curiosity: the edge carries no property, so the node stays.

**Compensation**: none

### R02 — N-ary relationship *(Must, iteration 1)* {#r02-relation-n-aire-must-it-1}

- **Construct**: N-ary relation (≥ 3 roles)
- **Detection**: At least 3 functional object roles.
- **Severity**: review (to decide)
- **Example in trap**: `am:WarrantyClaim`

**OWL example**

```turtle
ex:Vehicle a owl:Class . ex:Part a owl:Class . ex:Garage a owl:Class .
ex:WarrantyClaim a owl:Class .
ex:claimVehicle a owl:ObjectProperty, owl:FunctionalProperty ; rdfs:domain ex:WarrantyClaim ; rdfs:range ex:Vehicle .
ex:claimPart    a owl:ObjectProperty, owl:FunctionalProperty ; rdfs:domain ex:WarrantyClaim ; rdfs:range ex:Part .
ex:claimGarage  a owl:ObjectProperty, owl:FunctionalProperty ; rdfs:domain ex:WarrantyClaim ; rdfs:range ex:Garage .
```

**Curiosity** - Recommendation `keep_node` - Keep a node (W3C SWBP n-ary pattern): The only possible representation.
  Rationale: An LPG relationship links exactly two nodes.

**Neo4j** - Recommendation `keep_node` - Keep a node (W3C SWBP n-ary pattern): The only possible representation.
  Rationale: An LPG relationship links exactly two nodes.

**What is lost**: Nothing if the node is kept (the only way to represent a relation with 3 roles). An LPG edge links exactly two nodes.

**Compensation**: none


## Annotations (A) {#annotations-a}

### A01 — Annotations *(Must, iteration 1)* {#a01-annotations-must-it-1}

- **Construct**: Annotations (rdfs:comment, skos:*, dcterms:*)
- **Detection**: Entity carrying annotations beyond rdfs:label.
- **Severity**: auto (applied directly)
- **Example in trap**: `am:Vehicle`

**OWL example**

```turtle
ex:Vehicle a owl:Class ; rdfs:comment "Véhicule motorisé"@fr ; skos:definition "Moyen de transport" .
```

**Curiosity** - Recommendation `schema_metadata` - Schema metadata: Documentation comments in the generated code / schema.
  Rationale: Documentation kept with the schema.

**Neo4j** - Recommendation `schema_metadata` - Schema metadata: Documentation comments in the generated code / schema.
  Rationale: Documentation kept with the schema.

**What is lost**: The comment is kept as documentation of the generated schema. It does not exist as data.

**Compensation**: Documentation (transposition report)

### A02 — Axiom annotation {#a02-annotation-d-axiome}

- **Construct**: Axiom annotations (owl:Axiom)
- **Detection**: Annotated axiom reification.
- **Severity**: review (to decide)
- **Example in trap**: `am:Vehicle`

**OWL example**

```turtle
ex:Car a owl:Class . ex:Vehicle a owl:Class .
[ a owl:Axiom ; owl:annotatedSource ex:Car ; owl:annotatedProperty rdfs:subClassOf ;
  owl:annotatedTarget ex:Vehicle ; rdfs:comment "Source : norme X" ] .
```

**Curiosity** - Recommendation `report` - List in the report: Information kept in the transposition report only.
  Rationale: Axiom metadata has no schema equivalent.

**Neo4j** - Recommendation `report` - List in the report: Information kept in the transposition report only.
  Rationale: Axiom metadata has no schema equivalent.
  Other options: `provenance_property` (Provenance property).

**What is lost**: An axiom annotation has no schema equivalent. It is kept in the report (or as a Neo4j provenance property).

**Compensation**: Documentation (transposition report)

### A03 — Deprecated entity {#a03-entite-depreciee}

- **Construct**: owl:deprecated true
- **Detection**: Deprecated entity.
- **Severity**: auto (applied directly)
- **Example in trap**: `am:ServiceBooklet`

**OWL example**

```turtle
ex:ServiceBooklet a owl:Class ; owl:deprecated true .
```

**Curiosity** - Recommendation `exclude` - Exclude: Not generated.
  Rationale: A deprecated entity should not enter a new schema.
  Other options: `flag_deprecated` (Keep with a flag).

**Neo4j** - Recommendation `exclude` - Exclude: Not generated.
  Rationale: A deprecated entity should not enter a new schema.
  Other options: `flag_deprecated` (Keep with a flag).

**What is lost**: The deprecated entity is not generated (or is flagged). This is intentional.

**Compensation**: none


## meta {#meta}

### M01 — Ontology metadata {#m01-metadonnees-d-ontologie}

- **Construct**: Ontology header
- **Detection**: owl:Ontology (IRI, versionIRI, versionInfo, dcterms).
- **Severity**: auto (applied directly)
- **Example in trap**: `https://w3id.org/ontoforge/automaint`

**OWL example**

```turtle
<http://example.org/doc> a owl:Ontology ; owl:versionInfo "1.0" ; dcterms:title "Doc" .
```

**Curiosity** - Recommendation `schema_metadata` - Generated schema header: Name, version, original IRI.
  Rationale: Traceability.

**Neo4j** - Recommendation `schema_metadata` - Generated schema header: Name, version, original IRI.
  Rationale: Traceability.

**What is lost**: Nothing is lost: name, version and original IRI are carried over as metadata.

**Compensation**: Documentation (transposition report)

### M02 — Ontology import {#m02-import-d-ontologie}

- **Construct**: owl:imports
- **Detection**: Declared import.
- **Severity**: review (to decide)
- **Example in trap**: `https://w3id.org/ontoforge/automaint`

**OWL example**

```turtle
<http://example.org/doc> a owl:Ontology ; owl:imports <http://www.w3.org/ns/prov-o#> .
```

**Curiosity** - Recommendation `external_reference` - External references: Imported terms are not loaded: referenced by IRI, finding recorded.
  Rationale: Offline tool: the import closure is not resolved.
  Other options: `load_closure_offline` (Load the closure (offline cache)).

**Neo4j** - Recommendation `external_reference` - External references: Imported terms are not loaded: referenced by IRI, finding recorded.
  Rationale: Offline tool: the import closure is not resolved.
  Other options: `load_closure_offline` (Load the closure (offline cache)).

**What is lost**: The tool is offline: the import closure is not loaded, and imported terms stay referenced by IRI.

**Compensation**: Human decision (no automatic compensation)


## General (G) {#general-g}

### G01 — Construct not transposed {#g01-construct-non-transpose}

- **Construct**: Non-representable construct (OntoModel.unmapped)
- **Detection**: Triples not consumed by any rule.
- **Severity**: lost (certain loss without compensation)
- **Example in trap**: `am:tech_leroy`

**OWL example**

```turtle
ex:Technician a owl:Class .
ex:tech_leroy a ex:Technician ;
    ex:certifiedFor [ a owl:Class ; owl:oneOf ( ex:hybrid ex:electric ) ] .
```

**Curiosity** - Recommendation `report` - List in the report: Information kept in the transposition report only.
  Rationale: No silent loss: everything not transposed is listed.

**Neo4j** - Recommendation `report` - List in the report: Information kept in the transposition report only.
  Rationale: No silent loss: everything not transposed is listed.

**What is lost**: Everything not transposed is listed in the report. No loss is silent, but the information cannot be used.

**Compensation**: Documentation (transposition report)


## Individuals (I) {#individus-i}

### I01 — Individual {#i01-individu}

- **Construct**: Named individual
- **Detection**: Individual declared in the ontology.
- **Severity**: review (to decide)
- **Example in trap**: `—`

**OWL example**

```turtle
ex:FuelType a owl:Class .
ex:Petrol a ex:FuelType .   # named individual
```

**Curiosity** - Recommendation `reference_nodes` - Reference node: Ingested as reference data (facets).
  Rationale: Members of enumerations and reference lists → nodes; other individuals: sample data.
  Other options: `ignore` (Ignore).

**Neo4j** - Recommendation `reference_nodes` - Reference node: Ingested as reference data (facets).
  Rationale: Members of enumerations and reference lists → nodes; other individuals: sample data.
  Other options: `ignore` (Ignore).

**What is lost**: Reference data is ingested as nodes (facets) or ignored (sample data).

**Compensation**: Human decision (no automatic compensation)

### I02 — Identity (sameAs) {#i02-identite-sameas}

- **Construct**: owl:sameAs
- **Detection**: Identical individuals.
- **Severity**: lost (certain loss without compensation)
- **Example in trap**: `am:garage_TLN01`

**OWL example**

```turtle
ex:garage_TLN01 owl:sameAs ex:garage_toulon_01 .
```

**Curiosity** - Recommendation `merge_nodes` - Merge the nodes: Canonical key + alias.
  Rationale: OWL has no UNA; the LPG assumes UNA: explicit merge.
  Other options: `same_as_edge` (SAME_AS relationship).

**Neo4j** - Recommendation `merge_nodes` - Merge the nodes: Canonical key + alias.
  Rationale: OWL has no UNA; the LPG assumes UNA: explicit merge.
  Other options: `same_as_edge` (SAME_AS relationship).

**What is lost**: An LPG assumes UNA: either merge explicitly (canonical key plus alias) or keep two linked nodes. Identity substitution is no longer automatic.

**Compensation**: Materialization (derived property or edge recomputed after ingestion)

### I03 — Individual difference {#i03-difference-d-individus}

- **Construct**: owl:differentFrom / owl:AllDifferent
- **Detection**: Difference assertions.
- **Severity**: auto (applied directly)
- **Example in trap**: `am:Petrol`

**OWL example**

```turtle
ex:Petrol owl:differentFrom ex:Diesel .
```

**Curiosity** - Recommendation `noop_una` - No effect (UNA): The LPG assumes UNA everywhere (strengthening).
  Rationale: Already guaranteed by distinct keys.

**Neo4j** - Recommendation `noop_una` - No effect (UNA): The LPG assumes UNA everywhere (strengthening).
  Rationale: Already guaranteed by distinct keys.

**What is lost**: Nothing: UNA is already guaranteed by distinct keys (strengthening).

**Compensation**: none

### I04 — Negative assertion {#i04-assertion-negative}

- **Construct**: owl:NegativePropertyAssertion
- **Detection**: Negative assertion.
- **Severity**: lost (certain loss without compensation)
- **Example in trap**: `am:veh_002`

**OWL example**

```turtle
[ a owl:NegativePropertyAssertion ; owl:sourceIndividual ex:veh_002 ;
  owl:assertionProperty ex:hasOwner ; owl:targetIndividual ex:bob ] .
```

**Curiosity** - Recommendation `validation` - Validation (forbidden relationship / value): Application-level check.
  Rationale: No negative fact in an LPG (closed world: absence is enough, the prohibition is validated).
  Other options: `ignore` (Ignore).

**Neo4j** - Recommendation `validation` - Validation (forbidden relationship / value): Application-level check.
  Rationale: No negative fact in an LPG (closed world: absence is enough, the prohibition is validated).
  Other options: `ignore` (Ignore).

**What is lost**: An LPG has no negative fact (absence is enough), so the prohibition can only be validated.

**Compensation**: Validation (check at ingestion or detection query)

### I05 — Multi-typed individual {#i05-individu-multi-type}

- **Construct**: Individual with several types
- **Detection**: Types not related by subsumption.
- **Severity**: review (to decide)
- **Example in trap**: `am:veh_001`

**OWL example**

```turtle
ex:Car a owl:Class . ex:Taxi a owl:Class .
ex:veh_001 a ex:Car, ex:Taxi .   # types not related by subsumption
```

**Curiosity** - Recommendation `primary_parent_discriminator` - Main type + discriminator: One type carries the node; the others become discriminators.
  Rationale: Curiosity is single-type.
  Other options: `multi_label` (Multi-labels).

**Neo4j** - Recommendation `multi_label` - Multi-labels: All types as labels.
  Rationale: Curiosity is single-type.
  Other options: `primary_parent_discriminator` (Main type + discriminator).

**What is lost**: Curiosity is single-type: one type carries the node and the other membership becomes a discriminator.

**Compensation**: Human decision (no automatic compensation)


## Naming (N) {#nommage-n}

### N01 — Naming *(Must, iteration 1)* {#n01-nommage-must-it-1}

- **Construct**: Naming conventions / collisions
- **Detection**: Name outside the convention (snake_case, hyphen…) or a collision after normalization (case-insensitive).
- **Severity**: auto (applied directly)
- **Example in trap**: `am:dtc_code`

**OWL example**

```turtle
ex:Diagnostic a owl:Class .
ex:dtc_code a owl:DatatypeProperty ; rdfs:domain ex:Diagnostic ; rdfs:range xsd:string .
```

**Curiosity** - Recommendation `rename` - Rename: Normalized name (Curiosity: PascalCase; Neo4j: PascalCase / UPPER_SNAKE / camelCase); on collision → `has` prefix.
  Rationale: Target conventions; unique names are required.
  Other options: `ignore` (Keep the name).

**Neo4j** - Recommendation `rename` - Rename: Normalized name (Curiosity: PascalCase; Neo4j: PascalCase / UPPER_SNAKE / camelCase); on collision → `has` prefix.
  Rationale: Target conventions; unique names are required.
  Other options: `ignore` (Keep the name).

**What is lost**: The name is normalized (`dtcCode` / `DtcCode`). On a collision after normalization, the `has` prefix is added. The original IRI stays in `source`.

**Compensation**: Renaming


## SHACL (S, tooling) {#shacl-s-outillage}

### S01 — OWL / SHACL conflict {#s01-conflit-owl-shacl}

- **Construct**: OWL / SHACL conflict
- **Detection**: SHACL constraint incompatible with the OWL axiom (cardinality, type).
- **Severity**: review (to decide)
- **Example in trap**: `—`

**Example**

```turtle
# shapes (SHACL Turtle)
ex:OrderShape a sh:NodeShape ; sh:targetClass ex:RepairOrder ;
    sh:property [ sh:path ex:performedBy ; sh:maxCount 3 ] .
# ontology: ex:performedBy a owl:FunctionalProperty
```

**Curiosity** - Recommendation `shacl_wins` - Shapes take priority: The schema follows the shape (data contract).
  Rationale: Shapes describe the data contract; OWL describes what can be inferred.
  Other options: `owl_wins` (OWL takes priority).

**Neo4j** - Recommendation `shacl_wins` - Shapes take priority: The schema follows the shape (data contract).
  Rationale: Shapes describe the data contract; OWL describes what can be inferred.
  Other options: `owl_wins` (OWL takes priority).

**What is lost**: One of the two contracts is set aside for this point: `shacl_wins` follows the shape, `owl_wins` ignores it.

**Compensation**: Human decision (no automatic compensation)

### S02 — Property from the shapes {#s02-propriete-issue-des-shapes}

- **Construct**: SHACL property not declared in OWL
- **Detection**: Shape path missing from the ontology.
- **Severity**: review (to decide)
- **Example in trap**: `—`

**Example**

```turtle
# shapes (SHACL Turtle)
ex:OrderShape a sh:NodeShape ; sh:targetClass ex:RepairOrder ;
    sh:property [ sh:path ex:priority ; sh:datatype xsd:integer ] .
# ex:priority is not declared anywhere in the ontology
```

**Curiosity** - Recommendation `property` - Add the property: Created from the shape (sh:datatype type).
  Rationale: Shapes complete the schema.
  Other options: `ignore` (Ignore).

**Neo4j** - Recommendation `property` - Add the property: Created from the shape (sh:datatype type).
  Rationale: Shapes complete the schema.
  Other options: `ignore` (Ignore).

**What is lost**: Nothing if the property is created from the shape (typed by `sh:datatype`). Otherwise it is ignored.

**Compensation**: none


## General (G) {#general-g-2}

### G02 — Decision ignored {#g02-decision-ignoree}

- **Construct**: Invalid decision
- **Detection**: Unknown option for the targeted finding.
- **Severity**: review (to decide)
- **Example in trap**: `—`

**Example**

```json
{ "C07:https://example.org/doc#Customer": "option_inconnue" }
```

**Curiosity** - Recommendation `report` - List in the report: Information kept in the transposition report only.
  Rationale: The recommendation is applied instead.

**Neo4j** - Recommendation `report` - List in the report: Information kept in the transposition report only.
  Rationale: The recommendation is applied instead.

**What is lost**: The decision is ignored, the recommendation applies instead, and G02 reports it.

**Compensation**: Human decision (no automatic compensation)

## Recommendations overridden per finding {#recommandations-surchargees-par-constat}

| Rule | Condition | Recommendation |
|---|---|---|
| C09 | union as a superclass (covering axiom) rather than an equivalence | `doc_only` (both targets) |
| K03 | anonymous instances (blank nodes) | `generated_key` |
| D04 | several values observed for the same individual | `list_property` |
| D05 | xsd:hexBinary / base64Binary | `string_lexical` |
| D12 | several domains (not ranges) | `intersection_domain` |
| O13 | reflexivity alone | `ignore` (never materialize loops) |
| O21 | one of the domains subsumes the other | `most_specific_type` |
| I01 | individual outside an enumeration / reference list (sample data) | `ignore` |

## Semantic traps covered (`must_not` oracle) {#pieges-semantiques-couverts-oracle-mustnot}

1. `owl:hasKey` imposes neither existence nor uniqueness (Structural Specification §9.5). K02 is never `auto`, and NODE KEY / `[Key]` are strengthenings.
2. Two `rdfs:domain` (or `rdfs:range`) axioms mean an **intersection** (rdfs2/rdfs3). That is D12 / O21, never D03 / O03, which require an explicit `owl:unionOf`.
3. A reification with 3 or more roles is an n-ary relation: R02 (node kept), never R01.
4. For a non-simple property (transitive, chain, or their superproperties / inverses), no cardinality (O09/O10/O16) is generated.
5. A blank node has no IRI: K04 (generated key), never K01.