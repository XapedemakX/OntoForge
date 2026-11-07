"""SHACL → contraintes utiles au moteur de mapping property graph (consommé par mapping/engine.py, L3).

`shape_constraints(shapes)` indexe les contraintes **par classe cible puis par prédicat**.
`hints(shapes)` en donne une vue aplatie (une entrée par couple classe × propriété) — interface
prévue dans lots/L2.md (`PGHint`).

Classement des contraintes côté cible (voir skills/shacl-modeling/SKILL.md §5) :
- Neo4j natif : minCount ≥ 1 → contrainte d'existence (`IS NOT NULL`, Enterprise) ; datatype → contrainte de
  type de propriété (`IS :: INTEGER`…, Neo4j 5.9+ Enterprise — À VÉRIFIER selon l'édition) ; clé
  (min=max=1 + unicité) → NODE KEY / UNIQUE. Le reste (maxCount, sh:in, pattern, plages, class sur arête,
  lessThan, closed, qualifiées, logiques) → requêtes Cypher de validation.
- Curiosity : maxCount 1 → propriété scalaire, sinon liste ; sh:in → enum / nœuds de référence ;
  le reste → contrôles dans le connecteur (validation applicative).
"""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field

from ..core.onto_model import LiteralValue
from ..core.shapes_model import NodeShape, Path, PropertyShape, ShapesModel
from .export_shapes import path_to_sparql

_SEV_RANK = {"Info": 0, "Warning": 1, "Violation": 2}


def _val(v: LiteralValue | str) -> Any:
    return v.model_dump(exclude_none=True) if isinstance(v, LiteralValue) else v


def _empty_prop(pred: str, inverse: bool) -> dict:
    return {
        "predicate": pred, "inverse": inverse,
        "min_count": None, "max_count": None, "required": False, "list": True,
        "datatype": [], "class": [], "node_kind": None, "node": [], "in": [], "has_value": [],
        "pattern": [], "min_length": None, "max_length": None,
        "min_inclusive": None, "max_inclusive": None, "min_exclusive": None, "max_exclusive": None,
        "language_in": [], "unique_lang": False,
        "equals": [], "disjoint": [], "less_than": [], "less_than_or_equals": [],
        "qualified": [], "logical": [], "default_value": None,
        "severity": "Info", "messages": {}, "shapes": [],
    }


def _merge_prop(entry: dict, ps: PropertyShape, model: ShapesModel) -> None:
    """Conjonction des contraintes de plusieurs property shapes sur le même prédicat."""
    if ps.min_count is not None:
        entry["min_count"] = max(entry["min_count"] or 0, ps.min_count)
    if ps.max_count is not None:
        entry["max_count"] = ps.max_count if entry["max_count"] is None else min(entry["max_count"], ps.max_count)
    for key, vals in (("datatype", [ps.datatype] if ps.datatype else []), ("class", ps.class_), ("node", ps.node),
                      ("pattern", [ps.pattern] if ps.pattern else []), ("language_in", ps.language_in),
                      ("equals", ps.equals), ("disjoint", ps.disjoint), ("less_than", ps.less_than),
                      ("less_than_or_equals", ps.less_than_or_equals)):
        for v in vals:
            if v not in entry[key]:
                entry[key].append(v)
    if ps.in_:
        new = [_val(v) for v in ps.in_]
        entry["in"] = new if not entry["in"] else [v for v in entry["in"] if v in new]  # intersection
    for v in ps.has_value:
        if _val(v) not in entry["has_value"]:
            entry["has_value"].append(_val(v))
    if ps.node_kind:
        entry["node_kind"] = ps.node_kind
    for attr in ("min_length", "max_length", "min_inclusive", "max_inclusive", "min_exclusive", "max_exclusive"):
        v = getattr(ps, attr)
        if v is not None:
            entry[attr] = v  # dernière valeur ; plusieurs bornes différentes = cas rare, signalé par l'import
    entry["unique_lang"] = entry["unique_lang"] or ps.unique_lang
    for q in ps.qualified:
        target = model.shapes.get(q.shape)
        entry["qualified"].append({
            "shape": q.shape, "min_count": q.min_count, "max_count": q.max_count, "disjoint": q.disjoint,
            "class": list(target.class_) if target else [], "datatype": target.datatype if target else None,
        })
    for op, items in (("or", ps.or_), ("and", ps.and_), ("xone", ps.xone), ("not", ps.not_)):
        if items:
            entry["logical"].append({"op": op, "shapes": list(items),
                                     "classes": [list(model.shapes[s].class_) if s in model.shapes else [] for s in items]})
    if ps.default_value is not None and entry["default_value"] is None:
        entry["default_value"] = _val(ps.default_value)
    if _SEV_RANK[ps.severity] > _SEV_RANK[entry["severity"]]:
        entry["severity"] = ps.severity
    for lang, msg in ps.messages.items():
        entry["messages"].setdefault(lang, msg)
    entry["shapes"].append(ps.id)
    entry["required"] = (entry["min_count"] or 0) >= 1
    entry["list"] = entry["max_count"] is None or entry["max_count"] > 1


