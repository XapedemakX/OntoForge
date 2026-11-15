"""Carte métier : assemblage de la carte complète (GET), enregistrement (PUT), proposition de zones et de cadres, mise en page."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from .. import localize
from ..core.project import Project
from ..projects import store
from . import frames as frames_mod
from . import layout as lay
from . import zones as zones_mod
from .counts import apply_counts
from .graph import SchemaGraph, SRel, from_onto, from_pg, link_weights
from .model import BUILTIN_ROLES, EDGE_STYLES, SOURCES, canonical_role, BusinessMapState, Frame, Scenario, XY, Zone
from .roles import infer_roles, role_color, role_label

MAX_ROLE_LEN = 40


class MapError(ValueError):
    """Entrée invalide (→ 422)."""


@dataclass
class Ctx:
    project: Project
    source: str
    lang: str
    graph: SchemaGraph
    state: BusinessMapState
    model_date: str
    roles_auto: dict[str, str]
    roles: dict[str, str]
    radius: dict[str, float]
    zone_of: dict[str, str]
    rects: dict[str, lay.Rect]
    canvas: tuple[float, float]
    edges: list[dict]
    anchors: dict[str, tuple[float, float]]
    fresh: bool  # aucune carte enregistrée : proposition initiale
    warnings: list[str] = field(default_factory=list)


def check_source(source: str) -> str:
    if source not in SOURCES:
        raise MapError(f"Source inconnue « {source} » : attendu ontology ou target")
    return source


# ----------------------------------------------------------------------------- schéma
def load_graph(p: Project, source: str, lang: str) -> tuple[SchemaGraph, str]:
    """(graphe neutre avec effectifs, date du modèle)."""
    if source == "ontology":
        g = from_onto(p.onto, lang, p.perimeters)
        apply_counts(g, p.onto, p.id)
        return g, p.updated_at[:10]
    from ..api.analysis import run_analysis
    pg = run_analysis(p, p.target)
    g = from_pg(pg, p.onto, p.perimeters)
    apply_counts(g, p.onto, p.id)
    return g, (pg.meta.generated_at or p.updated_at)[:10]


# ----------------------------------------------------------------------------- état
def normalize(state: BusinessMapState, g: SchemaGraph, lang: str) -> tuple[BusinessMapState, list[str]]:
    """Copie de l'état alignée sur le schéma : membres inconnus retirés, un nœud dans une seule zone, nœuds sans zone dans « Autres »."""
    st = state.model_copy(deep=True)
    warns: list[str] = []
    ids = set(g.nodes)
    placed: set[str] = set()
    zones: list[Zone] = []
    for z in st.zones:
        ms = []
        for m in z.members:
            if m in ids and m not in placed:
                ms.append(m)
                placed.add(m)
        z.members = ms
        zones.append(z)
    free = [k for k in g.nodes if k not in placed]
    if free:
        other = next((z for z in zones if z.id == zones_mod.OTHER_ID), None)
        if other is None:
            other = zones_mod.other_zone([], lang)
            zones.append(other)
        other.members.extend(free)
    st.zones = [z for z in zones if z.members or z.id != zones_mod.OTHER_ID]
    st.roles = {k: v for k, v in st.roles.items() if k in ids}
    st.faded = [k for k in dict.fromkeys(st.faded) if k in ids]
    st.pinned = [k for k in dict.fromkeys(st.pinned) if k in ids]
    st.positions = {k: v for k, v in st.positions.items() if k in ids}
    frames = []
    for f in st.frames:
        f.members = [m for m in dict.fromkeys(f.members) if m in ids]
        if len(f.members) >= 2:
            frames.append(f)
        else:
            warns.append(f"Cadre « {f.id} » retiré : moins de deux types existants.")
    st.frames = frames
    for sc in st.scenarios:
        sc.nodes = [n for n in sc.nodes if n in ids]
    return st, warns


def get_state(p: Project, source: str) -> Optional[BusinessMapState]:
    return p.business_maps.get(source)


def _edge_json(r: SRel) -> dict:
    return {"id": r.id, "source": r.source, "target": r.target, "source_kind": "node", "kind": r.kind, "label": r.label,
            "inverse_label": r.inverse_label, "direction": "both" if r.both else "forward", "link": r.link if r.both else None, "union": r.union,
            "loop": r.source == r.target}


