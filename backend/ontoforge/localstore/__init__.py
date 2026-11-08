"""Triplestore local embarqué (L19) : un petit magasin RDF par projet, pour tester l'ontologie et les individus sans endpoint externe.

Moteur : pyoxigraph (Oxigraph, SPARQL 1.1 Query). Voir docs/veille/triplestore-embarque.md pour l'évaluation et CONTRACTS §6.1.
Modules : `store` (contenu, persistance, inférence), `runner` (exécution isolée des requêtes).
"""
from .store import StoreError  # noqa: F401
