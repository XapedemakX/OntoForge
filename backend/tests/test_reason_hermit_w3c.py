"""L32, relecture W3C it1 : cas sémantiques vérifiés contre HermiT réel (ignorés sans Java ni owlready2)."""
import pytest
import rdflib

from ontoforge.conformance import hermit as hm

needs = pytest.mark.skipif(not hm.availability()["available"], reason="Java ou owlready2 absent")
NS = "http://ex.org/t#"
HEAD = """@prefix : <http://ex.org/t#> . @prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> . @prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
<http://ex.org/t> a owl:Ontology .
"""


def run(ttl, **kw):
    return hm.run_hermit(rdflib.Graph().parse(data=HEAD + ttl, format="turtle"), timeout=60, **kw)


# ---- incohérences ----------------------------------------------------------------------------------------------
@needs
def test_inconsistent_by_cardinality_no_false_claim():
    r = run(""":p a owl:ObjectProperty . :C a owl:Class ; rdfs:subClassOf [ a owl:Restriction ; owl:onProperty :p ; owl:maxCardinality 1 ] .
               :x a :C ; :p :y , :z . :y a owl:NamedIndividual . :z a owl:NamedIndividual . :y owl:differentFrom :z .""")
    ex = r["explanation"]
    assert r["consistent"] is False and ex["justification"] is False and ex["items"] == []
    assert "cardinalités" in ex["note"] and "clés" in ex["note"]  # la note n'exclut plus les autres causes


@needs
def test_inconsistent_by_domain_range_found_by_heuristic():
    r = run(""":A a owl:Class . :B a owl:Class . :A owl:disjointWith :B . :p a owl:ObjectProperty ; rdfs:domain :A .
               :x a :B , owl:NamedIndividual ; :p :y . :y a owl:NamedIndividual .""")
    assert r["consistent"] is False
    it = r["explanation"]["items"]
    assert it and it[0]["individual"] == NS + "x" and it[0]["kind"] == "disjoint" and "domaine" in it[0]["message"]


@needs
def test_inconsistent_by_range():
    r = run(""":A a owl:Class . :B a owl:Class . :A owl:disjointWith :B . :p a owl:ObjectProperty ; rdfs:range :A .
               :x a owl:NamedIndividual ; :p :y . :y a :B , owl:NamedIndividual .""", lang="en")
    it = r["explanation"]["items"]
    assert r["consistent"] is False and it[0]["individual"] == NS + "y" and "range" in it[0]["message"]


@needs
def test_inconsistent_by_haskey():
    r = run(""":k a owl:DatatypeProperty . :A a owl:Class ; owl:hasKey ( :k ) . :x a :A , owl:NamedIndividual ; :k "1" .
               :y a :A , owl:NamedIndividual ; :k "1" . :x owl:differentFrom :y .""")
    assert r["consistent"] is False and r["explanation"]["justification"] is False


# ---- classes insatisfiables -----------------------------------------------------------------------------------
@needs
def test_unsat_via_some_values_from_empty_class():
    r = run(""":p a owl:ObjectProperty . :A a owl:Class . :B a owl:Class . :A owl:disjointWith :B .
               :E a owl:Class ; rdfs:subClassOf :A , :B .
               :C a owl:Class ; rdfs:subClassOf [ a owl:Restriction ; owl:onProperty :p ; owl:someValuesFrom :E ] .""")
    assert r["consistent"] is True and r["unsatisfiable"] == [NS + "C", NS + "E"]


@needs
def test_unsat_via_all_values_from_and_disjointness():
    r = run(""":p a owl:ObjectProperty . :A a owl:Class . :B a owl:Class . :A owl:disjointWith :B .
               :C a owl:Class ; rdfs:subClassOf [ a owl:Restriction ; owl:onProperty :p ; owl:allValuesFrom :A ] ,
                                                [ a owl:Restriction ; owl:onProperty :p ; owl:someValuesFrom :B ] .""")
    assert r["unsatisfiable"] == [NS + "C"] and r["hierarchy"]["new_subclass"] == []


