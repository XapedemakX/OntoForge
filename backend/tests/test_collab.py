"""L40 : projets nominatifs et partage collaboratif. Cloisonnement de toutes les routes, rôles, partage, transfert, migration,
conflit 409, présence, activité, réglages réservés aux administrateurs, mode local inchangé."""
import json
import re

import pytest
from fastapi.testclient import TestClient
from starlette.routing import Mount

from ontoforge.auth import limiter, passwords
from ontoforge.collab import access
from ontoforge.collab.middleware import CollabMiddleware
from ontoforge.collab.routes import ADMIN_PREFIX, BODY_PROJECT_ROUTES, NO_PROJECT, ROUTES, SETTINGS_PREFIX

PW = "correct horse battery"
HASH = passwords.hash_password(PW)
ENV = {"ONTOFORGE_AUTH": "password", "ONTOFORGE_SECRET_KEY": "k" * 48, "ONTOFORGE_AUTH_USERS": f"alice:{HASH};bob:{HASH};carol:{HASH}"}


@pytest.fixture(scope="module")
def app(tmp_path_factory):
    """Une seule application pour le module (les connexions argon2 sont lentes) ; chaque test crée son propre projet."""
    mp = pytest.MonkeyPatch()
    tmp = tmp_path_factory.mktemp("collab")
    mp.setenv("ONTOFORGE_DATA", str(tmp))
    mp.setenv("ONTOFORGE_LOCAL_STORE_DIR", str(tmp / "ls"))
    for k in ("ONTOFORGE_PUBLIC", "ONTOFORGE_AUTH_USERS_FILE", "ONTOFORGE_AUTH_ADMINS"):
        mp.delenv(k, raising=False)
    for k, v in ENV.items():
        mp.setenv(k, v)
    limiter.reset()
    from ontoforge.main import create_app
    yield create_app()
    mp.undo()


@pytest.fixture(autouse=True)
def _fresh_limits():
    limiter.reset()


class User:
    """Un navigateur connecté : cookie de session + jeton CSRF, ``If-Match`` géré à la demande."""

    def __init__(self, app, name):
        self.c = TestClient(app, base_url="https://testserver")
        r = self.c.post("/api/auth/login", json={"username": name, "password": PW})
        assert r.status_code == 200, r.text
        self.name, self.csrf = name, r.json()["csrf"]

    def req(self, method, url, rev="*", **kw):
        h = {"X-CSRF-Token": self.csrf, **kw.pop("headers", {})}
        if rev is not None and (method not in ("GET", "HEAD") or "/generate/" in url):   # L42 : la génération est une écriture
            h["If-Match"] = str(rev)
        return self.c.request(method, url, headers=h, **kw)

    def get(self, url, **kw):
        return self.req("GET", url, **kw)

    def post(self, url, **kw):
        return self.req("POST", url, **kw)

    def put(self, url, **kw):
        return self.req("PUT", url, **kw)

    def delete(self, url, **kw):
        return self.req("DELETE", url, **kw)

    def ids(self):
        return {p["id"] for p in self.get("/api/projects").json()}


@pytest.fixture(scope="module")
def users(app):
    return User(app, "alice"), User(app, "bob"), User(app, "carol")


@pytest.fixture
def pid(users):
    a = users[0]
    r = a.post("/api/projects", json={"name": "Garage"}, rev=None)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def add(a, pid, who, role):
    r = a.post(f"/api/projects/{pid}/access/members", json={"login": who, "role": role}, rev=None)
    assert r.status_code == 200, r.text
    return r.json()


# ---- 1. cloisonnement : inventaire exhaustif -------------------------------------------------------------------------------------

def _api_routes(app):
    out = set()
    for r in app.router.routes:
        if isinstance(r, Mount) or not hasattr(r, "methods") or not r.path.startswith("/api"):
            continue
        for m in r.methods - {"HEAD"}:
            out.add((m, r.path))
    return out


def test_every_route_is_classified(app):
    """Une route future qui porte un projet sans être classée fait échouer ce test."""
    seen = _api_routes(app)
    unclassified = []
    for m, path in sorted(seen):
        if "{pid}" in path and path.startswith("/api/projects/"):
            ok = (m, path) in ROUTES
        elif path == SETTINGS_PREFIX or path.startswith(SETTINGS_PREFIX + "/"):
            ok = True    # écritures réservées aux administrateurs par le garde
        elif path == ADMIN_PREFIX or path.startswith(ADMIN_PREFIX + "/"):
            ok = True    # L42 : administration des comptes, réservée aux administrateurs par le garde (test_l42_admin.py)
        else:
            ok = (m, path) in NO_PROJECT or (m, path) in BODY_PROJECT_ROUTES
        if not ok:
            unclassified.append((m, path))
    assert not unclassified, f"routes non classées dans collab/routes.py : {unclassified}"
    stale = set(ROUTES) - seen
    assert not stale, f"entrées de la table sans route : {sorted(stale)}"
    assert not (set(BODY_PROJECT_ROUTES) | NO_PROJECT) - seen


