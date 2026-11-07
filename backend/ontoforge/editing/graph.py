"""Graphe léger de l'ontologie pour l'éditeur (nœuds / arêtes à identifiants déterministes)."""
from __future__ import annotations

from typing import Optional

from ..core.onto_model import OWL, OntoModel
from ..core.project import ProjectView

ABSTRACT_ANNOTATION = "urn:ontoforge:abstract"


def _is_abstract(c) -> bool:
    return bool(c.disjoint_union_of) or any(a.property == ABSTRACT_ANNOTATION and a.value.lower() == "true" for a in c.annotations)


def build_graph(onto: OntoModel, view: ProjectView, lang: str = "fr", include: Optional[set[str]] = None) -> dict:
    """``include`` ⊆ {"datatypes", "individuals"} : ajoute les nœuds datatype / individu et leurs arêtes (hors défaut, pour rester léger)."""
    include = include or set()
    nodes: dict[str, dict] = {}
    edges: dict[str, dict] = {}
    skipped: list[str] = []

    def node(iri: str, kind: str, e=None, abstract: bool = False) -> None:
        pos = view.positions.get(iri)
        nodes[iri] = {"id": iri, "label": onto.label(iri, lang), "kind": kind, "icon": view.icons.get(iri),
                      "position": {"x": pos.x, "y": pos.y} if pos else None, "abstract": abstract,
                      "deprecated": bool(e and e.deprecated), "collapsed": iri in view.collapsed}

    def edge(kind: str, iri: str, s: str, t: str, label: str = "", **extra) -> str:
        eid = f"{kind}|{iri}|{s}|{t}"
        edges[eid] = {"id": eid, "source": s, "target": t, "kind": kind, "label": label, "iri": iri or None, **extra}
        return eid

    for iri, c in onto.classes.items():
        node(iri, "class", c, _is_abstract(c))
    for iri, c in onto.classes.items():
        for par in c.sub_class_of:
            if par in nodes:
                edge("subClassOf", "", iri, par)
        for d in c.disjoint_with:
            if d in nodes:
                a, b = sorted((iri, d))
                edge("disjointWith", "", a, b)
        for eq in c.equivalent_to:
            if eq.op == "named" and eq.iri in nodes and eq.iri != iri:
                a, b = sorted((iri, eq.iri))
                edge("equivalentClass", "", a, b)

    prop_edges: dict[str, list[str]] = {}
    for iri, p in onto.object_properties.items():
        doms = sorted(set(p.domain) | set(p.domain_union))
        rngs = sorted(set(p.range) | set(p.range_union))
        doms = [d for d in doms if d in nodes and d != OWL + "Thing"]
        rngs = [r for r in rngs if r in nodes and r != OWL + "Thing"]
        if not doms or not rngs:
            skipped.append(iri)
            continue
        for d in doms:
            for r in rngs:
                eid = edge("objectProperty", iri, d, r, onto.label(iri, lang), inverse_of=p.inverse_of,
                           characteristics=list(p.characteristics), deprecated=p.deprecated)
                prop_edges.setdefault(iri, []).append(eid)
    for iri, p in onto.object_properties.items():
        q = p.inverse_of
        if q and iri in prop_edges and q in prop_edges:
            a, b = sorted((iri, q))
            edge("inverseOf", f"{a}|{b}", prop_edges[a][0], prop_edges[b][0], "inverseOf", on="edges")

    if "datatypes" in include:
        for iri, p in onto.datatype_properties.items():
            doms = [d for d in sorted(set(p.domain) | set(p.domain_union)) if d in nodes]
            if not doms or not p.range:
                skipped.append(iri)
                continue
            for r in p.range:
                if r not in nodes:
                    node(r, "datatype", onto.datatypes.get(r))
                for d in doms:
                    edge("datatypeProperty", iri, d, r, onto.label(iri, lang), functional=p.functional)
    if "individuals" in include:
        for iri, ind in onto.individuals.items():
            node(iri, "individual", ind)
            for t in ind.types:
                if t in nodes and nodes[t]["kind"] == "class":
                    edge("type", "", iri, t)
    return {"nodes": [nodes[k] for k in sorted(nodes)], "edges": [edges[k] for k in sorted(edges)], "skipped": sorted(skipped)}
