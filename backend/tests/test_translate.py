import glob
import json
import os

import pytest

from ontoforge.core.onto_model import OntoModel
from ontoforge.core.pg_model import PGModel
from ontoforge.queries.competency import competency_questions
from ontoforge.queries.translate import translate

FX = os.path.join(os.path.dirname(__file__), "fixtures", "queries")


@pytest.fixture(scope="module")
def pg():
    return PGModel.model_validate(json.load(open(os.path.join(FX, "pg_automaint.json"))))


@pytest.fixture(scope="module")
def onto():
    return OntoModel.model_validate(json.load(open(os.path.join(FX, "onto_automaint.json"))))


def q(name):
    return open(os.path.join(FX, name + ".sparql")).read()


def test_ten_fixtures_never_raise(pg, onto):
    files = sorted(glob.glob(os.path.join(FX, "*.sparql")))
    assert len(files) == 10
    for f in files:
        r = translate(open(f).read(), pg, onto)
        assert r.sparql
        assert isinstance(r.notes, list)


def test_basic_select_order_limit(pg):
    r = translate(q("q01_vehicles"), pg)
    assert "MATCH (v:Vehicle)" in r.cypher and "v.registrationNumber AS reg" in r.cypher
    assert "ORDER BY reg" in r.cypher and "LIMIT 20" in r.cypher
    assert not r.lossy
    assert "Q().StartAt(N.Vehicle.Type)" in r.curiosity and "À VÉRIFIER" in r.curiosity


def test_discriminant_and_filter(pg):
    r = translate(q("q02_electric"), pg)
    assert "v.vehicleKind = 'ElectricVehicle'" in r.cypher and "v.vin <> 'X'" in r.cypher
    assert not r.lossy


def test_object_and_data_properties(pg):
    r = translate(q("q03_vehicle_owner"), pg)
    assert "(v:Vehicle)-[:OWNED_BY]->(c:Customer)" in r.cypher
    assert "c.displayName AS name" in r.cypher and not r.lossy


def test_optional(pg):
    r = translate(q("q04_optional"), pg)
    assert "OPTIONAL MATCH (o)-[:PERFORMED_AT]->(g:Garage)" in r.cypher
    assert r.graphql and "performedAt" in r.graphql  # lecture simple -> GraphQL


def test_transitive_path(pg):
    r = translate(q("q05_subparts"), pg)
    assert "[:PART_OF*1..]" in r.cypher and "manufacturerPartNumber = 'MPN-001'" in r.cypher
    assert "OutMany" in r.curiosity


def test_aggregate_group_by(pg, onto):
    r = translate(q("q06_count_orders"), pg, onto)
    assert "count(o) AS n" in r.cypher and "ORDER BY n DESC" in r.cypher


def test_regex(pg):
    r = translate(q("q07_filter_regex"), pg)
    assert "=~" in r.cypher


def test_inverse_path(pg):
    r = translate(q("q08_inverse_path"), pg)
    assert "(g:Garage)<-[:PERFORMED_AT]-(o:RepairOrder)" in r.cypher


def test_recalls_join(pg):
    r = translate(q("q09_recalls"), pg)
    assert "APPLIES_TO_MODEL" in r.cypher and "OF_MODEL" in r.cypher and not r.lossy


def test_inverseof_with_onto_is_traversal_not_loss(pg, onto):
    sp = "PREFIX am: <https://w3id.org/ontoforge/automaint#> SELECT ?o ?v WHERE { ?o am:concerns ?v }"
    r = translate(sp, pg, onto)
    assert "<-[:HAS_REPAIR_ORDER]-" in r.cypher and not r.lossy
    assert translate(sp, pg).lossy  # sans ontologie, l'inverse n'est pas connu


A = "PREFIX am: <https://w3id.org/ontoforge/automaint#> "


def test_unknown_class_never_untyped_superset(pg):
    r = translate(A + "SELECT ?x WHERE { ?x a am:Warrantyx }", pg)  # classe inconnue de tout
    r2 = translate(A + "SELECT ?x WHERE { ?x a am:Party }", pg)  # classe absente du PG, sans ontologie
    for res in (r, r2):
        assert res.lossy and any("[perte]" in n for n in res.notes)
        assert res.cypher is None or "WHERE false" in res.cypher


def test_two_discriminant_types_lossy(pg):
    r = translate(A + "SELECT ?x WHERE { ?x a am:ElectricVehicle . ?x a am:CombustionVehicle }", pg)
    assert r.lossy and "false" in r.cypher and any("discriminant" in n for n in r.notes)


def test_parent_then_subtype_keeps_precise(pg):
    r = translate(A + "SELECT ?x WHERE { ?x a am:Vehicle . ?x a am:ElectricVehicle }", pg)
    assert "x.vehicleKind = 'ElectricVehicle'" in r.cypher and not r.lossy


