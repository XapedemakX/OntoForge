"""Propositions de zones métier : périmètres, hiérarchie, espaces de noms, communautés (Louvain écrit à la main), LLM (titres).

Chaque stratégie renvoie des groupes de nœuds ; ``_finalize`` les transforme en zones (identifiants, couleurs, sous-titres),
rattache les nœuds restants à une zone « Autres » et plafonne le nombre de zones.
"""
from __future__ import annotations

import json
import logging
import random
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any, Optional

from .graph import SchemaGraph, link_weights
from .model import Zone
from .roles import ZONE_COLORS

log = logging.getLogger(__name__)

STRATEGIES = ("perimeters", "hierarchy", "namespace", "communities", "llm")
MIN_ZONES = 4
MAX_ZONES = 8
OTHER_ID = "other"
OTHER_COLOR = "#f1f2f4"
OTHER_TITLE = {"fr": "Autres", "en": "Other"}


@dataclass
class ZoneProposal:
    zones: list[Zone]
    strategy: str
    warnings: list[str] = field(default_factory=list)


def slug(text: str) -> str:
    s = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii").lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")[:30] or "zone"


def other_zone(members: list[str], lang: str) -> Zone:
    return Zone(id=OTHER_ID, title=OTHER_TITLE.get(lang, "Other"), subtitle="", color=OTHER_COLOR, members=members)


def _degree(g: SchemaGraph) -> dict[str, int]:
    deg = {k: 0 for k in g.nodes}
    for (a, b), w in link_weights(g).items():
        deg[a] += w
        deg[b] += w
    return deg


def subtitle_for(members: list[str], g: SchemaGraph, deg: dict[str, int], lang: str) -> str:
    top = sorted(members, key=lambda k: (-deg.get(k, 0), g.nodes[k].label))[:3]
    names = ", ".join(g.nodes[k].label for k in top) + ("…" if len(members) > 3 else "")
    return f"{len(members)} types : {names}" if lang == "fr" else f"{len(members)} types: {names}"


def _attach_orphans(groups: list[dict], orphans: list[str], g: SchemaGraph) -> list[str]:
    """Rattache chaque nœud sans groupe au groupe auquel il est le plus lié ; renvoie ceux qui n'ont aucun lien."""
    w = link_weights(g)
    adj: dict[str, dict[str, int]] = {}
    for (a, b), x in w.items():
        adj.setdefault(a, {})[b] = x
        adj.setdefault(b, {})[a] = x
    where = {m: i for i, grp in enumerate(groups) for m in grp["members"]}
    pending = list(orphans)
    for _ in range(4):
        left = []
        for n in pending:
            score: dict[int, int] = {}
            for nb, x in adj.get(n, {}).items():
                if nb in where:
                    score[where[nb]] = score.get(where[nb], 0) + x
            if score:
                best = max(sorted(score), key=lambda i: score[i])
                groups[best]["members"].append(n)
                where[n] = best
            else:
                left.append(n)
        if len(left) == len(pending):
            break
        pending = left
    return pending


def _finalize(groups: list[dict], g: SchemaGraph, lang: str, max_zones: int = MAX_ZONES, min_size: int = 2,
              attach: bool = True) -> list[Zone]:
    """groups : [{title, subtitle?, members}] ; ne garde que les groupes d'au moins ``min_size`` nœuds (les autres retombent dans « Autres »)."""
    deg = _degree(g)
    seen: set[str] = set()
    clean: list[dict] = []
    for grp in groups:
        ms = [m for m in grp["members"] if m in g.nodes and m not in seen]
        seen.update(ms)
        clean.append({**grp, "members": ms})
    big = [c for c in clean if len(c["members"]) >= min_size]
    small = [c for c in clean if len(c["members"]) < min_size]
    big.sort(key=lambda c: (-len(c["members"]), c["title"]))
    if len(big) > max_zones - 1:
        small += big[max_zones - 1:]
        big = big[:max_zones - 1]
    orphans = [m for c in small for m in c["members"]] + [k for k in g.nodes if k not in seen]
    if attach and big:
        orphans = _attach_orphans(big, orphans, g)
    zones: list[Zone] = []
    used: set[str] = set()
    for i, c in enumerate(big):
        zid = f"z-{slug(c['title'])}"
        while zid in used or zid == OTHER_ID:
            zid += "-2"
        used.add(zid)
        ms = sorted(c["members"], key=lambda k: (-deg.get(k, 0), g.nodes[k].label))
        zones.append(Zone(id=zid, title=c["title"], subtitle=c.get("subtitle") or subtitle_for(ms, g, deg, lang),
                          color=ZONE_COLORS[i % len(ZONE_COLORS)], members=ms))
    if orphans:
        zones.append(other_zone(sorted(orphans, key=lambda k: (-deg.get(k, 0), g.nodes[k].label)), lang))
    return zones