def build_edges(g: SchemaGraph, frames: list[Frame]) -> list[dict]:
    """Une arête par relation (sens direct) ; sous-classe ; inverses fusionnées (``both``) ; arêtes de cadre à la place des relations communes."""
    replaced: set[str] = set()
    out: list[dict] = []
    for f in frames:
        for rep, subs in frames_mod.frame_edges(f, g):
            replaced.update(r.id for r in subs)
            out.append({"id": f"frame|{f.id}|{rep.key}|{rep.target}", "source": f.id, "target": rep.target, "source_kind": "frame",
                        "kind": "frame", "label": rep.label, "inverse_label": rep.inverse_label,
                        "direction": "both" if rep.both else "forward", "link": rep.link if rep.both else None, "union": rep.union,
                        "loop": False, "members": [r.source for r in subs],
                        "replaces": [r.id for r in subs]})
    edges = [_edge_json(r) for r in g.rels if r.id not in replaced and r.source in g.nodes and r.target in g.nodes]
    return edges + out


def _zone_links(g: SchemaGraph, zone_of: dict[str, str]) -> dict[tuple[str, str], int]:
    out: dict[tuple[str, str], int] = {}
    for (a, b), w in link_weights(g).items():
        za, zb = zone_of.get(a), zone_of.get(b)
        if za and zb and za != zb:
            out[(za, zb)] = out.get((za, zb), 0) + w
    return out


def prepare(p: Project, source: str) -> Ctx:
    lang = localize.labels_lang()
    g, date = load_graph(p, source, lang)
    state = get_state(p, source)
    fresh = state is None
    warns: list[str] = []
    if fresh:
        prop = zones_mod.initial(g, p.perimeters, lang, p.onto.meta.prefixes)
        state = BusinessMapState(zones=prop.zones, generated=True)
        warns += prop.warnings
    state, w2 = normalize(state, g, lang)
    warns += w2
    roles_auto = infer_roles(g)
    roles = {k: canonical_role(state.roles.get(k)) or roles_auto[k] for k in g.nodes}
    radius = {k: lay.node_radius(n.count, roles[k]) for k, n in g.nodes.items()}
    zone_of = {m: z.id for z in state.zones for m in z.members}
    sizes = {z.id: len(z.members) for z in state.zones}
    rects, w, h = lay.arrange_zones(sizes, _zone_links(g, zone_of), zones_mod.OTHER_ID)
    pinned_pos = {k: (state.positions[k].x, state.positions[k].y) for k in state.pinned if k in state.positions}
    rects = lay.grow_for_pinned(rects, {k: (zone_of[k], x, y, radius[k]) for k, (x, y) in pinned_pos.items()})
    if rects:
        w = max(w, max(r[0] + r[2] for r in rects.values()) + lay.MARGIN)
        h = max(h, max(r[1] + r[3] for r in rects.values()) + lay.MARGIN)
    adjacency: dict[str, dict[str, int]] = {}
    for (a, b), x in link_weights(g).items():
        adjacency.setdefault(a, {})[b] = x
        adjacency.setdefault(b, {})[a] = x
    anchors: dict[str, tuple[float, float]] = {}
    for z in state.zones:
        if z.members and z.id in rects:
            anchors.update(lay.grid_anchors(z.members, rects[z.id], adjacency))
    edges = build_edges(g, state.frames)
    return Ctx(project=p, source=source, lang=lang, graph=g, state=state, model_date=date, roles_auto=roles_auto, roles=roles,
               radius=radius, zone_of=zone_of, rects=rects, canvas=(w, h), edges=edges, anchors=anchors, fresh=fresh, warnings=warns)


def node_positions(c: Ctx) -> dict[str, tuple[float, float]]:
    """Positions affichées : enregistrées si elles existent (rabattues dans la zone si le nœud n'est pas épinglé), sinon la case de la grille."""
    out: dict[str, tuple[float, float]] = {}
    pinned = set(c.state.pinned)
    for k in c.graph.nodes:
        if k in c.state.positions:
            pos = c.state.positions[k]
            x, y = pos.x, pos.y
            if k not in pinned and k in c.zone_of and c.zone_of[k] in c.rects:
                x0, y0, x1, y1 = lay.bounds_for(c.rects[c.zone_of[k]], c.radius[k])
                x, y = min(max(x, x0), max(x0, x1)), min(max(y, y0), max(y0, y1))
            out[k] = (round(x, 1), round(y, 1))
        else:
            out[k] = c.anchors.get(k, (lay.MARGIN, lay.MARGIN))
    return out


