---
name: owl-to-property-graph
description: Méthode de transposition d'une ontologie OWL 2 / RDFS (+ shapes SHACL) en modèle property graph prêt à l'emploi (Curiosity, Neo4j, LPG générique). À utiliser pour concevoir ou relire un mapping ontologie → graphe, classer chaque axiome en transposition triviale / perte possible / perte certaine, choisir une option par cible, générer les validations et matérialisations de compensation, et rédiger le rapport de transposition. Couvre le catalogue de 66 règles d'OntoForge, les arbres de décision par cible et les pièges sémantiques (monde ouvert, intersection des domaines, hasKey, propriétés non simples, nœuds blancs).
---

# OWL 2 / SHACL → Labeled Property Graph

Référence d'implémentation : `backend/ontoforge/mapping/` (moteur), `docs/RULES.md` (catalogue complet),
`samples/trap/` (ontologie piège + oracle `expected-findings.yaml`). Ce skill condense la méthode pour qu'un humain
ou un agent puisse la refaire sans l'outil.

## 1. Principe : OWL infère, le LPG contraint

| | OWL 2 / RDFS | Property graph |
|---|---|---|
| Hypothèse | monde ouvert (OWA), pas d'UNA | monde clos, UNA (une clé = un nœud) |
| Axiome | produit des inférences | devient une contrainte, une validation, une requête ou rien |
| Identité | IRI | clé métier locale (+ `uri`) |
| Typage | multiple, inféré | labels figés (Neo4j : N labels ; Curiosity : un type) |
| Relation | propriété binaire hiérarchisable | type d'arête plat (propriétés : Neo4j oui, Curiosity non) |

