#!/usr/bin/env python3
"""L30 : poses de nage et expressions de Krakie pour le jeu « Krakie's Triple Catch ».

AJOUT SEUL : ce script lit krakie-32-anim.json, y ajoute (ou remplace) uniquement les poses « nage* », écrit leurs
frames SVG dans frontend/public/krakie/anim/ et fusionne leurs durées dans manifest.json. Les autres poses (dont
forge et trophee de L29) ne sont jamais touchées. N'appelle jamais build.py --redraw ni --redraw-anim.

Usage :  python design/krakie/game_poses.py            # régénère les poses nage* (idempotent)
         python design/krakie/game_poses.py --sheet F  # + planche de contrôle PNG (x6) dans le fichier F

Poses (6 frames chacune, 32x32, même palette et même contour que le reste de Krakie) :
  nage          neutre : tentacules en onde, léger rebond, clignement
  nage_clin     clin d'œil (élément attrapé)
  nage_ravie    grand sourire + étincelles (triplet complet)
  nage_surprise yeux ronds, bouche en O, traits de surprise (bonus)
  nage_grimace  yeux serrés > <, bouche ondulée (constat perdu, IRI cassée)
  nage_inquiete sourcils inquiets, goutte de sueur (une seule vie)
Toutes sont dessinées de face ; l'inclinaison dans le sens du déplacement est un cisaillement par rangées fait par le moteur.
"""
import json
import math
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import build  # noqa: E402
from build import Canvas, draw_krakie, tentacles, W, H  # noqa: E402

N = 6
MS = [95, 95, 95, 95, 95, 95]
LABELS = {
    "nage": "nage (jeu)", "nage_clin": "nage et fait un clin d'œil (jeu)", "nage_ravie": "nage ravie, étincelles (jeu)",
    "nage_surprise": "nage, surprise (jeu)", "nage_grimace": "nage, grimace (jeu)", "nage_inquiete": "nage, inquiète (jeu)",
}

build.MOUTHS["grin"] = ["KKKKK", "KmmmK", ".KmK.", "..K.."]
build.MOUTHS["tiny_o"] = [".KK.", "K..K", ".KK."]
EYE_L_SQUEEZE = ["KK..", ".KK.", "..KK", ".KK.", "KK.."]   # >
EYE_R_SQUEEZE = ["..KK", ".KK.", "KK..", ".KK.", "..KK"]   # <
EYE_ROUND = [".KK.", "KWWK", "KWKK", "KWWK", ".KK."]
EYE_ARC = ["....", ".KK.", "K..K", "....", "...."]          # ^ (joie)
EYE_WINK = ["....", "....", "KKKK", "....", "...."]          # trait (œil fermé)
SPARK = [".Y.", "YWY", ".Y."]


def swim_override(f, amp=3.2):
    """Onde progressive : chaque tentacule a sa phase, la base est fixe, la pointe oscille le plus."""
    base = tentacles()
    order = ["T1", "T2", "T3", "T7", "T4", "T5", "T6"]
    out = {}
    for i, k in enumerate(order):
        pts, r0, r1, col = base[k]
        ph = 2 * math.pi * f / N - i * 0.85
        new = []
        for x, y in pts:
            t = max(0.0, (y - 17) / 12)          # 0 à la base, 1 à la pointe
            new.append((x + amp * math.sin(ph) * t ** 1.3, y - 0.6 * math.cos(ph) * t))
        out[k] = (new, r0, r1, col)
    return out


def face(c, dx, dy, left, right, ey_shift=0):
    """Remplace les deux yeux : efface le rectangle 4x5 puis estampille left / right."""
    cx, cy = 15.5 + dx, 9.5 + dy
    exl, exr, ey = round(cx - 6.5), round(cx + 3.5), round(cy - 0.5) + ey_shift
    for ex in (exl, exr):
        for i in range(4):
            for j in range(5):
                c.put((ex + i, ey + j), "L")
    c.stamp(exl, ey, left)
    c.stamp(exr, ey, right)
    return exl, exr, ey


BOB = [0, -1, -1, 0, 1, 1]


def base(f, mouth="smile", eyes="open", brows=None, cheeks=True, bob=True, amp=3.2, **kw):
    c = Canvas()
    dy = BOB[f] if bob else 0
    draw_krakie(c, dy=dy, eyes=eyes, mouth=mouth, brows=brows, cheeks=cheeks, override=swim_override(f, amp), **kw)
    return c, dy


def spark(c, x, y, big=True):
    if big:
        c.stamp(x - 1, y - 1, SPARK)
    else:
        c.put((x, y), "Y")


def p_nage(f):
    c, dy = base(f, blink=(f == 4))
    return c


