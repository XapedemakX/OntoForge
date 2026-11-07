# Revue W3C — catalogue de règles (§4) et contrats (§3) de docs/ARCHITECTURE.md — L0

Relecteur : w3c — 2 nov. 2026. Ontologie d'essai : `samples/trap/trap.ttl` (66 règles exercées), oracle `samples/trap/expected-findings.yaml`.
Références : OWL 2 Structural Specification (2e éd., 2012) = **SS**, OWL 2 Mapping to RDF Graphs = **MAP**, OWL 2 Profiles = **PRO**, RDF 1.1 Semantics = **RSEM**, RDF 1.1 Concepts = **RCON**.

```
verdict: KO
bloquants:
  - B1 [ARCHITECTURE.md:124,130] D03/O03 traitent « domaine/portée multiples » comme une union → écart RSEM §9.2.1 (rdfs2/rdfs3) et SS §9.2.5/9.3.4.
  - B2 [ARCHITECTURE.md:120] K02 owl:hasKey « auto » → écart SS §9.5 : hasKey n'impose ni existence ni unicité.
  - B3 [ARCHITECTURE.md:126] D05 cite xsd:gYear / duration comme types simplement « avec perte » → hors carte OWL 2 DL (SS §4, §5.2).
  - B4 [ARCHITECTURE.md:127] D06 cite rdf:langString : absent de la carte OWL 2 (SS §4.3) → rdf:PlainLiteral.
  - B5 [ARCHITECTURE.md:142] R01 dé-réifie toute classe à ≥ 2 rôles, y compris les relations n-aires (≥ 3 rôles) → impossible en LPG.
  - B6 [ARCHITECTURE.md:115] C05 « lost » : deux classes nommées équivalentes ont la même extension, la fusion ne perd rien → review.
  - B7 [ARCHITECTURE.md:68-72] contrat restriction incomplet (inverse, data vs objet, qualifiée, hasSelf, fillers anonymes).
  - B8 [ARCHITECTURE.md:72] hasKey?: [iri] → une classe peut porter plusieurs clés : [[iri]].
  - B9 [ARCHITECTURE.md:63-86] contrat sans datatypes définis, sans assertions négatives / sameAs / AllDifferent, sans versionIRI ni annotations d'axiome, sans réceptacle pour l'inconnu → perte silencieuse au round-trip.
  - B10 [ARCHITECTURE.md:106-145] 30 constructs OWL 2 DL sans règle (liste §3) → toute ontologie Protégé réelle produirait des pertes non signalées.
non-bloquants: voir §4
skill: skills/w3c-ontology-conformance/SKILL.md créé (checklists, pièges, bug owlrl prp-key).
```

## 1. Erreurs sémantiques (bloquants B1–B6) et lignes corrigées

**B1 — Domaines / portées multiples.** Deux triplets `rdfs:domain` (ou `rdfs:range`) sur la même propriété signifient que le sujet est instance des **deux** classes (RSEM §9.2.1, règles rdfs2/rdfs3 ; SS §9.2.5 : chaque `ObjectPropertyDomain` est un axiome indépendant). Seul `rdfs:domain [owl:unionOf (…)]` exprime une union. Le contrat a déjà `domainUnion`, mais D03/O03 disent « multiples ». Lignes corrigées + nouvelles règles O21/D12 :
```
| D03 | Domaine = `owl:unionOf` (union explicite) | review | Dupliquer sur chaque label | Dupliquer |
| O03 | Domaine/portée = `owl:unionOf` (union explicite) | review | Un type de relation, plusieurs paires de labels | Un edge par paire |
| O21 | Plusieurs `rdfs:domain`/`rdfs:range` sur une propriété objet (= **intersection**) | review | Garder la classe la plus spécifique si l'une subsume l'autre, sinon arbitrer (souvent erreur de modélisation) | Idem |
| D12 | Plusieurs `rdfs:domain`/`rdfs:range` sur une propriété de données (= intersection) | review | Type natif de l'intersection des datatypes (+ validation) | Idem |
```

