"""Lecture défensive des fichiers RDF fournis par l'utilisateur (L39-secu, SEC-04 / SEC-06 / SEC-07).

Tout fichier importé (ontologie, shapes, données à valider) passe par :func:`parse_into` au lieu de ``Graph.parse`` :

* RDF/XML, TriX : tout ``DOCTYPE`` est refusé (déclarations d'entités, expansion récursive) ;
* JSON-LD : tout contexte distant (``@context`` donné par une chaîne, ``@import``) est refusé : le serveur ne télécharge rien
  pendant la lecture (le contrôle SSRF ``netguard`` ne s'applique pas à rdflib) ;
* canonisation des nœuds blancs plafonnée (:func:`canonical_or_same`) : coût quadratique sur les longues listes.

Les refus lèvent :class:`UnsafeRdfError`, avec un message destiné à l'utilisateur.
"""
from __future__ import annotations

import json
import os
from typing import Any
from xml.parsers import expat

import rdflib
from rdflib.compare import to_canonical_graph

XML_FORMATS = {"xml", "application/rdf+xml", "trix"}
JSONLD_FORMATS = {"json-ld", "application/ld+json"}
MAX_JSON_DEPTH = 200


class UnsafeRdfError(ValueError):
    """Fichier refusé pour des raisons de sécurité (entités XML, contexte distant, trop de nœuds blancs)."""


def max_canon_triples() -> int:
    try:
        return max(50, int(os.environ.get("ONTOFORGE_MAX_CANON_TRIPLES", "1500")))
    except ValueError:
        return 1500


def max_unmapped_triples() -> int:
    """Plafond de triplets non reconnus conservés dans le projet (ils sont copiés, canonisés et réécrits à chaque sauvegarde)."""
    try:
        return max(100, int(os.environ.get("ONTOFORGE_MAX_UNMAPPED_TRIPLES", "10000")))
    except ValueError:
        return 10000


class _Stop(Exception):
    pass


def check_xml(data: str | bytes) -> None:
    """Refuse un document XML qui déclare un DOCTYPE. L'analyse s'arrête à la première balise : coût négligeable.
    Un document mal formé n'est pas jugé ici (rdflib produira son message d'erreur de syntaxe)."""
    p = expat.ParserCreate()

    def doctype(*_a: Any) -> None:
        raise UnsafeRdfError("Fichier RDF/XML refusé : il déclare un DOCTYPE ou des entités XML, qui ne sont pas acceptés par sécurité. "
                             "Réexportez le fichier sans entités (RDF/XML sans DOCTYPE) ou en Turtle.")

    def first_element(*_a: Any) -> None:
        raise _Stop()

    p.StartDoctypeDeclHandler = doctype
    p.EntityDeclHandler = doctype
    p.StartElementHandler = first_element
    try:
        p.Parse(data, True)
    except _Stop:
        return
    except expat.ExpatError:
        return


def _scan_context(node: Any, depth: int = 0) -> None:
    if depth > MAX_JSON_DEPTH:
        raise UnsafeRdfError("Fichier JSON-LD refusé : imbrication trop profonde.")
    if isinstance(node, dict):
        for k, v in node.items():
            if k == "@import":
                raise UnsafeRdfError("Fichier JSON-LD refusé : « @import » charge un contexte distant, ce qui n'est pas autorisé.")
            if k == "@context":
                items = v if isinstance(v, list) else [v]
                for it in items:
                    if isinstance(it, str):
                        raise UnsafeRdfError("Fichier JSON-LD refusé : le contexte « @context » est une référence distante. "
                                             "Remplacez-la par le contexte intégré au fichier (objet JSON), ou convertissez en Turtle.")
            _scan_context(v, depth + 1)
    elif isinstance(node, list):
        for it in node:
            _scan_context(it, depth + 1)


def check_jsonld(data: str | bytes) -> None:
    try:
        doc = json.loads(data)
    except (ValueError, RecursionError):
        return  # JSON invalide : le message de syntaxe viendra de rdflib
    _scan_context(doc)


def parse_into(g: rdflib.Graph, data: str | bytes, fmt: str, **kw: Any) -> rdflib.Graph:
    """``g.parse(data=data, format=fmt)`` après les contrôles ci-dessus."""
    f = (fmt or "").lower()
    if f in XML_FORMATS:
        check_xml(data)
    elif f in JSONLD_FORMATS:
        check_jsonld(data)
    g.parse(data=data, format=fmt, **kw)
    return g


def canonical_or_same(g: rdflib.Graph) -> tuple[rdflib.Graph, bool]:
    """(graphe, canonisé ?) : au-delà du plafond de triplets, le graphe est rendu tel quel (étiquettes de nœuds blancs non stables)."""
    if len(g) > max_canon_triples():
        return g, False
    return to_canonical_graph(g), True
