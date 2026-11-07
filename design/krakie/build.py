#!/usr/bin/env python3
"""Krakie sprites (32x32 pixel art) -> SVG.

Usage:
  python design/krakie/build.py            # krakie-32.json -> SVG (design/krakie/ + frontend/public/krakie/)
  python design/krakie/build.py --redraw   # regenerate krakie-32.json from the procedural drawing below, then SVG
  python design/krakie/build.py --redraw-anim  # regenerate krakie-32-anim.json (4 frames/pose), then anim SVG
                                           # -> frontend/public/krakie/anim/<pose>-<n>.svg (n = 1..4) + manifest.json (ms per frame)

krakie-32.json is the source of truth once hand-edited: do not --redraw after manual edits.
Each pose is a list of 32 strings of 32 chars; ' ' = transparent, other chars = palette keys.
SVG: one <rect> per horizontal run of the same colour, crispEdges.
"""
import json
import math
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent.parent
JSON_PATH = HERE / "krakie-32.json"
OUT_DIRS = [HERE, ROOT / "frontend" / "public" / "krakie"]
W = H = 32

PALETTE = {
    "K": "#0B2B33",  # contour / encre
    "B": "#147A77",  # lagon ombre
    "b": "#0E5754",  # lagon ombre profonde (tentacule arrière)
    "L": "#1FA39E",  # lagon
    "H": "#7FDCD4",  # lagon lumière
    "W": "#FFFFFF",  # reflet
    "C": "#F29A8E",  # joues
    "m": "#C2504A",  # bouche
    "A": "#E0A23B",  # lanterne (nœuds, loupe, ?)
    "a": "#A86E18",  # lanterne ombre / fils
    "p": "#F5E6C8",  # papier
    "q": "#C9B994",  # papier ombre / lignes de texte
    "V": "#3E5C9A",  # couverture du livre
    "G": "#CDEFF5",  # verre (loupe, pare-brise)
    "S": "#9AD7F0",  # goutte de sueur
    "R": "#D6453D",  # bolide
    "r": "#8F2420",  # bolide ombre
    "g": "#8A99A3",  # jante / traits de vitesse
}

POSES = ["accueil", "reflechit", "lit", "loupe", "graphe", "contente", "inquiete", "bolide"]
LABELS = {
    "accueil": "fait coucou", "reflechit": "réfléchit", "lit": "lit un livre (documentation)",
    "loupe": "examine à la loupe (conformité)", "graphe": "tire des fils entre des nœuds (graphe)",
    "contente": "contente", "inquiete": "inquiète", "bolide": "pilote un petit bolide (génération)",
}


# ---------------------------------------------------------------- drawing primitives
class Canvas:
    def __init__(self):
        self.px = {}

    def layer(self, pixels, outline=True):
        if outline:
            for (x, y) in pixels:
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    q = (x + dx, y + dy)
                    if q not in pixels:
                        self.put(q, "K")
        for p, c in pixels.items():
            self.put(p, c)

    def put(self, p, c):
        if 0 <= p[0] < W and 0 <= p[1] < H:
            self.px[p] = c

    def stamp(self, x, y, rows, mapping=None):
        for j, row in enumerate(rows):
            for i, ch in enumerate(row):
                if ch != ".":
                    self.put((x + i, y + j), (mapping or {}).get(ch, ch))

    def rows(self):
        return ["".join(self.px.get((x, y), " ") for x in range(W)) for y in range(H)]


def ellipse(cx, cy, rx, ry):
    return {(x, y) for x in range(-4, W + 4) for y in range(-4, H + 4)
            if ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2 <= 1.0}


def disc(cx, cy, r):
    return {(x, y) for x in range(int(cx - r) - 1, int(cx + r) + 2)
            for y in range(int(cy - r) - 1, int(cy + r) + 2)
            if (x - cx) ** 2 + (y - cy) ** 2 <= r * r + 0.01}


def path(points, r0=1.5, r1=0.8):
    segs = list(zip(points, points[1:]))
    lens = [math.dist(a, b) for a, b in segs]
    total = sum(lens) or 1
    out, done = set(), 0.0
    for (a, b), ln in zip(segs, lens):
        n = max(1, int(ln * 4))
        for k in range(n + 1):
            t = k / n
            x, y = a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t
            r = r0 + (r1 - r0) * ((done + ln * t) / total)
            out |= disc(x, y, r)
        done += ln
    return out


