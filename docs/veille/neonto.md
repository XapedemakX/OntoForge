# Veille : neonto

Auteur : agent `veille`. Lot L21. Consulté le 7 nov. 2026.
Site : https://neonto.de/. Lecture faite par un outil de lecture de pages (le site refuse l'accès direct depuis notre environnement). La page « Editor » dédiée et le tarif n'ont pas pu être lus : voir « Limites ».

## Verdict en cinq lignes

- neonto est d'abord une société de conseil de Cologne (graphes de connaissances, ontologies, automatisation, IA), avec trois produits annexes : une formation, un éditeur de graphes et un outil de métriques de qualité.
- Cible : PME et équipes qui construisent un graphe de connaissances RDF/OWL/SHACL « prêt pour la production ».
- Technologie : l'écosystème W3C pur (RDFS, OWL, SHACL, SPARQL) plus le mapping RML/YARRRML. Pas de property graph annoncé.
- Recouvrement avec OntoForge : faible. Même vocabulaire, autre destination. neonto reste dans RDF. OntoForge traduit vers Neo4j et Curiosity.
- À reprendre : les métriques de qualité d'ontologie et l'idée de mappings lisibles. À éviter : l'éditeur généraliste « IDE de graphe ».

## Le produit

Faits relevés, avec source.