Conséquence : chaque axiome tombe dans l'une de trois catégories, et seules les deux dernières sont arbitrées par un humain.
- auto : correspondance directe (classe → type, propriété fonctionnelle → scalaire, inverse → paire d'arêtes).
- review : la transposition existe mais change la sémantique (héritage aplati, hasKey → clé, union → duplication).
- lost : aucun équivalent ; sans compensation, la sémantique disparaît (transitivité, chaîne, classe définie,
  disjonction, only, complément, GCI, sameAs, assertions négatives).

Transposer `rdfs:domain`, `only`, `some`, `hasKey` en contrainte est un renforcement (monde clos). On le dit une
fois dans le rapport, pas à chaque constat.

## 2. Méthode (7 étapes)

1. Charger sans perte : tout triplet non structuré (expression anonyme, DataRange à facettes, owl:Axiom, ClassAssertion
   d'une expression) est conservé et relu ; ce qu'aucune règle n'explique devient un constat G01. *Aucune perte silencieuse.*
2. Décider la disposition des classes avant tout le reste : type propre, replié dans un ancêtre concret
   (discriminant `<racine>Kind`), abstrait (label secondaire / fusionné dans les feuilles), alias (équivalence),
   calculé (classe définie, complément, GCI), dé-réifié (relation porteuse), exclu (déprécié).
3. Placer les propriétés de données sur les types où vivent les instances du domaine (une classe abstraite
   fusionnée → ses sous-types ; une sous-classe repliée → sa racine). Typer via la carte xsd de la cible.
4. Clés : `uri` sur chaque type (source `urn:ontoforge:iri`), clé par défaut ; hasKey → clé métier seulement
   par arbitrage (renforcement).
5. Relations : extrémités = domaine × portée résolus (union → une arête par paire ; plusieurs domaines →
   intersection ; absents → restrictions, shapes, assertions, inverse). Curiosity : `reverse` toujours renseigné.
6. Compensations : restrictions → validations ; transitivité / chaînes / super-propriétés / classes définies →
   matérialisations ou requêtes ; shapes SHACL → obligatoire, scalaire, enum, motif, cardinalités.
7. Nommer et vérifier : conventions de la cible, collisions après normalisation insensible à la casse, aucune arête
   vers un type inexistant, ids de constats stables pour rejouer les arbitrages.

## 3. Catalogue condensé (66 règles ; ids d'options normatifs)

| Famille | Règles (sévérité) → reco Curiosity / Neo4j |
|---|---|
| Classes | C01 classe (auto) → `node_type`/`label` · C02 sous-classe (review) → `flatten_into_leaves`/`multi_label` · C03 héritage multiple (review) → `primary_parent_discriminator`/`multi_label` · C04 probablement abstraite (review) → `merge_into_leaves`/`secondary_label` · C05 équivalence nommée (review) → `merge_types` · C06 classe définie (lost) → `materialize_at_ingest`/`computed_label` · C07 disjonction (lost) → `validation` · C08 oneOf (review) → `reference_nodes` · C09 union/intersection anonyme (lost) → `doc_only`/`secondary_label` (couverture : `doc_only`) · C10 disjointUnion (review) → `primary_parent_discriminator`/`multi_label` · C11 complément (lost) → `materialize_at_ingest`/`computed_label` · C12 punning (review) → `reference_nodes` · C13 GCI (lost) → `materialize_at_ingest`/`computed_label` |
| Clés | K01 IRI (auto) → `uri_key`/`unique_constraint` · K02 hasKey données (review) → `uri_key`/`node_key` · K03 sans clé (review) → `uri_key` (nœuds blancs : `generated_key`) · K04 individu anonyme (review) → `generated_key` · K05 hasKey avec propriété objet (review) → `key_concat`/`materialize_key` |
| Données | D01 domaine unique (auto) → `property` · D02 sans domaine (review) → `attach_to_users` · D03 domaine unionOf (review) → `duplicate_per_type` · D04 non fonctionnelle (review) → `scalar` sauf valeurs multiples observées → `list_property` · D05 type avec perte (review) → `native_type` (binaire : `string_lexical`) · D06 multilingue (review) → `per_language_property` · D07 fonctionnelle (auto) → `scalar` · D08 DataOneOf (review) → `enum_property` · D09 facettes (review) → `validation` · D10 rdfs:Literal (review) → `string_property` · D11 sous-propriété (lost) → `most_specific_type` · D12 plusieurs domaines/portées (review) → `native_type` (domaines : `intersection_domain`) · D13 restriction données (review) → `validation` |
| Objets | O01 domaine/portée uniques (auto) → `edge_pair`/`relationship` · O02 sans domaine/portée (review) → résoudre · O03 unionOf (review) → `edge_pair`/`relationship` · O04 inverse (auto) → `edge_pair`/`single_direction` · O05 symétrique (review) → `self_reverse`/`undirected_query` · O06 transitive (lost) → `materialize_closure`/`var_length_query` · O07 sous-propriété (lost) → `most_specific_type` · O08 chaîne (lost) → `materialize_closure`/`path_query` · O09 max 1 (review) · O10 some/min (review) · O11 only (lost) · O12 hasValue (review) · O13 réflexive/irréflexive/asymétrique (lost ; réflexive seule : `ignore`) · O15 inverse-fonctionnelle (review) · O16 qualifiée (review) · O20 disjointes (lost) → `validation` · O14 inverse anonyme (review) → `reverse_traversal` · O17 hasSelf (lost) → `materialize_at_ingest`/`validation` · O18 topObjectProperty (auto) → `ignore` · O19 équivalentes (review) → `merge_relationship_types` · O21 plusieurs domaines/portées (review) → `intersection_domain` |
| Réification | R01 binaire : 2 rôles fonctionnels + données (review) → `keep_node`/`dereify_relationship` · R02 n-aire ≥ 3 rôles (review) → `keep_node` |
| Annotations, méta | A01 annotations (auto) → `schema_metadata` · A02 annotation d'axiome (review) → `report` · A03 dépréciée (auto) → `exclude` · M01 en-tête (auto) → `schema_metadata` · M02 imports (review) → `external_reference` · G01 non représentable (lost) → `report` |
| Individus | I01 individu (review) → `reference_nodes` (exemples : `ignore`) · I02 sameAs (lost) → `merge_nodes` · I03 différence / AllDifferent (auto) → `noop_una` · I04 assertion négative (lost) → `validation` · I05 multi-typé (review) → `primary_parent_discriminator`/`multi_label` |
| Nommage | N01 hors convention / collision (auto) → `rename` |

Ids de constats (D-035) : `<règle>:<IRI sujet>` + `:<IRI propriété>` pour une restriction + `:<sha1[:8]>` pour un
construct anonyme. Sans id stable, aucun arbitrage ne peut être rejoué après modification de l'ontologie.

## 4. Arbres de décision par cible

### Curiosity (mono-type, clé string unique, arêtes en paires sans propriétés)
- Héritage → aplatir : une racine concrète par hiérarchie, sous-types repliés avec discriminant `<Racine>Kind`
  (enum, facette) ; parent abstrait → fusionné dans les feuilles ; héritage multiple → parent principal (le plus riche)
  + booléens `Is<AutreParent>`.
- Classe définie / complément / GCI → booléen `Is<Classe>` calculé par le connecteur.
- Réification → toujours un nœud (les arêtes ne portent rien).
- Inverse → paire native (`HasPart`/`PartOf`) ; symétrique → l'arête est son propre retour ; sinon retour dérivé
  (`X` → `XInverse`, à renommer).
- Clé : `[Key] Uri` par défaut ; hasKey → validation d'unicité (ou `[Key]` = propriété si l'humain accepte le
  renforcement) ; composite → concaténation `a|b`.
- Transitivité, chaînes → arêtes dérivées matérialisées (pas de chemin variable documenté, À VÉRIFIER).
- Nommage PascalCase partout ; un nom d'arête ne doit pas égaler un nom de type (`warranty` → `HasWarranty`).

### Neo4j (multi-labels, propriétés de relation, contraintes sur nœuds seulement)
- Héritage → multi-labels (label propre + ancêtres) ; abstraite → label secondaire (type abstrait).
- Classe définie → label calculé par un job de classification rejoué après ingestion.
- Réification binaire → relation porteuse de propriétés ; n-aire → nœud.
- Inverse → un seul sens stocké, l'autre traversé ; symétrique → requêtes non orientées.
- Transitive → `-[:T*1..]->` (compensation complète en lecture seulement) ; chaîne → requête de chemin.
- hasKey → NODE KEY (Enterprise ; UNIQUE en Community) après arbitrage ; composite avec objet → recopier la clé de
  la cible (`manufacturerKey`).
- Cardinalités de relation, only, disjonctions → requêtes de validation (aucune contrainte native).
- Nommage : `PascalCase` labels, `UPPER_SNAKE` relations, `camelCase` propriétés.

### LPG générique (GQL / PG-Schema, Memgraph, Neptune openCypher)
- Si multi-labels et propriétés de relation : suivre Neo4j ; sinon suivre Curiosity.
- Ne jamais supposer de contrainte de cardinalité de relation ni de raisonneur : tout `some/only/max` devient validation.

## 5. Pièges sémantiques (à vérifier sur toute ontologie)

1. OWA : l'absence d'instance directe, de valeur multiple ou de `FunctionalProperty` ne prouve rien → C04 et D04
   sont des heuristiques, à confirmer.
2. Domaines multiples = intersection (RSEM rdfs2/rdfs3) : deux `rdfs:domain` ≠ union. Seul `[owl:unionOf (…)]`
   autorise la duplication. Souvent une erreur de modélisation : arbitrer.
3. hasKey ≠ clé de base (SS §9.5) : il infère `sameAs` entre individus *nommés* de mêmes valeurs, n'impose ni
   existence ni unicité. NODE KEY / `[Key]` = renforcement à faire valider. owlrl 7.1.2 `prp-key` ignore la dernière
   propriété de clé (tous les véhicules `sameAs`) : retirer hasKey avant la clôture.
4. Propriétés non simples (transitive, chaîne, leurs super-propriétés et inverses, SS §11.2) : aucune cardinalité,
   ni fonctionnalité, ni irréflexivité ne doit être générée dessus.
5. only ≠ sh:class et domain ≠ sh:targetSubjectsOf + sh:class : OWL infère le type, SHACL le vérifie.
6. Nœuds blancs : pas d'IRI → clé générée (hash / skolem `/.well-known/genid/`), jamais K01.
7. n-aire : une relation relie deux nœuds ; ≥ 3 rôles → nœud (pattern W3C SWBP).
8. Réflexivité globale : rend tout individu instance du domaine ; ne jamais matérialiser les boucles.
9. Datatypes hors carte OWL 2 (xsd:date, gYear, duration, rdf:langString) : signaler en conformité (W01) puis typer.
10. sh:closed × inférence : valider sans inférence, ou lister les super-propriétés dans `sh:ignoredProperties`.
11. Complément / négation : monde ouvert → négation par défaut en monde clos (sur-classification possible).
12. Chaîne = inclusion ordonnée (`p ∘ q ⊑ r`), jamais ≡ : ne jamais trier ni dédoublonner la chaîne ; `r` garde
    ses assertions directes.
13. domain(A ⊓ B) ⇒ domaine de chaque conjoint (inférence correcte) ; toute autre expression complexe → constat.
14. Restriction d'une sous-classe aplatie ⇒ validation filtrée par discriminant, jamais `required`, cardinalité
    d'arête ni clé sur le type racine.
15. sameAs / UNA : le LPG suppose l'UNA ; fusionner explicitement (clé canonique + alias).

## 6. SHACL d'abord quand il existe

Les shapes décrivent le contrat de données, plus proche d'un schéma LPG : `minCount ≥ 1` → obligatoire ; `maxCount 1`
→ scalaire ; `sh:in` → enum ; `sh:pattern` → motif (comparer aux facettes OWL sans `^…$`) ; `sh:datatype` → type ;
`sh:class`/`sh:or` → validation de cible ; `inversePath` → cardinalité entrante ; `qualifiedValueShape` → validation
qualifiée ; `lessThan` → validation. Conflit OWL/SHACL (maxCount > 1 sur fonctionnelle, types incompatibles) →
constat à arbitrer, priorité recommandée aux shapes.

## 7. Gabarit de rapport de transposition

```markdown
# Rapport de transposition — <ontologie> → <cible>
## Synthèse            (constats auto / review / lost ; arbitrés / non arbitrés ; nb types, relations, validations)
> Hypothèse de monde clos (rappelée une fois).
## Types de nœuds      | Type | Labels | Clé | Propriétés (`*` obligatoire, `[]` liste) | Classes OWL sources |
## Relations           | Relation | De | Vers | Retour | Cardinalité | Propriétés | Source | Note |
## Ce qui est perdu ou à risque
### Perdu — n          | Règle | Sujet | Constat | Option retenue (« non arbitré, recommandé ») | Impact | Compensation |
### À risque — n       (idem)
## Transposé automatiquement (compte par règle)
## Validations à implémenter | Id | Type | Cible | Description | Origine |
## Matérialisations          | Type | Cible | Description | Origine |
## Arbitrages                (décisions, décisions orphelines conservées)
```

## 8. Contrôle qualité

- Toutes les entités de l'ontologie apparaissent dans un constat ou une `source` du modèle (aucune perte silencieuse).
- Aucune relation vers un type inexistant ; noms uniques ; Curiosity : un label, pas de propriétés d'arête, `reverse`
  renseigné ; Neo4j : labels = types existants.
- Même entrée → même sortie (tri) ; accepter toutes les recommandations ne change pas le modèle.
- Oracle de non-régression : `samples/trap/expected-findings.yaml` (79 constats + 6 `must_not`), test
  `backend/tests/test_mapping_oracle.py`.
