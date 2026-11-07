"""Routes /api/assistant/* branchées sur le service réel (fournisseur mock) via TestClient."""
import sys
import types

import pytest
from fastapi.testclient import TestClient

from ontoforge.core.pg_model import EdgeType, Finding, NodeType, Option, PGModel
from ontoforge.main import app

B = "https://example.org/auto#"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("ONTOFORGE_DATA", str(tmp_path))
    monkeypatch.setenv("ONTOFORGE_LLM_PROVIDER", "mock")

    def analyze(onto, shapes, target, decisions=None):
        f = Finding(id="C02:car", rule="C02", severity="review", title="Sous-classe", detail="Car ⊑ Vehicle", subject=B + "Car",
                    options=[Option(id="flatten", label="Aplatir", impact="x")], recommended="flatten")
        return PGModel(target=target, findings=[f])
    mod = types.ModuleType("ontoforge.mapping.engine")
    mod.analyze = analyze
    monkeypatch.setitem(sys.modules, "ontoforge.mapping.engine", mod)
    return TestClient(app)


def test_assistant_routes(client):
    st = client.get("/api/assistant/status").json()
    assert {k: st[k] for k in ("provider", "model", "configured")} == {"provider": "mock", "model": "mock", "configured": True}
    assert st["providers"][0]["id"]
    r = client.post("/api/assistant/draft", json={"text": "vehicle_id,vin,mileage\n1,AB,10\n", "kind": "csv", "base_iri": B})
    assert r.status_code == 200, r.text
    j = r.json()
    assert B + "Vehicle" in j["proposal"]["classes"] and j["explanation"] and isinstance(j["warnings"], list)
    assert client.post("/api/assistant/draft", json={"text": ""}).status_code == 422

    pid = client.post("/api/projects", json={"name": "t"}).json()["id"]
    onto = j["proposal"]
    assert client.put(f"/api/projects/{pid}/onto", json=onto).status_code == 200
    r = client.post("/api/assistant/shapes", json={"project_id": pid})
    assert r.status_code == 200, r.text
    assert B + "VehicleShape" in r.json()["proposal"]["shapes"] or r.json()["proposal"]["shapes"]
    r = client.post("/api/assistant/explain", json={"project_id": pid, "target": "neo4j", "finding_id": "C02:car"})
    assert r.status_code == 200 and "C02" in r.json()["text"] and "Neo4j" in r.json()["text"]
    assert client.post("/api/assistant/explain", json={"project_id": pid, "target": "neo4j", "finding_id": "zzz"}).status_code == 404
