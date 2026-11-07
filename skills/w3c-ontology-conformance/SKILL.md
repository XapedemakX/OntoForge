---
name: w3c-ontology-conformance
description: Vérifier la conformité W3C d'une ontologie RDF/OWL 2 (syntaxe, OWL 2 DL et profils EL/QL/RL, datatypes, bonnes pratiques) et relire une règle de transposition OWL → property graph sous l'angle sémantique. À utiliser pour tout import/export RDF, tout lint d'ontologie, toute ontologie de test ou toute revue « est-ce que ce mapping dit vrai ? ».
---
# Conformité W3C des ontologies (premier jet, L0)

Références : OWL 2 Structural Specification (SS), Mapping to RDF Graphs (MAP), OWL 2 Profiles (PRO), Direct Semantics, RDF 1.1 Concepts (RCON), RDF 1.1 Semantics (RSEM), SHACL (W3C Rec. 2017). Toutes les URL sont sous https://www.w3.org/TR/ (`owl2-syntax`, `owl2-mapping-to-rdf`, `owl2-profiles`, `rdf11-concepts`, `rdf11-mt`, `shacl`).

## 1. Checklist RDF (RCON)
- [ ] Le fichier parse avec rdflib (`Graph().parse(path)`) sans avertissement. IRIs absolues, sans espace.
- [ ] Littéraux : la forme lexicale est valide pour le datatype (ex. `"0FB7A2"^^xsd:hexBinary`). Une balise de langue implique `rdf:langString` (RCON §3.3), jamais un datatype explicite.
- [ ] Préfixes standard (`owl rdf rdfs xsd skos dcterms`). Namespace de l'ontologie terminé par `#` ou `/`.

## 2. Checklist OWL 2 DL (SS §11 + MAP §3)
- [ ] Un en-tête `owl:Ontology` avec, de préférence, `owl:versionIRI` (SS §3.1-3.3) ; `owl:imports` résolus ou signalés (§3.4).
- [ ] **Chaque** IRI utilisée est déclarée (`owl:Class`, `owl:ObjectProperty`, `owl:DatatypeProperty`, `owl:AnnotationProperty`, `rdfs:Datatype`, `owl:NamedIndividual`), y compris `dcterms:*` et `skos:*` utilisés en annotation (SS §5.8).
- [ ] Datatypes : uniquement la **carte OWL 2** (SS §4) ou des datatypes définis (SS §9.4). Hors carte : `xsd:date`, `time`, `gYear`, `gYearMonth`, `gMonthDay`, `gDay`, `gMonth`, `duration`, `rdf:langString`. Dans la carte : `xsd:dateTime` et `dateTimeStamp`, la famille decimal/integer, `double`, `float`, `string` et ses dérivés, `boolean`, `hexBinary`, `base64Binary`, `anyURI`, `owl:real`, `owl:rational`, `rdf:PlainLiteral`, `rdf:XMLLiteral`, `rdfs:Literal`.
- [ ] Punning : classe/individu/propriété autorisé, **pas** objet/données/annotation entre elles, ni classe/datatype (SS §5.9).
- [ ] **Propriétés simples** (SS §11.2) : une propriété transitive, une propriété à chaîne, ou toute super-propriété ou inverse de celles-ci est *composite*. Elle est interdite dans les cardinalités (y compris qualifiées), `hasSelf`, Functional, InverseFunctional, Irreflexive, Asymmetric, DisjointObjectProperties.
- [ ] Propriété de données : ni InverseFunctional, ni Transitive, ni Symmetric (SS §9.3).
- [ ] Les chaînes de propriétés respectent la régularité (SS §11.2) : pas de cycle de sous-propriétés via les chaînes.
- [ ] Clés (SS §9.5) : elles ne s'appliquent qu'aux individus **nommés**. Elles n'imposent ni existence ni unicité.

## 3. Profils (PRO)
- **EL** : pas de `allValuesFrom`, de cardinalités, d'union, de complément, d'inverse, de propriété objet Functional ni InverseFunctional (FunctionalDataProperty autorisée) ; `oneOf` limité à un seul individu.
- **QL** : pas de `hasKey`, de chaînes, de transitivité, d'`hasValue` ni de cardinalité ; `someValuesFrom` en **sous-classe** seulement avec `owl:Thing` comme filler (en super-classe, filler classe nommée autorisé) ; pas d'union ni de `oneOf`.
- **RL** : en super-classe, pas de `someValuesFrom` ni d'union, et seulement `max 0/1` en cardinalité ; pas de propriété réflexive, de facettes de datatype ni d'`owl:real`.
- Un constat de profil cite le construct **et** l'IRI qui le porte (voir `samples/trap/expected-findings.yaml`, `profile_reasons`).

