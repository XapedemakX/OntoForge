"""Famille D — propriétés de données : D01–D13 (détection, plan, construction des propriétés)."""
from __future__ import annotations

from typing import Optional

from ...core.onto_model import OWL, RDF, RDFS, XSD
from ...core.pg_model import NodeType, PGProperty
from ...core.lang import label_lang
from ._base import TOP_DATA, Ctx, expr_text, add_materialization, add_validation, finding, props_of, upper_first
from .classes import node_targets, scope, scope_text

LOSSY = {XSD + "decimal", XSD + "hexBinary", XSD + "base64Binary", XSD + "dateTimeStamp", OWL + "real",
         OWL + "rational", XSD + "gYear", XSD + "gYearMonth", XSD + "gMonth", XSD + "gDay", XSD + "gMonthDay",
         XSD + "date", XSD + "time", XSD + "duration", XSD + "dayTimeDuration", XSD + "yearMonthDuration"}
BINARY = {XSD + "hexBinary", XSD + "base64Binary"}
LANG = {RDF + "PlainLiteral", RDF + "langString"}
FACET_NAMES = {XSD + "minInclusive": "min", XSD + "maxInclusive": "max", XSD + "minExclusive": "minExclusive",
               XSD + "maxExclusive": "maxExclusive", XSD + "pattern": "pattern", XSD + "length": "length",
               XSD + "minLength": "minLength", XSD + "maxLength": "maxLength"}
INT_BOUNDS = {XSD + "nonNegativeInteger": {"min": 0}, XSD + "positiveInteger": {"min": 1},
              XSD + "nonPositiveInteger": {"max": 0}, XSD + "negativeInteger": {"max": -1}}


def _dps(ctx: Ctx):
    return sorted(ctx.onto.datatype_properties.items())


def _langs(ctx: Ctx, p: str) -> list[str]:
    return sorted({f.lang for _, f in ctx.facts_using(p) if f.lang})


def _max1(ctx: Ctx, p: str) -> bool:
    for c in ctx.onto.classes:
        for r, _ in ctx.all_restrictions(c):
            if r.property == p and r.kind in ("max", "exactly") and (r.n or 0) <= 1:
                return True
    for c in ctx.shape_classes(p):
        sp = ctx.shape_prop(c, p)
        if sp and sp.get("max_count") == 1:
            return True
    return False


def detect_d01(ctx):
    return [finding(ctx, "D01", p, f"{ctx.short(p)} : domaine {ctx.short(_dom(ctx, p)[0])}.", related=_dom(ctx, p))
            for p, v in _dps(ctx) if len(_dom(ctx, p)) == 1 and not ctx.union_of(p, "domain")[0]
            and ctx.endpoints(p, "domain")["reducible"]]


def detect_d02(ctx):
    return [finding(ctx, "D02", p, f"{ctx.short(p)} n'a pas de domaine"
                    + (" ; utilisée seulement via ses sous-propriétés "
                       f"({', '.join(ctx.short(s) for s in _subprops(ctx, p))})." if _subprops(ctx, p) and not _users(ctx, p)
                       else "."), related=_subprops(ctx, p))
            for p, v in _dps(ctx) if not _dom(ctx, p) and not ctx.endpoints(p, "domain")["expr"]
            and not ctx.union_of(p, "domain")[0]]


def detect_d03(ctx):
    out = []
    for p, _ in _dps(ctx):
        members, node = ctx.union_of(p, "domain")
        if members:
            ctx.consume(node)
            out.append(finding(ctx, "D03", p, f"{ctx.short(p)} : domaine = {' ⊔ '.join(ctx.short(m) for m in members)}.",
                               related=members))
    return out


def detect_d04(ctx):
    out = []
    for p, v in _dps(ctx):
        if v.functional or _max1(ctx, p) or set(v.range) & LANG:
            continue
        per_subject: dict[str, int] = {}
        for i, f in ctx.facts_using(p):
            per_subject[i] = per_subject.get(i, 0) + 1
        multi = any(n > 1 for n in per_subject.values())
        out.append(finding(ctx, "D04", p, f"{ctx.short(p)} n'est pas fonctionnelle"
                           + (" ; plusieurs valeurs observées sur un même individu." if multi else
                              " ; aucune valeur multiple observée (OWA : non prouvé)."),
                           reco={"curiosity": "list_property", "neo4j": "list_property"} if multi else None))
    return out


