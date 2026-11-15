"""Effectifs par type : individus du triplestore local s'il est chargé, sinon individus de l'ontologie, sinon inconnu (None)."""
from __future__ import annotations

import logging
from typing import Any, Optional

from ..core.onto_model import OntoModel
from .graph import SchemaGraph

log = logging.getLogger(__name__)

RDF_TYPE = "http://www.w3.org/1999/02/22-rdf-syntax-ns#type"


def _run_store(pid: str, fn: Any) -> Any:
    from ..localstore import store as st
    with st.lock(pid).read():
        return st._with_store(pid, fn, readonly=True)


def store_counts(pid: str) -> Optional[dict[str, int]]:
    """Nombre d'individus distincts par classe (typage direct) dans l'union du triplestore local ; None s'il n'existe pas ou n'a aucune donnée."""
    try:
        from ..localstore import store as st
        if not st.exists(pid):
            return None
        q = "SELECT ?c (COUNT(DISTINCT ?s) AS ?n) WHERE { ?s a ?c . FILTER(isIRI(?c)) } GROUP BY ?c"

        def run(store: Any) -> dict[str, int]:
            out: dict[str, int] = {}
            for sol in store.query(q):
                out[sol["c"].value] = int(sol["n"].value)
            return out

        raw = _run_store(pid, run)
    except Exception as exc:  # noqa: BLE001 - le triplestore est facultatif pour la carte
        log.info("effectifs du triplestore indisponibles : %s", exc)
        return None
    skip = ("http://www.w3.org/2002/07/owl#", "http://www.w3.org/2000/01/rdf-schema#", "http://www.w3.org/1999/02/22-rdf-syntax-ns#")
    inst = {c: n for c, n in raw.items() if not c.startswith(skip)}
    return inst or None


def store_distinct_counts(pid: str, groups: dict[str, list[str]]) -> dict[str, int]:
    """Individus distincts typés par au moins une classe de chaque groupe (un individu typé par deux classes d'un même groupe compte une fois)."""
    def run(store: Any) -> dict[str, int]:
        out: dict[str, int] = {}
        for key, classes in groups.items():
            vals = " ".join(f"<{c}>" for c in classes)
            q = f"SELECT (COUNT(DISTINCT ?s) AS ?n) WHERE {{ VALUES ?c {{ {vals} }} ?s a ?c }}"
            for sol in store.query(q):
                out[key] = int(sol["n"].value)
        return out

    return _run_store(pid, run)


def onto_counts(onto: OntoModel) -> dict[str, int]:
    """Effectif par classe, typage direct (conservé pour compatibilité ; la carte utilise ``onto_closed_counts``)."""
    out: dict[str, int] = {}
    for ind in onto.individuals.values():
        for t in ind.types:
            out[t] = out.get(t, 0) + 1
    return out


def closure_of(onto: OntoModel, sources: list[str]) -> list[str]:
    """Classes sources et toutes leurs sous-classes (rdfs:subClassOf transitif) : un individu d'une sous-classe est aussi une instance de la mère (rdfs9)."""
    out: list[str] = []
    for s in sources:
        for c in [s, *(onto.descendants(s) if s in onto.classes else [])]:
            if c not in out:
                out.append(c)
    return out


def apply_counts(g: SchemaGraph, onto: OntoModel, pid: Optional[str]) -> str:
    """Renseigne ``SNode.count`` ; renvoie la provenance : ``store`` | ``ontology`` | ``none``.

    Effectif d'un type = nombre d'individus **distincts** typés par l'une de ses classes sources ou de leurs sous-classes
    (fermeture rdfs:subClassOf) ; un individu typé par plusieurs de ces classes compte une seule fois.
    """
    direct = store_counts(pid) if pid else None
    origin = "store"
    if direct is None:
        direct = onto_counts(onto)
        origin = "ontology"
    if not direct:
        g.count_origin = "none"
        return "none"
    g.count_origin = origin
    closure = {k: closure_of(onto, n.sources or [n.id]) for k, n in g.nodes.items()}
    if origin == "store":
        multi = {k: cl for k, cl in closure.items() if len([c for c in cl if direct.get(c)]) > 1}
        distinct: dict[str, int] = {}
        if multi:
            try:
                distinct = store_distinct_counts(pid, multi)  # type: ignore[arg-type]
            except Exception as exc:  # noqa: BLE001
                log.info("effectifs distincts indisponibles : %s", exc)
        for k, n in g.nodes.items():
            n.count = distinct[k] if k in distinct else sum(direct.get(c, 0) for c in closure[k])
    else:
        types_of = {key: set(i.types) for key, i in onto.individuals.items()}
        for k, n in g.nodes.items():
            cl = set(closure[k])
            n.count = sum(1 for ts in types_of.values() if ts & cl)
    return origin
