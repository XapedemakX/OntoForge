# Veille : NVIDIA Auto Ontology

Auteur : agent `veille`. Lot L21. Consulté le 7 nov. 2026.
Dépôt : https://github.com/NVIDIA/auto-ontology. Code lu sur un clone local (partiel, 50 derniers commits) : fichiers `README.md`, `AGENTS.md`, `pyproject.toml`, `auto_ontology/semantic/*`, `auto_ontology/server/model_interchange/*`.

## Verdict en cinq lignes

- Ce n'est pas un extracteur d'ontologie depuis des documents. Il part de bases relationnelles (schémas, colonnes, valeurs échantillonnées) pour construire une couche sémantique destinée à du text-to-SQL.
- Aucun OWL, RDF, SHACL ni SPARQL dans le code. Le mot « ontology » désigne un catalogue de termes métier, de relations de jointure et d'attributs SQL stocké dans Postgres.
- Licence Apache 2.0, code propre, mais pas de contributions externes et pas de release publiée sur la page GitHub.
- Ce qu'OntoForge peut reprendre : la méthode (un terme par table, certification humaine, détection de ce que le modèle ne couvre pas), pas le code.
- Pour amorcer une ontologie depuis des PDF ou du texte, il ne sert à rien. L'assistant d'OntoForge fait déjà le même geste avec une pièce jointe texte.

## Ce que fait vraiment l'outil

