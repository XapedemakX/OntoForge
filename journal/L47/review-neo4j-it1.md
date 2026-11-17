verdict: OK
bloquants:
non-bloquants:
  - Pour Neo4j les validations D13 / O09 / O10 / D09 sont des requêtes Cypher de détection ; les IS NOT NULL sont commentés (section Enterprise de schema.cypher) : rien ne bloque l'ingestion, donc le reclassement en auto ne cache pas de choix bloquant. Les constats lost restent humains (4 sur automaint : C07 x3, O06 ; mesure 15 review + 4 lost = 19 vérifiée).
  - [catalog.py:43-45] Le motif « ne fait que perdre la contrainte » est inexact en Enterprise : D13 `exactly 1` / O10 ont un équivalent natif (IS NOT NULL) pour les propriétés. À nuancer (« validation Cypher ; contrainte IS NOT NULL en Enterprise, à décommenter »), idéalement par cible.
  - Même réserve de fond que curiosity sur O10 / D13 `some` (renforcement du monde ouvert) : sans effet bloquant côté Neo4j, mais à dire dans le motif ou le dossier.
  - K02 laissé en review : d'accord (NODE KEY vs UNIQUE vs uri_key est un vrai choix, y compris selon l'édition). Règles à option unique non reclassées : d'accord.
  - Oracle trap : écarts f-D09a/b, f-D13, f-O09a/b, f-O10/O10b justifiés pour neo4j ; la note f-D13 (IS NOT NULL Enterprise sinon validation) reste vraie.
skill: neo4j-schema-design : rien (si ce n'est : « sans choix » n'efface pas la différence Community / Enterprise).
