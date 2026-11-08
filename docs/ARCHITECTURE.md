# OntoForge : structuration du projet

Outil de conception d'ontologies et de transposition OWL 2 / RDFS (+ SHACL) vers un Labeled Property Graph (LPG) prêt à l'emploi pour Neo4j et Curiosity.

## 1. Le problème de fond

Une ontologie OWL et un modèle property graph ne disent pas la même chose :

| | OWL 2 / RDFS | Property graph (LPG) |
|---|---|---|
| Hypothèse | Monde ouvert (OWA), pas d'UNA | Monde clos, schéma = contrat d'ingestion |
| Rôle des axiomes | Inférer (raisonneur) | Contraindre / valider (ou rien) |
| Identité | IRI globale | Clé métier locale (+ id interne) |
| Typage | Multiple, dynamique, inféré | Labels figés (Neo4j multi-label, Curiosity mono-type) |
| Relations | Propriétés binaires de 1ère classe, hiérarchisables | Types d'arêtes plats, porteuses de propriétés (Neo4j) ou non (Curiosity) |
| Littéraux | xsd:*, langString, datatypes custom | Types natifs limités |

La transposition se divise donc en trois parts. Une partie est mécanique. Une autre fait perdre de la sémantique. La dernière n'a aucun équivalent et devient une règle de validation, une requête ou de la matérialisation. L'outil classe chaque élément dans l'une de ces catégories et fait arbitrer les deux dernières par un humain.

## 2. Les quatre modules

```
┌──────────────┐   ┌──────────────┐   ┌───────────────────┐   ┌────────────────┐
│ 1. CONCEVOIR │──▶│ 2. ANALYSER  │──▶│ 3. ARBITRER       │──▶│ 4. GÉNÉRER     │
│ éditeur OWL  │   │ moteur de    │   │ décisions humaines│   │ Neo4j / Curio. │
│ import/export│   │ règles       │   │ + recommandations │   │ + rapport      │
└──────────────┘   └──────────────┘   └───────────────────┘   └────────────────┘
        ▲                                                             │
        └────────────── aller-retour (ré-analyse incrémentale) ───────┘
```

