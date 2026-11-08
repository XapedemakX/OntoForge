"""Authentification par mot de passe (L27) : refus sans session, connexion, CSRF, limitation, déconnexion, cookie."""
import pytest
from fastapi.testclient import TestClient

from ontoforge.auth import limiter, passwords, session as sess
from ontoforge.auth.config import AuthConfigError, load_config, parse_users

PW = "correct horse battery"
KEY = "k" * 48
HASH = passwords.hash_password(PW)
BHASH = passwords.hash_password("bcrypt-password-ok", "bcrypt")


def make(monkeypatch, **env):
    from ontoforge.main import create_app
    base = {"ONTOFORGE_AUTH": "password", "ONTOFORGE_AUTH_USERS": f"demo:{HASH};bob:{BHASH}", "ONTOFORGE_SECRET_KEY": KEY}
    base.update(env)
    for k in ("ONTOFORGE_AUTH", "ONTOFORGE_AUTH_USERS", "ONTOFORGE_AUTH_USERS_FILE", "ONTOFORGE_PUBLIC", "ONTOFORGE_SESSION_HOURS"):
        monkeypatch.delenv(k, raising=False)
    for k, v in base.items():
        monkeypatch.setenv(k, v)
    limiter.reset()
    return TestClient(create_app(), base_url="https://testserver")


def login(c, user="demo", pw=PW):
    return c.post("/api/auth/login", json={"username": user, "password": pw})


def test_disabled_by_default(monkeypatch):
    monkeypatch.delenv("ONTOFORGE_AUTH", raising=False)
    monkeypatch.delenv("ONTOFORGE_PUBLIC", raising=False)
    from ontoforge.main import create_app
    c = TestClient(create_app())
    assert c.get("/api/projects").status_code == 200
    assert c.get("/api/auth/session").json()["enabled"] is False


def test_api_refused_without_session_health_and_auth_open(monkeypatch):
    c = make(monkeypatch)
    for path in ("/api/projects", "/api/settings", "/api/samples", "/api/nope"):
        r = c.get(path)
        assert r.status_code == 401 and r.json()["code"] == "auth_required", path
    assert c.post("/api/projects", json={"name": "x"}).status_code == 401
    assert c.get("/api/health").status_code == 200
    s = c.get("/api/auth/session").json()
    assert s == {**s, "enabled": True, "authenticated": False, "csrf": None}


def test_login_cookie_flags_and_access(monkeypatch):
    c = make(monkeypatch)
    r = login(c)
    assert r.status_code == 200 and r.json()["user"] == "demo"
    sc = r.headers["set-cookie"]
    assert sc.startswith("__Host-ontoforge_session=") and "HttpOnly" in sc and "Secure" in sc and "SameSite=lax" in sc and "Path=/" in sc
    assert "Max-Age=28800" in sc
    assert c.get("/api/projects").status_code == 200
    assert c.get("/api/auth/session").json()["authenticated"] is True


def test_bcrypt_account_and_case_insensitive_user(monkeypatch):
    c = make(monkeypatch)
    assert login(c, "BOB", "bcrypt-password-ok").status_code == 200


def test_bad_credentials(monkeypatch):
    c = make(monkeypatch)
    for u, p in (("demo", "nope"), ("ghost", PW), ("", ""), ("demo", "")):
        limiter.reset()
        r = login(c, u, p)
        assert r.status_code == 401 and r.json()["code"] == "bad_credentials"
        assert "set-cookie" not in r.headers
    assert c.get("/api/projects").status_code == 401


