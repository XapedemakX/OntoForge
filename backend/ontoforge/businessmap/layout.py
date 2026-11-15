"""Mise en page de la carte métier : rectangles de zone en grille, positions initiales, recuit simulé en Python pur.

Le recuit (déplacement d'un nœud à la fois, acceptation de Metropolis, température décroissante) minimise une somme de pénalités :
chevauchement des nœuds, arêtes qui passent trop près d'un nœud étranger, croisements d'arêtes, arêtes trop courtes pour leur
étiquette ou trop longues, écart à la position de départ en grille. Les coûts sont calculés de façon incrémentale (seuls les termes
qui touchent le nœud déplacé), ce qui tient 60 nœuds en quelques secondes sans numpy (décision D-L21-02 : pas de dépendance ajoutée).

Contraintes dures : un nœud reste dans le rectangle de sa zone, deux disques ne se chevauchent jamais, un nœud épinglé ne bouge pas.
Une extrémité d'arête est un nœud, ou la moyenne des positions des membres d'un cadre.
"""
from __future__ import annotations

import math
import random
import time
from dataclasses import dataclass, field
from typing import Optional

R_BASE = 34.0
R_MAX = 50.0
CELL_W, CELL_H = 250.0, 210.0
HEAD = 90.0  # bandeau de titre de la zone
PAD = 30.0
ZONE_GAP = 40.0
MARGIN = 40.0

W_NODE, W_CLEAR, W_CROSS, W_SHORT, W_LONG, W_ANCHOR = 20.0, 120.0, 30000.0, 3.0, 0.25, 0.02
NODE_GAP = 40.0  # distance souhaitée (souple) entre deux disques
HARD_GAP = 12.0  # distance minimale (dure)
CLEAR_MARGIN = 50.0


def node_radius(count: Optional[int], role: Optional[str] = None) -> float:
    r = R_BASE
    if count:
        r += min(R_MAX - R_BASE, 3.0 * math.log10(count + 1))
    if role == "lookup":
        r -= 4
    return round(r, 1)


@dataclass
class LEdge:
    a: list[str]  # nœuds de l'extrémité de départ (un seul, ou les membres d'un cadre)
    b: list[str]
    label_len: int = 8
    a_frame: bool = False
    b_frame: bool = False


@dataclass
class LayoutResult:
    positions: dict[str, tuple[float, float]]
    iterations: int
    elapsed_ms: int
    cost: float
    crossings: int
    initial_crossings: int
    seed: int
    time_limited: bool = False


Rect = tuple[float, float, float, float]  # x, y, w, h


# ----------------------------------------------------------------------------- zones
def zone_size(n: int) -> tuple[int, int, float, float]:
    cols = 1 if n <= 1 else max(2, math.ceil(math.sqrt(n * 1.5)))
    rows = max(1, math.ceil(n / cols))
    return cols, rows, cols * CELL_W + 2 * PAD, HEAD + rows * CELL_H + PAD


def zone_order(sizes: dict[str, int], links: dict[tuple[str, str], int], last: Optional[str] = None) -> list[str]:
    """Grandes zones d'abord, puis à chaque pas la zone la plus liée à celles déjà placées ; ``last`` (« Autres ») en dernier."""
    left = sorted((z for z in sizes if z != last), key=lambda z: (-sizes[z], z))
    out: list[str] = []
    while left:
        if not out:
            nxt = left[0]
        else:
            def score(z: str) -> tuple:
                s = sum(links.get((z, o), 0) + links.get((o, z), 0) for o in out)
                return (-s, -sizes[z], z)
            nxt = min(left, key=score)
        out.append(nxt)
        left.remove(nxt)
    if last in sizes:
        out.append(last)
    return out


def arrange_zones(sizes: dict[str, int], links: dict[tuple[str, str], int], last: Optional[str] = None) -> tuple[dict[str, Rect], float, float]:
    """Rectangles de zone : une grille de colonnes par zone, de taille proportionnelle au nombre de membres, rangées en lignes."""
    order = zone_order(sizes, links, last)
    dims = {z: zone_size(sizes[z])[2:] for z in order}
    total = sum(w * h for w, h in dims.values()) or 1.0
    target_w = max(max((w for w, _ in dims.values()), default=0), math.sqrt(total * 1.8))
    rects: dict[str, Rect] = {}
    x = y = MARGIN
    row_h = 0.0
    width = 0.0
    for z in order:
        w, h = dims[z]
        if x > MARGIN and x + w > target_w + MARGIN:
            x, y, row_h = MARGIN, y + row_h + ZONE_GAP, 0.0
        rects[z] = (x, y, w, h)
        x += w + ZONE_GAP
        row_h = max(row_h, h)
        width = max(width, x - ZONE_GAP)
    return rects, width + MARGIN, y + row_h + MARGIN