| Point | Constat | Source |
|---|---|---|
| Nature | Société de conseil à Cologne : graphes de connaissances, intégration de données, automatisation, IA | [accueil](https://neonto.de/) |
| Équipe | Deux cofondateurs (Achim Reiz, docteur-ingénieur, recherche sur les métriques d'ontologies ; Pascal Sommer, développeur) et un ingénieur IA et données | [This is us](https://neonto.de/this-is-us/) |
| Financement | Programme public allemand EXIST (ministère de l'Économie et du Climat, Fonds social européen) | [accueil](https://neonto.de/) |
| Offre conseil | Choix d'architecture, cas d'usage, mise en œuvre en RDFS, OWL, R2RML, SHACL, SPARQL, qualité des données | [services graphe](https://neonto.de/solutions/knowledge-graph-services/) |
| Formation (« academy ») | RDF, Turtle, SHACL, SPARQL, ingestion RML/YARRRML, dans un bac à sable interactif | même page |
| Éditeur | « Turn VS Code into a Knowledge Graph IDE » : édition Turtle et SPARQL, validation SHACL, raisonnement RDFS/OWL, mappings YARRRML/RML, sources CSV, XML, JSON, SQL, points d'accès SPARQL | même page |
| Modèle commercial de l'éditeur | « neonto edit » : éditeur pour PME, SaaS facturé par utilisateur. Accès par démonstration, pas de prix public | [fiche Gateway Uni Köln](https://www.gateway-unikoeln.de/en/startups/neonto) |
| Métriques | « neonto metrics » : mesure de la qualité d'un graphe avec des métriques établies, issu de la thèse d'Achim Reiz | même fiche |
| Publications | Deux billets : taxonomies SKOS (1er juin 2026) et ingestion RML/YARRRML (27 janv. 2026) | [blog](https://neonto.de/blog/) |
| Clients cités | TNO, marein.io, adorsys (témoignages) | [accueil](https://neonto.de/) |

Le billet sur l'ingestion décrit un flux en sept étapes : ontologie, inventaire des sources, mappings YARRRML, conversion RML, graphe RDF avec Morph-KGC, validation SHACL, CI/CD ([billet](https://neonto.de/blog/heterogeneous-data-ingestion-knowledge-graphs/)). Il présente l'éditeur neonto comme un outil visuel pour concevoir les mappings.

Piste de recherche : Achim Reiz a publié sur le choix de métriques d'ontologies ([ceur-ws.org Vol-3235](https://ceur-ws.org/Vol-3235/paper16.pdf), [SciTePress 2023](https://www.scitepress.org/Papers/2023/119838/119838.pdf)). Titres vus dans les résultats de recherche, articles non lus.

## Positionnement d'OntoForge

Les colonnes tierces s'appuient sur les sources citées plus bas. Les cases « non vérifié » sont à confirmer avant toute communication externe.

| Critère | OntoForge | neonto edit | Protégé / WebProtégé | TopBraid / TopQuadrant | neosemantics (n10s) | Curiosity |
|---|---|---|---|---|---|---|
| Rôle | Concevoir, analyser, arbitrer, générer | Éditer le graphe RDF et ses mappings | Éditer des ontologies OWL | Gouverner modèles et contexte d'entreprise | Importer et valider du RDF dans Neo4j | Plateforme graphe + recherche + IA |
| Modèle | OWL 2 + SHACL vers property graph | RDF, OWL, SHACL | OWL 2 complet | Ontologies, graphes (détail non lu) | RDF vers LPG | LPG typé, arêtes par paires |
| Cible property graph | Oui, cœur du produit | Non annoncé | Non | Non annoncé | Oui, import/export RDF | Cible native |
| Rapport de perte | Oui (auto, à arbitrer, perdu) | Non | Non | Non vu | Non (mapping paramétrable) | — |
| Éditeur OWL riche | Moyen (DSL, éditeur, graphe) | Oui (VS Code) | Oui, référence | Oui (non vérifié) | Non | Non |
| LLM | Assistant optionnel | Non annoncé | Non | Serveur MCP annoncé | Non | Agents intégrés |
| Distribution | Auto-hébergé, Docker | SaaS par utilisateur | Gratuit, open source | Commercial, démo | Open source (Apache 2.0), projet Labs | Commercial |

Sources de la table :

- Protégé : « Full support for the OWL 2 Web Ontology Language », gratuit et open source, version de bureau 5.6.9 la plus récente listée ([protege.stanford.edu](https://protege.stanford.edu/), [releases](https://github.com/protegeproject/protege/releases) ; l'année de 5.6.9 n'apparaît pas sur la page). WebProtégé : édition collaborative dans le navigateur, étiquettes 4.0.x vues dans le dépôt ([dépôt](https://github.com/protegeproject/webprotege)).
- TopQuadrant : la page d'accueil présente aujourd'hui « TQ Data Foundation » (modéliser, approuver, gouverner le sens ; contexte servi via MCP et SDK ; 200+ connecteurs ; démo, essai gratuit annoncé). Elle ne cite ni TopBraid EDG, ni SHACL, ni tarifs ([topquadrant.com](https://www.topquadrant.com/)). Le positionnement actuel ressemble à celui de NVIDIA Auto Ontology : contexte pour agents.
- n10s : projet Neo4j Labs, « experimental … not part of Neo4j's supported product lineup », Apache 2.0, import/export Turtle, N-Triples, JSON-LD, RDF/XML, TriG, N-Quads, RDF-star, OWL/SKOS/RDFS, validation SHACL, inférence basique, auto-hébergé seulement, pas dans Aura ([labs](https://neo4j.com/labs/neosemantics/), [GitHub](https://github.com/neo4j-labs/neosemantics)). Dernière étiquette vue : `2025.06.1` ; la page GitHub n'affiche aucune release.
- Curiosity : « graph + search + AI platform », graphe aux nœuds et arêtes typés, clés stables ([docs](https://docs.curiosity.ai/)).

### Ce qui distingue OntoForge

1. Il traite la perte de sémantique comme objet de travail : rien d'équivalent trouvé chez les cinq autres.
2. Il vise deux cibles property graph avec recommandations par cible.
3. Il se lance en un `docker compose up`, sans compte.

### Où OntoForge est plus faible

- Éditeur OWL moins complet que Protégé (axiomes complexes, plugins).
- Pas de mappings source vers graphe (idée P-27 dans `docs/IDEES.md`).
- Pas de mesure de qualité d'ontologie (idée P-33, lot L17).
- Pas d'édition collaborative (P-26).

## Idées à reprendre ou à éviter

| # | Idée | Décision | Gain | Effort | Pourquoi |
|---|---|---|---|---|---|
| E1 | Métriques de qualité d'ontologie (profondeur, classes sans label, couverture par shapes, ratio perdu/auto) | Reprendre | 3 | S | Rejoint P-33. neonto en fait un produit à part, preuve d'un besoin. S'appuyer sur la littérature d'Achim Reiz pour choisir les métriques. |
| E2 | Mappings lisibles en YAML (YARRRML pour RDF) pour l'ingestion | Reprendre l'idée, pas le format | 3 | M | Le connecteur généré par OntoForge est du C# ou du Cypher. Un mapping déclaratif relisible par un non-développeur aiderait la relecture. Voir P-27. |
| E3 | Formation intégrée (bac à sable guidé) | Reprendre en petit | 2 | S | La visite guidée existe déjà. Ajouter 3 exercices sur l'arbitrage. |
| E4 | Éditeur dans VS Code | Éviter | 1 | L | Champ occupé (Protégé, neonto). OntoForge gagne sur le dernier kilomètre, pas sur l'édition. |
| E5 | SaaS par utilisateur | Éviter pour l'instant | 1 | L | Contraire au fonctionnement actuel (poste de l'ingénieur, données client). À rediscuter avec Jerem si l'outil sort de l'ESN. |
| E6 | Import RDF avec mappage vers LPG à la n10s | Comparer | 3 | M | Comparer les décisions de n10s (paramétrage `n10s.graphconfig`) avec les nôtres, pour la documentation « OntoForge vs n10s ». À vérifier dans la doc n10s. |
| E7 | Contexte pour agents via MCP (TopQuadrant, NVIDIA) | Étudier | 3 | M | Deux acteurs convergent. Voir N6 dans la fiche NVIDIA. |

## Messages de positionnement

- Face à Protégé : « Protégé pour écrire l'ontologie, OntoForge pour savoir ce qu'on perd en la passant en graphe ». Les deux se complètent : OntoForge importe le Turtle et le RDF/XML de Protégé.
- Face à neonto : « neonto reste dans RDF ; OntoForge traduit vers Neo4j et Curiosity ». Pas de concurrence directe, partenaire possible pour la partie RDF.
- Face à n10s : « n10s charge du RDF dans Neo4j ; OntoForge décide comment le modèle doit devenir un graphe, puis génère le schéma ».
- Face à Curiosity : OntoForge produit le schéma et le connecteur, Curiosity fait tourner.

## Limites de cette fiche

- La page de l'éditeur (`/editor`) a répondu en erreur. Le lien de démonstration redirige vers un agenda en ligne que je n'ai pas ouvert.
- Le modèle SaaS par utilisateur vient d'une fiche de l'incubateur universitaire (Gateway), pas du site neonto. Aucun prix public trouvé.
- Aucune exécution de l'éditeur, aucun test.
- Je n'ai pas lu la documentation de TopBraid EDG ni de TopBraid Composer : la table ne les décrit pas.
- Les résultats de la recherche sur les articles d'Achim Reiz donnent des titres et liens, pas le contenu.

## Sources

1. neonto, accueil : https://neonto.de/ (7/11/2026)
2. neonto, services graphe de connaissances : https://neonto.de/solutions/knowledge-graph-services/
3. neonto, équipe : https://neonto.de/this-is-us/
4. neonto, blog : https://neonto.de/blog/ ; billet ingestion : https://neonto.de/blog/heterogeneous-data-ingestion-knowledge-graphs/
5. Gateway Uni Köln, fiche neonto : https://www.gateway-unikoeln.de/en/startups/neonto
6. Protégé : https://protege.stanford.edu/ ; https://github.com/protegeproject/protege/releases
7. TopQuadrant : https://www.topquadrant.com/
8. Neosemantics : https://neo4j.com/labs/neosemantics/ ; https://github.com/neo4j-labs/neosemantics
9. Curiosity : https://docs.curiosity.ai/
10. Reiz et al. : https://ceur-ws.org/Vol-3235/paper16.pdf ; https://www.scitepress.org/Papers/2023/119838/119838.pdf
