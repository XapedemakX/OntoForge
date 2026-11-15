"""L39-secu SEC-03 : un secret enregistré n'est envoyé qu'à l'adresse pour laquelle il a été saisi ; SEC-13 : clé maître séparée."""
import http.server
import os
import stat
import threading

import pytest
from fastapi.testclient import TestClient

from ontoforge.settings import crypto, store

KEY = "sk-" + "ant-" + "FAKE" + "KEY0123456789abcdefghij"      # assemblées à l'exécution
TOKEN = "FAKE-BEARER-" + "TOKEN-0001"


class _Rec(http.server.BaseHTTPRequestHandler):
    hits: list = []

    def _h(self):
        n = int(self.headers.get("content-length") or 0)
        self.rfile.read(n) if n else b""
        _Rec.hits.append({k.lower(): v for k, v in self.headers.items()})
        out = b'{"boolean": true}'
        self.send_response(200)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(out)))
        self.end_headers()
        self.wfile.write(out)

    do_GET = do_POST = _h

    def log_message(self, *a):
        pass


@pytest.fixture
def rec():
    _Rec.hits = []
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Rec)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("ONTOFORGE_DATA", str(tmp_path))
    monkeypatch.setenv("ONTOFORGE_SECRET_KEY", "master-test-key")
    for v in ("ONTOFORGE_LLM_PROVIDER", "ANTHROPIC_API_KEY", "OPENAI_BASE_URL", "OLLAMA_BASE_URL"):
        monkeypatch.delenv(v, raising=False)
    from ontoforge.main import create_app
    return TestClient(create_app())


def put(client, url, body):
    """PUT via l'API (route classée par L40 : un 403 « unclassified » fait échouer le test)."""
    r = client.put(url, json=body)
    assert not (r.status_code == 403 and r.json().get("code") == "unclassified"), "route de réglages non classée"
    return r.json()


def _leaked(hits):
    return [h for h in hits if KEY in h.values() or any(TOKEN in v for v in h.values())]


def test_sec03_provider_test_with_other_url_never_sends_saved_key(client, rec):
    pid = client.post("/api/settings/providers", json={"name": "A", "kind": "openai_compat", "base_url": "https://api.example.org/v1",
                                                       "api_key": KEY, "model": "m"}).json()["id"]
    _Rec.hits.clear()
    client.post(f"/api/settings/providers/{pid}/test", json={"base_url": rec})
    assert _leaked(_Rec.hits) == []


def test_sec03_changing_url_erases_saved_key(client, rec):
    pid = client.post("/api/settings/providers", json={"name": "A", "kind": "openai_compat", "base_url": "https://api.example.org/v1",
                                                       "api_key": KEY, "model": "m"}).json()["id"]
    r = put(client, f"/api/settings/providers/{pid}", {"base_url": rec})
    assert r["has_key"] is False
    assert store.load().provider(pid).api_key is None
    _Rec.hits.clear()
    client.post(f"/api/settings/providers/{pid}/test")
    assert _leaked(_Rec.hits) == []


def test_sec03_same_url_keeps_key_and_new_key_with_new_url_is_accepted(client, rec):
    pid = client.post("/api/settings/providers", json={"name": "A", "kind": "openai_compat", "base_url": "https://api.example.org/v1",
                                                       "api_key": KEY, "model": "m"}).json()["id"]
    assert put(client, f"/api/settings/providers/{pid}", {"model": "m2", "base_url": "https://api.example.org/v2"})["has_key"] is True
    r = put(client, f"/api/settings/providers/{pid}", {"base_url": rec, "api_key": KEY + "-new"})
    assert r["has_key"] is True
    assert store.load().provider(pid).api_key == KEY + "-new"


def test_sec03_endpoint_secret_bound_to_url(client, rec):
    eid = client.post("/api/settings/endpoints", json={"name": "E", "url": "https://sparql.example.org/q", "auth": "bearer", "secret": TOKEN}).json()["id"]
    _Rec.hits.clear()
    client.post(f"/api/settings/endpoints/{eid}/test", json={"url": rec})
    assert _leaked(_Rec.hits) == []
    r = put(client, f"/api/settings/endpoints/{eid}", {"url": rec})
    assert r["has_secret"] is False and store.load().endpoint(eid).secret is None
    _Rec.hits.clear()
    client.post(f"/api/settings/endpoints/{eid}/test")
    assert _leaked(_Rec.hits) == []


def test_sec03_legacy_sparql_test_route(client, rec):
    put(client, "/api/settings", {"sparql_endpoint": {"url": "https://sparql.example.org/q", "auth": {"type": "bearer", "secret": TOKEN}}})
    _Rec.hits.clear()
    client.post("/api/settings/sparql/test", json={"url": rec})
    assert _leaked(_Rec.hits) == []