def detect_d05(ctx):
    out = []
    for p, v in _dps(ctx):
        for dt in v.range:
            if dt in LOSSY:
                typ, lossy, note = ctx.profile.datatype(dt)
                if not lossy and typ == "Decimal":
                    continue  # type décimal natif sans perte (Curiosity, D-L13-01)
                reco = {"curiosity": "string_lexical", "neo4j": "string_lexical"} if dt in BINARY else None
                out.append(finding(ctx, "D05", p, f"{ctx.short(p)} : {ctx.short(dt)} → {typ}. {note}".strip(),
                                   related=[dt], reco=reco,
                                   suffix=None if len([d for d in v.range if d in LOSSY]) == 1 else ctx.local(dt)))
    return out


def detect_d06(ctx):
    out = []
    for p, v in _dps(ctx):
        langs = _langs(ctx, p)
        if set(v.range) & LANG or langs:
            out.append(finding(ctx, "D06", p, f"{ctx.short(p)} : valeurs à langue ({', '.join(langs) or 'fr, en'})"
                               + (" ; rdf:langString n'est pas dans la carte OWL 2 (W01)." if RDF + "langString" in v.range else "."),
                               related=[d for d in v.range if d in LANG]))
    return out


def detect_d07(ctx):
    return [finding(ctx, "D07", p, f"{ctx.short(p)} est fonctionnelle.") for p, v in _dps(ctx) if v.functional]


def detect_d08(ctx):
    out = []
    for p, _ in _dps(ctx):
        dr, node = ctx.range_expr(p)
        if dr and dr.one_of:
            ctx.consume(node)
            out.append(finding(ctx, "D08", p, f"{ctx.short(p)} ∈ {{{', '.join(repr(x.value) for x in dr.one_of)}}}."))
    return out


def detect_d09(ctx):
    out = []
    for d in sorted(ctx.onto.datatypes):
        dr, node = ctx.datatype_def(d)
        if dr is None:
            continue
        ctx.consume(node)
        facets = ", ".join(f"{FACET_NAMES.get(k, ctx.short(k))}={v}" for k, v in sorted(dr.facets.items()))
        users = sorted(p for p, v in _dps(ctx) if d in v.range)
        out.append(finding(ctx, "D09", d, f"Datatype {ctx.short(d)} = {ctx.short(dr.base or '?')} [{facets}] ; "
                           f"utilisé par {', '.join(ctx.short(u) for u in users) or 'aucune propriété'}.",
                           related=users))
    return out


def detect_d10(ctx):
    return [finding(ctx, "D10", p, f"{ctx.short(p)} : portée {'rdfs:Literal' if v.range else 'absente'} (non typée).")
            for p, v in _dps(ctx) if (v.range == [RDFS + "Literal"] or not v.range) and not ctx.range_expr(p)[0]
            and not v.range_expr]


def detect_d11(ctx):
    out = []
    for p, v in _dps(ctx):
        parents = [s for s in v.sub_property_of if s != TOP_DATA]
        if parents:
            out.append(finding(ctx, "D11", p, f"{ctx.short(p)} ⊑ {', '.join(ctx.short(s) for s in parents)}.",
                               related=parents))
    return out


def detect_d12(ctx):
    out = []
    for p, v in _dps(ctx):
        if len(v.range) >= 2:
            out.append(finding(ctx, "D12", p, f"{ctx.short(p)} a {len(v.range)} portées "
                               f"({', '.join(ctx.short(r) for r in v.range)}) : intersection (rdfs3), pas union.",
                               related=v.range))
        ep = ctx.endpoints(p, "domain")
        if len(ep["classes"]) >= 2:
            if ep["reducible"]:
                ctx.consume(ep["node"])
            how = (f"domaine {expr_text(ep['expr'], ctx.short)}" if ep["expr"] is not None
                   else f"{len(ep['classes'])} domaines ({', '.join(ctx.short(r) for r in ep['classes'])})")
            out.append(finding(ctx, "D12", p, f"{ctx.short(p)} : {how} : intersection (rdfs2), pas union ; "
                               "propriété rattachée à chaque conjoint nommé.",
                               related=ep["classes"], suffix="domain",
                               reco={"curiosity": "intersection_domain", "neo4j": "intersection_domain"}))
    return out


def detect_d13(ctx):
    out = {}
    for c in sorted(ctx.onto.classes):
        for r, node in ctx.all_restrictions(c):
            if ctx.is_data_prop(r.property):
                ctx.consume(node)
                fid = f"D13:{c}:{r.property}"
                txt = f"{r.kind}{' ' + str(r.n) if r.n is not None else ''}{' ' + ctx.short(r.filler) if r.filler else ''}"
                if fid in out:
                    out[fid].detail += f" ; {txt}"
                    continue
                out[fid] = finding(ctx, "D13", c, f"{ctx.short(c)} : {ctx.short(r.property)} {txt}.",
                                   suffix=r.property, related=[r.property])
    for fid, f in out.items():  # max 1 seul = propriété scalaire, déjà le choix par défaut → auto
        c, prop = f.subject, f.related[0]
        if all(r.kind == "max" and (r.n or 0) <= 1 for r, _ in ctx.all_restrictions(c) if r.property == prop):
            f.severity = "auto"
    return list(out.values())


