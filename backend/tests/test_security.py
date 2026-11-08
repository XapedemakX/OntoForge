"""En-têtes de sécurité, limite de taille, front compilé (SPA) et fermeture de /docs en mode public (L27)."""
import pytest
from fastapi.testclient import TestClient

from ontoforge.auth import passwords


def build(monkeypatch, tmp_path=None, **env):
    from ontoforge.main import create_app
    for k in ("ONTOFORGE_AUTH", "ONTOFORGE_PUBLIC", "ONTOFORGE_STATIC_DIR", "ONTOFORGE_MAX_BODY_MB", "ONTOFORGE_CORS_ORIGINS"):
        monkeypatch.delenv(k, raising=False)
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    return TestClient(create_app(), base_url="https://testserver")


@pytest.fixture
def front(tmp_path):
    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text("<!doctype html><title>OntoForge</title><div id=root></div>", encoding="utf-8")
    (tmp_path / "assets" / "app-1.js").write_text("console.log(1)", encoding="utf-8")
    (tmp_path / "secret.txt").write_text("hors du dossier", encoding="utf-8")
    d = tmp_path / "dist"
    d.mkdir()
    for n in ("index.html",):
        (d / n).write_text((tmp_path / n).read_text(encoding="utf-8"), encoding="utf-8")
    (d / "assets").mkdir()
    (d / "assets" / "app-1.js").write_text("console.log(1)", encoding="utf-8")
    return d


def test_security_headers_on_api_and_static(monkeypatch, front):
    c = build(monkeypatch, ONTOFORGE_STATIC_DIR=str(front))
    for path in ("/api/health", "/", "/projet/x/tableau"):
        h = c.get(path).headers
        assert "frame-ancestors 'none'" in h["content-security-policy"] and "script-src 'self'" in h["content-security-policy"]
        assert h["x-content-type-options"] == "nosniff" and h["x-frame-options"] == "DENY"
        assert h["strict-transport-security"].startswith("max-age=")
    assert c.get("/api/health").headers["cache-control"] == "no-store"
    assert "strict-transport-security" not in TestClient(c.app).get("/api/health").headers   # http simple : pas de HSTS


def test_spa_fallback_and_traversal(monkeypatch, front):
    c = build(monkeypatch, ONTOFORGE_STATIC_DIR=str(front))
    r = c.get("/projet/abc/ontologie")
    assert r.status_code == 200 and "<div id=root>" in r.text and r.headers["cache-control"] == "no-cache"
    r = c.get("/assets/app-1.js")
    assert r.status_code == 200 and "immutable" in r.headers["cache-control"]
    assert c.get("/assets/absent.js").status_code == 404
    assert c.get("/api/inconnu").status_code == 404 and c.get("/api/inconnu").json() == {"detail": "Not Found"}
    for evil in ("/../secret.txt", "/%2e%2e/secret.txt", "/assets/..%2f..%2fsecret.txt"):
        assert "hors du dossier" not in c.get(evil).text
    assert c.get("/api/health").json()["status"] == "ok"


def test_static_public_but_api_protected(monkeypatch, front):
    h = passwords.hash_password("une phrase de passe")
    c = build(monkeypatch, ONTOFORGE_STATIC_DIR=str(front), ONTOFORGE_AUTH="password", ONTOFORGE_AUTH_USERS=f"d:{h}", ONTOFORGE_SECRET_KEY="s" * 40)
    assert c.get("/").status_code == 200 and c.get("/assets/app-1.js").status_code == 200
    assert c.get("/api/projects").status_code == 401
    assert c.get("/api/inconnu").status_code == 401        # même les routes inexistantes ne révèlent rien


def test_docs_closed_and_cors_closed_in_public_mode(monkeypatch):
    h = passwords.hash_password("une phrase de passe")
    c = build(monkeypatch, ONTOFORGE_PUBLIC="1", ONTOFORGE_AUTH="password", ONTOFORGE_AUTH_USERS=f"d:{h}", ONTOFORGE_SECRET_KEY="s" * 40)
    assert c.get("/docs").status_code == 404 and c.get("/openapi.json").status_code == 404
    r = c.options("/api/projects", headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "POST"})
    assert "access-control-allow-origin" not in r.headers


def test_public_without_auth_refuses_to_start(monkeypatch):
    from ontoforge.auth.config import AuthConfigError
    with pytest.raises(AuthConfigError):
        build(monkeypatch, ONTOFORGE_PUBLIC="1")


def test_body_limit(monkeypatch):
    c = build(monkeypatch, ONTOFORGE_MAX_BODY_MB="1")
    big = b"x" * (1024 * 1024 + 10)
    r = c.post("/api/projects", content=big, headers={"content-type": "application/json"})
    assert r.status_code == 413
    # corps en morceaux, sans Content-Length
    r = c.post("/api/projects", content=(big[i:i + 65536] for i in range(0, len(big), 65536)), headers={"content-type": "application/json"})
    assert r.status_code == 413
    assert c.post("/api/projects", json={"name": "petit"}).status_code in (200, 201)