def test_every_route_with_project_in_body_checks_access(app):
    """Les routes de l'assistant qui lisent ``project_id`` dans le corps appellent load_project (donc le contrôle d'accès)."""
    import inspect
    from ontoforge.api import assistant
    src = inspect.getsource(assistant)
    for (m, path) in BODY_PROJECT_ROUTES:
        assert path.startswith("/api/assistant/")
    assert src.count("load_project(body.project_id") >= 5


FILL = {"pid": "P", "target": "curiosity", "perimeter_id": "x", "qid": "q1", "login": "bob", "path": "a.ttl", "version": "1.0.0"}


def _fill(template, pid):
    return re.sub(r"\{(\w+)(?::path)?\}", lambda m: pid if m.group(1) == "pid" else FILL[m.group(1)], template)


class _Probe:
    """Application interne factice : répond 200 « atteint » si le garde laisse passer."""
    async def __call__(self, scope, receive, send):
        await send({"type": "http.response.start", "status": 200, "headers": [(b"content-type", b"application/json")]})
        await send({"type": "http.response.body", "body": b'{"reached": true}'})


class _AsUser:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        for k, v in scope["headers"]:
            if k == b"x-user":
                scope.setdefault("state", {})["auth_user"] = v.decode()
        await self.app(scope, receive, send)


@pytest.fixture
def stack(app, pid, users):
    """Garde réel + vrai routeur, handler factice : on ne teste que la décision du garde pour chaque route."""
    add(users[0], pid, "bob", "reader")
    add(users[0], pid, "carol", "editor")
    return TestClient(_AsUser(CollabMiddleware(_Probe(), app.state.auth, app.router)), base_url="https://testserver"), pid


@pytest.mark.parametrize("key", sorted(ROUTES), ids=lambda k: f"{k[0]} {k[1]}")
def test_all_routes_by_role(stack, key):
    c, pid = stack
    method, template = key
    level = ROUTES[key][0]
    url = _fill(template, pid)

    def hit(user, p=pid):
        return c.request(method, url.replace(pid, p), headers={"x-user": user, "If-Match": "*"})
    assert hit("dave").status_code == 404                       # compte sans accès : le projet « n'existe pas »
    assert hit("alice", "inconnu-1").status_code == 404          # projet inexistant : même réponse
    r = hit("bob")                                               # lecteur
    assert (r.status_code == 403) == (level in ("write", "owner")), (key, r.status_code)
    r = hit("carol")                                             # éditeur
    assert (r.status_code == 403) == (level == "owner"), (key, r.status_code)
    assert hit("alice").status_code == 200                       # propriétaire
    assert c.request(method, url, headers={"If-Match": "*"}).status_code == 401  # identité absente


def test_settings_writes_are_admin_only(app, users):
    a, b, _ = users
    methods = [(m, p) for (m, p) in _api_routes(app) if p.startswith(SETTINGS_PREFIX)]
    assert len(methods) > 10
    for m, p in methods:
        url = re.sub(r"\{\w+\}", "x", p)
        r = b.req(m, url, json={}) if m != "GET" else b.get(url)
        if m == "GET":
            assert r.status_code == 200, (m, p)
        else:
            assert r.status_code == 403 and r.json()["code"] == "admin_only", (m, p, r.status_code)
    assert a.put("/api/settings", json={"language": {"ui": "fr"}}).status_code == 200


def test_admin_can_use_provider_routes_whose_param_is_named_pid(users):
    """Régression : /api/settings/providers/{pid} désigne un fournisseur, pas un projet."""
    a = users[0]
    r = a.post("/api/settings/providers", json={"name": "Local", "kind": "ollama", "base_url": "http://ollama:11434"})
    assert r.status_code == 201, r.text
    pid = r.json()["id"]
    assert a.put(f"/api/settings/providers/{pid}", json={"model": "x"}).status_code == 200
    assert a.delete(f"/api/settings/providers/{pid}").status_code == 200


def test_settings_view_hides_secrets_for_non_admin(app, users):
    a, b, _ = users
    key = "sk-" + "x" * 8 + "-ABCDEFGH1234"
    a.post("/api/settings/providers", json={"name": "Prod", "kind": "anthropic", "api_key": key, "base_url": "https://api.example.org"})
    a.post("/api/settings/endpoints", json={"name": "Kg", "url": "https://sparql.example.org/q"})
    va, vb = a.get("/api/settings").json(), b.get("/api/settings").json()
    assert any(p.get("base_url") == "https://api.example.org" and p["has_key"] for p in va["llm_providers"])
    txt = json.dumps(vb)
    assert "api.example.org" not in txt and "sparql.example.org" not in txt and "key_last4" not in txt and key[-4:] not in txt
    assert any(p["name"] == "Prod" for p in vb["llm_providers"]) and vb["read_only"] is True
    assert "sparql.example.org" not in json.dumps(b.get("/api/settings/endpoints").json())


def test_session_tells_admin(users):
    assert users[0].get("/api/auth/session").json()["admin"] is True
    assert users[1].get("/api/auth/session").json()["admin"] is False


