# L15 — rapport backend (requêtage guidé)

Agent : query. Tests : `cd backend && pytest -q` -> 510 verts (15 nouveaux dans `tests/test_query_builder.py`).

## Livré
- Endpoints SPARQL multiples (`settings/models.py`, `store.py`, `api/settings.py`) : CRUD, test, actif, secret chiffré (`secret_enc`), rotation couverte, migration depuis `sparql_endpoint` (miroir conservé en PUT).
- `queries/builder.py` : `GuidedQuery`, `to_sparql` (IRIs compactées, parsé par rdflib), `Suggester` (domaine/portée effectifs, héritage, inverse, unions, shapes), `build_all` (réutilise `translate`), `guided_from_sparql`.
- `queries/endpoint.py` : exécution lecture seule (parseur), LIMIT forcé, timeout, aperçu graphe. `queries/saved.py` : requêtes sauvegardées par projet.
- `api/queries.py` : suggest / build / run / values / saved / competency guidées. Contrat : CONTRACTS §6.

## Limites et points ouverts
- `GET /query/suggest` : domaine ou portée via `domain_expr`/`range_expr` complexes = approximé (toujours admis).
- Propriétés de données sélectionnées = OPTIONAL (différence de sémantique avec une question de compétence où elles étaient obligatoires, signalée dans `reason`).
- Sous-propriétés non développées dans le SPARQL généré ; `subclasses` via chemin SPARQL.
- Le filtre `lang`/`LCASE`/`LANGMATCHES` : Cypher produit selon `translate` (notes `[perte]` éventuelles remontées dans `notes`).
- Aperçu graphe : arêtes seulement pour les requêtes guidées (SPARQL libre = nœuds).
- Un test run laissait `backend/data/settings.json` créé par un chargement hors fixture ; les tests assistant échouent s'il existe (hygiène, non lié au code).
- Rien d'externe non confirmé : aucune API Curiosity ajoutée (Curiosity sort du traducteur existant, déjà marqué À VÉRIFIER).

## Ajout : question en langage naturel (`POST /query/nl`, `queries/nl.py`)
- Pré-analyse déterministe + LLM optionnel + validation stricte + repli déterministe (mock) ; contrat dans CONTRACTS §6. Tests sur automaint avec le mock (trois questions de Jerem) et avec de faux fournisseurs (relation inventée, sens inversé, JSON invalide) : 516 tests verts.
- Limites : lexique FR->EN minimal (les ontologies avec libellés français ou altLabel n'en ont pas besoin) ; « Toulouse » est cherché dans la propriété nom (automaint n'a pas de ville) et signalé dans `explanation` ; pas de comptage / agrégat / tri en langage naturel ; année supposée = année courante.
- Le prompt LLM n'a pas été éprouvé sur un vrai modèle (aucun réseau en test) : à valider avec Jerem sur son fournisseur.
