"""Famille C — classes : détection C01–C13, plan de disposition des types de nœuds, construction.

Disposition (plan["mode"][classe]) :
  own            type de nœud propre
  fold           replié dans le type concret d'un ancêtre (discriminant `<racine>Kind`)  — héritage aplati
  merged         abstraite fusionnée dans ses sous-types (pas de type, propriétés recopiées vers le bas)
  abstract_label type abstrait (label secondaire porté par les sous-types, Neo4j)
  alias          fusionnée dans une classe équivalente (C05)
  computed       classe définie / conclusion de GCI : calculée sur un type de base (C06, C11, C13)
  union          union nommée documentée seulement (C09 doc_only) : se résout vers ses membres
  dereified      classe de réification devenue relation (R01, Neo4j)
  excluded       dépréciée exclue (A03)
"""
from __future__ import annotations

from typing import Optional

from ...core.onto_model import ClassExpr
from ...core.lang import label_lang
from ...core.pg_model import NodeType, PGProperty
from ._base import (Ctx, add_materialization, add_validation, expr_text, finding, named_conjuncts, sha8, walk,
                    canonical, upper_first, lower_first)


def _label(ctx: Ctx, iri: str) -> str:
    return ctx.onto.label(iri, label_lang())


def _classify_def(e: ClassExpr) -> str:
    if e.op == "oneOf":
        return "C08"
    if any(x.op == "not" for x in walk(e)):
        return "C11"
    if e.op == "or" and all(a.op == "named" for a in e.args):
        return "C09"
    return "C06"


# ================================================================================================ détection
def detect_c01(ctx: Ctx):
    return [finding(ctx, "C01", c, f"Classe {ctx.short(c)} ({_label(ctx, c)}).") for c in sorted(ctx.onto.classes)]


def hierarchy_root(ctx: Ctx, c: str) -> str:
    """Racine concrète de l'héritage simple : on remonte tant que le parent unique n'est pas probablement abstrait."""
    seen = {c}
    while True:
        ps = [p for p in ctx.onto.classes[c].sub_class_of if p in ctx.onto.classes]
        if len(ps) != 1 or ps[0] in seen or is_probably_abstract(ctx, ps[0]) or ctx.onto.classes[ps[0]].deprecated:
            return c
        c = ps[0]
        seen.add(c)


def detect_c02(ctx: Ctx):
    """Une décision par racine de hiérarchie (revue w3c it1) : elle vaut pour toutes les sous-classes à parent unique."""
    groups: dict[str, list[str]] = {}
    for c, v in sorted(ctx.onto.classes.items()):
        ps = [p for p in v.sub_class_of if p in ctx.onto.classes]
        if len(ps) == 1:
            r = hierarchy_root(ctx, c)
            if r != c:
                groups.setdefault(r, []).append(c)
    return [finding(ctx, "C02", r, f"Hiérarchie de {ctx.short(r)} : {len(m)} sous-classe(s) à parent unique "
                    f"({', '.join(ctx.short(x) for x in m)}) ; une décision pour toute la hiérarchie.", related=m)
            for r, m in sorted(groups.items())]


def primary_parent(ctx: Ctx, c: str) -> Optional[str]:
    ps = [p for p in ctx.onto.classes[c].sub_class_of if p in ctx.onto.classes] or ctx.parents(c)
    if not ps:
        return None

    def score(p):
        scope = [p] + ctx.ancestors(p)
        n = len(ctx.all_restrictions(p))
        n += sum(1 for d in ctx.onto.datatype_properties.values() if set(d.domain) & set(scope))
        n += sum(1 for d in ctx.onto.object_properties.values() if set(d.domain) & set(scope))
        return (-n, p)
    return sorted(ps, key=score)[0]


def detect_c03(ctx: Ctx):
    out = []
    for c, v in sorted(ctx.onto.classes.items()):
        ps = sorted(p for p in v.sub_class_of if p in ctx.onto.classes)
        if len(ps) >= 2:
            pp = primary_parent(ctx, c)
            out.append(finding(ctx, "C03", c, f"{ctx.short(c)} a {len(ps)} parents : "
                               f"{', '.join(ctx.short(p) for p in ps)} ; parent principal proposé : {ctx.short(pp)}.",
                               related=ps))
    return out


def _obj_involvement(ctx: Ctx, c: str) -> int:
    n = 0
    for p, v in ctx.onto.object_properties.items():
        if c in v.domain or c in v.range or c in v.domain_union or c in v.range_union:
            n += 1
    return n


