"""L42 (D-L42-01) : administration des comptes, langue par compte, administrateur sur tous les projets, plus de génération par le lecteur."""
import json
import os
import stat
import time

import pytest
from fastapi.testclient import TestClient
from starlette.routing import Mount

from ontoforge.auth import limiter, passwords
from ontoforge.auth.accounts import AccountDirectory, AccountError, provisional_password
from ontoforge.auth.config import AuthConfig
from ontoforge.collab.routes import ADMIN_PREFIX

PW = "correct horse battery"          # secrets de test assemblés à l'exécution (pas de littéral détectable)
NEWPW = "-".join(["tango", "uniform", "victor", str(os.getpid())])
HASH = passwords.hash_password(PW)
ENV = {"ONTOFORGE_AUTH": "password", "ONTOFORGE_SECRET_KEY": "k" * 48, "ONTOFORGE_AUTH_USERS": f"alice:{HASH};bob:{HASH}", "ONTOFORGE_AUTH_ADMINS": "alice"}


@pytest.fixture(scope="module")
def app(tmp_path_factory):
    mp = pytest.MonkeyPatch()
    tmp = tmp_path_factory.mktemp("l42")
    mp.setenv("ONTOFORGE_DATA", str(tmp))
    mp.setenv("ONTOFORGE_LOCAL_STORE_DIR", str(tmp / "ls"))
    for k in ("ONTOFORGE_PUBLIC", "ONTOFORGE_AUTH_USERS_FILE", "ONTOFORGE_ACCOUNTS_FILE"):
        mp.delenv(k, raising=False)
    for k, v in ENV.items():
        mp.setenv(k, v)
    limiter.reset()
    from ontoforge.main import create_app
    a = create_app()
    a.data_dir = tmp
    yield a
    mp.undo()


@pytest.fixture(autouse=True)
def _fresh():
    limiter.reset()


class User:
    def __init__(self, app, name, pw=PW):
        self.c = TestClient(app, base_url="https://testserver")
        r = self.c.post("/api/auth/login", json={"username": name, "password": pw})
        assert r.status_code == 200, r.text
        self.name, self.csrf, self.info = name, r.json()["csrf"], r.json()

    def req(self, method, url, rev="*", **kw):
        h = {"X-CSRF-Token": self.csrf, **kw.pop("headers", {})}
        if rev is not None and (method not in ("GET", "HEAD") or "/generate/" in url):
            h["If-Match"] = str(rev)
        return self.c.request(method, url, headers=h, **kw)

    def get(self, url, **kw): return self.req("GET", url, **kw)
    def post(self, url, **kw): return self.req("POST", url, **kw)
    def put(self, url, **kw): return self.req("PUT", url, **kw)
    def delete(self, url, **kw): return self.req("DELETE", url, **kw)


@pytest.fixture(scope="module")
def alice(app):
    return User(app, "alice")


@pytest.fixture(scope="module")
def bob(app):
    return User(app, "bob")


def make(alice, login, admin=False, password=None):
    r = alice.post("/api/admin/accounts", json={"login": login, "admin": admin, **({"password": password} if password else {})}, rev=None)
    assert r.status_code == 201, r.text
    return r.json()


def login_as(app, login, pw):
    return User(app, login, pw)


def settle(app, alice, login):
    """Crée ``login`` (provisoire), le connecte, change le mot de passe : renvoie un navigateur utilisable."""
    prov = make(alice, login)["provisional_password"]
    u = User(app, login, prov)
    r = u.post("/api/auth/password", json={"current": prov, "new": NEWPW}, rev=None)
    assert r.status_code == 200, r.text
    u.csrf = r.json()["csrf"]
    return u


# ---- 1. magasin de comptes -------------------------------------------------------------------------------------------------------