def line(x0, y0, x1, y1):
    n = int(max(abs(x1 - x0), abs(y1 - y0))) or 1
    return {(round(x0 + (x1 - x0) * k / n), round(y0 + (y1 - y0) * k / n)) for k in range(n + 1)}


def shade(mask, base="L", dark="B", light="H", cx=0.0, cy=0.0, rim=False):
    out = {}
    for (x, y) in mask:
        c = base
        if (x + 1, y) not in mask or (x, y + 1) not in mask:
            c = dark
        elif rim and x > cx and ((x + 2, y) not in mask or (x, y + 2) not in mask):
            c = dark
        elif light and ((x - 1, y) not in mask or (x, y - 1) not in mask) and x < cx and y < cy:
            c = light
        out[(x, y)] = c
    return out


def mirror(pts):
    return [(31 - x, y) for x, y in pts]


# ---------------------------------------------------------------- Krakie
EYES = {
    "open":   [".KK.", "KWWK", "KWKK", "KKKK", ".KK."],
    "closed": ["....", "....", "KKKK", "....", "...."],
    "up":     [".KK.", "KKWK", "KKWK", "KKKK", ".KK."],
    "down":   ["....", ".KK.", "KKKK", "KWKK", ".KK."],
    "happy":  ["....", ".KK.", "K..K", "....", "...."],
    "small":  ["....", ".KK.", "KWKK", ".KK.", "...."],
}
MOUTHS = {
    "smile": ["K..K", ".KK."],
    "open":  ["KKKK", "KmmK", ".KK."],
    "flat":  [".KKK", "...."],
    "wavy":  ["K.K.K.", ".K.K.K"],
    "o":     [".KK.", "K..K", ".KK."],
}


def tentacles(dx=0, dy=0, skip=(), override=None, sway=0.0, scale=1.0):
    """Default 7 tentacles (back middle + 3 pairs). Returns {name: (points, r0, r1, base)}."""
    left = {
        "T1": [(7, 16), (5, 21), (4, 24), (2, 26), (1, 24)],
        "T2": [(10, 17), (9, 22), (8, 26), (6, 28)],
        "T3": [(13, 17), (13, 23), (12, 27), (10, 29)],
    }
    t = {"T7": ([(15.5, 17), (15.5, 29)], 1.5, 1.0, "B")}
    for k, pts in left.items():
        t[k] = (pts, 1.5, 0.8, "L")
        t["T" + str(7 - int(k[1]))] = (mirror(pts), 1.5, 0.8, "L")
    t.update(override or {})
    res = {}
    for k, (pts, r0, r1, base) in t.items():
        if k in skip:
            continue
        res[k] = ([(x + dx + sway * max(0.0, y - 21) / 7, 16 + (y - 16) * scale + dy) for x, y in pts], r0, r1, base)
    return res


def draw_krakie(c, dx=0, dy=0, eyes="open", mouth="smile", cheeks=True, brows=None,
                skip=(), override=None, front=(), behind_head=(), rx=11.5,
                head_dy=0, sway=0.0, blink=False, scale=1.0):
    cx, cy = 15.5 + dx, 9.5 + dy + head_dy
    order = ["T7", "T1", "T6", "T2", "T5", "T3", "T4"]
    tt = tentacles(dx, dy, skip, override, sway, scale)
    if blink:
        eyes = "closed"
    for k in order + [k for k in tt if k not in order]:
        if k in tt and k not in front:
            pts, r0, r1, base = tt[k]
            m = path(pts, r0, r1)
            c.layer(shade(m, base, "b" if base == "B" else "B", None))
    for fn in behind_head:
        fn(c)
    head = ellipse(cx, cy, rx, 9) | ellipse(cx, cy + 5, rx - 0.5, 5)
    c.layer(shade(head, "L", "B", "H", cx, cy, rim=True))
    # specular streak top-left
    for p in [(-6.5, -6), (-5.5, -6), (-7.5, -5), (-6.5, -5), (-8.5, -4)]:
        c.put((round(cx + p[0]), round(cy + p[1])), "H")
    c.put((round(cx - 5.5), round(cy - 7)), "W")
    ex_l, ex_r, ey = round(cx - 6.5), round(cx + 3.5), round(cy - 0.5)
    e = EYES[eyes]
    c.stamp(ex_l, ey, e)
    c.stamp(ex_r, ey, e if eyes not in ("up",) else e)
    if brows == "worried":
        c.stamp(ex_l, ey - 2, ["KK..", "..KK"][::-1])
        c.stamp(ex_r, ey - 2, ["..KK", "KK.."][::-1])
    elif brows == "raised":
        c.stamp(ex_r, ey - 2, [".KK.", "K..K"])
    if cheeks:
        for x in (cx - 8.5, cx - 7.5, cx + 7.5, cx + 8.5):
            c.put((round(x), round(cy + 4.5)), "C")
    mo = MOUTHS[mouth]
    c.stamp(round(cx - len(mo[0]) / 2 + 0.5), round(cy + 4.5), mo)
    for k in front:
        if k in tt:
            pts, r0, r1, base = tt[k]
            c.layer(shade(path(pts, r0, r1), base, "B", None))
    return cx, cy