def is_probably_abstract(ctx: Ctx, c: str) -> bool:
    v = ctx.onto.classes[c]
    return bool(ctx.children(c)) and not ctx.direct_instances(c) and not v.has_keys and not v.disjoint_union_of \
        and not ctx.class_definitions(c) and not ctx.all_restrictions(c) and _obj_involvement(ctx, c) <= 1


def detect_c04(ctx: Ctx):
    return [finding(ctx, "C04", c, f"{ctx.short(c)} a des sous-classes ({', '.join(ctx.short(x) for x in ctx.children(c))}) "
                    "et aucune instance directe connue : probablement abstraite (heuristique, OWA).",
                    related=ctx.children(c))
            for c in sorted(ctx.onto.classes) if is_probably_abstract(ctx, c)]


def detect_c05(ctx: Ctx):
    out, seen = [], set()
    for c, v in sorted(ctx.onto.classes.items()):
        for e in v.equivalent_to:
            if e.op == "named" and e.iri and e.iri != c:
                pair = frozenset((c, e.iri))
                if pair in seen:
                    continue
                seen.add(pair)
                out.append(finding(ctx, "C05", c, f"{ctx.short(c)} ≡ {ctx.short(e.iri)} : même extension ; "
                                   f"nom canonique proposé {ctx.short(c)}, alias {ctx.short(e.iri)}.", related=[e.iri]))
    return out


def _defs_of_kind(ctx: Ctx, rule: str):
    out = []
    for c in sorted(ctx.onto.classes):
        for e, node in ctx.class_definitions(c):
            if _classify_def(e) == rule:
                out.append((c, e, node))
        if rule in ("C09", "C11"):
            for e, node in ctx.anon_supers(c):
                if e.op in ("and", "or", "not") and _classify_def(e) == rule:
                    out.append((c, e, node))
    return out


def detect_c06(ctx: Ctx):
    out = []
    for c, e, node in _defs_of_kind(ctx, "C06"):
        ctx.consume(node)
        if f"C06:{c}" in {f.id for f in out}:
            continue
        out.append(finding(ctx, "C06", c, f"{ctx.short(c)} ≡ {expr_text(e, ctx.short)} : appartenance calculée "
                           "(condition nécessaire et suffisante), aucun raisonneur côté LPG.",
                           related=[x for x in named_conjuncts(e) if x != c]))
    return out


def detect_c07(ctx: Ctx):
    return [finding(ctx, "C07", c, f"{ctx.short(c)} disjointe de {', '.join(ctx.short(x) for x in sorted(v.disjoint_with))}.",
                    related=sorted(v.disjoint_with))
            for c, v in sorted(ctx.onto.classes.items()) if v.disjoint_with]


def detect_c08(ctx: Ctx):
    out = []
    for c, v in sorted(ctx.onto.classes.items()):
        members = list(v.one_of or [])
        for e, node in ctx.class_definitions(c):
            if e.op == "oneOf":
                members += e.individuals
                ctx.consume(node)
        if members:
            out.append(finding(ctx, "C08", c, f"{ctx.short(c)} = {{{', '.join(ctx.short(m) for m in members)}}}.",
                               related=sorted(set(members))))
    return out


def detect_c09(ctx: Ctx):
    out = []
    for c, e, node in _defs_of_kind(ctx, "C09"):
        ctx.consume(node)
        kind = "équivalente à" if any(n is node for _, n in ctx.class_definitions(c)) else "sous-classe de"
        out.append(finding(ctx, "C09", c, f"{ctx.short(c)} {kind} {expr_text(e, ctx.short)} (expression anonyme).",
                           related=[a.iri for a in e.args if a.op == "named" and a.iri],
                           reco=None if kind == "équivalente à" else {"curiosity": "doc_only", "neo4j": "doc_only"},
                           suffix=None if not any(f.id == f"C09:{c}" for f in out) else sha8(canonical(ctx.g, node))))
    return out


def detect_c10(ctx: Ctx):
    return [finding(ctx, "C10", c, f"{ctx.short(c)} = union disjointe de {', '.join(ctx.short(x) for x in du)}.",
                    related=du)
            for c, v in sorted(ctx.onto.classes.items()) for du in v.disjoint_union_of[:1]]