def test_create_account_hashes_password_and_file_is_600(app, alice):
    out = make(alice, "dora")
    prov = out["provisional_password"]
    assert len(prov) >= 16 and out["account"]["login"] == "dora" and out["account"]["source"] == "interface" and out["account"]["must_change"] is True
    f = app.data_dir / "accounts.json"
    assert stat.S_IMODE(f.stat().st_mode) == 0o600
    raw = f.read_text()
    assert prov not in raw and json.loads(raw)["accounts"]["dora"]["hash"].startswith("$argon2")
    assert not [p for p in app.data_dir.iterdir() if p.name.endswith(".tmp")]                   # écriture atomique : aucun résidu
    # un mot de passe saisi n'est jamais renvoyé ; trop court refusé
    assert make(alice, "dora2", password=NEWPW)["provisional_password"] is None
    r = alice.post("/api/admin/accounts", json={"login": "dora3", "password": "court"}, rev=None)
    assert r.status_code == 422 and r.json()["code"] == "password_too_short"
    assert alice.post("/api/admin/accounts", json={"login": "Mauvais Nom"}, rev=None).json()["code"] == "bad_login"
    assert alice.post("/api/admin/accounts", json={"login": "dora"}, rev=None).json()["code"] == "login_taken"
    assert alice.post("/api/admin/accounts", json={"login": "bob"}, rev=None).json()["code"] == "login_taken"   # collision avec la configuration


def test_store_file_loosened_is_tightened_to_600(app, alice):
    f = app.data_dir / "accounts.json"
    make(alice, "loose1")
    os.chmod(f, 0o644)
    alice.get("/api/admin/accounts")
    assert stat.S_IMODE(f.stat().st_mode) == 0o600


def test_list_merges_config_and_store(alice):
    make(alice, "erin")
    rows = {a["login"]: a for a in alice.get("/api/admin/accounts").json()["accounts"]}
    assert rows["alice"]["source"] == "config" and rows["alice"]["managed"] and rows["alice"]["admin"] and rows["alice"]["active"]
    assert rows["bob"]["managed"] and not rows["bob"]["admin"]
    assert rows["erin"]["source"] == "interface" and not rows["erin"]["managed"]
    assert all("hash" not in a and "password" not in json.dumps(a) for a in rows.values())
    assert rows["alice"]["last_login"]                                                          # la connexion de la fixture est notée


def test_config_account_is_not_editable_from_the_interface(alice, bob):
    for url, kw in (("/api/admin/accounts/bob/disable", {}), ("/api/admin/accounts/bob/enable", {}),
                    ("/api/admin/accounts/bob/admin", {"json": {"admin": True}})):
        r = alice.post(url, rev=None, **kw)
        assert r.status_code == 409 and r.json()["code"] == "managed_by_config", (url, r.text)
    assert alice.delete("/api/admin/accounts/bob", rev=None).json()["code"] == "managed_by_config"
    # D-L43-01 : le mot de passe d'un compte de la configuration n'est plus verrouillé (voir test_l43_password.py) ; le reste l'est toujours
    assert alice.post("/api/admin/accounts/ghost/disable", rev=None).status_code == 404


def test_last_active_admin_is_protected(tmp_path, monkeypatch):
    monkeypatch.setenv("ONTOFORGE_DATA", str(tmp_path))
    d = AccountDirectory(AuthConfig(enabled=True, users={"cfg": HASH}, admins=frozenset()))   # aucune administration par la configuration
    d.create("t", "solo", NEWPW, admin=True)
    for op in (lambda: d.set_active("t", "solo", False), lambda: d.set_admin("t", "solo", False), lambda: (d.check_deletable("solo"), d.delete("t", "solo"))):
        with pytest.raises(AccountError) as e:
            op()
        assert e.value.payload["code"] == "last_admin" and d.is_admin("solo")
    d.create("t", "duo", NEWPW, admin=True)
    d.set_admin("t", "solo", False)                                                              # un second administrateur actif : permis
    with pytest.raises(AccountError):
        d.set_active("t", "duo", False)


def test_typed_password_is_also_provisional(app, alice):
    make(alice, "frank", admin=True, password=NEWPW)
    frank = User(app, "frank", NEWPW)
    assert frank.info["must_change"] is True and frank.get("/api/projects").status_code == 403


def test_disable_and_delete_cut_sessions_immediately(app, alice):
    u = settle(app, alice, "gina")
    assert u.get("/api/projects").status_code == 200
    assert alice.post("/api/admin/accounts/gina/disable", rev=None).status_code == 200
    assert u.get("/api/projects").status_code == 401                                              # session coupée sur-le-champ
    assert u.get("/api/auth/session").json()["authenticated"] is False
    bad = app_login(app, "gina", NEWPW)
    assert bad.status_code == 401 and bad.json()["code"] == "bad_credentials"                      # même réponse qu'un mauvais mot de passe
    assert alice.post("/api/admin/accounts/gina/enable", rev=None).status_code == 200
    assert User(app, "gina", NEWPW).get("/api/projects").status_code == 200                       # réactivé : on peut se reconnecter
    # suppression
    v = User(app, "gina", NEWPW)
    assert alice.delete("/api/admin/accounts/gina", rev=None).status_code == 200
    assert v.get("/api/projects").status_code == 401
    assert app_login(app, "gina", NEWPW).status_code == 401


