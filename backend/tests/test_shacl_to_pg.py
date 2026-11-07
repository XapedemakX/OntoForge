import pathlib

from ontoforge.shacl.import_shapes import parse_shapes
from ontoforge.shacl.shacl_to_pg import hints, shape_constraints

ROOT = pathlib.Path(__file__).resolve().parents[2]
AM = "https://w3id.org/ontoforge/automaint#"


def _trap():
    return parse_shapes((ROOT / "samples/trap/trap-shapes.ttl").read_text())[0]


def test_structure_by_class():
    sc = shape_constraints(_trap())
    assert set(sc) >= {"classes"}
    veh = sc["classes"][AM + "Vehicle"]
    assert {"class", "shapes", "closed", "properties", "inverse_properties", "node", "complex_paths", "sparql"} <= set(veh)
    assert AM + "vin" in veh["properties"]


def test_closed_shape_and_inverse_path():
    sc = shape_constraints(_trap())["classes"]
    assert sc[AM + "MileageReading"]["closed"] is True
    assert AM + "worksAt" in sc[AM + "Garage"]["inverse_properties"]


def test_hints_flatten_required_and_cardinality():
    hs = {(h.target_class, h.property, h.inverse): h for h in hints(_trap())}
    vin = hs[(AM + "Vehicle", AM + "vin", False)]
    assert vin.required and vin.pattern
    assert hs[(AM + "Garage", AM + "worksAt", True)].min_count == 1