def detect_c11(ctx: Ctx):
    out = []
    for c, e, node in _defs_of_kind(ctx, "C11"):
        ctx.consume(node)
        if not any(f.id == f"C11:{c}" for f in out):
            out.append(finding(ctx, "C11", c, f"{ctx.short(c)} : {expr_text(e, ctx.short)} — complément (monde ouvert) "
                               "→ négation par défaut en LPG (monde clos).",
                               related=[x.iri for x in walk(e) if x.op == "named" and x.iri and x.iri != c]))
    return out


def detect_c12(ctx: Ctx):
    return [finding(ctx, "C12", c, f"{ctx.short(c)} est à la fois une classe et un individu (punning, SS §5.9).",
                    related=ctx.onto.individuals[c].types)
            for c in sorted(ctx.onto.classes) if c in ctx.onto.individuals]


def detect_c13(ctx: Ctx):
    out = []
    for lhs, rhs, node in ctx.gcis():
        ctx.consume(node)
        out.append(finding(ctx, "C13", rhs, f"GCI : {expr_text(lhs, ctx.short)} ⊑ {ctx.short(rhs)}.",
                           suffix=sha8(canonical(ctx.g, node)),
                           related=[x.iri for x in walk(lhs) if x.op == "named" and x.iri]))
    return out


DETECT = {"C01": detect_c01, "C02": detect_c02, "C03": detect_c03, "C04": detect_c04, "C05": detect_c05,
          "C06": detect_c06, "C07": detect_c07, "C08": detect_c08, "C09": detect_c09, "C10": detect_c10,
          "C11": detect_c11, "C12": detect_c12, "C13": detect_c13}


# ================================================================================================ plan (phase 10)
def _plan(ctx: Ctx) -> dict:
    p = ctx.plan
    for k in ("mode", "canonical", "child_choice", "computed", "extra_parents", "flags", "aliases"):
        p.setdefault(k, {})
    p.setdefault("required_disc", set())
    return p


def apply_c02(ctx: Ctx, f, opt):
    for m in f.related:
        _plan(ctx)["child_choice"].setdefault(m, opt)


def apply_c03(ctx: Ctx, f, opt):
    _plan(ctx)["child_choice"][f.subject] = opt


def apply_c04(ctx: Ctx, f, opt):
    mode = {"merge_into_leaves": "merged", "secondary_label": "abstract_label"}.get(opt)
    if mode:
        _plan(ctx).setdefault("c04", {})[f.subject] = mode


def apply_c05(ctx: Ctx, f, opt):
    if opt == "merge_types":
        p = _plan(ctx)
        for other in f.related:
            p["mode"][other] = "alias"
            p["canonical"][other] = f.subject


def _base_classes(ctx: Ctx, c: str, f) -> list[str]:
    for e, _ in ctx.class_definitions(c):
        b = [x for x in named_conjuncts(e) if x != c and x in ctx.onto.classes]
        if b:
            return b[:1]
    if f.rule == "C13":
        for lhs, rhs, _ in ctx.gcis():
            if rhs == c:
                b = [x for x in named_conjuncts(lhs) if x in ctx.onto.classes]
                if b:
                    return b[:1]
    return [x for x in f.related if x in ctx.onto.classes and x != c][:1]


def apply_computed(ctx: Ctx, f, opt):
    p = _plan(ctx)
    p["mode"][f.subject] = "computed"
    p["computed"].setdefault(f.subject, {"base": _base_classes(ctx, f.subject, f), "opt": opt, "finding": f})


def apply_c09(ctx: Ctx, f, opt):
    p = _plan(ctx)
    is_def = any(e.op == "or" for e, _ in ctx.class_definitions(f.subject))
    if not is_def:
        return  # union en super-classe (axiome de couverture) : documentée, la classe reste un type
    if opt == "secondary_label":
        p["mode"][f.subject] = "abstract_label"
        for m in f.related:
            p["extra_parents"].setdefault(m, []).append(f.subject)
    else:
        p["mode"][f.subject] = "union"
        p.setdefault("union_members", {})[f.subject] = list(f.related)


def apply_c10(ctx: Ctx, f, opt):
    p = _plan(ctx)
    for ch in f.related:
        p["child_choice"].setdefault(ch, "flatten_into_leaves" if opt == "primary_parent_discriminator" else "node_type")
    if opt == "primary_parent_discriminator":
        p["required_disc"].add(f.subject)


def apply_c12(ctx: Ctx, f, opt):
    pass  # le type (classe) et le nœud de référence (individu) sont nommés distinctement par I01/N01


APPLY_PLAN = {"C02": apply_c02, "C03": apply_c03, "C04": apply_c04, "C05": apply_c05, "C06": apply_computed,
              "C11": apply_computed, "C13": apply_computed, "C09": apply_c09, "C10": apply_c10, "C12": apply_c12}