**B2 — owl:hasKey.** SS §9.5 : `HasKey(C P1…Pn)` dit seulement que deux individus **nommés** de C ayant les mêmes valeurs pour P1…Pn sont `owl:sameAs`. Il n'impose pas que la valeur existe et ne signale pas de doublon (il les fusionne). NODE KEY Neo4j = existence + unicité : c'est un **renforcement** qui doit être arbitré. Les clés peuvent en plus porter des propriétés objet (→ K05).
```
| K02 | `owl:hasKey` sur propriétés de données | review | Contrainte NODE KEY (renforcement : existence obligatoire) ; option : unicité seule | `[Key]` (une seule clé : composite → concaténation avec séparateur) ; clés supplémentaires → validation d'unicité |
| K05 | `owl:hasKey` incluant une propriété objet | review | Copier la clé de la cible en propriété (`manufacturerKey`) puis NODE KEY | Concaténation avec la clé du nœud cible |
```

**B3 — Datatypes hors carte OWL 2.** SS §4 et §5.2 : en OWL 2 DL une IRI de datatype doit être `rdfs:Literal`, un datatype de la carte OWL 2 ou une IRI hors vocabulaire réservé (datatype défini). `xsd:date`, `xsd:time`, `xsd:gYear`, `xsd:gYearMonth`, `xsd:duration`… sont dans l'espace xsd réservé mais **pas** dans la carte : l'ontologie quitte OWL 2 DL (HermiT les rejette). C'est d'abord un constat de conformité (L2 → règle de lint W01, §3.2), puis un D05. C'est pourquoi `modelYear` utilise dans le piège un datatype défini `am:ModelYear` (xsd:integer, facettes 1886..2100) et non xsd:gYear.
```
| D05 | Typage xsd avec perte (decimal, hexBinary/base64Binary, dateTimeStamp, owl:real/rational, datatypes définis) ; types hors carte OWL 2 (gYear, date, duration…) : signalés aussi par la conformité (W01) | review | Selon type (Float ou String pour decimal ; String pour binaire ; ZONED DATETIME ; INTEGER pour gYear) | Selon type |
```

**B4 — rdf:langString.** La carte OWL 2 (SS §4.3, 2012) contient `rdf:PlainLiteral`, pas `rdf:langString` (RDF 1.1, 2014). Les littéraux à langue d'un graphe RDF 1.1 sont lus comme des valeurs de `rdf:PlainLiteral`. Une portée `rdf:langString` est acceptée par certains outils, mais ce n'est pas conforme.
```
| D06 | Valeurs multilingues : portée `rdf:PlainLiteral` (ou littéraux `@lang` sur une propriété `xsd:string`) ; portée `rdf:langString` = non conforme OWL 2 (W01) | review | Une propriété par langue (`label_fr`) | Une propriété par langue |
```

**B5 — Réification binaire vs n-aire.** Une relation Neo4j relie exactement deux nœuds : une classe à 3 rôles ou plus (ex. WarrantyClaim : véhicule, pièce, garage, garantie) ne peut pas devenir une relation. Le critère « fonctionnelle » doit aussi accepter `exactly 1` / `max 1` en restriction (cas usuel sous Protégé).
```
| R01 | Classe de réification **binaire** : exactement 2 rôles objet fonctionnels (ou `max/exactly 1`) + des data properties | review | **Relation porteuse de propriétés** | Garder un nœud (les edges Curiosity ne portent pas de propriétés) |
| R02 | Relation **n-aire** (≥ 3 rôles fonctionnels) | review | Garder un nœud (pattern n-aire W3C SWBP) | Garder un nœud |
```

**B6 — Classes nommées équivalentes.** `EquivalentClasses(A B)` avec A et B nommées : extensions identiques, la fusion est **sans perte** (seul un nom devient alias). « lost » fausse le tri de la vue d'arbitrage.
```
| C05 | `owl:equivalentClass` entre classes nommées | review | Fusionner les labels (nom canonique + alias) | Fusionner (nom canonique + alias) |
```

