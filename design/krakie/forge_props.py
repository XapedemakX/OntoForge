#!/usr/bin/env python3
"""L29 — propositions « forge » + « trophée » pour Krakie (remplacement de la pose « bolide »).

Script dérivé de build.py (même grille 32x32, mêmes primitives, même contour, palette de base inchangée).
Il n'écrit RIEN dans frontend/ ni dans krakie-32*.json : sorties sous journal/L29/propositions/.

Usage :
  python design/krakie/forge_props.py --redraw   # dessin procédural -> JSON (une source par proposition), puis rendus
  python design/krakie/forge_props.py            # JSON (éventuellement retouchés à la main) -> SVG, PNG, GIF

Sources : journal/L29/propositions/<prop>/krakie-<prop>.json, au format de krakie-32-anim.json
          ({name, size, note, palette, poses: {forge: {frames: [{ms, rows}]}, trophee: {...}}}).
"""
import json
import math
import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import build  # noqa: E402  (primitives et palette de base de Krakie)
from build import Canvas, draw_krakie, disc, line, path, shade, mirror, W, H  # noqa: E402

from PIL import Image, ImageDraw, ImageFont  # noqa: E402

ROOT = build.ROOT
OUT = ROOT / "journal" / "L29" / "propositions"

# palette de base (inchangée) + palette de forge
FORGE = {
    "Y": "#FFE27A",  # incandescent (cœur des étincelles, métal chauffé à blanc)
    "O": "#F5861F",  # orange forge (métal rougeoyant, flammes)
    "E": "#B8321F",  # rouge braise
    "e": "#6E1E14",  # braise sombre / charbon chaud
    "N": "#4B5A64",  # acier sombre (ombre de l'enclume, tête du marteau)
    "n": "#C4D0D8",  # acier clair (face de l'enclume, arête du marteau)
    "d": "#7A4A26",  # bois (manche)
    "c": "#3A3F46",  # pierre / brique sombre du foyer
}
FORGE["w"] = "#D9A066"  # bois clair (manche)
PALETTE = build.PALETTE  # la palette de forge est fusionnée dans build.PALETTE (L29 étape 2)
assert all(PALETTE[k] == v for k, v in FORGE.items())

BG_LIGHT, BG_DARK = (246, 242, 233), (16, 30, 38)


# ---------------------------------------------------------------- objets
def stamp_layer(c, x, y, rows, outline=False):
    """Stamp ('.' transparent) ; avec outline=True, contour K automatique autour."""
    m = {}
    for j, r in enumerate(rows):
        for i, ch in enumerate(r):
            if ch != ".":
                m[(x + i, y + j)] = ch
    c.layer(m, outline=outline)


ANVIL = [  # 17 x 8, bigorne à gauche
    "KKKKKKKKKKKKKKKK.",
    "KnnnnnnnnnnnnnnNK",
    ".KKKggggggggggNNK",
    "....KKggggggNNKK.",
    "......KgggNNK....",
    "......KgggNNK....",
    "....KKggggggNNKK.",
    "...KNNNNNNNNNNNNK",
    "...KKKKKKKKKKKKKK",
]
ANVIL_SMALL = [  # 13 x 7
    "KKKKKKKKKKKKK",
    "KnnnnnnnnnnNK",
    ".KKKgggggNNK.",
    "....KggNNK...",
    "....KggNNK...",
    "...KggggNNK..",
    "..KNNNNNNNNK.",
    "..KKKKKKKKKK.",
]


def anvil(c, x, y, small=False):
    stamp_layer(c, x, y, ANVIL_SMALL if small else ANVIL)


def hot_bar(c, x, y, w, heat):
    """Barre de métal posée sur l'enclume ; heat 0..3 (rouge sombre -> blanc)."""
    cols = [("e", "E"), ("E", "O"), ("O", "Y"), ("Y", "W")][heat]
    m = {(x + i, y): cols[1] for i in range(w)}
    m.update({(x + i, y + 1): cols[0] for i in range(w)})
    c.layer(m)