# ----------------------------------------------------------------------------- stratégies
def by_perimeters(g: SchemaGraph, perimeters: list[Any], lang: str, max_zones: int = MAX_ZONES) -> ZoneProposal:
    groups = []
    for per in perimeters:
        ms = [k for k, n in g.nodes.items() if per.id in n.perimeters]
        if ms:
            groups.append({"title": per.name, "subtitle": per.description or "", "members": ms})
    warns = [] if groups else ["Aucun périmètre ne couvre de type : définissez des périmètres ou choisissez une autre stratégie."]
    return ZoneProposal(_finalize(groups, g, lang, max_zones, min_size=1, attach=False), "perimeters", warns)


def _hier_children(g: SchemaGraph) -> tuple[list[str], dict[str, list[str]]]:
    children: dict[str, list[str]] = {k: [] for k in g.nodes}
    for k, n in g.nodes.items():
        if n.parents:
            children[sorted(n.parents)[0]].append(k)  # héritage multiple : première branche
    roots = sorted(k for k, n in g.nodes.items() if not n.parents)
    return roots, children


def _subtree(k: str, children: dict[str, list[str]]) -> list[str]:
    out, stack = [], [k]
    while stack:
        x = stack.pop()
        if x not in out:
            out.append(x)
            stack.extend(sorted(children.get(x, []), reverse=True))
    return out


def by_hierarchy(g: SchemaGraph, lang: str, max_zones: int = MAX_ZONES) -> ZoneProposal:
    roots, children = _hier_children(g)
    heads = list(roots)
    extra: dict[str, list[str]] = {}  # tête éclatée → elle-même, rattachée à sa première branche

    def size(h: str) -> int:
        return len(_subtree(h, children))
    multi = [h for h in heads if size(h) >= 2]
    # on éclate la plus grosse branche tant qu'il y a trop peu de grandes branches
    while len(multi) < MIN_ZONES:
        cand = [h for h in multi if children[h] and h not in extra]
        if not cand:
            break
        big = max(cand, key=lambda h: (size(h), h))
        heads.remove(big)
        kids = sorted(children[big])
        heads.extend(kids)
        extra[big] = [kids[0]]
        multi = [h for h in heads if size(h) >= 2]
    groups = []
    for h in heads:
        ms = _subtree(h, children)
        groups.append({"title": g.nodes[h].label, "members": ms})
    for owner, (first,) in extra.items():
        for grp in groups:
            if first in grp["members"]:
                grp["members"].append(owner)
                break
    warns = [] if any(c for c in children.values()) else ["Aucune hiérarchie de classes : les zones sont formées par rattachement aux types les plus liés."]
    return ZoneProposal(_finalize(groups, g, lang, max_zones), "hierarchy", warns)


def by_namespace(g: SchemaGraph, lang: str, prefixes: Optional[dict[str, str]] = None, max_zones: int = MAX_ZONES) -> ZoneProposal:
    spaces: dict[str, list[str]] = {}
    for k, n in g.nodes.items():
        spaces.setdefault(n.namespace, []).append(k)
    if len(spaces) <= 1:
        prop = by_hierarchy(g, lang, max_zones)
        prop.strategy = "namespace"
        prop.warnings.insert(0, "Un seul espace de noms : repli sur la hiérarchie.")
        return prop
    rev = {v: k for k, v in (prefixes or {}).items() if k}
    groups = []
    for ns, ms in spaces.items():
        title = rev.get(ns) or (re.split(r"[#/]", ns.rstrip("#/"))[-1] if ns else "") or ("sans espace de noms" if lang == "fr" else "no namespace")
        groups.append({"title": title, "subtitle": ns, "members": ms})
    return ZoneProposal(_finalize(groups, g, lang, max_zones), "namespace", [])