def test_csrf_required_on_unsafe_methods(monkeypatch):
    c = make(monkeypatch)
    csrf = login(c).json()["csrf"]
    r = c.post("/api/projects", json={"name": "csrf-test"})
    assert r.status_code == 403 and r.json()["code"] == "csrf"
    assert c.post("/api/projects", json={"name": "csrf-test"}, headers={"X-CSRF-Token": "x" * len(csrf)}).status_code == 403
    ok = c.post("/api/projects", json={"name": "csrf-test"}, headers={"X-CSRF-Token": csrf})
    assert ok.status_code in (200, 201)
    assert c.get("/api/projects").status_code == 200   # GET : pas de jeton requis
    r = c.delete(f"/api/projects/{ok.json()['id']}")
    assert r.status_code == 403
    assert c.delete(f"/api/projects/{ok.json()['id']}", headers={"X-CSRF-Token": csrf}).status_code in (200, 204)


def test_cross_origin_refused(monkeypatch):
    c = make(monkeypatch)
    csrf = login(c).json()["csrf"]
    r = c.post("/api/projects", json={"name": "x"}, headers={"X-CSRF-Token": csrf, "Origin": "https://evil.example"})
    assert r.status_code == 403 and r.json()["code"] == "bad_origin"
    r = c.post("/api/auth/login", json={"username": "demo", "password": PW}, headers={"Origin": "https://evil.example"})
    assert r.status_code == 403
    assert c.post("/api/projects", json={"name": "same"}, headers={"X-CSRF-Token": csrf, "Origin": "https://testserver"}).status_code in (200, 201)


def test_logout_revokes_session(monkeypatch):
    c = make(monkeypatch)
    csrf = login(c).json()["csrf"]
    token = c.cookies.get("__Host-ontoforge_session")
    assert c.post("/api/auth/logout").status_code == 403           # sans CSRF
    assert c.post("/api/auth/logout", headers={"X-CSRF-Token": csrf}).status_code == 200
    assert c.get("/api/projects").status_code == 401
    c.cookies.set("__Host-ontoforge_session", token)                # rejouer l'ancien cookie
    assert c.get("/api/projects").status_code == 401


def test_logout_without_session_is_idempotent(monkeypatch):
    c = make(monkeypatch)
    assert c.post("/api/auth/logout").status_code == 200


def test_tampered_and_expired_cookie(monkeypatch):
    c = make(monkeypatch)
    login(c)
    tok = c.cookies.get("__Host-ontoforge_session")
    head, body, sig = tok.split(".")
    c.cookies.clear()
    for bad in (f"{head}.{body}.{sig[:-2]}AA", f"{head}.{body}x.{sig}", "garbage", ""):
        c.cookies.set("__Host-ontoforge_session", bad)
        assert c.get("/api/projects").status_code == 401
    key = load_config().key
    old, _ = sess.issue(key, "demo", -1)
    c.cookies.set("__Host-ontoforge_session", old)
    assert c.get("/api/projects").status_code == 401
    other, _ = sess.issue(b"z" * 32, "demo", 1)                      # signé avec une autre clé
    c.cookies.set("__Host-ontoforge_session", other)
    assert c.get("/api/projects").status_code == 401


def test_rate_limit_progressive(monkeypatch):
    c = make(monkeypatch)
    clock = [1000.0]
    monkeypatch.setattr(limiter, "_now", lambda: clock[0])
    assert login(c, pw="x").status_code == 401           # 1
    assert login(c, pw="x").status_code == 401           # 2 : libre
    r = login(c, pw="x")                                 # 3 : accepté puis bloqué 2 s
    assert r.status_code == 401 and r.json()["retry_after"] == 3
    r = login(c)                                         # bon mot de passe pendant le blocage : refusé aussi
    assert r.status_code == 429 and r.json()["code"] == "rate_limited" and int(r.headers["Retry-After"]) >= 1
    clock[0] += 3
    assert login(c, pw="x").status_code == 401           # 4 : blocage 4 s
    clock[0] += 3
    assert login(c).status_code == 429
    clock[0] += 2
    assert login(c).status_code == 200                   # succès : compteur remis à zéro
    assert limiter.retry_after("testclient") == 0
    delays = [limiter.failure("1.2.3.4") for _ in range(14)]
    assert delays[:3] == [0, 0, 2] and delays[3] == 4 and delays[4] == 8 and max(delays) == limiter.MAX_DELAY