def hammer(c, grip, angle, length=7, head=(5, 3), outline=True):
    """Marteau : manche du point de prise vers angle (degrés, 0 = droite, -90 = haut), tête perpendiculaire."""
    a = math.radians(angle)
    ux, uy = math.cos(a), math.sin(a)
    vx, vy = -uy, ux
    hx, hy = grip[0] + ux * length, grip[1] + uy * length
    m = {}
    for p in line(grip[0], grip[1], round(hx - ux * 1.5), round(hy - uy * 1.5)):
        m[p] = "w"
    hl, ht = head
    for i in range(-hl * 2, hl * 2 + 1):
        for j in range(-ht * 2, ht * 2 + 1):
            s, t = i / 4, j / 4
            if abs(s) <= hl / 2 and abs(t) <= ht / 2:
                px = (round(hx + vx * s + ux * t), round(hy + vy * s + uy * t))
                # arête claire du côté de la frappe (bout du marteau), ombre de l'autre
                m[px] = "n" if t > ht / 2 - 0.75 else ("N" if t < -ht / 2 + 0.75 else "g")
    c.layer(m, outline=outline)
    return (round(hx + ux * ht / 2), round(hy + uy * ht / 2))


def hammer_diag(c, grip, dx, length=4):
    """Marteau incliné à 45° dessiné à la main : manche fin en bois clair, tête en bande d'acier
    perpendiculaire (arête claire / flanc sombre). dx = +1 vers la droite, -1 vers la gauche."""
    gx, gy = grip
    hx, hy = gx + dx * length, gy - length
    m = {}
    for k in range(length):
        m[(gx + dx * k, gy - k)] = "w"
    for k in range(-2, 3):  # bande d'acier perpendiculaire au manche (diagonale opposée), 2 px d'épaisseur
        m[(hx + dx * k, hy + k)] = "n"
        m[(hx + dx * k, hy + k + 1)] = "N"
    c.layer(m, outline=True)


def sparks(c, origin, f, n=7, spread=1.0, seed=0, colors="YOE", arc=(-170, -10)):
    """Étincelles radiales autour du point d'impact ; f = âge (0 = impact)."""
    ox, oy = origin
    if f < 0:
        return
    for k in range(n):
        ang = math.radians(arc[0] + (arc[1] - arc[0]) * k / max(1, n - 1) + (seed * 37 % 11) - 5)
        r = (1.5 + f * 2.2) * spread * (0.8 + 0.4 * ((k * 7 + seed) % 3) / 2)
        x, y = round(ox + math.cos(ang) * r), round(oy + math.sin(ang) * r + f * f * 0.35)
        col = colors[min(f, len(colors) - 1)] if f > 0 else "W"
        c.put((x, y), col)
        if f <= 1:  # traînée
            c.put((round(ox + math.cos(ang) * (r - 1)), round(oy + math.sin(ang) * (r - 1))), "O" if f else "Y")


def star(c, x, y, big=False, col="Y"):
    if big:
        c.stamp(x - 2, y - 2, ["..O..", "..Y..", "OYWYO", "..Y..", "..O.."])
    else:
        c.stamp(x - 1, y - 1, [".%s." % col, "%sW%s" % (col, col), ".%s." % col])


# ---------------------------------------------------------------- trophées (dessinés à la main)
# Nœuds : pastilles Y/O (métal chaud) cerclées de K ; arêtes : 1 px (a = or sombre, g = acier).
TROPHY_CUP = [  # P1 — coupe à anses surmontée d'un graphe en losange (4 nœuds, 5 arêtes) — 13 x 21
    ".....KKK.....",
    "....KYWOK....",
    "....KOOOK....",
    "....aKKKa....",
    "...a.....a...",
    ".KKK.....KKK.",
    "KYYOK...KYYOK",
    "KOOOKaaaKOOOK",
    ".KKK.....KKK.",
    "...a.....a...",
    "KK..aKKKa..KK",
    "KaK.KYYOK.KaK",
    "KaKKKOOOKKKaK",
    ".KaAAKKKAAaK.",
    "..KAWAAAAaK..",
    "...KAWAAaK...",
    "....KAAaK....",
    ".....KAK.....",
    "....KAAaK....",
    "...KAAAAaK...",
    "...KKKKKKK...",
]
TROPHY_CUP_SHINE = [[], [(5, 13), (4, 14)], [(5, 1), (6, 15)], [(1, 6), (9, 6)]]

