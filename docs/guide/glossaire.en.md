# Glossary {#glossaire}

Vocabulary of OntoForge, of the OWL/SHACL world and of the property graph world. References marked "SS" point to the *OWL 2 Structural Specification*.

## Ontology and W3C {#ontologie-et-w3c}

| Term | Definition |
|---|---|
| **OWL 2** | W3C ontology language (description logic). OntoForge reads and writes OWL 2 / RDFS. |
| **RDF / Turtle** | Data model made of triples (subject, predicate, object) and its readable syntax. Main exchange format of OntoForge; RDF/XML, JSON-LD, N-Triples, N3 and TriG are read too. |
| **IRI** | Global identifier of a resource (class, property, individual). Always absolute in OntoForge models; shortened to a **CURIE** (`am:Vehicle`) for display. |
| **Class** | Set of individuals (`owl:Class`). Becomes a node type (Curiosity) or a label (Neo4j). |
| **Object property** | Relation between two individuals (`owl:ObjectProperty`). Becomes an edge / relationship. |
| **Datatype property** | Relation between an individual and a literal (`owl:DatatypeProperty`). Becomes a node property. |
| **Individual** | Named instance (`owl:NamedIndividual`) or anonymous one (blank node). |
| **Blank node (bnode)** | Individual without an IRI. No key can be derived: rule K04. |
| **Restriction** | Anonymous class defined by a property and a quantifier: `some` (∃), `only` (∀), `min`/`max`/`exactly` (cardinalities), `value`, `self`. |
| **Domain / range** | `rdfs:domain` / `rdfs:range` **infer** the type of the subject / object (rdfs2/rdfs3); they do not constrain it. Several domains mean an **intersection**. |
| **Union (`owl:unionOf`)** | "A or B". Only an explicit union allows a property to be duplicated (D03/O03). |
| **Functional property** | At most one value per subject (`owl:FunctionalProperty`). |
| **Simple property** | A property that is neither transitive, nor defined by a chain, nor a super-property / inverse of such a property (SS §11.2). Only simple properties accept cardinalities in OWL 2 DL. |
| **`owl:hasKey`** | Key of a class. It enforces **neither existence nor uniqueness**: it infers `sameAs` between named individuals with the same values (SS §9.5). |
| **Punning** | Using the same IRI as a class and as an individual (SS §5.9). Legal in OWL 2 DL (rule C12). |
| **GCI** | *General Class Inclusion*: a `subClassOf` axiom whose subject is anonymous (rule C13). |
| **OWA (open world)** | What is not asserted is not false, only unknown. Assumption of OWL. |
| **CWA (closed world)** | What is not in the database is false. Assumption of property graphs. |
| **UNA** | *Unique Name Assumption*: two different names denote two different things. Absent from OWL, assumed by a property graph. |
| **OWL 2 profiles (DL, EL, QL, RL)** | Subsets of OWL 2 with different computational properties. OntoForge reports conformance to each one, with the reasons for any gap. |
| **Reasoner (HermiT)** | Program that computes the inferences of an ontology. Optional in OntoForge (subprocess, never blocking). |
| **Rules W01–W07 / BP01–BP07** | OWL 2 DL conformance codes (W) and best-practice codes (BP) of the Conformance screen. Not the same as the transposition rules. |

## SHACL {#shacl}

| Term | Definition |
|---|---|
| **SHACL** | W3C language for *constraints* on RDF graphs. Closer to a data schema than OWL is. |
| **NodeShape / PropertyShape** | Shape that applies to target nodes / to the values of a property path. |
| **Constraint** | `sh:minCount`, `sh:maxCount`, `sh:datatype`, `sh:class`, `sh:in`, `sh:pattern`, `sh:closed`... |
| **Validation report** | `conforms` + list of results (`focus`, `path`, `severity`, `constraint`, `message`, `value`, `shape`). |
| **Inference (validation)** | Off by default in OntoForge (D-034): under RDFS, `sh:closed` would see the super-properties. |

## Property graph and targets {#property-graph-et-cibles}

| Term | Definition |
|---|---|
| **Property graph (LPG)** | Graph of directed nodes and relationships that carry properties. The schema is an ingestion contract (closed world). |
| **Curiosity** | Knowledge graph platform (primary target). Schema as C# classes with `[Node]`, `[Key]`, `[Property]`, edges as **forward/backward pairs**, a single type per node. |
| **Neo4j** | Graph database (secondary target). Multiple labels, relationship properties, Cypher constraints. |
| **Node type** | `NodeType` of the `PGModel`: name, labels, key, properties. |
| **Edge type / relationship** | `EdgeType`: `from`, `to`, `reverse`, cardinality. No properties in Curiosity. |
| **Key** | Property (or properties) that identify a node: `[Key]` (Curiosity), `UNIQUE` / `NODE KEY` (Neo4j). |
| **`uri` / `Uri`** | Property that holds the original IRI of a node (marked `urn:ontoforge:iri`), default key. |
| **Discriminator** | `<root>Kind` property that holds the subtype when the hierarchy is flattened (Curiosity). |
| **Multi-label** | Several labels per node (natural inheritance in Neo4j). |
| **Edge pair** | Curiosity: each relationship is declared together with its backward edge (`Link(a, b, forward, backward)`). |
| **Reification** | Representing a relationship with an intermediate node (R01 binary, R02 n-ary). **De-reifying** replaces that node with a relationship that carries properties (Neo4j only). |
| **Materialization** | Computing and storing a fact that the reasoner would infer (transitive closure, chain, classification, `sameAs`). |
| **Validation (application level)** | Check run at ingestion time (connector) or detection query, where the database cannot enforce a constraint. |
| **NODE KEY** | Neo4j Enterprise constraint: existence + uniqueness of a set of properties. |
| **Enterprise / Community** | Neo4j editions. Some constraints (`NODE KEY`, `IS NOT NULL`, types) are Enterprise-only. |
| **GraphQL (schema)** | `schema.graphql` generated for both targets. For Neo4j it uses directives of the Neo4j GraphQL Library (`À VÉRIFIER`). |