## 4. Pièges sémantiques pour la transposition vers un LPG
1. Plusieurs `rdfs:domain`/`rdfs:range` = **intersection** (RSEM rdfs2/rdfs3). Seul `owl:unionOf` exprime une union.
2. `rdfs:domain`/`range` infèrent des types, ils ne contraignent pas. Le LPG en fait des contraintes : c'est un choix monde clos à documenter.
3. OWA + absence d'UNA. Un `max 1` violé produit un `sameAs` inféré, pas une erreur, sauf avec `AllDifferent`. Le LPG suppose l'UNA partout : c'est un renforcement.
4. `owl:hasKey` → NODE KEY : ajoute l'existence. À arbitrer.
5. Une classe de réification ne se dé-réifie en relation que si elle a **2** rôles. Avec 3 rôles ou plus, c'est un pattern n-aire et elle reste un nœud.
6. La réflexivité globale rend tout individu instance du domaine : souvent une erreur de modélisation.
7. Une classe « abstraite » n'est jamais prouvable sous OWA : la règle reste heuristique.
8. `sh:closed` + inférence RDFS : les super-propriétés entaillées violent la forme fermée.
9. Une propriété devient **non simple par son inverse** : si `isPartOf` est transitive et inverse de `hasPart`, alors `hasPart` ne peut plus porter de cardinalité.
10. Validation SHACL : inférence `none` par défaut, RDFS seulement à la demande (voir 8).
11. `owl:hasKey` + OWL RL : outil (owlrl) bogué, voir §5.

## 5. Vérifier avec les outils
```python
import rdflib, owlrl, pyshacl
from owlrl.Namespaces import ERRNS
g = rdflib.Graph().parse("onto.ttl")
# OWL RL : incohérences = triplets ERRNS.error (et non owl:Nothing)
# ⚠ bug owlrl 7.1.2 prp-key : `range(0, len(pis) - 1)` ignore la dernière propriété de clé
#   → retirer les axiomes owl:hasKey avant DeductiveClosure.
g2 = rdflib.Graph(); g2 += g
for k in list(g2.triples((None, rdflib.OWL.hasKey, None))): g2.remove(k)
owlrl.DeductiveClosure(owlrl.OWLRL_Semantics).expand(g2)
errors = [str(o) for o in g2.objects(None, ERRNS.error)]
conforms, report, text = pyshacl.validate("data.ttl", shacl_graph="shapes.ttl", inference="none")
```
- Contrôles DL statiques (déclarations, carte de datatypes, propriétés simples, punning) : à coder dans `conformance/profiles.py`. Prototype de référence dans la revue L0.
- Satisfiabilité / DL complète : HermiT (Java, optionnel). À VÉRIFIER : intégration via owlready2 (`sync_reasoner`) dans l'image Docker.
- Toujours tester contre `samples/trap/trap.ttl` (66 règles, OWL 2 DL) et `expected-findings.yaml`.

## 6. Bonnes pratiques
- `rdfs:label` en fr **et** en en sur chaque entité ; `skos:definition` pour les classes cœur.
- Réutilisation : SKOS (labels, schémas de concepts), dcterms (métadonnées), PROV-O (provenance), OWL-Time (attention : `time:inXSDgYear` sort de la carte DL).
- Nommage : classes en `PascalCase`, propriétés en `camelCase`, pas de `_`. Vérifier les collisions après normalisation vers la cible.