TROPHY_PLINTH = [  # P2 — graphe forgé de 5 nœuds (2-1-2) sur un socle d'acier — 13 x 19
    ".KKK.....KKK.",
    "KYWOK...KYYOK",
    "KOOOKgggKOOOK",
    ".KKKg...gKKK.",
    "....gKKKg....",
    "....KYYOK....",
    "....KOOOK....",
    "...g.KKK.g...",
    ".KKK..g..KKK.",
    "KYYOK.g.KYYOK",
    "KOOOKgggKOOOK",
    ".KKK..g..KKK.",
    "...KKKgKKK...",
    "...KnnnnnK...",
    "....KggNK....",
    "....KggNK....",
    "..KnnnnnnNK..",
    "..KgggggNNK..",
    "..KKKKKKKKK..",
]
TROPHY_PLINTH_SHINE = [[], [(5, 5), (4, 13)], [(9, 1), (3, 16)], [(1, 9), (9, 9)]]

TROPHY_CROWN = [  # P3 final — coupe large, graphe de 3 nœuds (triangle, 3 arêtes) — 13 x 18
    ".KKK.....KKK.",
    "KYWOK...KYYOK",
    "KOOOKaaaKOOOK",
    ".KKKa...aKKK.",
    ".....a.a.....",
    ".....KKK.....",
    "....KYWOK....",
    "....KOOOK....",
    "KK...KKK...KK",
    "KaKKKKaKKKKaK",
    ".KaAAAAAAAaK.",
    "..KAWAAAAaK..",
    "...KAWAAaK...",
    "....KAAaK....",
    ".....KAK.....",
    "....KAAaK....",
    "...KAAAAaK...",
    "...KKKKKKK...",
]
TROPHY_CROWN_SHINE = [[], [(4, 11), (5, 12)], [(2, 1), (6, 6)], [(10, 1), (6, 7)]]


def trophy(c, x, y, rows, shine_pts):
    c.stamp(x, y, rows)
    for (i, j) in shine_pts:
        c.put((x + i, y + j), "W")


# ---------------------------------------------------------------- marteau, prises
def hold(c, pts, r0=1.4, r1=1.0):
    """Tentacule dessiné par-dessus un objet (prise)."""
    c.layer(shade(path(pts, r0, r1), "L", "B", None))


def wrap(c, grip):
    """Petite boucle de tentacule autour du manche, dessinée après le marteau."""
    c.layer(shade(disc(grip[0], grip[1], 1.0), "L", "B", None))


def embers(c, f, xs, y0, period=4):
    """Braises qui montent (souffle de chaleur)."""
    for k, x in enumerate(xs):
        y = y0 - ((f + k * 2) % period) * 2
        c.put((x + ((f + k) % 2), y), "O" if (f + k) % 3 else "E")


# ---------------------------------------------------------------- proposition 1 : « Frappe frontale »
# Krakie à gauche, enclume à droite ; marteau dans le tentacule droit, pince dans le gauche.
# Lecture : silhouette d'enclume pleine largeur, marteau en T, barre qui chauffe à blanc à l'impact.
P1_MS = [240, 150, 90, 70, 100, 120, 150, 200]
P1_HAM = [((25, 15), -90, 7), ((25, 15), -45, 6), ((26, 16), -135, 7), ((27, 18), 180, 7),
          ((27, 18), 180, 7), ((26, 16), -135, 7), ((25, 15), -90, 7), ((25, 14), -90, 7)]
P1_HEAT = [1, 1, 2, 3, 3, 2, 1, 1]


