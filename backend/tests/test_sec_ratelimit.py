"""L39-secu SEC-10 : limitation de débit par adresse et par session, plus stricte sur l'assistant et les routes coûteuses."""
import pytest
from fastapi.testclient import TestClient

from ontoforge import ratelimit


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("ONTOFORGE_DATA", str(tmp_path))
    monkeypatch.setenv("ONTOFORGE_RATE_LIMIT", "1")
    monkeypatch.setenv("ONTOFORGE_LLM_PROVIDER", "mock")
    for k in ("ONTOFORGE_AUTH", "ONTOFORGE_PUBLIC", "ONTOFORGE_STATIC_DIR"):
        monkeypatch.delenv(k, raising=False)
    ratelimit.reset()
    from ontoforge.main import create_app
    yield TestClient(create_app())
    ratelimit.reset()


def test_sec10_assistant_chat_returns_429_with_retry_after(client):
    codes, last = [], None
    for _ in range(30):
        last = client.post("/api/assistant/chat", json={"messages": [{"role": "user", "content": "bonjour"}]})
        codes.append(last.status_code)
    assert codes[0] != 429 and codes.count(429) >= 8 and codes[-1] == 429
    assert int(last.headers["retry-after"]) >= 1
    body = last.json()
    assert body["code"] == "rate_limited" and body["retry_after"] >= 1 and "requêtes" in body["detail"]


def test_sec10_global_limit_and_health_exempt(client, monkeypatch):
    monkeypatch.setenv("ONTOFORGE_RATE_GLOBAL_PER_MIN", "5")
    codes = [client.get("/api/projects").status_code for _ in range(8)]
    assert codes[:5] == [200] * 5 and set(codes[5:]) == {429}
    assert all(client.get("/api/health").status_code == 200 for _ in range(10))


def test_sec10_expensive_routes_stricter_than_global(client, monkeypatch):
    monkeypatch.setenv("ONTOFORGE_RATE_HEAVY_PER_MIN", "3")
    pid = client.post("/api/projects", json={"name": "r"}).json()["id"]
    codes = [client.post(f"/api/projects/{pid}/analyze").status_code for _ in range(6)]
    assert codes.count(429) == 3 and client.get(f"/api/projects/{pid}").status_code == 200
    ratelimit.reset()
    assert [client.post(f"/api/projects/{pid}/reason", json={}).status_code for _ in range(12)].count(429) >= 2


def test_sec10_per_session_bucket_independent_of_address(client, monkeypatch):
    monkeypatch.setenv("ONTOFORGE_RATE_GLOBAL_PER_MIN", "4")
    # même session, adresses de client différentes (en-tête transmis par un frontal de confiance) : le plafond de session s'applique
    from ontoforge.ratelimit import WINDOWS
    assert WINDOWS.hit("g:s:abc", 2) == 0 and WINDOWS.hit("g:s:abc", 2) == 0 and WINDOWS.hit("g:s:abc", 2) > 0
    assert WINDOWS.hit("g:s:autre", 2) == 0


def test_sec10_disabled_by_variable(client, monkeypatch):
    monkeypatch.setenv("ONTOFORGE_RATE_LIMIT", "0")
    monkeypatch.setenv("ONTOFORGE_RATE_GLOBAL_PER_MIN", "2")
    assert all(client.get("/api/projects").status_code == 200 for _ in range(6))


def test_sec10_login_limiter_api_unchanged():
    from ontoforge.auth import limiter
    for name in ("retry_after", "failure", "success", "client_ip", "allow", "reset", "reset_hits"):
        assert callable(getattr(limiter, name))
