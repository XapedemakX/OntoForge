"""L39-secu : exposition réseau (SEC-01, SEC-02, SEC-12, SEC-16), conteneurs (SEC-11) et constructions reproductibles (SEC-14).

Docker n'étant pas toujours disponible, les contrôles portent sur les fichiers (compose, Dockerfile, nginx) ; le démarrage réel
d'`docker compose up` reste à rejouer par une personne disposant d'un démon (voir journal/L39-secu/rapport.md).
"""
import re
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]


def build(monkeypatch, **env):
    for k in ("ONTOFORGE_AUTH", "ONTOFORGE_PUBLIC", "ONTOFORGE_STATIC_DIR", "ONTOFORGE_CORS_ORIGINS", "ONTOFORGE_BIND_HOST"):
        monkeypatch.delenv(k, raising=False)
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    from ontoforge.main import create_app
    return TestClient(create_app())


# ---- SEC-01 ---------------------------------------------------------------------------------------------------------
def test_sec01_compose_publishes_only_on_loopback_by_default():
    dc = yaml.safe_load((ROOT / "docker-compose.yml").read_text(encoding="utf-8"))
    ports = [p for svc in dc["services"].values() for p in svc.get("ports", [])]
    assert ports, "aucun port publié"
    for p in ports:
        assert str(p).startswith("${ONTOFORGE_BIND:-127.0.0.1}:"), p
    assert not any("ports" in dc["services"][s] for s in ("backend", "init-perms"))


def test_sec01_warning_when_open_without_auth_only():
    from ontoforge import hardening
    assert hardening.exposure_warning({"ONTOFORGE_BIND_HOST": "0.0.0.0"}, False)
    assert hardening.exposure_warning({"ONTOFORGE_BIND_HOST": "192.168.1.5"}, False)
    assert hardening.exposure_warning({"ONTOFORGE_BIND_HOST": "0.0.0.0"}, True) is None
    assert hardening.exposure_warning({"ONTOFORGE_BIND_HOST": "127.0.0.1"}, False) is None
    assert hardening.exposure_warning({"ONTOFORGE_BIND_HOST": "localhost"}, False) is None
    assert "authentification" in hardening.exposure_warning({}, False, ["uvicorn", "--host", "0.0.0.0"]) or Path("/.dockerenv").exists()


def test_sec01_startup_logs_the_warning(monkeypatch, capsys):
    build(monkeypatch, ONTOFORGE_BIND_HOST="0.0.0.0")
    assert "SANS authentification" in capsys.readouterr().err


# ---- SEC-02 ---------------------------------------------------------------------------------------------------------
def test_sec02_cors_closed_by_default_open_for_listed_origin(monkeypatch):
    hdr = {"Origin": "https://evil.example"}
    c = build(monkeypatch)
    assert "access-control-allow-origin" not in c.get("/api/projects", headers=hdr).headers
    pre = c.options("/api/projects", headers={**hdr, "Access-Control-Request-Method": "DELETE"})
    assert "access-control-allow-origin" not in pre.headers
    c = build(monkeypatch, ONTOFORGE_CORS_ORIGINS="http://localhost:5173")
    assert c.get("/api/projects", headers={"Origin": "http://localhost:5173"}).headers["access-control-allow-origin"] == "http://localhost:5173"
    assert "access-control-allow-origin" not in c.get("/api/projects", headers=hdr).headers


# ---- SEC-12 ---------------------------------------------------------------------------------------------------------
def test_sec12_nginx_headers_and_csp_match_the_server():
    from ontoforge import security
    conf = (ROOT / "frontend" / "nginx.conf").read_text(encoding="utf-8")
    inc = (ROOT / "frontend" / "security-headers.conf").read_text(encoding="utf-8")
    assert "server_tokens off" in conf
    assert 'Content-Security-Policy "' + security.CSP + '" always' in inc
    for h in ("X-Frame-Options \"DENY\"", "X-Content-Type-Options \"nosniff\"", "Referrer-Policy", "Permissions-Policy"):
        assert f"add_header {h}" in inc or h in inc
    # nginx n'hérite pas add_header d'un bloc parent : CHAQUE location doit inclure le fichier
    assert conf.count("location ") == conf.count("include /etc/nginx/ontoforge-security-headers.conf;") >= 5
    assert "proxy_set_header X-Forwarded-For $remote_addr;" in conf and "no-store" in conf


# ---- SEC-11 ---------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("path", ["backend/Dockerfile", "deploy/cloudrun/Dockerfile"])
def test_sec11_python_images_run_as_non_root(path):
    lines = [ln.strip() for ln in (ROOT / path).read_text(encoding="utf-8").splitlines()]
    users = [ln for ln in lines if ln.startswith("USER ")]
    assert users and users[-1] != "USER root" and "USER 0" not in users[-1]
    assert any("useradd" in ln and "10001" in ln for ln in lines)


def test_sec11_frontend_image_is_unprivileged_and_listens_above_1024():
    df = (ROOT / "frontend" / "Dockerfile").read_text(encoding="utf-8")
    assert re.search(r"^FROM nginxinc/nginx-unprivileged:", df, re.M)
    assert re.search(r"listen 8080;", (ROOT / "frontend" / "nginx.conf").read_text(encoding="utf-8"))
    dc = yaml.safe_load((ROOT / "docker-compose.yml").read_text(encoding="utf-8"))
    assert dc["services"]["frontend"]["ports"][0].endswith(":8080")


