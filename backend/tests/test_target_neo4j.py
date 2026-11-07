"""Générateur Neo4j : DDL, ingestion, validations, Mermaid, README (sans serveur Neo4j : formes vérifiées par regex)."""
import json
import re
from pathlib import Path

import pytest

from ontoforge.core.pg_model import EdgeType, NodeType, PGModel, PGProperty, Validation
from ontoforge.targets import neo4j as t

FIX = Path(__file__).parent / "fixtures" / "pg_neo4j_automaint.json"

ID = r"(?:[A-Za-z_][A-Za-z0-9_]*|`[^`]+`)"
CONSTRAINT = re.compile(
    rf"^CREATE CONSTRAINT {ID} IF NOT EXISTS FOR (?:\(n:{ID}\)|\(\)-\[r:{ID}\]-\(\)) REQUIRE "
    rf"(?:\(?(?:[nr]\.{ID})(?:, [nr]\.{ID})*\)?) "
    r"(?:IS UNIQUE|IS NODE KEY|IS NOT NULL|IS :: [A-Z]+(?: [A-Z]+)?(?:<[A-Z ]+>)?);$")
INDEX = re.compile(
    rf"^CREATE (?:TEXT |FULLTEXT )?INDEX {ID} IF NOT EXISTS FOR (?:\(n:{ID}(?:\|{ID})*\)|\(\)-\[r:{ID}\]-\(\)) "
    rf"ON (?:\([nr]\.{ID}(?:, [nr]\.{ID})*\)|EACH \[[^\]]+\]);$")


@pytest.fixture(scope="module")
def pg():
    return PGModel.model_validate(json.loads(FIX.read_text(encoding="utf-8")))


@pytest.fixture(scope="module")
def out(pg):
    return t.generate(pg)


def _statements(text):
    return [l for l in text.splitlines() if l.startswith("CREATE ")]


def _enterprise(text):
    return [l[3:] for l in text.splitlines() if l.startswith("// CREATE ")]


def test_files_and_determinism(pg, out):
    assert set(out) == {"schema.cypher", "ingest.cypher", "validation.cypher", "model.mmd", "README-neo4j.md"}
    assert all(v.strip() for v in out.values())
    assert t.generate(pg) == out
    assert t.generate(pg, onto=object()) == out
    assert not any("{chr(10)}" in v or "{rows}" in v for v in out.values())


# --- DDL -------------------------------------------------------------------------------------
def test_ddl_forms_and_unique_names(out):
    schema = out["schema.cypher"]
    active = _statements(schema)
    ent = _enterprise(schema)
    assert active and ent
    for s in active + ent:
        assert CONSTRAINT.match(s) or INDEX.match(s), s
    names = [re.match(rf"CREATE (?:TEXT |FULLTEXT )?(?:CONSTRAINT|INDEX) ({ID})", s).group(1) for s in active + ent]
    # un nom de contrainte/index est unique dans toute la base (le NODE KEY Enterprise remplace l'UNIQUE : noms distincts)
    assert len(names) == len(set(names))
    assert all(len(n) < 200 for n in names)


def test_community_has_no_enterprise_only_statements(out):
    for s in _statements(out["schema.cypher"]):
        assert "IS NODE KEY" not in s and "IS NOT NULL" not in s and " IS :: " not in s


def test_enterprise_section_is_commented_and_complete(out):
    schema = out["schema.cypher"]
    ent = "\n".join(_enterprise(schema))
    assert "Enterprise" in schema
    assert "IS NODE KEY" in ent and "IS NOT NULL" in ent
    assert "REQUIRE (n.brandCode, n.modelCode) IS NODE KEY" in ent
    assert "IS :: LIST<STRING NOT NULL>" in ent
    assert "IS :: ZONED DATETIME" in ent and "IS :: LOCAL DATETIME" in ent and "IS :: DURATION" in ent
    assert "IS :: LOCAL TIME" in ent and "IS :: DATE" in ent and "IS :: FLOAT" in ent and "IS :: INTEGER" in ent
    # NODE KEY : la contrainte UNIQUE de même schéma est retirée d'abord
    assert "// DROP CONSTRAINT vehicle_key_unique IF EXISTS;" in schema


