"""Pose un identifiant explicite {#id} sur chaque titre des guides traduits (L33), sans changer le texte du titre.
L'identifiant est celui que docs.ts calculait depuis le titre français (même algorithme que backend/tests/test_help_map.py)."""
import re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend" / "tests"))
from test_help_map import slugify  # noqa: E402

GUIDE = Path(__file__).resolve().parents[1] / "docs" / "guide"
for name in sys.argv[1:]:
    p = GUIDE / name
    out, fence, seen = [], False, {}
    for line in p.read_text(encoding="utf-8").splitlines():
        if line.lstrip().startswith("```"):
            fence = not fence
        m = None if fence else re.match(r"^(#{1,6})\s+(.+?)\s*#*\s*$", line)
        if m and not re.search(r"\{#[\w-]+\}\s*$", m.group(2)):
            base = slugify(m.group(2)) or "section"
            n = seen.get(base, 0); seen[base] = n + 1
            line = f"{m.group(1)} {m.group(2)} {{#{base if n == 0 else f'{base}-{n + 1}'}}}"
        elif m:
            base = re.search(r"\{#([\w-]+)\}", m.group(2)).group(1); seen[base] = seen.get(base, 0) + 1
        out.append(line)
    p.write_text("\n".join(out) + "\n", encoding="utf-8")