DETECT = {"D01": detect_d01, "D02": detect_d02, "D03": detect_d03, "D04": detect_d04, "D05": detect_d05,
          "D06": detect_d06, "D07": detect_d07, "D08": detect_d08, "D09": detect_d09, "D10": detect_d10,
          "D11": detect_d11, "D12": detect_d12, "D13": detect_d13}


# ================================================================================================ helpers
def _dom(ctx: Ctx, p: str) -> list[str]:
    return ctx.endpoints(p, "domain")["classes"]


def _subprops(ctx: Ctx, p: str) -> list[str]:
    return sorted(q for q, v in ctx.onto.datatype_properties.items() if p in v.sub_property_of)


def _most_specific(ctx: Ctx, types: list[str]) -> list[str]:
    ts = [t for t in types if ctx.is_class(t)]
    return sorted(t for t in ts if not any(o != t and ctx.subsumes(t, o) for o in ts))


def _users(ctx: Ctx, p: str) -> list[str]:
    users = set(ctx.restricting_classes(p)) | set(ctx.shape_classes(p))
    for i, _ in ctx.facts_using(p):
        users |= set(_most_specific(ctx, ctx.onto.individuals[i].types))
    return sorted(users)


# ================================================================================================ construction (phase 40)
def _range_type(ctx: Ctx, p: str) -> tuple[str, Optional[str], dict]:
    """(type PG, datatype de base, facettes) pour la portée de p."""
    v = ctx.onto.datatype_properties[p]
    dr, _ = ctx.range_expr(p)
    if dr and dr.one_of:
        dts = {x.datatype for x in dr.one_of if x.datatype}
        base = dts.pop() if len(dts) == 1 else XSD + "string"
        return ctx.profile.datatype(base)[0], base, {}
    types = []
    for r in v.range or [RDFS + "Literal"]:
        if r in ctx.onto.datatypes:
            dd, _ = ctx.datatype_def(r)
            base = (dd.base if dd else None) or XSD + "string"
            types.append((ctx.profile.datatype(base)[0], base, dict(dd.facets) if dd else {}))
        else:
            types.append((ctx.profile.datatype(r)[0], r, dict(INT_BOUNDS.get(r, {}))))
    if len(types) == 1:
        return types[0]
    non_str = [t for t in types if t[0] != "String"] or types
    merged: dict = {}
    for t in types:
        merged.update({FACET_NAMES.get(k, k): v for k, v in t[2].items()})
    return non_str[0][0], non_str[0][1], merged


def build_props(ctx: Ctx) -> None:
    plan = ctx.plan
    pg = ctx.pg
    for p, v in _dps(ctx):
        if v.deprecated and plan.get("deprecated", {}).get(p, "exclude") == "exclude":
            continue
        if plan.get("enum_props", {}).get(p) == "reference_nodes":
            pass  # traité plus bas (nœuds de référence)
        # ---- classes porteuses
        union, _ = ctx.union_of(p, "domain")
        if union:
            classes = union
        elif _dom(ctx, p):
            classes = _dom(ctx, p)
        else:
            opt = ctx.option_of("D02", p, default="attach_to_users")
            classes = _users(ctx, p) if opt == "attach_to_users" else []
        nts = sorted({nt for c in classes for nt in node_targets(ctx, c)})
        dereified = [c for c in classes if plan["mode"].get(c) == "dereified"]
        for c in dereified:
            plan.setdefault("edge_props", {}).setdefault(c, []).append(p)
        if not nts:
            continue
        # ---- type
        typ, base, facets = _range_type(ctx, p)
        if ctx.option_of("D05", p) == "string_lexical":
            typ = "String"
        is_list = ctx.option_of("D04", p) == "list_property"
        enum = []
        dr, _ = ctx.range_expr(p)
        if dr and dr.one_of and ctx.option_of("D08", p, default="enum_property") == "enum_property":
            enum = [x.value for x in dr.one_of]
        pattern = None
        fac = {FACET_NAMES.get(k, k): val for k, val in facets.items()}
        dtype_rule = next((r for r in v.range if r in ctx.onto.datatypes), None)
        if dtype_rule and ctx.option_of("D09", dtype_rule, default="validation") == "validation":
            pattern = fac.get("pattern")
        langs = None
        if ctx.findings.get(f"D06:{p}") and ctx.option_of("D06", p) == "per_language_property":
            langs = _langs(ctx, p) or ["fr", "en"]
        desc = ctx.onto.label(p, label_lang())
        for nt_name in nts:
            nt = pg.node_types[nt_name]
            for lang in (langs or [None]):
                name = ctx.profile.prop(ctx.local(p), lang)
                if any(x.name == name and x.source == p for x in nt.properties):
                    continue
                nt.properties.append(PGProperty(name=name, type=typ, is_list=is_list, source=p, description=desc,
                                                enum=enum, pattern=pattern, lang=lang,
                                                note=("datatype " + ctx.short(base)) if base else None))
            plan.setdefault("prop_facets", {})[p] = fac


