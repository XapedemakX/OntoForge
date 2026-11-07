"""Non-régression des bloquants de la revue w3c it1 (journal/L3/review-w3c-it1.md) + bruit d'arbitrage."""
import pathlib

import pytest

from ontoforge.mapping.engine import analyze

ROOT = pathlib.Path(__file__).resolve().parents[2]
X = "http://ex.org/x#"
H = """@prefix : <http://ex.org/x#> . @prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> . @prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
<http://ex.org/x> a owl:Ontology . :A a owl:Class . :B a owl:Class . :C a owl:Class .
"""


def onto(body):
    from ontoforge.io.rdf_import import parse_ontology
    return parse_ontology((H + body).encode(), format="turtle")[0]


@pytest.mark.parametrize("target", ["curiosity", "neo4j"])
def test_b1_chain_order_and_repetition(target):
    o = onto(":zeta a owl:ObjectProperty ; rdfs:domain :A ; rdfs:range :B . "
             ":alpha a owl:ObjectProperty ; rdfs:domain :B ; rdfs:range :C . "
             ":r a owl:ObjectProperty ; rdfs:domain :A ; rdfs:range :C ; owl:propertyChainAxiom (:zeta :alpha) . "
             ":s a owl:ObjectProperty ; rdfs:domain :A ; rdfs:range :A ; owl:propertyChainAxiom (:s2 :s2) . "
             ":s2 a owl:ObjectProperty ; rdfs:domain :A ; rdfs:range :A .")
    pg = analyze(o, None, target, {f"O08:{X}r": "materialize_closure", f"O08:{X}s": "materialize_closure"})
    f = next(x for x in pg.findings if x.id == f"O08:{X}r")
    assert f.related == [X + "zeta", X + "alpha"]
    m = next(x for x in pg.materializations if x.source == X + "r")
    assert [c.lower() for c in m.chain] == ["zeta", "alpha"]
    m2 = next(x for x in pg.materializations if x.source == X + "s")
    assert len(m2.chain) == 2 and m2.chain[0] == m2.chain[1]  # p ∘ p conservée


@pytest.mark.parametrize("target", ["curiosity", "neo4j"])
def test_b2_chain_is_inclusion_and_edge_kept(target):
    o = onto(":p a owl:ObjectProperty ; rdfs:domain :A ; rdfs:range :B . "
             ":q a owl:ObjectProperty ; rdfs:domain :B ; rdfs:range :C . "
             ":r a owl:ObjectProperty ; rdfs:domain :A ; rdfs:range :C ; owl:propertyChainAxiom (:p :q) .")
    pg = analyze(o, None, target)
    f = next(x for x in pg.findings if x.rule == "O08")
    assert "⊑" in f.detail and "≡" not in f.detail
    r = [e for e in pg.edge_types if e.source == X + "r"]
    assert r and not r[0].derived  # assertions directes de r conservées


@pytest.mark.parametrize("target", ["curiosity", "neo4j"])
def test_b3_complex_domain_never_silent(target):
    o = onto(":p a owl:DatatypeProperty ; rdfs:domain [ a owl:Class ; owl:intersectionOf (:A :B) ] ; rdfs:range xsd:string . "
             ":o a owl:ObjectProperty ; rdfs:domain [ a owl:Class ; owl:intersectionOf (:A :B) ] ; rdfs:range :C . "
             ":k a owl:DatatypeProperty ; rdfs:domain [ a owl:Class ; owl:complementOf :A ] ; rdfs:range xsd:string .")
    pg = analyze(o, None, target)
    holders = {nt.name.lower() for nt in pg.node_types.values() for x in nt.properties if x.source == X + "p"}
    assert holders == {"a", "b"}  # domain(A ⊓ B) ⊨ domain(A), domain(B)
    assert any(f.rule == "D12" and f.subject == X + "p" for f in pg.findings)
    assert {e.from_.lower() for e in pg.edge_types if e.source == X + "o"} == {"a", "b"}
    assert any(f.rule == "O21" and f.subject == X + "o" for f in pg.findings)
    assert any(f.rule == "G01" and f.subject == X + "k" for f in pg.findings)  # non réductible : constat explicite


def test_b4_flattened_subclass_restriction_is_scoped():
    o = onto(":B rdfs:subClassOf :A , [ a owl:Restriction ; owl:onProperty :n ; owl:cardinality 1 ] , "
             "[ a owl:Restriction ; owl:onProperty :e ; owl:someValuesFrom :C ] . "
             ":n a owl:DatatypeProperty ; rdfs:domain :B ; rdfs:range xsd:string . "
             ":e a owl:ObjectProperty ; rdfs:domain :A ; rdfs:range :C . :a1 a :A .")
    pg = analyze(o, None, "curiosity")
    a = pg.node_types["A"]
    assert "B" in a.discriminator_values
    n = next(x for x in a.properties if x.source == X + "n")
    assert not n.required  # pas obligatoire pour tous les A
    e = next(x for x in pg.edge_types if x.source == X + "e")
    assert e.cardinality.out == "0..*"
    vals = [v for v in pg.validations if v.property == n.name or v.edge_type == e.name]
    assert vals and all(v.params.get("discriminator") == a.discriminator and v.params.get("values") == ["B"]
                        for v in vals)


def test_b5_two_some_is_not_exactly_one():
    o = onto(":e a owl:ObjectProperty ; rdfs:domain :A ; rdfs:range :B . :C rdfs:subClassOf :B . "
             ":A rdfs:subClassOf [ a owl:Restriction ; owl:onProperty :e ; owl:someValuesFrom :B ] , "
             "[ a owl:Restriction ; owl:onProperty :e ; owl:someValuesFrom :C ] . :a1 a :A . :b1 a :B .")
    for t in ("curiosity", "neo4j"):
        pg = analyze(o, None, t)
        assert {e.cardinality.out for e in pg.edge_types if e.source == X + "e"} == {"1..*"}


def test_grouped_decision_wildcard():
    o = onto(":n a owl:DatatypeProperty ; rdfs:domain :A ; rdfs:range xsd:string . "
             ":m a owl:DatatypeProperty ; rdfs:domain :B ; rdfs:range xsd:string . "
             ":A rdfs:subClassOf [ a owl:Restriction ; owl:onProperty :n ; owl:cardinality 1 ] . "
             ":B rdfs:subClassOf [ a owl:Restriction ; owl:onProperty :m ; owl:cardinality 1 ] .")
    pg = analyze(o, None, "neo4j", {"D13:*": "ignore"})
    d13 = [f for f in pg.findings if f.rule == "D13"]
    assert len(d13) == 2 and all(f.chosen == "ignore" for f in d13)


@pytest.mark.skipif(not (ROOT / "samples/automaint/automaint.ttl").exists(), reason="automaint absent")
@pytest.mark.parametrize("target", ["curiosity", "neo4j"])
def test_noise_automaint(target):
    from ontoforge.io.rdf_import import parse_ontology
    from ontoforge.shacl.import_shapes import parse_shapes
    d = ROOT / "samples/automaint"
    o = parse_ontology((d / "automaint.ttl").read_text(encoding="utf-8"), filename="automaint.ttl")[0]
    s = parse_shapes((d / "automaint-shapes.ttl").read_text(encoding="utf-8"), filename="s.ttl")[0]
    pg = analyze(o, s, target)
    pending = pg.summary()["pending"]
    assert pending <= 55, pending  # avant revue it1 : 80 (review + lost) sur les deux cibles
    party = pg.node_types.get("Party")
    if target == "curiosity" and party is not None:
        assert not any(x.required for x in party.properties if x.name == "BrandName")
