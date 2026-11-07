"""Famille O — propriétés objet : O01–O21 (détection, plan, construction des types de relation)."""
from __future__ import annotations

from ...core.pg_model import Cardinality, EdgeType, PGProperty
from ...core.lang import label_lang
from ._base import (TOP_OBJ, Ctx, add_materialization, add_validation, edges_of, expr_text, finding, upper_first)
from .classes import node_targets, scope, scope_text

REL_RULES = ("O09", "O10", "O11", "O12", "O14", "O16", "O17")


def _ep(ctx: Ctx, p: str, which: str) -> list[str]:
    return ctx.endpoints(p, which)["classes"]


def _ops(ctx: Ctx):
    return sorted(ctx.onto.object_properties.items())


# ================================================================================================ détection
def detect_o01(ctx):
    return [finding(ctx, "O01", p, f"{ctx.short(p)} : {ctx.short(_ep(ctx, p, 'domain')[0])} → "
                    f"{ctx.short(_ep(ctx, p, 'range')[0])}.", related=_ep(ctx, p, "domain") + _ep(ctx, p, "range"))
            for p, v in _ops(ctx) if len(_ep(ctx, p, "domain")) == 1 and len(_ep(ctx, p, "range")) == 1
            and ctx.endpoints(p, "domain")["reducible"] and ctx.endpoints(p, "range")["reducible"]
            and not ctx.union_of(p, "domain")[0] and not ctx.union_of(p, "range")[0]]


def detect_o02(ctx):
    out = []
    for p, v in _ops(ctx):
        if v.equivalent_to:
            continue  # O19 : extrémités portées par la propriété canonique
        q = ctx.inverse_of(p)
        if q and ctx.onto.object_properties.get(q) and ctx.onto.object_properties[q].domain and ctx.onto.object_properties[q].range:
            continue  # extrémités déduites de l'inverse (O04)
        nd = not _ep(ctx, p, "domain") and not ctx.union_of(p, "domain")[0] and not ctx.endpoints(p, "domain")["expr"]
        nr = not _ep(ctx, p, "range") and not ctx.union_of(p, "range")[0] and not ctx.endpoints(p, "range")["expr"]
        if nd or nr:
            d, r = resolve(ctx, p, "domain"), resolve(ctx, p, "range")
            out.append(finding(ctx, "O02", p, f"{ctx.short(p)} : {'domaine' if nd else ''}{' et ' if nd and nr else ''}"
                               f"{'portée' if nr else ''} absent(s) ; résolution : "
                               f"{', '.join(ctx.short(x) for x in d) or '?'} → {', '.join(ctx.short(x) for x in r) or '?'}.",
                               related=sorted(set(d + r))))
    return out


def detect_o03(ctx):
    out = []
    for p, v in _ops(ctx):
        du, n1 = ctx.union_of(p, "domain")
        ru, n2 = ctx.union_of(p, "range")
        if du or ru:
            ctx.consume(n1); ctx.consume(n2)
            dom = " ⊔ ".join(ctx.short(x) for x in du) if du else ", ".join(ctx.short(x) for x in v.domain)
            rng = " ⊔ ".join(ctx.short(x) for x in ru) if ru else ", ".join(ctx.short(x) for x in v.range)
            out.append(finding(ctx, "O03", p, f"{ctx.short(p)} : {dom} → {rng} (union explicite).", related=du + ru))
    return out


def detect_o04(ctx):
    out, seen = [], set()
    for p, v in _ops(ctx):
        if v.inverse_of and frozenset((p, v.inverse_of)) not in seen:
            seen.add(frozenset((p, v.inverse_of)))
            q = v.inverse_of
            sym = [x for x in (p, q) if x in ctx.onto.object_properties
                   and "symmetric" in ctx.onto.object_properties[x].characteristics]
            out.append(finding(ctx, "O04", p, f"{ctx.short(p)} = inverse de {ctx.short(q)}."
                               + (f" {ctx.short(sym[0])} étant symétrique, {ctx.short(p)} ≡ {ctx.short(q)} : une seule "
                                  "relation suffit." if sym else ""),
                               related=[v.inverse_of]))
    return out