## 2. Contrats §3 (bloquants B7–B9) — corrections exactes

> Mise à jour 23 h : D-028 rend `backend/ontoforge/core/onto_model.py` normatif. Il couvre déjà B7, B8 et la majeure partie de B9 (inverse, `self`, `has_keys: list[list]`, `datatypes`, `negative`, `same_as`/`different_from`, `all_different`, `unmapped`). Restent les écarts listés dans `review-w3c-it1.md` §2. ARCHITECTURE §3 doit simplement renvoyer à `core/*.py`.

**B7 — restrictions** (§3.1, l. 68-69), remplacer par :
```js
restrictions: [ { property: iri | { inverseOf: iri },          // ObjectInverseOf anonyme (SS §6.1.1)
                  propertyKind: 'object'|'data',
                  kind: 'some'|'only'|'min'|'max'|'exactly'|'value'|'self',
                  n?: int,
                  filler?: ClassExpr | DataRange,               // qualifiée : onClass / onDataRange ; filler anonyme admis
                  qualified?: bool,
                  value?: iri | Literal } ],
```
`ClassExpr` (l. 88) : `iri | { op: 'and'|'or'|'not'|'oneOf'|'restriction', args: [...] }`. `'restriction'` porte l'objet ci-dessus, ce qui permet l'imbrication. Ajouter `DataRange = xsd | iri | { op: 'and'|'or'|'not'|'oneOf'|'facet', base?, facets?: [{facet, value}], args? }`.

**B8 — clés** (l. 72) : `hasKey?: [[iri]]` (une liste par axiome HasKey ; propriétés objet ou de données).

**B9 — compléments du contrat** (à ajouter à `OntoModel`) :
```js
meta: { iri, versionIRI?, versionInfo?, prefixes, label, comment, imports: [],
        annotations: [ { property: iri, value: iri|Literal } ] },
datatypes: { [iri]: { iri, label, comment, definition: DataRange } },        // DatatypeDefinition (SS §9.4)
generalAxioms: [ { kind: 'subClassOf'|'equivalentClasses'|'disjointClasses'|'disjointUnion'|'allDisjointClasses'
                        |'equivalentProperties'|'disjointProperties'|'gci',
                   args: [ClassExpr|iri] } ],
// classes[iri] : + disjointUnionOf?: [iri], complementOf?: iri
// objectProperties[iri] : + equivalentTo: [iri], disjointWith: [iri], inverseOf: [iri] (liste), deprecated?
// datatypeProperties[iri] : range: [DataRange], + equivalentTo, disjointWith, deprecated?
// annotationProperties[iri] : + subPropertyOf: [iri], domain: [iri], range: [iri]
individuals[id] : { iri | null, anonymous?: bool, label, types: [iri], facts: [...],
                    negativeFacts: [ { property, value, datatype?, lang? } ],
                    sameAs: [iri], differentFrom: [iri] },
allDifferent: [[iri]],
axiomAnnotations: [ { axiom: { s, p, o }, annotations: [ { property, value } ] } ],  // MAP §2.3.2 (owl:Axiom)
unmapped: [ { s, p, o } ]       // tout triplet non consommé par l'import : JAMAIS supprimé en silence (→ G01)
```
`Literal` = `{ lexical, datatype, lang? }` : la forme lexicale est conservée pour éviter les pertes de précision sur xsd:decimal (RCON §3.3).

## 3. Règles manquantes (B10) — lignes prêtes à coller