def pose_accueil():
    c = Canvas()
    wave = [(9, 17), (5, 15), (3, 11), (3, 7), (4, 4)]
    draw_krakie(c, dx=2, eyes="open", mouth="open", rx=10.5,
                override={"T1": ([(p[0] - 2, p[1]) for p in wave], 1.5, 0.9, "L")}, front=("T1",))
    for p in [(0, 3), (0, 5), (1, 1), (7, 1), (8, 2)]:
        c.put(p, "g")
    return c


def pose_reflechit():
    c = Canvas()
    chin = [(21, 26), (23, 23), (22, 20), (19, 18), (17, 18)]
    draw_krakie(c, dx=-2, eyes="up", mouth="flat", brows="raised", rx=10.5,
                override={"T5": ([(x - 2 + 2, y) for x, y in chin], 1.4, 0.9, "L")}, front=("T5",))
    q = [".AA.", "A..A", "...A", "..A.", "....", "..A."]
    c.layer({(26 + i, 1 + j): "A" for j, r in enumerate(q) for i, ch in enumerate(r) if ch == "A"})
    return c


def pose_lit():
    c = Canvas()

    def book(cv):
        m = {}
        for x in range(7, 25):
            for y in range(18, 26):
                m[(x, y)] = "V"
        for x in range(8, 24):
            for y in range(17, 25):
                if (x, y) in ((8, 17), (23, 17)):
                    continue
                m[(x, y)] = "q" if x in (15, 16) else "p"
        for y in (19, 21, 23):
            for x in list(range(9, 14)) + list(range(18, 23)):
                m[(x, y)] = "q"
        cv.layer(m)

    draw_krakie(c, eyes="down", mouth="smile", skip=("T7",),
                override={"T2": ([(9, 17), (7, 21), (8, 23)], 1.5, 1.0, "L"),
                          "T5": ([(22, 17), (24, 21), (23, 23)], 1.5, 1.0, "L")})
    book(c)
    for x, y in [(7, 21), (8, 22), (7, 22), (24, 21), (23, 22), (24, 22)]:
        c.put((x, y), "L")
    return c


def pose_loupe():
    c = Canvas()
    handle = [(26, 26), (28, 22), (27, 18)]
    draw_krakie(c, dx=-1, eyes="open", mouth="o", rx=11,
                override={"T6": (handle, 1.5, 1.0, "L")})
    lx, ly = 21, 10
    ring = {p: "A" for p in disc(lx, ly, 4.6)}
    for p in disc(lx, ly, 3.5):
        ring[p] = "G"
    for p in line(24, 14, 26, 17):
        ring[p] = "a"
        ring[(p[0] + 1, p[1])] = "a"
    c.layer(ring)
    c.stamp(19, 7, [".KKK.", "KWWKK", "KWKKK", "KKKKK", ".KKK."])
    c.put((18, 8), "W")
    pts, r0, r1, base = tentacles(-1, 0, override={"T6": (handle, 1.5, 1.0, "L")})["T6"]
    c.layer(shade(path(pts[1:], 1.4, 1.0), "L", "B", None))
    return c


