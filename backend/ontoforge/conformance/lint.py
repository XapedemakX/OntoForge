"""Lint d'ontologie : règles de conformité W01–W07 et bonnes pratiques (BP01–BP07).

W01–W05 sont calculées par profiles.dl_issues (contrôles structurels OWL 2 DL) ; W06 (insatisfiabilité)
par reasoner.py ; W07 (labels fr/en, versionIRI, préfixes) est ici. Les BP sont des constats « info » ou
« warning », jamais bloquants.
"""
from __future__ import annotations

import re
from typing import Optional

import rdflib

from ..core.onto_model import OWL, RDFS, OntoModel, local_name
from .report import Issue

LANGS = ("fr", "en")
SS = "OWL 2 Structural Specification"
STANDARD_PREFIXES = {
    "http://www.w3.org/1999/02/22-rdf-syntax-ns#": "rdf", "http://www.w3.org/2000/01/rdf-schema#": "rdfs",
    "http://www.w3.org/2002/07/owl#": "owl", "http://www.w3.org/2001/XMLSchema#": "xsd",
    "http://www.w3.org/2004/02/skos/core#": "skos", "http://purl.org/dc/terms/": "dcterms",
    "http://purl.org/dc/elements/1.1/": "dc", "http://xmlns.com/foaf/0.1/": "foaf",
    "http://www.w3.org/ns/prov#": "prov", "http://www.w3.org/ns/shacl#": "sh", "https://schema.org/": "schema",
}


def _entities(o: OntoModel):
    for kind, coll in (("classe", o.classes), ("propriété objet", o.object_properties),
                       ("propriété de données", o.datatype_properties),
                       ("propriété d'annotation", o.annotation_properties)):
        for e in coll.values():
            yield kind, e