def _frame_rect(members: list[str], pos: dict[str, tuple[float, float]], radius: dict[str, float]) -> dict:
    x0 = min(pos[m][0] - radius[m] for m in members) - 28
    y0 = min(pos[m][1] - radius[m] for m in members) - 38
    x1 = max(pos[m][0] + radius[m] for m in members) + 28
    y1 = max(pos[m][1] + radius[m] for m in members) + 36
    return {"x": round(x0, 1), "y": round(y0, 1), "w": round(x1 - x0, 1), "h": round(y1 - y0, 1)}


def compose(c: Ctx, pos: Optional[dict[str, tuple[float, float]]] = None) -> dict:
    g, st = c.graph, c.state
    pos = pos or node_positions(c)
    faded, pinned = set(st.faded), set(st.pinned)
    nodes = [{"id": k, "label": n.label, "role": c.roles[k], "role_source": "manual" if canonical_role(st.roles.get(k)) not in (None, c.roles_auto[k]) else "auto",
              "zone": c.zone_of.get(k), "count": n.count, "faded": k in faded, "pinned": k in pinned,
              "x": pos[k][0], "y": pos[k][1], "r": c.radius[k], "abstract": n.abstract}
             for k, n in g.nodes.items()]
    zones = [{"id": z.id, "title": z.title, "subtitle": z.subtitle, "color": z.color, "members": list(z.members),
              "rect": dict(zip("xywh", (round(v, 1) for v in c.rects[z.id])))} for z in st.zones if z.id in c.rects]
    frames = [{"id": f.id, "title": f.title, "members": list(f.members), "note": f.note, "rect": _frame_rect(f.members, pos, c.radius)}
              for f in st.frames]
    used = sorted(set(c.roles.values()), key=lambda r: (r not in BUILTIN_ROLES, BUILTIN_ROLES.index(r) if r in BUILTIN_ROLES else 0, r))
    legend = [{"role": r, "label": role_label(r, c.lang), "color": role_color(r, st.role_colors),
               "count": sum(1 for v in c.roles.values() if v == r)} for r in used]
    width = max([c.canvas[0]] + [f["rect"]["x"] + f["rect"]["w"] + lay.MARGIN for f in frames])
    height = max([c.canvas[1]] + [f["rect"]["y"] + f["rect"]["h"] + lay.MARGIN for f in frames])
    n_rel = sum(1 for r in g.rels if r.kind == "relation")
    target = c.project.target if c.source == "target" else None
    return {
        "source": c.source, "nodes": nodes, "edges": c.edges, "frames": frames, "zones": zones,
        "scenarios": [s.model_dump() for s in st.scenarios], "legend": legend, "edge_styles": list(EDGE_STYLES),
        "canvas": {"width": round(width, 1), "height": round(height, 1)},
        "meta": {"title": st.title or c.project.name, "model_date": c.model_date, "n_types": len(g.nodes), "n_relations": n_rel,
                 "target": target, "lang": c.lang,
                 "skipped": [{"id": i, "label": g.skipped_labels.get(i, i)} for i in g.skipped],
                 "n_union": sum(1 for r in g.rels if r.union), "generated": st.generated, "updated_at": st.updated_at,
                 "counts": g.count_origin},
        "warnings": c.warnings,
    }


# ----------------------------------------------------------------------------- opérations
_INITIAL: dict[tuple, dict[str, XY]] = {}   # L41 : mises en page initiales de la route de lecture, gardées en mémoire (jamais écrites)
_INITIAL_MAX = 64