# ---- inférences -----------------------------------------------------------------------------------------------
@needs
def test_subclass_inferred_through_equivalent_intersection():
    r = run(""":p a owl:ObjectProperty . :Person a owl:Class . :Car a owl:Class .
               :Driver a owl:Class ; owl:equivalentClass [ a owl:Class ; owl:intersectionOf ( :Person [ a owl:Restriction ; owl:onProperty :p ; owl:someValuesFrom :Car ] ) ] .
               :Trucker a owl:Class ; rdfs:subClassOf :Person , [ a owl:Restriction ; owl:onProperty :p ; owl:someValuesFrom :Car ] .""")
    assert r["hierarchy"]["new_subclass"] == [{"sub": NS + "Trucker", "sup": NS + "Driver"}]
    # Driver ⊑ Person vient d'un conjoint nommé de la définition : déjà déclaré, pas proposé


@needs
def test_reclassified_by_has_value():
    r = run(""":p a owl:ObjectProperty . :Fr a owl:NamedIndividual .
               :French a owl:Class ; owl:equivalentClass [ a owl:Restriction ; owl:onProperty :p ; owl:hasValue :Fr ] .
               :x a owl:NamedIndividual ; :p :Fr .""")
    assert r["reclassified"] == [{"individual": NS + "x", "declared": [], "inferred": [NS + "French"]}]


@needs
def test_equivalence_representative_does_not_produce_redundant_subclass():
    """HermiT n'écrit qu'un représentant par groupe équivalent : C ⊑ B déclaré et A ≡ B inféré ne doit pas proposer C ⊑ A."""
    r = run(""":p a owl:ObjectProperty . :X a owl:Class .
               :A a owl:Class ; owl:equivalentClass [ a owl:Restriction ; owl:onProperty :p ; owl:someValuesFrom :X ] .
               :B a owl:Class ; owl:equivalentClass [ a owl:Restriction ; owl:onProperty :p ; owl:someValuesFrom :X ] .
               :C a owl:Class ; rdfs:subClassOf :B . :D a owl:Class ; rdfs:subClassOf :A .""")
    assert r["hierarchy"]["new_equivalent"] == [[NS + "A", NS + "B"]]
    assert r["hierarchy"]["new_subclass"] == []


@needs
def test_trivial_axioms_not_proposed_and_thing_equivalence_warned():
    r = run(""":A a owl:Class ; owl:equivalentClass owl:Thing . :B a owl:Class . :C a owl:Class ; rdfs:subClassOf :C .""")
    assert r["hierarchy"]["new_subclass"] == [] and r["hierarchy"]["new_equivalent"] == []
    assert any("owl:Thing" in w and w.startswith("A ") for w in r["warnings"])


# ---- entrées : imports, datatypes, hors DL --------------------------------------------------------------------
@needs
def test_imports_are_not_fetched():
    r = run("""<http://ex.org/t> owl:imports <http://example.invalid/nothing.owl> . :A a owl:Class .""")
    assert r["status"] == "ok" and r["consistent"] is True
    assert any("owl:imports" in w and "example.invalid" in w for w in r["warnings"])


@needs
def test_non_owl2_datatype_warns():
    r = run(""":d a owl:DatatypeProperty ; rdfs:range xsd:date . :x a owl:NamedIndividual ; :d "2020-01-01"^^xsd:date .""")
    assert r["status"] == "ok" and r["dl"]["conformant"] is False and "OWL 2 DL" in r["warnings"][0]


@needs
def test_non_dl_hermit_refusal_is_explained():
    r = run(""":p a owl:ObjectProperty , owl:TransitiveProperty .
               :C a owl:Class ; rdfs:subClassOf [ a owl:Restriction ; owl:onProperty :p ; owl:maxCardinality 1 ] .""")
    assert r["status"] == "error" and r["consistent"] is None and r["dl"]["conformant"] is False
    assert "Non-simple" in r["error"] and "OWL 2 DL" in r["error"]


def test_krakie_reasoning_hooked_in_agent_run(monkeypatch):
    """L'intention « raisonne » passe par assistant.agent.run (et pas seulement par reasoning.answer)."""
    from ontoforge.assistant import agent, reasoning
    seen = {}

    def fake(project, message, lang):
        seen["m"] = message
        return {"reply": "ok", "actions": [], "warnings": []}
    monkeypatch.setattr(reasoning, "answer", fake)

    class P:
        onto = None
    r = agent.run(P(), [{"role": "user", "content": "raisonne"}], {})
    assert seen["m"] == "raisonne" and r["reply"] == "ok"