def pose_graphe():
    c = Canvas()
    nodes = [(3, 3), (28, 3), (2, 17), (29, 17), (5, 29), (26, 29)]
    for (a, b) in [(0, 2), (1, 3), (2, 4), (3, 5), (0, 1), (4, 5)]:
        for p in line(*nodes[a], *nodes[b]):
            c.put(p, "a")
    for n in nodes:
        c.layer({p: ("A" if p != (n[0] - 1, n[1] - 1) else "W") for p in disc(n[0], n[1], 1.5)})
    left = [(8, 16), (5, 18), (3, 18)]
    draw_krakie(c, eyes="open", mouth="smile", rx=10, skip=("T7",),
                override={"T1": (left, 1.5, 1.0, "L"), "T6": (mirror(left), 1.5, 1.0, "L"),
                          "T2": ([(10, 17), (9, 22), (7, 26), (6, 28)], 1.5, 1.0, "L"),
                          "T5": (mirror([(10, 17), (9, 22), (7, 26), (6, 28)]), 1.5, 1.0, "L")})
    for n in nodes:  # nodes stay on top of tentacle tips
        c.layer({p: ("A" if p != (n[0] - 1, n[1] - 1) else "W") for p in disc(n[0], n[1], 1.5)})
    return c


def pose_contente():
    c = Canvas()
    draw_krakie(c, eyes="happy", mouth="open",
                override={"T1": ([(7, 16), (4, 18), (2, 15), (2, 12)], 1.5, 0.9, "L"),
                          "T6": (mirror([(7, 16), (4, 18), (2, 15), (2, 12)]), 1.5, 0.9, "L")})
    for (x, y) in [(2, 3), (29, 5), (27, 1)]:
        c.stamp(x - 1, y - 1, [".A.", "AWA", ".A."])
    return c


def pose_inquiete():
    c = Canvas()
    draw_krakie(c, eyes="small", mouth="wavy", brows="worried",
                override={"T3": ([(13, 17), (14, 22), (15, 25)], 1.5, 0.9, "L"),
                          "T4": ([(18, 17), (17, 22), (16, 25)], 1.5, 0.9, "L")})
    drop = {(27, 2): "S", (26, 3): "S", (27, 3): "S", (28, 3): "S", (26, 4): "W", (27, 4): "S", (28, 4): "S",
            (27, 5): "S"}
    c.layer(drop)
    return c


def pose_bolide():
    c = Canvas()
    for y, x0, x1 in [(8, 0, 3), (12, 0, 2), (16, 0, 3)]:
        for x in range(x0, x1 + 1):
            c.put((x, y), "g")
    draw_krakie(c, dx=-2, dy=1, eyes="open", mouth="open", rx=10, skip=("T1", "T2", "T3", "T4", "T7"),
                override={"T6": ([(21, 18), (23, 16), (24, 14)], 1.4, 1.0, "L")}, front=("T6",))
    body = {}
    for x in range(1, 31):
        for y in range(19, 28):
            top = 19 if x <= 21 else 19 + (x - 21) * 0.5
            if y >= top and not (x == 1 and y in (19, 27)) and not (x == 30 and y == 27):
                body[(x, y)] = "R"
    for (x, y) in list(body):
        if y >= 26:
            body[(x, y)] = "r"
        elif y == 22 and 2 <= x <= 28:
            body[(x, y)] = "W"
    for x in range(4, 18):
        body[(x, 19)] = "r"
    c.layer(body)
    shield = {(x, y): "G" for x in (21, 22) for y in range(15, 19)}
    shield.update({(23, 17): "G", (23, 18): "G"})
    c.layer(shield)
    hand = path([(7, 21), (5, 18), (3, 17), (1, 18)], 1.4, 0.9)  # tentacle over the door, streaming back
    c.layer(shade(hand, "L", "B", None))
    for wx in (7, 24):
        c.layer({p: "K" for p in disc(wx, 28, 2.6)})
        for p in disc(wx, 28, 1.0):
            c.put(p, "g")
    return c


DRAW = {"accueil": pose_accueil, "reflechit": pose_reflechit, "lit": pose_lit, "loupe": pose_loupe,
        "graphe": pose_graphe, "contente": pose_contente, "inquiete": pose_inquiete, "bolide": pose_bolide}



# ---------------------------------------------------------------- animation (krakie-32-anim.json)
ANIM_JSON = HERE / "krakie-32-anim.json"
ANIM_DIR = ROOT / "frontend" / "public" / "krakie" / "anim"
# idle commun : ondoiement des tentacules, respiration (tête qui s'affaisse d'1 px), clignement
IDLE = [dict(sway=0.0), dict(sway=0.8), dict(sway=0.0, head_dy=1, blink=True), dict(sway=-0.8)]
MS = [260, 220, 140, 220]