def _char(ctx, rule, chars, text):
    return [finding(ctx, rule, p, f"{ctx.short(p)} : {text}.") for p, v in _ops(ctx) if set(chars) & set(v.characteristics)]


def detect_o05(ctx):
    return _char(ctx, "O05", ["symmetric"], "symétrique")


def detect_o06(ctx):
    return _char(ctx, "O06", ["transitive"], "transitive (propriété non simple)")


def detect_o07(ctx):
    out = []
    for p, v in _ops(ctx):
        parents = [s for s in v.sub_property_of if s != TOP_OBJ]
        if parents:
            out.append(finding(ctx, "O07", p, f"{ctx.short(p)} ⊑ {', '.join(ctx.short(s) for s in parents)}.",
                               related=parents))
    return out


def detect_o08(ctx):
    return [finding(ctx, "O08", p, f"{' ∘ '.join(ctx.short(x) for x in ch)} ⊑ {ctx.short(p)} (inclusion : "
                    f"{ctx.short(p)} peut aussi avoir des assertions directes).", related=list(ch),
                    suffix=str(i + 1) if i else None)
            for p, v in _ops(ctx) for i, ch in enumerate(v.chains)]


def detect_o13(ctx):
    out = []
    for p, v in _ops(ctx):
        chars = sorted(set(v.characteristics) & {"reflexive", "irreflexive", "asymmetric"})
        if chars:
            only_reflexive = chars == ["reflexive"]
            out.append(finding(ctx, "O13", p, f"{ctx.short(p)} : {', '.join(chars)}"
                               + (" — réflexivité globale : tout individu est relié à lui-même ; souvent une erreur, ne "
                                  "jamais matérialiser les boucles." if "reflexive" in chars else "."),
                               reco={"curiosity": "ignore", "neo4j": "ignore"} if only_reflexive else None))
    return out


def detect_o15(ctx):
    return _char(ctx, "O15", ["inverseFunctional"], "inverse-fonctionnelle (au plus une relation entrante)")


def detect_o18(ctx):
    return [finding(ctx, "O18", p, f"{ctx.short(p)} ⊑ owl:topObjectProperty (sans effet).")
            for p, v in sorted(list(ctx.onto.object_properties.items()) + list(ctx.onto.datatype_properties.items()))
            if TOP_OBJ in v.sub_property_of or "http://www.w3.org/2002/07/owl#topDataProperty" in v.sub_property_of]


def detect_o19(ctx):
    out, seen = [], set()
    for p, v in _ops(ctx):
        for q in v.equivalent_to:
            if frozenset((p, q)) not in seen:
                seen.add(frozenset((p, q)))
                out.append(finding(ctx, "O19", p, f"{ctx.short(p)} ≡ {ctx.short(q)}.", related=[q]))
    return out


def detect_o20(ctx):
    out, seen = [], set()
    for p, v in _ops(ctx):
        for q in v.disjoint_with:
            if frozenset((p, q)) not in seen:
                seen.add(frozenset((p, q)))
                out.append(finding(ctx, "O20", p, f"{ctx.short(p)} et {ctx.short(q)} sont disjointes : jamais la même "
                                   "paire.", related=[q]))
    return out


def detect_o21(ctx):
    out = []
    for p, v in _ops(ctx):
        for which in ("domain", "range"):
            ep = ctx.endpoints(p, which)
            lst = ep["classes"]
            if len(lst) >= 2:
                if ep["reducible"]:
                    ctx.consume(ep["node"])
                sub = [a for a in lst if any(b != a and ctx.subsumes(b, a) for b in lst)]
                out.append(finding(ctx, "O21", p, f"{ctx.short(p)} a {len(lst)} {'domaines' if which == 'domain' else 'portées'} "
                                   f"({', '.join(ctx.short(x) for x in lst)}) : intersection (rdfs2/rdfs3), pas union"
                                   + ("." if not sub else f" ; {ctx.short(sub[0])} est la plus spécifique."),
                                   related=lst, suffix=None if which == "domain" else "range",
                                   reco={"curiosity": "most_specific_type", "neo4j": "most_specific_type"} if sub else None))
    return out