# ================================================================================================ layout (phase 20)
def resolve_modes(ctx: Ctx) -> None:
    p = _plan(ctx)
    modes = p["mode"]
    for c in sorted(ctx.onto.classes):
        v = ctx.onto.classes[c]
        if v.deprecated and p.get("deprecated", {}).get(c, "exclude") == "exclude":
            modes[c] = "excluded"
    for c in p.get("dereified", {}):
        modes[c] = "dereified"
    p["root"] = {}

    def mode(c: str, stack=()) -> str:
        if c in modes:
            return modes[c]
        if c in stack:
            return "own"
        choice = p["child_choice"].get(c)
        parent = primary_parent(ctx, c) if choice else None
        if parent and choice in ("flatten_into_leaves", "primary_parent_discriminator") or \
                (parent and choice == "multi_label" and not ctx.profile.multi_label):
            pm = mode(parent, stack + (c,))
            if pm in ("own", "fold"):
                modes[c] = "fold"
                p["root"][c] = p["root"].get(parent, parent) if pm == "fold" else parent
                if choice == "multi_label":
                    p.setdefault("list_disc", set()).add(p["root"][c])
                return "fold"
        modes[c] = p.get("c04", {}).get(c, "own")
        return modes[c]

    for c in sorted(ctx.onto.classes):
        mode(c)
    # C03 : appartenances secondaires → booléens is<Parent> sur la racine
    for f in ctx.by_rule("C03"):
        c = f.subject
        if modes.get(c) == "fold" and ctx.option(f.id) == "primary_parent_discriminator":
            pp = primary_parent(ctx, c)
            for other in f.related:
                if other != pp:
                    p["flags"].setdefault(p["root"][c], []).append(("is" + upper_first(ctx.local(other)), other, c))


def canonical_of(ctx: Ctx, c: str) -> str:
    seen = set()
    while ctx.plan["mode"].get(c) == "alias" and c not in seen:
        seen.add(c)
        c = ctx.plan["canonical"][c]
    return c


def node_targets(ctx: Ctx, c: str, _stack=()) -> list[str]:
    """Noms des types de nœuds où vivent les instances de la classe `c`."""
    key = ("nt", c)
    if key in ctx.cache:
        return ctx.cache[key]
    if c in _stack or c not in ctx.onto.classes:
        return []
    p = ctx.plan
    m = p["mode"].get(c, "own")
    out: list[str] = []
    if m == "alias":
        out = node_targets(ctx, canonical_of(ctx, c), _stack + (c,))
    elif m == "fold":
        out = [p["nt_name"][p["root"][c]]]
        # sous-classes concrètes (types propres) sous une classe repliée : elles héritent aussi (recopie dans les feuilles)
        for ch in ctx.children(c):
            if p["mode"].get(ch) in ("own", "merged", "abstract_label", "fold"):
                out += node_targets(ctx, ch, _stack + (c,))
    elif m == "computed":
        for b in p["computed"][c]["base"]:
            out += node_targets(ctx, b, _stack + (c,))
    elif m == "union":
        for b in p.get("union_members", {}).get(c, []):
            out += node_targets(ctx, b, _stack + (c,))
    elif m in ("excluded", "dereified"):
        out = []
    else:
        if m in ("own", "abstract_label"):
            out.append(p["nt_name"][c])
        if not (ctx.profile.multi_label and m in ("own", "abstract_label")):
            for ch in ctx.children(c):
                if p["mode"].get(ch) in ("own", "merged", "abstract_label", "fold"):
                    out += node_targets(ctx, ch, _stack + (c,))
    res = sorted(set(out))
    ctx.cache[key] = res
    return res


def scope(ctx: Ctx, c: str, nt_name: Optional[str]) -> Optional[dict]:
    """Restriction / contrainte portée par `c` appliquée au type `nt_name` : None si elle vaut pour tout le type
    (c est la classe du type ou un ancêtre) ; sinon filtre par discriminant (sous-classe repliée, héritage aplati)."""
    if not nt_name or c not in ctx.onto.classes:
        return None
    owner = ctx.plan.get("nt_owner", {}).get(nt_name)
    if owner is None:
        return None
    c0 = canonical_of(ctx, c)
    if ctx.subsumes(c0, owner) or ctx.plan["mode"].get(c0) in ("merged", "computed", "union"):
        return None
    nt = ctx.pg.node_types.get(nt_name)
    vals = sorted({ctx.profile.node(ctx.local(x)) for x in [c0] + ctx.descendants(c0)
                   if ctx.plan["mode"].get(x) == "fold" and ctx.plan["root"].get(x) == owner})
    if not vals:
        return None
    return {"discriminator": nt.discriminator if nt else None, "values": vals, "scope_class": c0}