def a_accueil(f, idle):
    c = Canvas()
    tips = [[(3, 7), (4, 4)], [(4, 7), (6, 3)], [(3, 7), (4, 4)], [(2, 8), (1, 5)]][f]
    wave = [(9, 17), (5, 15), (3, 11)] + tips
    draw_krakie(c, dx=2, eyes="open", mouth="open", rx=10.5, front=("T1",),
                override={"T1": ([(p[0] - 2, p[1]) for p in wave], 1.5, 0.9, "L")}, **idle)
    marks = [[(0, 3), (0, 5), (1, 1)], [(7, 1), (8, 2), (9, 4)], [(0, 3), (0, 5), (1, 1)], [(0, 7), (0, 9), (0, 2)]][f]
    for p in marks:
        c.put(p, "g")
    return c


def a_reflechit(f, idle):
    c = Canvas()
    chin = [(21, 26), (23, 23), (22, 20), (19, 18), (17, 18)]
    draw_krakie(c, dx=-2, eyes="up", mouth="flat", brows="raised", rx=10.5,
                override={"T5": (chin, 1.4, 0.9, "L")}, front=("T5",), **idle)
    q = [".AA.", "A..A", "...A", "..A.", "....", "..A."]
    y0, col = [(1, "A"), (0, "A"), (1, "a"), (1, "A")][f]
    c.layer({(26 + i, y0 + j): col for j, r in enumerate(q) for i, ch in enumerate(r) if ch == "A"})
    if f == 1:
        c.put((25, 0), "W")
        c.put((31, 3), "W")
    return c


def a_lit(f, idle):
    c = Canvas()
    idle = dict(idle, blink=False)
    draw_krakie(c, eyes="down", mouth="smile", skip=("T7",),
                override={"T2": ([(9, 17), (7, 21), (8, 23)], 1.5, 1.0, "L"),
                          "T5": ([(22, 17), (24, 21), (23, 23)], 1.5, 1.0, "L")}, **idle)
    m = {}
    for x in range(7, 25):
        for y in range(18, 26):
            m[(x, y)] = "V"
    for x in range(8, 24):
        for y in range(17, 25):
            if (x, y) not in ((8, 17), (23, 17)):
                m[(x, y)] = "q" if x in (15, 16) else "p"
    for y in (19, 21, 23):
        for x in list(range(9, 14)) + list(range(18, 23)):
            m[(x, y)] = "q"
    c.layer(m)
    page = {1: (17, 21, 15, 23), 2: (15, 16, 12, 23), 3: (10, 14, 15, 23)}.get(f)
    if page:
        x0, x1, y0, y1 = page
        pg = {(x, y): "p" for x in range(x0, x1 + 1) for y in range(y0, y1 + 1)}
        if x1 - x0 > 2:
            for y in range(y0 + 2, y1, 2):
                for x in range(x0 + 1, x1):
                    pg[(x, y)] = "q"
        c.layer(pg)
    for x, y in [(7, 21), (8, 22), (7, 22), (24, 21), (23, 22), (24, 22)]:
        c.put((x, y), "L")
    return c


def a_loupe(f, idle):
    c = Canvas()
    lx, ly = [(21, 10), (22, 11), (21, 12), (20, 11)][f]
    handle = [(26, 26), (28, 22), (lx + 6, ly + 8)]
    draw_krakie(c, dx=-1, eyes="open", mouth="o", rx=11, override={"T6": (handle, 1.5, 1.0, "L")}, **idle)
    ring = {p: "A" for p in disc(lx, ly, 4.6)}
    for p in disc(lx, ly, 3.5):
        ring[p] = "G"
    for p in line(lx + 3, ly + 4, lx + 5, ly + 7):
        ring[p] = "a"
        ring[(p[0] + 1, p[1])] = "a"
    c.layer(ring)
    c.stamp(lx - 2, ly - 3, [".KKK.", "KWWKK", "KWKKK", "KKKKK", ".KKK."] if not idle.get("blink") else
            [".....", ".....", "KKKKK", ".....", "....."])
    c.put((lx - 3, ly - 2), "W")
    c.layer(shade(path(handle[1:], 1.4, 1.0), "L", "B", None))
    return c


