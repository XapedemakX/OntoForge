"""L47 it2 : le générateur Curiosity lit les bornes de la forme restriction {kind, n} et garde la présence des plages."""
from __future__ import annotations

from ontoforge.core.pg_model import PGModel, Validation
from ontoforge.targets.curiosity import _bounds, generate

TTL = b"""@prefix : <http://ex.org/t#> . @prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> . @prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
<http://ex.org/t> a owl:Ontology .
:Car a owl:Class ; rdfs:subClassOf
   [ a owl:Restriction ; owl:onProperty :hasWheel ; owl:qualifiedCardinality 4 ; owl:onClass :Wheel ] .
:Wheel a owl:Class .
:Truck a owl:Class ;
   rdfs:subClassOf [ a owl:Restriction ; owl:onProperty :hasAxle ; owl:maxCardinality 3 ] ;
   rdfs:subClassOf [ a owl:Restriction ; owl:onProperty :hasDriver ; owl:minCardinality 2 ] ;
   rdfs:subClassOf [ a owl:Restriction ; owl:onProperty :hasPlate ; owl:cardinality 1 ] .
:hasAxle a owl:ObjectProperty ; rdfs:domain :Truck ; rdfs:range :Wheel .
:hasDriver a owl:ObjectProperty ; rdfs:domain :Truck ; rdfs:range :Wheel .
:hasPlate a owl:ObjectProperty ; rdfs:domain :Truck ; rdfs:range :Wheel .
"""


def _v(**params):
    return Validation(id="V1", kind="cardinality", description="d", severity="Warning", params=params)


def test_bounds_reads_restriction_form():
    assert _bounds(_v(kind="exactly", n=2)) == ("2", "2")
    assert _bounds(_v(kind="max", n=3)) == (None, "3")
    assert _bounds(_v(kind="min", n=2)) == ("2", None)
    assert _bounds(_v(kind="some")) == ("1", None)
    assert _bounds(_v(min=1, max=4)) == ("1", "4")
    assert _bounds(_v()) == (None, None)


def test_graph_checks_exactly_max_min_are_code_not_notchecked():
    from ontoforge.io.rdf_import import parse_ontology
    from ontoforge.mapping.engine import analyze
    onto, _ = parse_ontology(TTL, filename="t.ttl")
    pg = analyze(onto, None, "curiosity", {})
    cs = generate(pg)["Connector.cs"]
    graph = [v for v in pg.validations if v.edge_type and not v.property]
    assert graph, "des validations de cardinalité sur arêtes sont attendues"
    for v in graph:
        assert f'NotChecked("{v.id}"' not in cs, v.id
        assert f'Report("{v.id}"' in cs, v.id


DATA = b"""@prefix : <http://ex.org/t#> . @prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> . @prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
<http://ex.org/t> a owl:Ontology .
:Part a owl:Class ;
   rdfs:subClassOf [ a owl:Restriction ; owl:onProperty :tag ; owl:maxCardinality 1 ] ;
   rdfs:subClassOf [ a owl:Restriction ; owl:onProperty :label ; owl:minCardinality 1 ] .
:tag a owl:DatatypeProperty ; rdfs:domain :Part ; rdfs:range xsd:string .
:label a owl:DatatypeProperty ; rdfs:domain :Part ; rdfs:range xsd:string .
:weight a owl:DatatypeProperty ; rdfs:domain :Part ;
   rdfs:range [ a rdfs:Datatype ; owl:onDatatype xsd:integer ;
                owl:withRestrictions ( [ xsd:minInclusive 1 ] [ xsd:maxInclusive 500 ] ) ] .
"""


def test_range_has_presence_guard_and_data_cardinality_is_code():
    from ontoforge.io.rdf_import import parse_ontology
    from ontoforge.mapping.engine import analyze
    onto, _ = parse_ontology(DATA, filename="d.ttl")
    pg = analyze(onto, None, "curiosity", {})
    node = next(iter(pg.node_types.values()))
    wp = next(p for p in node.properties if p.name.lower().startswith("weight"))
    wp.type = "Integer"
    pg.validations.append(Validation(id="R1", kind="range", node_type=node.name, property=wp.name,
                                     params={"min": 1, "max": 500}, description="poids", severity="Violation"))
    cs = generate(pg)["Connector.cs"]
    line = next(l for l in cs.splitlines() if 'Report("R1"' in l)
    assert " != 0 && (" in line, line
    for v in pg.validations:
        if v.kind in ("cardinality", "existence") and v.property:
            assert f'NotChecked("{v.id}"' not in cs, v.id
    assert 'Guaranteed("D13:http://ex.org/t#Part:http://ex.org/t#tag#v1"' in cs  # max 1 sur un scalaire


def test_generated_text_and_reclassification_for_exactly_max_min():
    from ontoforge.io.rdf_import import parse_ontology
    from ontoforge.mapping.engine import analyze
    onto, _ = parse_ontology(TTL, filename="t.ttl")
    pg = analyze(onto, None, "curiosity", {})
    cs = generate(pg)["Connector.cs"]
    assert "if (c > 3) Report(" in cs                 # max 3
    assert "if (c < 1 || c > 1) Report(" in cs        # exactly 1 = min 1 + max 1
    assert "if (c < 2) Report(" in cs                 # min 2
    sev = {f.id.rsplit("#", 1)[-1]: f.severity for f in pg.findings if f.rule in ("O09", "O10")}
    assert sev["hasAxle"] == "auto"    # max : ne renforce pas
    assert sev["hasPlate"] == "review"  # exactly 1 : renforcement bloquant
    assert sev["hasDriver"] == "review"
    neo = {f.id.rsplit("#", 1)[-1]: f.severity for f in analyze(onto, None, "neo4j", {}).findings if f.rule in ("O09", "O10")}
    assert set(neo.values()) == {"auto"}               # Neo4j : détection non bloquante


def test_markdown_neutralizes_extended_autolinks():
    from ontoforge.targets.justification import _md
    out = _md("voir www.evil.com et a@b.org")
    assert "www\\." in out and "a\\@b" in out



def test_scalar_max_zero_is_not_guaranteed():
    """Revue curiosity it3 : max 0 / exactly 0 sur un scalaire n'est pas « au plus une valeur »."""
    from ontoforge.io.rdf_import import parse_ontology
    from ontoforge.mapping.engine import analyze
    onto, _ = parse_ontology(DATA, filename="d.ttl")
    pg = analyze(onto, None, "curiosity", {})
    node = next(iter(pg.node_types.values()))
    sp = next(p for p in node.properties if p.name.lower().startswith("tag"))
    pg.validations.append(Validation(id="Z0", kind="cardinality", node_type=node.name, property=sp.name,
                                     params={"kind": "exactly", "n": 0}, description="aucune", severity="Violation"))
    cs = generate(pg)["Connector.cs"]
    assert not any('Z0' in l and "au plus une valeur" in l for l in cs.splitlines())
    line = next(l for l in cs.splitlines() if 'Report("Z0"' in l)
    assert "!string.IsNullOrWhiteSpace(" in line, line
