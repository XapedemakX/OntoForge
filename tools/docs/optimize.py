"""Optimise les captures de la documentation (docs/guide/img/**/*.png).
Largeur maximale 1280 px, PNG compressé : pngquant s'il est installé, sinon Pillow (palette 128 couleurs, repli à 64 puis 32
si l'image dépasse 150 Ko). Usage : python -I tools/docs/optimize.py docs/guide/img"""
import io, json, shutil, subprocess, sys
from pathlib import Path
from PIL import Image

MAX_W, BUDGET = 1280, 100 * 1024  # cible par image ; plafond dur 150 Ko
root = Path(sys.argv[1] if len(sys.argv) > 1 else "docs/guide/img")
PNGQUANT = shutil.which("pngquant")


def encode(im: Image.Image, colors: int) -> bytes:
    q = im.quantize(colors=colors, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    buf = io.BytesIO(); q.save(buf, "PNG", optimize=True); return buf.getvalue()


total = n = 0
sizes = {}
for f in sorted(root.rglob("*.png")):
    im = Image.open(f); im.load()
    if im.mode != "RGB": im = im.convert("RGB")
    if im.width > MAX_W: im = im.resize((MAX_W, round(im.height * MAX_W / im.width)), Image.Resampling.LANCZOS)
    if PNGQUANT:
        buf = io.BytesIO(); im.save(buf, "PNG"); r = subprocess.run([PNGQUANT, "--quality", "70-95", "--speed", "1", "-"], input=buf.getvalue(), capture_output=True)
        data = r.stdout if r.returncode == 0 and r.stdout else buf.getvalue()
    else:
        data = encode(im, 128)
        for c in (64, 32):
            if len(data) <= BUDGET: break
            data = encode(im, c)
    f.write_bytes(data); total += len(data); n += 1
    sizes[f.relative_to(root).as_posix()] = [im.width, im.height]
big = [p for p in root.rglob("*.png") if p.stat().st_size > 150 * 1024]
print(f"optimisation : {n} images, {total / 1048576:.2f} Mo au total, {len(big)} au-dessus de 150 Ko" + ("".join(f"\n  {p.relative_to(root)} {p.stat().st_size // 1024} Ko" for p in big)))
# dimensions des images : le front les pose en attributs width/height (pas de saut de mise en page au chargement paresseux)
(root / "sizes.json").write_text(json.dumps(dict(sorted(sizes.items())), indent=0, ensure_ascii=False) + "\n", encoding="utf-8")
