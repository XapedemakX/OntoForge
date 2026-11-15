"""L39-secu SEC-08 : le rendu Markdown du front (explication de l'assistant) n'émet aucun lien ni image actif dangereux.

Le test s'appuie sur frontend/tests/safe_markdown.test.mjs (node --test) ; ignoré si Node ou les dépendances du front sont absents.
"""
import shutil
import subprocess
from pathlib import Path

import pytest

FRONT = Path(__file__).resolve().parents[2] / "frontend"


@pytest.mark.skipif(shutil.which("node") is None or not (FRONT / "node_modules" / "marked").exists(), reason="Node ou frontend/node_modules absent")
def test_sec08_markdown_links_neutralised():
    r = subprocess.run(["node", "--test", "tests/safe_markdown.test.mjs"], cwd=FRONT, capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stdout[-1500:] + r.stderr[-500:]


def test_sec08_analysis_screen_uses_the_safe_renderer():
    src = (FRONT / "src" / "screens" / "Analysis.tsx").read_text(encoding="utf-8")
    assert "renderSafeMarkdown(exp)" in src and "marked.parse" not in src and "from 'marked'" not in src