## OntoForge decisions {#arbitrage-ontoforge}

| Term | Definition |
|---|---|
| **Finding (`Finding`)** | Result of a rule on an element of the ontology: identifier, severity, options, recommendation. |
| **`auto` severity** | Trivial transposition, applied directly. |
| **`review` severity** | Possible loss: a human decides. |
| **`lost` severity** | No native equivalent: the loss is certain until a compensation is chosen. |
| **Option** | One way to transpose a finding (`multi_label`, `validation`...). The identifiers form the normative vocabulary of `samples/trap/expected-findings.yaml`. |
| **Recommendation** | Option applied until a human decides; specific to the target. |
| **Decision** | `{finding: option}` stored in the project per target and replayed at each analysis. Grouped form: `"<rule>:*"`. |
| **Compensation** | What the engine generates to limit the loss: validation, materialization, query, documentation. |
| **Trap ontology (`trap`)** | `samples/trap/trap.ttl`: exercises the 66 rules and the semantic traps (`must_not`). |
| **Oracle** | `samples/trap/expected-findings.yaml`: minimal expected findings, replayed by the tests. |
| **`À VÉRIFIER`** | Marks an external API (Curiosity.Library, Neo4j, pySHACL...) whose behavior has not been confirmed by running it. |
| **`X00`** | Former generic finding for unimplemented rules. No longer emitted (all 66 rules are implemented). |

## Iteration 2 {#iteration-2}

| Term | Definition |
|---|---|
| **Perimeter** | Named subset of the ontology (classes, properties, with or without descendants) to transpose. A project can have several; one is selected with `?perimeter=<id>`. It is never applied implicitly: `active_perimeter` is a UI state. Information findings P00–P03. |
| **Operation (`op`)** | Atomic editing gesture (`add_class`, `rename_entity`...) sent to `POST /ops`. A batch is applied entirely or not at all. |
| **Simple property** | Property that is not transitive, not the target of a chain and has no non-simple super-property. Only these are allowed for cardinalities, functional, asymmetric... (OWL 2 Structural Spec §11.2). |
| **Guided query (`GuidedQuery`)** | Query built like a sentence ("I'm looking for a Vehicle that has as repair order..."): root, steps, filters, columns. Translated to SPARQL, Cypher, Curiosity and GraphQL. |
| **Natural-language question** | Free text converted into an editable guided query (`/query/nl`): deterministic match against labels + optional LLM. Any unknown element is dropped (`unmatched`). |
| **Active SPARQL endpoint** | The endpoint, among those declared in Settings, on which queries run. Only one at a time. |
| **Proposal** | Set of classes, properties or changes suggested by the assistant, highlighted (additions in green, changes in orange) and accepted or rejected item by item. Nothing is applied before acceptance. |
| **Discriminator** | Property (`VehicleKind`, `PartyKind`) that keeps the original type when subclasses are folded under a concrete root. |
| **Copy into leaves** | Under a merged abstract class (C04 `merge_into_leaves`), the properties and relationships of the ancestor are duplicated in each concrete subtype (D-L15-01). |
| **LLM provider** | Configuration `{type, URL, model, key}` (`anthropic`, `openai_compat`, `ollama`, `mock`). The key is encrypted on the server. |
| **Master key** | `ONTOFORGE_SECRET_KEY`: derives the encryption key (Fernet) for secrets. Without it, the `.secret` file is used. |
| **Krakie** | OntoForge mascot: a small lagoon-colored pixel-art octopus with 9 poses (welcome, thinking, reading, magnifier, graph, happy, worried, forge, trophy). It forges (two hammers on an anvil) during a generation or a transposition, then holds up a graph-shaped trophy when done. |
| **Dashboard** | Home screen of a project: state of the four steps and next action. |
| **Quick input** | Editor panel: one DSL line = one axiom. |

## The agent team {#equipe-d-agents}

| Term | Definition |
|---|---|
| **Batch (`Lx`)** | Unit of work set out in a contract, `lots/Lx.md`. |
| **Owner / reviewer** | The agent that produces a batch / the agents that cross-review it. |
| **Review (`verdict: OK\|KO`)** | File `journal/Lx/review-<reviewer>-it<N>.md`. |
| **Agent room** | Live tracking Artifact (collection `events`). |
| **Skill** | Reusable method maintained by an agent in `skills/<name>/SKILL.md`. |
