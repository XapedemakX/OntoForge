"""Arbitrages humains : validation et rejeu des décisions `{finding_id: option_id}`.

Une décision vers une option inconnue est ignorée (la recommandation s'applique) et produit un constat G02.
Une décision dont le constat n'existe plus (ontologie modifiée) est conservée dans `PGModel.decisions` pour être
rejouée si le constat réapparaît, sans effet entre-temps.
"""
from __future__ import annotations

from typing import Optional

from ..core.pg_model import Finding
from .rules._base import Ctx, finding


def resolve(ctx: Ctx, decisions: Optional[dict[str, Optional[str]]]) -> list[Finding]:
    extra: list[Finding] = []
    # décision groupée « <règle>:* » : vaut pour chaque constat de la règle sans décision individuelle
    for key, opt in sorted((decisions or {}).items()):
        if not key.endswith(":*") or not opt:
            continue
        rule = key[:-2]
        for f in sorted(ctx.findings.values(), key=lambda x: x.id):
            if f.rule == rule and f.id not in (decisions or {}) and opt in {o.id for o in f.options}:
                f.chosen = opt
    for fid, opt in sorted((decisions or {}).items()):
        if fid.endswith(":*"):
            continue
        f = ctx.findings.get(fid)
        if f is None or opt is None:
            continue
        if opt in {o.id for o in f.options}:
            f.chosen = opt
        else:
            g = finding(ctx, "G02", f.subject, f"Décision « {opt} » inconnue pour {fid} (options : "
                        f"{', '.join(o.id for o in f.options)}) : recommandation « {f.recommended} » appliquée.",
                        suffix=f"{f.rule}:{opt}", related=[fid])
            extra.append(g)
    return extra


def clean(decisions: Optional[dict[str, Optional[str]]]) -> dict[str, str]:
    return {k: v for k, v in sorted((decisions or {}).items()) if v}