def app_login(app, login, pw):
    return TestClient(app, base_url="https://testserver").post("/api/auth/login", json={"username": login, "password": pw})


def test_reset_password_cuts_sessions_and_forces_change(app, alice):
    u = settle(app, alice, "hugo")
    new_prov = alice.post("/api/admin/accounts/hugo/reset-password", rev=None).json()["provisional_password"]
    assert u.get("/api/projects").status_code == 401                                              # ancienne session morte
    assert app_login(app, "hugo", NEWPW).status_code == 401                                       # ancien mot de passe mort
    v = User(app, "hugo", new_prov)
    assert v.info["must_change"] is True


def test_provisional_password_must_be_changed_first(app, alice):
    prov = make(alice, "iris")["provisional_password"]
    u = User(app, "iris", prov)
    assert u.info["must_change"] is True
    for url in ("/api/projects", "/api/settings", "/api/admin/accounts"):
        r = u.get(url)
        assert r.status_code == 403 and r.json()["code"] == "password_change_required", url
    assert u.get("/api/auth/session").json()["must_change"] is True
    # règles : ancien requis, 10 caractères, différent
    assert u.post("/api/auth/password", json={"current": "faux faux faux", "new": NEWPW}, rev=None).json()["code"] == "bad_current_password"
    assert u.post("/api/auth/password", json={"current": prov, "new": "court"}, rev=None).json()["code"] == "password_too_short"
    assert u.post("/api/auth/password", json={"current": prov, "new": prov}, rev=None).json()["code"] == "password_unchanged"
    r = u.post("/api/auth/password", json={"current": prov, "new": NEWPW}, rev=None)
    assert r.status_code == 200 and r.json()["must_change"] is False
    u.csrf = r.json()["csrf"]
    assert u.get("/api/projects").status_code == 200                                              # la session renouvelée sert tout de suite
    assert app_login(app, "iris", prov).status_code == 401 and app_login(app, "iris", NEWPW).status_code == 200


def test_change_own_password_needs_session_and_csrf(app, alice):
    u = settle(app, alice, "jade")
    c = TestClient(app, base_url="https://testserver")
    assert c.post("/api/auth/password", json={"current": NEWPW, "new": NEWPW + "x"}).status_code == 401
    r = u.c.post("/api/auth/password", json={"current": NEWPW, "new": NEWPW + "x"})              # sans jeton CSRF
    assert r.status_code == 403 and r.json()["code"] == "csrf"


def test_password_change_is_rate_limited(app, alice):
    u = settle(app, alice, "kim")
    codes = [u.post("/api/auth/password", json={"current": "faux faux faux", "new": NEWPW + "y"}, rev=None).status_code for _ in range(5)]
    assert codes[:2] == [403, 403] and 429 in codes                                               # même limiteur que la connexion
    r = u.post("/api/auth/password", json={"current": NEWPW, "new": NEWPW + "y"}, rev=None)
    assert r.status_code == 429 and "Retry-After" in r.headers


def test_admin_journal_never_holds_a_secret(app, alice):
    prov = make(alice, "leo", password=NEWPW + "z")
    p2 = alice.post("/api/admin/accounts/leo/reset-password", rev=None).json()["provisional_password"]
    alice.post("/api/admin/accounts/leo/disable", rev=None)
    alice.post("/api/admin/accounts/leo/enable", rev=None)
    alice.post("/api/admin/accounts/leo/admin", json={"admin": True}, rev=None)
    alice.post("/api/admin/accounts/leo/admin", json={"admin": False}, rev=None)
    alice.delete("/api/admin/accounts/leo", rev=None)
    rows = alice.get("/api/admin/audit").json()["entries"]
    mine = [r for r in rows if r["target"] == "leo"]
    assert [r["action"] for r in mine][::-1] == ["create", "reset_password", "disable", "enable", "promote", "demote", "delete"]
    assert all(r["actor"] == "alice" for r in mine)
    blob = (app.data_dir / "admin-audit.jsonl").read_text() + json.dumps(rows)
    assert p2 not in blob and (NEWPW + "z") not in blob and "$argon2" not in blob and "password" not in json.dumps([r.get("detail") for r in rows])
    assert stat.S_IMODE((app.data_dir / "admin-audit.jsonl").stat().st_mode) == 0o600