## 7. Import/export RDF : pièges
- **rdf:Property non typée** : typer par la portée (littéral/datatype → DatatypeProperty, classe → ObjectProperty) et avertir ; sinon `unmapped`.
- **Plusieurs rdfs:domain/range = intersection** (RDFS rdfs2/rdfs3), jamais une union ; l'union n'existe que via `owl:unionOf`. Le DSL, lui, lit « même propriété sur plusieurs classes » comme une union (intention de l'utilisateur) et l'exporte en `unionOf`.
- **Listes RDF** (`rdf:first/rest`) : l'ordre est significatif pour les chaînes (`propertyChainAxiom`) et `hasKey`; ne pas trier ces listes dans la normalisation.
- **xsd:decimal** : rdflib/Turtle réécrit `"0"^^xsd:decimal` en `0.0` ; normaliser la forme lexicale à l'import, sinon le round-trip diverge. `xsd:string` explicite = littéral simple en RDF 1.1 (JSON-LD le replie) : les confondre à l'import.
- **Préfixes** : rdf/rdfs/owl/xsd sont toujours liés par l'export, ne pas les mémoriser comme préfixes de l'utilisateur (sinon round-trip instable). Les descriptions de `unmapped` ne doivent pas dépendre des préfixes du fichier.
- **RDF/XML** : rdflib émet des avertissements pour les nœuds de liste (`Assertions on BNode … ignored`) mais le résultat est correct ; IRIs avec espace (« Euro 5 ») invalides, à signaler.
- **Annotations d'axiome** (`owl:Axiom`, `owl:annotatedSource`…) et GCI (sujet anonyme avec `subClassOf`) : hors OntoModel → `unmapped`, réémis tels quels à l'export, jamais perdus.
- **Punning** (classe + individu) licite en OWL 2 DL (SS §5.9) mais signalé ; classe + propriété ne l'est pas.
- **Datatypes** : xsd:date/gYear/duration hors carte OWL 2 DL ; l'exemple AutoMaint utilise xsd:dateTime ou un datatype défini (`am:ModelYear`).

## 7. Conformité (implémentation `backend/ontoforge/conformance/`, lot L2)
- `check_conformance(onto, graph=None, run_reasoner=True, hermit=False)` → `ConformanceReport` (`profiles` DL/EL/QL/RL/RDFS, `profile_violations`, `issues`, `reasoner`). Travaille sur le **graphe RDF** (déclarations, punning, littéraux typés ne sont pas dans `OntoModel`) ; sans graphe, il est reconstruit par `rdf_export`.
- Codes : W01 datatype hors carte OWL 2 (SS §4) ; W02 déclaration manquante / `rdf:Property` seul (SS §5.8, MAP §3.1) ; W03 propriété non simple dans cardinalité, hasSelf, Functional, InverseFunctional, Asymmetric, Irreflexive, disjonction (SS §11.2) ; W04 punning interdit (SS §5.9) ; W05 caractéristique interdite sur propriété de données (SS §9.3) ; W06 classe insatisfiable / incohérence ; W07 labels fr/en, versionIRI, préfixes. BP01–BP07 : orphelines, sans domaine/portée, cycles, labels dupliqués, imports non résolus, parent déprécié, nommage.
- W01 est un **warning** pour une valeur d'annotation hors carte (`dcterms:created "2020-01-01"^^xsd:date`), une **erreur** ailleurs.
- Propriétés non simples : point fixe sur transitives + chaînes, propagé aux super-propriétés, équivalentes et inverses.
- Profils : un profil implique DL (sous-ensemble syntaxique). `DisjointUnion` est classé hors des trois profils — À VÉRIFIER contre PROF §2.3/§3.3/§4.2. L'RDFS est « vrai » si aucune construction OWL au-delà des déclarations.
- Raisonneur : OWL RL (`owlrl`), `hasKey` retiré avant `DeductiveClosure` puis `prp-key` appliqué par OntoForge (bug owlrl 7.1.2). Insatisfiabilité = heuristique RL (⊑ Nothing, ancêtres disjoints ou complémentaires) ; pas de raisonnement sur les restrictions : HermiT (owlready2, sous-processus, 30 s) est optionnel et ses échecs ne sont que des notes.
- Pièges de test : `trap.ttl` doit rester DL=vrai et 0 erreur ; `trap-nondl.ttl` doit déclencher W01–W07 (un test par code).
- Profils, rappels vérifiés en revue it1 (PROF §2.2, §3.2, §4.2) : DataRange EL = Datatype, DataIntersectionOf, DataOneOf à 1 littéral ; QL et RL = Datatype, DataIntersectionOf (DataUnionOf/ComplementOf interdits partout). DatatypeDefinition admis dans les 3 profils (seule sa portée compte : facettes interdites). Assertions négatives : EL oui, RL oui, QL non. FunctionalDataProperty : EL oui, QL non. RL : owl:Thing interdit en sous-classe comme en super-classe ; DisjointUnion hors des 3 profils. QL : DataSomeValuesFrom en sous-classe seulement avec rdfs:Literal. Littéral mal typé (`"abc"^^xsd:integer`) = erreur W01. xsd:float et xsd:double ont des espaces de valeurs disjoints (SS §4.1) : élargissement float→double à noter dans les cartes de types PG.

## 8. Checklists issues des revues L9 et L15
- **§11.2 sur toute ClassExpr, imbriquée comprise** (SS §11.2, §8.3) : parcourir récursivement `and`/`or`/`not`/restrictions ; une cardinalité, `hasSelf` ou une propriété fonctionnelle/irréflexive/asymétrique portant sur une propriété non simple est interdite à n'importe quelle profondeur, pas seulement au premier niveau.
- **Suppression = axiome entier** (SS §8.1, §8.2) : retirer un opérande d'une expression n-aire (intersection, union, oneOf, listes d'équivalence ou de disjonction) change le sens ; si moins de 2 opérandes restent, supprimer l'axiome et non l'opérande.
- **Vocabulaire réservé refusé comme IRI d'entité** (SS §5.2, §5.8 ; MAP §3.1) : aucune classe, propriété ou individu dans les espaces rdf:, rdfs:, owl:, xsd: hors termes définis par la spécification.
- **Entrées d'un LLM validées strictement** : IRI conformes à RFC 3987 (RDF 1.1 Concepts §3.2), sans espace ni `<>"{}|\^`` ; étiquettes de langue BCP47 (RDF 1.1 Concepts §3.3, RFC 5646) ; datatypes dans la carte OWL 2 (SS §4) et formes lexicales valides (§5.7).
- **SPARQL généré** (SPARQL 1.1 Query §4.1.1, §6, §17) : déclarer PREFIX pour tous les termes, rdf et rdfs inclus ; OPTIONAL imbriqués avec leurs FILTER et étapes dépendantes dans leur propre groupe ; négation par NOT EXISTS ; IRIREF et langtag validés ; dates comparées en xsd:dateTime.
- **Vérification du SPARQL** : utiliser rdflib `translateQuery` avec `initNs={}` et non le seul parseur, car rdflib prédéfinit rdf, rdfs et xsd et masque l'oubli de PREFIX.