def _restriction_findings(ctx: Ctx) -> dict[str, list]:
    if "restr_f" in ctx.cache:
        return ctx.cache["restr_f"]
    out: dict[str, list] = {r: [] for r in REL_RULES}
    store = ctx.cache.setdefault("restr", {})
    ns = ctx.non_simple()
    items = []
    for c in sorted(ctx.onto.classes):
        items += [(c, r, node) for r, node in ctx.all_restrictions(c)]
        for e, node in ctx.class_definitions(c):  # hasSelf dans une définition (O17)
            from ._base import walk
            for x in walk(e):
                if x.op == "self" and x.property:
                    from ...core.onto_model import Restriction
                    items.append((c, Restriction(property=x.property, kind="self"), None))
    for c, r, node in items:
        if not ctx.is_obj_prop(r.property):
            continue
        if r.inverse:
            rule = "O14"
        elif r.kind in ("min", "max", "exactly") and r.property in ns:
            continue  # propriété non simple : aucune cardinalité (SS §11.2, must_not)
        elif r.kind in ("min", "max", "exactly") and r.filler and r.filler != "http://www.w3.org/2002/07/owl#Thing":
            rule = "O16"
        elif r.kind == "some" or (r.kind == "min" and (r.n or 0) >= 1):
            rule = "O10"
        elif r.kind in ("max", "exactly"):
            rule = "O09"
        elif r.kind == "only":
            rule = "O11"
        elif r.kind == "value":
            rule = "O12"
        elif r.kind == "self":
            rule = "O17"
        else:
            continue
        ctx.consume(node)
        fid = f"{rule}:{c}:{r.property}"
        store.setdefault(fid, []).append((c, r))
        if any(f.id == fid for f in out[rule]):
            continue
        val = r.value.value if hasattr(r.value, "value") else (ctx.short(r.value) if r.value else "")
        txt = (f"{'inverse(' + ctx.short(r.property) + ')' if r.inverse else ctx.short(r.property)} {r.kind}"
               f"{' ' + str(r.n) if r.n is not None else ''}{' ' + ctx.short(r.filler) if r.filler else ''}"
               f"{' ' + val if val else ''}")
        out[rule].append(finding(ctx, rule, c, f"{ctx.short(c)} ⊑ {txt}.", suffix=r.property,
                                 related=[r.property] + ([r.filler] if r.filler else [])))
    ctx.cache["restr_f"] = out
    return out


def _restr_detector(rule):
    def d(ctx):
        base = list(_restriction_findings(ctx)[rule])
        if rule == "O09":
            base += [finding(ctx, "O09", p, f"{ctx.short(p)} est fonctionnelle (au plus une relation sortante).")
                     for p, v in _ops(ctx) if "functional" in v.characteristics]
        return base
    return d


DETECT = {"O01": detect_o01, "O02": detect_o02, "O03": detect_o03, "O04": detect_o04, "O05": detect_o05,
          "O06": detect_o06, "O07": detect_o07, "O08": detect_o08, "O13": detect_o13, "O15": detect_o15,
          "O18": detect_o18, "O19": detect_o19, "O20": detect_o20, "O21": detect_o21}
DETECT.update({r: _restr_detector(r) for r in REL_RULES})


# ================================================================================================ résolution des extrémités
def _most_specific(ctx: Ctx, types) -> list[str]:
    ts = [t for t in types if ctx.is_class(t)]
    return sorted(t for t in ts if not any(o != t and ctx.subsumes(t, o) for o in ts))


def resolve(ctx: Ctx, p: str, which: str) -> list[str]:
    v = ctx.onto.object_properties[p]
    union, _ = ctx.union_of(p, which)
    if union:
        return union
    lst = list(_ep(ctx, p, which))
    if len(lst) >= 2:
        opt = ctx.option_of("O21", p, None if which == "domain" else "range", "intersection_domain")
        if opt == "most_specific_type":
            return _most_specific(ctx, lst)[:1] or lst[:1]
        return lst
    if lst:
        return lst
    q = ctx.inverse_of(p)
    if q and q in ctx.onto.object_properties:
        qv = ctx.onto.object_properties[q]
        other = qv.range if which == "domain" else qv.domain
        if other:
            return list(other)
    found: set[str] = set()
    if which == "domain":
        found |= set(ctx.restricting_classes(p)) | set(ctx.shape_classes(p))
        for i, _ in ctx.facts_using(p):
            found |= set(_most_specific(ctx, ctx.onto.individuals[i].types))
    else:
        for c in ctx.onto.classes:
            for r, _ in ctx.all_restrictions(c):
                if r.property == p and not r.inverse and r.filler and ctx.is_class(r.filler):
                    found.add(r.filler)
        for c in ctx.shape_classes(p):
            sp = ctx.shape_prop(c, p) or {}
            found |= {x for x in sp.get("class", []) if ctx.is_class(x)}
        for _, f in ctx.facts_using(p):
            if f.is_iri and f.value in ctx.onto.individuals:
                found |= set(_most_specific(ctx, ctx.onto.individuals[f.value].types))
    return sorted(found)