def test_admins_from_env(monkeypatch, tmp_path):
    monkeypatch.setenv("ONTOFORGE_AUTH_ADMINS", "bob")
    for k, v in ENV.items():
        monkeypatch.setenv(k, v)
    from ontoforge.auth.config import load_config, AuthConfigError
    cfg = load_config()
    assert cfg.admins == frozenset({"bob"}) and cfg.first_admin == "bob"
    monkeypatch.setenv("ONTOFORGE_AUTH_ADMINS", "zoe")
    with pytest.raises(AuthConfigError):
        load_config()


# ---- 2. visibilité, rôles, partage ------------------------------------------------------------------------------------------------

def test_owner_only_sees_own_projects(users, pid):
    a, b, c = users
    assert pid in a.ids() and pid not in b.ids() and pid not in c.ids()
    assert b.get(f"/api/projects/{pid}").status_code == 404
    assert b.get(f"/api/projects/{pid}").json()["detail"] == b.get("/api/projects/inconnu").json()["detail"].replace("inconnu", pid)
    row = next(p for p in a.get("/api/projects").json() if p["id"] == pid)
    assert row["owner"] == "alice" and row["role"] == "owner" and row["shared"] is False


def test_share_reader_then_editor(users, pid):
    a, b, _ = users
    v = add(a, pid, "bob", "reader")
    assert v["members"] == [{"login": "bob", "role": "reader"}]
    assert pid in b.ids()
    row = next(p for p in b.get("/api/projects").json() if p["id"] == pid)
    assert row["owner"] == "alice" and row["role"] == "reader" and row["shared"] is True
    assert b.get(f"/api/projects/{pid}").status_code == 200
    assert b.get(f"/api/projects/{pid}/export/ontology").status_code == 200
    p = b.get(f"/api/projects/{pid}").json()
    r = b.put(f"/api/projects/{pid}", json={**p, "name": "X"})
    assert r.status_code == 403 and r.json()["code"] == "read_only"
    assert b.put(f"/api/projects/{pid}/onto", json=p["onto"]).status_code == 403
    assert b.delete(f"/api/projects/{pid}").status_code == 403
    add(a, pid, "bob", "editor")   # changement de rôle
    rev = b.get(f"/api/projects/{pid}").headers["etag"]
    r = b.put(f"/api/projects/{pid}", json={**p, "name": "Garage 2"}, rev=rev)
    assert r.status_code == 200 and r.json()["name"] == "Garage 2"
    assert a.get(f"/api/projects/{pid}").json()["name"] == "Garage 2"


def test_editor_cannot_share_delete_or_transfer(users, pid):
    a, b, c = users
    add(a, pid, "bob", "editor")
    for r in (b.post(f"/api/projects/{pid}/access/members", json={"login": "carol", "role": "reader"}, rev=None),
              b.post(f"/api/projects/{pid}/access/transfer", json={"login": "bob"}, rev=None),
              b.delete(f"/api/projects/{pid}"), b.delete(f"/api/projects/{pid}/access/members/alice", rev=None)):
        assert r.status_code == 403, r.text
    assert pid not in c.ids()


def test_remove_access_and_leave(users, pid):
    a, b, c = users
    add(a, pid, "bob", "reader")
    add(a, pid, "carol", "editor")
    assert a.delete(f"/api/projects/{pid}/access/members/bob", rev=None).status_code == 200
    assert pid not in b.ids() and b.get(f"/api/projects/{pid}").status_code == 404
    assert c.delete(f"/api/projects/{pid}/access/members/carol", rev=None).status_code == 200   # un membre se retire lui-même
    assert pid not in c.ids()
    assert a.delete(f"/api/projects/{pid}/access/members/carol", rev=None).status_code == 404


def test_transfer_ownership(users, pid):
    a, b, c = users
    add(a, pid, "bob", "reader")
    r = a.post(f"/api/projects/{pid}/access/transfer", json={"login": "bob"}, rev=None)
    assert r.status_code == 200 and r.json()["owner"] == "bob"
    assert b.get(f"/api/projects/{pid}/access").json()["role"] == "owner"
    assert {"login": "alice", "role": "editor"} in r.json()["members"] and all(m["login"] != "bob" for m in r.json()["members"])
    assert a.delete(f"/api/projects/{pid}").status_code == 403         # l'ancien propriétaire est éditeur
    assert b.post(f"/api/projects/{pid}/access/members", json={"login": "carol", "role": "reader"}, rev=None).status_code == 200
    assert b.delete(f"/api/projects/{pid}").status_code == 200


def test_unknown_account_is_neutral_and_rate_limited(users, pid):
    a, *_ = users
    msgs = set()
    for i in range(10):
        r = a.post(f"/api/projects/{pid}/access/members", json={"login": f"ghost{i}", "role": "reader"}, rev=None)
        assert r.status_code == 422 and r.json()["code"] == "share_refused", r.text
        msgs.add(r.json()["detail"])
    assert msgs == {access.share_refused().detail}   # L41 (L40-04) : une seule réponse
    r = a.post(f"/api/projects/{pid}/access/members", json={"login": "bob", "role": "reader"}, rev=None)   # 11e tentative dans la minute
    assert r.status_code == 429
    assert a.post(f"/api/projects/{pid}/access/transfer", json={"login": "ghost"}, rev=None).status_code == 429


