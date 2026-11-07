import json
import os

import pytest
from graphql import build_schema

from ontoforge.core.pg_model import PGModel
from ontoforge.targets.graphql import generate

FX = os.path.join(os.path.dirname(__file__), "fixtures", "queries")


@pytest.fixture(scope="module")
def pg():
    return PGModel.model_validate(json.load(open(os.path.join(FX, "pg_automaint.json"))))


def test_files_and_valid_sdl(pg):
    out = generate(pg)
    assert set(out) == {"schema.graphql", "README-graphql.md"}
    schema = build_schema(out["schema.graphql"])  # SDL valide (graphql-core)
    assert schema.query_type is not None
    assert "Neo4j GraphQL" in out["README-graphql.md"] and "VÉRIFIER" in out["README-graphql.md"]


def test_one_type_per_nodetype(pg):
    schema = build_schema(generate(pg)["schema.graphql"])
    for nt in pg.node_types.values() if isinstance(pg.node_types, dict) else pg.node_types:
        assert nt.name in schema.type_map, nt.name


def test_fields_required_dates_enums(pg):
    sdl = generate(pg)["schema.graphql"]
    schema = build_schema(sdl)
    veh = schema.type_map["Vehicle"]
    assert str(veh.fields["vin"].type) == "String!"
    assert str(veh.fields["firstRegistrationDate"].type) == "DateTime"
    assert "scalar DateTime" in sdl


def test_relations_both_directions(pg):
    schema = build_schema(generate(pg)["schema.graphql"])
    assert "partOf" in schema.type_map["Part"].fields and "inversePartOf" in schema.type_map["Part"].fields
    assert "inverseOwnedBy" in schema.type_map["Customer"].fields and "ownedBy" in schema.type_map["Vehicle"].fields


def test_query_root(pg):
    q = build_schema(generate(pg)["schema.graphql"]).query_type
    assert "vehicle" in q.fields and "vehicles" in q.fields
    assert "vin" in q.fields["vehicle"].args and "first" in q.fields["vehicles"].args