# ================================================================================================ plan (phase 48)
def apply_o04(ctx, f, opt):
    p, q = f.subject, f.related[0]
    ops = ctx.onto.object_properties
    def info(x):
        v = ops.get(x)
        return (len(v.domain) + len(v.range)) if v else -1
    primary, secondary = (p, q) if info(p) >= info(q) else (q, p)
    ctx.plan.setdefault("inverse_secondary", {})[secondary] = primary
    ctx.plan.setdefault("inverse_primary", {})[primary] = (secondary, opt)


def apply_o19(ctx, f, opt):
    if opt != "merge_relationship_types":
        return
    p, q = f.subject, f.related[0]
    ops = ctx.onto.object_properties
    has = lambda x: bool(ops[x].domain or ops[x].range or ctx.union_of(x, "range")[0]) if x in ops else False
    alias, canon = (p, q) if has(q) or not has(p) else (q, p)
    ctx.plan.setdefault("prop_alias", {})[alias] = canon


def apply_skip(ctx, f, opt):
    if f.rule == "O02" and opt == "ignore":
        ctx.plan.setdefault("skip_edge", set()).add(f.subject)


APPLY_PLAN = {"O04": apply_o04, "O19": apply_o19, "O08": apply_skip, "O02": apply_skip}


# ================================================================================================ construction (phase 50)
def _card(v) -> Cardinality:
    return Cardinality(out="0..1" if "functional" in v.characteristics else "0..*",
                       **{"in": "0..1" if "inverseFunctional" in v.characteristics else "0..*"})


def build_edges(ctx: Ctx) -> None:
    plan, pg, prof = ctx.plan, ctx.pg, ctx.profile
    roles = {r for d in plan.get("dereified", {}).values() for r in d["roles"]}
    for p, v in _ops(ctx):
        if p in plan.get("prop_alias", {}) or p in plan.get("inverse_secondary", {}) or p in roles \
                or p in plan.get("skip_edge", set()):
            continue
        if v.deprecated and plan.get("deprecated", {}).get(p, "exclude") == "exclude":
            continue
        froms = sorted({nt for c in resolve(ctx, p, "domain") for nt in node_targets(ctx, c)})
        tos = sorted({nt for c in resolve(ctx, p, "range") for nt in node_targets(ctx, c)})
        if not froms or not tos:
            plan.setdefault("unresolved_edges", []).append(p)
            continue
        sym = "symmetric" in v.characteristics
        inv = plan.get("inverse_primary", {}).get(p)
        name = prof.edge(ctx.local(p))
        rev = prof.reverse(ctx.local(p), ctx.local(inv[0]) if inv else None, sym)
        sym_opt = ctx.option_of("O05", p) if sym else None
        derived = False  # O08 : la relation garde ses assertions directes (inclusion, pas équivalence)
        for side, which in (("from", "domain"), ("to", "range")):
            for c in resolve(ctx, p, which):
                for nt in node_targets(ctx, c):
                    sc = scope(ctx, c, nt)
                    if sc:
                        plan.setdefault("endpoint_scopes", []).append((p, name, side, nt, sc, c))
        for a in froms:
            for b in tos:
                pg.edge_types.append(EdgeType(name=name, from_=a, to=b, reverse=rev, source=p,
                                              description=ctx.onto.label(p, label_lang()), cardinality=_card(v),
                                              directed=not (sym and sym_opt == "undirected_query"),
                                              symmetric=sym, derived=derived))
                if inv and inv[1] == "edge_pair" and not prof.native_reverse:
                    pg.edge_types.append(EdgeType(name=prof.edge(ctx.local(inv[0])), from_=b, to=a, source=inv[0],
                                                  description=ctx.onto.label(inv[0], label_lang()),
                                                  note=f"Sens inverse de {name} stocké (O04 edge_pair)."))
                if sym and sym_opt == "edge_pair" and not prof.native_reverse and a != b:
                    pass
    _build_dereified(ctx)
    from ...core.pg_model import Validation
    for k, (p, name, side, nt, sc, c) in enumerate(sorted(plan.get("endpoint_scopes", []), key=lambda t: t[:4])):
        ctx.pg.validations.append(Validation(
            id=f"EP:{p}:{side}:{nt}#v1", kind="allValuesFrom", node_type=nt, edge_type=name, source=p,
            description=f"{name} : {'source' if side == 'from' else 'cible'} {nt} limitée à {sc['discriminator']} ∈ "
                        f"{{{', '.join(sc['values'])}}} ({'domaine' if side == 'from' else 'portée'} {ctx.short(c)}, "
                        "héritage aplati).",
            params={"side": side, "discriminator": sc["discriminator"], "values": sc["values"], "class": c}))