def test_share_with_self_and_bad_role(users, pid):
    a, *_ = users
    r = a.post(f"/api/projects/{pid}/access/members", json={"login": "ALICE", "role": "reader"}, rev=None)
    assert r.status_code == 422 and r.json()["code"] == "share_refused"   # indiscernable d'un compte inconnu (L41, L40-04)
    ghost = a.post(f"/api/projects/{pid}/access/members", json={"login": "nobody", "role": "reader"}, rev=None)
    assert (r.status_code, r.json()) == (ghost.status_code, ghost.json())
    r = a.post(f"/api/projects/{pid}/access/members", json={"login": "bob", "role": "admin"}, rev=None)
    assert r.status_code == 422 and r.json()["code"] == "bad_role"


def test_body_project_routes_are_cloistered(users, pid):
    a, b, c = users
    add(a, pid, "bob", "reader")
    body = {"project_id": pid, "messages": [{"role": "user", "content": "bonjour"}], "context": {"screen": "ontologie"}}
    assert c.post("/api/assistant/chat", json=body, rev=None).status_code == 404
    assert c.post("/api/assistant/shapes", json={"project_id": pid}, rev=None).status_code == 404
    assert c.post("/api/assistant/shapes/apply", json={"project_id": pid, "patches": []}, rev=None).status_code == 404
    r = b.post("/api/assistant/shapes/apply", json={"project_id": pid, "patches": []}, rev=None)
    assert r.status_code == 403 and r.json()["code"] == "read_only"
    assert b.post("/api/assistant/chat", json=body, rev=None).status_code == 200


# ---- 3. concurrence optimiste -------------------------------------------------------------------------------------------------------

def test_etag_and_conflict_409(users, pid):
    a, b, _ = users
    add(a, pid, "bob", "editor")
    pa = a.get(f"/api/projects/{pid}")
    ea = pa.headers["etag"]
    pb = b.get(f"/api/projects/{pid}")
    r = a.put(f"/api/projects/{pid}", json={**pa.json(), "name": "A1"}, rev=ea)
    assert r.status_code == 200 and r.headers["etag"] != ea
    r = b.put(f"/api/projects/{pid}", json={**pb.json(), "name": "B1"}, rev=pb.headers["etag"])
    assert r.status_code == 409
    j = r.json()
    assert j["code"] == "conflict" and j["last_actor"] == "alice" and "alice" in j["detail"] and str(j["current_rev"]) == a.get(f"/api/projects/{pid}").headers["etag"].strip('"')
    assert a.get(f"/api/projects/{pid}").json()["name"] == "A1"          # jamais d'écrasement silencieux
    fresh = b.get(f"/api/projects/{pid}")
    assert b.put(f"/api/projects/{pid}", json={**fresh.json(), "name": "B2"}, rev=fresh.headers["etag"]).status_code == 200


def test_shared_project_requires_if_match(users, pid):
    a, b, _ = users
    p = a.get(f"/api/projects/{pid}").json()
    assert a.put(f"/api/projects/{pid}", json=p, rev=None).status_code == 200      # non partagé : If-Match facultatif
    add(a, pid, "bob", "editor")
    r = a.put(f"/api/projects/{pid}", json=p, rev=None)
    assert r.status_code == 428 and r.json()["code"] == "precondition_required"


def test_rev_bumps_only_when_project_changes(users, pid):
    a, *_ = users
    e0 = a.get(f"/api/projects/{pid}").headers["etag"]
    r = a.post(f"/api/projects/{pid}/ops", json={"ops": [{"op": "no-such-op"}]}, rev=e0)   # opération invalide : 200, projet inchangé
    assert r.headers["etag"] == e0
    r = a.put(f"/api/projects/{pid}/perimeters/active", json={"id": None}, rev=e0)
    assert r.status_code == 200
    r = a.post(f"/api/projects/{pid}/ops", json={"ops": [{"op": "add_class", "iri": "https://w3id.org/ontoforge/new#Moteur"}]}, rev=r.headers["etag"])
    assert r.status_code == 200 and r.json()["ok"] is True, r.text
    assert int(r.headers["etag"].strip('"')) > int(e0.strip('"'))


def test_activity_log(users, pid):
    a, b, _ = users
    add(a, pid, "bob", "editor")
    p = b.get(f"/api/projects/{pid}")
    b.put(f"/api/projects/{pid}", json={**p.json(), "name": "N"}, rev=p.headers["etag"])
    add(a, pid, "bob", "reader")
    log = b.get(f"/api/projects/{pid}/activity").json()
    acts = [(e["user"], e["action"]) for e in log]
    assert acts[0] == ("alice", "role") and ("bob", "project") in acts and ("alice", "share") in acts and ("alice", "create") in acts
    assert all(e["at"] for e in log)
    assert next(e for e in log if e["action"] == "share")["detail"] == {"login": "bob", "role": "editor"}


# ---- 4. présence ------------------------------------------------------------------------------------------------------------------------