def louvain(nodes: list[str], weights: dict[tuple[str, str], float], seed: int = 0) -> dict[str, str]:
    """Détection de communautés par optimisation de la modularité (méthode de Louvain, deux phases répétées). Déterministe pour une graine."""
    adj: dict[str, dict[str, float]] = {n: {} for n in nodes}
    for (a, b), w in weights.items():
        adj[a][b] = adj[a].get(b, 0) + w
        adj[b][a] = adj[b].get(a, 0) + w
    m2 = sum(sum(d.values()) for d in adj.values())
    member_of = {n: n for n in nodes}  # nœud d'origine → nœud agrégé courant
    if m2 == 0:
        return member_of
    self_w = {n: 0.0 for n in nodes}
    rng = random.Random(seed)
    for _ in range(10):
        comm = {n: n for n in adj}
        deg = {n: sum(adj[n].values()) + 2 * self_w[n] for n in adj}
        tot = dict(deg)
        order = sorted(adj)
        moved_any = False
        for _round in range(50):
            rng.shuffle(order)
            improved = False
            for n in order:
                c0 = comm[n]
                wc: dict[str, float] = {}
                for nb, w in adj[n].items():
                    wc[comm[nb]] = wc.get(comm[nb], 0) + w
                tot[c0] -= deg[n]
                best_c, best_gain = c0, wc.get(c0, 0) - tot[c0] * deg[n] / m2
                for c in sorted(wc):
                    gain = wc[c] - tot[c] * deg[n] / m2
                    if gain > best_gain + 1e-12:
                        best_c, best_gain = c, gain
                tot[best_c] += deg[n]
                if best_c != c0:
                    comm[n] = best_c
                    improved = moved_any = True
            if not improved:
                break
        if not moved_any:
            break
        for n in member_of:
            member_of[n] = comm[member_of[n]]
        new_adj: dict[str, dict[str, float]] = {c: {} for c in set(comm.values())}
        new_self = {c: 0.0 for c in new_adj}
        for n, nbs in adj.items():
            new_self[comm[n]] += self_w[n]
            for nb, w in nbs.items():
                if comm[n] == comm[nb]:
                    new_self[comm[n]] += w / 2
                else:
                    new_adj[comm[n]][comm[nb]] = new_adj[comm[n]].get(comm[nb], 0) + w
        adj, self_w = new_adj, new_self
    return member_of


def by_communities(g: SchemaGraph, lang: str, seed: int = 0, max_zones: int = MAX_ZONES) -> ZoneProposal:
    w = {k: float(v) for k, v in link_weights(g).items()}
    comm = louvain(sorted(g.nodes), w, seed)
    groups_by: dict[str, list[str]] = {}
    for k, c in comm.items():
        groups_by.setdefault(c, []).append(k)
    deg = _degree(g)
    groups = []
    for ms in groups_by.values():
        hub = sorted(ms, key=lambda k: (-deg[k], g.nodes[k].label))[0]
        groups.append({"title": ("Autour de " if lang == "fr" else "Around ") + g.nodes[hub].label, "members": ms})
    warns = [] if w else ["Aucune relation entre les types : aucune communauté à détecter."]
    return ZoneProposal(_finalize(groups, g, lang, max_zones), "communities", warns)


# ----------------------------------------------------------------------------- LLM
LLM_SYSTEM = ("Tu aides à lire un schéma de données. On te donne des zones métier (groupes de types) ; propose pour chacune un titre court "
              "(3 mots au plus) et un sous-titre (une courte phrase) qui dit à quoi servent ses types. Réponds uniquement par un objet JSON "
              '{"zones": [{"id": "...", "title": "...", "subtitle": "..."}]} avec exactement les identifiants reçus.')


