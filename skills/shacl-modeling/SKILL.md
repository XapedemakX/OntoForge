---
name: shacl-modeling
description: Concevoir des shapes SHACL, choisir OWL vs SHACL, générer des shapes depuis une ontologie OWL, traduire des shapes en contraintes property graph (Neo4j natif vs validation applicative Curiosity) et valider avec pySHACL. À utiliser dès qu'il s'agit de contraintes de données, de qualité ou de passage ontologie → schéma de graphe.
---
# Modéliser avec SHACL

## OWL vs SHACL
- OWL infère (monde ouvert, pas de nom unique) ; SHACL valide (monde clos sur le graphe fourni). `someValuesFrom` OWL « déduit » une valeur manquante ; `sh:minCount 1` la réclame.
- Domaine/portée OWL ne contraignent pas : ils déduisent des types. Pour contraindre, utiliser `sh:class` / `sh:datatype`.
- SHACL est le plus proche d'un schéma de property graph : cardinalités, types, énumérations, clés.

## Concevoir des shapes
- Une `sh:NodeShape` par classe (`sh:targetClass`, ou shape = classe pour la cible implicite) ; une `sh:property` par propriété, avec `sh:path`.
- Toujours : `sh:minCount`/`sh:maxCount`, `sh:datatype` ou `sh:class`, `sh:message` en français, `sh:severity` (Warning pour le « souhaitable »).
- Valeurs : `sh:in`, `sh:pattern`, `sh:min/maxInclusive`, `sh:minLength`, `sh:languageIn`, `sh:uniqueLang`.
- Paires : `sh:equals`, `sh:disjoint`, `sh:lessThan(OrEquals)` (dates ouverture ≤ clôture).
- Logique : `sh:or` (propriétaire = Person ou Company), `sh:not`, `sh:xone`, `sh:and`.
- Cardinalité qualifiée : `sh:qualifiedValueShape` + `sh:qualifiedMinCount` (≥ 1 opération de type X).
- Chemins inverses `[sh:inversePath p]` pour contraindre les arêtes entrantes ; `sh:closed true` + `sh:ignoredProperties (rdf:type)` pour une forme fermée.
- Clés composites et unicité : non exprimables en Core → SHACL-SPARQL ou validation applicative.

## OWL → SHACL (`owl_to_shacl.generate_shapes`)
Retourne `(ShapesModel, notes)`. Chaque note est préfixée : `[OWA]` sens différent, `[RENFORCÉ]` plus strict que l'axiome (hasKey → minCount 1), `[PARTIEL]`, `[NON-CORE]` (unicité, transitivité, chaînes, self), `[HÉRITAGE]` (dépend de rdfs:subClassOf dans le graphe validé), `[IGNORÉ]`. Les afficher à l'humain pour arbitrage, jamais les taire.

## SHACL → property graph (`shacl_to_pg.shape_constraints`, `hints`)
| Contrainte SHACL | Neo4j natif | Curiosity |
|---|---|---|
| minCount 1 (propriété) | `IS NOT NULL` (Enterprise) | champ obligatoire à l'ingestion (connecteur) |
| clé / unicité | `IS UNIQUE` / `IS NODE KEY` | `[Key]` sur le node type |
| datatype | `IS :: TYPE` (5.x, Enterprise) | type du champ |
| maxCount 1 | propriété scalaire | champ scalaire (sinon liste) |
| sh:in, pattern, bornes, minCount sur relation, sh:class cible, or/xone/not, qualifié, closed, paires, SPARQL | validation applicative (requête Cypher de contrôle) | contrôle dans le connecteur |
Toujours présenter ce qui est perdu côté moteur (Curiosity n'a pas de contraintes déclaratives hors types/clés). Les syntaxes exactes de contraintes Neo4j sont à vérifier selon la version (`# À VÉRIFIER`).

## pySHACL
- `validate(data, shapes, onto=None, inference="none")` : défaut sans inférence. Avec `rdfs`/`owlrl`, les triplets déduits sont aussi validés.
- Piège `sh:closed` × super-propriétés : avec inférence RDFS, `rdfs:subPropertyOf` ajoute le triplet de la super-propriété, hors des propriétés déclarées → fausse violation de `ClosedConstraintComponent`. Valider sans inférence, ou lister la super-propriété dans `sh:ignoredProperties`.
- Autre piège : `rdfs:domain`/`range` inférés satisfont `sh:class`/`sh:targetClass` et masquent des erreurs de typage.
- `sh:targetClass` couvre les sous-classes seulement si `rdfs:subClassOf` figure dans le graphe (fournir `onto`).
- owlrl 7.1.2 : bug `owl:hasKey` (dernière propriété ignorée, faux `sameAs`). Retirer les hasKey avant fermeture.
- SHACL-SPARQL : conservé brut à l'import (warning), exécuté par pySHACL, à traduire en validation applicative côté PG.

## Pièges XSD (OWL → SHACL)
- `xsd:pattern` est implicitement ancré ; `sh:pattern` (REGEX SPARQL) cherche une sous-chaîne : générer `^(?:…)$`.
- `sh:datatype` ignore la hiérarchie des datatypes XSD (xsd:int rejeté pour xsd:integer, xsd:integer pour xsd:decimal) : générer `sh:or` des datatypes dérivés.
- length/minLength/maxLength comptent des octets pour hexBinary/base64Binary, des caractères pour `sh:minLength`.