def test_composite_key_and_multilabel(out):
    schema, ingest = out["schema.cypher"], out["ingest.cypher"]
    assert "FOR (n:VehicleModel) REQUIRE (n.brandCode, n.modelCode) IS UNIQUE;" in schema
    # contrainte posée sur le label le plus général (Vehicle), pas sur ElectricVehicle
    assert "FOR (n:Vehicle) REQUIRE n.vin IS UNIQUE;" in schema
    assert not re.search(r"^CREATE CONSTRAINT .* FOR \(n:ElectricVehicle\) REQUIRE n\.vin", schema, re.M)
    assert "MERGE (n:Vehicle {vin: row.vin})\nSET n:ElectricVehicle" in ingest


def test_relationship_constraints_and_indexes(out):
    schema = out["schema.cypher"]
    assert "FOR ()-[r:INSTALLED_ON]-() REQUIRE r.installationId IS UNIQUE;" in schema
    assert "FOR ()-[r:INSTALLED_ON]-() ON (r.mileageKm);" in schema
    assert re.search(r"CREATE TEXT INDEX \w+ IF NOT EXISTS FOR \(n:Part\) ON \(n\.name_fr\);", schema)
    assert "CREATE FULLTEXT INDEX" in schema and "ON EACH [" in schema


def test_no_invented_cardinality_constraint(out):
    # la cardinalité de relation n'est jamais une contrainte : commentaire + validation
    assert not re.search(r"^CREATE CONSTRAINT.*(CONCERNS_VEHICLE|HANDLED_BY|PERFORMED_AT)", out["schema.cypher"], re.M)
    assert "// CARDINALITY (RepairOrder)-[:CONCERNS_VEHICLE]->(Vehicle)" in out["schema.cypher"]


def test_lost_findings_listed(pg, out):
    for f in pg.findings:
        if f.severity == "lost":
            assert f"// LOST {f.id}" in out["schema.cypher"]
            assert f.id in out["README-neo4j.md"]


def test_enum_pattern_noted_not_constrained(out):
    schema = out["schema.cypher"]
    assert "// ENUM Vehicle.fuelType" in schema and "// PATTERN Vehicle.vin" in schema


# --- Ingestion -------------------------------------------------------------------------------
def test_ingest_nodes_before_relations_and_idempotent(pg, out):
    ing = out["ingest.cypher"]
    assert ing.index("===== Nœuds") < ing.index("===== Relations")
    blocks = [b for b in ing.split("\n\n") if b.startswith("// :") or b.startswith("// (")]
    assert blocks
    assert ing.count("UNWIND $rows AS row") >= len(pg.node_types) - 3
    assert "CREATE (" not in ing and "CREATE (n" not in ing
    labels = {l for n in pg.node_types.values() for l in n.labels}
    for m in re.finditer(r"MERGE \(n:(\w+) \{", ing):
        assert m.group(1) in labels


def test_ingest_relationship_with_properties(out):
    ing = out["ingest.cypher"]
    i = ing.index("INSTALLED_ON")
    block = ing[i:i + 900]
    assert "MERGE (a)-[r:INSTALLED_ON" in ing
    assert "installedAt" in block and "mileageKm" in block
    assert "toInteger(row.mileageKm)" in ing and "datetime(row.installedAt)" in ing


def test_ingest_default_enum_cast(out):
    ing = out["ingest.cypher"]
    assert "coalesce(row.status, 'OPEN')" in ing
    assert "toFloat(row.totalCost)" in ing and "date(row.firstRegistrationDate)" in ing
    assert "duration(row.laborDuration)" in ing