def grow_for_pinned(rects: dict[str, Rect], pinned: dict[str, tuple[str, float, float, float]]) -> dict[str, Rect]:
    """Agrandit le rectangle d'une zone pour contenir ses nœuds épinglés : {nœud: (zone, x, y, r)}."""
    out = dict(rects)
    for _, (z, x, y, r) in pinned.items():
        if z not in out:
            continue
        x0, y0, w, h = out[z]
        nx0 = min(x0, x - r - 30)
        ny0 = min(y0, y - r - HEAD + 20)
        nx1 = max(x0 + w, x + r + 30)
        ny1 = max(y0 + h, y + r + 40)
        out[z] = (nx0, ny0, nx1 - nx0, ny1 - ny0)
    return out


def bounds_for(rect: Rect, r: float) -> tuple[float, float, float, float]:
    x0, y0, w, h = rect
    return x0 + r + 30, y0 + HEAD + r - 20, x0 + w - r - 30, y0 + h - r - 40


def grid_anchors(members: list[str], rect: Rect, adjacency: dict[str, dict[str, int]]) -> dict[str, tuple[float, float]]:
    """Positions de départ : cases de la grille de la zone, remplies dans l'ordre d'un parcours en largeur depuis le nœud le plus lié."""
    ms = set(members)
    deg = {m: sum(w for o, w in adjacency.get(m, {}).items() if o in ms) for m in members}
    left = sorted(members, key=lambda m: (-deg[m], m))
    order: list[str] = []
    while left:
        start = left[0]
        queue = [start]
        while queue:
            cur = queue.pop(0)
            if cur in order:
                continue
            order.append(cur)
            for o in sorted(adjacency.get(cur, {}), key=lambda o: (-adjacency[cur][o], o)):
                if o in ms and o not in order:
                    queue.append(o)
        left = [m for m in left if m not in order]
    cols, rows, _, _ = zone_size(len(members))
    x0, y0, w, _ = rect
    out: dict[str, tuple[float, float]] = {}
    for i, m in enumerate(order):
        row, col = divmod(i, cols)
        if row % 2:  # parcours en serpent : deux nœuds consécutifs restent voisins
            col = cols - 1 - col
        out[m] = (x0 + PAD + (col + 0.5) * CELL_W, y0 + HEAD + (row + 0.5) * CELL_H)
    return out


# ----------------------------------------------------------------------------- recuit
def _crosses(p1x, p1y, p2x, p2y, p3x, p3y, p4x, p4y) -> bool:
    d1 = (p2x - p1x) * (p3y - p1y) - (p2y - p1y) * (p3x - p1x)
    d2 = (p2x - p1x) * (p4y - p1y) - (p2y - p1y) * (p4x - p1x)
    if (d1 > 0) == (d2 > 0):
        return False
    d3 = (p4x - p3x) * (p1y - p3y) - (p4y - p3y) * (p1x - p3x)
    d4 = (p4x - p3x) * (p2y - p3y) - (p4y - p3y) * (p2x - p3x)
    return (d3 > 0) != (d4 > 0)


