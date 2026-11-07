"""Enrichissement SHACL (S01 conflits OWL/SHACL, S02 propriétés issues des shapes).

Les shapes décrivent le contrat de données (monde clos) : elles sont plus proches d'un schéma LPG que OWL.
minCount → obligatoire / existence, maxCount 1 → scalaire, sh:in → enum, sh:pattern → motif, sh:datatype → type,
sh:class / sh:or → validation de la cible, sh:lessThan, sh:closed, qualifiées → validations.
"""
from __future__ import annotations

import re
from typing import Optional

from ...core.pg_model import PGProperty, Validation
from ._base import Ctx, finding, sha8
from .classes import node_targets, scope, scope_text


def _owl_max1(ctx: Ctx, c: str, p: str) -> bool:
    v = ctx.onto.datatype_properties.get(p) or ctx.onto.object_properties.get(p)
    if v is None:
        return False
    if getattr(v, "functional", False) or "functional" in getattr(v, "characteristics", []):
        return True
    for a in [c] + ctx.ancestors(c):
        for r, _ in ctx.all_restrictions(a):
            if r.property == p and r.kind in ("max", "exactly") and (r.n or 0) <= 1:
                return True
    return False


def _norm_pattern(s: Optional[str]) -> str:
    return re.sub(r"^\^|\$$", "", s or "")


def _conflicts(ctx: Ctx, c: str, p: str, sp: dict) -> list[str]:
    out = []
    if sp.get("max_count") is not None and sp["max_count"] > 1 and _owl_max1(ctx, c, p):
        out.append(f"sh:maxCount {sp['max_count']} alors qu'OWL impose au plus 1 valeur")
    dp = ctx.onto.datatype_properties.get(p)
    if dp and sp.get("datatype"):
        owl_types = set()
        for r in dp.range:
            if r in ctx.onto.datatypes:
                dd, _ = ctx.datatype_def(r)
                r = (dd.base if dd else None) or r
            owl_types.add(ctx.profile.datatype(r)[0])
        sh_types = {ctx.profile.datatype(d)[0] for d in sp["datatype"]}
        if owl_types and sh_types and not (owl_types & sh_types):
            out.append(f"sh:datatype {', '.join(sp['datatype'])} incompatible avec la portée OWL")
        for d in (dp.range if dp else []):
            if d in ctx.onto.datatypes:
                dd, _ = ctx.datatype_def(d)
                owl_pat = (dd.facets.get("http://www.w3.org/2001/XMLSchema#pattern") if dd else None)
                for sp_pat in sp.get("pattern", []):
                    if owl_pat and _norm_pattern(owl_pat) != _norm_pattern(sp_pat):
                        out.append(f"sh:pattern {sp_pat!r} ≠ facette OWL {owl_pat!r}")
    op = ctx.onto.object_properties.get(p)
    if op and sp.get("class") and op.range:
        for k in sp["class"]:
            if ctx.is_class(k) and not any(ctx.subsumes(r, k) or ctx.subsumes(k, r) for r in op.range):
                out.append(f"sh:class {ctx.short(k)} disjointe de la portée OWL {', '.join(ctx.short(r) for r in op.range)}")
    return out


def _iter(ctx: Ctx):
    for c, ce in sorted(ctx.sc.get("classes", {}).items()):
        for inv, bucket in ((False, "properties"), (True, "inverse_properties")):
            for p, sp in sorted(ce.get(bucket, {}).items()):
                yield c, p, inv, sp


def detect_s01(ctx: Ctx):
    out = []
    for c, p, inv, sp in _iter(ctx):
        if inv:
            continue
        cs = _conflicts(ctx, c, p, sp)
        if cs:
            out.append(finding(ctx, "S01", c, f"{ctx.short(c)} / {ctx.short(p)} : " + " ; ".join(cs) + ".",
                               suffix=p, related=[p]))
    return out


def detect_s02(ctx: Ctx):
    return [finding(ctx, "S02", c, f"Shape sur {ctx.short(c)} : {ctx.short(p)} n'est pas déclarée dans l'ontologie.",
                    suffix=p, related=[p])
            for c, p, inv, sp in _iter(ctx) if not inv and not ctx.is_data_prop(p) and not ctx.is_obj_prop(p)]


DETECT = {"S01": detect_s01, "S02": detect_s02}


def _val(ctx: Ctx, vid: str, kind: str, desc: str, src: str, **kw) -> None:
    ctx.pg.validations.append(Validation(id=vid, kind=kind, description=desc, source=src, **kw))


