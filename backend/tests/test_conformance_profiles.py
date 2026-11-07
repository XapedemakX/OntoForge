"""Tests de conformité W3C (lot L2) : DL, profils EL/QL/RL, lint W01–W07, raisonneur."""
import pathlib

import rdflib
import pytest

from ontoforge.conformance.profiles import check_conformance
from ontoforge.conformance.reasoner import reason
from ontoforge.conformance.report import ConformanceReport
from ontoforge.io.rdf_import import graph_to_model

ROOT = pathlib.Path(__file__).resolve().parents[2]
PRE = "@prefix : <http://ex.org/> . @prefix owl: <http://www.w3.org/2002/07/owl#> . " \
      "@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> . @prefix xsd: <http://www.w3.org/2001/XMLSchema#> . " \
      "<http://ex.org> a owl:Ontology . "


def run(ttl: str, **kw) -> ConformanceReport:
    g = rdflib.Graph().parse(data=PRE + ttl if not ttl.startswith("@") else ttl, format="turtle")
    m, _ = graph_to_model(g)
    return check_conformance(m, g, **kw)


def load(path: str) -> ConformanceReport:
    g = rdflib.Graph().parse(ROOT / path)
    m, _ = graph_to_model(g)
    return check_conformance(m, g)


def test_trap_is_owl2_dl_without_error():
    r = load("samples/trap/trap.ttl")
    assert r.profiles["DL"] is True
    assert [i for i in r.issues if i.level == "error"] == []
    assert r.profiles["EL"] is r.profiles["QL"] is r.profiles["RL"] is False
    assert r.reasoner.consistent is True  # grâce au contournement prp-key
    assert r.reasoner.unsatisfiable == []


def test_trap_profile_reasons_match_oracle():
    r = load("samples/trap/trap.ttl")
    j = lambda p: " ".join(r.profile_violations[p])  # noqa: E731
    assert "Garage" in j("EL") and "ObjectInverseOf" in j("EL") and "ObjectUnionOf" in j("EL")
    assert "hasRepairOrder" in j("EL")
    assert "Vehicle" in j("QL") and "HasKey" in j("QL") and "vehicleBrand" in j("QL") and "isComponentOf" in j("QL")
    assert "ElectricVehicle" in j("RL") and "ServiceProvider" in j("RL") and "interchangeableWith" in j("RL")
    assert "ModelYear" in j("RL")


@pytest.mark.parametrize("code", ["W01", "W02", "W03", "W04", "W05", "W06", "W07"])
def test_trap_nondl_triggers_each_rule(code):
    r = load("samples/trap/trap-nondl.ttl")
    assert code in r.codes()
    assert r.profiles["DL"] is False


def test_trap_nondl_details():
    r = load("samples/trap/trap-nondl.ttl")
    subj = lambda c: {i.subject.rsplit("#", 1)[-1] for i in r.issues if i.code == c and i.subject}  # noqa: E731
    assert {"purchaseDate", "modelYear", "nickname"} <= subj("W01")
    assert {"untypedLink", "UndeclaredThing", "usesUndeclared"} <= subj("W02")
    assert {"isPartOf", "hasPart"} <= subj("W03")
    assert {"colour", "Euro"} <= subj("W04")
    assert {"serial", "related"} <= subj("W05")
    assert "GhostVehicle" in subj("W06")
    assert {"BP03"} <= r.codes()  # cycle Alpha/Beta
    assert all(i.message and i.level in ("error", "warning", "info") for i in r.issues)


def test_el_ontology():
    r = run(":A a owl:Class . :B a owl:Class . :p a owl:ObjectProperty , owl:TransitiveProperty . "
            ":A rdfs:subClassOf [ a owl:Restriction ; owl:onProperty :p ; owl:someValuesFrom :B ] .")
    assert r.profiles["EL"] and r.profiles["DL"]
    assert not r.profiles["QL"]  # transitive + qualified some en sous-classe n'est pas ici : transitive suffit
    r2 = run(":A a owl:Class . :B a owl:Class . :p a owl:ObjectProperty , owl:FunctionalProperty .")
    assert not r2.profiles["EL"] and r2.profiles["RL"]


def test_ql_ontology():
    r = run(":A a owl:Class . :B a owl:Class . :p a owl:ObjectProperty ; owl:inverseOf :q . :q a owl:ObjectProperty . "
            ":A rdfs:subClassOf [ a owl:Restriction ; owl:onProperty :p ; owl:someValuesFrom :B ] . "
            ":A owl:disjointWith :B . "
            "[ a owl:Restriction ; owl:onProperty :p ; owl:someValuesFrom owl:Thing ] rdfs:subClassOf :B .")
    assert r.profiles["QL"], r.profile_violations["QL"]
    assert not r.profiles["EL"]  # inverseOf
    r2 = run(":A a owl:Class . :B a owl:Class . :p a owl:ObjectProperty . "
             "[ a owl:Restriction ; owl:onProperty :p ; owl:someValuesFrom :B ] rdfs:subClassOf :A .")
    assert not r2.profiles["QL"] and r2.profiles["EL"]  # filler qualifié en sous-classe


def test_rl_ontology():
    r = run(":A a owl:Class . :B a owl:Class . :C a owl:Class . :p a owl:ObjectProperty , owl:FunctionalProperty . "
            ":A rdfs:subClassOf [ a owl:Restriction ; owl:onProperty :p ; owl:allValuesFrom :B ] . "
            "[ owl:unionOf ( :A :B ) ] rdfs:subClassOf :C .")
    assert r.profiles["RL"], r.profile_violations["RL"]
    assert not r.profiles["EL"] and not r.profiles["QL"]
    r2 = run(":A a owl:Class . :B a owl:Class . :p a owl:ObjectProperty . "
             ":A rdfs:subClassOf [ owl:unionOf ( :A :B ) ] .")
    assert not r2.profiles["RL"] and "ObjectUnionOf" in " ".join(r2.profile_violations["RL"])


