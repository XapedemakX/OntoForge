"""L41 : corrections de la relecture sécurité L39/L40 (appels sortants, SHACL, processus fils, limiteur, clé maître, nginx)."""
import os
import re
import stat
import subprocess
import sys
import threading
import time
from pathlib import Path

import httpx
import pytest

from ontoforge import childproc, netguard
from test_netguard import fake_dns, mock_client

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def auth_only(monkeypatch):
    """Authentification activée, mode public éteint (D-L41-01)."""
    monkeypatch.delenv("ONTOFORGE_PUBLIC", raising=False)
    monkeypatch.delenv("ONTOFORGE_EGRESS_ALLOW", raising=False)
    monkeypatch.delenv("ONTOFORGE_EGRESS_ALLOW_INTERNAL", raising=False)
    monkeypatch.setenv("ONTOFORGE_AUTH", "password")


# ---- L40-03 / D-L41-01 : protection des appels sortants -------------------------------------------------------------------------------

def test_netguard_enabled_with_auth_or_public_only(monkeypatch):
    for k in ("ONTOFORGE_AUTH", "ONTOFORGE_PUBLIC"):
        monkeypatch.delenv(k, raising=False)
    assert not netguard.enabled()                                   # local sans authentification : comportement d'avant
    monkeypatch.setenv("ONTOFORGE_AUTH", "password")
    assert netguard.enabled()
    monkeypatch.setenv("ONTOFORGE_AUTH", "none")
    assert not netguard.enabled()
    monkeypatch.setenv("ONTOFORGE_PUBLIC", "1")
    assert netguard.enabled()


def test_local_mode_still_reaches_local_endpoints(monkeypatch):
    for k in ("ONTOFORGE_AUTH", "ONTOFORGE_PUBLIC"):
        monkeypatch.delenv(k, raising=False)
    seen = {}
    monkeypatch.setattr(httpx, "post", lambda url, **kw: seen.setdefault("u", url) and httpx.Response(200, request=httpx.Request("POST", url)))
    assert netguard.post("http://127.0.0.1:3030/sparql", data={}).status_code == 200


@pytest.mark.parametrize("url", ["http://127.0.0.1:3030/x", "http://localhost/x", "http://10.0.0.5/x", "http://fuseki/x", "http://169.254.169.254/",
                                 "http://metadata.google.internal/", "http://[::1]/x"])
def test_auth_mode_refuses_internal_addresses(auth_only, url):
    with pytest.raises(netguard.NetGuardError):
        netguard.post(url, data={})


def test_internal_allowlist_authorises_only_named_hosts(auth_only, monkeypatch):
    monkeypatch.setenv("ONTOFORGE_EGRESS_ALLOW_INTERNAL", "fuseki, *.corp.example, 10.1.2.3, localhost")
    fake_dns(monkeypatch, {"fuseki": ["10.0.0.7"], "kg.corp.example": ["10.0.0.8"], "other.example": ["10.0.0.9"], "meta.corp.example": ["169.254.169.254"],
                           "localhost": ["127.0.0.1"]})
    mock_client(monkeypatch, lambda req: httpx.Response(200))
    for ok in ("http://fuseki:3030/s", "https://kg.corp.example/s", "http://10.1.2.3/s", "http://localhost:3030/s"):
        assert netguard.post(ok, data={}).status_code == 200, ok
    for bad in ("http://10.1.2.4/s", "http://169.254.169.254/",
                "http://metadata.google.internal/", "http://192.168.0.1/"):   # liste non exhaustive : tout le reste reste refusé, métadonnées comprises
        with pytest.raises(netguard.NetGuardError):
            netguard.post(bad, data={})


def test_internal_allowlist_never_opens_metadata_addresses_after_resolution(auth_only, monkeypatch):
    monkeypatch.setenv("ONTOFORGE_EGRESS_ALLOW_INTERNAL", "*.corp.example")
    fake_dns(monkeypatch, {"meta.corp.example": ["169.254.169.254"], "mix.corp.example": ["10.0.0.8", "fe80::1"], "ok.corp.example": ["10.0.0.8"]})
    for h in ("meta.corp.example", "mix.corp.example"):
        with pytest.raises(netguard.NetGuardError):
            netguard.resolve_checked(h, 80)
    assert netguard.resolve_checked("ok.corp.example", 80) == ["10.0.0.8"]
    monkeypatch.setenv("ONTOFORGE_EGRESS_ALLOW_INTERNAL", "fuseki")
    fake_dns(monkeypatch, {"other.example": ["10.0.0.9"]})
    with pytest.raises(netguard.NetGuardError):   # nom non listé qui se résout vers une adresse privée : refusé
        netguard.resolve_checked("other.example", 80)


