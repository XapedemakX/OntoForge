"""Raisonnement : OWL RL (owlrl) avec contournement du bug prp-key ; HermiT est dans conformance/hermit.py. Jamais bloquant.

Bug owlrl 7.1.2 (OWLRL.py, règle prp-key) : la boucle `range(0, len(pis) - 1)` ignore la dernière propriété
de la clé ; avec `owl:hasKey (p)` tous les individus du type deviennent owl:sameAs. Contournement : retirer
les axiomes hasKey du graphe avant DeductiveClosure et appliquer prp-key ici (OWL 2 RL, tableau 7).
"""
from __future__ import annotations

import threading
from typing import Optional

import rdflib
from rdflib import BNode, URIRef
from rdflib.namespace import OWL, RDF, RDFS

from .report import ReasonerInfo


def rdf_list(g, head) -> list:
    out, seen = [], set()
    while head is not None and head != RDF.nil and head not in seen:
        seen.add(head)
        f = g.value(head, RDF.first)
        if f is not None:
            out.append(f)
        head = g.value(head, RDF.rest)
    return out


def apply_prp_key(g: rdflib.Graph, keys: list[tuple[object, list]]) -> int:
    """prp-key : x, y de type C (individus nommés) partageant une valeur pour chaque propriété de la clé → x owl:sameAs y."""
    added = 0
    for cls, props in keys:
        if not props:
            continue
        members = [m for m in g.subjects(RDF.type, cls) if isinstance(m, URIRef)]
        vals = {m: [set(g.objects(m, p)) for p in props] for m in members}
        index: dict[object, list] = {}
        for m, vs in vals.items():
            if all(vs):
                for v in vs[0]:
                    index.setdefault(v, []).append(m)
        for group in index.values():
            for i, x in enumerate(group):
                for y in group[i + 1:]:
                    if x != y and all(vals[x][k] & vals[y][k] for k in range(len(props))):
                        for a, b in ((x, y), (y, x)):
                            if (a, OWL.sameAs, b) not in g:
                                g.add((a, OWL.sameAs, b)); added += 1
    return added


def _owlrl(g: rdflib.Graph, info: ReasonerInfo) -> None:
    import owlrl
    from owlrl.Namespaces import ERRNS

    work = rdflib.Graph()
    for t in g:
        work.add(t)
    keys = []
    for c, h in list(work.subject_objects(OWL.hasKey)):
        keys.append((c, [p for p in rdf_list(work, h) if isinstance(p, URIRef)]))
        work.remove((c, OWL.hasKey, h))
    owlrl.DeductiveClosure(owlrl.OWLRL_Semantics, axiomatic_triples=False, datatype_axioms=False).expand(work)
    if keys and apply_prp_key(work, keys):
        owlrl.DeductiveClosure(owlrl.OWLRL_Semantics, axiomatic_triples=False, datatype_axioms=False).expand(work)
        info.notes.append("prp-key appliqué par OntoForge (contournement du bug owlrl 7.1.2).")
    errors = sorted({str(o) for o in work.objects(None, ERRNS.error)})
    info.consistent = not errors
    info.notes.extend(f"Incohérence OWL RL : {e}" for e in errors[:10])
    info.unsatisfiable = _unsat(work, g)
    info.used = "owlrl"


def _unsat(closure: rdflib.Graph, original: rdflib.Graph) -> list[str]:
    """Classes nommées insatisfiables, dérivables de la clôture RL : ⊑ owl:Nothing, deux ancêtres disjoints,
    ou un ancêtre et son complément. (Heuristique complète pour la disjonction ; pas de raisonnement sur les restrictions.)"""
    named = {c for c in closure.subjects(RDF.type, OWL.Class) if isinstance(c, URIRef)}
    disj: set[tuple] = set()
    for a, b in closure.subject_objects(OWL.disjointWith):
        disj.add((a, b)); disj.add((b, a))
    for s in closure.subjects(RDF.type, OWL.AllDisjointClasses):
        m = rdf_list(closure, closure.value(s, OWL.members))
        for i, a in enumerate(m):
            for b in m[i + 1:]:
                disj.add((a, b)); disj.add((b, a))
    comp = {(a, b) for a, b in closure.subject_objects(OWL.complementOf)}
    comp |= {(b, a) for a, b in comp}
    out = []
    for c in sorted(named, key=str):
        if c == OWL.Nothing:
            continue
        anc = {c} | set(closure.objects(c, RDFS.subClassOf)) | set(closure.objects(c, OWL.equivalentClass)) \
            | set(closure.subjects(OWL.equivalentClass, c))
        if OWL.Nothing in anc or any((a, b) in disj or (a, b) in comp for a in anc for b in anc):
            out.append(str(c))
    return out


def reason(g: rdflib.Graph, *, hermit: bool = False, timeout: float = 30.0) -> ReasonerInfo:
    """OWL RL (fil daemon, délai `timeout`) puis HermiT optionnel. Retourne toujours un ReasonerInfo."""
    info = ReasonerInfo()
    box: dict = {}

    def run():
        try:
            _owlrl(g, info)
        except Exception as e:  # noqa: BLE001
            box["err"] = e

    t = threading.Thread(target=run, daemon=True)
    t.start()
    t.join(timeout)
    if t.is_alive():
        info.notes.append(f"OWL RL : délai de {timeout:.0f} s dépassé, raisonnement abandonné.")
        info.used, info.consistent = "none", None
        return info
    if "err" in box:
        info.notes.append(f"OWL RL indisponible : {type(box['err']).__name__}: {box['err']}")
        return info
    if hermit:
        # SEC-21 : l ancien chargement par fichier local via owlready2 (sans retrait des owl:imports) est supprimé ; HermiT passe par conformance.hermit.
        info.notes.append("HermiT : utilisez le raisonneur dédié (conformance.hermit), qui retire les owl:imports avant l'exécution.")
    return info
