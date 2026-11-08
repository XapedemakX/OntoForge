"""Protection SSRF des appels sortants (L27) : IP privées, métadonnées, anti-rebinding, redirections, liste blanche."""
import ipaddress
import socket

import httpcore
import httpx
import pytest
from fastapi.testclient import TestClient

from ontoforge import netguard
from ontoforge.assistant.providers.base import LLMError, post_json

PRIVATE = ["http://169.254.169.254/", "http://169.254.169.254/computeMetadata/v1/", "http://metadata.google.internal/", "http://metadata/",
           "http://localhost:8000/", "http://127.0.0.1/", "http://127.1/", "http://0.0.0.0/", "http://10.1.2.3/", "http://172.16.0.9/",
           "http://192.168.0.1/", "http://100.64.0.1/", "http://[::1]/", "http://[fd00:ec2::254]/", "http://[fe80::1]/",
           "http://[::ffff:169.254.169.254]/", "http://[::ffff:127.0.0.1]/", "http://[64:ff9b::a9fe:a9fe]/", "http://[2002:a9fe:a9fe::1]/",
           "http://2852039166/", "http://0xa9fea9fe/", "http://0251.0376.0251.0376/", "http://foo.internal/", "http://printer.local/",
           "http://intranet/", "ftp://example.org/", "file:///etc/passwd", "http://user:pw@example.org/"]


@pytest.fixture
def public(monkeypatch):
    monkeypatch.setenv("ONTOFORGE_PUBLIC", "1")
    monkeypatch.delenv("ONTOFORGE_EGRESS_ALLOW", raising=False)


def fake_dns(monkeypatch, mapping, calls=None):
    def gai(host, port, *a, **k):
        if calls is not None:
            calls.append(host)
        if host not in mapping:
            raise socket.gaierror("inconnu")
        ips = mapping[host]
        ips = ips.pop(0) if isinstance(ips, list) and ips and isinstance(ips[0], list) else ips
        return [(socket.AF_INET6 if ":" in ip else socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, port)) for ip in ips]
    monkeypatch.setattr(socket, "getaddrinfo", gai)


@pytest.mark.parametrize("url", PRIVATE)
def test_literal_and_internal_urls_refused(public, url):
    with pytest.raises(netguard.NetGuardError):
        netguard.post(url, data={"query": "ASK {}"})


def test_public_ips_allowed():
    for ip in ("8.8.8.8", "1.1.1.1", "2606:4700:4700::1111"):
        assert netguard.ip_allowed(ipaddress.ip_address(ip))
    for ip in ("169.254.169.254", "10.0.0.1", "127.0.0.1", "::1", "fd00:ec2::254", "::ffff:10.0.0.1", "0.0.0.0", "224.0.0.1"):
        assert not netguard.ip_allowed(ipaddress.ip_address(ip))


def test_disabled_passes_through_to_httpx(monkeypatch):
    monkeypatch.delenv("ONTOFORGE_PUBLIC", raising=False)
    seen = {}
    monkeypatch.setattr(httpx, "post", lambda url, **kw: seen.setdefault("url", url) and httpx.Response(200, request=httpx.Request("POST", url)))
    assert netguard.post("http://localhost:3030/sparql", data={}).status_code == 200
    assert seen["url"] == "http://localhost:3030/sparql"


def test_dns_pointing_to_private_is_refused(public, monkeypatch):
    fake_dns(monkeypatch, {"evil.example.org": ["10.0.0.5"], "mixed.example.org": ["93.184.216.34", "169.254.169.254"],
                           "v6.example.org": ["fd00:ec2::254"]})
    for host in ("evil.example.org", "mixed.example.org", "v6.example.org"):
        with pytest.raises(netguard.NetGuardError):
            netguard.post(f"https://{host}/sparql", data={})


def test_connection_is_pinned_to_checked_ip(public, monkeypatch):
    """Anti-rebinding : le backend se connecte à l'adresse contrôlée, pas au nom ; une seconde résolution n'a pas lieu."""
    calls, connected = [], []
    fake_dns(monkeypatch, {"good.example.org": [["93.184.216.34"], ["127.0.0.1"]]}, calls)   # la 2e réponse serait piégée

    def fake_connect(self, host, port, timeout=None, local_address=None, socket_options=None):
        connected.append(host)
        raise httpcore.ConnectError("pas de réseau dans les tests")
    monkeypatch.setattr(httpcore.SyncBackend, "connect_tcp", fake_connect)
    with pytest.raises(httpx.ConnectError):
        netguard.post("https://good.example.org/sparql", data={})
    assert connected == ["93.184.216.34"] and calls.count("good.example.org") == 1


