"""Famille N — nommage : N01 (conventions, collisions) + contrôle final d'unicité des noms."""
from __future__ import annotations

import re

from ._base import Ctx, finding, upper_first, lower_first


def _key(local: str) -> str:
    return re.sub(r"[^a-z0-9]", "", local.lower())


def _camel(local: str) -> str:
    parts = [p for p in re.split(r"[^0-9A-Za-z]+", local) if p]
    return lower_first(parts[0]) + "".join(upper_first(p) for p in parts[1:]) if parts else local


def _kind(ctx: Ctx, iri: str) -> str:
    return "class" if ctx.is_class(iri) else ("object" if ctx.is_obj_prop(iri) else "data")


def detect_n01(ctx: Ctx):
    ents = sorted(set(ctx.onto.classes) | set(ctx.onto.object_properties) | set(ctx.onto.datatype_properties))
    out: dict[str, object] = {}
    for iri in ents:
        loc = ctx.local(iri)
        if re.search(r"[^0-9A-Za-z]", loc) or (loc and loc[0].isdigit()):
            k = _kind(ctx, iri)
            target = (ctx.profile.node(loc) if k == "class" else ctx.profile.edge(loc) if k == "object"
                      else ctx.profile.prop(loc))
            out[iri] = finding(ctx, "N01", iri, f"{ctx.short(iri)} : nom hors convention → {target}.")
    groups: dict[str, list[str]] = {}
    for iri in ents:
        groups.setdefault(_key(ctx.local(iri)), []).append(iri)
    for key, members in sorted(groups.items()):
        if len(members) < 2:
            continue
        classes = [m for m in members if ctx.is_class(m)]
        others = [m for m in members if not ctx.is_class(m)] if classes else members[1:]
        for m in others:
            rel = classes or [members[0]]
            new = "has" + upper_first(ctx.local(m)) if ctx.is_obj_prop(m) else ctx.local(m)
            txt = (f"{ctx.short(m)} et {', '.join(ctx.short(r) for r in rel)} ont le même nom après normalisation "
                   f"(« {key} ») ; renommage proposé : {new}.")
            if m in out:
                out[m].detail += " " + txt
                out[m].related = sorted(set(out[m].related) | set(rel))
            else:
                out[m] = finding(ctx, "N01", m, txt, related=rel)
    return [out[k] for k in sorted(out)]


DETECT = {"N01": detect_n01}


def apply_n01(ctx: Ctx, f, opt):
    if opt != "rename":
        return
    loc = ctx.local(f.subject)
    rename = ctx.plan.setdefault("rename", {})
    if f.related and ctx.is_obj_prop(f.subject):
        rename[f.subject] = "has" + upper_first(_camel(loc))
    elif re.search(r"[^0-9A-Za-z]", loc):
        rename[f.subject] = upper_first(_camel(loc)) if ctx.is_class(f.subject) else _camel(loc)


APPLY_PLAN = {"N01": apply_n01}


def finalize(ctx: Ctx) -> list:
    """Unicité des noms dans le PGModel final ; renvoie des constats N01 supplémentaires (auto, appliqués)."""
    extra = []
    pg = ctx.pg
    nodes = set(pg.node_types)
    if ctx.target == "curiosity":
        for e in pg.edge_types:
            if e.name in nodes:
                old = e.name
                e.name = "Has" + e.name
                if e.reverse == old:
                    e.reverse = e.name
                fid = f"N01:{e.source}"
                if fid not in ctx.findings and e.source:
                    extra.append(finding(ctx, "N01", e.source, f"Arête {old} = nom d'un type de nœud : renommée {e.name}.",
                                         related=[old]))
    for nt in pg.node_types.values():
        seen: dict[str, str] = {}
        for p in nt.properties:
            if p.name in seen and seen[p.name] != p.source:
                old, p.name = p.name, f"{p.name}{len(seen)}"
                fid = f"N01:{p.source}"
                if p.source and fid not in ctx.findings and fid not in {x.id for x in extra}:
                    extra.append(finding(ctx, "N01", p.source, f"Propriété {old} en double sur {nt.name} : renommée {p.name}."))
            seen.setdefault(p.name, p.source)
    for name, c1, c2 in ctx.plan.get("collisions", []):
        fid = f"N01:{c2}"
        if fid not in ctx.findings:
            extra.append(finding(ctx, "N01", c2, f"Type de nœud {name} déjà utilisé par {ctx.short(c1)} : nom suffixé.",
                                 related=[c1]))
    return extra
