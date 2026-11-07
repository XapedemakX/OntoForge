"""Version anglaise : assistant déterministe (sans LLM), explication NL, textes de l'analyse affichés à l'écran."""
import re

import pytest
from fastapi.testclient import TestClient

from ontoforge.main import app

ACCENT = re.compile(r"[éèàçùêâîôûëïœ]", re.I)


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("ONTOFORGE_DATA", str(tmp_path))
    monkeypatch.setenv("ONTOFORGE_LLM_PROVIDER", "mock")
    return TestClient(app)


def _english(c):
    r = c.put("/api/settings", json={"language": {"ui": "en", "labels": "en", "assistant": "en"}})
    assert r.status_code == 200, r.text


@pytest.fixture
def pid(client):
    _english(client)
    r = client.post("/api/projects", json={"name": "t", "sample": "automaint"})
    assert r.status_code in (200, 201), r.text
    return r.json()["id"]


def chat(c, pid, msg, screen="ontologie"):
    r = c.post("/api/assistant/chat", json={"project_id": pid, "messages": [{"role": "user", "content": msg}], "context": {"screen": screen}})
    assert r.status_code == 200, r.text
    return r.json()


def test_add_class_with_property_is_an_ops_action_not_a_proposal(client, pid):
    j = chat(client, pid, "add the class Tyre under Part with a property pressure in bar")
    assert [a["kind"] for a in j["actions"]] == ["ops"]
    ops = j["actions"][0]["payload"]["ops"]
    assert [o["op"] for o in ops[:2]] == ["add_class", "add_datatype_property"]
    assert ops[0]["label"] == "Tyre" and ops[0]["lang"] == "en"
    assert ops[1]["label"].startswith("pressure")
    assert not ACCENT.search(j["reply"]) and "I suggest" in j["reply"]
    assert not any(ACCENT.search(p["text"]) for p in j["actions"][0]["payload"]["preview"])


def test_add_property_and_make_required_in_english(client, pid):
    j = chat(client, pid, "add the property pressure to Vehicle")
    op = j["actions"][0]["payload"]["ops"][0]
    assert op["op"] == "add_datatype_property" and op["lang"] == "en"
    j = chat(client, pid, "make vin required")
    assert j["actions"][0]["payload"]["ops"][0]["op"] == "set_restriction"
    assert "required" in j["reply"] and not ACCENT.search(j["reply"])


def test_delete_warnings_and_unknown_entity_are_english(client, pid):
    j = chat(client, pid, "delete Garage")
    assert j["actions"][0]["payload"]["ops"][0]["op"] == "delete_entity"
    assert j["warnings"] and not any(ACCENT.search(w) for w in j["warnings"])
    j = chat(client, pid, "delete the class Nonexistent")
    assert j["actions"] == [] and "can't find" in j["reply"]


def test_shape_constraints_in_english(client, pid):
    j = chat(client, pid, "add a min constraint 0 on mileageKm in shape VehicleShape", screen="shacl")
    a = j["actions"][0]
    assert a["kind"] == "shapes" and "minimum value 0" in a["payload"]["preview"][0]["text"]
    j = chat(client, pid, "add a max constraint 300000 on mileageKm in the shape Vehicle", screen="shacl")
    assert "maximum value 300000" in j["actions"][0]["payload"]["preview"][0]["text"]


def test_find_and_open_in_english(client, pid):
    j = chat(client, pid, "find the vehicles whose fuel is Diesel")
    assert j["actions"][0]["kind"] == "guided_query"
    assert not ACCENT.search(j["actions"][0]["summary"])
    j = chat(client, pid, "open the shapes")
    assert j["actions"][0]["kind"] == "navigate" and j["actions"][0]["payload"].get("screen") in ("shapes", "shacl")


def test_french_request_still_answered_in_french_when_ui_is_french(client):
    pid = client.post("/api/projects", json={"name": "f", "sample": "automaint"}).json()["id"]
    j = chat(client, pid, "Ajoute la classe Pneu sous Pièce avec une propriété pression en bar")
    assert j["actions"][0]["kind"] == "ops" and "Je propose" in j["reply"]
    assert j["actions"][0]["payload"]["ops"][0]["lang"] == "fr"


def test_english_request_labels_in_en_even_if_ui_is_french(client):
    pid = client.post("/api/projects", json={"name": "f", "sample": "automaint"}).json()["id"]
    j = chat(client, pid, "add the class Tyre under Part")
    assert j["actions"][0]["payload"]["ops"][0]["lang"] == "en" and "I suggest" in j["reply"]


def test_nl_explanation_in_english(client, pid):
    r = client.post(f"/api/projects/{pid}/query/nl", json={"question": "vehicles whose fuel is Diesel"})
    assert r.status_code == 200, r.text
    j = r.json()
    assert not ACCENT.search(j["explanation"]), j["explanation"]
    assert "Vehicle" in j["explanation"] and "Diesel" in j["explanation"]
    assert not any(ACCENT.search(n) for n in j["notes"]), j["notes"]


def test_nl_explanation_stays_french_in_french(client):
    pid = client.post("/api/projects", json={"name": "f", "sample": "automaint"}).json()["id"]
    j = client.post(f"/api/projects/{pid}/query/nl", json={"question": "les véhicules dont le carburant est Diesel"}).json()
    assert "Classe de départ" in j["explanation"] or "départ" in j["explanation"]


def test_analysis_texts_have_no_french_in_english(client, pid):
    pg = client.post(f"/api/projects/{pid}/analyze", params={"target": "curiosity"})
    assert pg.status_code == 200, pg.text
    data = pg.json()
    assert data["findings"]
    for f in data["findings"]:
        texts = [f["title"], f["detail"], f.get("rationale") or ""] + [o["label"] + " " + o["impact"] for o in f["options"]]
        for t in texts:
            assert not ACCENT.search(t), (f["rule"], t)
    for v in data["validations"]:
        assert not ACCENT.search(v["description"]), v


def test_conformance_and_error_messages_in_english(client, pid):
    r = client.get(f"/api/projects/{pid}/conformance")
    assert r.status_code == 200
    assert not any(ACCENT.search(i["message"]) for i in r.json()["issues"])
    r = client.get("/api/projects/does-not-exist")
    assert r.status_code == 404 and "not found" in r.json()["detail"]
