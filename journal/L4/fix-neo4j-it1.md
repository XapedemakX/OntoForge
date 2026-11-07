# Réponse à la revue curiosity (neo4j, it1 -> it2)

Bloquants
1. Type sans clé / motif vide : corrigé. `_Model.key()` replie sur la propriété IRI, puis sur une propriété unique+required ; `node_pattern()` renvoie `None` sans clé et n'émet jamais de `{}`. Une relation dont une extrémité n'a aucune clé est commentée (« À COMPLÉTER : relation non ingérée »). Le nœud est ingéré par `MERGE` sur la clé de repli (aligné sur la contrainte UNIQUE) ; seul un type sans aucune clé reste en `CREATE` avec ATTENTION. Tests : `test_keyless_type_uses_iri_property_as_fallback_key` (Uri / iri_x / URI sans marqueur), `test_never_empty_pattern_and_incomplete_relation_commented`.
2. Nom `uri` codé en dur : corrigé. `iri_name()` = propriété `source == "urn:ontoforge:iri"` (D-L4-02), repli insensible à la casse sur `uri`. Utilisé pour la clé de repli, `AS uri` des validations (sinon `null AS uri` explicite), hasValue et le contrôle symétrique. Test `test_uri_null_when_no_iri_property`.

Non-bloquants
- `Materialization.chain` = noms d'EdgeType (fixture déjà conforme) ; repli défensif : un élément qui est l'`source` d'un EdgeType non dérivé est résolu vers son nom. Test dédié.
- V06 (disjoint) : généré en vraie requête (`WHERE n:A OR n:B`) quand `params.with/targets` est renseigné ; sinon patron commenté. V09/V13 : requêtes réelles déjà générées quand les paramètres existent (pattern -> `=~`), patron seulement sans paramètre exploitable.
- Pertes de schema.cypher : `sujet : <nom court> <IRI complète>` ajoutés.
- Index : commentaire d'origine (« propriété marquée indexed », source) ajouté.
- Écarts d'oracle (C09, D05, O13) : déjà documentés dans rapport-neo4j.md ; à porter par `ctx` côté moteur.

Fixture : propriétés `uri` marquées `urn:ontoforge:iri`. Tests : 198 verts hors `test_target_curiosity.py`, qui ne compile pas (SyntaxError ligne 551 de targets/curiosity.py, fichier de l'agent curiosity).

## it2 : revue W3C
- `profiles/neo4j.py:132` : `rdf:langString` passe à `owl2=False` (hors carte OWL 2, W01) ; mapping de tolérance (String, perte signalée) conservé ; `rdf:PlainLiteral` reste `owl2=True`. Test `test_langstring_not_owl2_but_tolerated`.
- Non-bloquant GraphQL Int 32 bits : sans objet côté Neo4j (INTEGER = 64 bits, documenté dans le profil) ; aucun exemple GraphQL généré ici.