### 3.1 Règles de transposition (toutes exercées dans trap.ttl)
```
| C10 | `owl:disjointUnionOf` | review | Label parent + labels enfants, validation « exactement un enfant » | Un node type parent + discriminant obligatoire |
| C11 | `owl:complementOf` | lost | Label calculé par requête (`NOT`) ou documenté | Matérialisé à l'ingestion ou documenté |
| C12 | Punning classe/individu (même IRI, SS §5.9) | review | Node label + nœud de référence, noms distincts | Node type + nœud de référence, noms distincts |
| C13 | Axiome général d'inclusion (GCI : sujet anonyme de `rdfs:subClassOf`) | lost | Job de classification | Matérialisé à l'ingestion |
| K04 | Individu anonyme (nœud blanc, SS §5.6.2) | review | Clé générée (hash / IRI skolem `/.well-known/genid/`) | Idem |
| D08 | `owl:oneOf` sur datatype (DataOneOf) | review | Propriété + validation de valeurs | Propriété + validation / facette |
| D09 | Datatype défini / facettes (`owl:withRestrictions` : min/max, pattern, length) | review | Type de base natif + validation | Idem |
| D10 | Portée `rdfs:Literal` (ou absente) | review | String | string |
| D11 | `rdfs:subPropertyOf` entre propriétés de données | lost | Propriété la plus spécifique (option : dupliquer dans le parent) | Idem |
| D13 | Restriction sur propriété de données (some / only / cardinalité, `owl:onDataRange`) | review | Validation (`exactly 1` → propriété obligatoire) | Validation / propriété obligatoire |
| O14 | `ObjectInverseOf` anonyme (`[owl:inverseOf :p]` dans une restriction ou une chaîne) | review | Inverse nommé s'il existe, sinon traversée inverse | Reverse de l'edge |
| O15 | `owl:InverseFunctionalProperty` | review | Validation (≤ 1 relation entrante) | Validation |
| O16 | Cardinalité qualifiée (`owl:onClass`, `*QualifiedCardinality`) | review | Validation filtrée par label cible | Validation |
| O17 | `owl:hasSelf` | lost | Validation / booléen matérialisé | Booléen matérialisé |
| O18 | `owl:topObjectProperty` / `topDataProperty` en super-propriété | auto | Ignorer (documenté) | Ignorer |
| O19 | `owl:equivalentProperty` | review | Fusionner les types de relation (canonique + alias) | Idem |
| O20 | `owl:propertyDisjointWith` / `owl:AllDisjointProperties` | lost | Validation | Validation |
| A02 | Annotations d'axiome (`owl:Axiom`, MAP §2.3.2) | review | Rapport (option : propriété de provenance sur la relation) | Rapport |
| A03 | `owl:deprecated true` | auto | Exclure (option : garder avec drapeau) | Idem |
| M01 | En-tête d'ontologie (`owl:versionIRI`, `owl:versionInfo`, dcterms) | auto | Métadonnées du schéma / en-tête généré | Idem |
| M02 | `owl:imports` | review | Charger la fermeture hors-ligne (cache), sinon termes importés = références externes + constat | Idem |
| I02 | `owl:sameAs` | lost | Fusion des nœuds (clé canonique + alias) ; option relation SAME_AS | Fusion |
| I03 | `owl:differentFrom` / `owl:AllDifferent` | auto | Aucun effet (le LPG suppose l'UNA partout : renforcement à noter dans le rapport) | Idem |
| I04 | `owl:NegativePropertyAssertion` | lost | Validation (relation/valeur interdite) | Validation |
| I05 | Individu à plusieurs types | review | Multi-labels | Type principal + discriminant |
| G01 | Construct valide mais non représentable dans OntoModel (= toute entrée `unmapped` : ex. ClassAssertion d'une expression anonyme) | lost | Listé au rapport, jamais supprimé en silence | Idem |
```
Mettre à jour aussi **C07** : `| C07 | owl:disjointWith / owl:AllDisjointClasses | lost | Règle de validation | Validation (souvent garantie par le mono-typage Curiosity) |`.

