verdict: OK
bloquants:
  - aucun
non-bloquants:
  - [standards.json] Statuts vérifiés avec WebFetch sur https://neo4j.com/developer/kb/neo4j-supported-versions/ (la page support.neo4j.com est rendue en JavaScript et illisible) : 5.26 LTS sorti le 6/12/2024, correctifs jusqu'au 6/06/2028 ; 4.4 fin de support le 30/11/2025 ; les versions 5.x et calendaires n'ont de correctifs que jusqu'à la sortie de la suivante. Conforme à `end_of_support`, `obsolete` et `supported`. La copie lue s'arrête à 2026.07.1 : le statut de 2026.10 (« supportée, non LTS ») suit la règle de la page mais n'est pas lu tel quel.
  - [standards.json, cypher 25] « devient le défaut des nouvelles bases à partir de 2026.02 » contredit la page Cypher versioning lue le 8/11 (défaut = Cypher 5, « might change »). Corrigé : mention À VÉRIFIER ajoutée aux deux langues. Sans effet sur le code (le préfixe CYPHER 5 est posé explicitement sur base calendaire).
  - [targets/neo4j.py `_pfx`] Préfixe par requête correct dans schema, ingest et validation (test_neo4j_prefix_on_every_statement). CYPHER 25 devant CREATE CONSTRAINT / CREATE INDEX suit le principe « par requête » mais n'a pas pu être revérifié sur le manuel (page illisible) : À VÉRIFIER par Jerem (D-L21-03).
  - [préfixe sur 5.x] Omis sur 5.x : choix prudent (acceptation de CYPHER 5 par 5.26 non confirmée par la page lue). OK.
  - [4.4] Syntaxe `CREATE CONSTRAINT n IF NOT EXISTS ON (n:L) ASSERT n.p IS UNIQUE | IS NODE KEY | IS NOT NULL` et index `FOR` conformes à ma connaissance de 4.4 ; types et contraintes de relation non générés. Reste marqué À VÉRIFIER, à juste titre.
  - [5.26 contre 2026.x] Même syntaxe REQUIRE / IS :: ; seul le préfixe change. Seuils (5.7, 5.9, 5.10, 5.23) cohérents avec L21.
skill: neo4j-schema-design : le préfixe CYPHER vaut par requête ; la page de support Neo4j se lit sur neo4j.com/developer/kb/neo4j-supported-versions/.
Corrections faites : note Cypher 25 (standards.json). Gardes : build, l31_versions 12/12, e2e_ui 30/30, pytest.