def a_graphe(f, idle):
    c = Canvas()
    nodes = [(3, 3), (28, 3), (2, 17), (29, 17), (5, 29), (26, 29)]
    lit = [{2, 3}, {2, 3, 0, 1}, {2, 3, 0, 1, 4}, {0, 1, 2, 3, 4, 5}][f]
    for (a, b) in [(0, 2), (1, 3), (2, 4), (3, 5), (0, 1), (4, 5)]:
        on = a in lit and b in lit
        for p in line(*nodes[a], *nodes[b]):
            c.put(p, "A" if on else "g")
    left = [(8, 16), (5, 18), (3, 18)]

    def dots(cv):
        for i, n in enumerate(nodes):
            on = i in lit
            cv.layer({p: (("W" if p == (n[0] - 1, n[1] - 1) else "A") if on else "g") for p in disc(n[0], n[1], 1.5)})

    dots(c)
    draw_krakie(c, eyes="open", mouth="smile", rx=10, skip=("T7",),
                override={"T1": (left, 1.5, 1.0, "L"), "T6": (mirror(left), 1.5, 1.0, "L"),
                          "T2": ([(10, 17), (9, 22), (7, 26), (6, 28)], 1.5, 1.0, "L"),
                          "T5": (mirror([(10, 17), (9, 22), (7, 26), (6, 28)]), 1.5, 1.0, "L")}, **idle)
    dots(c)
    return c


def a_contente(f, idle):
    c = Canvas()
    dy, sc = [(2, 0.8), (1, 0.9), (0, 0.7), (1, 0.9)][f]
    arm = [(7, 16), (4, 18), (2, 15), (2, 12)] if f != 2 else [(7, 16), (4, 16), (2, 12), (3, 9)]
    draw_krakie(c, dy=dy, eyes="happy", mouth="open", scale=sc,
                override={"T1": (arm, 1.5, 0.9, "L"), "T6": (mirror(arm), 1.5, 0.9, "L")},
                sway=idle.get("sway", 0))
    spark = [[(2, 3), (29, 5), (27, 1)], [(4, 1), (28, 8)], [(1, 6), (30, 2), (25, 3), (6, 1)], [(3, 2), (29, 6)]][f]
    for (x, y) in spark:
        c.stamp(x - 1, y - 1, [".A.", "AWA", ".A."])
    return c


def a_inquiete(f, idle):
    c = Canvas()
    dx = [0, 1, 0, 1][f]
    draw_krakie(c, dx=dx, eyes="small", mouth="wavy", brows="worried",
                override={"T3": ([(13, 17), (14, 22), (15, 25)], 1.5, 0.9, "L"),
                          "T4": ([(18, 17), (17, 22), (16, 25)], 1.5, 0.9, "L")}, **dict(idle, head_dy=0))
    x, y = [(27, 2), (28, 6), (29, 10), (29, 15)][f]
    drop = {(x, y): "S", (x - 1, y + 1): "S", (x, y + 1): "S", (x + 1, y + 1): "S", (x - 1, y + 2): "W",
            (x, y + 2): "S", (x + 1, y + 2): "S", (x, y + 3): "S"}
    if f == 3:
        drop = {(x, y): "S", (x - 1, y + 1): "W", (x, y + 1): "S", (x + 1, y + 1): "S", (x, y + 2): "S"}
    c.layer(drop)
    return c


def a_bolide(f, idle):
    c = Canvas()
    off = [0, 1, 2, 1][f]
    for y, x0, x1 in [(8, 0, 3), (12, 0, 2), (16, 0, 3), (4, 0, 1)]:
        for x in range(x0 + off - 1, x1 + off):
            c.put((x % 5, y + (f % 2 if y == 4 else 0)), "g")
    hb = [0, 1, 0, 1][f]
    draw_krakie(c, dx=-2, dy=1, eyes="open", mouth="open", rx=10, skip=("T1", "T2", "T3", "T4", "T7"),
                override={"T6": ([(21, 18), (23, 16), (24, 14)], 1.4, 1.0, "L")}, front=("T6",),
                head_dy=hb, blink=idle.get("blink", False))
    body = {}
    for x in range(1, 31):
        for y in range(19, 28):
            top = 19 if x <= 21 else 19 + (x - 21) * 0.5
            if y >= top and not (x == 1 and y in (19, 27)) and not (x == 30 and y == 27):
                body[(x, y)] = "r" if y >= 26 else ("W" if y == 22 and 2 <= x <= 28 else "R")
    for x in range(4, 18):
        body[(x, 19)] = "r"
    c.layer(body)
    shield = {(x, y): "G" for x in (21, 22) for y in range(15, 19)}
    shield.update({(23, 17): "G", (23, 18): "G"})
    c.layer(shield)
    tip = [(1, 18), (1, 16), (1, 18), (2, 19)][f]
    c.layer(shade(path([(7, 21), (5, 18), (3, 17), tip], 1.4, 0.9), "L", "B", None))
    for wx in (7, 24):
        c.layer({p: "K" for p in disc(wx, 28, 2.6)})
        for p in disc(wx, 28, 1.0):
            c.put(p, "g")
        spokes = [(0, 0), (-1, 0), (1, 0), (0, -1), (0, 1)] if f % 2 == 0 else [(0, 0), (-1, -1), (1, 1), (-1, 1), (1, -1)]
        for sx, sy in spokes:
            c.put((wx + sx, 28 + sy), "K")
    return c