def _simple(path: Path) -> Optional[tuple[str, bool]]:
    if path.kind == "predicate" and path.iri:
        return path.iri, False
    if path.kind == "inverse" and path.args and path.args[0].kind == "predicate":
        return path.args[0].iri or "", True
    return None


def _empty_class(cls: str) -> dict:
    return {"class": cls, "shapes": [], "closed": False, "ignored_properties": [], "properties": {},
            "inverse_properties": {}, "node": {"in": [], "class": [], "not_class": [], "or_class": [],
                                                "xone_class": [], "has_value": [], "node_kind": None},
            "complex_paths": [], "sparql": []}


def shape_constraints(shapes: ShapesModel) -> dict:
    """Index des contraintes SHACL utiles au mapping, par classe cible et par prédicat.

    Structure retournée ::

        {
          "classes": {
            "<IRI classe cible>": {
              "class": "<IRI>",
              "shapes": ["<id NodeShape>", ...],          # shapes ciblant la classe (+ sh:node/sh:and suivis)
              "closed": bool,                              # au moins une shape fermée
              "ignored_properties": ["<IRI>", ...],
              "properties": {                              # chemins simples sujet → objet
                "<IRI prédicat>": PropEntry, ...
              },
              "inverse_properties": {                      # chemins ^p (contrainte sur les arêtes entrantes)
                "<IRI prédicat>": PropEntry, ...
              },
              "node": {                                    # contraintes sur le nœud focus lui-même
                "in": [valeur...],                         # énumération (classe oneOf)
                "class": [IRI], "not_class": [IRI],        # sh:class / sh:not [sh:class] (disjonction)
                "or_class": [[IRI]...], "xone_class": [[IRI]...],
                "has_value": [...], "node_kind": str|None
              },
              "complex_paths": [{"shape", "path" (SPARQL 1.1), "min_count", "max_count"}],
              "sparql": ["<id shape>", ...]                # shapes portant du SHACL-SPARQL (validation applicative)
            }
          },
          "subjects_of": {"<IRI p>": {                     # shapes sh:targetSubjectsOf p (quel que soit le type du sujet)
              "predicate", "shapes": [id], "properties": {pred: PropEntry}, "inverse_properties": {pred: PropEntry},
              "node": {"class": [IRI], "or_class": [[IRI]]}}},   # ex. domaine OWL → sh:class sur le sujet
          "objects_of":  {"<IRI p>": {...même structure...}}, # shapes sh:targetObjectsOf p (ex. inverse-fonctionnelle)
          "node_targets": {"<id shape>": ["<nœud>", ...]},# sh:targetNode (données de référence)
          "untargeted": ["<id shape>", ...],               # shapes sans cible (référencées seulement)
          "warnings": [str]
        }

    PropEntry (conjonction de toutes les property shapes du même prédicat, shapes désactivées exclues) ::

        {"predicate", "inverse": bool,
         "min_count": int|None (max des minCount), "max_count": int|None (min des maxCount),
         "required": min_count ≥ 1, "list": max_count absent ou > 1,
         "datatype": [IRI], "class": [IRI], "node_kind", "node": [id shape],
         "in": [valeur] (intersection), "has_value": [valeur], "pattern": [regex],
         "min_length", "max_length", "min_inclusive", "max_inclusive", "min_exclusive", "max_exclusive"
            (forme lexicale ou N-Triples, cf. import_shapes.encode_term),
         "language_in": [str], "unique_lang": bool,
         "equals"/"disjoint"/"less_than"/"less_than_or_equals": [IRI prédicat],
         "qualified": [{"shape", "min_count", "max_count", "disjoint", "class": [IRI], "datatype"}],
         "logical": [{"op": or|and|xone|not, "shapes": [id], "classes": [[IRI]]}],
         "default_value", "severity": la plus forte, "messages": {lang: msg}, "shapes": [id PropertyShape]}

    Les valeurs (in, has_value, default_value) sont des IRIs (str) ou des dicts LiteralValue
    `{"value", "datatype"?, "lang"?}`.
    """
    out: dict = {"classes": {}, "subjects_of": {}, "objects_of": {}, "node_targets": {}, "untargeted": [],
                 "warnings": []}

    def expand(ns: NodeShape, seen: set) -> list[NodeShape]:
        """La shape + celles atteintes par sh:node / sh:and (conjonction : contraintes applicables au focus)."""
        res = [ns]
        for ref in list(ns.node) + list(ns.and_):
            sub = shapes.shapes.get(ref)
            if sub is not None and sub.id not in seen and not sub.deactivated:
                seen.add(sub.id)
                res.extend(expand(sub, seen))
        return res

    def feed(bucket: dict, inv_bucket: Optional[dict], complex_list: Optional[list], ns: NodeShape) -> None:
        for ps in ns.properties:
            if ps.deactivated:
                continue
            simple = _simple(ps.path)
            if simple is None:
                if complex_list is not None:
                    complex_list.append({"shape": ps.id, "path": path_to_sparql(ps.path),
                                         "min_count": ps.min_count, "max_count": ps.max_count})
                continue
            pred, inv = simple
            target = (inv_bucket if inv else bucket)
            if target is None:
                continue
            entry = target.setdefault(pred, _empty_prop(pred, inv))
            _merge_prop(entry, ps, shapes)

    for ns in shapes.shapes.values():
        if ns.deactivated:
            continue
        t = ns.targets
        group = expand(ns, {ns.id})
        for cls in t.target_class:
            ce = out["classes"].setdefault(cls, _empty_class(cls))
            for s in group:
                if s.id not in ce["shapes"]:
                    ce["shapes"].append(s.id)
                ce["closed"] = ce["closed"] or s.closed
                for ip in s.ignored_properties:
                    if ip not in ce["ignored_properties"]:
                        ce["ignored_properties"].append(ip)
                feed(ce["properties"], ce["inverse_properties"], ce["complex_paths"], s)
                nd = ce["node"]
                nd["in"].extend(_val(v) for v in s.in_ if _val(v) not in nd["in"])
                nd["class"].extend(c for c in s.class_ if c not in nd["class"])
                nd["has_value"].extend(_val(v) for v in s.has_value)
                nd["node_kind"] = nd["node_kind"] or s.node_kind
                for ref in s.not_:
                    sub = shapes.shapes.get(ref)
                    if sub:
                        nd["not_class"].extend(c for c in sub.class_ if c not in nd["not_class"])
                for key, items in (("or_class", s.or_), ("xone_class", s.xone)):
                    if items:
                        nd[key].append([c for ref in items for c in (shapes.shapes[ref].class_ if ref in shapes.shapes else [])])
                if s.sparql or any(p.sparql for p in s.properties):
                    ce["sparql"].append(s.id)
        for key, preds in (("subjects_of", t.target_subjects_of), ("objects_of", t.target_objects_of)):
            for p in preds:
                se = out[key].setdefault(p, {"predicate": p, "shapes": [], "properties": {},
                                             "inverse_properties": {}, "node": {"class": [], "or_class": []}})
                for s in group:
                    if s.id not in se["shapes"]:
                        se["shapes"].append(s.id)
                    feed(se["properties"], se["inverse_properties"], None, s)
                    se["node"]["class"].extend(c for c in s.class_ if c not in se["node"]["class"])
                    if s.or_:
                        se["node"]["or_class"].append(
                            [c for ref in s.or_ for c in (shapes.shapes[ref].class_ if ref in shapes.shapes else [])])
        if t.target_node:
            out["node_targets"][ns.id] = list(t.target_node)
        if not (t.target_class or t.target_subjects_of or t.target_objects_of or t.target_node):
            out["untargeted"].append(ns.id)
    for ps in shapes.property_shapes.values():
        out["warnings"].append(f"Property shape autonome {ps.id} : prise en compte seulement via ses références.")
    return out


