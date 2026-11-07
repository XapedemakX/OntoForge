"""Moteur L3 : invariants du PGModel, décisions (rejeu, invalides), déterminisme, registre, automaint."""
import copy
import pathlib
import time

import pytest

from ontoforge.core.onto_model import OntClass
from ontoforge.mapping.engine import analyze

ROOT = pathlib.Path(__file__).resolve().parents[2]
TRAP = ROOT / "samples" / "trap"
AUTO = ROOT / "samples" / "automaint"
AM = "https://w3id.org/ontoforge/automaint#"
TARGETS = ["curiosity", "neo4j"]


def _load(path):
    from ontoforge.io.rdf_import import parse_ontology
    return parse_ontology(path.read_text(encoding="utf-8"), filename=path.name)[0]


def _shapes(path):
    from ontoforge.shacl.import_shapes import parse_shapes
    return parse_shapes(path.read_text(encoding="utf-8"), filename=path.name)[0]


@pytest.fixture(scope="module")
def trap():
    return _load(TRAP / "trap.ttl")


@pytest.fixture(scope="module")
def trap_shapes():
    return _shapes(TRAP / "trap-shapes.ttl")


def lab_ok(pg, nt):
    return all(lab in pg.node_types for lab in nt.labels)


def check_invariants(pg):
    names = set(pg.node_types)
    assert pg.node_types, "aucun type de nœud"
    for nt in pg.node_types.values():
        assert nt.key, f"{nt.name} sans clé"
        pnames = [p.name for p in nt.properties]
        assert len(pnames) == len(set(pnames)), f"propriétés en double sur {nt.name}"
        inherited = {p.name for lab in nt.labels[1:] for p in pg.node_types[lab].properties} if lab_ok(pg, nt) else set()
        assert all(k in pnames or k in inherited for k in nt.key), f"clé {nt.key} absente de {nt.name}"
        assert any(p.source == "urn:ontoforge:iri" for p in nt.properties), f"{nt.name} sans propriété IRI"
        assert nt.labels and nt.labels[0] == nt.name
        for lab in nt.labels:
            assert lab in names, f"label {lab} sans type de nœud"
    keys = [(e.name, e.from_, e.to) for e in pg.edge_types]
    assert len(keys) == len(set(keys)), "relations en double"
    for e in pg.edge_types:
        assert e.from_ in names and e.to in names, f"relation {e.name} vers un type inexistant"
    ids = [f.id for f in pg.findings]
    assert len(ids) == len(set(ids)) and ids == sorted(ids)
    for f in pg.findings:
        assert f.options, f"{f.id} sans option"
        assert f.recommended in {o.id for o in f.options}, f.id
        assert f.rationale, f"{f.id} sans justification"
    vids = [v.id for v in pg.validations]
    assert len(vids) == len(set(vids))
    if pg.target == "curiosity":
        assert all(len(nt.labels) == 1 for nt in pg.node_types.values())
        assert all(not e.properties for e in pg.edge_types)
        assert all(e.reverse for e in pg.edge_types)
        edges = {e.name for e in pg.edge_types}
        assert not edges & names, f"collision arête / type : {edges & names}"


@pytest.mark.parametrize("target", TARGETS)
def test_invariants_trap(trap, trap_shapes, target):
    check_invariants(analyze(trap, trap_shapes, target))
    check_invariants(analyze(trap, None, target))


def test_neo4j_specifics(trap, trap_shapes):
    pg = analyze(trap, trap_shapes, "neo4j")
    assert "PartInstallation" not in pg.node_types  # R01 dé-réifiée
    inst = [e for e in pg.edge_types if e.name == "INSTALLED_ON"]
    assert inst and inst[0].from_ == "Part" and inst[0].to == "Vehicle"
    assert {p.name for p in inst[0].properties} == {"installationDate", "installMileageKm"}
    assert pg.node_types["HybridVehicle"].labels[:2] == ["HybridVehicle", "CombustionVehicle"] or \
        {"ElectricVehicle", "CombustionVehicle", "Vehicle"} <= set(pg.node_types["HybridVehicle"].labels)
    assert pg.node_types["Vehicle"].key == ["vin"]  # K02 node_key (renforcement)
    assert "WarrantyClaim" in pg.node_types  # R02 : jamais dé-réifiée
    assert any(e.name == "HAS_WARRANTY" for e in pg.edge_types)  # N01


def test_curiosity_specifics(trap, trap_shapes):
    pg = analyze(trap, trap_shapes, "curiosity")
    v = pg.node_types["Vehicle"]
    assert v.discriminator and "HybridVehicle" in v.discriminator_values  # C02 aplati
    assert "ElectricVehicle" not in pg.node_types and "MotorVehicle" not in pg.node_types
    assert "PartInstallation" in pg.node_types  # R01 keep_node
    assert v.key == ["Uri"]  # K02 uri_key
    hp = [e for e in pg.edge_types if e.name == "HasPart"]
    assert hp and hp[0].reverse == "PartOf"  # O04 paire native
    iw = [e for e in pg.edge_types if e.name == "InterchangeableWith"][0]
    assert iw.reverse == iw.name  # O05 self_reverse
    assert any(e.name == "HasWarranty" for e in pg.edge_types)  # collision Warranty
    assert next(p for p in v.properties if p.name == "Vin").pattern  # shapes / D09
    assert next(p for p in pg.node_types["RepairOrder"].properties if p.name == "OpenedAt").required  # D13 + shape