def test_internal_allowlist_does_not_cover_a_redirect_to_an_unlisted_internal_host(auth_only, monkeypatch):
    monkeypatch.setenv("ONTOFORGE_EGRESS_ALLOW_INTERNAL", "fuseki")
    fake_dns(monkeypatch, {"fuseki": ["10.0.0.7"], "autre": ["10.0.0.8"]})
    mock_client(monkeypatch, lambda req: httpx.Response(302, headers={"location": "http://autre/x"}))
    with pytest.raises(netguard.NetGuardError):
        netguard.post("http://fuseki/s", data={})


def test_public_allowlist_semantics_unchanged(monkeypatch):
    """ONTOFORGE_EGRESS_ALLOW reste une liste de destinations permises (restriction) : elle n'ouvre pas les adresses internes."""
    monkeypatch.setenv("ONTOFORGE_PUBLIC", "1")
    monkeypatch.setenv("ONTOFORGE_EGRESS_ALLOW", "fuseki.corp.example")
    monkeypatch.delenv("ONTOFORGE_EGRESS_ALLOW_INTERNAL", raising=False)
    fake_dns(monkeypatch, {"fuseki.corp.example": ["10.0.0.7"]})
    with pytest.raises(netguard.NetGuardError):
        netguard.post("https://fuseki.corp.example/s", data={})


@pytest.mark.parametrize("location,keeps", [("https://a.example.org:8443/x", False), ("http://a.example.org/x", False),
                                            ("https://A.EXAMPLE.ORG/y", True), ("https://a.example.org:443/z", True)])
def test_l39_06_credentials_dropped_when_scheme_host_or_port_changes(auth_only, monkeypatch, location, keeps):
    fake_dns(monkeypatch, {"a.example.org": ["93.184.216.34"]})
    seen = []

    def handler(req):
        seen.append((str(req.url), req.headers.get("authorization")))
        return httpx.Response(307, headers={"location": location}) if len(seen) == 1 else httpx.Response(200)
    mock_client(monkeypatch, handler)
    netguard.post("https://a.example.org/", data={}, headers={"Authorization": "Bearer " + "x" * 12})
    assert len(seen) == 2 and (seen[1][1] is not None) == keeps, seen


def test_refused_error_never_carries_the_start_of_the_host_response(auth_only, monkeypatch):
    from ontoforge.queries import endpoint as ep
    from ontoforge.settings.models import EndpointConfig
    monkeypatch.setattr(netguard, "request", lambda m, u, **k: httpx.Response(500, text="DEBUT-DE-LA-REPONSE", request=httpx.Request(m, u)))
    with pytest.raises(ep.EndpointError) as e:
        ep.run_select(EndpointConfig(id="x", name="X", url="https://exemple.org/sparql"), "SELECT * WHERE {?s ?p ?o}")
    assert "DEBUT" not in str(e.value) and "HTTP 500" in str(e.value)
    monkeypatch.delenv("ONTOFORGE_AUTH")      # usage local : le détail reste utile à l'utilisateur unique
    monkeypatch.setattr(httpx.Client, "post", lambda self, url, **k: httpx.Response(500, text="DETAIL-LOCAL", request=httpx.Request("POST", url)))
    with pytest.raises(ep.EndpointError) as e:
        ep.run_select(EndpointConfig(id="x", name="X", url="http://localhost:3030/sparql"), "SELECT * WHERE {?s ?p ?o}")
    assert "DETAIL-LOCAL" in str(e.value)


