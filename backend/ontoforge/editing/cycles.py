"""Cycles de sous-classes : détection à la saisie (DSL de saisie rapide, /ops) et message commun.

Un cycle A ⊑ B ⊑ … ⊑ A rend toutes ses classes équivalentes en OWL 2 : presque toujours une erreur de saisie, et un cas que
le moteur de transposition ne sait pas aplatir. La saisie le refuse ; l'analyse, elle, doit supporter un cycle déjà présent
(import, ancien projet) et le signaler (:func:`find_cycles`).
"""
from __future__ import annotations

from typing import Optional

from ..core.onto_model import OntoModel, local_name


def subclass_path(onto: OntoModel, start: str, goal: str) -> Optional[list[str]]:
    """Plus court chemin ``start → … → goal`` en remontant ``sub_class_of`` (classes déclarées seulement), ou ``None``."""
    if start == goal:
        return [start]
    prev: dict[str, Optional[str]] = {start: None}
    queue = [start]
    while queue:
        cur = queue.pop(0)
        for par in onto.classes[cur].sub_class_of if cur in onto.classes else ():
            if par in prev or par not in onto.classes:
                continue
            prev[par] = cur
            if par == goal:
                out = [par]
                while prev[out[-1]] is not None:
                    out.append(prev[out[-1]])  # type: ignore[arg-type]
                return out[::-1]
            queue.append(par)
    return None


def closing_path(onto: OntoModel, child: str, parent: str) -> Optional[list[str]]:
    """Chemin ``parent → … → child`` qui existe déjà si déclarer ``child ⊑ parent`` fermerait un cycle, sinon ``None``."""
    return subclass_path(onto, parent, child)


def cycle_message(child: str, parent: str, path: list[str]) -> str:
    """Message français (traduit en anglais à la frontière HTTP par ``localize.tr``) ; noms locaux entre « »."""
    c, p = local_name(child), local_name(parent)
    if child == parent:
        return "Cycle de sous-classes : une classe ne peut pas être sa propre sous-classe"
    chain = " → ".join(local_name(x) for x in path)
    return f"Cycle de sous-classes : « {p} » descend déjà de « {c} » ({chain}) ; « {c} < {p} » fermerait la boucle."


def find_cycles(onto: OntoModel) -> list[list[str]]:
    """Groupes de classes qui se contiennent mutuellement (composantes fortement connexes non triviales), triés."""
    graph = {c.iri: [p for p in c.sub_class_of if p in onto.classes] for c in onto.classes.values()}
    index: dict[str, int] = {}
    low: dict[str, int] = {}
    on: set[str] = set()
    stack: list[str] = []
    res: list[list[str]] = []
    counter = 0
    for root in sorted(graph):  # Tarjan itératif : pas de limite de récursion sur une grande ontologie
        if root in index:
            continue
        work = [(root, iter(graph[root]))]
        index[root] = low[root] = counter
        counter += 1
        stack.append(root)
        on.add(root)
        while work:
            v, it = work[-1]
            advanced = False
            for w in it:
                if w not in index:
                    index[w] = low[w] = counter
                    counter += 1
                    stack.append(w)
                    on.add(w)
                    work.append((w, iter(graph[w])))
                    advanced = True
                    break
                if w in on:
                    low[v] = min(low[v], index[w])
            if advanced:
                continue
            work.pop()
            if work:
                u = work[-1][0]
                low[u] = min(low[u], low[v])
            if low[v] == index[v]:
                comp = []
                while True:
                    w = stack.pop()
                    on.discard(w)
                    comp.append(w)
                    if w == v:
                        break
                if len(comp) > 1 or v in graph[v]:
                    res.append(sorted(comp))
    return sorted(res)
