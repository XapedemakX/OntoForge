"""L34d : le cycle de sous-classes est refusé à la saisie (DSL, /ops) et ne fait plus échouer /analyze."""
import pytest
from fastapi.testclient import TestClient

from ontoforge.core.onto_model import OntClass
from ontoforge.editing import cycles
from ontoforge.io.dsl import parse_dsl
from ontoforge.main import app

B = "https://example.org/shop#"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("ONTOFORGE_DATA", str(tmp_path))
    monkeypatch.setenv("ONTOFORGE_LLM_PROVIDER", "mock")
    return TestClient(app)


def _set_ui(c, lang):
    assert c.put("/api/settings", json={"language": {"ui": lang, "labels": lang, "assistant": lang}}).status_code == 200


@pytest.fixture
def pid(client):
    r = client.post("/api/projects", json={"name": "Cycles", "sample": "automaint"})
    assert r.status_code == 201, r.text
    return r.json()["id"]


AM = "https://w3id.org/ontoforge/automaint#"


# ---- DSL --------------------------------------------------------------------------------------------------

def test_dsl_refuses_direct_and_indirect_cycles_with_the_line():
    m, errs = parse_dsl("@base <https://e.org/o#>\nElectricVehicle < Vehicle\nVehicle < ElectricVehicle")
    assert [e["line"] for e in errs] == [3] and set(errs[0]) == {"line", "message"}
    assert "Cycle de sous-classes" in errs[0]["message"] and "ElectricVehicle → Vehicle" in errs[0]["message"]
    assert m.classes["https://e.org/o#Vehicle"].sub_class_of == []  # la ligne refusée n'a aucun effet
    assert m.classes["https://e.org/o#ElectricVehicle"].sub_class_of == ["https://e.org/o#Vehicle"]
    _, errs = parse_dsl("@base <https://e.org/o#>\nA < B\nB < C\nC < A\nD < C")
    assert [e["line"] for e in errs] == [4] and "A → B → C" in errs[0]["message"]
    # autres lignes gardées ; sous-classe d'elle-même toujours refusée
    m, errs = parse_dsl("@base <https://e.org/o#>\nX < X\nY < Z")
    assert [e["line"] for e in errs] == [2] and "https://e.org/o#Y" in m.classes


def test_dsl_multi_parent_line_is_all_or_nothing():
    base, errs = parse_dsl("@base <https://e.org/o#>\nB < A")
    assert errs == []
    m, errs = parse_dsl("@base <https://e.org/o#>\nA < C, B", base)  # C passerait, B ferme le cycle
    assert len(errs) == 1 and m.classes["https://e.org/o#A"].sub_class_of == []


def test_dsl_equivalence_and_diamonds_are_not_cycles():
    m, errs = parse_dsl("@base <https://e.org/o#>\nA < B, C\nB < D\nC < D\nA = A2\nA2 < D")
    assert errs == []


def test_dsl_api_reports_cycle_in_french_and_english(client, pid):
    text = "@base <%s>\nVehicle < ElectricVehicle" % AM
    _set_ui(client, "fr")
    r = client.post(f"/api/projects/{pid}/dsl", json={"text": text, "merge": True}).json()
    assert [e["line"] for e in r["errors"]] == [2]
    assert "« ElectricVehicle » descend déjà de « Vehicle »" in r["errors"][0]["message"] and "fermerait la boucle" in r["errors"][0]["message"]
    assert r["project"]["onto"]["classes"][AM + "Vehicle"]["sub_class_of"] == []
    _set_ui(client, "en")
    r = client.post(f"/api/projects/{pid}/dsl", json={"text": text, "merge": True}).json()
    msg = r["errors"][0]["message"]
    assert msg == "Subclass cycle: “ElectricVehicle” already descends from “Vehicle” (ElectricVehicle → Vehicle); “Vehicle < ElectricVehicle” would close the loop."
    assert r["errors"][0]["line"] == 2
    # le projet reste analysable
    assert client.post(f"/api/projects/{pid}/analyze?target=curiosity").status_code == 200


# ---- /ops ----------------------------------------------------------------------------------------------------

def test_ops_refuse_cycle_with_clear_message_and_index(client, pid):
    op = {"op": "add_subclass", "iri": AM + "Vehicle", "parent": AM + "ElectricVehicle"}
    _set_ui(client, "fr")
    r = client.post(f"/api/projects/{pid}/ops", json={"ops": [{"op": "add_class", "name": "Zed", "label": "Zed"}, op]}).json()
    assert r["ok"] is False and r["errors"][0]["index"] == 1
    assert r["errors"][0]["message"].startswith("Cycle de sous-classes : « ElectricVehicle » descend déjà de « Vehicle »")
    assert AM + "Zed" not in client.get(f"/api/projects/{pid}").json()["onto"]["classes"]  # tout ou rien
    _set_ui(client, "en")
    r = client.post(f"/api/projects/{pid}/ops", json={"ops": [op]}).json()
    assert r["errors"][0]["message"] == "Subclass cycle: “ElectricVehicle” already descends from “Vehicle” (ElectricVehicle → Vehicle); “Vehicle < ElectricVehicle” would close the loop."
    r = client.post(f"/api/projects/{pid}/ops", json={"ops": [{"op": "add_subclass", "iri": AM + "Vehicle", "parent": AM + "Vehicle"}]}).json()
    assert r["errors"][0]["message"] == "Subclass cycle: a class cannot be its own subclass"