def test_sec03_loading_from_disk_is_not_affected(client):
    client.post("/api/settings/providers", json={"name": "A", "kind": "anthropic", "api_key": KEY, "model": "m"})
    assert store.load().provider("a").api_key == KEY


# ---- SEC-13 -------------------------------------------------------------------------------------------------------
def test_sec13_key_file_location_configurable_and_600(tmp_path, monkeypatch):
    data, keys = tmp_path / "data", tmp_path / "keys"
    data.mkdir()
    monkeypatch.setenv("ONTOFORGE_DATA", str(data))
    monkeypatch.delenv("ONTOFORGE_SECRET_KEY", raising=False)
    monkeypatch.delenv("ONTOFORGE_SETTINGS_KEY", raising=False)
    monkeypatch.setenv("ONTOFORGE_SECRET_FILE", str(keys / "master.key"))
    k = crypto.master_secret()
    assert (keys / "master.key").read_text().strip() == k and not (data / ".secret").exists()
    assert stat.S_IMODE((keys / "master.key").stat().st_mode) == 0o600
    assert stat.S_IMODE(keys.stat().st_mode) == 0o700
    store.save(store.from_env())
    assert stat.S_IMODE((data / "settings.json").stat().st_mode) == 0o600


def test_sec13_legacy_key_is_moved_out_of_the_data_folder(tmp_path, monkeypatch):
    data = tmp_path / "data"
    data.mkdir()
    monkeypatch.setenv("ONTOFORGE_DATA", str(data))
    monkeypatch.delenv("ONTOFORGE_SECRET_KEY", raising=False)
    monkeypatch.delenv("ONTOFORGE_SECRET_FILE", raising=False)
    old = crypto.master_secret()
    assert (data / ".secret").exists()
    monkeypatch.setenv("ONTOFORGE_SECRET_FILE", str(tmp_path / "keys" / "master.key"))
    assert crypto.master_secret() == old
    assert not (data / ".secret").exists() and (tmp_path / "keys" / "master.key").exists()


def test_sec13_dedicated_settings_key_takes_precedence(tmp_path, monkeypatch):
    monkeypatch.setenv("ONTOFORGE_DATA", str(tmp_path))
    monkeypatch.setenv("ONTOFORGE_SECRET_KEY", "session-root")
    monkeypatch.setenv("ONTOFORGE_SETTINGS_KEY", "settings-root")
    assert crypto.master_secret() == "settings-root"


def test_sec13_env_file_warning_never_reads_content(tmp_path):
    from ontoforge import hardening
    f = tmp_path / ".env"
    f.write_text("CONTENU-NON-LU")
    f.chmod(0o644)
    msg = hardening.env_file_warning([f])
    assert msg and "chmod 600" in msg and "CONTENU-NON-LU" not in msg
    f.chmod(0o600)
    assert hardening.env_file_warning([f]) is None


# ---- couche réglages seule (sans passer par les routes PUT) ---------------------------------------------------------
def test_sec03_settings_layer_clears_key_when_origin_changes(tmp_path, monkeypatch):
    from ontoforge.api.settings import _patch_endpoint, _patch_provider
    from ontoforge.settings.models import EndpointConfig, ProviderConfig
    monkeypatch.setenv("ONTOFORGE_DATA", str(tmp_path))
    monkeypatch.setenv("ONTOFORGE_SECRET_KEY", "master-test-key")
    s = store.from_env()
    s.llm_providers.append(ProviderConfig(id="a", name="A", kind="openai_compat", base_url="https://api.example.org/v1", model="m", api_key=KEY))
    s.sparql_endpoints.append(EndpointConfig(id="e", name="E", url="https://sparql.example.org/q", auth="bearer", secret=TOKEN))
    store.save(s)
    s = store.load()
    cur = s.provider("a")
    assert _patch_provider(cur, {"base_url": "https://api.example.org/v2"}, set()).api_key == KEY          # même origine : conservée
    assert _patch_provider(cur, {"base_url": "http://127.0.0.1:9"}, set()).api_key is None                 # autre origine : effacée
    assert _patch_provider(cur, {"base_url": "https://autre.example.org"}, set()).api_key is None
    assert _patch_provider(cur, {"base_url": "http://127.0.0.1:9", "api_key": KEY + "-n"}, set()).api_key == KEY + "-n"
    ep = s.endpoint("e")
    assert _patch_endpoint(ep, {"url": "https://sparql.example.org/other"}, set()).secret == TOKEN
    assert _patch_endpoint(ep, {"url": "http://127.0.0.1:9/q"}, set()).secret is None
    assert _patch_endpoint(ep, {"url": "http://127.0.0.1:9/q", "secret": TOKEN + "x"}, set()).secret == TOKEN + "x"
