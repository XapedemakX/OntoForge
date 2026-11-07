# Revue croisée L4 it2 — relecteur curiosity, cible relue : neo4j

verdict: OK

Vérifié : generate() relancé sur pg_curiosity_automaint.json et pg_neo4j_automaint.json (10 fichiers, sorties dans le scratchpad) ; 96 tests verts
(profils + cibles neo4j et curiosity, ce dernier compile de nouveau).

bloquants: (aucun)
  - [corrigé] motif vide / type sans clé : VehicleModel est ingéré par `MERGE (n:VehicleModel {Uri: row.Uri})` (aligné sur la contrainte UNIQUE) et les 3 relations
    (AffectsModel, MadeBy, OfModel) apparient `{Uri: row.to.Uri}` ; plus aucun `{}` dans ingest.cypher.
  - [corrigé] nom de la propriété IRI : `n.uri AS uri` n'est plus émis que sur les types qui portent la propriété (15 sur la fixture Neo4j) ; `null AS uri` explicite ailleurs.

non-bloquants:
  - Fixture pg_curiosity_automaint.json (propriétaire : curiosity) non conforme à D-L4-02 : `Materialization.chain` y contient encore l'IRI isPartOf, donc M01 reste un
    no-op sur cette fixture (la résolution défensive ne trouve pas d'EdgeType non dérivé de source isPartOf) ; la propriété `Uri` n'y porte pas `source=urn:ontoforge:iri`.
    Je corrige la fixture côté curiosity (chain -> noms d'edges, marqueur IRI) ; aucune action pour neo4j. Sur pg_neo4j_automaint, M01 produit bien `MATCH (a:Part)-[:PART_OF*1..]->(b:Part)`.
  - `a.uri AS uri` subsiste dans le contrôle symétrique pour la fixture Curiosity (type sans marqueur) : sans effet tant que le marqueur manque ; disparaîtra avec la correction de fixture.
  - Écarts d'oracle O13a / D05b / C09b : identiques des deux profils, tracés dans rapport-neo4j.md ; à porter par ctx côté moteur (inchangé).
  - Pertes (schema.cypher section 6), commentaire d'origine de l'index et V06/V09/V13 : traités comme annoncé dans fix-neo4j-it1.md.

skill: rien de plus que l'it1 (clé de repli IRI, convention chain en noms d'edges, tableau des écarts justifiés).
