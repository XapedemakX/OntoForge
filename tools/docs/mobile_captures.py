"""Réduit les captures téléphone du guide (docs/guide/img/{fr,en}/mobile-*.png) à 480 px de large, palette 128 couleurs, et les inscrit dans sizes.json.
Usage : python -I tools/docs/mobile_captures.py   (les autres images ne sont pas touchées)."""
import json
from pathlib import Path
from PIL import Image

root = Path("docs/guide/img")
sizes = json.loads((root / "sizes.json").read_text(encoding="utf-8"))
import os
for f in sorted(root.glob("*/mobile-*.png")):
    if os.environ.get("ONLY") and f.stem != "mobile-" + os.environ["ONLY"]: continue
    im = Image.open(f); im.load(); im = im.convert("RGB")
    if im.width > 480: im = im.resize((480, round(im.height * 480 / im.width)), Image.Resampling.LANCZOS)
    im.quantize(colors=128, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE).save(f, "PNG", optimize=True)
    sizes[f.relative_to(root).as_posix()] = [im.width, im.height]
    print(f, im.size, f.stat().st_size // 1024, "Ko")
(root / "sizes.json").write_text(json.dumps(dict(sorted(sizes.items())), indent=0, ensure_ascii=False) + "\n", encoding="utf-8")