def _build_dereified(ctx: Ctx) -> None:
    from .data import _range_type
    plan, prof = ctx.plan, ctx.profile
    for c, d in sorted(plan.get("dereified", {}).items()):
        src_role, dst_role = d["from_role"], d["to_role"]
        froms = sorted({nt for x in resolve(ctx, src_role, "range") for nt in node_targets(ctx, x)})
        tos = sorted({nt for x in resolve(ctx, dst_role, "range") for nt in node_targets(ctx, x)})
        props = []
        for p in sorted(plan.get("edge_props", {}).get(c, [])):
            typ, base, _ = _range_type(ctx, p)
            props.append(PGProperty(name=prof.prop(ctx.local(p)), type=typ, source=p,
                                    description=ctx.onto.label(p, label_lang())))
        for a in froms:
            for b in tos:
                ctx.pg.edge_types.append(EdgeType(
                    name=prof.edge(ctx.local(dst_role)), from_=a, to=b, source=c, properties=props,
                    description=ctx.onto.label(c, label_lang()),
                    note=f"Dé-réification de {ctx.short(c)} (R01) : rôles {ctx.short(src_role)} / {ctx.short(dst_role)}."))


# ================================================================================================ compensations (phase 60)
def _edges(ctx, p, from_nts=None):
    out = [e for e in ctx.pg.edge_types if e.source == p and not e.derived]
    return [e for e in out if from_nts is None or e.from_ in from_nts]


def apply_o06(ctx, f, opt):
    edges = _edges(ctx, f.subject)
    if opt == "materialize_closure":
        prof = ctx.profile
        for e in edges:
            dname = prof.edge(ctx.local(f.subject) + "Transitive")
            ctx.pg.edge_types.append(EdgeType(name=dname, from_=e.from_, to=e.to,
                                              reverse=prof.reverse(ctx.local(f.subject) + "Transitive"),
                                              source=f.subject, derived=True,
                                              note=f"Fermeture transitive de {e.name}, recalculée après ingestion."))
            add_materialization(ctx, f, "transitiveClosure", f"Calculer la fermeture transitive de {e.name} "
                                f"({e.from_} → {e.to}) dans {dname}.", edge_type=dname, chain=[e.name])
    elif opt == "var_length_query":
        for e in edges:
            e.note = f"Transitive : interroger avec -[:{e.name}*1..]-> (compensation complète en lecture, aucune contrainte)."


