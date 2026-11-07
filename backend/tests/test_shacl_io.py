import pathlib

import pytest
import rdflib
from rdflib.compare import isomorphic

from ontoforge.shacl.export_shapes import serialize_shapes, shapes_to_graph
from ontoforge.shacl.import_shapes import parse_shapes

ROOT = pathlib.Path(__file__).resolve().parents[2]
FIX = pathlib.Path(__file__).parent / "fixtures" / "shacl"
SAMPLES = [ROOT / "samples/trap/trap-shapes.ttl", ROOT / "samples/automaint/automaint-shapes.ttl", FIX / "core-full.ttl"]


@pytest.mark.parametrize("path", SAMPLES, ids=lambda p: p.name)
def test_roundtrip_model_stable(path):
    m, warns = parse_shapes(path.read_text(), filename=path.name)
    assert all("SHACL-SPARQL" in w for w in warns)  # seuls les sh:sparql bruts sont signalés
    m2, warns2 = parse_shapes(serialize_shapes(m))
    assert len(warns2) == len(warns)
    assert m2.model_dump() == m.model_dump()


@pytest.mark.parametrize("path", SAMPLES, ids=lambda p: p.name)
def test_roundtrip_graph_isomorphic(path):
    m, _ = parse_shapes(path.read_text())
    g = shapes_to_graph(m)
    g2 = shapes_to_graph(parse_shapes(serialize_shapes(m))[0])
    assert isomorphic(g, g2)


def test_trap_shapes_have_key_constraints():
    m, _ = parse_shapes((ROOT / "samples/trap/trap-shapes.ttl").read_text())
    ttl = serialize_shapes(m)
    for token in ("sh:pattern", "sh:in", "sh:or", "sh:lessThan", "sh:qualifiedValueShape", "sh:inversePath", "sh:closed"):
        assert token in ttl


def test_unmodeled_triples_produce_warnings():
    _, warns = parse_shapes((FIX / "unmodeled.ttl").read_text())
    assert warns, "les triplets non modélisés ne doivent jamais être perdus en silence"


def test_json_ld_and_invalid_input():
    m, _ = parse_shapes((ROOT / "samples/automaint/automaint-shapes.ttl").read_text())
    jl = serialize_shapes(m, "json-ld")
    m2, _ = parse_shapes(jl, format="json-ld")
    assert set(m2.shapes) == set(m.shapes)
    bad, w = parse_shapes("ceci n'est pas du RDF {{{", format="turtle")  # pas d'exception : warning
    assert not bad.shapes and w