def scope_text(sc: Optional[dict]) -> str:
    return f" [si {sc['discriminator']} ∈ {{{', '.join(sc['values'])}}}]" if sc else ""


def build_nodes(ctx: Ctx) -> None:
    resolve_modes(ctx)
    p, pg = ctx.plan, ctx.pg
    p["nt_name"] = {}
    used: dict[str, str] = {}
    for c in sorted(ctx.onto.classes):
        if p["mode"][c] not in ("own", "abstract_label"):
            continue
        name = ctx.profile.node(ctx.local(c))
        if name in used:  # collision de noms (namespaces différents) : suffixe déterministe (N01 en fin d'analyse)
            p.setdefault("collisions", []).append((name, used[name], c))
            name = f"{name}{len(used)}"
        used[name] = c
        p["nt_name"][c] = name
        p.setdefault("nt_owner", {})[name] = c
    for c, name in sorted(p["nt_name"].items(), key=lambda kv: kv[1]):
        v = ctx.onto.classes[c]
        labels = [name]
        if ctx.profile.multi_label:
            for a in [x for x in ctx.ancestors(c)] + p["extra_parents"].get(c, []):
                a = canonical_of(ctx, a)
                if p["mode"].get(a) in ("own", "abstract_label") and p["nt_name"].get(a) not in labels:
                    labels.append(p["nt_name"][a])
        desc = v.comments.get(label_lang()) or v.comments.get("fr") or v.comments.get("en") or ctx.onto.label(c, label_lang())
        pg.node_types[name] = NodeType(name=name, labels=labels, source=[c], description=desc,
                                       abstract=p["mode"][c] == "abstract_label")
    # sources : classes repliées, fusionnées, alias
    for c in sorted(ctx.onto.classes):
        m = p["mode"][c]
        if m in ("fold", "alias", "merged", "computed", "union"):
            for nt in node_targets(ctx, c):
                if c not in pg.node_types[nt].source:
                    pg.node_types[nt].source.append(c)
    # discriminants des hiérarchies aplaties
    folded: dict[str, list[str]] = {}
    for c, root in sorted(p["root"].items()):
        folded.setdefault(root, []).append(c)
    for root, kids in sorted(folded.items()):
        nt = pg.node_types[p["nt_name"][root]]
        values = sorted({ctx.profile.node(ctx.local(k)) for k in kids} |
                        ({nt.name} if not is_probably_abstract(ctx, root) else set()))
        as_list = root in p.get("list_disc", set())
        dname = ctx.profile.prop(lower_first(ctx.local(root)) + ("Types" if as_list else "Kind"))
        nt.discriminator, nt.discriminator_values = dname, values
        req = root in p["required_disc"]
        nt.properties.append(PGProperty(name=dname, type="String", is_list=as_list, required=req, enum=values,
                                        indexed=True, source=root,
                                        note="Discriminant de l'héritage aplati : " + ", ".join(ctx.short(k) for k in kids)))
    # Curiosity (mono-type) : multi_label demandé sur un type propre → liste des types OWL portés
    if not ctx.profile.multi_label:
        for c, choice in sorted(p["child_choice"].items()):
            if choice == "multi_label" and p["mode"].get(c) == "own" and c in p["nt_name"]:
                nt = pg.node_types[p["nt_name"][c]]
                tname = ctx.profile.prop(lower_first(ctx.local(c)) + "Types")
                if not any(x.name == tname for x in nt.properties):
                    vals = sorted({ctx.profile.node(ctx.local(x)) for x in [c] + ctx.ancestors(c) + ctx.descendants(c)})
                    nt.properties.append(PGProperty(name=tname, type="String", is_list=True, enum=vals, indexed=True,
                                                    source=c, note="Types OWL portés par le nœud (multi_label émulé, C02/C03)."))
    for root, flags in sorted(p["flags"].items()):
        nt = pg.node_types[p["nt_name"][root]]
        for fname, other, child in flags:
            pname = ctx.profile.prop(fname)
            if not any(x.name == pname for x in nt.properties):
                nt.properties.append(PGProperty(name=pname, type="Boolean", source=other,
                                                note=f"Appartenance secondaire de {ctx.short(child)} (C03)."))


