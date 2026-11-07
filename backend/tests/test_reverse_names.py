"""L13 : noms de reverse lisibles quand aucun owl:inverseOf n'existe."""
import pytest

from ontoforge.mapping.reverse_names import derive_reverse, uniquify_reverses
from ontoforge.core.pg_model import EdgeType


@pytest.mark.parametrize("edge,src,want", [
    ("HasPart", "A", "PartOf"), ("IsPartOf", "A", "HasPart"), ("PartOf", "A", "HasPart"),
    ("Covers", "Warranty", "CoveredBy"), ("UsesPart", "Op", "UsedBy"), ("Prescribes", "P", "PrescribedBy"),
    ("Addresses", "Op", "AddressedBy"), ("Applies", "X", "AppliedBy"),
    ("OwnedBy", "Vehicle", "HasVehicle"), ("AssignedTo", "RepairOrder", "HasRepairOrder"),
    ("WorksAt", "Technician", "HasTechnician"), ("MadeBy", "Model", "HasModel"), ("OfModel", "Vehicle", "HasVehicle"),
    ("PartOfTransitive", "Part", "HasPartTransitive"),
    ("ClaimGarage", "Claim", "ClaimGarageOfClaim"),
])
def test_derive(edge, src, want):
    assert derive_reverse(edge, src) == want


def test_no_inverse_suffix_and_no_collision():
    es = [EdgeType(name="CheckedBy", from_="RO", to="Person", reverse="CheckedByInverse"),
          EdgeType(name="PerformedBy", from_="RO", to="Person", reverse="PerformedByInverse"),
          EdgeType(name="UsesFuel", from_="V", to="Fuel", reverse="UsesFuelInverse"),
          EdgeType(name="Owns", from_="Person", to="Person", reverse="OwnedBy")]
    uniquify_reverses(es, is_default=lambda e: e.reverse == f"{e.name}Inverse")
    revs = [(e.to, e.reverse) for e in es]
    assert len(set(revs)) == len(revs)
    assert all("Inverse" not in r for _, r in revs)
    assert es[0].reverse == "HasRO" and es[1].reverse == "PerformedByOfRO"
    assert es[2].reverse == "UsedBy"


def test_engine_automaint_readable():
    from ontoforge.io.rdf_import import parse_ontology
    from ontoforge.mapping.engine import analyze
    import pathlib
    p = pathlib.Path(__file__).resolve().parents[2] / "samples" / "automaint" / "automaint.ttl"
    m, _ = parse_ontology(p.read_text(encoding="utf-8"), filename=p.name)
    pg = analyze(m, None, "curiosity")
    assert not [e for e in pg.edge_types if e.reverse.endswith("Inverse")]


def test_derived_never_usurps_owl_property_name():
    es = [EdgeType(name="AssignedTo", from_="RepairOrder", to="Tech", reverse="AssignedToInverse")]
    uniquify_reverses(es, is_default=lambda e: e.reverse == f"{e.name}Inverse", reserved=["hasRepairOrder"])
    assert es[0].reverse == "AssignedToOfRepairOrder"


def _derived(name, ttl):
    import pathlib
    from ontoforge.io.rdf_import import parse_ontology
    from ontoforge.mapping.engine import analyze
    p = pathlib.Path(__file__).resolve().parents[2] / "samples" / name / ttl
    m, _ = parse_ontology(p.read_text(encoding="utf-8"), filename=p.name)
    pg = analyze(m, None, "curiosity")
    props = {u.split("#")[-1].lower() for u in list(m.object_properties) + list(m.datatype_properties)}
    return pg, props


def test_automaint_trap_no_usurped_names():
    for name, ttl in (("automaint", "automaint.ttl"), ("trap", "trap.ttl")):
        pg, props = _derived(name, ttl)
        from ontoforge.core.onto_model import local_name
        m_inv = {}
        import pathlib
        from ontoforge.io.rdf_import import parse_ontology
        p = pathlib.Path(__file__).resolve().parents[2] / "samples" / name / ttl
        m, _ = parse_ontology(p.read_text(encoding="utf-8"), filename=p.name)
        for u, op in m.object_properties.items():
            m_inv[local_name(u).lower()] = {local_name(i).lower() for i in ([op.inverse_of] if isinstance(op.inverse_of, str) else (op.inverse_of or []))}
        for e in pg.edge_types:
            r = e.reverse.lower()
            if r in props and not e.symmetric and r != e.name.lower():  # admis seulement si c'est l'inverse déclaré de l'arête
                src = local_name(e.source or e.name).lower()
                assert src in m_inv.get(r, set()) or r in m_inv.get(src, set()), (name, e.name, e.reverse)
    pg, _ = _derived("trap", "trap.ttl")
    r = {(e.name, e.to): e.reverse for e in pg.edge_types}
    assert r[("InstanceOfReference", "PartReference")] != "HasPart"
    assert r[("PerformedAt", "Garage")] != "HasRepairOrder"