def test_unsupported_graph_is_lossy_not_exception(pg):
    r = translate(q("q10_unsupported"), pg)
    assert r.lossy and any("GRAPH" in n for n in r.notes)


def test_lost_property_flagged(pg):
    r = translate("PREFIX am: <https://w3id.org/ontoforge/automaint#> SELECT ?v ?c WHERE { ?v am:usesFuel ?c }", pg)
    assert r.lossy and any("usesFuel" in n for n in r.notes)


def test_invalid_sparql_no_exception(pg):
    r = translate("SELEKT nothing {{", pg)
    assert r.lossy and not r.supported and r.cypher is None
    r = translate("INSERT DATA { <a:a> <a:b> <a:c> }", pg)
    assert r.lossy


def test_competency_questions(pg, onto):
    cqs = competency_questions(pg, onto)
    assert 5 <= len(cqs) <= 10
    assert len({c.id for c in cqs}) == len(cqs)
    for c in cqs:
        assert c.sparql and c.cypher and c.curiosity and not c.lossy, (c.id, c.notes)
    assert {"relation", "count", "transitive"} <= {c.pattern for c in cqs}


def test_missing_property_in_mandatory_pattern_gives_empty_block(pg):
    r = translate(A + "SELECT ?v ?x WHERE { ?v am:ownedBy ?c . ?v am:nope ?x }", pg)
    assert r.lossy and "false" in r.cypher and any("nope" in n and "[perte]" in n for n in r.notes)


def test_missing_edge_without_onto_gives_empty_block(pg):
    r = translate(A + "SELECT ?o ?v WHERE { ?o am:concerns ?v }", pg)  # inverse non connue sans ontologie
    assert r.lossy and "false" in r.cypher


def test_missing_property_in_optional_keeps_rows(pg):
    r = translate(A + "SELECT ?v ?x WHERE { ?v a am:Vehicle . OPTIONAL { ?v am:nope ?x } }", pg)
    assert r.lossy and "false" not in r.cypher


# ---- sous-classes repliées / héritées (L15, revue Curiosity) --------------------------------------
AMNS = "https://w3id.org/ontoforge/automaint#"
_SUB_Q = (f"PREFIX am:<{AMNS}> SELECT ?ro ?n ?gn WHERE {{ ?ro am:assignedTo ?t . ?t a am:Technician ; "
          "am:displayName ?n ; am:worksAt ?g . ?g a am:Garage ; am:displayName ?gn }")


def _automaint_pg(target):
    from pathlib import Path
    from ontoforge.io.rdf_import import parse_ontology
    from ontoforge.mapping.engine import analyze
    p = Path(__file__).resolve().parents[2] / "samples" / "automaint" / "automaint.ttl"
    onto, _ = parse_ontology(p.read_text(), filename="a.ttl")
    return onto, analyze(onto, None, target)


def test_curiosity_abstract_ancestor_props_copied_into_leaves():
    """Décision lead L15 : Technician/Garage/Customer/Brand restent des types distincts et reçoivent DisplayName."""
    onto, pg = _automaint_pg("curiosity")
    for n in ("Technician", "Garage", "Customer", "Brand"):
        assert n in pg.node_types and "DisplayName" in [p.name for p in pg.node_types[n].properties], n
    assert not {"Technician", "Garage", "Customer", "Brand"} & set(pg.node_types["Party"].discriminator_values)
    r = translate(_SUB_Q, pg, onto)
    assert not [n for n in r.notes if n.startswith("[perte]")], r.notes
    assert "(t:Technician)" in r.cypher and "t.DisplayName AS n" in r.cypher and "g.DisplayName AS gn" in r.cypher
    assert "N.Technician.Type" in r.curiosity and "N.Party" not in r.curiosity


def test_curiosity_folded_subclass_uses_root_and_discriminant():
    onto, pg = _automaint_pg("curiosity")
    q = f"PREFIX am:<{AMNS}> SELECT ?v ?x WHERE {{ ?v a am:ElectricVehicle ; am:vin ?x }}"
    r = translate(q, pg, onto)
    assert not [n for n in r.notes if n.startswith("[perte]")], r.notes
    assert "v.VehicleKind = 'ElectricVehicle'" in r.cypher and "(v:Vehicle)" in r.cypher
    assert '.WhereString(N.Vehicle.Type, N.Vehicle.VehicleKind, "ElectricVehicle")' in r.curiosity


def test_neo4j_inherited_property_through_secondary_labels():
    onto, pg = _automaint_pg("neo4j")
    r = translate(_SUB_Q, pg, onto)
    assert not [n for n in r.notes if n.startswith("[perte]")], r.notes
    assert "(t:Technician)" in r.cypher and "t.displayName AS n" in r.cypher