def get_map(p: Project, source: str, persist: bool = True) -> dict:
    """Carte complète prête à dessiner. Sans carte enregistrée : proposition initiale (zones + mise en page).
    ``persist=True`` (routes d'écriture) l'enregistre avec ``generated: true``. ``persist=False`` (GET, route de lecture, L41 : une lecture
    n'écrit jamais dans le projet) la garde en mémoire, par état du projet, pour que les lectures suivantes la retrouvent à l'identique ;
    elle est enregistrée à la première modification de la carte."""
    check_source(source)
    c = prepare(p, source)
    if c.fresh and c.graph.nodes:
        key = (p.id, source, p.updated_at)
        cached = None if persist else _INITIAL.get(key)
        if cached is not None:
            c.state.positions = dict(cached)
        else:
            res = run_layout(c, iterations=1500, seed=0, time_limit_s=2.0)
            c.state.positions = {k: XY(x=x, y=y) for k, (x, y) in res.positions.items()}
            if not persist:
                if len(_INITIAL) >= _INITIAL_MAX:
                    _INITIAL.pop(next(iter(_INITIAL)))
                _INITIAL[key] = dict(c.state.positions)
        if persist:
            c.state.updated_at = store.now_iso()
            p.business_maps[source] = c.state
            store.save(p, touch=False)
    return compose(c)


