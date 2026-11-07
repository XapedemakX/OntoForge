"""Noms lisibles pour les arêtes retour sans owl:inverseOf (cibles à reverse obligatoire : Curiosity).

Règles simples, dans l'ordre (``edge`` en PascalCase, ``source`` = type de départ de l'arête) :

1. ``HasX`` -> ``XOf`` ; ``IsXOf`` / ``XOf`` -> ``HasX`` (déjà gérées par le profil).
2. Verbe à la 3e personne suivi d'un objet éventuel (``Covers``, ``UsesPart``, ``Prescribes``)
   -> participe passé + ``By`` : ``CoveredBy``, ``UsedBy``, ``PrescribedBy``.
3. Participe ou verbe suivi d'une préposition (``OwnedBy``, ``AssignedTo``, ``InstalledIn``,
   ``PerformedAt``, ``WorksAt``, ``PlannedFor``) -> ``Has<Source>`` : le type d'arrivée « a » les sources
   (Customer ``HasVehicle``, Garage ``HasRepairOrder``).
4. Sinon -> ``<Nom>Of<Source>`` (``Foo`` -> ``FooOfBar``).

Cas particuliers : ``XxxTransitive`` -> retour de ``Xxx`` + ``Transitive`` ; préposition en tête ou en queue -> règle 3.
Collisions (même type d'arrivée, ou une arête sortante du même nom) : ``<Arête>Of<Source>``, puis un entier.
"""
from __future__ import annotations

import re
from typing import Iterable

PREPOSITIONS = ("To", "In", "At", "For", "On", "From", "With", "By", "Of", "Into", "Over", "Under", "Within")


def _words(name: str) -> list[str]:
    return re.findall(r"[A-Z]+(?=[A-Z][a-z]|\d|$)|[A-Z]?[a-z]+|\d+", name)


def _participle(verb_s: str) -> str:
    """Applies -> Applied, Includes -> Included, Addresses -> Addressed, Covers -> Covered."""
    low = verb_s
    if low.endswith("ies") and len(low) > 4:
        return low[:-3] + "ied"
    if re.search(r"(ss|x|ch|sh|zz)es$", low):
        return low[:-2] + "ed"
    if low.endswith("es") and len(low) > 3 and not low.endswith(("ees", "oes")):
        return low[:-1] + "d"
    return low[:-1] + "ed"


def derive_reverse(edge: str, source: str) -> str:
    """Nom lisible de l'arête retour de ``edge`` (aucun inverse OWL), partant de ``source``."""
    if edge.endswith("Transitive") and len(edge) > 10:  # fermeture dérivée : retour de la relation de base
        return derive_reverse(edge[:-10], source) + "Transitive"
    w = _words(edge)
    if not w:
        return f"{edge}Of{source}"
    first, rest = w[0], w[1:]
    m = re.fullmatch(r"Has([A-Z0-9].*)", edge)
    if m:
        return f"{m.group(1)}Of"
    m = re.fullmatch(r"Is([A-Z0-9].*)Of", edge) or re.fullmatch(r"([A-Z0-9].*)Of", edge)
    if m:
        return f"Has{m.group(1)}"
    is_past = first.endswith("ed") and len(first) > 3
    is_verb_s = (first.endswith("s") and not first.endswith(("ss", "us", "is")) and len(first) > 3
                 and first not in ("Has", "Is"))
    if first in PREPOSITIONS or (rest and rest[-1] in PREPOSITIONS) or (rest and rest[0] in PREPOSITIONS):
        return f"Has{source}"
    if is_past and not rest:
        return f"Has{source}"
    if is_verb_s:
        return _participle(first) + "By"
    if first == "Made":
        return f"Has{source}"
    return f"{edge}Of{source}"


def uniquify_reverses(edges: Iterable, *, is_default, reserved: Iterable[str] = ()) -> None:
    """Remplace les retours par défaut (``is_default(e)``) par un nom dérivé, sans collision par type d'arrivée."""
    edges = list(edges)
    # Noms de propriétés OWL (insensibles à la casse) : un reverse dérivé ne doit jamais en usurper un
    # (revue w3c L13). Les inverses déclarés sont des retours explicites, donc non concernés.
    forbidden = {r.lower() for r in reserved} | {e.name.lower() for e in edges}
    forbidden |= {e.reverse.lower() for e in edges if e.reverse and not is_default(e)}
    taken: dict[str, set[str]] = {}
    for e in edges:  # noms déjà pris : arêtes sortantes du type + retours explicites
        taken.setdefault(e.from_, set()).add(e.name)
        if e.reverse and not is_default(e):
            taken.setdefault(e.to, set()).add(e.reverse)
    for e in sorted((x for x in edges if is_default(x)), key=lambda x: (x.to, x.name, x.from_)):
        names = taken.setdefault(e.to, set())
        cand = derive_reverse(e.name, e.from_)
        base, n = cand, 2
        if cand in names or cand.lower() in forbidden:
            cand = f"{e.name}Of{e.from_}"
            base = cand
        while cand in names:
            cand, n = f"{base}{n}", n + 1
        names.add(cand)
        e.reverse = cand