def p_nage_clin(f):
    c, dy = base(f, mouth="smile")
    face(c, 0, dy, EYE_WINK if f in (1, 2, 3) else EYE_ARC, build.EYES["open"])
    if f in (1, 2):
        spark(c, 5, 7 + dy)
    return c


def p_nage_ravie(f):
    c, dy = base(f, mouth="grin", eyes="happy")
    face(c, 0, dy, EYE_ARC, EYE_ARC)
    pos = [[(3, 3), (28, 6), (26, 1)], [(5, 1), (29, 3), (2, 8)], [(2, 5), (28, 1), (30, 9)],
           [(4, 2), (27, 5), (29, 12)], [(3, 6), (26, 2), (1, 2)], [(6, 2), (29, 7), (28, 1)]][f]
    for k, (x, y) in enumerate(pos):
        spark(c, x, y, big=(k + f) % 3 != 2)
    return c


def p_nage_surprise(f):
    c, dy = base(f, mouth="tiny_o", brows="raised", amp=1.6, bob=False)
    face(c, 0, dy, EYE_ROUND, EYE_ROUND)
    for (x, y) in [(2, 5), (3, 3), (5, 1), (29, 5), (28, 3), (26, 1)]:
        c.put((x, y), "Y")
    if f % 2 == 0:
        for (x, y) in [(1, 7), (30, 7)]:
            c.put((x, y), "Y")
    return c


def p_nage_grimace(f):
    c, dy = base(f, mouth="wavy", cheeks=False, amp=1.2, bob=False)
    face(c, 0, dy, EYE_L_SQUEEZE, EYE_R_SQUEEZE)
    for (x, y) in [(3, 5), (28, 4)] if f % 2 == 0 else [(2, 7), (29, 7)]:
        c.put((x, y), "O")
        c.put((x + 1, y - 1), "Y")
    return c


def p_nage_inquiete(f):
    c, dy = base(f, mouth="wavy", eyes="small", brows="worried", amp=1.4, bob=False)
    x, y = [(27, 2), (28, 6), (29, 10), (29, 15), (27, 2), (27, 3)][f]
    drop = {(x, y): "S", (x - 1, y + 1): "S", (x, y + 1): "S", (x + 1, y + 1): "S", (x - 1, y + 2): "W",
            (x, y + 2): "S", (x + 1, y + 2): "S", (x, y + 3): "S"}
    c.layer(drop)
    return c


POSES = {"nage": p_nage, "nage_clin": p_nage_clin, "nage_ravie": p_nage_ravie, "nage_surprise": p_nage_surprise,
         "nage_grimace": p_nage_grimace, "nage_inquiete": p_nage_inquiete}
POSE_MS = {"nage_inquiete": [130] * 6, "nage_surprise": [110] * 6, "nage_grimace": [70] * 6}


def main():
    anim_json = build.ANIM_JSON
    data = json.loads(anim_json.read_text(encoding="utf-8"))
    for k, v in {"Y": "#FFE27A", "O": "#F5861F", "S": "#9AD7F0"}.items():
        assert data["palette"].get(k) == v, k
    out_dir = build.ANIM_DIR
    manifest_path = out_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    sheets = {}
    for name, fn in POSES.items():
        ms = POSE_MS.get(name, MS)
        frames = []
        for f in range(N):
            rows = fn(f).rows()
            assert len(rows) == H and all(len(r) == W for r in rows), (name, f)
            frames.append({"ms": ms[f], "rows": rows})
        data["poses"][name] = {"frames": frames}
        build.LABELS[name] = LABELS[name]
        for n, fr in enumerate(frames, start=1):
            (out_dir / f"{name}-{n}.svg").write_text(build.to_svg(name, fr["rows"], data["palette"]), encoding="utf-8")
        manifest[name] = ms
        sheets[name] = frames
    anim_json.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    manifest_path.write_text(json.dumps(manifest) + "\n", encoding="utf-8")
    print("nage ok:", ", ".join(POSES))
    if "--sheet" in sys.argv:
        sheet(data, sheets, sys.argv[sys.argv.index("--sheet") + 1])


def sheet(data, sheets, path, s=6):
    from PIL import Image
    pal = {k: tuple(int(v[i:i + 2], 16) for i in (1, 3, 5)) for k, v in data["palette"].items()}
    img = Image.new("RGB", (N * 34 * s, len(sheets) * 34 * s), (16, 56, 62))
    for r, (name, frames) in enumerate(sheets.items()):
        for f, fr in enumerate(frames):
            for y, row in enumerate(fr["rows"]):
                for x, ch in enumerate(row):
                    if ch != " ":
                        for i in range(s):
                            for j in range(s):
                                img.putpixel((f * 34 * s + x * s + i, r * 34 * s + y * s + j), pal[ch])
    img.save(path)


if __name__ == "__main__":
    main()