def build_shacl(ctx: Ctx) -> None:
    """Phase 90 : applique les shapes au PGModel (sauf points tranchés « owl_wins » en S01)."""
    if not ctx.sc:
        return
    prof = ctx.profile
    for c, p, inv, sp in _iter(ctx):
        if ctx.option_of("S01", c, p) == "owl_wins":
            continue
        nts = set(node_targets(ctx, c))
        base = f"SH:{c}:{p}" + (":inverse" if inv else "")
        n = 0

        def nid():
            nonlocal n
            n += 1
            return f"{base}#v{n}"
        shape_src = (sp.get("shapes") or [c])[0]
        msg = (sp.get("messages") or {}).get("fr")
        if not inv and (ctx.is_data_prop(p) or (not ctx.is_obj_prop(p) and ctx.option_of("S02", c, p) == "property")):
            props = [(ctx.pg.node_types[nt], x) for nt in sorted(nts) for x in ctx.pg.node_types[nt].properties
                     if x.source == p]
            if not props and not ctx.is_data_prop(p):
                for nt in sorted(nts):
                    typ = prof.datatype(sp["datatype"][0] if sp.get("datatype") else None)[0]
                    x = PGProperty(name=prof.prop(ctx.local(p)), type=typ, source=p, note="Issue des shapes (S02).")
                    ctx.pg.node_types[nt].properties.append(x)
                    props.append((ctx.pg.node_types[nt], x))
            for nt, x in props:
                sc = scope(ctx, c, nt.name)  # shape d'une sous-classe aplatie : filtrée par discriminant
                scp = {"discriminator": sc["discriminator"], "values": sc["values"]} if sc else {}
                if sp.get("required"):
                    if sc is None:
                        x.required = True
                    _val(ctx, nid(), "existence", msg or f"{nt.name}.{x.name}{scope_text(sc)} obligatoire (sh:minCount {sp['min_count']}).",
                         shape_src, node_type=nt.name, property=x.name, params={**scp, "min": sp["min_count"]})
                if sp.get("max_count") == 1 and sc is None:
                    x.is_list = False
                if sp.get("max_count") is not None and not x.lang:
                    _val(ctx, nid(), "cardinality", f"{nt.name}.{x.name} : au plus {sp['max_count']} valeur(s).",
                         shape_src, node_type=nt.name, property=x.name, params={**scp, "max": sp["max_count"]})
                if sp.get("pattern"):
                    x.pattern = x.pattern or sp["pattern"][0]
                    _val(ctx, nid(), "pattern", msg or f"{nt.name}.{x.name} ~ {sp['pattern'][0]}", shape_src,
                         node_type=nt.name, property=x.name, params={**scp, "pattern": sp["pattern"][0]})
                if sp.get("in"):
                    vals = [v["value"] if isinstance(v, dict) else v for v in sp["in"]]
                    x.enum = x.enum or [str(v) for v in vals]
                    _val(ctx, nid(), "enum", f"{nt.name}.{x.name} ∈ {vals}", shape_src, node_type=nt.name,
                         property=x.name, params={**scp, "values": vals})
                rng = {k: sp.get(k) for k in ("min_inclusive", "max_inclusive", "min_exclusive", "max_exclusive")
                       if sp.get(k) is not None}
                if rng:
                    _val(ctx, nid(), "range", f"{nt.name}.{x.name} : bornes {rng}.", shape_src, node_type=nt.name,
                         property=x.name, params={**scp, **rng})
                for other in sp.get("less_than", []) + sp.get("less_than_or_equals", []):
                    _val(ctx, nid(), "other", f"{nt.name}.{x.name} < {ctx.short(other)} (sh:lessThan).", shape_src,
                         node_type=nt.name, property=x.name, params={**scp, "lessThan": other})
        elif ctx.is_obj_prop(p):
            edges = [e for e in ctx.pg.edge_types if e.source == p and not e.derived
                     and ((e.to in nts) if inv else (e.from_ in nts))]
            for e in edges:
                if scope(ctx, c, e.to if inv else e.from_):
                    continue  # shape d'une sous-classe aplatie : validation seulement (filtrée), arête inchangée
                card = e.cardinality
                attr = "in_" if inv else "out"
                lo = (sp.get("min_count") or 0) >= 1 or any((q.get("min_count") or 0) >= 1 for q in sp.get("qualified", []))
                hi = sp.get("max_count") == 1
                setattr(card, attr, ("1" if hi else "1..*") if lo else ("0..1" if hi else getattr(card, attr)))
            target_nt = sorted(nts)[0] if nts else None
            edge_name = edges[0].name if edges else None
            if sp.get("min_count"):
                _val(ctx, nid(), "existence", msg or f"{target_nt} : au moins {sp['min_count']} "
                     f"{'relation entrante' if inv else 'relation'} {edge_name or ctx.short(p)}.", shape_src,
                     node_type=target_nt, edge_type=edge_name,
                     params={"min": sp["min_count"], "direction": "in" if inv else "out"})
            if sp.get("max_count") is not None:
                _val(ctx, nid(), "cardinality", f"{target_nt} : au plus {sp['max_count']} {edge_name or ctx.short(p)}.",
                     shape_src, node_type=target_nt, edge_type=edge_name, params={"max": sp["max_count"]})
            if sp.get("class"):
                _val(ctx, nid(), "allValuesFrom", f"{edge_name or ctx.short(p)} → {', '.join(ctx.short(k) for k in sp['class'])} "
                     "(sh:class).", shape_src, node_type=target_nt, edge_type=edge_name, params={"class": sp["class"]})
            if sp.get("in"):
                vals = [v["value"] if isinstance(v, dict) else v for v in sp["in"]]
                _val(ctx, nid(), "enum", f"{edge_name or ctx.short(p)} → {{{', '.join(ctx.short(str(v)) for v in vals)}}}.",
                     shape_src, node_type=target_nt, edge_type=edge_name, params={"values": vals})
            for lg in sp.get("logical", []):
                _val(ctx, nid(), "allValuesFrom", f"{edge_name or ctx.short(p)} : sh:{lg['op']} "
                     f"{lg.get('classes')}.", shape_src, node_type=target_nt, edge_type=edge_name, params=lg)
            for q in sp.get("qualified", []):
                _val(ctx, nid(), "cardinality", f"{edge_name or ctx.short(p)} : qualifiée {q}.", shape_src,
                     node_type=target_nt, edge_type=edge_name, params=q)
    for c, ce in sorted(ctx.sc.get("classes", {}).items()):
        if ce.get("closed"):
            for nt in node_targets(ctx, c):
                ctx.pg.validations.append(Validation(
                    id=f"SH:{c}:closed:{nt}#v1", kind="closed", node_type=nt, source=(ce.get("shapes") or [c])[0],
                    description=f"{nt} : forme fermée (sh:closed) — seules les propriétés déclarées sont admises "
                                "(valider sans inférence : les super-propriétés entaillées violeraient la forme, D11).",
                    params={"ignored": ce.get("ignored_properties", [])}))