### 2.1 Concevoir (façon Protégé, en plus rapide)
- Arbre des classes, propriétés objet, propriétés de données, individus.
- Éditeur de classe : sous-classes, équivalences, disjonctions, restrictions (some / only / min / max / exactly / value), clés (`owl:hasKey`).
- Éditeur de propriété : domaine, portée, inverse, caractéristiques (fonctionnelle, inverse-fonctionnelle, transitive, symétrique, asymétrique, réflexive, irréflexive), sous-propriétés, chaînes.
- Saisie rapide (DSL) : une ligne = un axiome, pour dégrossir une ontologie en quelques minutes.
- Import : Turtle, N-Triples, RDF/XML (OWL exporté par Protégé), JSON-LD simple. Export Turtle.
- Projet sauvegardé en JSON (ontologie + décisions d'arbitrage).

### 2.2 Analyser : moteur de règles
Entrée : méta-modèle ontologique (§3.1) + profil cible (Neo4j ou Curiosity).
Sortie : liste de constats (`Finding`), chacun avec :
- `severity` : `auto` (transposition triviale), `review` (perte possible, à arbitrer), `lost` (pas d'équivalent natif, perte certaine si rien n'est fait)
- `options` : alternatives de transposition, chacune avec son impact
- `recommended` : l'option conseillée pour la cible choisie
- `rule` : identifiant de la règle (traçabilité)

### 2.3 Arbitrer
- Vue par sévérité : ce qui passe tout seul est replié, ce qui est à risque est mis en avant.
- Chaque arbitrage est stocké (`decisions[findingId] = optionId`) et rejoué à la ré-analyse. Modifier l'ontologie ne fait pas perdre les choix déjà faits.
- « Accepter toutes les recommandations » pour aller vite, puis affiner.

### 2.4 Générer
- Neo4j : DDL Cypher (contraintes d'unicité / de clé / d'existence / de type, index), templates d'ingestion `MERGE`, schéma JSON, diagramme.
- Curiosity : classes C# `[Node]` / `[Key]` / `[Property]`, classe `Edges` (paires aller/retour), code d'enregistrement du schéma, squelette de connecteur.
- Rapport de transposition (Markdown) : ce qui a été perdu, pourquoi, et la compensation retenue (validation applicative, requête, matérialisation).

## 3. Contrats de données

### 3.1 Méta-modèle ontologique (`OntoModel`)
```js
{
  meta: { iri, prefixes: {owl:..., ex:...}, label, comment, imports: [] },
  classes: { [iri]: {
     iri, label: {fr?, en?, ...}|string, comment,
     subClassOf: [iri],              // parents nommés
     equivalentTo: [ClassExpr], disjointWith: [iri],
     restrictions: [ { property: iri, kind: 'some'|'only'|'min'|'max'|'exactly'|'value',
                       n?: int, filler?: iri|xsd, value?: any } ],
     oneOf?: [iri],                  // classe énumérée
     unionOf?: [iri], intersectionOf?: [iri],
     hasKey?: [iri], deprecated?: bool } },
  objectProperties: { [iri]: {
     iri, label, comment, domain: [iri], range: [iri],
     domainUnion?: bool, rangeUnion?: bool,      // true si domaine/portée = owl:unionOf
     inverseOf?: iri, subPropertyOf: [iri], chain?: [[iri]],
     characteristics: ['functional','inverseFunctional','transitive','symmetric',
                       'asymmetric','reflexive','irreflexive'] } },
  datatypeProperties: { [iri]: {
     iri, label, comment, domain: [iri], range: [xsd], domainUnion?: bool,
     subPropertyOf: [iri], functional: bool } },
  annotationProperties: { [iri]: { iri, label } },
  individuals: { [iri]: { iri, label, types: [iri],
     facts: [ { property: iri, value: iri|literal, datatype?, lang? } ] } },
  shapes?: { ... }                   // SHACL (v2)
}
```
`ClassExpr` = `iri` | `{ op: 'and'|'or'|'not'|'restriction'|'oneOf', args: [...] }`.

### 3.2 Méta-modèle cible (`PGModel`)
```js
{
  target: 'neo4j'|'curiosity',
  nodeTypes: { [name]: { name, labels: [str], source: [iri], key: [propName],
     properties: [ { name, type, list: bool, required: bool, unique: bool,
                     indexed: bool, source: iri, note? } ] } },
  edgeTypes: [ { name, from, to, reverse?: str, source: iri,
     properties: [ ... ], cardinality: { out: '0..1'|'0..*'|'1'|'1..*', in: ... },
     directed: bool, note? } ],
  validations: [ { kind, target, expr, source } ],   // ce qui devient du contrôle applicatif
  materializations: [ { kind, source, description } ], // fermetures transitives, chaînes, inverses
  findings: [Finding], decisions: { [findingId]: optionId }
}
```

## 4. Catalogue des règles (cœur métier)

| ID | Construct OWL | Sévérité | Neo4j (reco) | Curiosity (reco) |
|---|---|---|---|---|
| C01 | `owl:Class` | auto | Label | Node type |
| C02 | `rdfs:subClassOf` (simple) | review | Multi-labels (héritage des propriétés) | Aplatir : propriétés recopiées dans la feuille + propriété discriminante |
| C03 | Héritage multiple | review | Multi-labels | Choisir un parent principal, discriminant pour l'autre |
| C04 | Classe abstraite (sans instance directe, que des sous-classes) | review | Label secondaire seulement | Pas de node type, fusion dans les feuilles |
| C05 | `owl:equivalentClass` (nommée) | lost | Fusionner les labels | Fusionner |
| C06 | `owl:equivalentClass` / définition par restriction (classe définie) | lost | Label calculé par requête / job de classification | Idem, matérialisé à l'ingestion |
| C07 | `owl:disjointWith` | lost | Règle de validation | Règle de validation |
| C08 | `owl:oneOf` (énumération) | review | Propriété enum (contrainte de valeurs app.) ou nœuds de référence | Nœuds de référence (facettes) |
| C09 | `unionOf` / `intersectionOf` anonymes | lost | Documenté, pas transposé | Idem |
| K01 | Identité IRI | auto | Propriété `uri` + contrainte d'unicité | `[Key]` = uri |
| K02 | `owl:hasKey` | auto | Contrainte NODE KEY | `[Key]` (une seule clé : composite → concaténation) |
| K03 | Pas de clé métier | review | `uri` | `uri` ou propriété choisie |
| D01 | Datatype property, domaine unique | auto | Propriété | `[Property]` |
| D02 | Sans domaine | review | Rattacher à chaque classe utilisatrice / à la racine | Idem |
| D03 | Domaine multiple (union) | review | Dupliquer sur chaque label | Dupliquer |
| D04 | Non fonctionnelle | review | Liste (array) | `string[]` / liste |
| D05 | Typage xsd avec perte (decimal, gYear, duration, langString, datatypes custom) | review | Selon type (String / Float / Duration…) | Selon type |
| D06 | `rdf:langString` / labels multilingues | review | Une propriété par langue (`label_fr`) | Une propriété par langue |
| D07 | `owl:FunctionalProperty` (data) | auto | Scalaire + (optionnel) contrainte de type | Scalaire |
| O01 | Object property, domaine/portée uniques | auto | Type de relation | Edge + reverse |
| O02 | Sans domaine ou sans portée | review | Résolu depuis les restrictions, sinon à arbitrer | Idem |
| O03 | Domaine/portée multiples | review | Un type de relation, plusieurs paires de labels | Un edge par paire |
| O04 | `owl:inverseOf` | auto | Un seul sens stocké, l'autre traversé | Paire edge / reverse native |
| O05 | Symétrique | review | Un sens stocké, requête non orientée | Edge = son propre reverse |
| O06 | Transitive | lost | Requête à longueur variable `*1..` | Matérialiser ou traverser |
| O07 | `rdfs:subPropertyOf` | lost | Type le plus spécifique (+ option : matérialiser le parent) | Idem |
| O08 | `owl:propertyChainAxiom` | lost | Requête de chemin / matérialisation | Matérialisation |
| O09 | Fonctionnelle / `max 1` / `exactly 1` sur objet | review | Validation applicative (pas de contrainte de cardinalité de relation) | Validation applicative |
| O10 | `some` / `min n` (existence) | review | Validation applicative | Validation applicative |
| O11 | `only` (allValuesFrom) | lost | Validation de type de cible | Validation |
| O12 | `hasValue` | review | Valeur par défaut / propriété fixe | Idem |
| O13 | Réflexive / irréflexive / asymétrique | lost | Validation | Validation |
| R01 | **Classe de réification** (n-aire : classe portant ≥ 2 object properties fonctionnelles + des data properties) | review | **Relation porteuse de propriétés** | Garder un nœud (les edges Curiosity ne portent pas de propriétés) |
| A01 | Annotations (`rdfs:label`, `rdfs:comment`, `skos:*`) | auto | Métadonnées du schéma / doc | Idem |
| I01 | Individus | review | Données de référence (nœuds) ou ignorer | Idem |
| N01 | Conventions de nommage | auto | `PascalCase` labels, `UPPER_SNAKE` relations, `camelCase` propriétés | `PascalCase` partout |

## 5. Recommandations par profil cible

Neo4j : les multi-labels font passer l'héritage, les relations porteuses de propriétés permettent de dé-réifier, et les contraintes Cypher ne portent que sur les nœuds et propriétés, donc les cardinalités deviennent de la validation.

Curiosity : un nœud = un type, une clé `string`. Les edges sont typés, sans propriétés, déclarés par paires aller/retour. L'héritage s'aplatit, la réification reste un nœud et les inverses sont gratuits.

## 6. Arborescence du prototype

```
OntoForge/
  index.html                  ouvrir dans le navigateur (aucun serveur requis)
  css/app.css
  vendor/                     n3.min.js, cytoscape.min.js (hors-ligne)
  js/core/model.js            OntoModel : création, helpers, IRIs, xsd
  js/io/turtle.js             import Turtle/N-Triples (N3.js) → OntoModel
  js/io/rdfxml.js             import RDF/XML (DOMParser) → triples
  js/io/export-turtle.js      OntoModel → Turtle
  js/io/dsl.js                saisie rapide
  js/mapping/rules.js         catalogue de règles
  js/mapping/engine.js        analyse + application des décisions → PGModel
  js/targets/neo4j.js         générateur Cypher
  js/targets/curiosity.js     générateur C#
  js/targets/report.js        rapport Markdown
  js/ui/*.js                  vues
  samples/*.ttl               ontologies d'exemple
  tests/*.test.js             tests node
  .claude/agents/*.md         agents spécialisés pour faire évoluer l'outil
  CLAUDE.md
```

## 7. Feuille de route

- v0.1 (ce prototype) : éditeur, DSL, import TTL/RDF-XML, moteur de règles, arbitrage, génération Neo4j + Curiosity + rapport, diagramme.
- v0.2 : import SHACL (les shapes sont plus proches d'un schéma LPG qu'OWL : priorité aux shapes quand elles existent), diff entre deux versions d'ontologie, export SHACL depuis les décisions de validation.
- v0.3 : assistant de conception (génération d'ontologie depuis un texte / un CSV / un schéma SQL), alignement avec des ontologies de référence (schema.org, gist, BFO…), cibles supplémentaires (Neptune openCypher, Memgraph, GQL / PG-Schema).