def test_registered_endpoint_refusal_is_generic(auth_only):
    from ontoforge.queries import endpoint as ep
    from ontoforge.settings.models import EndpointConfig
    e = EndpointConfig(id="fuseki-rh", name="Fuseki RH", url="http://secret-host.corp.example:7777/sparql")
    with pytest.raises(ep.EndpointError) as exc:
        ep.run_select(e, "ASK {}")
    m = str(exc.value)
    assert "fuseki-rh" in m and "secret-host" not in m and "7777" not in m
    t = EndpointConfig(id="temporaire", name="Temporaire", url="http://10.9.8.7/sparql")   # adresse saisie par l'appelant : motif conservé
    with pytest.raises(ep.EndpointError) as exc:
        ep.run_select(t, "ASK {}")
    assert "10.9.8.7" in str(exc.value)


# ---- L39-01 à L39-03 : processus fils SHACL -------------------------------------------------------------------------------------------

def test_l39_01_shacl_concurrency_is_capped_and_answer_is_503(monkeypatch):
    from fastapi.testclient import TestClient
    from ontoforge.main import app
    from ontoforge.shacl import validate as v
    started, release = threading.Event(), threading.Event()

    def slow(*a, **k):
        started.set()
        release.wait(5)
        return True, v.rdflib.Graph(), ""
    monkeypatch.setattr(v, "_run_isolated_locked", slow)
    monkeypatch.setattr(v, "_SLOTS", threading.BoundedSemaphore(1))
    from ontoforge.core.shapes_model import ShapesModel
    t = threading.Thread(target=lambda: v.validate("<a:s> <a:p> <a:o> .", ShapesModel(), None, "nt"))
    t.start()
    assert started.wait(5)
    with pytest.raises(v.ShaclBusyError):
        v.validate("<a:s> <a:p> <a:o> .", ShapesModel(), None, "nt")
    c = TestClient(app)
    pid = c.post("/api/projects", json={"name": "Busy", "sample": "automaint"}).json()["id"]
    r = c.post(f"/api/projects/{pid}/shacl/validate", files={"file": ("d.ttl", b"<http://e/a> <http://e/p> <http://e/b> .", "text/turtle")})
    assert r.status_code == 503 and r.headers["retry-after"] == "5" and r.json()["code"] == "busy", r.text
    release.set()
    t.join(10)
    assert v._SLOTS.acquire(blocking=False)   # le créneau a été rendu


def test_l39_01_slot_count_is_configurable(monkeypatch):
    from ontoforge.shacl import validate as v
    monkeypatch.setenv("ONTOFORGE_SHACL_SLOTS", "5")
    assert v._slot_count() == 5
    monkeypatch.setenv("ONTOFORGE_SHACL_SLOTS", "zéro")
    assert v._slot_count() == 2
    monkeypatch.setenv("ONTOFORGE_SHACL_SLOTS", "0")
    assert v._slot_count() == 1


def test_l39_02_no_preexec_fn_anywhere_in_the_backend():
    for f in (ROOT / "backend" / "ontoforge").rglob("*.py"):
        code = "\n".join(ln for ln in f.read_text(encoding="utf-8").splitlines() if not ln.lstrip().startswith(("#", '"""')))
        assert "preexec_fn=" not in code, f


def test_l39_02_limits_are_applied_by_the_child_itself(tmp_path):
    script = tmp_path / "probe.py"
    script.write_text("import resource, sys, json\n"
                      "print(json.dumps({'as': resource.getrlimit(resource.RLIMIT_AS)[0], 'cpu': resource.getrlimit(resource.RLIMIT_CPU)[0],\n"
                      "                  'fsize': resource.getrlimit(resource.RLIMIT_FSIZE)[0], 'argv': sys.argv[1:]}))\n", encoding="utf-8")
    out = childproc.run_limited(script, b"", timeout=20, mem_mb=1500, cpu_s=9, fsize=0, args=["a"])
    import json
    d = json.loads(out.stdout)
    assert d == {"as": 1500 << 20, "cpu": 9, "fsize": 0, "argv": ["a"]}, out.stderr