def p1_forge(f):
    c = Canvas()
    grip, ang, ln = P1_HAM[f]
    hit = f in (3, 4)
    draw_krakie(c, dx=-5, dy=-1, eyes="closed" if hit else ("happy" if f == 7 else "open"),
                mouth="open" if hit else "smile", rx=9.5, skip=("T7", "T6", "T1"),
                head_dy=1 if hit else 0)
    anvil(c, 13, 23)
    hot_bar(c, 17, 21, 6, P1_HEAT[f])
    embers(c, f, [19, 22], 19)
    # pince (tentacule gauche) qui tient la barre
    for p in line(12, 20, 17, 21):
        c.put(p, "N")
    hold(c, [(6, 15), (8, 19), (12, 20)])
    hold(c, [(17, 17), (23, 20), (27, 19)] if ang == 180 else [(17, 16), (21, 16), grip])
    hammer(c, grip, ang, length=ln)
    wrap(c, grip)
    if f >= 3:
        sparks(c, (20, 20), f - 3, n=7, spread=1.2, seed=f, arc=(-110, 20))
    if f == 3:
        star(c, 20, 19, big=True)
    return c


def p1_trophee(f):
    c = Canvas()
    draw_krakie(c, dx=-6, dy=1, eyes="happy", mouth="open", rx=9.5, scale=0.85, skip=("T6",),
                override={"T1": ([(6, 16), (3, 17), (1, 14), (1, 11)], 1.4, 0.9, "L")},
                head_dy=[0, 0, 1, 0][f])
    trophy(c, 19, 0 - (1 if f == 2 else 0), TROPHY_CUP, TROPHY_CUP_SHINE[f])
    hold(c, [(15, 17), (19, 22), (23, 22), (25, 21 - (1 if f == 2 else 0))])
    for k, (x, y) in enumerate([(2, 2), (31, 3), (16, 4), (30, 22)]):
        if (k + f) % 2 == 0:
            star(c, x, y)
    return c


# ---------------------------------------------------------------- proposition 2 : « L'atelier »
# Foyer de pierre à gauche (flammes + coups de soufflet), enclume au centre, Krakie à droite.
P2_MS = [200, 160, 90, 70, 100, 130, 160, 200]
P2_HAM = [((10, 15), -90, 7), ((10, 14), -90, 7), ((11, 16), -135, 7), ((20, 18), 180, 6),
          ((20, 18), 180, 6), ((11, 16), -135, 7), ((10, 15), -90, 7), ((10, 15), -90, 7)]
P2_HEAT = [2, 2, 2, 3, 3, 2, 2, 2]