# ================================================================================================ validations (phase 60)
def apply_c06_build(ctx: Ctx, f, opt):
    c = f.subject
    info = ctx.plan["computed"].get(c, {})
    bases = [nt for b in info.get("base", []) for nt in node_targets(ctx, b)]
    definition = "; ".join(expr_text(e, ctx.short) for e, _ in ctx.class_definitions(c)) or f.detail
    if opt == "doc_only":
        return
    for nt in sorted(set(bases)):
        if opt == "materialize_at_ingest":
            pname = ctx.profile.prop("is" + upper_first(ctx.local(c)))
            ntype = ctx.pg.node_types[nt]
            if not any(x.name == pname for x in ntype.properties):
                ntype.properties.append(PGProperty(name=pname, type="Boolean", source=c,
                                                   note=f"Calculé à l'ingestion : {definition}"))
        add_materialization(ctx, f, "classification", f"Classer les nœuds {nt} vérifiant {definition} "
                            f"({'label ' + ctx.profile.node(ctx.local(c)) if opt == 'computed_label' else 'booléen'}).",
                            node_type=nt, definition=definition)


def _disc_values(ctx: Ctx, c: str, nt: str) -> Optional[set]:
    t = ctx.pg.node_types[nt]
    if not t.discriminator or any(x.is_list for x in t.properties if x.name == t.discriminator):
        return None
    sc = scope(ctx, c, nt)
    return set(sc["values"]) if sc else set(t.discriminator_values)


def _guaranteed(ctx: Ctx, a: str, b: str) -> bool:
    """Mono-type Curiosity : disjonction garantie si les types diffèrent ou si un discriminant scalaire les sépare."""
    if ctx.profile.multi_label:
        return False
    for nt in set(node_targets(ctx, a)) & set(node_targets(ctx, b)):
        va, vb = _disc_values(ctx, a, nt), _disc_values(ctx, b, nt)
        if va is None or vb is None or va & vb:
            return False
    return True


def apply_c07_build(ctx: Ctx, f, opt):
    seen = ctx.plan.setdefault("disjoint_pairs", set())
    pairs = [o for o in f.related]
    if pairs and all(_guaranteed(ctx, f.subject, o) for o in pairs):
        f.severity = "auto"
        f.detail += " Garanti par construction (types de nœuds distincts ou discriminant scalaire)."
        return
    if opt != "validation":
        return
    for other in pairs:
        pair = frozenset((f.subject, other))
        if pair in seen or _guaranteed(ctx, f.subject, other):
            continue
        seen.add(pair)
        a, b = node_targets(ctx, f.subject), node_targets(ctx, other)
        same = sorted(set(a) & set(b))
        add_validation(ctx, f, "disjoint", f"Aucun nœud n'est à la fois {ctx.short(f.subject)} et {ctx.short(other)}"
                       + (f" (types partagés : {', '.join(same)})" if same else "") + ".",
                       node_type=(a or [None])[0], params={"classes": [f.subject, other], "node_types": [a, b]})


def apply_c08_build(ctx: Ctx, f, opt):
    nts = node_targets(ctx, f.subject)
    values = [ctx.local(m) for m in f.related]
    for nt in nts:
        t = ctx.pg.node_types[nt]
        t.description = (t.description or "") + f" Données de référence : {', '.join(values)}."
        if opt == "reference_nodes":
            ref = ctx.plan.setdefault("reference_nodes", {})
            ref.setdefault(nt, []).extend(m for m in f.related if m in ctx.onto.individuals)
            add_validation(ctx, f, "enum", f"Les nœuds {nt} appartiennent à l'énumération {{{', '.join(values)}}}.",
                           node_type=nt, params={"values": f.related})
    if opt == "enum_property":
        ctx.plan.setdefault("enum_classes", {})[f.subject] = f.related


def apply_c10_build(ctx: Ctx, f, opt):
    nts = node_targets(ctx, f.subject)
    for nt in nts:
        add_validation(ctx, f, "enum" if opt == "primary_parent_discriminator" else "other",
                       f"Chaque {nt} appartient à exactement un sous-type parmi "
                       f"{', '.join(ctx.short(x) for x in f.related)} (partition).",
                       node_type=nt, params={"exactly_one_of": f.related})


APPLY_BUILD = {"C06": apply_c06_build, "C11": apply_c06_build, "C13": apply_c06_build, "C07": apply_c07_build,
               "C08": apply_c08_build, "C10": apply_c10_build}