def test_rate_limit_is_per_ip_and_uses_forwarded_for(monkeypatch):
    c = make(monkeypatch, ONTOFORGE_PROXY_HOPS="1")
    xff = lambda ip: {"X-Forwarded-For": f"6.6.6.6, {ip}"}   # l'entrée de gauche est falsifiable, celle de droite non
    for _ in range(3):
        c.post("/api/auth/login", json={"username": "demo", "password": "x"}, headers=xff("9.9.9.9"))
    assert c.post("/api/auth/login", json={"username": "demo", "password": PW}, headers=xff("9.9.9.9")).status_code == 429
    assert c.post("/api/auth/login", json={"username": "demo", "password": PW}, headers=xff("8.8.4.4")).status_code == 200
    assert limiter.client_ip({"x-forwarded-for": "1.1.1.1, 2.2.2.2"}, "10.0.0.1", 0) == "10.0.0.1"
    assert limiter.client_ip({"x-forwarded-for": "not-an-ip"}, "10.0.0.1", 1) == "10.0.0.1"


def test_config_refuses_unsafe_setups(monkeypatch):
    with pytest.raises(AuthConfigError):
        load_config({"ONTOFORGE_AUTH": "password", "ONTOFORGE_SECRET_KEY": KEY})                      # aucun compte
    with pytest.raises(AuthConfigError):
        load_config({"ONTOFORGE_AUTH": "password", "ONTOFORGE_AUTH_USERS": f"demo:{HASH}", "ONTOFORGE_SECRET_KEY": "court"})
    with pytest.raises(AuthConfigError):
        parse_users("demo:motdepasse-en-clair")
    with pytest.raises(AuthConfigError):
        load_config({"ONTOFORGE_PUBLIC": "1"})                                                        # public sans auth
    assert load_config({"ONTOFORGE_PUBLIC": "1", "ONTOFORGE_ALLOW_PUBLIC_NOAUTH": "1"}).enabled is False
    assert load_config({}).enabled is False


def test_users_file_and_session_hours(monkeypatch, tmp_path):
    f = tmp_path / "users"
    f.write_text(f"carol:{HASH}\n", encoding="utf-8")
    c = make(monkeypatch, ONTOFORGE_AUTH_USERS=f"demo:{HASH}", ONTOFORGE_AUTH_USERS_FILE=str(f), ONTOFORGE_SESSION_HOURS="2")
    r = login(c, "carol")
    assert r.status_code == 200 and "Max-Age=7200" in r.headers["set-cookie"]
    assert login(c, "demo").status_code == 200


def test_password_helpers():
    assert passwords.verify_password(HASH, PW) and not passwords.verify_password(HASH, PW + "x")
    assert not passwords.verify_password("pas-un-hash", PW) and not passwords.verify_password(HASH, "")
    assert not passwords.verify_password(BHASH, "x" * 100)
    with pytest.raises(ValueError):
        passwords.hash_password("x" * 80, "bcrypt")


def test_hash_cli(capsys, monkeypatch):
    import io
    from ontoforge.auth.__main__ import main
    monkeypatch.setattr("sys.stdin", io.StringIO("une phrase de passe longue\n"))
    assert main(["hash", "--stdin", "--user", "Demo"]) == 0
    out = capsys.readouterr().out.strip()
    name, _, h = out.partition(":")
    assert name == "demo" and h.startswith("$argon2id$") and passwords.verify_password(h, "une phrase de passe longue")
    monkeypatch.setattr("sys.stdin", io.StringIO("une phrase de passe longue"))
    assert main(["hash", "--stdin", "--bcrypt"]) == 0 and capsys.readouterr().out.startswith("$2b$")
    monkeypatch.setattr("sys.stdin", io.StringIO("court"))
    assert main(["hash", "--stdin"]) == 2
    assert main(["secret"]) == 0 and len(capsys.readouterr().out.strip()) >= 48
