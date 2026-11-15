"""Graphe neutre de schéma (nœuds, relations) extrait d'une ontologie ou d'un PGModel, pour la carte métier.

Une seule représentation pour les deux sources : les stratégies de zones, les rôles, les cadres et la mise en page n'ont
pas à savoir d'où vient le schéma.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Optional

from ..core.onto_model import OWL, OntoModel, local_name
from ..core.pg_model import PGModel

PART_OF = re.compile(r"^(is)?partof|belongsto|componentof|memberof|partiede|faitpartie|appartient")
HAS_PART = re.compile(r"^has\w*(part|component|detail)s?$|^includes|^contains|^comprend|^inclut|^composedof")


@dataclass
class SNode:
    id: str
    label: str
    parents: list[str] = field(default_factory=list)  # parents directs (nœuds du graphe)
    namespace: str = ""
    perimeters: set[str] = field(default_factory=set)
    abstract: bool = False
    enumerated: bool = False
    sources: list[str] = field(default_factory=list)  # IRIs des classes d'origine
    count: Optional[int] = None
    n_data: Optional[int] = None  # nombre de propriétés à valeur littérale (None si inconnu)


@dataclass
class SRel:
    id: str
    source: str
    target: str
    label: str
    key: str  # identité de la relation (IRI de propriété ou nom de type d'arête), pour comparer des relations de nœuds différents
    kind: str = "relation"  # relation | subclass
    inverse_label: Optional[str] = None
    both: bool = False  # inverses fusionnées (ou symétrique) : une seule arête, deux noms
    part: Optional[str] = None  # part_of (source = partie) | has_part (source = tout) | None
    link: Optional[str] = None  # si ``both`` : « inverse » (deux propriétés liées par owl:inverseOf, ou inverse non nommée dans le schéma) | « symmetric »
    union: bool = False  # domaine ou image déclaré par une union de classes : chaque flèche est une possibilité (« une parmi »), pas un fait


@dataclass
class SchemaGraph:
    nodes: dict[str, SNode] = field(default_factory=dict)
    rels: list[SRel] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)  # propriétés objet sans domaine ou sans image exploitable (non dessinées)
    skipped_labels: dict[str, str] = field(default_factory=dict)  # IRI → libellé, pour les prévenir dans l'interface
    count_origin: str = "none"  # provenance des effectifs : store | ontology | none


def part_kind(*names: Optional[str]) -> Optional[str]:
    for n in names:
        if not n:
            continue
        norm = re.sub(r"[^a-z0-9]+", "", n.lower())
        if PART_OF.search(norm):
            return "part_of"
        if HAS_PART.search(norm):
            return "has_part"
    return None


def namespace_of(iri: str) -> str:
    cut = max(iri.rfind("#"), iri.rfind("/"))
    return iri[:cut + 1] if cut > 0 else ""


def _ends(iri_list: list[str], union: list[str], classes: dict) -> list[str]:
    return [c for c in sorted(set(iri_list) | set(union)) if c in classes and c != OWL + "Thing"]


def from_onto(onto: OntoModel, lang: str, perimeters: Optional[list[Any]] = None) -> SchemaGraph:
    g = SchemaGraph()
    per_of: dict[str, set[str]] = {}
    for per in perimeters or []:
        cs = {c for c in per.classes if c in onto.classes}
        if per.include_descendants:
            for c in list(cs):
                cs.update(onto.descendants(c))
        for c in cs:
            per_of.setdefault(c, set()).add(per.id)
    for iri, c in onto.classes.items():
        g.nodes[iri] = SNode(id=iri, label=onto.label(iri, lang), parents=[p for p in c.sub_class_of if p in onto.classes and p != iri],
                             namespace=namespace_of(iri), perimeters=per_of.get(iri, set()),
                             abstract=False, enumerated=c.one_of is not None, sources=[iri])
    n_data: dict[str, int] = {}
    for dp in onto.datatype_properties.values():
        for d in set(dp.domain) | set(dp.domain_union):
            n_data[d] = n_data.get(d, 0) + 1
    for iri, node in g.nodes.items():
        node.n_data = n_data.get(iri, 0)
    for iri, c in onto.classes.items():
        for par in g.nodes[iri].parents:
            g.rels.append(SRel(id=f"subClassOf|{iri}|{par}", source=iri, target=par, label="subClassOf", key="subClassOf", kind="subclass"))

    pairs: dict[str, list[tuple[str, str]]] = {}
    is_union: dict[str, bool] = {}
    for piri, p in onto.object_properties.items():
        doms = _ends(p.domain, p.domain_union, onto.classes)
        rngs = _ends(p.range, p.range_union, onto.classes)
        if not doms or not rngs:
            pairs[piri] = []
            continue
        pairs[piri] = [(d, r) for d in doms for r in rngs]
        is_union[piri] = len(doms) > 1 and bool(p.domain_union) or len(rngs) > 1 and bool(p.range_union)
    inv_of: dict[str, str] = {}
    for piri, p in onto.object_properties.items():
        if p.inverse_of and p.inverse_of != piri:
            inv_of.setdefault(piri, p.inverse_of)
            inv_of.setdefault(p.inverse_of, piri)
    done: set[str] = set()
    for piri in sorted(onto.object_properties):
        if piri in done:
            continue
        p = onto.object_properties[piri]
        q = inv_of.get(piri) if inv_of.get(piri) in onto.object_properties else None
        label = onto.label(piri, lang)
        inv_label = onto.label(inv_of[piri], lang) if piri in inv_of else None
        edges = pairs[piri]
        if not edges and not (q and pairs.get(q)):
            g.skipped.append(piri)
            g.skipped_labels[piri] = label
            done.add(piri)
            continue
        if q and q != piri:
            # inverses : une arête dans le sens du nom le plus petit, fusionnée avec les arêtes de l'autre sens
            first, second = sorted((piri, q))
            if piri != first:
                continue  # traité depuis `first`
            p1, p2 = onto.object_properties[first], onto.object_properties[second]
            e1, e2 = pairs[first], pairs[second]
            merged: list[tuple[str, str]] = list(e1) + [(b, a) for a, b in e2 if (a, b) not in {(y, x) for x, y in e1}]
            for a, b in merged:
                g.rels.append(SRel(id=f"{first}|{a}|{b}", source=a, target=b, label=onto.label(first, lang), key=first,
                                   inverse_label=onto.label(second, lang), both=True,
                                   part=part_kind(local_name(first), local_name(second)), link="inverse",
                                   union=is_union.get(first, False) or is_union.get(second, False)))
            done.update((first, second))
            continue
        done.add(piri)
        sym = "symmetric" in p.characteristics
        for a, b in edges:
            g.rels.append(SRel(id=f"{piri}|{a}|{b}", source=a, target=b, label=label, key=piri,
                               both=sym or bool(piri in inv_of and not q),
                               inverse_label=inv_label if piri in inv_of and not q else None, part=part_kind(local_name(piri)),
                               link="symmetric" if sym else "inverse" if piri in inv_of and not q else None, union=is_union.get(piri, False)))
    g.rels.sort(key=lambda r: (r.kind != "subclass", r.id))
    return g


def from_pg(pg: PGModel, onto: Optional[OntoModel], perimeters: Optional[list[Any]] = None) -> SchemaGraph:
    g = SchemaGraph()
    per_of: dict[str, set[str]] = {}
    for per in perimeters or []:
        cs = {c for c in per.classes if onto and c in onto.classes}
        if per.include_descendants and onto:
            for c in list(cs):
                cs.update(onto.descendants(c))
        for c in cs:
            per_of.setdefault(c, set()).add(per.id)
    owner: dict[str, str] = {}
    for name, nt in pg.node_types.items():
        for s in nt.source:
            owner.setdefault(s, name)
    for name in sorted(pg.node_types):
        nt = pg.node_types[name]
        parents: list[str] = []
        if onto:
            for s in nt.source:
                for par in (onto.classes[s].sub_class_of if s in onto.classes else []):
                    o = owner.get(par)
                    if o and o != name and o not in parents:
                        parents.append(o)
        pers: set[str] = set()
        for s in nt.source:
            pers |= per_of.get(s, set())
        enumerated = bool(onto and nt.source and all(s in onto.classes and onto.classes[s].one_of is not None for s in nt.source))
        g.nodes[name] = SNode(id=name, label=name, parents=parents, namespace=namespace_of(nt.source[0]) if nt.source else "",
                              perimeters=pers, abstract=nt.abstract, enumerated=enumerated, sources=list(nt.source),
                              n_data=len(nt.properties))
    edges = [e for e in pg.edge_types if e.from_ in g.nodes and e.to in g.nodes]
    by_name = {}
    for e in edges:
        by_name.setdefault(e.name, []).append(e)
    consumed: set[int] = set()
    for i, e in enumerate(edges):
        if i in consumed:
            continue
        both = bool(e.symmetric)
        link = "symmetric" if both else None
        inv = e.reverse
        # un type d'arête distinct, de sens contraire et nommé comme l'inverse, est fusionné avec celui-ci
        if inv and inv != e.name:
            for j, f in enumerate(edges):
                if j != i and j not in consumed and f.name == inv and f.from_ == e.to and f.to == e.from_:
                    consumed.add(j)
                    both = True
                    link = "inverse"
                    break
        g.rels.append(SRel(id=f"{e.name}|{e.from_}|{e.to}", source=e.from_, target=e.to, label=e.name, key=e.name, both=both,
                           inverse_label=inv, part=part_kind(e.name, inv), link=link))
    g.rels.sort(key=lambda r: r.id)
    return g


def link_weights(g: SchemaGraph) -> dict[tuple[str, str], int]:
    """Poids des liens non orientés entre deux nœuds (nombre de relations ; la hiérarchie compte aussi)."""
    w: dict[tuple[str, str], int] = {}
    for r in g.rels:
        if r.source == r.target or r.source not in g.nodes or r.target not in g.nodes:
            continue
        k = (r.source, r.target) if r.source < r.target else (r.target, r.source)
        w[k] = w.get(k, 0) + 1
    return w