def hearth(c, f):
    m = {}
    for x in range(0, 9):
        for y in range(19, 31):
            m[(x, y)] = "c"
    for x in range(1, 8):
        for y in range(24, 29):
            m[(x, y)] = "e"
        m[(x, 23)] = "N"
    c.layer(m)
    for y in (21, 30):
        for x in range(0, 9, 3):
            c.put((x, y), "K")
    for x in range(1, 8):
        c.put((x, 28), "E" if (x + f) % 3 else "O")
    fl = [
        ["..Y....", ".YOY.Y.", "OOEOOYO", "EEEEOEE"],
        ["....Y..", ".Y.YOY.", "OYOOOEO", "EEOEEEE"],
        [".Y..Y..", "YOY.OY.", "OOEOOOY", "EEEEEOE"],
        ["...Y...", "..YOY..", ".YOEOY.", "OOEEEOO"],
    ][f % 4]
    big = f in (0, 6, 7)  # coups de soufflet : flammes plus hautes, braises qui jaillissent
    c.stamp(1, 24 - (1 if big else 0), fl)
    if big:
        c.stamp(2, 22, ["Y.Y..", ".O.Y."])
    for k in range(3):  # fumée
        y = 17 - ((f + k * 3) % 8)
        if y > 10:
            c.put((3 + (k + (f // 2)) % 3, y), "g")


def p2_forge(f):
    c = Canvas()
    hearth(c, f)
    grip, ang, ln = P2_HAM[f]
    hit = f in (3, 4)
    draw_krakie(c, dx=6, dy=-1, eyes="closed" if hit else "open", mouth="open" if hit else "smile", rx=9.5,
                skip=("T7", "T1", "T2", "T3", "T4", "T5", "T6"), head_dy=1 if hit else 0)
    for t in ([(18, 17), (17, 22), (16, 28)], [(22, 17), (23, 22), (25, 27), (27, 29)],
              [(25, 16), (27, 21), (29, 24), (30, 22)]):
        c.layer(shade(path(t, 1.4, 0.8), "L", "B", None))
    anvil(c, 9, 23)
    hot_bar(c, 12, 21, 5, P2_HEAT[f])
    embers(c, f, [13, 16], 19)
    hold(c, [(14, 17), (12, 17), grip] if not hit else [(15, 17), (18, 19), grip])
    hammer(c, grip, ang, length=ln)
    wrap(c, grip)
    if f >= 3:
        sparks(c, (14, 20), f - 3, n=6, spread=1.1, seed=f + 3, arc=(-200, -80))
    if f == 3:
        star(c, 14, 19, big=True)
    return c


def p2_trophee(f):
    c = Canvas()
    hearth(c, [0, 1, 6, 3][f])
    draw_krakie(c, dx=6, dy=1, eyes="happy", mouth="open", rx=9.5, scale=0.85, skip=("T1",),
                override={"T6": ([(27, 16), (30, 15), (30, 12)], 1.4, 0.9, "L")},
                head_dy=[0, 1, 0, 1][f])
    trophy(c, 0, 0 - (1 if f == 1 else 0), TROPHY_PLINTH, TROPHY_PLINTH_SHINE[f])
    hold(c, [(15, 16), (12, 17), (10, 15), (9, 13)])
    for k, (x, y) in enumerate([(16, 2), (30, 3), (14, 9)]):
        if (k + f) % 2 == 0:
            star(c, x, y)
    return c


# ---------------------------------------------------------------- proposition 3 : « Deux marteaux »
# Emblème symétrique : Krakie derrière l'enclume frappe en alternance avec deux marteaux
# (une pieuvre a des bras à revendre) ; longue barre chauffée, braises au centre.
P3_MS = [130, 70, 110, 150, 130, 70, 110, 150]
# états d'un marteau : up (levé) / back (armé, vers l'extérieur) / hit ; droite = gauche décalée d'une demi-mesure
P3_L = ["back", "hit", "hit", "up", "up", "up", "up", "up"]
P3_R = [P3_L[(f + 4) % 8] for f in range(8)]
P3_HITS = (1, 5)
P3_POS_R = {"up": ((27, 14), -90, 7), "back": ((23, 15), None, 4), "hit": ((26, 18), 180, 6)}
P3_POS_L = {"up": ((4, 14), -90, 7), "back": ((8, 15), None, 4), "hit": ((5, 18), 0, 6)}


def p3_forge(f):
    c = Canvas()
    hit_now = f in P3_HITS
    draw_krakie(c, dy=-1, eyes="closed" if hit_now else "open", mouth="open", rx=9,
                skip=("T7", "T1", "T6", "T2", "T5"), head_dy=1 if hit_now else 0)
    anvil(c, 7, 23)
    heat = 3 if hit_now else (2 if f in (2, 6) else 1)
    hot_bar(c, 10, 21, 12, heat)
    for x in (10, 21):  # souffle : les extrémités de la barre crachent une braise à tour de rôle
        if (f + x) % 3 == 0:
            c.put((x - 1 if x == 10 else x + 1, 20 - f % 2), "O")
    for side, st, pos in (("L", P3_L[f], P3_POS_L), ("R", P3_R[f], P3_POS_R)):
        grip, ang, ln = pos[st]
        root = (9, 16) if side == "L" else (22, 16)
        hold(c, [root, ((root[0] + grip[0]) / 2, (root[1] + grip[1]) / 2 + 1), grip])
        if ang is None:
            hammer_diag(c, grip, 1 if side == "R" else -1, ln)
        else:
            hammer(c, grip, ang, length=ln)
        wrap(c, grip)
    for (age_f, o, arc) in ((P3_HITS[0], (12, 20), (-200, -110)), (P3_HITS[1], (19, 20), (-70, 20))):
        age = (f - age_f) % 8
        if age <= 2:
            sparks(c, o, age, n=6, spread=1.0, seed=f + age_f, arc=arc)
            if age == 0:
                star(c, o[0], o[1] - 1, big=True)
    return c


def p3_trophee(f):
    c = Canvas()
    wave = [[(26, 16), (29, 14), (30, 10), (29, 7)], [(26, 16), (29, 15), (31, 12), (31, 9)]][f % 2]
    draw_krakie(c, dx=5, dy=[2, 1, 0, 1][f], eyes="happy", mouth="open", rx=9.5, scale=[0.8, 0.9, 0.7, 0.9][f],
                skip=("T1",), override={"T6": (wave, 1.5, 0.9, "L")})
    lift = [0, 1, 2, 1][f]
    trophy(c, 0, 1 - lift, TROPHY_CROWN, TROPHY_CROWN_SHINE[f])
    hold(c, [(13, 17), (10, 20 - lift), (7, 19 - lift), (6, 17 - lift)])
    for k, (x, y) in enumerate([(15, 2), (26, 1), (1, 24), (13, 26)]):
        if (k + f) % 2 == 0:
            star(c, x, y)
    return c


PROPS = {
    "p1-frappe": {
        "title": "Proposition 1 — Frappe frontale",
        "forge": (p1_forge, P1_MS), "key": 3, "trophee": (p1_trophee, [260, 200, 260, 200]),
    },
    "p2-atelier": {
        "title": "Proposition 2 — L'atelier",
        "forge": (p2_forge, P2_MS), "key": 3, "trophee": (p2_trophee, [260, 220, 260, 220]),
    },
    "p3-deux-marteaux": {
        "title": "Proposition 3 — Deux marteaux",
        "forge": (p3_forge, P3_MS), "key": P3_HITS[0], "trophee": (p3_trophee, [260, 200, 260, 200]),
    },
}


# ---------------------------------------------------------------- JSON
def json_path(prop):
    return OUT / prop / f"krakie-{prop}.json"


def redraw():
    for prop, spec in PROPS.items():
        poses = {}
        for pose in ("forge", "trophee"):
            fn, ms = spec[pose]
            poses[pose] = {"frames": [{"ms": ms[f], "rows": fn(f).rows()} for f in range(len(ms))]}
        data = {"name": f"Krakie — {spec['title']}", "size": [W, H],
                "note": "L29 étape 1, proposition (non intégrée). Généré par design/krakie/forge_props.py --redraw, "
                        "retouchable à la main. ' ' = transparent ; palette = palette de base + palette de forge.",
                "palette": PALETTE, "poses": poses}
        p = json_path(prop)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def load(prop):
    return json.loads(json_path(prop).read_text(encoding="utf-8"))


# ---------------------------------------------------------------- rendus
def rgb(h):
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))


def to_img(rows, palette, scale=1, bg=None):
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0) if bg is None else bg + (255,))
    px = im.load()
    for y, r in enumerate(rows):
        for x, ch in enumerate(r):
            if ch != " ":
                px[x, y] = rgb(palette[ch]) + (255,)
    return im.resize((W * scale, H * scale), Image.NEAREST) if scale != 1 else im