def lint(onto: OntoModel, graph: Optional[rdflib.Graph] = None, *, include_dl: bool = True) -> list[Issue]:
    out: list[Issue] = []
    if include_dl:
        from .profiles import _graph_of, dl_issues
        out.extend(dl_issues(graph if graph is not None else _graph_of(onto)))

    # --- W07 : labels, versionIRI, préfixes
    for kind, e in _entities(onto):
        if e.iri.startswith(tuple(STANDARD_PREFIXES) + ("http://purl.org/vocab/vann/",)):
            continue  # vocabulaire réutilisé, pas une entité de l'ontologie
        miss = [lg for lg in LANGS if lg not in e.labels]
        if miss:
            out.append(Issue(level="warning", code="W07", subject=e.iri, spec_ref="Bonnes pratiques (rdfs:label)",
                             message=f"{kind.capitalize()} {local_name(e.iri)} : label manquant en {' et '.join(miss)}."))
    if not onto.meta.version_iri:
        out.append(Issue(level="warning", code="W07", subject=onto.meta.iri or None, spec_ref=f"{SS} §3.1 (owl:versionIRI)",
                         message="L'ontologie n'a pas d'owl:versionIRI : les versions ne sont pas identifiables."))
    prefixes = dict(onto.meta.prefixes)
    if graph is not None:
        prefixes.update({p: str(n) for p, n in graph.namespaces() if p})
    for pre, ns in prefixes.items():
        std = STANDARD_PREFIXES.get(ns)
        if std and pre != std:
            out.append(Issue(level="warning", code="W07", subject=ns, spec_ref="Bonnes pratiques (préfixes)",
                             message=f"Le préfixe « {pre} » désigne l'espace de noms standard {std}: : utiliser « {std} »."))

    # --- BP01 classes orphelines
    used: set[str] = set()
    for p in list(onto.object_properties.values()) + list(onto.datatype_properties.values()):
        used.update(p.domain + p.domain_union)
        if hasattr(p, "range"):
            used.update(r for r in p.range if r in onto.classes)
    for c in onto.classes.values():
        used.update(r.filler for r in c.restrictions if r.filler)
    for i in onto.individuals.values():
        used.update(i.types)
    for c in onto.classes.values():
        parents = [p for p in c.sub_class_of if p != OWL + "Thing"]
        if not parents and not onto.children(c.iri) and c.iri not in used and not c.equivalent_to \
                and not c.restrictions and not c.super_expressions:
            out.append(Issue(level="info", code="BP01", subject=c.iri, spec_ref="Bonnes pratiques",
                             message=f"La classe {local_name(c.iri)} est orpheline : sans parent, enfant, propriété ni individu."))
    # --- BP02 propriétés sans domaine / portée
    for p in onto.object_properties.values():
        if not (p.domain or p.domain_union or p.domain_expr) or not (p.range or p.range_union or p.range_expr):
            out.append(Issue(level="info", code="BP02", subject=p.iri, spec_ref="Bonnes pratiques",
                             message=f"La propriété objet {local_name(p.iri)} n'a pas de {'domaine' if not (p.domain or p.domain_union or p.domain_expr) else 'portée'}."))
    for p in onto.datatype_properties.values():
        if not (p.domain or p.domain_union or p.domain_expr) or not (p.range or p.range_expr):
            out.append(Issue(level="info", code="BP02", subject=p.iri, spec_ref="Bonnes pratiques",
                             message=f"La propriété de données {local_name(p.iri)} n'a pas de {'domaine' if not (p.domain or p.domain_union or p.domain_expr) else 'portée'}."))
    # --- BP03 cycles de sous-classes
    for cyc in _cycles({c.iri: [p for p in c.sub_class_of if p in onto.classes] for c in onto.classes.values()}):
        out.append(Issue(level="warning", code="BP03", subject=cyc[0], spec_ref=f"{SS} §9.1 (SubClassOf)",
                         message="Cycle de sous-classes " + " → ".join(local_name(x) for x in cyc + [cyc[0]])
                                 + " : ces classes sont équivalentes, ce qui est rarement voulu."))
    # --- BP04 labels dupliqués
    seen: dict[tuple[str, str], list[str]] = {}
    for kind, e in _entities(onto):
        for lg, txt in e.labels.items():
            lst = seen.setdefault((lg, txt.strip().lower()), []); lst.append(e.iri) if e.iri not in lst else None
    for (lg, txt), iris in seen.items():
        if len(iris) > 1 and txt:
            out.append(Issue(level="warning", code="BP04", subject=iris[0], spec_ref="Bonnes pratiques",
                             message=f"Le label « {txt} » ({lg or 'sans langue'}) est partagé par {', '.join(local_name(i) for i in iris)}."))
    # --- BP05 imports non résolus (travail hors-ligne)
    for imp in onto.meta.imports:
        out.append(Issue(level="info", code="BP05", subject=imp, spec_ref=f"{SS} §3.4 (owl:imports)",
                         message=f"L'import {imp} n'est pas résolu hors-ligne : ses axiomes ne sont pas analysés."))
    # --- BP06 entités dépréciées utilisées comme parent
    for c in onto.classes.values():
        for p in c.sub_class_of:
            if p in onto.classes and onto.classes[p].deprecated and not c.deprecated:
                out.append(Issue(level="warning", code="BP06", subject=c.iri, spec_ref="Bonnes pratiques (owl:deprecated)",
                                 message=f"{local_name(c.iri)} hérite de {local_name(p)}, qui est dépréciée."))
    # --- BP07 conventions de nommage
    for c in onto.classes.values():
        n = local_name(c.iri)
        if n and (not n[0].isupper() or "_" in n):
            out.append(Issue(level="info", code="BP07", subject=c.iri, spec_ref="Bonnes pratiques (nommage)",
                             message=f"Le nom de classe {n} devrait être en PascalCase, sans « _ »."))
    for p in list(onto.object_properties.values()) + list(onto.datatype_properties.values()):
        n = local_name(p.iri)
        if n and (not n[0].islower() or re.search(r"[_\s]", n)):
            out.append(Issue(level="info", code="BP07", subject=p.iri, spec_ref="Bonnes pratiques (nommage)",
                             message=f"Le nom de propriété {n} devrait être en camelCase, sans « _ »."))
    return out


def _cycles(graph: dict[str, list[str]]) -> list[list[str]]:
    """Composantes fortement connexes non triviales (algorithme de Tarjan itératif simplifié)."""
    idx, low, on, stack, res, counter = {}, {}, set(), [], [], [0]

    def strong(v):
        idx[v] = low[v] = counter[0]; counter[0] += 1
        stack.append(v); on.add(v)
        for w in graph.get(v, []):
            if w not in idx:
                strong(w); low[v] = min(low[v], low[w])
            elif w in on:
                low[v] = min(low[v], idx[w])
        if low[v] == idx[v]:
            comp = []
            while True:
                w = stack.pop(); on.discard(w); comp.append(w)
                if w == v:
                    break
            if len(comp) > 1 or v in graph.get(v, []):
                res.append(sorted(comp))

    import sys
    sys.setrecursionlimit(max(1000, sys.getrecursionlimit()))
    for v in graph:
        if v not in idx:
            strong(v)
    return res