def test_l39_02_shacl_ceilings_still_hold(monkeypatch):
    """Régression du plafond de temps : un sh:pattern pathologique est interrompu au délai réglé."""
    from ontoforge.shacl.validate import ShaclLimitError, _run_isolated
    import rdflib
    monkeypatch.setenv("ONTOFORGE_SHACL_TIMEOUT_S", "3")
    sg = rdflib.Graph().parse(data='''@prefix sh: <http://www.w3.org/ns/shacl#> . @prefix e: <http://e/> .
e:S a sh:NodeShape ; sh:targetClass e:C ; sh:property [ sh:path e:p ; sh:pattern "^(a+)+$" ] .''', format="turtle")
    dg = rdflib.Graph().parse(data='@prefix e: <http://e/> . e:x a e:C ; e:p "' + "a" * 40 + '!" .', format="turtle")
    t0 = time.time()
    with pytest.raises(ShaclLimitError):
        _run_isolated(dg, sg, None, "none")
    assert time.time() - t0 < 10


def test_l39_03_child_gets_a_minimal_environment(tmp_path, monkeypatch):
    monkeypatch.setenv("ONTOFORGE_SECRET_KEY", "cle-maitre-de-test-" + "z" * 20)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "valeur-factice-" + "q" * 10)
    monkeypatch.setenv("ONTOFORGE_AUTH_USERS", "u:hash")
    monkeypatch.setenv("LANG", "C.UTF-8")
    script = tmp_path / "env.py"
    script.write_text("import os, json; print(json.dumps(sorted(os.environ)))\n", encoding="utf-8")
    import json
    names = json.loads(childproc.run_limited(script, b"", timeout=20, mem_mb=1024, cpu_s=10).stdout)
    assert set(names) <= {"PATH", "LANG", "LC_ALL", "PYTHONPATH", "LC_CTYPE"}   # LC_CTYPE : posé par l'interpréteur lui-même
    assert "PATH" in names and not any(("KEY" in n or "SECRET" in n or "AUTH" in n) for n in names)
    assert set(childproc.minimal_env()) <= {"PATH", "LANG", "LC_ALL", "PYTHONPATH"}


# ---- L39-04 : plafond « lourd » élargi -------------------------------------------------------------------------------------------

@pytest.mark.parametrize("suffix", ["conformance", "graph", "ops", "ops/undo", "ops/redo", "export/ontology", "export/shapes", "files", "files/onto.ttl",
                                    "query/values", "query/options"])
def test_l39_04_costly_routes_are_in_the_heavy_class(suffix):
    from ontoforge import ratelimit
    assert ratelimit.category(f"/api/projects/p1/{suffix}") == "heavy", suffix
    assert ratelimit.category("/api/projects/p1/versions") is None


def test_l39_04_env_example_matches_the_code():
    from ontoforge import ratelimit
    txt = (ROOT / ".env.example").read_text(encoding="utf-8")
    m = re.search(r"ONTOFORGE_RATE_HEAVY_PER_MIN=(\d+)", txt)
    assert m and int(m.group(1)) == ratelimit.limits()["heavy"] == 120


# ---- L39-05 : fichier de clé préexistant -------------------------------------------------------------------------------------------

def test_l39_05_existing_key_file_is_tightened_to_600(tmp_path, monkeypatch, caplog):
    from cryptography.fernet import Fernet
    from ontoforge.settings import crypto
    for k in ("ONTOFORGE_SETTINGS_KEY", "ONTOFORGE_SECRET_KEY"):
        monkeypatch.delenv(k, raising=False)
    f = tmp_path / "cle" / ".secret"
    f.parent.mkdir()
    f.write_text(Fernet.generate_key().decode(), encoding="utf-8")
    f.chmod(0o644)
    monkeypatch.setenv("ONTOFORGE_SECRET_FILE", str(f))
    with caplog.at_level("WARNING", logger="ontoforge.settings"):
        assert crypto.master_secret()
    assert stat.S_IMODE(f.stat().st_mode) == 0o600
    assert any("lisible par d'autres" in r.getMessage() and "600" in r.getMessage() for r in caplog.records)
    caplog.clear()
    crypto.master_secret()
    assert not caplog.records   # déjà en 600 : silence


# ---- L39-07 : nginx --------------------------------------------------------------------------------------------------------------------

def test_l39_07_nginx_keeps_the_port_in_host():
    conf = (ROOT / "frontend" / "nginx.conf").read_text(encoding="utf-8")
    assert re.search(r"^\s*proxy_set_header Host \$http_host;", conf, re.M)
    assert not re.search(r"proxy_set_header Host \$host;", conf)
