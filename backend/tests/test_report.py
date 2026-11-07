"""Rapport de transposition (targets/report.py)."""
import pathlib

import pytest

from ontoforge.mapping.engine import analyze
from ontoforge.targets.report import generate

ROOT = pathlib.Path(__file__).resolve().parents[2]
TRAP = ROOT / "samples" / "trap"
AM = "https://w3id.org/ontoforge/automaint#"


@pytest.fixture(scope="module")
def trap():
    from ontoforge.io.rdf_import import parse_ontology
    return parse_ontology((TRAP / "trap.ttl").read_text(encoding="utf-8"), filename="trap.ttl")[0]


@pytest.mark.parametrize("target", ["curiosity", "neo4j"])
def test_report_sections(trap, target):
    pg = analyze(trap, None, target, {f"C02:{AM}Vehicle": "multi_label"})
    files = generate(pg, trap)
    assert list(files) == ["rapport-transposition.md"]
    md = files["rapport-transposition.md"]
    for h in ("## Synthèse", "## Types de nœuds", "## Relations", "## Ce qui est perdu ou à risque",
              "## Transposé automatiquement", "## Validations à implémenter", "## Matérialisations"):
        assert h in md, h
    assert md.count("monde clos") >= 1 and md.count("Hypothèse de monde clos") == 1
    s = pg.summary()
    assert f"| Transposés automatiquement (auto) | {s['auto']} |" in md
    assert f"| Arbitrés / non arbitrés (review + lost) | {s['decided']} / {s['pending']} |" in md
    assert "non arbitré" in md
    lost = [f for f in pg.findings if f.severity == "lost"]
    for f in lost:
        assert f"| {f.rule} | " in md
    assert "`multi_label`" in md and "(non arbitré" in md
    for nt in pg.node_types:
        assert f"| {nt}" in md


def test_report_without_onto(trap):
    md = generate(analyze(trap, None, "curiosity"))["rapport-transposition.md"]
    assert md.startswith("# Rapport de transposition")
