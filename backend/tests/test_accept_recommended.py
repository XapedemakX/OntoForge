"""accept-recommended : les constats « lost » restent à arbitrer par l'humain sauf include_lost=true."""
from fastapi.testclient import TestClient

from ontoforge.main import app


def _lost(pg):
    return [f for f in pg["findings"] if f["severity"] == "lost" and f.get("recommended")]


def test_accept_recommended_skips_lost_by_default(tmp_path, monkeypatch):
    monkeypatch.setenv("ONTOFORGE_DATA", str(tmp_path))
    c = TestClient(app)
    pid = c.post("/api/projects", json={"name": "x", "sample": "automaint"}).json()["id"]
    base = c.post(f"/api/projects/{pid}/analyze?target=neo4j").json()
    assert _lost(base), "l'exemple doit produire des constats perdus avec recommandation"
    pg = c.post(f"/api/projects/{pid}/decisions/neo4j/accept-recommended").json()
    assert len(_lost(pg)) == len(_lost(base))
    assert all(not f["chosen"] for f in _lost(pg))
    assert any(f["chosen"] for f in pg["findings"] if f["severity"] == "review")
    pg = c.post(f"/api/projects/{pid}/decisions/neo4j/accept-recommended?include_lost=true").json()
    assert all(f["chosen"] for f in _lost(pg))