def by_llm(g: SchemaGraph, perimeters: list[Any], lang: str, provider_id: Optional[str] = None, max_zones: int = MAX_ZONES) -> ZoneProposal:
    """Structure : périmètres s'il y en a au moins deux, sinon hiérarchie si elle donne des zones équilibrées, sinon communautés.
    Titres et sous-titres : fournisseur actif. Mock, fournisseur non configuré ou réponse inutilisable : titres déterministes."""
    base = by_perimeters(g, perimeters, lang, max_zones) if len(perimeters) >= 2 else None
    if base is None or not base.zones:
        base = by_hierarchy(g, lang, max_zones)
        if not _balanced(base, g):
            base = by_communities(g, lang, 0, max_zones)
    prop = ZoneProposal(base.zones, "llm", list(base.warnings))
    try:
        from ..assistant.convert import extract_json
        from ..assistant.providers import LLMError, get_provider
        p = get_provider(provider_id) if provider_id else get_provider()
    except Exception as exc:  # noqa: BLE001
        prop.warnings.append(f"Fournisseur indisponible ({exc}) : titres déterministes.")
        return prop
    if getattr(p, "name", "") == "mock" or not p.configured:
        prop.warnings.append("Fournisseur de démonstration ou non configuré : titres déterministes.")
        return prop
    listing = [{"id": z.id, "types": [g.nodes[m].label for m in z.members[:25]]} for z in prop.zones]
    user = ("Langue de la réponse : " + ("English" if lang == "en" else "français") + "\nZones :\n"
            + json.dumps(listing, ensure_ascii=False))
    try:
        data = extract_json(p.complete(LLM_SYSTEM, [{"role": "user", "content": user}], 2000))
        titles = {str(z.get("id")): z for z in data.get("zones", []) if isinstance(z, dict)}
    except (LLMError, ValueError) as exc:
        prop.warnings.append(f"Réponse du fournisseur inutilisable ({str(exc)[:120]}) : titres déterministes.")
        return prop
    for z in prop.zones:
        t = titles.get(z.id)
        if t and str(t.get("title", "")).strip():
            z.title = str(t["title"]).strip()[:60]
            z.subtitle = str(t.get("subtitle") or z.subtitle).strip()[:140]
    return prop


def suggest(g: SchemaGraph, strategy: str, *, perimeters: list[Any], lang: str, prefixes: Optional[dict[str, str]] = None,
            provider_id: Optional[str] = None, seed: int = 0, max_zones: int = MAX_ZONES) -> ZoneProposal:
    if strategy == "perimeters":
        return by_perimeters(g, perimeters, lang, max_zones)
    if strategy == "hierarchy":
        return by_hierarchy(g, lang, max_zones)
    if strategy == "namespace":
        return by_namespace(g, lang, prefixes, max_zones)
    if strategy == "communities":
        return by_communities(g, lang, seed, max_zones)
    if strategy == "llm":
        return by_llm(g, perimeters, lang, provider_id, max_zones)
    raise ValueError(f"stratégie inconnue « {strategy} » : attendu {', '.join(STRATEGIES)}")


def initial(g: SchemaGraph, perimeters: list[Any], lang: str, prefixes: Optional[dict[str, str]] = None) -> ZoneProposal:
    """Proposition initiale : périmètres s'il y en a au moins deux, sinon hiérarchie, sinon communautés."""
    if len(perimeters) >= 2:
        p = by_perimeters(g, perimeters, lang)
        if p.zones:
            return p
    p = by_hierarchy(g, lang)
    if _balanced(p, g):
        return p
    return by_communities(g, lang)


def _balanced(p: ZoneProposal, g: SchemaGraph) -> bool:
    """Au moins deux vraies zones, et aucune ne contient plus de 60 % des types."""
    real = [z for z in p.zones if z.id != OTHER_ID]
    return len(real) >= 2 and max(len(z.members) for z in p.zones) <= max(3, 0.6 * len(g.nodes))