ANIM = {"accueil": a_accueil, "reflechit": a_reflechit, "lit": a_lit, "loupe": a_loupe, "graphe": a_graphe,
        "contente": a_contente, "inquiete": a_inquiete, "bolide": a_bolide}
ANIM_MS = {"lit": [600, 160, 140, 160], "graphe": [260, 260, 260, 520], "contente": [160, 120, 160, 120],
           "inquiete": [240, 200, 200, 200], "bolide": [110, 110, 110, 110], "reflechit": [320, 240, 320, 160]}


def redraw_anim():
    poses = {}
    for name in POSES:
        ms = ANIM_MS.get(name, MS)
        poses[name] = {"frames": [{"ms": ms[f], "rows": ANIM[name](f, IDLE[f]).rows()} for f in range(4)]}
    data = {"name": "Krakie (animé)", "size": [W, H],
            "note": "Frames 32x32 par pose (idle commun + animation propre). Généré par build.py --redraw-anim, retouchable à la main.",
            "palette": PALETTE, "poses": poses}
    ANIM_JSON.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def build_anim():
    data = json.loads(ANIM_JSON.read_text(encoding="utf-8"))
    ANIM_DIR.mkdir(parents=True, exist_ok=True)
    manifest = {}
    for name, pose in data["poses"].items():
        manifest[name] = []
        for n, fr in enumerate(pose["frames"], start=1):
            rows = fr["rows"]
            assert len(rows) == H and all(len(r) == W for r in rows), (name, n)
            (ANIM_DIR / f"{name}-{n}.svg").write_text(to_svg(name, rows, data["palette"]), encoding="utf-8")
            manifest[name].append(fr["ms"])
    (ANIM_DIR / "manifest.json").write_text(json.dumps(manifest) + "\n", encoding="utf-8")
    print("anim ok:", ", ".join(f"{k}×{len(v)}" for k, v in manifest.items()))


# ---------------------------------------------------------------- JSON -> SVG
def to_svg(name, rows, palette):
    rects = []
    for y, row in enumerate(rows):
        x = 0
        while x < len(row):
            ch = row[x]
            if ch == " ":
                x += 1
                continue
            x0 = x
            while x < len(row) and row[x] == ch:
                x += 1
            rects.append(f'<rect x="{x0}" y="{y}" width="{x - x0}" height="1" fill="{palette[ch]}"/>')
    title = f"Krakie — {LABELS.get(name, name)}"
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" '
            f'shape-rendering="crispEdges" role="img" aria-label="{title}"><title>{title}</title>'
            + "".join(rects) + "</svg>\n")


def main():
    if "--redraw" in sys.argv:
        data = {
            "name": "Krakie",
            "note": "Sprites 32x32 (ébauche 20 px validée le 3/11). ' ' = transparent. Généré par build.py --redraw puis retouchable à la main.",
            "size": [W, H],
            "palette": PALETTE,
            "poses": {p: DRAW[p]().rows() for p in POSES},
        }
        JSON_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    data = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    for d in OUT_DIRS:
        d.mkdir(parents=True, exist_ok=True)
        for name, rows in data["poses"].items():
            assert len(rows) == H and all(len(r) == W for r in rows), name
            (d / f"{name}.svg").write_text(to_svg(name, rows, data["palette"]), encoding="utf-8")
    print("ok:", ", ".join(data["poses"]))
    if "--redraw-anim" in sys.argv:
        redraw_anim()
    if ANIM_JSON.exists():
        build_anim()


if __name__ == "__main__":
    main()