def test_presence_heartbeat_and_expiry(users, pid, monkeypatch):
    a, b, _ = users
    add(a, pid, "bob", "reader")
    t = [1000.0]
    monkeypatch.setattr(access, "now", lambda: t[0])
    r = a.post(f"/api/projects/{pid}/presence", rev=None).json()
    assert [x["user"] for x in r["present"]] == ["alice"] and r["role"] == "owner" and r["present"][0]["me"] is True
    t[0] += 20
    r = b.post(f"/api/projects/{pid}/presence", rev=None).json()
    assert [x["user"] for x in r["present"]] == ["alice", "bob"] and r["role"] == "reader"
    assert {x["user"]: x["role"] for x in r["present"]} == {"alice": "owner", "bob": "reader"}
    t[0] += 45   # alice n'a plus battu depuis 65 s : expirée ; bob a battu 45 s plus tôt : encore là
    r = b.post(f"/api/projects/{pid}/presence", rev=None).json()
    assert [x["user"] for x in r["present"]] == ["bob"]


def test_presence_needs_access(users, pid):
    assert users[2].post(f"/api/projects/{pid}/presence", rev=None).status_code == 404


# ---- 5. migration -----------------------------------------------------------------------------------------------------------------

def test_migration_is_idempotent(tmp_path, monkeypatch):
    monkeypatch.setenv("ONTOFORGE_DATA", str(tmp_path))
    from ontoforge.projects import store
    old = store.create("Ancien")
    store.save(old)                       # projet créé avant L40 : aucun collab.json
    mine = store.create("Déjà à bob")
    store.save(mine)
    access.init_project(mine.id, "bob")
    assert access.migrate("alice") == 1
    assert access.read(old.id)["owner"] == "alice" and access.read(mine.id)["owner"] == "bob"
    assert access.migrate("alice") == 0   # deuxième démarrage : rien ne change
    assert [e["action"] for e in access.activity(old.id)] == ["migrate"]
    assert access.migrate(None) == 0


def test_startup_migration_and_visibility(tmp_path, monkeypatch):
    monkeypatch.setenv("ONTOFORGE_DATA", str(tmp_path))
    from ontoforge.projects import store
    old = store.create("Ancien")
    store.save(old)
    for k in ("ONTOFORGE_PUBLIC", "ONTOFORGE_AUTH_USERS_FILE", "ONTOFORGE_AUTH_ADMINS"):
        monkeypatch.delenv(k, raising=False)
    for k, v in ENV.items():
        monkeypatch.setenv(k, v)
    from ontoforge.main import create_app
    app = create_app()
    a, b = User(app, "alice"), User(app, "bob")
    assert old.id in a.ids() and old.id not in b.ids()
    assert a.get(f"/api/projects/{old.id}/access").json()["owner"] == "alice"


# ---- 6. mode local ----------------------------------------------------------------------------------------------------------------

@pytest.fixture
def local(tmp_path, monkeypatch):
    monkeypatch.setenv("ONTOFORGE_DATA", str(tmp_path))
    for k in ("ONTOFORGE_AUTH", "ONTOFORGE_PUBLIC"):
        monkeypatch.delenv(k, raising=False)
    from ontoforge.main import create_app
    return TestClient(create_app())


def test_local_mode_is_unchanged(local):
    pid = local.post("/api/projects", json={"name": "Local"}).json()["id"]
    row = local.get("/api/projects").json()[0]
    assert row["role"] == "owner" and row["owner"] is None and row["shared"] is False
    p = local.get(f"/api/projects/{pid}")
    assert p.status_code == 200 and "etag" in p.headers
    assert local.put(f"/api/projects/{pid}", json=p.json()).status_code == 200                       # sans If-Match : accepté
    assert local.put("/api/settings", json={"language": {"ui": "fr"}}).status_code == 200            # réglages libres
    v = local.get(f"/api/projects/{pid}/access").json()
    assert v["sharing_available"] is False and v["role"] == "owner"
    r = local.post(f"/api/projects/{pid}/access/members", json={"login": "bob", "role": "reader"})
    assert r.status_code == 409 and r.json()["code"] == "auth_required_for_sharing"
    assert local.get("/api/auth/session").json()["admin"] is True
    # même en local, une écriture périmée est refusée
    stale = p.headers["etag"]
    local.put(f"/api/projects/{pid}", json={**p.json(), "name": "N2"}, headers={"If-Match": stale})
    assert local.put(f"/api/projects/{pid}", json=p.json(), headers={"If-Match": stale}).status_code == 409
    assert local.delete(f"/api/projects/{pid}").status_code == 200


def test_krakie_help_points_to_the_sharing_section():
    from ontoforge.assistant.agent import help_section
    fr, en = help_section("sharing", "fr"), help_section("sharing", "en")
    assert fr["screen"] == "sharing" and fr["anchor"] == "partager-un-projet" and fr["page"] == "utilisateur"
    assert fr["title"] == "Partager un projet" and en["title"] == "Sharing a project"


# ---- 7. L41 : corrections de la relecture sécurité L39/L40 ---------------------------------------------------------------------------

