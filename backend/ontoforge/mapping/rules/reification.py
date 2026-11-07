"""Famille R — réification : R01 (binaire) / R02 (n-aire)."""
from __future__ import annotations

import re

from ._base import Ctx, finding

_TARGET_HINT = re.compile(r"(On|To|At|For|In|Of)$")


def roles(ctx: Ctx, c: str) -> list[str]:
    """Rôles fonctionnels : propriétés objet de domaine c, fonctionnelles ou restreintes à max/exactly 1 sur c."""
    out = set()
    for p, v in ctx.onto.object_properties.items():
        if v.domain == [c] and "functional" in v.characteristics:
            out.add(p)
    for r, _ in ctx.all_restrictions(c):
        if ctx.is_obj_prop(r.property) and not r.inverse and r.kind in ("max", "exactly") and (r.n or 0) == 1:
            out.add(r.property)
    return sorted(out)


def _data_props(ctx: Ctx, c: str) -> list[str]:
    return sorted(p for p, v in ctx.onto.datatype_properties.items() if c in v.domain)


def _is_referenced(ctx: Ctx, c: str) -> bool:
    return any(c in v.range for v in ctx.onto.object_properties.values())


def detect_r01(ctx: Ctx):
    out = []
    for c in sorted(ctx.onto.classes):
        rs = roles(ctx, c)
        if len(rs) == 2 and _data_props(ctx, c) and not _is_referenced(ctx, c) and not ctx.children(c):
            out.append(finding(ctx, "R01", c, f"{ctx.short(c)} relie exactement deux rôles fonctionnels "
                               f"({', '.join(ctx.short(r) for r in rs)}) et porte "
                               f"{', '.join(ctx.short(d) for d in _data_props(ctx, c))} : réification binaire.",
                               related=rs + _data_props(ctx, c)))
    return out


def detect_r02(ctx: Ctx):
    out = []
    for c in sorted(ctx.onto.classes):
        rs = roles(ctx, c)
        if len(rs) >= 3:
            out.append(finding(ctx, "R02", c, f"{ctx.short(c)} a {len(rs)} rôles fonctionnels "
                               f"({', '.join(ctx.short(r) for r in rs)}) : relation n-aire, non dé-réifiable.",
                               related=rs))
    return out


DETECT = {"R01": detect_r01, "R02": detect_r02}


def apply_r01(ctx: Ctx, f, opt):
    if opt != "dereify_relationship" or not ctx.profile.edge_properties:
        return
    rs = roles(ctx, f.subject)
    hinted = [r for r in rs if _TARGET_HINT.search(ctx.local(r))]
    to_role = hinted[0] if hinted else rs[-1]
    from_role = [r for r in rs if r != to_role][0]
    ctx.plan.setdefault("dereified", {})[f.subject] = {"roles": rs, "from_role": from_role, "to_role": to_role}


APPLY_PLAN = {"R01": apply_r01}