def font(sz):
    for p in ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/dejavu/DejaVuSans.ttf"):
        if pathlib.Path(p).exists():
            return ImageFont.truetype(p, sz)
    return ImageFont.load_default()


def board(rows_list, labels, palette, scale, bg, fg, title=None, gap=None):
    gap = gap if gap is not None else max(8, scale * 3)
    fsz = 14 if scale >= 4 else 11
    lab_h = fsz + 8 if labels else 0
    top = (fsz + 18) if title else 6
    n = len(rows_list)
    w = gap + n * (W * scale + gap)
    h = top + H * scale + lab_h + gap
    im = Image.new("RGB", (w, h), bg)
    d = ImageDraw.Draw(im)
    if title:
        d.text((gap, 6), title, fill=fg, font=font(fsz + 2))
    for i, rows in enumerate(rows_list):
        x = gap + i * (W * scale + gap)
        im.paste(to_img(rows, palette, scale), (x, top), to_img(rows, palette, scale))
        if labels:
            d.text((x, top + H * scale + 4), labels[i], fill=fg, font=font(fsz))
    return im


def stack_full(parts):
    """Empile des (image, fond) en étendant chaque bande à la largeur max avec son propre fond."""
    w = max(p.width for p, _ in parts)
    out = Image.new("RGB", (w, sum(p.height for p, _ in parts)))
    y = 0
    for p, bg in parts:
        out.paste(Image.new("RGB", (w, p.height), bg), (0, y))
        out.paste(p, (0, y))
        y += p.height
    return out


