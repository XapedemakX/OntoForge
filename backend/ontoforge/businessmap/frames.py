"""Cadres : groupes de types qui partagent au moins deux relations identiques vers les mêmes cibles.

Un cadre se dessine comme un rectangle autour de ses membres ; les relations que *tous* ses membres ont vers la même cible
sont remplacées par une seule arête partant du cadre (« arête de cadre »).
"""
from __future__ import annotations

from typing import Iterable

from .graph import SchemaGraph, SRel
from .model import Frame

MIN_SHARED = 2
MIN_MEMBERS = 2


def signatures(g: SchemaGraph) -> dict[str, set[tuple[str, str]]]:
    """Pour chaque type : l'ensemble des (relation, cible) sortantes. Hors hiérarchie, hors boucles."""
    sig: dict[str, set[tuple[str, str]]] = {k: set() for k in g.nodes}
    for r in g.rels:
        if r.kind != "relation" or r.source == r.target or r.source not in g.nodes or r.target not in g.nodes:
            continue
        sig[r.source].add((r.key, r.target))
    return sig


def suggest(g: SchemaGraph) -> list[dict]:
    """[{members, shared: [(relation, cible)]}] triés du plus partagé au moins partagé ; un type n'est que dans un seul cadre."""
    sig = signatures(g)
    ids = sorted(k for k, s in sig.items() if len(s) >= MIN_SHARED)
    cands: dict[frozenset, set[str]] = {}
    for i, a in enumerate(ids):
        for b in ids[i + 1:]:
            common = frozenset(sig[a] & sig[b])
            if len(common) >= MIN_SHARED:
                cands[common] = set()
    for common in cands:
        cands[common] = {k for k in ids if common <= sig[k]}
    groups = [(common, ms) for common, ms in cands.items() if len(ms) >= MIN_MEMBERS]
    # on garde le groupe le plus riche (membres × relations communes) puis on retire ses membres des suivants
    groups.sort(key=lambda t: (-len(t[1]) * len(t[0]), -len(t[0]), sorted(t[1])))
    taken: set[str] = set()
    out: list[dict] = []
    for common, ms in groups:
        free = sorted(ms - taken)
        if len(free) < MIN_MEMBERS:
            continue
        shared = sorted(set.intersection(*(sig[k] for k in free)))
        if len(shared) < MIN_SHARED:
            continue
        taken.update(free)
        out.append({"members": free, "shared": shared})
    return out


def describe(found: Iterable[dict], g: SchemaGraph, lang: str) -> list[Frame]:
    frames: list[Frame] = []
    label_of = {r.key: r.label for r in g.rels}
    for i, f in enumerate(found, 1):
        names = [g.nodes[m].label for m in f["members"]]
        title = " · ".join(names[:4]) + (f" · +{len(names) - 4}" if len(names) > 4 else "")
        shared = ", ".join(f"{label_of.get(k, k)} → {g.nodes[t].label}" for k, t in f["shared"][:4])
        note = ("Partagent : " if lang == "fr" else "Share: ") + shared
        frames.append(Frame(id=f"frame-{i}", title=title, members=list(f["members"]), note=note))
    return frames


def frame_edges(frame: Frame, g: SchemaGraph) -> list[tuple[SRel, list[SRel]]]:
    """Relations communes à tous les membres du cadre vers une même cible : [(relation représentative, relations remplacées)]."""
    members = [m for m in frame.members if m in g.nodes]
    if len(members) < MIN_MEMBERS:
        return []
    by: dict[tuple[str, str], dict[str, SRel]] = {}
    for r in g.rels:
        if r.kind == "relation" and r.source in members and r.source != r.target:
            by.setdefault((r.key, r.target), {})[r.source] = r
    out = []
    for (_, tgt), per in sorted(by.items()):
        if len(per) == len(members) and tgt not in members:
            out.append((per[members[0]], [per[m] for m in members]))
    return out