def test_ingest_symmetric_and_derived(out):
    ing = out["ingest.cypher"]
    assert "COLLEAGUE_OF" in ing
    # relations dérivées non ingérées (recalculées par validation.cypher)
    assert not re.search(r"MERGE \(a\)-\[(?:r:)?PART_OF_TRANSITIVE", ing)


# --- Validations / matérialisations ---------------------------------------------------------
def test_one_query_per_validation(pg, out):
    val = out["validation.cypher"]
    for v in pg.validations:
        assert re.search(rf"^// {v.id} \[{v.kind}\]", val, re.M), v.id
    live = re.findall(r"^RETURN '(V\d+)' AS validation", val, re.M)
    assert sorted(live) == sorted(v.id for v in pg.validations if v.id != "V16")


def test_validation_shapes(out):
    val = out["validation.cypher"]
    assert "COUNT { (n)-[:CONCERNS_VEHICLE]->(:Vehicle) }" in val
    assert "WHERE n:Warranty" in val
    assert "NOT n.fuelType IN ['DIESEL', 'ELECTRIC', 'HYBRID', 'PETROL']" in val
    assert "(n:Part)-[r:PART_OF]->(n)" in val
    assert "=~ '[A-HJ-NPR-Z0-9]{17}'" in val  # =~ = correspondance complète : ancres retirées
    assert "'Warning' AS severity" in val
    # non traduisible : patron commenté, jamais de faux positif exécutable
    assert "// WHERE /* À COMPLÉTER" in val


def test_materializations(pg, out):
    val = out["validation.cypher"]
    for m in pg.materializations:
        assert re.search(rf"^// {m.id} \[{m.kind}\]", val, re.M), m.id
    assert "MERGE (a)-[:PART_OF_TRANSITIVE]->(b);" in val
    assert "MATCH ()-[r:PART_OF_TRANSITIVE]->() DELETE r;" in val
    assert "(a:RepairOrder)-[:CONCERNS_VEHICLE]->()-[:HAS_MODEL]->(b:VehicleModel)" in val
    assert "MERGE (a)-[:USES_PART]->(b);" in val


def test_every_validation_kind_generates():
    kinds = ["cardinality", "existence", "disjoint", "allValuesFrom", "enum", "irreflexive", "asymmetric", "functional",
             "hasValue", "pattern", "range", "closed", "other"]
    pg = PGModel(target="neo4j", node_types={"A": NodeType(name="A", labels=["A"], key=["id"],
                 properties=[PGProperty(name="id", required=True, unique=True)])},
                 edge_types=[EdgeType(name="R", **{"from": "A", "to": "A"})])
    pg.validations = [Validation(id=f"X{i}", kind=k, node_type="A", edge_type="R", property="id",
                                 params={"min": 1, "max": 2, "values": ["a"], "targets": ["A"], "pattern": "^a+$"},
                                 description=k) for i, k in enumerate(kinds)]
    val = t.generate(pg)["validation.cypher"]
    for i in range(len(kinds)):
        assert f"// X{i} [" in val


# --- Identifiants, Mermaid, README -----------------------------------------------------------
def test_quoting():
    assert t.quote("Vehicle") == "Vehicle"
    assert t.quote("My Label") == "`My Label`"
    assert t.quote("a`b") == "`a``b`"
    assert t.quote("1abc") == "`1abc`"
    assert t.literal("it's") == "'it\\'s'" and t.literal(True) == "true"


def test_weird_names_are_quoted_in_ddl():
    pg = PGModel(target="neo4j", node_types={"Odd": NodeType(name="Odd", labels=["Odd Label"], key=["my key"],
                 properties=[PGProperty(name="my key", unique=True)])})
    schema = t.generate(pg)["schema.cypher"]
    assert "(n:`Odd Label`)" in schema and "n.`my key`" in schema


