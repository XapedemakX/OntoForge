import pathlib

import pytest

from ontoforge.shacl.import_shapes import parse_shapes
from ontoforge.shacl.validate import ShaclReport, validate

ROOT = pathlib.Path(__file__).resolve().parents[2]
SH = "http://www.w3.org/ns/shacl#"
AM = "https://w3id.org/ontoforge/automaint#"

TRAP_EXPECTED = {
    ("veh_bad_vin", AM + "vin", "PatternConstraintComponent"),
    ("veh_no_model", AM + "ofModel", "MinCountConstraintComponent"),
    ("veh_bad_fuel", AM + "usesFuel", "InConstraintComponent"),
    ("veh_bad_owner", AM + "hasOwner", "OrConstraintComponent"),
    ("ro_bad_dates", AM + "openedAt", "LessThanConstraintComponent"),
    ("ro_no_op", AM + "includesOperation", "QualifiedMinCountConstraintComponent"),
    ("garage_empty", "^<" + AM + "worksAt>", "MinCountConstraintComponent"),
    ("reading_extra", AM + "note", "ClosedConstraintComponent"),
}


def _triples(r: ShaclReport):
    return {(x.focus.split("#")[-1], x.path, x.constraint.split("#")[-1]) for x in r.results}


@pytest.fixture(scope="module")
def trap():
    shapes, _ = parse_shapes((ROOT / "samples/trap/trap-shapes.ttl").read_text())
    return shapes, (ROOT / "samples/trap/trap-data.ttl").read_text()


def test_default_inference_is_none(trap):
    shapes, data = trap
    r = validate(data, shapes)
    assert r.inference == "none"


def test_trap_exact_eight_violations(trap):
    shapes, data = trap
    r = validate(data, shapes)
    assert r.conforms is False
    assert len(r.results) == 8
    assert _triples(r) == TRAP_EXPECTED
    assert all(x.severity == "Violation" for x in r.results)
    assert all(x.shape for x in r.results)


def test_automaint_four_violations():
    shapes, _ = parse_shapes((ROOT / "samples/automaint/automaint-shapes.ttl").read_text())
    r = validate((ROOT / "samples/automaint/automaint-data.ttl").read_text(), shapes)
    assert {x.focus.split("#")[-1] for x in r.results} == {"veh_bad_vin", "veh_no_model", "ro_no_garage", "tech_idle"}


def test_conforming_data():
    shapes, _ = parse_shapes((ROOT / "samples/automaint/automaint-shapes.ttl").read_text())
    r = validate("@prefix am: <https://w3id.org/ontoforge/automaint#> . am:b a am:Brand ; am:brandName 'X' .", shapes)
    assert r.conforms and r.results == [] and r.counts()["Violation"] == 0


def test_invalid_inputs_do_not_raise(trap):
    shapes, data = trap
    assert not validate("pas du rdf {{", shapes).conforms
    bad = validate(data, shapes, inference="magie")
    assert not bad.conforms and bad.warnings


def test_closed_with_rdfs_inference_still_reports(trap):
    # piège D11 × sh:closed : avec inférence + ontologie, des constats supplémentaires sont possibles
    shapes, data = trap
    r = validate(data, shapes, onto=__import__("rdflib").Graph().parse(ROOT / "samples/trap/trap.ttl"),
                 inference="rdfs")
    assert r.inference == "rdfs" and not r.conforms
    assert TRAP_EXPECTED <= _triples(r) or len(r.results) >= 8


def test_trap_with_project_ontology_still_eight(trap):
    """Non-régression recette it2 : l'ontologie du projet fournie à validate() ne doit pas faire valider ses
    propres individus (ro_2026_0001 / QualifiedMinCount) -> toujours 8 violations ; les shapes survivent à
    un aller-retour export/import."""
    from ontoforge.io.rdf_import import parse_ontology
    from ontoforge.shacl.export_shapes import serialize_shapes
    shapes, data = trap
    onto, _ = parse_ontology((ROOT / "samples/trap/trap.ttl").read_text(), None, "trap.ttl")
    assert len(validate(data, shapes, onto).results) == 8
    shapes2, _ = parse_shapes(serialize_shapes(shapes))
    assert _triples(validate(data, shapes2, onto)) == TRAP_EXPECTED
