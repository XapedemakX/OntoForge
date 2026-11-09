"""L32 : POST /api/projects/{id}/reason (HermiT). Les tests qui lancent Java sont ignorés si Java ou owlready2 manquent."""
import pathlib

import pytest
import rdflib
from fastapi.testclient import TestClient

from ontoforge.conformance import hermit as hm

FIX = pathlib.Path(__file__).parent / "fixtures" / "reasoner"
HAS = hm.availability()["available"]
needs = pytest.mark.skipif(not HAS, reason="Java ou owlready2 absent")
NS = "http://example.org/reason#"


def graph(name):
    return rdflib.Graph().parse(FIX / f"{name}.ttl")


@needs
def test_consistent():
    r = hm.run_hermit(graph("consistent"))
    assert r["status"] == "ok" and r["consistent"] is True and r["unsatisfiable"] == []
    assert r["version"].startswith("HermiT 1.3.8") and r["duration_ms"] > 0
    assert r["dl"]["conformant"] is True and r["explanation"] is None


@needs
def test_inconsistent_two_disjoint_classes():
    r = hm.run_hermit(graph("inconsistent"))
    assert r["consistent"] is False
    ex = r["explanation"]
    assert ex["justification"] is False and ex["source"] == "heuristic"
    assert ex["individuals"] == [NS + "rex"] and set(ex["classes"]) == {NS + "Dog", NS + "Cat"}


@needs
def test_unsatisfiable_class():
    r = hm.run_hermit(graph("unsat"))
    assert r["consistent"] is True and r["unsatisfiable"] == [NS + "Chimera"]


@needs
def test_inferred_subclass_and_equivalence_and_reclassification():
    r = hm.run_hermit(graph("definition"))
    subs = {(x["sub"], x["sup"]) for x in r["hierarchy"]["new_subclass"]}
    assert (NS + "Driver", NS + "Motorist") in subs and (NS + "Motorist", NS + "CarOwner") in subs
    assert [sorted(g) for g in r["hierarchy"]["new_equivalent"]] == [[NS + "CarOwner", NS + "Twin"]]
    assert r["reclassified"] == [{"individual": NS + "alice", "declared": [NS + "Person"], "inferred": [NS + "Motorist"]}]


@needs
def test_non_dl_warns_but_runs():
    g = graph("consistent")
    g.add((rdflib.URIRef(NS + "Dog"), rdflib.URIRef(NS + "p"), rdflib.Literal(1)))  # propriété non déclarée : sort d'OWL 2 DL
    r = hm.run_hermit(g)
    assert r["dl"]["conformant"] is False and r["status"] == "ok"
    assert "OWL 2 DL" in r["warnings"][0]


@needs
def test_timeout_kills_and_cleans(monkeypatch, tmp_path):
    monkeypatch.setenv("TMPDIR", str(tmp_path))
    import tempfile
    tempfile.tempdir = None
    real = hm.locate()
    # Java dort 20 s : le délai de 1 s doit couper le processus
    monkeypatch.setattr(hm, "locate", lambda: hm.Setup(java="/bin/sleep", classpath=real.classpath, jar=real.jar, version=real.version))
    real_popen = hm.subprocess.Popen
    monkeypatch.setattr(hm.subprocess, "Popen", lambda cmd, **kw: real_popen(["/bin/sleep", "20"], **kw))
    r = hm.run_hermit(graph("consistent"), timeout=1)
    tempfile.tempdir = None
    assert r["status"] == "timeout" and r["consistent"] is None and r["duration_ms"] < 5000
    assert not list(tmp_path.glob("ontoforge-hermit-*"))


def _client():
    from ontoforge.main import app
    return TestClient(app)


def _project(c):
    r = c.post("/api/projects", json={"name": "reason", "sample": "automaint"})
    assert r.status_code in (200, 201), r.text
    return r.json()["id"]


def test_api_501_without_java(monkeypatch):
    def boom():
        raise hm.HermitUnavailable("java")
    monkeypatch.setattr(hm, "locate", boom)
    c = _client()
    r = c.post(f"/api/projects/{_project(c)}/reason", json={"reasoner": "hermit"})
    assert r.status_code == 501 and "Java" in r.json()["detail"] and "WITH_REASONER" in r.json()["detail"]


def test_api_501_without_owlready2(monkeypatch):
    def boom():
        raise hm.HermitUnavailable("owlready2")
    monkeypatch.setattr(hm, "locate", boom)
    c = _client()
    r = c.post(f"/api/projects/{_project(c)}/reason", json={})
    assert r.status_code == 501 and "owlready2" in r.json()["detail"]


def test_api_unknown_reasoner():
    c = _client()
    assert c.post(f"/api/projects/{_project(c)}/reason", json={"reasoner": "pellet"}).status_code == 422


@needs
def test_api_ok():
    c = _client()
    r = c.post(f"/api/projects/{_project(c)}/reason", json={"reasoner": "hermit"})
    assert r.status_code == 200, r.text
    assert r.json()["consistent"] is True and r.json()["status"] == "ok"


# ---- Krakie ----------------------------------------------------------------------------------------------
@pytest.mark.parametrize("msg", ["raisonne", "Lance le raisonneur", "vérifie la cohérence", "Vérifie la cohérence de l'ontologie", "run the reasoner",
                                 "Check consistency", "reason over the ontology", "is the ontology consistent?"])
def test_krakie_intent_matches(msg):
    from ontoforge.assistant import reasoning
    assert reasoning.matches(msg)


@pytest.mark.parametrize("msg", ["ajoute la classe Pneu", "open the shapes", "reasoning about tyres is hard"])
def test_krakie_intent_ignores_others(msg):
    from ontoforge.assistant import reasoning
    assert not reasoning.matches(msg)


def _answer(msg, lang, monkeypatch=None):
    from ontoforge.assistant import reasoning
    from ontoforge.io.rdf_export import model_to_graph  # noqa: F401
    from ontoforge.projects import store
    c = _client()
    pid = _project(c)
    return reasoning.answer(store.get(pid), msg, lang)


@needs
def test_krakie_summary_fr_en():
    fr = _answer("vérifie la cohérence", "fr")
    assert "cohérente" in fr["reply"] and fr["actions"][0]["screen"] == "conformite"
    en = _answer("run the reasoner", "en")
    assert "consistent" in en["reply"] and "HermiT" in en["reply"]


def test_krakie_unavailable(monkeypatch):
    def boom():
        raise hm.HermitUnavailable("java")
    monkeypatch.setattr(hm, "locate", boom)
    r = _answer("raisonne", "fr")
    assert "Java" in r["reply"] and r["actions"] == []