def test_audit_detail_drops_secret_looking_keys(tmp_path, monkeypatch):
    monkeypatch.setenv("ONTOFORGE_DATA", str(tmp_path))
    d = AccountDirectory(AuthConfig(enabled=True, users={"a": HASH}, admins=frozenset({"a"})))
    d.audit("a", "x", "t", password="s1", new_hash="s2", api_token="s3", note="ok")
    assert d.audit_rows()[0]["detail"] == {"note": "ok"}


def test_provisional_passwords_are_random_and_long():
    s = {provisional_password() for _ in range(50)}
    assert len(s) == 50 and all(len(x) == 19 for x in s)


# ---- 2. routes d'administration réservées -----------------------------------------------------------------------------------------

def test_non_admin_is_refused_on_every_admin_route(app, bob):
    routes = set()
    for r in app.router.routes:
        if not isinstance(r, Mount) and hasattr(r, "methods") and r.path.startswith(ADMIN_PREFIX):
            routes |= {(m, r.path) for m in r.methods - {"HEAD"}}
    assert len(routes) >= 8
    c = TestClient(app, base_url="https://testserver")
    for m, path in sorted(routes):
        url = path.replace("{login}", "alice")
        assert c.request(m, url).status_code == 401, (m, url)                                      # sans session
        r = bob.req(m, url, rev=None, json={} if m in ("POST", "PUT") else None)
        assert r.status_code == 403 and r.json()["code"] == "admin_only", (m, url, r.text)         # compte ordinaire


def test_new_admin_can_administer_and_demoted_admin_loses_access(app, alice):
    u = settle(app, alice, "mia")
    assert u.get("/api/admin/accounts").status_code == 403
    alice.post("/api/admin/accounts/mia/admin", json={"admin": True}, rev=None)
    assert u.get("/api/admin/accounts").status_code == 200                                          # effet immédiat, sans nouvelle connexion
    alice.post("/api/admin/accounts/mia/admin", json={"admin": False}, rev=None)
    assert u.get("/api/admin/accounts").status_code == 403


def test_delete_account_transfers_projects(app, alice, bob):
    u = settle(app, alice, "nora")
    pid = u.post("/api/projects", json={"name": "De Nora"}, rev=None).json()["id"]
    u.post(f"/api/projects/{pid}/access/members", json={"login": "bob", "role": "reader"}, rev=None)
    pid2 = bob.post("/api/projects", json={"name": "De Bob"}, rev=None).json()["id"]
    bob.post(f"/api/projects/{pid2}/access/members", json={"login": "nora", "role": "editor"}, rev=None)
    r = alice.delete("/api/admin/accounts/nora", rev=None)
    assert r.status_code == 409 and r.json()["code"] == "transfer_required" and r.json()["projects"] == 1
    assert alice.delete("/api/admin/accounts/nora?transfer_to=ghost", rev=None).json()["code"] == "transfer_required"
    assert alice.delete("/api/admin/accounts/nora?transfer_to=nora", rev=None).json()["code"] == "transfer_required"
    r = alice.delete("/api/admin/accounts/nora?transfer_to=bob", rev=None)
    assert r.status_code == 200 and r.json()["projects_moved"] == 1
    acc = bob.get(f"/api/projects/{pid}/access").json()
    assert acc["owner"] == "bob" and acc["members"] == []                                           # bob propriétaire, plus de doublon de membre
    assert bob.get(f"/api/projects/{pid2}/access").json()["members"] == []                          # l'accès de nora aux projets des autres est retiré
    assert any(e["action"] == "delete" and e["target"] == "nora" and e["detail"]["transferred_to"] == "bob" for e in alice.get("/api/admin/audit").json()["entries"])


# ---- 3. l'administrateur voit et agit sur tous les projets --------------------------------------------------------------------------