def stack(images, bg, pad=0):
    w = max(i.width for i in images)
    h = sum(i.height for i in images) + pad * (len(images) - 1)
    out = Image.new("RGB", (w, h), bg)
    y = 0
    for i in images:
        out.paste(i, (0, y))
        y += i.height + pad
    return out


def gif(frames, palette, path_, scale=6, bg=BG_LIGHT, loops=1):
    ims, ds = [], []
    for _ in range(loops):
        for fr in frames:
            ims.append(to_img(fr["rows"], palette, scale, bg).convert("RGB").convert("P", palette=Image.ADAPTIVE))
            ds.append(fr["ms"])
    ims[0].save(path_, save_all=True, append_images=ims[1:], duration=ds, loop=0, disposal=2, optimize=False)


def render(prop):
    data = load(prop)
    pal = data["palette"]
    d = OUT / prop
    d.mkdir(parents=True, exist_ok=True)
    (d / "svg").mkdir(exist_ok=True)
    forge, troph = data["poses"]["forge"]["frames"], data["poses"]["trophee"]["frames"]
    for pose, frs in (("forge", forge), ("trophee", troph)):
        for n, fr in enumerate(frs, 1):
            assert len(fr["rows"]) == H and all(len(r) == W for r in fr["rows"]), (prop, pose, n)
            (d / "svg" / f"{pose}-{n}.svg").write_text(build.to_svg(pose, fr["rows"], pal), encoding="utf-8")
    rows = [fr["rows"] for fr in forge] + [fr["rows"] for fr in troph]
    labels = [f"forge {i + 1} · {fr['ms']} ms" for i, fr in enumerate(forge)] + \
             [f"trophée {i + 1} · {fr['ms']} ms" for i, fr in enumerate(troph)]
    title = data["name"]
    for name, bg, fg in (("planche-claire.png", BG_LIGHT, (40, 40, 40)), ("planche-sombre.png", BG_DARK, (220, 230, 235))):
        half = len(forge)
        top = board(rows[:half], labels[:half], pal, 8, bg, fg, title=title)
        bot = board(rows[half:], labels[half:], pal, 8, bg, fg)
        stack([top, bot], bg).save(d / name)
    # taille réelle ×1 et ×2, fond clair et sombre
    parts = []
    for bg, fg in ((BG_LIGHT, (40, 40, 40)), (BG_DARK, (220, 230, 235))):
        parts.append((board(rows, None, pal, 1, bg, fg, title=f"{title} — taille réelle ×1", gap=6), bg))
        parts.append((board(rows, None, pal, 2, bg, fg, title="×2", gap=8), bg))
    stack_full(parts).save(d / "taille-reelle.png")
    gif(forge, pal, d / "forge.gif")
    gif(troph, pal, d / "trophee.gif")
    gif(forge, pal, d / "forge-sombre.gif", bg=BG_DARK)
    seq = forge * 3 + troph * 3
    gif(seq, pal, d / "sequence.gif")
    return data




def comparatif(all_data):
    base = json.loads(build.JSON_PATH.read_text(encoding="utf-8"))
    contente = base["poses"]["contente"]
    rows, labels = [contente], ["contente (actuelle)"]
    for prop, data in all_data.items():
        rows += [data["poses"]["forge"]["frames"][0]["rows"], data["poses"]["forge"]["frames"][PROPS[prop]["key"]]["rows"],
                 data["poses"]["trophee"]["frames"][0]["rows"]]
        k = prop.split("-")[0].upper()
        labels += [f"{k} forge (levé)", f"{k} forge (frappe)", f"{k} trophée"]
    parts = []
    for bg, fg in ((BG_LIGHT, (40, 40, 40)), (BG_DARK, (220, 230, 235))):
        parts.append((board(rows, labels, PALETTE, 8, bg, fg,
                            title="L29 — Krakie forgeronne : 3 propositions face à « contente »"), bg))
        parts.append((board(rows, None, PALETTE, 2, bg, fg, title="×2"), bg))
        parts.append((board(rows, None, PALETTE, 1, bg, fg, title="×1", gap=12), bg))
    stack_full(parts).save(OUT / "planche.png")