def test_ops_two_steps_in_one_batch_cycle_is_refused(client, pid):
    r = client.post(f"/api/projects/{pid}/ops", json={"ops": [
        {"op": "add_class", "name": "Bike", "label": "Bike"},
        {"op": "add_subclass", "iri": AM + "Bike", "parent": AM + "Vehicle"},
        {"op": "add_subclass", "iri": AM + "Vehicle", "parent": AM + "Bike"}]}).json()
    assert r["ok"] is False and r["errors"][0]["index"] == 2 and "Cycle de sous-classes" in r["errors"][0]["message"]


# ---- /analyze avec un cycle déjà présent (import) -------------------------------------------------------------

def _inject_cycles(client, pid):
    p = client.get(f"/api/projects/{pid}").json()
    cl = p["onto"]["classes"]
    cl[AM + "Vehicle"]["sub_class_of"].append(AM + "ElectricVehicle")  # 2-cycle avec ElectricVehicle < Vehicle
    cl[AM + "Party"]["sub_class_of"].append(AM + "Person")  # 2-cycle avec Person < Party
    cl[AM + "Customer"]["sub_class_of"].append(AM + "Customer")  # auto-boucle
    assert client.put(f"/api/projects/{pid}/onto", json=p["onto"]).status_code == 200


@pytest.mark.parametrize("target", ["curiosity", "neo4j"])
def test_analyze_survives_existing_cycles_with_a_readable_finding(client, pid, target):
    _inject_cycles(client, pid)
    r = client.post(f"/api/projects/{pid}/analyze?target={target}")
    assert r.status_code == 200, r.text
    pg = r.json()
    notes = [f for f in pg["findings"] if f["rule"] == "BP03"]
    assert {f["subject"] for f in notes} == {AM + "Customer", AM + "ElectricVehicle", AM + "Party"}
    assert all(f["severity"] == "info" and f["title"] == "Cycle de sous-classes" and f["detail"] for f in notes)
    assert any("forment un cycle de sous-classes" in f["detail"] for f in notes)
    assert any("sous-classe d'elle-même" in f["detail"] for f in notes)
    assert sum(1 for f in pg["findings"] if f["severity"] in ("auto", "review", "lost")) > 0  # la transposition produit toujours ses constats
    assert pg["node_types"]
    # arbitrage, génération et conformité ne cassent pas non plus
    assert client.post(f"/api/projects/{pid}/decisions/{target}/accept-recommended?include_lost=true").status_code == 200
    assert client.get(f"/api/projects/{pid}/generate/{target}").status_code == 200
    assert client.get(f"/api/projects/{pid}/conformance").status_code == 200


def test_cycle_finding_is_translated_in_english(client, pid):
    _inject_cycles(client, pid)
    _set_ui(client, "en")
    notes = [f for f in client.post(f"/api/projects/{pid}/analyze?target=curiosity").json()["findings"] if f["rule"] == "BP03"]
    assert notes and all(f["title"] == "Subclass cycle" for f in notes)
    multi = next(f for f in notes if f["subject"] == AM + "ElectricVehicle")
    assert multi["detail"].startswith("The classes am:ElectricVehicle, am:Vehicle form a subclass cycle: in OWL 2 they are equivalent")
    loop = next(f for f in notes if f["subject"] == AM + "Customer")
    assert loop["detail"] == "The class am:Customer is declared a subclass of itself: in OWL 2 this axiom has no effect. Remove it."


def test_every_cycle_shape_through_the_engine():
    """Cycles de 2, 3 classes, auto-boucle, feuille sous un cycle, plusieurs parents : aucune exception, pour les deux cibles."""
    from ontoforge.mapping.engine import analyze
    for text in ("A\nB < A\nA < B", "A < B\nB < C\nC < A", "A < A", "A < B\nB < A\nC < A\nD < C", "A < B, C\nB < A\nC < B"):
        m, _ = parse_dsl("@base <https://e.org/o#>\n" + text)
        for line in text.splitlines():  # on contourne le refus de la saisie en posant les liens à la main
            if "<" in line:
                kid, parents = line.split("<")
                for par in [x.strip() for x in parents.split(",")]:
                    for n in (kid.strip(), par):
                        m.classes.setdefault("https://e.org/o#" + n, OntClass(iri="https://e.org/o#" + n))
                    c = m.classes["https://e.org/o#" + kid.strip()]
                    if "https://e.org/o#" + par not in c.sub_class_of:
                        c.sub_class_of.append("https://e.org/o#" + par)
        assert cycles.find_cycles(m), text
        for target in ("curiosity", "neo4j"):
            pg = analyze(m, None, target, {})
            assert any(f.rule == "BP03" and f.severity == "info" for f in pg.findings), (text, target)


def test_find_cycles_and_paths():
    m, _ = parse_dsl("@base <https://e.org/o#>\nA < B\nB < C\nX < A")
    assert cycles.find_cycles(m) == []
    assert cycles.subclass_path(m, "https://e.org/o#X", "https://e.org/o#C") == ["https://e.org/o#X", "https://e.org/o#A", "https://e.org/o#B", "https://e.org/o#C"]
    assert cycles.closing_path(m, "https://e.org/o#C", "https://e.org/o#X")  # C < X fermerait la boucle
    assert cycles.closing_path(m, "https://e.org/o#X", "https://e.org/o#C") is None
