"""Verrou unique pour l'analyseur SPARQL de rdflib (L53, DF-B17).

L'analyseur de `rdflib.plugins.sparql.parser` est construit avec pyparsing : ses éléments de grammaire sont des objets partagés par tout le
processus, modifiés pendant l'analyse, donc pas réentrants. Deux analyses simultanées (deux requêtes HTTP traitées par deux fils du serveur)
échouaient au hasard avec des erreurs internes (« Param.postParse2() missing 1 required positional argument », « <lambda>() missing … »),
vues comme « SPARQL invalide » (422) sur une requête valide, ou, dans `localstore/runner.py`, comme un contrôle de `SERVICE` et de `FROM`
silencieusement sauté.

Règle : tout appel au parseur ou au traducteur SPARQL de rdflib dans le processus du serveur passe par ce module. Verrou réentrant (une analyse
peut en appeler une autre), tenu le temps d'une analyse (quelques millisecondes), jamais pendant une exécution de requête ni un appel réseau.
Les processus fils (`_worker.py`, shacl, owlrl) ont leur propre processus : sans objet. Test de garde : `tests/test_l53_b17.py`.
"""
from __future__ import annotations

import threading
from typing import Any

LOCK = threading.RLock()


def parse_query(sparql: str) -> Any:
    from rdflib.plugins.sparql import parser
    with LOCK:
        return parser.parseQuery(sparql)


def parse_update(sparql: str) -> Any:
    from rdflib.plugins.sparql import parser
    with LOCK:
        return parser.parseUpdate(sparql)


def prepare_query(sparql: str, **kwargs: Any) -> Any:
    """`rdflib.plugins.sparql.prepareQuery` (analyse puis algèbre) sous le verrou."""
    from rdflib.plugins.sparql import prepareQuery
    with LOCK:
        return prepareQuery(sparql, **kwargs)


def translate_parsed(sparql: str) -> Any:
    """Algèbre d'une requête (analyse + `translateQuery`) sous le verrou."""
    from rdflib.plugins.sparql import algebra
    with LOCK:
        return algebra.translateQuery(parse_query(sparql))