def test_sec11_volumes_owned_by_app_user_before_volume_and_init_service():
    df = (ROOT / "backend" / "Dockerfile").read_text(encoding="utf-8")
    assert df.index("chown ontoforge:ontoforge /data /keys") < df.index("VOLUME /data")
    dc = yaml.safe_load((ROOT / "docker-compose.yml").read_text(encoding="utf-8"))
    assert dc["services"]["backend"]["depends_on"]["init-perms"]["condition"] == "service_completed_successfully"
    assert dc["services"]["backend"]["environment"]["ONTOFORGE_SECRET_FILE"].startswith("/keys/")
    assert dc["services"]["init-perms"]["user"] in ("0:0", "root", 0)  # seule étape en root : un chown unique, jamais l'application


# ---- SEC-14 ---------------------------------------------------------------------------------------------------------
def test_sec14_reproducible_builds():
    for path in ("frontend/Dockerfile", "deploy/cloudrun/Dockerfile"):
        run = "\n".join(ln for ln in (ROOT / path).read_text(encoding="utf-8").splitlines() if ln.startswith("RUN "))
        assert "npm install" not in run and "|| npm" not in run and "RUN npm ci" in run, path
    for path in ("backend/Dockerfile", "deploy/cloudrun/Dockerfile"):
        txt = (ROOT / path).read_text(encoding="utf-8")
        assert "-c constraints.txt" in txt and "backend/constraints.txt" in txt, path


def test_sec14_constraints_match_pyproject_pins():
    cons = {}
    for ln in (ROOT / "backend" / "constraints.txt").read_text(encoding="utf-8").splitlines():
        if ln and not ln.startswith("#"):
            name, ver = ln.split("==")
            cons[name.lower().replace("_", "-")] = ver
    py = (ROOT / "backend" / "pyproject.toml").read_text(encoding="utf-8")
    pins = re.findall(r'"([A-Za-z0-9_.-]+)(?:\[[a-z]+\])?==([0-9][^"]*)"', py)
    assert len(pins) >= 14
    for name, ver in pins:
        if name in ("pytest", "graphql-core"):
            continue  # extra dev : hors des images
        assert cons.get(name.lower().replace("_", "-")) == ver, f"{name} {ver} != contraintes {cons.get(name.lower())}"
    assert "pytest" not in cons


def test_sec09_server_dependencies_at_or_above_fixed_versions():
    """SEC-09 (L46) : serveur web et analyseur multipart au moins aux versions corrigées ; CI : étape pip-audit."""
    def ver(s):
        return tuple(int(x) for x in s.split("."))
    cons = {}
    for ln in (ROOT / "backend" / "constraints.txt").read_text(encoding="utf-8").splitlines():
        if ln and not ln.startswith("#"):
            name, v = ln.split("==")
            cons[name] = v
    assert ver(cons["starlette"]) >= (1, 3, 1)
    assert ver(cons["python-multipart"]) >= (0, 0, 31)
    ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert "pip-audit" in ci and "backend/constraints.txt" in ci


# ---- SEC-16 ---------------------------------------------------------------------------------------------------------
def test_sec16_cloudrun_draft_restricts_forwarded_ips_and_requires_egress_list():
    txt = (ROOT / "deploy" / "cloudrun" / "Dockerfile").read_text(encoding="utf-8")
    cmd = txt[txt.index("CMD ["):]
    assert "--forwarded-allow-ips='*'" not in txt and "FORWARDED_ALLOW_IPS:-127.0.0.1" in cmd
    assert "ONTOFORGE_EGRESS_ALLOW:?" in cmd


def test_sec16_startup_warning_for_public_without_egress_list():
    from ontoforge import hardening
    assert hardening.egress_warning({"ONTOFORGE_PUBLIC": "1"}, True)
    assert hardening.egress_warning({"ONTOFORGE_EGRESS_ALLOW": "api.example.org"}, True) is None
    assert hardening.egress_warning({}, False) is None


def test_sec16_netguard_allowlist_blocks_other_hosts(monkeypatch):
    from ontoforge import netguard
    monkeypatch.setenv("ONTOFORGE_EGRESS_ALLOW", "api.example.org")
    with pytest.raises(netguard.NetGuardError):
        netguard.check_url("https://autre.example.net/")
    assert netguard.check_url("https://api.example.org/v1")[0] == "api.example.org"


def test_api_like_paths_never_served_as_spa(tmp_path):
    """« //api/… » et « /API/… » répondent 404 JSON au lieu de la page du front (défense en profondeur, contre-audit L39)."""
    import asyncio
    from ontoforge.security import SpaStatic
    (tmp_path / "index.html").write_text("<html>idx</html>")
    app = SpaStatic(tmp_path)
    for path in ("//api/projects", "/API/projects", "/Api"):
        sent = []
        async def receive():
            return {"type": "http.request"}
        async def send(m):
            sent.append(m)
        asyncio.run(app({"type": "http", "method": "GET", "path": path, "headers": [], "query_string": b""}, receive, send))
        assert sent[0]["status"] == 404, path
