"""L8 — paramètres : chiffrement, CRUD fournisseurs, sélection dans l'assistant, upload."""
import json
import stat

import httpx
import pytest
from fastapi.testclient import TestClient

from ontoforge.main import app
from ontoforge.settings import crypto, store

KEY = "sk-ant-SECRET-1234567890abcd"


@pytest.fixture
def client(tmp_path, monkeypatch):
    for v in ("ONTOFORGE_LLM_PROVIDER", "ANTHROPIC_API_KEY", "OPENAI_BASE_URL", "OPENAI_API_KEY", "OLLAMA_BASE_URL", "ONTOFORGE_LLM_MODEL"):
        monkeypatch.delenv(v, raising=False)
    monkeypatch.setenv("ONTOFORGE_DATA", str(tmp_path))
    monkeypatch.setenv("ONTOFORGE_SECRET_KEY", "master-test-key")
    return TestClient(app)


def test_first_start_mock_only(client):
    s = client.get("/api/settings").json()
    assert [p["id"] for p in s["llm_providers"]] == ["mock"] and s["default_provider_id"] == "mock"
    assert s["language"] == {"ui": "fr", "labels": "fr", "assistant": "fr"} and s["defaults"]["target"] == "curiosity"


def test_env_compat_first_start(client, monkeypatch):
    monkeypatch.setenv("ONTOFORGE_LLM_PROVIDER", "anthropic")
    monkeypatch.setenv("ANTHROPIC_API_KEY", KEY)
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://ollama:11434")
    s = client.get("/api/settings").json()
    by = {p["id"]: p for p in s["llm_providers"]}
    assert set(by) == {"anthropic", "ollama", "mock"} and s["default_provider_id"] == "anthropic"
    assert by["anthropic"]["has_key"] and by["anthropic"]["key_last4"] == KEY[-4:] and by["anthropic"]["configured"]
    assert KEY not in json.dumps(s)


def test_key_encrypted_and_never_exposed(client, tmp_path):
    r = client.post("/api/settings/providers", json={"name": "Claude", "kind": "anthropic", "api_key": KEY})
    assert r.status_code == 201, r.text
    pid = r.json()["id"]
    assert "api_key" not in r.json() and r.json()["has_key"] and r.json()["key_last4"] == KEY[-4:]
    raw = (tmp_path / "settings.json").read_text()
    assert KEY not in raw and "enc:v1:" in raw and "api_key\"" not in raw
    assert oct(stat.S_IMODE((tmp_path / "settings.json").stat().st_mode)) == "0o600"
    for resp in (client.get("/api/settings"), client.put("/api/settings", json={"default_provider_id": pid}),
                 client.put(f"/api/settings/providers/{pid}", json={"model": "x"})):
        assert resp.status_code == 200 and KEY not in resp.text and "sk-ant" not in resp.text
    # le déchiffrement fonctionne avec la bonne clé maître seulement
    tok = json.loads(raw)["llm_providers"][-1]["api_key_enc"]
    assert crypto.decrypt(tok) == KEY
    with pytest.raises(crypto.SecretError):
        crypto.decrypt(tok, "autre-cle")


def test_generated_secret_file(tmp_path, monkeypatch):
    monkeypatch.delenv("ONTOFORGE_SECRET_KEY", raising=False)
    monkeypatch.setenv("ONTOFORGE_DATA", str(tmp_path))
    tok = crypto.encrypt("abc")
    f = tmp_path / ".secret"
    assert f.exists() and stat.S_IMODE(f.stat().st_mode) == 0o600 and crypto.decrypt(tok) == "abc"


def test_wrong_master_key_flags_unreadable_and_rotation(client, tmp_path, monkeypatch):
    client.post("/api/settings/providers", json={"name": "Claude", "kind": "anthropic", "api_key": KEY})
    assert store.rotate("master-test-key", "nouvelle-cle") == 1
    monkeypatch.setenv("ONTOFORGE_SECRET_KEY", "master-test-key")
    p = [x for x in client.get("/api/settings").json()["llm_providers"] if x["kind"] == "anthropic"][0]
    assert p["key_unreadable"] and not p["has_key"]
    monkeypatch.setenv("ONTOFORGE_SECRET_KEY", "nouvelle-cle")
    p = [x for x in client.get("/api/settings").json()["llm_providers"] if x["kind"] == "anthropic"][0]
    assert p["has_key"] and not p["key_unreadable"]
    with pytest.raises(crypto.SecretError):
        store.rotate("mauvaise", "x")


