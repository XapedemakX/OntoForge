"""Registre des règles de transposition OWL 2 / SHACL → LPG (une famille par module).

`REGISTRY[rule_id]` → RuleInfo : métadonnées (catalog.py), détection pure `detect(ctx) -> list[Finding]`,
application `plan(ctx, finding, option)` (phase 10 : disposition) et/ou `build(ctx, finding, option)`
(après construction des nœuds / propriétés / relations : propriétés, validations, matérialisations).
Les 66 règles de transposition (D-031) sont implémentées ; S01, S02, G02 sont des règles d'outillage.
"""

from dataclasses import dataclass
from typing import Callable, Optional

from . import annotations as annotations_rules, catalog, classes, data, individuals, keys, naming, objects, reification, shacl


@dataclass(frozen=True)
class RuleInfo:
    id: str
    family: str
    module: str
    detect: Callable
    plan: Optional[Callable]
    build: Optional[Callable]
    implemented: bool
    it1: bool
    meta: dict


MODULES = (classes, keys, data, objects, reification, annotations_rules, individuals, naming, shacl)


def _build() -> dict[str, RuleInfo]:
    reg: dict[str, RuleInfo] = {}
    for mod in MODULES:
        detects = dict(getattr(mod, "DETECT", {}))
        detects.update(getattr(mod, "DETECT_LAST", {}))
        for rid, fn in detects.items():
            reg[rid] = RuleInfo(rid, catalog.RULES[rid]["family"], mod.__name__.rsplit(".", 1)[1], fn,
                                getattr(mod, "APPLY_PLAN", {}).get(rid), getattr(mod, "APPLY_BUILD", {}).get(rid),
                                True, rid in catalog.IT1, catalog.RULES[rid])
    return dict(sorted(reg.items()))


REGISTRY: dict[str, RuleInfo] = _build()
LAST = {"G01"}  # détections qui lisent ce que les autres règles ont consommé
TRANSPOSITION = [r for r in REGISTRY if r in catalog.TRANSPOSITION_RULES]
EXTRA = sorted(set(catalog.RULES) - set(catalog.TRANSPOSITION_RULES))
assert sorted(TRANSPOSITION) == sorted(catalog.TRANSPOSITION_RULES), \
    set(catalog.TRANSPOSITION_RULES) - set(TRANSPOSITION)


def rules_table() -> list[dict]:
    """Vue sérialisable du registre (front / RULES.md)."""
    return [{"id": r.id, "family": r.family, "construct": r.meta["construct"], "severity": r.meta["severity"],
             "title": r.meta["title"], "implemented": r.implemented, "it1": r.it1,
             "options": list(r.meta["options"]), "recommended": r.meta["reco"]} for r in REGISTRY.values()]
