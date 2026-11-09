"""L31 (relecture croisée) : toutes les intentions déterministes de Krakie répondent en français et en anglais,
après la reconstruction de assistant/agent.py (fusion corrompue). Mock LLM, projet automaint."""
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


def ask(client, pid, text, screen="editor"):
    r = client.post("/api/assistant/chat", json={"project_id": pid, "messages": [{"role": "user", "content": text}],
                                                 "context": {"screen": screen, "projectId": pid}})
    assert r.status_code == 200, r.text
    return r.json()


@pytest.mark.parametrize("text", ["ajoute la classe Pneu sous Pièce avec une propriété pression en bar",
                                  "add the class Tyre under Part with a property pressure in bar"])
def test_add_class_with_property(client, pid, text):
    a = ask(client, pid, text)["actions"][0]
    ops = a["payload"]["ops"]
    assert a["kind"] == "ops" and ops[0]["op"] == "add_class" and ops[0]["parent"] == AM + "Part"
    assert any(o["op"] == "add_datatype_property" for o in ops)


@pytest.mark.parametrize("text", ["ajoute la propriété poids de type entier à Véhicule", "add the property weight of type integer to Vehicle"])
def test_add_property(client, pid, text):
    op = ask(client, pid, text)["actions"][0]["payload"]["ops"][0]
    assert op["op"] == "add_datatype_property" and op["domain"] == [AM + "Vehicle"] and op["range"].endswith("integer")


@pytest.mark.parametrize("text", ["rends immatriculation obligatoire", "make registrationNumber required"])
def test_make_required(client, pid, text):
    op = ask(client, pid, text)["actions"][0]["payload"]["ops"][0]
    assert (op["op"], op["kind"], op["n"], op["iri"]) == ("set_restriction", "min", 1, AM + "Vehicle")


@pytest.mark.parametrize("text", ["supprime Technicien", "delete Technician", "remove the class Technician"])
def test_delete(client, pid, text):
    assert ask(client, pid, text)["actions"][0]["payload"]["ops"] == [{"op": "delete_entity", "iri": AM + "Technician"}]


@pytest.mark.parametrize("text", ["supprime Machin", "delete Gizmo"])
def test_delete_unknown_proposes_nothing(client, pid, text):
    assert ask(client, pid, text)["actions"] == []


@pytest.mark.parametrize("text", ["ajoute une contrainte min 1 sur immatriculation dans la shape Véhicule",
                                  "add a min constraint 1 on registrationNumber in shape Vehicle"])
def test_shape_constraint(client, pid, text):
    a = ask(client, pid, text)["actions"][0]
    assert a["kind"] == "shapes" and a["payload"]["patches"][0]["constraints"] == {"min_count": 1}


@pytest.mark.parametrize("text", ["cherche les véhicules dont le kilométrage dépasse 100000", "find the vehicles whose mileage exceeds 100000"])
def test_search_is_a_guided_query(client, pid, text):
    a = ask(client, pid, text)["actions"][0]
    assert a["kind"] == "guided_query" and a["payload"]["guided"]


@pytest.mark.parametrize("text", ["ouvre les shapes", "open the shapes"])
def test_open_shapes(client, pid, text):
    assert ask(client, pid, text)["actions"][0]["payload"] == {"screen": "shapes"}


@pytest.mark.parametrize("text,lang", [("aide", "fr"), ("help", "en")])
def test_help(client, pid, text, lang):
    j = ask(client, pid, text)
    assert [a["kind"] for a in j["actions"]] == ["help"]
    assert ("Voici" in j["reply"]) == (lang == "fr")


@pytest.mark.parametrize("text", ["raisonne", "run the reasoner"])
def test_reasoning_goes_through_the_agent(monkeypatch, text):
    from ontoforge.assistant import agent, reasoning
    seen = []
    monkeypatch.setattr(reasoning, "answer", lambda project, message, lang: seen.append((message, lang)) or {"reply": "ok", "actions": [], "warnings": []})

    class P:
        onto = None
    assert agent.run(P(), [{"role": "user", "content": text}], {})["reply"] == "ok"
    assert seen == [(text, "en" if text.startswith("run") else "fr")]


@pytest.mark.parametrize("text", ["versions", "which versions?"])
def test_versions_and_open_screen(client, pid, text):
    j = ask(client, pid, text)
    assert "Neo4j 5.26" in j["reply"] and j["actions"][0]["payload"] == {"screen": "versions"}


@pytest.mark.parametrize("text", ["mets à jour les versions", "update the versions"])
def test_update_versions_when_nothing_to_do(client, pid, text):
    j = ask(client, pid, text)
    assert [a["kind"] for a in j["actions"]] == ["navigate"]


@pytest.mark.parametrize("text", ["mets à jour les versions", "update the versions"])
def test_update_versions_proposes_the_patch(client, pid, text):
    client.put(f"/api/projects/{pid}/versions", json={"neo4j": "5.13"})
    a = ask(client, pid, text)["actions"][0]
    assert a["kind"] == "versions" and a["payload"]["patch"] == {"neo4j": "5.26"}




def test_invalid_llm_actions_are_removed_end_to_end(client, pid):
    from ontoforge.assistant import agent
    from ontoforge.projects import store
    p = store.get(pid)
    acts, w = agent.build_actions(p, [
        {"kind": "navigate", "screen": "nowhere"},
        {"kind": "rm_rf"},
        {"kind": "versions", "patch": {"neo4j": "not-a-version"}},
        {"kind": "ops", "ops": [{"op": "delete_entity", "iri": "http://autre/Chose"}]},
        {"kind": "shapes", "patches": [{"class": "Inconnue", "property": "x", "constraints": {"min_count": 1}}]},
    ], None, {})
    assert not any(a["kind"] in ("ops", "shapes", "versions") and a["payload"].get("ops") for a in acts)
    assert all(a["kind"] != "rm_rf" for a in acts) and w