def test_admin_sees_and_acts_on_every_project_with_trace(app, alice, bob):
    c = settle(app, alice, "otto")
    pid = c.post("/api/projects", json={"name": "Projet d'Otto", "sample": "automaint"}, rev=None).json()["id"]
    rows = {p["id"]: p for p in alice.get("/api/projects").json()}
    assert pid in rows and rows[pid]["owner"] == "otto" and rows[pid]["via_admin"] is True and rows[pid]["role"] == "owner"
    assert pid not in {p["id"] for p in bob.get("/api/projects").json()}                            # non-administrateur : inchangé
    assert bob.get(f"/api/projects/{pid}").status_code == 404
    # lire, modifier, partager, transférer
    cur = alice.get(f"/api/projects/{pid}").json()
    cur["notes"] = "revu par l'administratrice"
    assert alice.put(f"/api/projects/{pid}", json=cur, rev="*").status_code == 200
    assert alice.post(f"/api/projects/{pid}/access/members", json={"login": "bob", "role": "reader"}, rev=None).status_code == 200
    assert alice.delete(f"/api/projects/{pid}/access/members/bob", rev=None).status_code == 200
    log = c.get(f"/api/projects/{pid}/activity").json()
    mine = [e for e in log if e["user"] == "alice"]
    assert {e["action"] for e in mine} >= {"project", "share", "unshare"}
    assert all(e["detail"].get("as_admin") is True for e in mine), mine                              # « en tant qu'administrateur »
    assert not any(e.get("detail", {}).get("as_admin") for e in log if e["user"] == "otto")
    assert alice.post(f"/api/projects/{pid}/access/transfer", json={"login": "bob"}, rev=None).status_code == 200
    assert bob.get(f"/api/projects/{pid}/access").json()["owner"] == "bob"
    # suppression : trace dans le journal d'administration (l'activité du projet disparaît avec lui)
    assert alice.delete(f"/api/projects/{pid}", rev=None).status_code == 200
    entry = [e for e in alice.get("/api/admin/audit").json()["entries"] if e["action"] == "project_delete" and e["target"] == pid]
    assert entry and entry[0]["detail"]["as_admin"] is True and entry[0]["detail"]["owner"] == "bob"


def test_admin_own_project_actions_are_not_marked_as_admin(alice):
    pid = alice.post("/api/projects", json={"name": "Le mien"}, rev=None).json()["id"]
    cur = alice.get(f"/api/projects/{pid}").json(); cur["notes"] = "x"
    alice.put(f"/api/projects/{pid}", json=cur, rev="*")
    assert not any(e.get("detail", {}).get("as_admin") for e in alice.get(f"/api/projects/{pid}/activity").json())
    assert next(p for p in alice.get("/api/projects").json() if p["id"] == pid)["via_admin"] is False


# ---- 4. le lecteur ne génère plus ------------------------------------------------------------------------------------------------

def test_reader_cannot_generate_but_editor_can(app, alice, bob):
    pid = alice.post("/api/projects", json={"name": "Gen", "sample": "automaint"}, rev=None).json()["id"]
    alice.post(f"/api/projects/{pid}/access/members", json={"login": "bob", "role": "reader"}, rev=None)
    for t in ("curiosity", "neo4j"):
        for suffix in ("", "/zip"):
            r = bob.get(f"/api/projects/{pid}/generate/{t}{suffix}", rev=None)
            assert r.status_code == 403 and r.json()["code"] == "read_only"
    assert bob.get(f"/api/projects/{pid}/generations").json() == []
    assert bob.get(f"/api/projects/{pid}/export/ontology").status_code == 200                         # consultation et export de l'existant : gardés
    alice.post(f"/api/projects/{pid}/access/members", json={"login": "bob", "role": "editor"}, rev=None)
    assert bob.get(f"/api/projects/{pid}/generate/curiosity", rev=None).status_code == 428           # projet partagé : If-Match obligatoire
    assert bob.get(f"/api/projects/{pid}/generate/curiosity", rev="*").status_code == 200
    assert [e["action"] for e in alice.get(f"/api/projects/{pid}/activity").json()][0] == "generate"   # journal d'activité
    alice.post(f"/api/projects/{pid}/access/members", json={"login": "bob", "role": "reader"}, rev=None)
    assert len(bob.get(f"/api/projects/{pid}/generations").json()) == 1                               # le lecteur voit l'historique existant


def test_generate_by_get_requires_csrf(app, alice):
    pid = alice.post("/api/projects", json={"name": "Csrf", "sample": "automaint"}, rev=None).json()["id"]
    r = alice.c.get(f"/api/projects/{pid}/generate/curiosity")                                        # sans jeton : refusé comme une écriture
    assert r.status_code == 403 and r.json()["code"] == "csrf"
    assert alice.c.get(f"/api/projects/{pid}/export/ontology").status_code == 200                      # les vraies lectures n'exigent rien