def test_provider_crud_and_key_semantics(client):
    r = client.post("/api/settings/providers", json={"name": "Local", "kind": "ollama", "base_url": "http://o:11434", "api_key": KEY})
    pid = r.json()["id"]
    assert pid == "local"
    assert client.post("/api/settings/providers", json={"id": "local", "name": "x", "kind": "ollama"}).status_code == 409
    assert client.post("/api/settings/providers", json={"name": "Bad", "kind": "nope"}).status_code == 422
    assert client.post("/api/settings/providers", json={"name": "Bad", "kind": "ollama", "base_url": "ftp://x"}).status_code == 422
    # clé vide = inchangée
    r = client.put(f"/api/settings/providers/{pid}", json={"api_key": "", "model": "llama3.2"}).json()
    assert r["has_key"] and r["model"] == "llama3.2"
    # null = supprimée
    r = client.put(f"/api/settings/providers/{pid}", json={"api_key": None}).json()
    assert not r["has_key"] and r["key_last4"] == ""
    # PUT global partiel
    s = client.put("/api/settings", json={"default_provider_id": pid, "language": {"ui": "en"},
                                          "defaults": {"target": "neo4j"},
                                          "sparql_endpoint": {"url": "http://fuseki/ds/sparql", "auth": {"type": "bearer", "secret": "tok-123456789012"}}}).json()
    assert s["default_provider_id"] == pid and s["language"] == {"ui": "en", "labels": "fr", "assistant": "fr"}
    assert s["defaults"]["target"] == "neo4j" and s["defaults"]["base_iri"].startswith("https://")
    assert s["sparql_endpoint"]["auth"] == {"type": "bearer", "username": None, "has_secret": True} and "tok-1234" not in json.dumps(s)
    assert client.put("/api/settings", json={"default_provider_id": "zzz"}).status_code == 422
    assert client.put("/api/settings", json={"language": {"ui": "de"}}).status_code == 422
    # suppression : le défaut retombe sur le mock ; le mock est indestructible
    assert client.delete(f"/api/settings/providers/{pid}").json()["default_provider_id"] == "mock"
    assert client.delete("/api/settings/providers/mock").status_code == 409
    assert client.delete("/api/settings/providers/inconnu").status_code == 404
    assert client.put("/api/settings", json={"sparql_endpoint": None}).json()["sparql_endpoint"]["url"] == ""


def test_provider_test_endpoint(client, monkeypatch):
    assert client.post("/api/settings/providers/mock/test").json()["ok"] is True
    r = client.post("/api/settings/providers", json={"name": "Claude", "kind": "anthropic"}).json()
    out = client.post(f"/api/settings/providers/{r['id']}/test").json()
    assert out["ok"] is False and "non configuré" in out["message"]
    seen = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        seen.update(timeout=timeout, headers=headers)
        return httpx.Response(401, text="bad " + KEY, request=httpx.Request("POST", url))
    monkeypatch.setattr(httpx, "post", fake_post)
    out = client.post(f"/api/settings/providers/{r['id']}/test", json={"api_key": KEY}).json()
    assert out["ok"] is False and "authentification" in out["message"] and KEY not in json.dumps(out) and seen["timeout"] == 15.0
    monkeypatch.setattr(httpx, "post", lambda url, headers=None, json=None, timeout=None: httpx.Response(
        200, json={"content": [{"type": "text", "text": "OK"}]}, request=httpx.Request("POST", url)))
    out = client.post(f"/api/settings/providers/{r['id']}/test", json={"api_key": KEY}).json()
    assert out["ok"] is True and out["model"] == "claude-sonnet-5-5" and out["latency_ms"] >= 0
    assert client.post("/api/settings/providers/zzz/test").status_code == 404


def test_sparql_test(client, monkeypatch):
    assert client.post("/api/settings/sparql/test").json()["ok"] is False
    monkeypatch.setattr(httpx, "post", lambda url, **k: httpx.Response(200, json={"boolean": True}, request=httpx.Request("POST", url)))
    out = client.post("/api/settings/sparql/test", json={"url": "http://x/sparql"}).json()
    assert out["ok"] is True


