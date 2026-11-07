"""Historique des générations par projet (L14)."""
from fastapi.testclient import TestClient

from ontoforge.main import app

client = TestClient(app)


def _project() -> str:
    r = client.post("/api/projects", json={"name": "Hist", "sample": "automaint"})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def test_generations_recorded_and_listed():
    pid = _project()
    assert client.get(f"/api/projects/{pid}/generations").json() == []
    before = client.get(f"/api/projects/{pid}").json()["updated_at"]
    r = client.get(f"/api/projects/{pid}/generate/neo4j")
    assert r.status_code == 200
    client.get(f"/api/projects/{pid}/generate/curiosity")
    gens = client.get(f"/api/projects/{pid}/generations").json()
    assert [g["target"] for g in gens] == ["curiosity", "neo4j"]  # récente d'abord
    g = gens[1]
    assert g["files"] and set(g["findings_summary"]) == {"auto", "review", "lost", "pending"}
    assert g["at"] and g["perimeter"] is None
    assert g["project_updated_at"] == before
    assert client.get(f"/api/projects/{pid}").json()["updated_at"] == before  # updated_at inchangé


def test_generations_unknown_project_404():
    assert client.get("/api/projects/nope/generations").status_code == 404


def test_summary_exposes_origin_and_creation():
    pid = _project()
    s = next(x for x in client.get("/api/projects").json() if x["id"] == pid)
    assert s["created_at"] and s["source_files"]