import hashlib
import time

HOST_EP, PORT_EP = "fuseki-interne.corp.example", "3443"
HOST_LLM, PORT_LLM = "llm-interne.corp.example", "8443"


def _addr_free(text: str) -> bool:
    return not any(x in text for x in (HOST_EP, PORT_EP, HOST_LLM, PORT_LLM, "corp.example"))


@pytest.fixture
def admin_config(users):
    """L'administrateur enregistre un endpoint SPARQL et un fournisseur LLM à adresses internes ; nettoyé ensuite."""
    a = users[0]
    r = a.post("/api/settings/endpoints", json={"name": "Fuseki interne", "url": f"https://{HOST_EP}:{PORT_EP}/ds/sparql", "auth": "none"}, rev=None)
    assert r.status_code == 201, r.text
    eid = r.json()["id"]
    before = a.get("/api/settings/endpoints").json()["active_endpoint_id"]
    assert a.put("/api/settings/endpoints/active", json={"id": eid}, rev=None).status_code == 200
    r = a.post("/api/settings/providers", json={"name": "LLM interne", "kind": "openai_compat", "base_url": f"https://{HOST_LLM}:{PORT_LLM}/v1"}, rev=None)
    assert r.status_code == 201, r.text
    lid = r.json()["id"]
    yield eid, lid
    a.put("/api/settings/endpoints/active", json={"id": before}, rev=None)
    a.delete(f"/api/settings/endpoints/{eid}", rev=None)
    a.delete(f"/api/settings/providers/{lid}", rev=None)


def _ask(user, text, section="sparql"):
    r = user.post("/api/assistant/chat", rev=None, json={"messages": [{"role": "user", "content": text}],
                                                          "context": {"screen": "settings", "extra": {"section": section}}})
    assert r.status_code == 200, r.text
    return r.json()


@pytest.mark.parametrize("section,text", [("sparql", "quelle est l'adresse de mon endpoint SPARQL ?"), ("sparql", "teste mon endpoint"),
                                           ("llm", "quelle est l'URL de mon fournisseur ?"), ("llm", "diagnostic de mon fournisseur")])
def test_l40_01_settings_assistant_gives_no_address_to_non_admin(users, admin_config, section, text):
    a, b, _ = users
    j = _ask(b, text, section)
    assert _addr_free(json.dumps(j, ensure_ascii=False)), j
    assert any(x["kind"] == "settings_test" for x in j["actions"]) or section == "llm"   # la carte de test existe toujours, sans l'adresse
    ja = _ask(a, text, section)                      # contrôle : l'administrateur, lui, voit l'adresse (le test n'est pas vide de sens)
    if section == "sparql":
        assert HOST_EP in json.dumps(ja, ensure_ascii=False)


def test_l40_01_nothing_sent_to_the_llm_and_replies_masked_for_non_admin(users, admin_config, monkeypatch):
    from ontoforge.assistant import service
    a, b, _ = users
    sent = []

    class Echo:
        configured, name = True, "echo"

        def complete(self, system, messages, max_tokens):
            sent.append(json.dumps([system, messages], ensure_ascii=False))
            return json.dumps({"reply": f"Votre endpoint est https://{HOST_EP}:{PORT_EP}/ds/sparql et le LLM {HOST_LLM}.", "actions": []})
    monkeypatch.setattr(service, "_provider", lambda pid=None: Echo())
    jb = _ask(b, "quelle est l'adresse de mon endpoint ?")
    assert sent and _addr_free(sent[-1]) and _addr_free(json.dumps(jb, ensure_ascii=False)), (sent, jb)
    sent.clear()
    ja = _ask(a, "quelle est l'adresse de mon endpoint ?")
    assert HOST_EP in sent[-1] and HOST_EP in ja["reply"]   # l'administrateur garde l'adresse