# ---- assistant : sélection du fournisseur ------------------------------------------------------
def _project(client):
    return client.post("/api/projects", json={"name": "P"}).json()["id"]


def test_assistant_uses_requested_and_default_provider(client, monkeypatch):
    pid = _project(client)
    client.get("/api/settings")  # premier démarrage : fichier créé depuis l'environnement (mock seul)
    st = client.get("/api/assistant/status").json()
    assert st["provider"] == "mock" and [p["id"] for p in st["providers"]] == ["mock"]
    # un second fournisseur « claude » non configuré, défini par défaut
    client.post("/api/settings/providers", json={"id": "claude", "name": "Claude", "kind": "anthropic"})
    client.put("/api/settings", json={"default_provider_id": "claude"})
    st = client.get("/api/assistant/status").json()
    assert st["provider"] == "anthropic" and st["configured"] is False and st["default_provider_id"] == "claude"
    body = {"project_id": pid, "messages": [{"role": "user", "content": "Un garage avec véhicules et réparations"}]}
    assert client.post("/api/assistant/chat", json=body).status_code == 503  # défaut non configuré
    r = client.post("/api/assistant/chat", json={**body, "provider_id": "mock"})
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["reply"] and out["proposal"]["classes"] and isinstance(out["warnings"], list)
    assert client.post("/api/assistant/chat", json={**body, "provider_id": "zzz"}).status_code == 404
    # draft avec provider_id explicite
    d = client.post("/api/assistant/draft", json={"text": "garage véhicules", "provider_id": "mock"})
    assert d.status_code == 200 and d.json()["proposal"]["classes"]
    # chat sans proposition
    r = client.post("/api/assistant/chat", json={"project_id": pid, "provider_id": "mock", "messages": [{"role": "user", "content": "bonjour"}]})
    assert r.json()["proposal"] is None and r.json()["reply"]
    assert client.post("/api/assistant/chat", json={"project_id": pid, "messages": [{"role": "assistant", "content": "x"}]}).status_code == 422


def test_chat_with_csv_attachment(client):
    pid = _project(client)
    r = client.post("/api/assistant/chat", json={"project_id": pid, "provider_id": "mock",
                    "messages": [{"role": "user", "content": "Modélise ce fichier"}],
                    "attachments": [{"name": "clients.csv", "kind": "csv", "content": "id,nom,ville\n1,Ana,Albi\n2,Bob,Pau\n"}]})
    assert r.status_code == 200, r.text
    prop = r.json()["proposal"]
    assert prop["classes"] and any(k.endswith("#nom") for k in prop["datatype_properties"])


# ---- upload ---------------------------------------------------------------------------------
def test_upload_csv_sql_text(client):
    r = client.post("/api/assistant/upload", files={"file": ("pieces.csv", "ref;nom;prix\n" + "\n".join(f"{i};p{i};1" for i in range(30)), "text/csv")})
    out = r.json()
    assert r.status_code == 200 and out["kind"] == "csv" and len(out["preview"]["lines"]) == 20 and out["preview"]["columns"] == ["ref", "nom", "prix"]
    assert out["preview"]["truncated"] and out["size"] > 0 and out["name"] == "pieces.csv"
    sql = "CREATE TABLE vehicle (vin TEXT PRIMARY KEY);\nCREATE TABLE IF NOT EXISTS `owner` (id INT);\n"
    out = client.post("/api/assistant/upload", files={"file": ("schema.sql", sql, "text/plain")}).json()
    assert out["kind"] == "sql" and out["preview"]["tables"] == ["vehicle", "owner"]
    assert client.post("/api/assistant/upload", files={"file": ("dump.dat", sql, "text/plain")}).json()["kind"] == "sql"
    assert client.post("/api/assistant/upload", files={"file": ("n.md", "# Titre\ntexte", "text/markdown")}).json()["kind"] == "markdown"
    assert client.post("/api/assistant/upload", files={"file": ("n.txt", "juste du texte", "text/plain")}).json()["kind"] == "text"
    assert client.post("/api/assistant/upload", files={"file": ("e.txt", "  ", "text/plain")}).status_code == 422
    assert client.post("/api/assistant/upload", files={"file": ("big.txt", "x" * (2 * 1024 * 1024 + 5), "text/plain")}).status_code == 413
