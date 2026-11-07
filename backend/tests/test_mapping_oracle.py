"""Oracle L3 : samples/trap/expected-findings.yaml (findings + must_not), pour Curiosity et Neo4j."""
import pathlib

import pytest
import yaml

ROOT = pathlib.Path(__file__).resolve().parents[2]
TRAP = ROOT / "samples" / "trap"
AM = "https://w3id.org/ontoforge/automaint#"
ORACLE = yaml.safe_load((TRAP / "expected-findings.yaml").read_text(encoding="utf-8"))
TARGETS = ["curiosity", "neo4j"]


def _iri(s: str) -> str:
    return AM + s[3:] if s.startswith("am:") else s


@pytest.fixture(scope="module")
def onto():
    from ontoforge.io.rdf_import import parse_ontology
    m, _ = parse_ontology((TRAP / "trap.ttl").read_text(encoding="utf-8"), filename="trap.ttl")
    return m


@pytest.fixture(scope="module")
def shapes():
    try:
        from ontoforge.shacl.import_shapes import parse_shapes
    except Exception:  # pragma: no cover - module shacl absent
        return None
    s, _ = parse_shapes((TRAP / "trap-shapes.ttl").read_text(encoding="utf-8"), filename="trap-shapes.ttl")
    return s


@pytest.fixture(scope="module")
def pgs(onto, shapes):
    from ontoforge.mapping.engine import analyze
    return {t: analyze(onto, shapes, t) for t in TARGETS}


@pytest.mark.parametrize("target", TARGETS)
@pytest.mark.parametrize("entry", ORACLE["findings"], ids=[e["id"] for e in ORACLE["findings"]])
def test_expected(pgs, target, entry):
    pg = pgs[target]
    subj = _iri(entry["subject"])
    cands = [f for f in pg.findings if f.rule == entry["rule"] and f.subject == subj]
    if entry[target].get("absent"):  # L13 : constat volontairement absent pour cette cible
        assert not cands, [f.id for f in cands]
        return
    assert cands, f"aucun {entry['rule']} sur {subj}"
    sev = entry[target].get("severity", entry["severity"])
    assert any(f.severity == sev for f in cands), [f.severity for f in cands]
    want = entry[target]["recommended"]
    ok = [f for f in cands if f.severity == sev and f.recommended == want]
    assert ok, f"{entry['rule']} {subj} [{target}] : recommandé {[f.recommended for f in cands]} ≠ {want}"
    f = ok[0]
    assert f.options and f.rationale and want in {o.id for o in f.options}


@pytest.mark.parametrize("target", TARGETS)
@pytest.mark.parametrize("entry", ORACLE["must_not"], ids=[f"{e['rule']}-{e.get('subject', '*')}" for e in ORACLE["must_not"]])
def test_must_not(pgs, target, entry):
    for f in pgs[target].findings:
        if f.rule != entry["rule"]:
            continue
        if "subject" in entry and f.subject != _iri(entry["subject"]):
            continue
        if "severity" in entry and f.severity != entry["severity"]:
            continue
        if "bnode" in entry and not f.id.count(":") > 2:
            continue
        pytest.fail(f"constat interdit : {f.id} ({entry['why']})")


@pytest.mark.parametrize("target", TARGETS)
def test_no_silent_loss(pgs, onto, target):
    pg = pgs[target]
    seen = set()
    for f in pg.findings:
        seen.add(f.subject)
        seen |= set(f.related)
    for nt in pg.node_types.values():
        seen |= set(nt.source) | {p.source for p in nt.properties}
    for e in pg.edge_types:
        seen.add(e.source)
        seen |= {p.source for p in e.properties}
    ents = set(onto.classes) | set(onto.object_properties) | set(onto.datatype_properties) | set(onto.individuals)
    missing = sorted(e for e in ents if e.startswith(AM) and e not in seen)
    assert not missing
    # chaque entrée non mappée produit un constat (règle dédiée ou G01)
    assert len(onto.unmapped) > 0
    assert any(f.rule == "G01" for f in pg.findings)


def test_coverage_100(pgs):
    """Couverture de l'oracle (affichée) : doit être de 100 % pour les deux cibles."""
    for t in TARGETS:
        pg = pgs[t]
        ok = 0
        for e in ORACLE["findings"]:
            subj = _iri(e["subject"])
            if e[t].get("absent"):
                ok += not any(f.rule == e["rule"] and f.subject == subj for f in pg.findings)
                continue
            if any(f.rule == e["rule"] and f.subject == subj and f.severity == e[t].get("severity", e["severity"])
                   and f.recommended == e[t]["recommended"] for f in pg.findings):
                ok += 1
        assert ok == len(ORACLE["findings"]), f"{t}: {ok}/{len(ORACLE['findings'])}"
