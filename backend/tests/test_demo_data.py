"""Jeu de démo AutoMaint : parse, conformité aux shapes (0 violation), cohérence métier, requêtes guidées, reproductibilité."""
import importlib.util
import pathlib
from collections import defaultdict

import pytest
import rdflib
from pyshacl import validate
from rdflib import RDF

from ontoforge.io.rdf_import import parse_ontology
from ontoforge.queries import builder
from ontoforge.queries.builder import GuidedQuery

ROOT = pathlib.Path(__file__).resolve().parents[2]
AMD = ROOT / "samples" / "automaint"
AM = "https://w3id.org/ontoforge/automaint#"
A = rdflib.Namespace(AM)


@pytest.fixture(scope="module")
def graph():
    g = rdflib.Graph()
    g.parse(AMD / "automaint-demo-data.ttl")
    return g


@pytest.fixture(scope="module")
def onto():
    return parse_ontology((AMD / "automaint.ttl").read_text(), filename="a.ttl")[0]


def count(g, cls):
    return len(set(g.subjects(RDF.type, A[cls])))


def test_conforms_to_shapes_without_inference(graph):
    shapes = rdflib.Graph().parse(AMD / "automaint-shapes.ttl")
    conforms, _, text = validate(graph, shacl_graph=shapes, inference="none")
    assert conforms, text


def test_volumes(graph):
    assert count(graph, "VehicleModel") == 8 and count(graph, "Vehicle") == 40
    assert count(graph, "Garage") == 6 and count(graph, "Technician") == 15 and count(graph, "Customer") == 30
    assert count(graph, "RepairOrder") == 120 and count(graph, "Recall") == 3 and count(graph, "Warranty") >= 20
    assert {str(x) for x in graph.objects(None, A.usesFuel)} >= {AM + "Petrol", AM + "Diesel", AM + "Electric"}
    assert count(graph, "ElectricVehicle") and count(graph, "CombustionVehicle")
    codes = {str(c) for c in graph.objects(None, A.dtcCode)}
    assert {"P0300", "P0420"} <= codes


def test_chain_and_dates(graph):
    for ro in graph.subjects(RDF.type, A.RepairOrder):
        v = graph.value(ro, A.concerns)
        assert (v, A.hasRepairOrder, ro) in graph
        gar, tech = graph.value(ro, A.performedAt), graph.value(ro, A.assignedTo)
        assert gar and tech and (tech, A.worksAt, gar) in graph
        o = graph.value(ro, A.openedAt).toPython()
        assert 2025 <= o.year <= 2026
        c = graph.value(ro, A.closedAt)
        assert c is None or c.toPython() >= o
    for p in graph.subjects(RDF.type, A.Part):
        assert graph.value(p, A.installedIn) and graph.value(p, A.instanceOf)


def test_mileage_increasing(graph):
    per = defaultdict(list)
    for r in graph.subjects(RDF.type, A.MileageReading):
        v = graph.value(r, A.readingOf)
        assert (v, A.hasMileageReading, r) in graph
        per[v].append((graph.value(r, A.readingDate).toPython(), float(graph.value(r, A.readingMileageKm))))
    assert len(per) == 40
    for v, rows in per.items():
        rows.sort()
        kms = [k for _, k in rows]
        assert all(b > a for a, b in zip(kms, kms[1:])), v


def run(graph, onto, spec):
    sp = builder.to_sparql(GuidedQuery.model_validate(spec), onto)
    return list(graph.query(sp))


def test_guided_queries_return_rows(graph, onto):
    # 1. véhicule -> ordre de réparation -> technicien
    rows = run(graph, onto, {"root": {"var": "v", "class_iri": AM + "Vehicle"}, "steps": [
        {"from_var": "v", "property_iri": AM + "hasRepairOrder", "to_var": "ro", "to_class_iri": AM + "RepairOrder"},
        {"from_var": "ro", "property_iri": AM + "assignedTo", "to_var": "t", "to_class_iri": AM + "Technician"}],
        "select": [{"var": "v", "property_iri": AM + "vin"}, {"var": "ro", "property_iri": AM + "orderNumber"},
                   {"var": "t", "property_iri": AM + "displayName"}], "limit": 500})
    assert len(rows) >= 100
    # 2. ordres réalisés dans un garage de Toulouse (la ville est dans le nom)
    rows = run(graph, onto, {"root": {"var": "ro", "class_iri": AM + "RepairOrder"}, "steps": [
        {"from_var": "ro", "property_iri": AM + "performedAt", "to_var": "g", "to_class_iri": AM + "Garage"}],
        "filters": [{"var": "g", "kind": "text_contains", "property_iri": AM + "displayName", "value": "Toulouse"}],
        "select": [{"var": "ro", "property_iri": AM + "orderNumber"}, {"var": "g", "property_iri": AM + "displayName"}]})
    assert len(rows) >= 5
    # 3. véhicules ayant un code défaut actif, avec le code
    rows = run(graph, onto, {"root": {"var": "v", "class_iri": AM + "Vehicle"}, "steps": [
        {"from_var": "v", "property_iri": AM + "hasActiveCode", "to_var": "d", "to_class_iri": AM + "DiagnosticTroubleCode"}],
        "select": [{"var": "v", "property_iri": AM + "registrationNumber"}, {"var": "d", "property_iri": AM + "dtcCode"}]})
    assert len(rows) >= 10
    # 4. rappel -> modèle -> marque
    rows = run(graph, onto, {"root": {"var": "r", "class_iri": AM + "Recall"}, "steps": [
        {"from_var": "r", "property_iri": AM + "appliesToModel", "to_var": "m", "to_class_iri": AM + "VehicleModel"},
        {"from_var": "m", "property_iri": AM + "madeBy", "to_var": "b", "to_class_iri": AM + "Brand"}],
        "select": [{"var": "r", "property_iri": AM + "recallNumber"}, {"var": "b", "property_iri": AM + "brandName"}]})
    assert len(rows) >= 6


def test_generator_is_reproducible(graph):
    spec = importlib.util.spec_from_file_location("gen", ROOT / "tools" / "demo" / "generate_demo_data.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    from rdflib.compare import isomorphic
    again = rdflib.Graph().parse(data=mod.build().serialize(format="turtle"), format="turtle")  # aller-retour : lexicaux normalisés
    assert isomorphic(again, graph)