def test_mermaid(pg, out):
    mmd = out["model.mmd"]
    assert mmd.startswith("classDiagram")
    for n in pg.node_types.values():
        if not n.abstract:
            assert re.search(rf"class {re.escape(n.labels[-1] if n.labels else n.name)} ", mmd) or \
                re.search(rf"class {re.escape(n.name)} ", mmd), n.name
    assert "INSTALLED_ON" in mmd and "-->" in mmd and "..>" in mmd


def test_readme(out):
    r = out["README-neo4j.md"]
    for s in ("Community", "Enterprise", "schema.cypher", "ingest.cypher", "validation.cypher", "Constats non arbitrés"):
        assert s in r
    assert "D05:auto:totalCost" in r


# --- Itération 2 : clé de repli, propriété IRI marquée, chaîne de matérialisation -------------
def _pg_nokey(iri_name="Uri", with_marker=True):
    iri = PGProperty(name=iri_name, required=True, unique=True, source="urn:ontoforge:iri" if with_marker else None)
    return PGModel(
        target="neo4j",
        node_types={
            "VehicleModel": NodeType(name="VehicleModel", labels=["VehicleModel"], properties=[iri]),
            "Orphan": NodeType(name="Orphan", labels=["Orphan"], properties=[PGProperty(name="note")]),
            "Recall": NodeType(name="Recall", labels=["Recall"], key=[iri_name], properties=[iri]),
        },
        edge_types=[EdgeType(name="AFFECTS_MODEL", **{"from": "Recall", "to": "VehicleModel"}),
                    EdgeType(name="LINKS_ORPHAN", **{"from": "Recall", "to": "Orphan"})],
        validations=[Validation(id="V1", kind="existence", node_type="VehicleModel", property=iri_name,
                                description="iri")],
    )


@pytest.mark.parametrize("name,marker", [("Uri", True), ("iri_x", True), ("URI", False)])
def test_keyless_type_uses_iri_property_as_fallback_key(name, marker):
    out = t.generate(_pg_nokey(name, marker))
    ing = out["ingest.cypher"]
    assert f"MERGE (n:VehicleModel {{{name}: row.{name}}})" in ing
    assert "MATCH (b:VehicleModel {})" not in ing and "{}" not in ing
    assert f"MATCH (b:VehicleModel {{{name}: row.to.{name}}})" in ing
    assert f"n.{name} AS uri" in out["validation.cypher"]


def test_never_empty_pattern_and_incomplete_relation_commented():
    out = t.generate(_pg_nokey())
    ing = out["ingest.cypher"]
    assert "{}" not in ing
    assert "// À COMPLÉTER : relation non ingérée" in ing
    active = [l for l in ing.splitlines() if not l.startswith("//")]
    assert not any("LINKS_ORPHAN" in l for l in active)
    # nœud sans aucune clé : CREATE signalé
    assert "ATTENTION : aucune clé" in ing


def test_uri_null_when_no_iri_property():
    pg = _pg_nokey()
    pg.validations = [Validation(id="V2", kind="existence", node_type="Orphan", property="note", description="x")]
    assert "null AS uri" in t.generate(pg)["validation.cypher"]


def test_materialization_chain_by_edge_name_and_source_fallback(pg):
    out = t.generate(pg)["validation.cypher"]
    assert "MATCH (a:Part)-[:PART_OF*1..]->(b:Part)" in out
    p2 = pg.model_copy(deep=True)
    p2.edge_types = [e.model_copy(update={"source": "https://example.org/auto#isPartOf"}) if e.name == "PART_OF" else e
                     for e in p2.edge_types]
    p2.materializations[0] = p2.materializations[0].model_copy(update={"chain": ["https://example.org/auto#isPartOf"]})
    assert "MATCH (a:Part)-[:PART_OF*1..]->(b:Part)" in t.generate(p2)["validation.cypher"]


def test_loss_subjects_readable_and_index_origin(out):
    schema = out["schema.cypher"]
    assert "sujet : Warranty" in schema or "sujet : Recall" in schema
    assert "<https://example.org/auto#" in schema
    assert "// index Brand.name : propriété marquée « indexed »" in schema
