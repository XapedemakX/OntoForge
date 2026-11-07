"""Valeurs possibles connues SANS endpoint (L17) : individus des classes énumérées ou peuplées, `sh:in`, DataOneOf, enum du PGModel.

Sert la route `GET /query/options` (CONTRACTS §6) : listes à cocher et autocomplétion dans le requêtage guidé.
"""
from __future__ import annotations

from typing import Any, Optional

from ..core.onto_model import OntoModel, local_name
from ..core.pg_model import PGModel
from ..core.shapes_model import ShapesModel

MAX_VALUES = 500


def _enum_members(o: OntoModel, c: str) -> list[str]:
    """Individus déclarés par owl:oneOf pour la classe (équivalence, `one_of` ou superclasse anonyme)."""
    cl = o.classes.get(c)
    if cl is None:
        return []
    out: list[str] = list(cl.one_of or [])
    for e in [*cl.equivalent_to, *cl.super_expressions]:
        if e.op == "oneOf":
            out.extend(e.individuals)
    return out


def class_individuals(o: OntoModel, c: str, lang: str = "fr", with_subclasses: bool = True) -> dict[str, Any]:
    """Individus connus d'une classe : membres de la classe énumérée + individus typés (sous-classes comprises)."""
    classes = {c, *(o.descendants(c) if with_subclasses else [])}
    members: list[str] = []
    enumerated = False
    for k in classes:
        m = _enum_members(o, k)
        if m:
            enumerated = enumerated or k == c
            members.extend(m)
    members.extend(i for i, ind in o.individuals.items() if classes & set(ind.types))
    uniq = list(dict.fromkeys(members))
    vals = [{"value": i, "label": o.label(i, lang), "is_iri": True, "source": "enum" if i in _enum_members(o, c) else "individual"}
            for i in uniq]
    vals.sort(key=lambda v: (v["label"].lower(), v["value"]))
    return {"values": vals, "enumerated": enumerated}


def known_count(o: OntoModel, c: str) -> int:
    return len(class_individuals(o, c)["values"])


def _lit(v: Any) -> tuple[str, Optional[str]]:
    if hasattr(v, "value"):
        return str(v.value), getattr(v, "lang", None)
    return str(v), None


def data_values(o: OntoModel, shapes: Optional[ShapesModel], pg: Optional[PGModel], cls: Optional[str], prop: str) -> list[dict[str, Any]]:
    """Valeurs permises d'une propriété de données : `sh:in` des shapes, DataOneOf (propriété ou datatype), enum du PGModel."""
    out: list[dict[str, Any]] = []

    def add(val: str, src: str, lang: Optional[str] = None) -> None:
        out.append({"value": val, "label": val, "is_iri": False, "lang": lang, "source": src})

    scope = {cls, *o.ancestors(cls)} if cls else set()
    if shapes is not None:
        for sh in shapes.shapes.values():
            tg = set(sh.targets.target_class)
            if scope and tg and not (tg & scope):
                continue
            for ps in sh.properties:
                if ps.path.kind == "predicate" and ps.path.iri == prop and not getattr(ps, "deactivated", False):
                    for v in ps.in_:
                        add(*_lit(v)[:1], "sh:in", _lit(v)[1])
    dp = o.datatype_properties.get(prop)
    if dp is not None:
        if dp.range_expr is not None:
            for v in dp.range_expr.one_of:
                add(*_lit(v)[:1], "DataOneOf", _lit(v)[1])
        for r in dp.range:
            dd = o.datatypes.get(r)
            if dd and dd.definition:
                for v in dd.definition.one_of:
                    add(*_lit(v)[:1], "DataOneOf", _lit(v)[1])
    if pg is not None:
        for nt in pg.node_types.values():
            if cls and cls not in nt.source:
                continue
            for pp in nt.properties:
                if pp.source == prop and pp.enum:
                    for v in pp.enum:
                        add(str(v), "PGModel")
    seen: set[str] = set()
    uniq = []
    for v in out:
        if v["value"] not in seen:
            seen.add(v["value"])
            uniq.append(v)
    return uniq


def options(o: OntoModel, shapes: Optional[ShapesModel], pg: Optional[PGModel], cls: Optional[str], prop: Optional[str],
            q: str = "", lang: str = "fr") -> dict[str, Any]:
    """Valeurs connues de l'ontologie pour (classe) ou (classe, propriété)."""
    vals: list[dict[str, Any]] = []
    enumerated = False
    kind = "class"
    if prop and prop in o.datatype_properties:
        kind = "data"
        vals = data_values(o, shapes, pg, cls, prop)
        enumerated = bool(vals)
    elif prop and prop in o.object_properties:
        kind = "object"
        op = o.object_properties[prop]
        for r in op.range or op.range_union:
            ci = class_individuals(o, r, lang)
            vals += ci["values"]
            enumerated = enumerated or ci["enumerated"]
    elif cls:
        ci = class_individuals(o, cls, lang)
        vals, enumerated = ci["values"], ci["enumerated"]
        if prop:  # libellé (rdfs:label, skos:prefLabel…) ou propriété annotée : on propose les libellés des individus connus
            kind = "label"
            seen: set[str] = set()
            lab: list[dict[str, Any]] = []
            for v in vals:
                ind = o.individuals.get(v["value"])
                texts = list((ind.labels if ind else {}).values()) or [v["label"]]
                for tx in texts:
                    if tx not in seen:
                        seen.add(tx)
                        lab.append({"value": tx, "label": tx, "is_iri": False, "source": v["source"]})
            vals = sorted(lab, key=lambda x: x["label"].lower())
    needle = q.strip().lower()
    if needle:
        vals = [v for v in vals if needle in v["label"].lower() or needle in v["value"].lower()]
    total = len(vals)
    return {"class": cls, "property": prop, "kind": kind, "known_count": total, "enumerated": enumerated,
            "values": vals[:MAX_VALUES], "truncated": total > MAX_VALUES}