# ---- 5. langue par compte ------------------------------------------------------------------------------------------------------

def test_language_is_per_account(app, alice, bob):
    assert alice.get("/api/auth/session").json()["lang"] == "fr"
    r = bob.put("/api/auth/preferences", json={"lang": "en"}, rev=None)
    assert r.status_code == 200 and r.json()["lang"] == "en"
    assert bob.get("/api/auth/session").json()["lang"] == "en" and alice.get("/api/auth/session").json()["lang"] == "fr"
    assert "not found" in bob.get("/api/projects/inconnu").json()["detail"]                              # messages d'erreur dans sa langue
    assert "introuvable" in alice.get("/api/projects/inconnu").json()["detail"]
    assert bob.put("/api/auth/preferences", json={"lang": "de"}, rev=None).json()["code"] == "bad_lang"
    # Krakie répond dans la langue du compte
    from ontoforge.assistant.agent import reply_lang
    from ontoforge import localize
    tok = localize.REQUEST_LANG.set("en")
    try:
        assert reply_lang("bonjour") == "en"
    finally:
        localize.REQUEST_LANG.reset(tok)
    tok = localize.REQUEST_LANG.set("fr")
    try:
        assert localize.ui_lang() == "fr" and localize.assistant_lang() == "fr"
    finally:
        localize.REQUEST_LANG.reset(tok)
    bob.put("/api/auth/preferences", json={"lang": "fr"}, rev=None)


def test_account_language_survives_relogin_and_is_stored_server_side(app, alice):
    u = settle(app, alice, "pia")
    u.put("/api/auth/preferences", json={"lang": "en"}, rev=None)
    assert User(app, "pia", NEWPW).info["lang"] == "en"
    assert json.loads((app.data_dir / "accounts.json").read_text())["accounts"]["pia"]["lang"] == "en"
    assert next(a for a in alice.get("/api/admin/accounts").json()["accounts"] if a["login"] == "pia")["lang"] == "en"


def test_global_language_is_the_default_for_new_accounts(app, alice):
    r = alice.put("/api/settings", json={"language": {"ui": "en"}}, rev=None)
    assert r.status_code == 200, r.text
    try:
        out = make(alice, "quinn")
        assert out["account"]["lang"] == "en"
        assert alice.get("/api/auth/session").json()["lang"] == "en"                                    # alice n'a pas fait de choix : elle suit le défaut
    finally:
        alice.put("/api/settings", json={"language": {"ui": "fr"}}, rev=None)
    assert make(alice, "quinn2")["account"]["lang"] == "fr"


def test_config_account_can_set_language(app, alice, bob):
    bob.put("/api/auth/preferences", json={"lang": "en"}, rev=None)
    assert next(a for a in alice.get("/api/admin/accounts").json()["accounts"] if a["login"] == "bob")["lang"] == "en"
    bob.put("/api/auth/preferences", json={"lang": "fr"}, rev=None)


def test_admin_routes_need_authentication_enabled(tmp_path, monkeypatch):
    for k in ("ONTOFORGE_AUTH", "ONTOFORGE_AUTH_USERS", "ONTOFORGE_PUBLIC"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("ONTOFORGE_DATA", str(tmp_path))
    from ontoforge.main import create_app
    c = TestClient(create_app())
    r = c.get("/api/admin/accounts")
    assert r.status_code == 409 and r.json()["code"] == "auth_required_for_accounts"
    s = c.get("/api/auth/session").json()
    assert s["enabled"] is False and s["admin"] is True                                                # mode local : comportement actuel


def test_l42_04_validation_error_never_echoes_input():
    """L42-04 : un 422 ne renvoie pas la valeur saisie (ex. mot de passe trop long)."""
    from fastapi.testclient import TestClient
    from ontoforge.main import create_app
    secret = "x" * 300 + "-" + "MARQUEUR"
    c = TestClient(create_app())
    r = c.post("/api/auth/login", json={"username": "a", "password": secret})
    assert secret not in r.text and "MARQUEUR" not in r.text


def test_l42_02_failed_save_does_not_leave_cache_modified(tmp_path, monkeypatch):
    """L42-02 : si l'écriture du magasin échoue, le cache n'est pas laissé dans l'état non écrit."""
    import inspect
    from ontoforge.auth.accounts import AccountDirectory
    src = inspect.getsource(AccountDirectory._save)
    assert "finally" in src and "_cache = None" in src
