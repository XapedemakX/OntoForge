"""Import/export RDF : mapping inverse OWL 2, warnings, unmapped, round-trip."""
import glob
import pathlib

import pytest

from ontoforge.core.onto_model import OWL, XSD
from ontoforge.io.rdf_export import model_to_graph, serialize
from ontoforge.io.rdf_import import canonical_model, graph_to_model, parse_ontology, parse_warning

HERE = pathlib.Path(__file__).parent
FIX = sorted(glob.glob(str(HERE / "fixtures" / "io" / "*.ttl")))
ROOT = HERE.parents[1]
EX = "https://example.org/t#"
PRE = f"@prefix : <{EX}> . @prefix owl: <{OWL}> . @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> . @prefix xsd: <{XSD}> . @prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .\n"


def ttl(body: str):
    return parse_ontology(PRE + body, "turtle")


def test_declarations_labels_deprecated_and_multilingual():
    m, w = ttl(':A a owl:Class ; rdfs:label "Véhicule"@fr , "Vehicle"@en ; rdfs:comment "c" ; owl:deprecated true .')
    a = m.classes[EX + "A"]
    assert a.labels == {"fr": "Véhicule", "en": "Vehicle"} and a.comments == {"": "c"} and a.deprecated


def test_punning_is_warned():
    m, w = ttl(":A a owl:Class , owl:NamedIndividual .")
    assert any("pun" in x.lower() for x in w)


def test_restrictions_all_kinds():
    m, _ = ttl("""
    :p a owl:ObjectProperty . :d a owl:DatatypeProperty . :B a owl:Class .
    :A a owl:Class ; rdfs:subClassOf
      [ a owl:Restriction ; owl:onProperty :p ; owl:someValuesFrom :B ] ,
      [ a owl:Restriction ; owl:onProperty :p ; owl:allValuesFrom :B ] ,
      [ a owl:Restriction ; owl:onProperty :p ; owl:minQualifiedCardinality 2 ; owl:onClass :B ] ,
      [ a owl:Restriction ; owl:onProperty :d ; owl:maxCardinality 1 ] ,
      [ a owl:Restriction ; owl:onProperty :p ; owl:hasSelf true ] ,
      [ a owl:Restriction ; owl:onProperty [ owl:inverseOf :p ] ; owl:someValuesFrom :B ] .""")
    kinds = sorted((r.kind, r.inverse, r.n) for r in m.classes[EX + "A"].restrictions)
    assert ("some", False, None) in kinds and ("only", False, None) in kinds and ("min", False, 2) in kinds
    assert ("max", False, 1) in kinds and ("self", False, None) in kinds and ("some", True, None) in kinds


def test_domain_multiple_is_intersection_union_is_union():
    m, _ = ttl("""
    :p a owl:ObjectProperty ; rdfs:domain :A , :B ; rdfs:range [ a owl:Class ; owl:unionOf ( :C :D ) ] .
    :A a owl:Class . :B a owl:Class . :C a owl:Class . :D a owl:Class .""")
    p = m.object_properties[EX + "p"]
    assert sorted(p.domain) == [EX + "A", EX + "B"] and p.domain_union == []
    assert sorted(p.range_union) == [EX + "C", EX + "D"] and p.range == []


def test_untyped_rdf_property_is_typed_with_warning():
    m, w = ttl(":p a rdf:Property ; rdfs:range xsd:string . :q a rdf:Property ; rdfs:range :C . :C a owl:Class .")
    assert EX + "p" in m.datatype_properties and EX + "q" in m.object_properties
    assert any("rdf:Property" in x or "Property" in x for x in w)


def test_unmapped_is_kept_and_warned():
    m, w = parse_ontology(pathlib.Path(FIX[-1]).read_text(), "turtle")
    assert m.unmapped and any(parse_warning(x)["code"] == "unmapped_triple" for x in w)


def test_individuals_negative_alldifferent():
    m, _ = ttl("""
    :C a owl:Class . :p a owl:ObjectProperty . :a a owl:NamedIndividual , :C ; :p :b ; owl:sameAs :c .
    :b a owl:NamedIndividual . :c a owl:NamedIndividual .
    [] a owl:AllDifferent ; owl:distinctMembers ( :a :b ) .
    [] a owl:NegativePropertyAssertion ; owl:sourceIndividual :a ; owl:assertionProperty :p ; owl:targetIndividual :c .""")
    a = m.individuals[EX + "a"]
    assert EX + "c" in a.same_as and any(f.negative for f in a.facts) and any(not f.negative for f in a.facts)
    assert m.all_different == [[EX + "a", EX + "b"]]


@pytest.mark.parametrize("fmt", ["turtle", "xml", "json-ld", "nt", "n3"])
def test_formats_detected_and_equivalent(fmt):
    src = pathlib.Path(ROOT / "samples/automaint/automaint.ttl").read_text()
    m, _ = parse_ontology(src, "turtle")
    out = serialize(m, "xml" if fmt == "xml" else fmt) if fmt != "n3" else serialize(m, "turtle")
    m2, _ = parse_ontology(out)  # détection par le contenu
    m2.meta.prefixes = m.meta.prefixes
    assert m2 == m


def test_detect_by_extension_and_bytes():
    m, _ = parse_ontology(b"<a:a> <a:b> <a:c> .", filename="x.nt")
    assert m is not None
    m, _ = parse_ontology((PRE + ":A a owl:Class .").encode(), filename="onto.ttl")
    assert EX + "A" in m.classes


@pytest.mark.parametrize("path", FIX + [str(ROOT / "samples/trap/trap.ttl"), str(ROOT / "samples/automaint/automaint.ttl"),
                                       str(ROOT / "samples/automaint/automaint.owl")])
def test_roundtrip_identical(path):
    m, _ = parse_ontology(pathlib.Path(path).read_text(), filename=path)
    m2, _ = graph_to_model(model_to_graph(m))
    assert m2 == canonical_model(m)
    m3, _ = parse_ontology(serialize(m, "turtle"), "turtle")
    assert m3 == m


def test_automaint_owl_equals_ttl_and_is_clean():
    a, wa = parse_ontology((ROOT / "samples/automaint/automaint.ttl").read_text(), filename="a.ttl")
    b, wb = parse_ontology((ROOT / "samples/automaint/automaint.owl").read_text(), filename="a.owl")
    assert a.classes == b.classes and a.object_properties == b.object_properties
    assert not a.unmapped and all(parse_warning(x)["code"] == "format" for x in wa)
    assert len(a.classes) >= 20
    assert "http://www.w3.org/2001/XMLSchema#date" not in serialize(a)


def test_export_is_readable_turtle():
    m, _ = ttl(':A a owl:Class ; rdfs:label "A"@en .')
    s = serialize(m)
    assert "@prefix" in s and "owl:Class" in s
