"""Graphe léger de l'ontologie pour l'éditeur (nœuds / arêtes à identifiants déterministes)."""
from __future__ import annotations

from typing import Optional

from ..core.onto_model import OWL, OntoModel
from ..core.project import ProjectView

ABSTRACT_ANNOTATION = "urn:ontoforge:abstract"


def _is_abstract(c) -> bool:
    return bool(c.disjoint_union_of) or any(a.property == ABSTRACT_ANNOTATION and a.value.lower() == "true" for a in c.annotations)


def _namespaces(onto: OntoModel) -> tuple[str, ...]:
    """Préfixes de l'espace de noms de l'ontologie (IRI de l'ontologie, avec ``#`` ou ``/`` final) ; vide si elle n'a pas d'IRI.

    Repli (revue w3c L26) : si aucune classe déclarée n'est dans cet espace (IRI d'ontologie versionnée ou distincte du
    vocabulaire, cas fréquent), on prend l'espace de noms majoritaire des classes déclarées, sinon tout serait « externe ».
    """
    base = (onto.meta.iri or "").rstrip("#/")
    if not base:
        return ()
    spaces = (base + "#", base + "/")
    if onto.classes and not any(i.startswith(spaces) for i in onto.classes):
        counts: dict[str, int] = {}
        for i in onto.classes:
            cut = max(i.rfind("#"), i.rfind("/"))
            if cut > 0:
                counts[i[:cut + 1]] = counts.get(i[:cut + 1], 0) + 1
        if counts:
            return (max(sorted(counts), key=counts.__getitem__),)
    return spaces