def apply_d09_build(ctx: Ctx, f, opt):
    if opt != "validation":
        return
    dr, _ = ctx.datatype_def(f.subject)
    if not dr:
        return
    fac = {FACET_NAMES.get(k, k): v for k, v in dr.facets.items()}
    for p in f.related:
        for nt, prop in props_of(ctx, p):
            kind = "pattern" if "pattern" in fac else "range"
            add_validation(ctx, f, kind, f"{nt.name}.{prop.name} respecte {ctx.short(f.subject)} "
                           f"({', '.join(f'{k}={v}' for k, v in sorted(fac.items()))}).",
                           node_type=nt.name, prop=prop.name, params=fac)


def apply_d08_build(ctx: Ctx, f, opt):
    dr, _ = ctx.range_expr(f.subject)
    values = [x.value for x in dr.one_of] if dr else []
    for nt, prop in props_of(ctx, f.subject):
        add_validation(ctx, f, "enum", f"{nt.name}.{prop.name} ∈ {{{', '.join(values)}}}.", node_type=nt.name,
                       prop=prop.name, params={"values": values})


def apply_d12_build(ctx: Ctx, f, opt):
    fac = ctx.plan.get("prop_facets", {}).get(f.subject, {})
    for nt, prop in props_of(ctx, f.subject):
        if f.id.endswith(":domain"):
            if opt == "intersection_domain":
                add_validation(ctx, f, "other", f"Le nœud portant {prop.name} appartient à tous les domaines "
                               f"({', '.join(ctx.short(r) for r in f.related)}).", node_type=nt.name, prop=prop.name,
                               params={"all_of": f.related})
        else:
            add_validation(ctx, f, "range", f"{nt.name}.{prop.name} appartient à l'intersection "
                           f"{' ⊓ '.join(ctx.short(r) for r in f.related)}" + (f" ({fac})" if fac else "") + ".",
                           node_type=nt.name, prop=prop.name, params=dict(fac, datatypes=f.related))


def apply_d13_build(ctx: Ctx, f, opt):
    if opt != "validation":
        return
    prop_iri = f.related[0]
    nts = set(node_targets(ctx, f.subject))
    rs = [r for r, _ in ctx.all_restrictions(f.subject) if r.property == prop_iri]
    for nt, prop in props_of(ctx, prop_iri):
        if nt.name not in nts:
            continue
        sc = scope(ctx, f.subject, nt.name)
        for r in rs:
            if sc is None:  # restriction d'une sous-classe aplatie : jamais obligatoire pour toute la racine
                if r.kind in ("exactly", "min", "some") and (r.n or 1) >= 1:
                    prop.required = True
                if r.kind in ("exactly", "max") and (r.n or 0) <= 1:
                    prop.is_list = False
            kind = "existence" if r.kind in ("some", "min") else "cardinality"
            add_validation(ctx, f, kind, f"{nt.name}.{prop.name}{scope_text(sc)} : {r.kind} "
                           f"{r.n if r.n is not None else ''} {ctx.short(r.filler) if r.filler else ''}".rstrip() + ".",
                           node_type=nt.name, prop=prop.name,
                           params={"kind": r.kind, "n": r.n, "datatype": r.filler,
                                   **({"discriminator": sc["discriminator"], "values": sc["values"]} if sc else {})})


def apply_d11_build(ctx: Ctx, f, opt):
    if opt != "materialize_closure":
        return
    for parent in f.related:
        for nt, prop in props_of(ctx, f.subject):
            pname = ctx.profile.prop(ctx.local(parent))
            if not any(x.name == pname for x in nt.properties):
                nt.properties.append(PGProperty(name=pname, type=prop.type, is_list=prop.is_list, source=parent,
                                                note=f"Recopie de {prop.name} (super-propriété, D11)."))
        add_materialization(ctx, f, "superProperty", f"Recopier {ctx.short(f.subject)} dans {ctx.short(parent)} à "
                            "l'ingestion.", parent=parent)


APPLY_BUILD = {"D09": apply_d09_build, "D08": apply_d08_build, "D12": apply_d12_build, "D13": apply_d13_build,
               "D11": apply_d11_build}