def layout_edges(c: Ctx) -> list[lay.LEdge]:
    out = []
    for e in c.edges:
        if e["loop"]:
            continue
        a = e["members"] if e["source_kind"] == "frame" else [e["source"]]
        out.append(lay.LEdge(a=a, b=[e["target"]], label_len=len(e["label"]) + (len(e["inverse_label"] or "") // 2),
                             a_frame=e["source_kind"] == "frame"))
    return out


def run_layout(c: Ctx, iterations: int = 20000, seed: int = 0, time_limit_s: float = 3.5) -> lay.LayoutResult:
    g = c.graph
    ids = list(g.nodes)
    fixed = {k for k in c.state.pinned if k in c.state.positions}
    start = dict(c.anchors)
    for k in fixed:
        start[k] = (c.state.positions[k].x, c.state.positions[k].y)
    rect_of = {k: c.rects[c.zone_of[k]] for k in ids if c.zone_of.get(k) in c.rects}
    ids = [k for k in ids if k in rect_of and k in start]
    return lay.anneal(ids, c.radius, rect_of, start, fixed, layout_edges(c), iterations, seed, time_limit_s)


def save_state(p: Project, source: str, data: dict[str, Any]) -> dict:
    """PUT : remplace les champs fournis (zones, roles, role_colors, faded, pinned, positions, frames, scenarios, title)."""
    check_source(source)
    lang = localize.labels_lang()
    g, _ = load_graph(p, source, lang)
    cur = get_state(p, source) or BusinessMapState()
    st = cur.model_copy(deep=True)
    if "zones" in data and data["zones"] is not None:
        zs = [Zone.model_validate(z) for z in data["zones"]]
        ids = [z.id for z in zs]
        if any(not i for i in ids) or len(set(ids)) != len(ids):
            raise MapError("Identifiants de zone vides ou en double.")
        seen: dict[str, str] = {}
        for z in zs:
            for m in z.members:
                if m in seen and seen[m] != z.id:
                    raise MapError(f"Le type « {m} » est dans deux zones ({seen[m]} et {z.id}).")
                seen[m] = z.id
        st.zones = zs
    if "roles" in data and data["roles"] is not None:
        for k, v in data["roles"].items():
            if not isinstance(v, str) or not v.strip() or len(v) > MAX_ROLE_LEN:
                raise MapError(f"Rôle invalide pour « {k} » (texte de 1 à {MAX_ROLE_LEN} caractères).")
        auto = infer_roles(g)
        st.roles = {k: canonical_role(v.strip()) for k, v in data["roles"].items() if k in g.nodes and canonical_role(v.strip()) != auto.get(k)}
    if data.get("role_colors") is not None:
        st.role_colors = {str(k): str(v)[:32] for k, v in data["role_colors"].items()}
    if data.get("faded") is not None:
        st.faded = list(data["faded"])
    if data.get("pinned") is not None:
        st.pinned = list(data["pinned"])
    if data.get("positions") is not None:
        st.positions = {k: XY.model_validate(v) for k, v in data["positions"].items()}
    if data.get("frames") is not None:
        fs = [Frame.model_validate(f) for f in data["frames"]]
        if len({f.id for f in fs}) != len(fs) or any(not f.id for f in fs):
            raise MapError("Identifiants de cadre vides ou en double.")
        st.frames = fs
    if data.get("scenarios") is not None:
        scs = [Scenario.model_validate(s) for s in data["scenarios"]]
        if len({s.id for s in scs}) != len(scs) or any(not s.id for s in scs):
            raise MapError("Identifiants de scénario vides ou en double.")
        for s in scs:
            bad = sorted({v for v in s.edge_styles.values() if v not in EDGE_STYLES})
            if bad:
                raise MapError(f"Style d'arête inconnu dans le scénario « {s.id} » : {', '.join(bad)} (attendu {', '.join(EDGE_STYLES)}).")
        st.scenarios = scs
    if "title" in data:
        st.title = data["title"] or None
    st.generated = False
    st.updated_at = store.now_iso()
    p.business_maps[source] = st
    store.save(p, touch=False)
    return get_map(p, source)


def suggest_zones(p: Project, source: str, strategy: str, *, provider_id: Optional[str] = None, seed: int = 0,
                  max_zones: int = zones_mod.MAX_ZONES, apply: bool = False) -> dict:
    check_source(source)
    if strategy not in zones_mod.STRATEGIES:
        raise MapError(f"Stratégie inconnue « {strategy} » : attendu {', '.join(zones_mod.STRATEGIES)}.")
    max_zones = max(2, min(12, max_zones))
    lang = localize.labels_lang()
    g, _ = load_graph(p, source, lang)
    prop = zones_mod.suggest(g, strategy, perimeters=p.perimeters, lang=lang, prefixes=p.onto.meta.prefixes,
                             provider_id=provider_id, seed=seed, max_zones=max_zones)
    out: dict[str, Any] = {"requested": strategy, "strategy": prop.strategy, "zones": [z.model_dump() for z in prop.zones],
                           "warnings": prop.warnings, "applied": apply}
    if apply:
        st = (get_state(p, source) or BusinessMapState()).model_copy(deep=True)
        st.zones = prop.zones
        st.positions = {k: v for k, v in st.positions.items() if k in st.pinned}
        st.generated = False
        st.updated_at = store.now_iso()
        p.business_maps[source] = st
        store.save(p, touch=False)
        out["map"] = get_map(p, source)
    return out


def suggest_frames(p: Project, source: str, apply: bool = False) -> dict:
    check_source(source)
    lang = localize.labels_lang()
    g, _ = load_graph(p, source, lang)
    found = frames_mod.suggest(g)
    frames = frames_mod.describe(found, g, lang)
    label_of = {r.key: r.label for r in g.rels}
    out: dict[str, Any] = {"frames": [{**f.model_dump(), "shared": [
        {"relation": k, "label": label_of.get(k, k), "target": t, "target_label": g.nodes[t].label} for k, t in found[i]["shared"]]}
        for i, f in enumerate(frames)], "applied": apply}
    if apply:
        st = (get_state(p, source) or BusinessMapState()).model_copy(deep=True)
        st.frames = frames
        st.generated = False
        st.updated_at = store.now_iso()
        p.business_maps[source] = st
        store.save(p, touch=False)
        out["map"] = get_map(p, source)
    return out


def layout(p: Project, source: str, iterations: Optional[int] = None, seed: int = 0, time_limit_s: Optional[float] = None,
           apply: bool = False) -> dict:
    check_source(source)
    c = prepare(p, source)
    res = run_layout(c, iterations=max(1, min(200000, iterations or 20000)), seed=seed, time_limit_s=max(0.2, min(30.0, time_limit_s or 3.5)))
    pos = dict(res.positions)
    out = {"positions": {k: {"x": x, "y": y} for k, (x, y) in pos.items()},
           "zones": [{"id": zid, "rect": dict(zip("xywh", (round(v, 1) for v in r)))} for zid, r in c.rects.items()],
           "canvas": {"width": round(c.canvas[0], 1), "height": round(c.canvas[1], 1)},
           "stats": {"iterations": res.iterations, "elapsed_ms": res.elapsed_ms, "cost": res.cost, "crossings": res.crossings,
                     "initial_crossings": res.initial_crossings, "seed": res.seed, "time_limited": res.time_limited},
           "applied": apply}
    if apply:
        st = (get_state(p, source) or c.state).model_copy(deep=True)
        st.positions = {k: XY(x=x, y=y) for k, (x, y) in pos.items()}
        if not get_state(p, source):
            st.zones = c.state.zones
        st.generated = False
        st.updated_at = store.now_iso()
        p.business_maps[source] = st
        store.save(p, touch=False)
        out["map"] = get_map(p, source)
    return out