def build_graph(onto: OntoModel, view: ProjectView, lang: str = "fr", include: Optional[set[str]] = None) -> dict:
    """``include`` ⊆ {"datatypes", "individuals", "external", "anonymous", "thing"} : ajoute des nœuds et arêtes, hors défaut pour rester léger.

    - datatypes : nœuds datatype et arêtes ``datatypeProperty`` (étiquette, ``functional``, ``deprecated``) ;
    - individuals : individus et arêtes ``type`` ;
    - external : classes référencées (parent, équivalence, disjonction, domaine, image) mais non déclarées → nœuds ``external: true`` ;
    - anonymous : classes anonymes (and / or / not) des équivalences et superclasses → nœuds ``kind: "anonymous"`` (``op``) ;
    - thing : nœuds ``kind: "thing"`` (owl:Thing, un par extrémité) pour les propriétés dont le domaine ou l'image est owl:Thing ou absent.
    Toujours présents (ajout rétrocompatible) : ``external`` (classe hors de l'espace de noms de l'ontologie) et ``equivalent`` (équivalence nommée) sur chaque nœud.
    """
    include = include or set()
    spaces = _namespaces(onto)
    nodes: dict[str, dict] = {}
    edges: dict[str, dict] = {}
    skipped: list[str] = []

    def node(iri: str, kind: str, e=None, abstract: bool = False, external: Optional[bool] = None) -> None:
        pos = view.positions.get(iri)
        if external is None:
            external = bool(spaces) and kind == "class" and not iri.startswith(spaces)
        nodes[iri] = {"id": iri, "label": onto.label(iri, lang), "kind": kind, "icon": view.icons.get(iri),
                      "position": {"x": pos.x, "y": pos.y} if pos else None, "abstract": abstract,
                      "deprecated": bool(e and e.deprecated), "collapsed": iri in view.collapsed,
                      "external": external, "equivalent": False}

    def edge(kind: str, iri: str, s: str, t: str, label: str = "", **extra) -> str:
        eid = f"{kind}|{iri}|{s}|{t}"
        edges[eid] = {"id": eid, "source": s, "target": t, "kind": kind, "label": label, "iri": iri or None, **extra}
        return eid

    for iri, c in onto.classes.items():
        node(iri, "class", c, _is_abstract(c))
    if "external" in include:
        refs: set[str] = set()
        for iri, c in onto.classes.items():
            refs.update(c.sub_class_of, c.disjoint_with, (e.iri for e in c.equivalent_to if e.op == "named" and e.iri))
        for p in onto.object_properties.values():
            refs.update(p.domain, p.domain_union, p.range, p.range_union)
        for r in sorted(refs):
            if r and r not in nodes and r != OWL + "Thing":
                # non déclarée : externe si hors de l'espace de noms (sans IRI d'ontologie : toujours externe)
                node(r, "class", None, external=not r.startswith(spaces) if spaces else True)
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
                nodes[iri]["equivalent"] = nodes[eq.iri]["equivalent"] = True
    if "anonymous" in include:
        def anon(owner: str, rel: str, k: int, ex) -> None:
            if ex.op not in ("and", "or", "not"):
                return
            aid = f"anon|{owner}|{rel}|{k}"
            nodes[aid] = {"id": aid, "label": {"and": "∩", "or": "∪", "not": "¬"}[ex.op], "kind": "anonymous", "op": ex.op, "icon": None,
                          "position": None, "abstract": False, "deprecated": False, "collapsed": False, "external": False, "equivalent": False}
            edge(rel, "", owner, aid)
            for a in ex.args:
                if a.op == "named" and a.iri in nodes:
                    edge("anonymousOf", "", aid, a.iri, {"and": "intersectionOf", "or": "unionOf", "not": "complementOf"}[ex.op])
        for iri, c in onto.classes.items():
            for k, ex in enumerate(c.equivalent_to):
                anon(iri, "equivalentClass", k, ex)
            for k, ex in enumerate(c.super_expressions):
                anon(iri, "subClassOf", k, ex)

    prop_edges: dict[str, list[str]] = {}
    for iri, p in onto.object_properties.items():
        doms = sorted(set(p.domain) | set(p.domain_union))
        rngs = sorted(set(p.range) | set(p.range_union))
        # owl:Thing seulement si le domaine (l'image) est absent ou vaut owl:Thing dans l'ontologie, pas s'il vise une classe
        # simplement absente de la vue (périmètre, externes non demandées) : ce serait affirmer un axiome faux.
        thing_d = "thing" in include and not [d for d in doms if d != OWL + "Thing"]
        thing_r = "thing" in include and not [r for r in rngs if r != OWL + "Thing"]
        doms = [d for d in doms if d in nodes and d != OWL + "Thing"]
        rngs = [r for r in rngs if r in nodes and r != OWL + "Thing"]
        if (not doms and not thing_d) or (not rngs and not thing_r) or (thing_d and thing_r):
            skipped.append(iri)
            continue
        for side, flag in (("d", thing_d), ("r", thing_r)):
            if flag:
                tid = f"{OWL}Thing|{iri}|{side}"
                nodes[tid] = {"id": tid, "label": "Thing", "kind": "thing", "icon": None, "position": None, "abstract": False,
                              "deprecated": False, "collapsed": False, "external": False, "equivalent": False}
                (doms if side == "d" else rngs).append(tid)
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
    # inverse sans arête propre (ni domaine ni image, cas de am:partOf) : InverseObjectProperties(P, Q) suffit à lui donner
    # les extrémités de P inversées (OWL 2 Direct Semantics), on porte donc son libellé sur les arêtes de P (VOWL : double pointe).
    pairs = {(iri, p.inverse_of) for iri, p in onto.object_properties.items() if p.inverse_of}
    pairs |= {(q, p) for p, q in pairs}
    for p_iri, q_iri in sorted(pairs):
        if p_iri in prop_edges and q_iri not in prop_edges and q_iri in onto.object_properties:
            for eid in prop_edges[p_iri]:
                edges[eid]["inverse_label"] = onto.label(q_iri, lang)
            if q_iri in skipped:
                skipped.remove(q_iri)

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
                    edge("datatypeProperty", iri, d, r, onto.label(iri, lang), functional=p.functional, deprecated=p.deprecated)
    if "individuals" in include:
        for iri, ind in onto.individuals.items():
            node(iri, "individual", ind)
            for t in ind.types:
                if t in nodes and nodes[t]["kind"] == "class":
                    edge("type", "", iri, t)
    return {"nodes": [nodes[k] for k in sorted(nodes)], "edges": [edges[k] for k in sorted(edges)], "skipped": sorted(skipped)}
