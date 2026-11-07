from ontoforge.core.onto_model import XSD
from ontoforge.io.dsl import DSL_EXAMPLE, DSL_HELP, parse_dsl
from ontoforge.io.rdf_export import serialize
from ontoforge.io.rdf_import import parse_ontology

AM = "https://w3id.org/ontoforge/automaint#"


def test_example_in_help_parses_cleanly():
    m, errs = parse_dsl(DSL_EXAMPLE)
    assert errs == [] and DSL_EXAMPLE in DSL_HELP
    v = m.classes[AM + "Vehicle"]
    assert v.labels == {"fr": "Véhicule", "en": "Vehicle"}
    assert AM + "LowEmissionAsset" in m.classes  # classe citée créée
    assert [AM + "vin"] in v.has_keys
    assert any(r.property == AM + "vin" and r.kind == "exactly" and r.n == 1 for r in v.restrictions)
    assert m.datatype_properties[AM + "vin"].range == [XSD + "string"]
    assert m.object_properties[AM + "concerns"].inverse_of == AM + "hasRepairOrder"
    assert "transitive" in m.object_properties[AM + "partOf"].characteristics
    assert m.classes[AM + "FuelType"].one_of == [AM + "Diesel", AM + "Petrol", AM + "Electric"]
    assert AM + "Garage" in m.individuals[AM + "garage42"].types


def test_errors_by_line_never_raise_and_good_lines_kept():
    m, errs = parse_dsl("A < B\nA.x : string [bad]\nfoo bar baz\nzz:C < A\nB -p-> C inverse\nC.k : int transitive\nD")
    assert [e["line"] for e in errs] == [2, 3, 4, 5, 6]
    assert all(set(e) == {"line", "message"} for e in errs)
    assert any("A" == i.rsplit("#", 1)[1] for i in m.classes) and any(i.endswith("#D") for i in m.classes)


def test_comments_blank_and_hash_in_iri():
    m, errs = parse_dsl('# titre\n\nX "a # b"@en   # fin\n<https://e.org/o#Y> < X')
    assert errs == [] and list(m.classes.values())[0].labels["en"] == "a # b"
    assert "https://e.org/o#Y" in m.classes


def test_merge_with_base_and_union_domain():
    base, _ = parse_dsl("@base <https://e.org/o#>\nA\nA.n : string")
    m, errs = parse_dsl("@base <https://e.org/o#>\nB.n : string", base)
    assert errs == [] and sorted(m.datatype_properties["https://e.org/o#n"].domain_union) == ["https://e.org/o#A", "https://e.org/o#B"]
    assert m.datatype_properties["https://e.org/o#n"].domain == []


def test_cardinalities():
    m, _ = parse_dsl("@base <https://e.org/o#>\nA -p-> B [1..*]\nA -q-> B [0..1]\nA -r-> B [2..5]\nA -s-> B [*]")
    rs = {(r.property.rsplit('#', 1)[1], r.kind, r.n) for r in m.classes["https://e.org/o#A"].restrictions}
    assert rs == {("p", "min", 1), ("q", "max", 1), ("r", "min", 2), ("r", "max", 5)}


def test_quickstart_dsl_matches_automaint():
    from pathlib import Path
    root = Path(__file__).resolve().parents[2] / "samples" / "automaint"
    m, errs = parse_dsl((root / "quickstart.dsl").read_text())
    assert errs == []
    full, _ = parse_ontology((root / "automaint.ttl").read_text(), filename="x.ttl")
    assert set(m.classes) == set(full.classes)
    assert set(m.object_properties) == set(full.object_properties)
    assert set(m.datatype_properties) == set(full.datatype_properties)
    parse_ontology(serialize(m), "turtle")