def apply_o07(ctx, f, opt):
    for e in _edges(ctx, f.subject):
        parents = [ctx.profile.edge(ctx.local(x)) for x in f.related]
        e.note = ((e.note + " ") if e.note else "") + f"Sous-propriété de {', '.join(parents)}."
        if opt == "materialize_closure":
            for par in f.related:
                pname = ctx.profile.edge(ctx.local(par))
                add_materialization(ctx, f, "superProperty", f"Pour chaque {e.name}, créer aussi {pname} "
                                    f"({e.from_} → {e.to}).", edge_type=e.name, parent=pname, chain=[e.name])
                if not any(x.name == pname and x.from_ == e.from_ and x.to == e.to for x in ctx.pg.edge_types):
                    ctx.pg.edge_types.append(EdgeType(name=pname, from_=e.from_, to=e.to, source=par, derived=True,
                                                      reverse=ctx.profile.reverse(ctx.local(par)),
                                                      note=f"Dérivée de {e.name} (O07)."))


def _chain_of(ctx, f) -> list[str]:
    v = ctx.onto.object_properties[f.subject]
    tail = f.id[len(f"O08:{f.subject}"):].lstrip(":")
    i = int(tail) - 1 if tail.isdigit() else 0
    return list(v.chains[i]) if i < len(v.chains) else list(f.related)


def apply_o08(ctx, f, opt):
    props = _chain_of(ctx, f)  # ordre ET répétitions conservés (SS §9.2.1)
    chain = [ctx.profile.edge(ctx.local(x)) for x in props]
    for e in [x for x in ctx.pg.edge_types if x.source == f.subject and not x.derived]:
        if opt == "materialize_closure":
            add_materialization(ctx, f, "propertyChain", f"Ajouter {e.name} pour chaque chemin {' / '.join(chain)} "
                                f"({e.from_} → {e.to}), en plus des {e.name} assertés.", edge_type=e.name, chain=chain)
            e.note = f"Assertée + matérialisée depuis {' ∘ '.join(chain)} (inclusion)."
        elif opt == "path_query":
            e.note = (f"Assertée ; compléter en lecture par le chemin {'/'.join(':' + c for c in chain)} "
                      f"(inclusion {' ∘ '.join(chain)} ⊑ {e.name}).")


def _restr(ctx, f):
    return ctx.cache.get("restr", {}).get(f.id, [])


def apply_card(ctx, f, opt):
    if opt == "ignore":
        return
    rule = f.rule
    if ":" in f.id[len(rule) + 1 + len(f.subject):]:  # constat de restriction (suffixe propriété)
        for c, r in _restr(ctx, f):
            nts = set(node_targets(ctx, c))
            edges = _edges(ctx, r.property, nts) if not r.inverse else \
                [e for e in ctx.pg.edge_types if e.source == r.property and e.to in nts]
            targets = {"node_types": sorted({nt for x in [r.filler] if x and ctx.is_class(x) for nt in node_targets(ctx, x)})}
            kind = {"O09": "cardinality", "O10": "existence", "O11": "allValuesFrom", "O12": "hasValue",
                    "O14": "existence", "O16": "cardinality", "O17": "other"}[rule]
            if rule == "O17" and opt == "materialize_at_ingest":
                for nt in sorted(nts):
                    pname = ctx.profile.prop("is" + upper_first(ctx.local(r.property)) + "Self")
                    t = ctx.pg.node_types[nt]
                    if not any(x.name == pname for x in t.properties):
                        t.properties.append(PGProperty(name=pname, type="Boolean", source=r.property,
                                                       note=f"Vrai si le nœud est relié à lui-même par {ctx.short(r.property)} (hasSelf)."))
                continue
            fill_scopes = {}
            if r.filler and ctx.is_class(r.filler):
                for nt in node_targets(ctx, r.filler):
                    fs = scope(ctx, r.filler, nt)
                    if fs:
                        fill_scopes[nt] = fs["values"]
            if fill_scopes:
                targets["target_discriminator_values"] = fill_scopes
            if not edges:
                for nt in sorted(nts):
                    sc = scope(ctx, c, nt)
                    add_validation(ctx, f, kind, f"{nt}{scope_text(sc)} : {f.detail}", node_type=nt,
                                   params={"property": r.property, "kind": r.kind, "n": r.n, "filler": r.filler,
                                           **({"discriminator": sc["discriminator"], "values": sc["values"]} if sc else {})})
                continue
            for e in edges:
                holder = e.to if r.inverse else e.from_
                sc = scope(ctx, c, holder)
                if rule == "O12" and opt == "materialize_at_ingest":
                    add_materialization(ctx, f, "classification", f"Créer {e.name} vers {ctx.short(str(r.value))} pour "
                                        f"chaque {e.from_}{scope_text(sc)}.", edge_type=e.name, node_type=e.from_)
                    continue
                if sc is None and not r.inverse:  # une restriction de sous-classe aplatie ne touche pas l'arête
                    if rule == "O10":
                        e.cardinality.out = {"0..*": "1..*", "1..*": "1..*", "0..1": "1", "1": "1"}[e.cardinality.out]
                    if rule == "O09" and (r.n or 0) <= 1:
                        lo = r.kind == "exactly" and r.n == 1 or e.cardinality.out in ("1", "1..*")
                        e.cardinality.out = "1" if lo else "0..1"
                desc = (f"{holder}{scope_text(sc)} : {f.detail}" +
                        (" (traversée inverse de " + e.name + ")" if r.inverse else ""))
                add_validation(ctx, f, kind, desc, node_type=holder, edge_type=e.name,
                               params={"kind": r.kind, "n": r.n, "filler": r.filler,
                                       "value": str(r.value) if r.value is not None else None,
                                       "direction": "in" if r.inverse else "out", **targets,
                                       **({"discriminator": sc["discriminator"], "values": sc["values"]} if sc else {})})
    else:  # O09 fonctionnelle (sujet = propriété)
        for e in _edges(ctx, f.subject):
            e.cardinality.out = "0..1" if e.cardinality.out == "0..*" else e.cardinality.out
            add_validation(ctx, f, "functional", f"{e.from_} : au plus une relation {e.name} sortante.",
                           node_type=e.from_, edge_type=e.name, params={"max": 1, "direction": "out"})