### 3.2 Règles de conformité (L2, `conformance/lint.py`, pas de transposition)
Elles ne figurent pas dans trap.ttl, qui est OWL 2 DL par construction. Fixture à créer en L2 : `samples/trap/trap-nondl.ttl`.
```
| W01 | Datatype hors carte OWL 2 et non défini (xsd:date, gYear, duration, rdf:langString…) — SS §4, §5.2 | erreur DL |
| W02 | Entité utilisée sans déclaration / propriété non typée (`rdf:Property` seul) — SS §5.8, MAP §3.1 | erreur DL |
| W03 | Propriété non simple (transitive, chaîne, ou super-propriété/inverse de celles-ci) dans cardinalité, hasSelf, Functional, InverseFunctional, Irreflexive, Asymmetric, DisjointProperties — SS §11.2 | erreur DL |
| W04 | Punning entre types de propriétés (objet/données/annotation) ou classe/datatype — SS §5.9 | erreur DL |
| W05 | Caractéristique interdite sur propriété de données (InverseFunctional, Transitive, Symmetric) — SS §9.3 | erreur DL |
| W06 | Classe insatisfiable / incohérence (raisonneur) | erreur |
| W07 | Labels manquants fr/en, IRI d'ontologie sans versionIRI, préfixes non standard | avertissement |
```

## 4. Non-bloquants
- **C02/D01** : `rdfs:domain` ne « contraint » pas, il **infère** (RSEM rdfs2). La transposition en contrainte est un choix monde clos, à écrire une fois dans le rapport (§2.4) plutôt qu'à chaque constat.
- **C04** : sous OWA, l'absence d'instance directe ne se prouve pas. C'est une heuristique, à libeller « probablement abstraite ».
- **D04** : l'absence de `owl:FunctionalProperty` ne prouve pas la multivaluation. Recommander `scalar` si aucune valeur multiple n'est observée dans les individus/données et qu'aucun `max 1` n'existe, `list` sinon.
- **O06** : `*1..` ne compense que les requêtes, pas les contraintes. OK pour « lost », mais l'option Neo4j recommandée (`var_length_query`) devrait être notée « compensation complète en lecture ».
- **O13** : la réflexivité (globale) d'une propriété avec domaine rend **tout** individu instance du domaine. Ajouter dans la note : « souvent une erreur ; ne jamais matérialiser les boucles ».
- **K03** : distinguer « aucune clé, IRI disponible » (→ `uri`) et « nœud blanc » (→ K04).
- **N01** : détecter les **collisions** après normalisation (ex. classe `Warranty` / propriété `warranty` → `Warranty` en PascalCase Curiosity). Convention Curiosity « PascalCase partout » : À VÉRIFIER (expert curiosity).
- **PGModel** : `cardinality` limité à `0..1|0..*|1|1..*`. Ajouter `{min, max}` numériques pour O16 (`min 4`).
- **§6 Arborescence** : obsolète (prototype JS) face au PLAN (FastAPI). À aligner pour éviter la confusion des agents.
- **Outillage** : owlrl 7.1.2, règle `prp-key` (`OWLRL.py`, `range(0, len(pis) - 1)`) ignore la dernière propriété de clé. Avec `owl:hasKey (am:vin)`, tous les véhicules deviennent `owl:sameAs`. `conformance/reasoner.py` doit retirer les axiomes hasKey avant `DeductiveClosure` et implémenter prp-key lui-même. Constaté sur trap.ttl le 2 nov.
- **SHACL × inférence** : avec `-i rdfs`, `sh:closed` voit les super-propriétés entaillées (D11). Le validateur doit valider sans inférence par défaut, ou ajouter les super-propriétés aux `sh:ignoredProperties`. Démonstration dans trap-shapes.ttl.

## 5. Proposition (non bloquante) : identifiants d'options
`expected-findings.yaml` fixe un vocabulaire d'options (`multi_label`, `flatten_into_leaves`, `edge_pair`, `dereify_relationship`, `keep_node`, `validation`, `materialize_closure`, `var_length_query`, `node_key`, `key_concat`, `generated_key`, …). Le lead peut le reprendre tel quel dans `mapping/rules`, ou le renommer en le traçant dans `journal/decisions.md` et en me prévenant pour mettre l'oracle à jour.

## Bilan
36 règles d'origine + 30 ajoutées = **66 règles de transposition**, toutes exercées dans `samples/trap/trap.ttl` (OWL 2 DL, 895 triplets ; cohérent selon OWL RL, hors bug owlrl prp-key), plus 7 règles de conformité W01–W07 pour L2.
