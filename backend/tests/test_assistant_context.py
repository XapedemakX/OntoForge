"""L16 — assistant global : /api/assistant/chat avec contexte, actions validées, repli déterministe (mock) sur automaint."""
import pytest
from fastapi.testclient import TestClient

from ontoforge.main import app

AM = "https://w3id.org/ontoforge/automaint#"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("ONTOFORGE_DATA", str(tmp_path))
    monkeypatch.setenv("ONTOFORGE_LLM_PROVIDER", "mock")
    return TestClient(app)


@pytest.fixture
def pid(client):
    r = client.post("/api/projects", json={"name": "AM", "sample": "automaint"})
    assert r.status_code in (200, 201), r.text
    return r.json()["id"]


def ask(client, pid, text, ctx=None):
    r = client.post("/api/assistant/chat", json={"project_id": pid, "messages": [{"role": "user", "content": text}],
                                                 "context": ctx or {"screen": "editor", "projectId": pid}})
    assert r.status_code == 200, r.text
    return r.json()


def apply(client, pid, action):
    r = client.post(f"/api/projects/{pid}/ops", json={"ops": action["payload"]["ops"]})
    assert r.status_code == 200 and r.json()["ok"], r.text
    return r.json()["project"]


def test_add_class_with_property_and_unit(client, pid):
    j = ask(client, pid, "ajoute la classe Pneu sous Pièce avec une propriété pression en bar")
    a = j["actions"][0]
    assert a["kind"] == "ops" and not j["warnings"]
    ops = a["payload"]["ops"]
    assert ops[0]["op"] == "add_class" and ops[0]["iri"] == AM + "Pneu" and ops[0]["parent"] == AM + "Part"
    assert ops[1]["op"] == "add_datatype_property" and ops[1]["iri"] == AM + "pression" and ops[1]["range"].endswith("decimal")
    assert any("Pneu" in x["text"] and "Pièce" in x["text"] for x in a["payload"]["preview"])
    p = apply(client, pid, a)
    assert AM + "Pneu" in p["onto"]["classes"] and AM + "pression" in p["onto"]["datatype_properties"]
    assert p["onto"]["datatype_properties"][AM + "pression"]["domain"] == [AM + "Pneu"]
    assert client.post(f"/api/projects/{pid}/ops/undo").status_code == 200  # annulable


def test_unknown_parent_is_flagged(client, pid):
    j = ask(client, pid, "ajoute la classe Pneu sous Truc")
    assert j["actions"][0]["payload"]["ops"][0].get("parent") is None and j["warnings"]


def test_add_property_to_class(client, pid):
    j = ask(client, pid, "ajoute la propriété poids de type entier à Véhicule")
    op = j["actions"][0]["payload"]["ops"][0]
    assert op["domain"] == [AM + "Vehicle"] and op["range"].endswith("integer")
    j = ask(client, pid, "ajoute la propriété couleur à cette classe", {"screen": "editor", "selection": {"kind": "class", "id": AM + "Vehicle"}})
    assert j["actions"][0]["payload"]["ops"][0]["domain"] == [AM + "Vehicle"]


def test_make_required_and_delete(client, pid):
    j = ask(client, pid, "rends immatriculation obligatoire")
    op = j["actions"][0]["payload"]["ops"][0]
    assert op["op"] == "set_restriction" and op["kind"] == "min" and op["n"] == 1 and op["iri"] == AM + "Vehicle"
    assert "obligatoire" in j["actions"][0]["payload"]["preview"][0]["text"]
    j = ask(client, pid, "supprime Technicien")
    assert j["actions"][0]["payload"]["ops"][0] == {"op": "delete_entity", "iri": AM + "Technician"}
    j = ask(client, pid, "supprime Machin")
    assert j["actions"] == []


def test_shape_constraint(client, pid):
    j = ask(client, pid, "ajoute une contrainte min 1 sur immatriculation dans la shape Véhicule")
    a = j["actions"][0]
    assert a["kind"] == "shapes" and a["payload"]["patches"][0]["constraints"] == {"min_count": 1}
    r = client.post("/api/assistant/shapes/apply", json={"project_id": pid, "patches": a["payload"]["patches"]})
    assert r.status_code == 200 and r.json()["applied"] == 1
    shapes = r.json()["project"]["shapes"]["shapes"]
    assert any(ps.get("min_count") == 1 and ps["path"]["iri"].endswith("registrationNumber") for s in shapes.values() for ps in s["properties"])
    assert client.post(f"/api/projects/{pid}/ops/undo").status_code == 200
    bad = client.post("/api/assistant/shapes/apply", json={"project_id": pid, "patches": [{"class": "Inconnue", "property": "x", "constraints": {"min_count": 1}}]})
    assert bad.status_code == 422


def test_guided_query_and_navigate(client, pid):
    j = ask(client, pid, "cherche les véhicules dont le kilométrage dépasse 100000")
    a = j["actions"][0]
    assert a["kind"] == "guided_query" and a["payload"]["guided"] and a["payload"].get("sparql")
    j = ask(client, pid, "ouvre les shapes")
    assert j["actions"][0] == {"kind": "navigate", "payload": {"screen": "shapes"}, "summary": "Ouvrir : shapes"}


def test_invalid_llm_ops_are_dropped(client, pid):
    from ontoforge.assistant import agent
    from ontoforge.projects import store
    p = store.get(pid)
    acts, w = agent.build_actions(p, [{"kind": "ops", "ops": [
        {"op": "add_class", "name": "Pneu", "parent": "Part", "iri": "http://evil.example/Pneu"},
        {"op": "add_subclass", "iri": "Inventée", "parent": "Part"},
        {"op": "delete_entity", "iri": "http://autre/Chose"},
        {"op": "rm_rf"}]}], None, {})
    ops = acts[0]["payload"]["ops"]
    assert len(ops) == 1 and ops[0]["iri"] == AM + "Pneu" and len(w) == 3


def test_without_context_stays_compatible(client, pid):
    r = client.post("/api/assistant/chat", json={"project_id": pid, "messages": [{"role": "user", "content": "un garage de réparation de véhicules"}]})
    assert r.status_code == 200 and "actions" in r.json()
    j = ask(client, pid, "un garage de réparation de véhicules")
    assert j["actions"] and j["actions"][0]["kind"] == "proposal"