def apply_o13(ctx, f, opt):
    v = ctx.onto.object_properties[f.subject]
    for e in _edges(ctx, f.subject):
        for ch in sorted(set(v.characteristics) & {"irreflexive", "asymmetric", "reflexive"}):
            if ch == "reflexive" and opt != "validation":
                e.note = ((e.note + " ") if e.note else "") + "Réflexive : boucles implicites, jamais matérialisées."
                continue
            if opt == "validation":
                add_validation(ctx, f, ch if ch != "reflexive" else "other", f"{e.name} : {ch}.", edge_type=e.name,
                               node_type=e.from_, params={"characteristic": ch})


def apply_o15(ctx, f, opt):
    for e in _edges(ctx, f.subject):
        e.cardinality.in_ = "0..1"
        if opt == "validation":
            add_validation(ctx, f, "cardinality", f"{e.to} : au plus une relation {e.name} entrante.", node_type=e.to,
                           edge_type=e.name, params={"max": 1, "direction": "in"})


def apply_o20(ctx, f, opt):
    if opt != "validation":
        return
    a = sorted({e.name for e in _edges(ctx, f.subject)})
    b = sorted({e.name for q in f.related for e in _edges(ctx, q)})
    if a and b:
        add_validation(ctx, f, "disjoint", f"Aucune paire de nœuds reliée à la fois par {a[0]} et {b[0]}.",
                       edge_type=a[0], params={"edge_types": a + b})


def apply_o21(ctx, f, opt):
    if opt == "intersection_domain":
        for e in _edges(ctx, f.subject):
            add_validation(ctx, f, "other", f"La source de {e.name} est à la fois {' et '.join(ctx.short(x) for x in f.related)} "
                           "(intersection ; probable erreur de modélisation).", edge_type=e.name, node_type=e.from_,
                           params={"all_of": f.related})


def apply_o03(ctx, f, opt):
    edges = _edges(ctx, f.subject)
    if edges and opt == "relationship":
        add_validation(ctx, f, "allValuesFrom", f"{edges[0].name} : paires autorisées "
                       f"{', '.join(sorted({e.from_ + '→' + e.to for e in edges}))}.", edge_type=edges[0].name,
                       params={"pairs": sorted([e.from_, e.to] for e in edges)})


APPLY_BUILD = {"O06": apply_o06, "O07": apply_o07, "O08": apply_o08, "O13": apply_o13, "O15": apply_o15,
               "O20": apply_o20, "O21": apply_o21, "O03": apply_o03}
APPLY_BUILD.update({r: apply_card for r in REL_RULES})