def anneal(ids: list[str], radius: dict[str, float], rect_of: dict[str, Rect], start: dict[str, tuple[float, float]],
           pinned: set[str], edges: list[LEdge], iterations: int = 20000, seed: int = 0, time_limit_s: float = 3.5) -> LayoutResult:
    t_begin = time.perf_counter()
    N = len(ids)
    idx = {k: i for i, k in enumerate(ids)}
    R = [radius[k] for k in ids]
    X = [start[k][0] for k in ids]
    Y = [start[k][1] for k in ids]
    AX, AY = list(X), list(Y)
    fixed = [k in pinned for k in ids]
    lo_x, lo_y, hi_x, hi_y = [], [], [], []
    for i, k in enumerate(ids):
        a, b, c, d = bounds_for(rect_of[k], R[i])
        lo_x.append(a), lo_y.append(b), hi_x.append(max(a, c)), hi_y.append(max(b, d))
    # arêtes : une par couple d'extrémités (non orienté), longueur d'étiquette maximale ; les boucles sont ignorées
    pair: dict[tuple, LEdge] = {}
    for e in edges:
        ka, kb = tuple(sorted(e.a)), tuple(sorted(e.b))
        if ka == kb or not e.a or not e.b:
            continue
        key = (ka, kb) if ka <= kb else (kb, ka)
        old = pair.get(key)
        if old is None or e.label_len > old.label_len:
            pair[key] = e
    ea = [[idx[m] for m in e.a if m in idx] for e in pair.values()]
    eb = [[idx[m] for m in e.b if m in idx] for e in pair.values()]
    keep = [i for i in range(len(ea)) if ea[i] and eb[i]]
    elist = [list(pair.values())[i] for i in keep]
    ea, eb = [ea[i] for i in keep], [eb[i] for i in keep]
    M = len(elist)
    ends = [frozenset(ea[e]) | frozenset(eb[e]) for e in range(M)]
    inc: list[list[int]] = [[] for _ in range(N)]
    for e in range(M):
        for n in ends[e]:
            inc[n].append(e)
    share = [frozenset(f for f in range(M) if f != e and ends[e] & ends[f]) for e in range(M)]
    minlen = [6.5 * elist[e].label_len + 16 + sum(R[n] for n in (ea[e][:1] + eb[e][:1])) + (150 if elist[e].a_frame else 0)
              + (150 if elist[e].b_frame else 0) + 20 for e in range(M)]
    max_len = max(1300.0, 0.6 * max((max(r[0] + r[2] for r in rect_of.values()), 1.0)) if rect_of else 1300.0)
    seg = [[0.0, 0.0, 0.0, 0.0] for _ in range(M)]

    def refresh(e: int) -> None:
        la, lb = ea[e], eb[e]
        s = seg[e]
        s[0] = sum(X[n] for n in la) / len(la)
        s[1] = sum(Y[n] for n in la) / len(la)
        s[2] = sum(X[n] for n in lb) / len(lb)
        s[3] = sum(Y[n] for n in lb) / len(lb)

    for e in range(M):
        refresh(e)
    sqrt = math.sqrt

    def seg_clear(e: int, k: int) -> float:
        ax, ay, bx, by = seg[e]
        thr = R[k] + CLEAR_MARGIN
        px, py = X[k], Y[k]
        if (px < (ax if ax < bx else bx) - thr or px > (ax if ax > bx else bx) + thr
                or py < (ay if ay < by else by) - thr or py > (ay if ay > by else by) + thr):
            return 0.0
        abx, aby = bx - ax, by - ay
        l2 = abx * abx + aby * aby
        t = 0.0 if l2 < 1e-9 else max(0.0, min(1.0, ((px - ax) * abx + (py - ay) * aby) / l2))
        dx, dy = px - (ax + t * abx), py - (ay + t * aby)
        d2 = dx * dx + dy * dy
        if d2 >= thr * thr:
            return 0.0
        ov = thr - sqrt(d2)
        return W_CLEAR * ov * ov

    def local(n: int) -> float:
        s = 0.0
        xn, yn, rn = X[n], Y[n], R[n]
        for j in range(N):
            if j != n:
                dx, dy = X[j] - xn, Y[j] - yn
                lim = rn + R[j] + NODE_GAP
                d2 = dx * dx + dy * dy
                if d2 < lim * lim:
                    ov = lim - sqrt(d2)
                    s += W_NODE * ov * ov
        mine = inc[n]
        mine_set = set(mine)
        for e in mine:
            ax, ay, bx, by = seg[e]
            length = sqrt((bx - ax) ** 2 + (by - ay) ** 2)
            if length < minlen[e]:
                s += W_SHORT * (minlen[e] - length) ** 2
            elif length > max_len:
                s += W_LONG * (length - max_len) ** 2
            en = ends[e]
            for k in range(N):
                if k not in en:
                    s += seg_clear(e, k)
            lx0, lx1 = (ax, bx) if ax < bx else (bx, ax)
            ly0, ly1 = (ay, by) if ay < by else (by, ay)
            sh = share[e]
            for f in range(M):
                if f == e or f in sh or (f in mine_set and f < e):
                    continue
                cx, cy, dx_, dy_ = seg[f]
                if (cx < lx0 and dx_ < lx0) or (cx > lx1 and dx_ > lx1) or (cy < ly0 and dy_ < ly0) or (cy > ly1 and dy_ > ly1):
                    continue
                if _crosses(ax, ay, bx, by, cx, cy, dx_, dy_):
                    s += W_CROSS
        for e in range(M):
            if e not in mine_set:
                s += seg_clear(e, n)
        s += W_ANCHOR * ((xn - AX[n]) ** 2 + (yn - AY[n]) ** 2)
        return s

    def count_crossings() -> int:
        c = 0
        for e in range(M):
            ax, ay, bx, by = seg[e]
            for f in range(e + 1, M):
                if f not in share[e] and _crosses(ax, ay, bx, by, *seg[f]):
                    c += 1
        return c

    def total() -> float:
        # coût global : chaque terme d'un nœud est compté, puis ramené à une valeur comparable (utile seulement au rapport)
        return sum(local(n) for n in range(N)) / 2.0

    movable = [i for i in range(N) if not fixed[i]]
    rng = random.Random(seed)

    def free_of_overlap(n: int, x: float, y: float) -> bool:
        rn = R[n] + HARD_GAP
        for j in range(N):
            if j != n:
                dx, dy = X[j] - x, Y[j] - y
                lim = rn + R[j]
                if dx * dx + dy * dy < lim * lim:
                    return False
        return True

    # réparation du départ : un nœud qui touche un autre disque cherche une place libre dans sa zone
    for n in movable:
        if not free_of_overlap(n, X[n], Y[n]):
            for _ in range(300):
                x, y = rng.uniform(lo_x[n], hi_x[n]), rng.uniform(lo_y[n], hi_y[n])
                if free_of_overlap(n, x, y):
                    X[n], Y[n] = x, y
                    break
    for e in range(M):
        refresh(e)
    initial_crossings = count_crossings()

    done = 0
    time_limited = False
    if movable and M:
        cur = total()
        best, bx_, by_ = cur, list(X), list(Y)
        t0, t1 = 4000.0, 20.0
        iters = max(1, iterations)
        k = -1
        t_loop = time.perf_counter()
        while k + 1 < iters:
            k += 1
            if k == 100:
                # calibrage unique : si le budget de temps ne suffit pas, on réduit le nombre d'itérations (le refroidissement suit)
                rate = (time.perf_counter() - t_loop) / 100
                budget = time_limit_s * 0.85 - (t_loop - t_begin)
                if rate * iters > budget:
                    iters = max(150, int(max(budget, 0.1) / rate))
                    time_limited = True
            if k % 16 == 0 and time.perf_counter() - t_begin > time_limit_s:
                time_limited = True
                break
            done = k + 1
            frac = k / iters
            temp = t0 * (t1 / t0) ** frac
            n = movable[rng.randrange(len(movable))]
            step = 40 + 160 * (1 - frac)
            nx = min(hi_x[n], max(lo_x[n], X[n] + rng.gauss(0, step)))
            ny = min(hi_y[n], max(lo_y[n], Y[n] + rng.gauss(0, step)))
            if not free_of_overlap(n, nx, ny):
                continue
            old = local(n)
            ox, oy = X[n], Y[n]
            X[n], Y[n] = nx, ny
            for e in inc[n]:
                refresh(e)
            new = local(n)
            delta = new - old
            if delta < 0 or rng.random() < math.exp(-delta / temp):
                cur += delta
                if cur < best - 1e-9:
                    best, bx_, by_ = cur, list(X), list(Y)
            else:
                X[n], Y[n] = ox, oy
                for e in inc[n]:
                    refresh(e)
        X, Y = bx_, by_
        for e in range(M):
            refresh(e)
    final_cost = total() if M else 0.0
    return LayoutResult(positions={k: (round(X[i], 1), round(Y[i], 1)) for i, k in enumerate(ids)}, iterations=done,
                        elapsed_ms=int((time.perf_counter() - t_begin) * 1000), cost=round(final_cost, 1),
                        crossings=count_crossings() if M else 0, initial_crossings=initial_crossings, seed=seed, time_limited=time_limited)
