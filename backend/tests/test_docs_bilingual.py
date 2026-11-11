"""L34a : chaque guide docs/guide/X.md a une version X.en.md avec les mêmes ancres {#id} et le même nombre de titres par niveau."""
import re
from collections import Counter
from pathlib import Path

import pytest

from test_help_map import anchors

GUIDE = Path(__file__).resolve().parents[2] / "docs" / "guide"

# Temporaire (L34a) : d'autres agents rédigent encore ces deux traductions. Retirer chaque nom de cette liste
# dès que sa version .en.md est livrée : le test devient alors bloquant pour lui.
EXPECTED_MISSING = {"regles", "utilisateur"}

FR = sorted(p for p in GUIDE.glob("*.md") if not p.name.endswith(".en.md"))


def heading_levels(md: str) -> Counter:
    levels: Counter = Counter()
    fence = False
    for line in md.splitlines():
        if line.lstrip().startswith("```"):
            fence = not fence
            continue
        m = None if fence else re.match(r"^(#{1,6})\s+\S", line)
        if m:
            levels[len(m.group(1))] += 1
    return levels


@pytest.mark.parametrize("fr", FR, ids=lambda p: p.stem)
def test_guide_has_matching_english_version(fr: Path):
    en = fr.with_name(fr.stem + ".en.md")
    if fr.stem in EXPECTED_MISSING:
        try:
            _check(fr, en)
        except AssertionError as e:
            pytest.xfail(f"{en.name} attendu (autre agent en cours) : {e}")
        return
    _check(fr, en)


def _check(fr: Path, en: Path):
    assert en.exists(), f"{en.name} manquant"
    fr_md, en_md = fr.read_text(encoding="utf-8"), en.read_text(encoding="utf-8")
    fr_ids, en_ids = list(anchors(fr_md)), list(anchors(en_md))
    assert fr_ids == en_ids, f"ancres différentes : {sorted(set(fr_ids) ^ set(en_ids))}"
    assert heading_levels(fr_md) == heading_levels(en_md), f"{heading_levels(fr_md)} != {heading_levels(en_md)}"