class PGHint(BaseModel):
    """Vue aplatie (lots/L2.md) : une entrée par classe cible × prédicat."""
    target_class: str
    property: str
    inverse: bool = False
    required: bool = False
    is_list: bool = Field(default=True, alias="list")
    datatype: Optional[str] = None
    class_: list[str] = Field(default_factory=list, alias="class")
    enum: list[Any] = Field(default_factory=list)
    pattern: Optional[str] = None
    min_count: Optional[int] = None
    max_count: Optional[int] = None
    shapes: list[str] = Field(default_factory=list)

    model_config = {"populate_by_name": True}


def hints(shapes: ShapesModel) -> list[PGHint]:
    idx = shape_constraints(shapes)
    out: list[PGHint] = []
    for cls, ce in idx["classes"].items():
        for bucket in ("properties", "inverse_properties"):
            for pred, e in ce[bucket].items():
                out.append(PGHint(target_class=cls, property=pred, inverse=e["inverse"], required=e["required"],
                                  is_list=e["list"], datatype=e["datatype"][0] if e["datatype"] else None,
                                  class_=e["class"], enum=e["in"], pattern=e["pattern"][0] if e["pattern"] else None,
                                  min_count=e["min_count"], max_count=e["max_count"], shapes=e["shapes"]))
    return out