Source : [README](https://raw.githubusercontent.com/NVIDIA/auto-ontology/main/README.md) (consulté le 7/11/2026). Les citations ci-dessous viennent de ce fichier.

Le README dit : « builds that layer from enterprise metadata, reconciles definitions across systems, and exposes it to any agent harness through MCP, CLI, and API ». L'entrée est donc la métadonnée d'entreprise, pas un corpus de documents.

Trois étapes : générer, certifier, répondre.

1. Générer (service d'ingestion, `auto_ontology/semantic/`).
   - Lecture des sources : schémas, profilage de colonnes, valeurs échantillonnées, dans un catalogue.
   - Nommage des entités : un LLM propose des « Terms » table par table et affecte chaque colonne à un terme (`term_extractor.py`).
   - Résolution des relations : jointures déduites des clés et des données, tables de pont (`bridge_tables.py`, `fk_suggester.py`, `semantic_fk.py`).
   - Écriture : termes, relations et « attributs SQL » en Postgres, plongements dans pgvector (`embed.py`).
2. Certifier : des humains testent avec des vraies questions, corrigent termes et descriptions, puis certifient.
3. Répondre : l'agent classe l'intention, retrouve les termes par recherche vectorielle, écrit le SQL, vérifie les valeurs de filtre dans la base, puis exécute. S'il ne peut pas répondre, il le dit (`check_answerable`).

Ce qu'on voit dans le code :

- Le prompt d'extraction impose « Strongly prefer ONE Term per table » et interdit de proposer des relations `IS_A`, `PART_OF` ou `ROLE` ([`term_extractor.py`](https://github.com/NVIDIA/auto-ontology/blob/main/auto_ontology/semantic/term_extractor.py)). Les constantes existent dans `constants.py`, mais le modèle ne les produit pas.
- Les sorties du LLM sont des modèles Pydantic stricts (`extra="forbid"` dans `models.py`). C'est un bon exemple de sortie structurée.
- Un contrôle déterministe suit chaque étape LLM (noms valides, regex de libellé, `deterministic.py`).
- `grep` sur `owl`, `rdf`, `turtle`, `sparql`, `shacl` : aucun résultat dans le code Python et les documents hors fichier de verrouillage.

## Pipeline, formats, modèles

| Point | Constat | Source |
|---|---|---|
| Entrées | 10 moteurs SQL : PostgreSQL, MySQL, Databricks, Snowflake, ClickHouse, Trino, Kyuubi, HeavyDB, DuckDB, SQLite | README, section « Sources » |
| Stockage | Postgres 17 + pgvector, catalogue et ontologie dans les mêmes tables | README |
| Échange | YAML Apache Ossie (`semantic_model.yaml`, `ontology.yaml`, `mapping.yaml`) via un convertisseur tiers | `model_interchange/service.py`, README |
| Sorties agent | MCP en lecture seule (FastMCP), CLI, API REST, SSE pour le chat | README |
| Pile | Backend FastAPI + LangChain + LangGraph (Python 3.12 à 3.13), frontend Next.js 16 / React 19 | `pyproject.toml`, README |
| Modèles | 4 rôles : raisonnement et non-raisonnement (`nvidia/nemotron-3.5-lightning-30b-a3b`), plongements (`nemotron-3.5-embed-1b`), reranker (`nemotron-3.5-rerank-8b`) | README, section « Models » |
| Hébergement des modèles | NVIDIA API catalog par défaut, tout point d'accès compatible OpenAI possible, clé `nvapi-` requise | README |
| Service externe optionnel | KumoRFM (prédictions) : envoie les tables connectées à un service hébergé | README, section « Predictions » |

Apache Ossie est un standard d'échange de modèles sémantiques. Son dépôt de convertisseurs : [apache/ossie-converters](https://github.com/apache/ossie-converters). Le site ossie.apache.org n'était pas joignable depuis notre environnement (proxy) : je n'ai pas pu lire sa spécification. À revérifier avant toute idée d'import.

## Licence et maturité

| Point | Constat | Source |
|---|---|---|
| Licence | Apache 2.0, en-têtes SPDX dans chaque fichier | [LICENSE](https://raw.githubusercontent.com/NVIDIA/auto-ontology/main/LICENSE) |
| Contributions | « This project is currently not accepting external contributions » | README |
| Version | 1.2.0 (`pyproject.toml`), bump du 5 nov. 2026 | clone local, `git log` |
| Releases GitHub | Aucune affichée | [page du dépôt](https://github.com/NVIDIA/auto-ontology), via WebFetch |
| Activité | Dernier commit lu : 6 nov. 2026 (« Pin Python 3.12.16 »). La page indique environ 9,6 k étoiles, 769 forks, 39 tickets ouverts | clone local ; page du dépôt (chiffres de la page à recouper, relevés par un outil de lecture automatique) |
| Tests | 159 fichiers `test_*.py`, CI GitHub Actions présente (`.github/workflows`) | clone local |
| Sécurité | Ports 3001 et 3002 sans authentification propre, à garder en réseau privé | README |

Lecture : projet jeune, très actif, géré comme un produit interne ouvert. L'historique visible court depuis fin sept. 2026 dans notre clone partiel, donc je ne peux pas dater sa création. Je ne m'appuierais pas sur ses API.

## Recouvrement avec OntoForge

| Sujet | Auto Ontology | OntoForge |
|---|---|---|
| Objet modélisé | Couche métier sur du SQL (termes, jointures, mesures) | Ontologie OWL 2 / SHACL puis property graph |
| Sortie | Réponses SQL | DDL Neo4j, code C# Curiosity, rapport de pertes |
| Humain dans la boucle | Certification des termes | Arbitrage des constats `review` et `lost` |
| LLM | Au cœur du produit | Optionnel (assistant), repli déterministe |
| Standards W3C | Aucun | Cœur du produit |

Le recouvrement est faible. Les deux outils se rejoignent sur un point : un brouillon produit par un LLM doit être certifié par un humain avant usage.

## Ce qu'OntoForge peut en reprendre

Classement gain / effort, de 1 à 5 pour le gain ; S ≤ 1 j, M 2 à 4 j, L > 4 j.

| # | Idée | Gain | Effort | Détail |
|---|---|---|---|---|
| N1 | Brouillon structuré + contrôles déterministes | 4 | S | Faire valider la sortie LLM de l'assistant par un schéma strict, puis par des règles déterministes (nom valide, IRI nouvelle, pas de doublon). OntoForge fait déjà l'essai à blanc des opérations (`assistant/agent.py`). À étendre à `proposal`. |
| N2 | « Un terme par table » comme règle de départ pour l'import SQL (P-07) | 3 | S | Règle simple et défendable, citée dans le prompt de NVIDIA. À garder comme défaut, avec une décision humaine pour les tables de jonction. |
| N3 | Détection de ce que le modèle ne couvre pas (`check_answerable`) | 4 | M | Appliquée aux questions de compétence (P-12) : « cette question n'a aucun terme pour *ad spend* ». Cela rejoint l'idée OntoForge de mettre en avant ce qui manque. |
| N4 | Amorcer une ontologie depuis du texte ou des PDF | 3 | M | Voir ci-dessous. Rien à reprendre de NVIDIA, le geste existe déjà côté OntoForge. |
| N5 | Export en YAML Ossie | 2 | M | À étudier seulement si un client le demande. Spécification non lue (site inaccessible). |
| N6 | Serveur MCP en lecture sur le projet OntoForge | 3 | M | Même idée que leur MCP : exposer ontologie et constats à un agent. Pas lié à leur code. |

### Amorcer depuis des PDF ou du texte : coût et risques

État actuel d'OntoForge, lu dans le code :

- L'assistant accepte déjà des pièces jointes de type `text`, `csv`, `sql` ou `markdown` (`api/assistant.py`), tronquées à 12 000 caractères (`ATT_LIMIT` dans `assistant/service.py`).
- Il renvoie une `proposal` (ontologie partielle) validée avant application, avec repli déterministe sans LLM.

Ce qui manque pour des PDF :

1. Extraction de texte du PDF (bibliothèque dédiée ; les PDF scannés exigent de la reconnaissance de caractères). Effort S à M.
2. Découpage au-delà de 12 000 caractères, avec fusion des propositions. Effort M.
3. Traçabilité : chaque classe ou propriété proposée doit citer l'extrait source, sinon l'arbitrage est impossible. Effort S.
4. Questions de compétence générées d'abord, puis ontologie. C'est l'approche de la littérature citée dans `docs/IDEES.md` (sources 8). Effort M.

Risques :

- Confidentialité : un document client envoyé à un LLM hébergé. L'outil prévoit déjà des fournisseurs locaux (Ollama). Il faut un avertissement explicite avant envoi.
- Hallucination : classes plausibles absentes du texte. Parade : extrait source obligatoire et statut « à confirmer » par défaut.
- Qualité OWL : un LLM produit souvent des hiérarchies fausses (relation partie-tout confondue avec sous-classe). Parade : passer le brouillon dans le lint W3C existant avant affichage.
- Coût et dérive : documents longs, appels multiples. Plafonner et afficher une estimation.

Reco : faire N1 et N4 dans un seul lot (« amorcer depuis un document »), en texte puis PDF. Ne rien reprendre du code NVIDIA.

## Risques propres à NVIDIA

- Aucune garantie d'API stable (pas de release, pas de contribution externe).
- Dépendance à des modèles et services NVIDIA par défaut (clé `nvapi-`).
- Une dépendance du serveur est épinglée sur un commit git d'un dépôt tiers (convertisseur Ossie). Signe d'un projet qui bouge vite.
- Licence Apache 2.0 : réutilisation du code possible avec mention. Je ne recommande pas de le faire : pile différente (Postgres, LangChain), usage différent.

## Sources

1. NVIDIA, README : https://raw.githubusercontent.com/NVIDIA/auto-ontology/main/README.md (7/11/2026)
2. NVIDIA, `pyproject.toml` : https://raw.githubusercontent.com/NVIDIA/auto-ontology/main/pyproject.toml (7/11/2026)
3. NVIDIA, LICENSE : https://raw.githubusercontent.com/NVIDIA/auto-ontology/main/LICENSE (7/11/2026)
4. NVIDIA, `term_extractor.py` : https://github.com/NVIDIA/auto-ontology/blob/main/auto_ontology/semantic/term_extractor.py
5. NVIDIA, `AGENTS.md` et `CONTRIBUTING.md` : https://github.com/NVIDIA/auto-ontology
6. Apache Ossie, convertisseurs : https://github.com/apache/ossie-converters
7. OntoForge, assistant : `backend/ontoforge/assistant/service.py`, `backend/ontoforge/api/assistant.py`

## Limites de cette fiche

- L'API GitHub n'était pas accessible : étoiles, forks et tickets viennent d'une lecture automatique de la page, à recouper.
- Clone partiel : l'âge du dépôt et le nombre exact de commits ne sont pas établis.
- Les dossiers `frontend/`, `mcp/`, `helm/` n'ont pas été lus en détail.
- Aucune exécution de l'outil, aucun test de qualité des termes produits.