def test_l40_01_query_errors_do_not_cite_the_host_of_a_registered_endpoint(users, admin_config, monkeypatch):
    from ontoforge.queries import endpoint as ep_mod
    a, b, _ = users
    eid, _l = admin_config
    r = a.post("/api/projects", json={"name": "Err", "sample": "automaint"}, rev=None)
    pid = r.json()["id"]
    add(a, pid, "bob", "reader")
    import socket
    monkeypatch.setattr(socket, "getaddrinfo", lambda host, port, *x, **k: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.1.2.3", port))])
    for body in ({"sparql": "ASK {}", "endpoint_id": eid}, {"sparql": "ASK {}"}):   # endpoint nommé, puis endpoint actif
        r = b.post(f"/api/projects/{pid}/query/run", json=body, rev=None)
        assert r.status_code == 403, r.text
        assert _addr_free(r.text) and "10.1.2.3" not in r.text and eid in r.text, r.text
    # le test de connexion d'un endpoint temporaire ne renvoie pas le début de la réponse de l'hôte
    import httpx
    from ontoforge import netguard
    monkeypatch.setattr(netguard, "request", lambda m, u, **k: httpx.Response(500, text="CORPS-PRIVE-DE-L-HOTE", request=httpx.Request(m, u)))
    r = b.post(f"/api/projects/{pid}/query/run", json={"sparql": "ASK {}", "endpoint": {"url": "https://exemple.org/sparql"}}, rev=None)
    assert r.status_code == 502 and "CORPS-PRIVE" not in r.text and "HTTP 500" in r.text, r.text


def test_l40_03_auth_enables_netguard_for_any_account(users):
    """Avec l'authentification, un lecteur ne fait plus émettre de requête vers une adresse interne."""
    a, b, _ = users
    pid = a.post("/api/projects", json={"name": "Ssrf"}, rev=None).json()["id"]
    add(a, pid, "bob", "reader")
    for url in ("http://127.0.0.1:9/x", "http://169.254.169.254/", "http://localhost/", "http://[::1]/", "http://10.0.0.5/"):
        r = b.post(f"/api/projects/{pid}/query/run", json={"sparql": "ASK {}", "endpoint": {"url": url}}, rev=None)
        assert r.status_code == 403 and "Adresse refusée" in r.json()["detail"], (url, r.text)
        r = b.post(f"/api/projects/{pid}/query/endpoint-test", json={"url": url}, rev=None)
        assert r.status_code == 200 and r.json()["ok"] is False and "Adresse refusée" in r.json()["message"], (url, r.text)


def _tree(pid):
    """Empreinte de TOUS les fichiers du dossier du projet (L42 : plus d'exception pour ``generations.json`` : un lecteur n'écrit rien du tout)."""
    from ontoforge.projects import store
    out = {}
    for f in sorted(store.project_dir(pid).rglob("*")):
        if f.is_file():
            st = f.stat()
            out[str(f.relative_to(store.project_dir(pid)))] = (st.st_size, st.st_mtime_ns, hashlib.sha256(f.read_bytes()).hexdigest())
    return out


def test_l40_02_no_read_route_modifies_the_project_folder(users):
    """Toutes les routes classées « lecture », appelées par un lecteur avec la vraie application (pas de handler factice) :
    empreinte (taille, date, condensat) de tous les fichiers du dossier du projet avant et après."""
    a, b, _ = users
    pid = a.post("/api/projects", json={"name": "Lecture", "sample": "automaint"}, rev=None).json()["id"]
    add(a, pid, "bob", "reader")
    reads = sorted(k for k, (lvl, _a) in ROUTES.items() if lvl == "read")
    assert len(reads) >= 30
    before = _tree(pid)
    served = 0
    for method, template in reads:
        if template.endswith("/access/members/{login}"):
            continue   # DELETE : « se retirer soi-même » est une écriture de partage assumée (classée lecture : un lecteur peut quitter le projet)
        url = _fill(template, pid)
        kw = {"json": {}} if method in ("POST", "PUT") else {}
        r = b.req(method, url, rev=None, **kw)
        served += r.status_code < 500
        assert r.status_code != 403, (method, template, r.text)   # le lecteur a bien le droit : la route a été réellement atteinte
        assert _tree(pid) == before, f"{method} {template} a modifié le dossier du projet"
    assert served == len(reads) - 1
    for t in ("curiosity", "neo4j"):   # L42 : le lecteur ne génère plus (ni historique, ni archive) ; l'éditeur, si
        for suffix in ("", "/zip"):
            r = b.get(f"/api/projects/{pid}/generate/{t}{suffix}", rev=None)
            assert r.status_code == 403 and r.json()["code"] == "read_only", r.text
    assert _tree(pid) == before, "un fichier du dossier du projet a changé"
    assert b.get(f"/api/projects/{pid}/generations", rev=None).json() == []
    assert a.get(f"/api/projects/{pid}/generate/curiosity", rev="*").status_code == 200
    assert len(b.get(f"/api/projects/{pid}/generations", rev=None).json()) == 1   # le lecteur consulte l'historique existant


def test_l40_02_editor_change_during_generation_is_not_lost(users, monkeypatch):
    from ontoforge.api import analysis
    a, b, c = users
    pid = a.post("/api/projects", json={"name": "Course", "sample": "automaint"}, rev=None).json()["id"]
    add(a, pid, "carol", "editor")
    real = analysis._generate
    done = {}

    def slow(p, target, perimeter, lang):
        out = real(p, target, perimeter, lang)
        cur = c.get(f"/api/projects/{pid}", rev=None).json()    # un éditeur enregistre PENDANT la génération
        cur["notes"] = "modif de l'éditeur"
        done["put"] = c.put(f"/api/projects/{pid}", json=cur, rev="*").status_code
        return out
    monkeypatch.setattr(analysis, "_generate", slow)
    assert a.get(f"/api/projects/{pid}/generate/curiosity", rev="*").status_code == 200
    assert done["put"] == 200
    assert a.get(f"/api/projects/{pid}", rev=None).json()["notes"] == "modif de l'éditeur"
    assert len(a.get(f"/api/projects/{pid}/generations", rev=None).json()) == 1


def test_l40_02_legacy_history_in_project_json_is_kept(users):
    """Un projet d'avant L41 garde son historique (dans project.json) ; la génération suivante le reprend dans le fichier annexe."""
    from ontoforge.core.project import GenerationRecord
    from ontoforge.projects import store
    a, *_ = users
    pid = a.post("/api/projects", json={"name": "Ancien", "sample": "automaint"}, rev=None).json()["id"]
    p = store.get(pid)
    p.generations.append(GenerationRecord(target="neo4j", at="2026-01-01T00:00:00+00:00", files=["x.cypher"]))
    store.save(p, touch=False)
    assert [g["files"] for g in a.get(f"/api/projects/{pid}/generations", rev=None).json()] == [["x.cypher"]]
    a.get(f"/api/projects/{pid}/generate/curiosity", rev=None)
    hist = a.get(f"/api/projects/{pid}/generations", rev=None).json()
    assert [g["target"] for g in hist] == ["curiosity", "neo4j"]


def test_l40_04_share_unknown_and_owner_give_the_same_answer_and_time(users):
    a, *_ = users
    pid = a.post("/api/projects", json={"name": "Neutre"}, rev=None).json()["id"]
    t = {"unknown": [], "owner": []}
    answers = set()
    for i in range(4):
        limiter.reset()
        for kind, login in (("unknown", f"ghost{i}"), ("owner", "alice")):
            t0 = time.perf_counter()
            r = a.post(f"/api/projects/{pid}/access/members", json={"login": login, "role": "reader"}, rev=None)
            t[kind].append(time.perf_counter() - t0)
            answers.add((r.status_code, json.dumps(r.json(), sort_keys=True)))
    assert len(answers) == 1, answers
    assert abs(sorted(t["unknown"])[1] - sorted(t["owner"])[1]) < 0.05   # même ordre de grandeur (médiane, à 50 ms près)
    r = a.post(f"/api/projects/{pid}/access/members", json={"login": "bob", "role": "reader"}, rev=None)
    assert r.status_code == 200 and r.json()["members"] == [{"login": "bob", "role": "reader"}]   # le succès reste distinct
    assert a.post(f"/api/projects/{pid}/access/transfer", json={"login": "alice"}, rev=None).json()["code"] == "share_refused"


@pytest.mark.parametrize("content", ["{ pas du json", "[]", '{"owner": 5}', '{"owner": "bob", "members": {"carol": "root"}}', ""])
def test_l40_05_corrupt_collab_file_locks_the_project_instead_of_reassigning(users, content, caplog):
    from ontoforge.projects import store
    a, b, _ = users
    pid = b.post("/api/projects", json={"name": "Verrou", "sample": "automaint"}, rev=None).json()["id"]   # propriétaire : bob
    (store.project_dir(pid) / "collab.json").write_text(content, encoding="utf-8")
    with caplog.at_level("ERROR", logger="ontoforge.collab"):
        r = a.get(f"/api/projects/{pid}", rev=None)                                     # alice est l'administrateur : lecture seule
        assert r.status_code == 200
        w = a.put(f"/api/projects/{pid}", json=r.json(), rev="*")
        assert w.status_code == 403 and w.json()["code"] == "collab_corrupt" and "collab.json" in w.json()["detail"]
        assert a.post(f"/api/projects/{pid}/access/members", json={"login": "carol", "role": "reader"}, rev=None).status_code == 403
        assert b.get(f"/api/projects/{pid}", rev=None).status_code == 404            # le propriétaire d'avant n'est plus reconnu : pas de réattribution
    assert any(pid in rec.getMessage() for rec in caplog.records)                      # journalisé côté serveur
    assert (store.project_dir(pid) / "collab.json").read_text(encoding="utf-8") == content   # jamais écrasé par la migration ni par une lecture
    from ontoforge.collab import access
    assert access.migrate("alice") >= 0 and (store.project_dir(pid) / "collab.json").read_text(encoding="utf-8") == content
    (store.project_dir(pid) / "collab.json").unlink()                                   # fichier ABSENT : retour au premier administrateur
    assert a.put(f"/api/projects/{pid}", json=r.json(), rev="*").status_code == 200


def test_l39_07_origin_check_with_port_behind_the_proxy(app):
    """Le navigateur sur le port 8088 envoie Origin « hôte:8088 » ; nginx transmet Host avec le port ($http_host)."""
    c = TestClient(app, base_url="https://ontoforge.test:8088")
    r = c.post("/api/auth/login", json={"username": "alice", "password": PW}, headers={"Origin": "https://ontoforge.test:8088", "Host": "ontoforge.test:8088"})
    assert r.status_code == 200, r.text
    csrf = r.json()["csrf"]
    h = {"X-CSRF-Token": csrf, "If-Match": "*"}
    ok = c.post("/api/projects", json={"name": "Port"}, headers={**h, "Origin": "https://ontoforge.test:8088", "Host": "ontoforge.test:8088"})
    assert ok.status_code == 201, ok.text
    old = c.post("/api/projects", json={"name": "Port"}, headers={**h, "Origin": "https://ontoforge.test:8088", "Host": "ontoforge.test"})   # l'ancien nginx
    assert old.status_code == 403 and old.json()["code"] == "bad_origin"