def test_rebinding_between_check_and_connect_is_caught(public, monkeypatch):
    """Si le nom change de réponse entre deux connexions (rebinding), chaque connexion est re-contrôlée."""
    fake_dns(monkeypatch, {"rebind.example.org": [["93.184.216.34"], ["169.254.169.254"]]})
    monkeypatch.setattr(httpcore.SyncBackend, "connect_tcp", lambda self, host, port, **k: (_ for _ in ()).throw(httpcore.ConnectError("x")))
    with pytest.raises(httpx.ConnectError):
        netguard.post("http://rebind.example.org/", data={})
    with pytest.raises(netguard.NetGuardError):
        netguard.post("http://rebind.example.org/", data={})


def mock_client(monkeypatch, handler):
    monkeypatch.setattr(netguard, "guarded_client", lambda timeout: httpx.Client(transport=httpx.MockTransport(handler), timeout=timeout))


def test_redirect_to_metadata_refused(public, monkeypatch):
    fake_dns(monkeypatch, {"ok.example.org": ["93.184.216.34"]})
    seen = []

    def handler(req):
        seen.append(str(req.url))
        return httpx.Response(302, headers={"location": "http://169.254.169.254/computeMetadata/v1/"})
    mock_client(monkeypatch, handler)
    with pytest.raises(netguard.NetGuardError):
        netguard.post("https://ok.example.org/sparql", data={})
    assert seen == ["https://ok.example.org/sparql"]


def test_redirect_limit_and_auth_stripped(public, monkeypatch):
    fake_dns(monkeypatch, {"a.example.org": ["93.184.216.34"], "b.example.org": ["93.184.216.35"]})
    seen = []

    def handler(req):
        seen.append((req.url.host, req.headers.get("authorization"), req.method))
        n = len(seen)
        if n == 1:
            return httpx.Response(307, headers={"location": "https://b.example.org/x"})
        return httpx.Response(200, json={"ok": True})
    mock_client(monkeypatch, handler)
    r = netguard.post("https://a.example.org/", data={}, headers={"Authorization": "Bearer secret"})
    assert r.status_code == 200 and seen == [("a.example.org", "Bearer secret", "POST"), ("b.example.org", None, "POST")]
    mock_client(monkeypatch, lambda req: httpx.Response(302, headers={"location": "/boucle"}))
    with pytest.raises(netguard.NetGuardError, match="redirections"):
        netguard.post("https://a.example.org/", data={})


def test_allowlist(public, monkeypatch):
    monkeypatch.setenv("ONTOFORGE_EGRESS_ALLOW", "api.anthropic.com, *.exemple.org")
    fake_dns(monkeypatch, {"api.anthropic.com": ["160.79.104.10"], "x.exemple.org": ["93.184.216.34"], "other.org": ["93.184.216.34"]})
    mock_client(monkeypatch, lambda req: httpx.Response(200))
    assert netguard.post("https://api.anthropic.com/v1/messages", json={}).status_code == 200
    assert netguard.post("https://x.exemple.org/", data={}).status_code == 200
    for bad in ("https://other.org/", "https://exemple.org/", "https://evil-exemple.org/"):
        with pytest.raises(netguard.NetGuardError, match="liste blanche"):
            netguard.post(bad, data={})


def test_llm_provider_post_json_blocked(public):
    with pytest.raises(LLMError, match="Adresse refusée"):
        post_json("Ollama", "http://169.254.169.254/api/chat", {}, {})
    with pytest.raises(LLMError, match="Adresse refusée"):
        post_json("OpenAI-compatible", "http://10.0.0.8:8000/v1/chat/completions", {"authorization": "Bearer sk-secret"}, {})


# ---- via l'API (endpoint temporaire, endpoint enregistré, test des réglages) ----------------------

@pytest.fixture
def client(public, monkeypatch):
    monkeypatch.setenv("ONTOFORGE_ALLOW_PUBLIC_NOAUTH", "1")
    from ontoforge.main import create_app
    return TestClient(create_app())


def test_api_temporary_endpoint_refused(client):
    pid = client.post("/api/projects", json={"name": "ssrf", "sample": "automaint"}).json()["id"]
    r = client.post(f"/api/projects/{pid}/query/endpoint-test", json={"url": "http://169.254.169.254/", "auth": "none"})
    assert r.status_code == 200 and r.json()["ok"] is False and "Adresse refusée" in r.json()["message"]
    r = client.post(f"/api/projects/{pid}/query/run", json={"sparql": "SELECT * WHERE {?s ?p ?o}", "endpoint": {"url": "http://metadata.google.internal/", "auth": "none"}})
    assert r.status_code == 403 and "Adresse refusée" in r.json()["detail"]


def test_api_saved_endpoint_and_settings_test_refused(client):
    r = client.post("/api/settings/sparql/test", json={"url": "http://127.0.0.1:3030/ds/sparql"})
    assert r.json()["ok"] is False and "Adresse refusée" in r.json()["message"]
    r = client.post("/api/settings/sparql/test", json={"url": "http://[::ffff:10.0.0.1]/sparql"})
    assert r.json()["ok"] is False and "Adresse refusée" in r.json()["message"]