def test_w03_via_super_property_of_chain():
    r = run(":a a owl:ObjectProperty . :b a owl:ObjectProperty . :c a owl:ObjectProperty ; owl:propertyChainAxiom ( :a :b ) . "
            ":c rdfs:subPropertyOf :d . :d a owl:ObjectProperty , owl:IrreflexiveProperty .")
    assert "W03" in r.codes() and r.profiles["DL"] is False


def test_reasoner_prp_key_workaround():
    ttl = (":V a owl:Class ; owl:hasKey ( :vin ) . :vin a owl:DatatypeProperty . :x a :V ; :vin \"A\" . :y a :V ; :vin \"B\" . "
           ":x a owl:NamedIndividual . :y a owl:NamedIndividual . [] a owl:NegativePropertyAssertion ; "
           "owl:sourceIndividual :x ; owl:assertionProperty :vin ; owl:targetValue \"Z\" . :x owl:differentFrom :y .")
    g = rdflib.Graph().parse(data=PRE + ttl, format="turtle")
    info = reason(g)
    assert info.consistent is True  # sans contournement, owlrl rend x et y owl:sameAs
    g2 = rdflib.Graph().parse(data=PRE + ttl.replace('"B"', '"A"'), format="turtle")
    assert reason(g2).consistent is False  # clé partagée + differentFrom : vraie incohérence


def test_reasoner_never_raises_and_reports_hermit_notes():
    g = rdflib.Graph().parse(data=PRE + ":A a owl:Class .", format="turtle")
    info = reason(g, hermit=True, timeout=30)
    assert info.used in ("owlrl", "owlrl+hermit") and info.consistent is True


# ---- itération 1 de revue (journal/L2/review-w3c-it1.md) -------------------------------------
def test_it1_datatype_definition_allowed_in_all_profiles():
    r = run(":DT a rdfs:Datatype ; owl:equivalentClass xsd:integer .")
    assert r.profiles["EL"] and r.profiles["QL"] and r.profiles["RL"]
    r2 = run(":DT a rdfs:Datatype ; owl:equivalentClass [ a rdfs:Datatype ; owl:onDatatype xsd:integer ; "
             "owl:withRestrictions ( [ xsd:minInclusive 1 ] ) ] .")
    assert not r2.profiles["EL"] and "facettes" in " ".join(r2.profile_violations["RL"])


DR = ":d a owl:DatatypeProperty ; rdfs:range [ a rdfs:Datatype ; %s ] ."


@pytest.mark.parametrize("body,el,ql,rl", [
    ("owl:intersectionOf ( xsd:integer xsd:string )", True, True, True),
    ("owl:unionOf ( xsd:integer xsd:string )", False, False, False),
    ("owl:datatypeComplementOf xsd:integer", False, False, False),
    ('owl:oneOf ( "a" )', True, False, False),
    ('owl:oneOf ( "a" "b" )', False, False, False),
])
def test_it1_data_ranges_per_profile(body, el, ql, rl):
    r = run(DR % body)
    assert (r.profiles["EL"], r.profiles["QL"], r.profiles["RL"]) == (el, ql, rl), r.profile_violations


def test_it1_functional_data_property():
    r = run(":d a owl:DatatypeProperty , owl:FunctionalProperty .")
    assert r.profiles["EL"] and not r.profiles["QL"] and r.profiles["RL"]
    r2 = run(":p a owl:ObjectProperty , owl:FunctionalProperty .")
    assert not r2.profiles["EL"]


def test_it1_negative_assertions_ql_not_el():
    r = run(":p a owl:ObjectProperty . :a a owl:NamedIndividual . :b a owl:NamedIndividual . "
            "[] a owl:NegativePropertyAssertion ; owl:sourceIndividual :a ; owl:assertionProperty :p ; owl:targetIndividual :b .")
    assert r.profiles["EL"] and not r.profiles["QL"] and r.profiles["RL"]


def test_it1_ql_data_some_values_from_sub_requires_literal():
    base = ":A a owl:Class . :d a owl:DatatypeProperty . [ a owl:Restriction ; owl:onProperty :d ; owl:someValuesFrom %s ] rdfs:subClassOf :A ."
    assert run(base % "xsd:integer").profiles["QL"] is False
    assert run(base % "rdfs:Literal").profiles["QL"] is True


def test_it1_rl_owl_thing_forbidden():
    assert run(":A a owl:Class . owl:Thing rdfs:subClassOf :A .").profiles["RL"] is False
    assert run(":A a owl:Class . :A rdfs:subClassOf owl:Thing .").profiles["RL"] is False
    assert run(":A a owl:Class . :B a owl:Class . :A rdfs:subClassOf :B .").profiles["RL"] is True


def test_it1_ill_typed_literal():
    r = run(':A a owl:Class . :d a owl:DatatypeProperty . :x a :A ; :d "abc"^^xsd:integer .')
    assert any(i.code == "W01" and "mal typé" in i.message for i in r.issues) and r.profiles["DL"] is False
    assert not any("mal typé" in i.message for i in run(':A a owl:Class . :d a owl:DatatypeProperty . :x a :A ; :d "12"^^xsd:integer .').issues)