FINAL = ROOT / "journal" / "L29" / "final"


def final(integrate):
    """Étape 2 : P3 retenue. Dessine, écrit la source finale, rend planches/GIF dans journal/L29/final/,
    et (integrate) fusionne forge + trophee dans krakie-32-anim.json / krakie-32.json."""
    spec = PROPS["p3-deux-marteaux"]
    poses = {}
    for pose in ("forge", "trophee"):
        fn, ms = spec[pose]
        poses[pose] = {"frames": [{"ms": ms[f], "rows": fn(f).rows()} for f in range(len(ms))]}
    FINAL.mkdir(parents=True, exist_ok=True)
    src = {"name": "Krakie forgeronne (P3 deux marteaux, final)", "size": [W, H], "palette": PALETTE, "poses": poses}
    (FINAL / "krakie-forge-trophee.json").write_text(json.dumps(src, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    forge, troph = poses["forge"]["frames"], poses["trophee"]["frames"]
    rows = [f["rows"] for f in forge] + [f["rows"] for f in troph]
    labels = [f"forge {i + 1} - {f['ms']} ms" for i, f in enumerate(forge)] + [f"trophee {i + 1} - {f['ms']} ms" for i, f in enumerate(troph)]
    for name, bg, fg in (("planche-x8-claire.png", BG_LIGHT, (40, 40, 40)), ("planche-x8-sombre.png", BG_DARK, (220, 230, 235))):
        top = board(rows[:8], labels[:8], PALETTE, 8, bg, fg, title=src["name"])
        bot = board(rows[8:], labels[8:], PALETTE, 8, bg, fg)
        stack([top, bot], bg).save(FINAL / name)
    parts = []
    for bg, fg in ((BG_LIGHT, (40, 40, 40)), (BG_DARK, (220, 230, 235))):
        parts.append((board(rows, None, PALETTE, 1, bg, fg, title="taille reelle x1", gap=6), bg))
        parts.append((board(rows, None, PALETTE, 2, bg, fg, title="x2", gap=8), bg))
    stack_full(parts).save(FINAL / "planche-x1-x2.png")
    gif(forge, PALETTE, FINAL / "forge.gif")
    gif(forge, PALETTE, FINAL / "forge-sombre.gif", bg=BG_DARK)
    gif(troph, PALETTE, FINAL / "trophee.gif")
    gif(forge * 3 + troph * 3, PALETTE, FINAL / "sequence.gif")
    if integrate:
        ap = build.ANIM_JSON
        data = json.loads(ap.read_text(encoding="utf-8"))
        data["palette"] = PALETTE
        data["poses"].update(poses)
        tmp = ap.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        os.replace(tmp, ap)
        sp = build.JSON_PATH
        st = json.loads(sp.read_text(encoding="utf-8"))
        st["palette"] = PALETTE
        st["poses"]["forge"] = forge[0]["rows"]
        st["poses"]["trophee"] = troph[0]["rows"]
        tmp = sp.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(st, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        os.replace(tmp, sp)
        build.main()  # JSON -> SVG statiques + anim + manifeste (sans --redraw)


def main():
    if "--final" in sys.argv or "--integrate" in sys.argv:
        final("--integrate" in sys.argv)
        return
    if "--redraw" in sys.argv:
        redraw()
    all_data = {p: render(p) for p in PROPS}
    comparatif(all_data)
    print("ok:", ", ".join(f"{p} forge×{len(d['poses']['forge']['frames'])} trophée×{len(d['poses']['trophee']['frames'])}"
                           for p, d in all_data.items()))


if __name__ == "__main__":
    main()