@pytest.mark.parametrize("target", TARGETS)
def test_deterministic(trap, trap_shapes, target):
    a = analyze(trap, trap_shapes, target).model_dump(by_alias=True)
    b = analyze(copy.deepcopy(trap), copy.deepcopy(trap_shapes), target).model_dump(by_alias=True)
    assert a == b


def test_decisions_replay(trap, trap_shapes):
    fid = f"C02:{AM}Vehicle"
    pg0 = analyze(trap, trap_shapes, "curiosity")
    pg1 = analyze(trap, trap_shapes, "curiosity", {fid: "multi_label"})
    f = next(x for x in pg1.findings if x.id == fid)
    assert f.chosen == "multi_label" and pg1.decisions == {fid: "multi_label"}
    assert any(p.is_list and p.name == "VehicleTypes" for p in pg1.node_types["Vehicle"].properties)
    assert not any(p.name == "VehicleTypes" for p in pg0.node_types["Vehicle"].properties)
    # ré-analyse après modification de l'ontologie : décision conservée, nouveau constat non arbitré
    onto2 = copy.deepcopy(trap)
    onto2.classes[AM + "Truck"] = OntClass(iri=AM + "Truck", labels={"fr": "camion"}, sub_class_of=[AM + "Vehicle"])
    pg2 = analyze(onto2, trap_shapes, "curiosity", pg1.decisions)
    assert next(x for x in pg2.findings if x.id == fid).chosen == "multi_label"
    # C02 = une décision par racine : la nouvelle sous-classe est couverte par la décision existante
    c02 = next(x for x in pg2.findings if x.id == fid)
    assert AM + "Truck" in c02.related and any(x.id == f"C01:{AM}Truck" for x in pg2.findings)
    assert "Truck" in pg2.node_types["Vehicle"].discriminator_values
    assert set(f.id for f in pg0.findings) <= set(f.id for f in pg2.findings)
    # Neo4j : flatten → les sous-types disparaissent dans Vehicle
    pg3 = analyze(trap, trap_shapes, "neo4j", {f"C02:{AM}Vehicle": "flatten_into_leaves"})
    assert "ElectricVehicle" not in pg3.node_types
    # R01 : garder le nœud côté Neo4j
    pg4 = analyze(trap, trap_shapes, "neo4j", {f"R01:{AM}PartInstallation": "keep_node"})
    assert "PartInstallation" in pg4.node_types
    check_invariants(pg2), check_invariants(pg3), check_invariants(pg4)


def test_invalid_decision(trap, trap_shapes):
    fid = f"R01:{AM}PartInstallation"
    pg = analyze(trap, trap_shapes, "curiosity", {fid: "dereify_relationship", "X99:nope": "foo"})
    f = next(x for x in pg.findings if x.id == fid)
    assert f.chosen is None  # option Neo4j seulement : refusée pour Curiosity
    g = [x for x in pg.findings if x.rule == "G02"]
    assert len(g) == 1 and fid in g[0].related
    assert "PartInstallation" in pg.node_types
    assert pg.decisions[fid] == "dereify_relationship"  # conservée (rejouable sur Neo4j)
    check_invariants(pg)


def test_accept_all_recommended(trap, trap_shapes):
    pg = analyze(trap, trap_shapes, "neo4j")
    dec = {f.id: f.recommended for f in pg.findings if f.severity != "auto"}
    pg2 = analyze(trap, trap_shapes, "neo4j", dec)
    assert pg2.summary()["pending"] == 0
    a, b = pg.model_dump(exclude={"findings", "decisions"}), pg2.model_dump(exclude={"findings", "decisions"})
    assert a == b  # accepter les recommandations ne change pas le modèle


def test_registry():
    from ontoforge.mapping.rules import REGISTRY, TRANSPOSITION, catalog
    assert len(TRANSPOSITION) == 66
    assert all(REGISTRY[r].implemented for r in TRANSPOSITION)
    assert {r for r in TRANSPOSITION if REGISTRY[r].it1} == catalog.IT1


def test_performance(trap, trap_shapes):
    t0 = time.perf_counter()
    for t in TARGETS:
        analyze(trap, trap_shapes, t)
    assert time.perf_counter() - t0 < 2


@pytest.mark.skipif(not (AUTO / "automaint.ttl").exists(), reason="samples/automaint absent")
@pytest.mark.parametrize("target", TARGETS)
def test_automaint(target):
    onto = _load(AUTO / "automaint.ttl")
    sh = AUTO / "automaint-shapes.ttl"
    shapes = _shapes(sh) if sh.exists() else None
    pg = analyze(onto, shapes, target)
    check_invariants(pg)
    assert len(pg.node_types) >= 5 and pg.edge_types
    from ontoforge.targets.report import generate
    assert "Ce qui est perdu ou à risque" in generate(pg, onto)["rapport-transposition.md"]
