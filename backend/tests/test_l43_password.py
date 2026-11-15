"""L43 (D-L43-01) : changement de mot de passe pour tous les comptes (masque des comptes de la configuration), corrections L42-01, L42-03."""
import json
import os
import stat
import threading
import time

import pytest
from fastapi.testclient import TestClient

from ontoforge.auth import limiter, passwords
from ontoforge.auth.accounts import AccountDirectory, AccountError
from ontoforge.auth.config import AuthConfig

PW = "correct horse battery"                 # secrets de test assemblés à l'exécution
PW2 = "-".join(["sierra", "tango", str(os.getpid())])
PW3 = "-".join(["whiskey", "xray", str(os.getpid())])
HASH = passwords.hash_password(PW)
ENV = {"ONTOFORGE_AUTH": "password", "ONTOFORGE_SECRET_KEY": "k" * 48, "ONTOFORGE_AUTH_USERS": f"alice:{HASH};carol:{HASH};dave:{HASH}", "ONTOFORGE_AUTH_ADMINS": "alice"}


def _env(mp, tmp):
    mp.setenv("ONTOFORGE_DATA", str(tmp))
    mp.setenv("ONTOFORGE_LOCAL_STORE_DIR", str(tmp / "ls"))
    for k in ("ONTOFORGE_PUBLIC", "ONTOFORGE_AUTH_USERS_FILE", "ONTOFORGE_ACCOUNTS_FILE"):
        mp.delenv(k, raising=False)
    for k, v in ENV.items():
        mp.setenv(k, v)


@pytest.fixture()
def app(tmp_path, monkeypatch):
    _env(monkeypatch, tmp_path)
    limiter.reset()
    from ontoforge.main import create_app
    a = create_app()
    a.data_dir = tmp_path
    return a


class U:
    def __init__(self, app, name, pw=PW):
        self.c = TestClient(app, base_url="https://testserver")
        r = self.c.post("/api/auth/login", json={"username": name, "password": pw})
        assert r.status_code == 200, r.text
        self.name, self.csrf, self.info = name, r.json()["csrf"], r.json()

    def req(self, method, url, **kw):
        return self.c.request(method, url, headers={"X-CSRF-Token": self.csrf}, **kw)

    def get(self, url, **kw): return self.req("GET", url, **kw)
    def post(self, url, **kw): return self.req("POST", url, **kw)

    def change(self, cur, new):
        r = self.post("/api/auth/password", json={"current": cur, "new": new})
        if r.status_code == 200:
            self.csrf = r.json()["csrf"]
        return r


def login(app, name, pw):
    return TestClient(app, base_url="https://testserver").post("/api/auth/login", json={"username": name, "password": pw})


def store(app):
    return json.loads((app.data_dir / "accounts.json").read_text())


# ---- 1. compte de la configuration : changement depuis l'interface ----------------------------------------------------------------

def test_config_account_changes_its_password_and_masks_the_config_one(app):
    other, carol = U(app, "carol"), U(app, "carol")
    r = carol.change(PW, PW2)
    assert r.status_code == 200 and r.json()["must_change"] is False and r.json()["source"] == "config"
    assert login(app, "carol", PW).status_code == 401                      # le mot de passe de la configuration ne fonctionne plus
    assert login(app, "carol", PW2).status_code == 200
    assert other.get("/api/projects").status_code == 401                   # autres sessions coupées (jeton gen)
    assert carol.get("/api/projects").status_code == 200                   # session courante : renouvelée, valide
    assert U(app, "dave").get("/api/projects").status_code == 200 and login(app, "dave", PW).status_code == 200   # les autres comptes de la configuration : intacts
    f = app.data_dir / "accounts.json"
    raw = f.read_text()
    assert stat.S_IMODE(f.stat().st_mode) == 0o600 and PW2 not in raw and store(app)["config"]["carol"]["hash"].startswith("$argon2")
    assert not store(app)["config"].get("dave", {}).get("hash")


def test_config_account_rules_on_change(app):
    c = U(app, "carol")
    assert c.change("faux faux faux", PW2).json()["code"] == "bad_current_password"
    assert c.change(PW, "court").json()["code"] == "password_too_short"
    assert c.change(PW, PW).json()["code"] == "password_unchanged"
    assert login(app, "carol", PW).status_code == 200                      # rien n'a changé


def test_mask_survives_a_restart_and_wins_over_a_changed_config_hash(app, tmp_path):
    U(app, "carol").change(PW, PW2)
    from ontoforge.main import create_app
    again = create_app()                                                   # « redémarrage » : même magasin, annuaire neuf
    again.data_dir = tmp_path
    assert login(again, "carol", PW2).status_code == 200 and login(again, "carol", PW).status_code == 401
    # Jerem édite son .env : nouveau hachage pour carol ; le masque reste prioritaire, l'écart est signalé
    new_cfg = passwords.hash_password(PW3)
    d = AccountDirectory(AuthConfig(enabled=True, users={"alice": HASH, "carol": new_cfg, "dave": HASH}, admins=frozenset({"alice"})))
    a = d.get("carol")
    assert passwords.verify_password(a.hash, PW2) and not passwords.verify_password(a.hash, PW3)
    assert a.pw_override and a.cfg_changed and a.public()["cfg_changed"] is True
    assert not d.get("dave").pw_override and not d.get("dave").cfg_changed
    d2 = AccountDirectory(AuthConfig(enabled=True, users={"alice": HASH, "carol": HASH, "dave": HASH}, admins=frozenset({"alice"})))
    assert d2.get("carol").pw_override and not d2.get("carol").cfg_changed  # config inchangée : pas d'avertissement


def test_admin_resets_a_config_account_then_reverts_to_the_config_password(app):
    alice, carol = U(app, "alice"), U(app, "carol")
    r = alice.post("/api/admin/accounts/carol/reset-password")
    assert r.status_code == 200
    prov = r.json()["provisional_password"]
    assert r.json()["account"]["pw_override"] is True and r.json()["account"]["managed"] is True
    assert carol.get("/api/projects").status_code == 401                   # sessions coupées
    assert login(app, "carol", PW).status_code == 401
    c2 = U(app, "carol", prov)
    assert c2.info["must_change"] is True and c2.get("/api/projects").status_code == 403   # à changer d'abord
    assert prov not in (app.data_dir / "accounts.json").read_text() and prov not in (app.data_dir / "admin-audit.jsonl").read_text()
    assert c2.change(prov, PW2).status_code == 200 and c2.get("/api/projects").status_code == 200
    # retour au mot de passe de la configuration
    rows = {a["login"]: a for a in alice.get("/api/admin/accounts").json()["accounts"]}
    assert rows["carol"]["pw_override"] is True and rows["dave"]["pw_override"] is False
    assert alice.post("/api/admin/accounts/dave/revert-password").json()["code"] == "no_override"
    assert alice.post("/api/admin/accounts/ghost/revert-password").status_code == 404
    r = alice.post("/api/admin/accounts/carol/revert-password")
    assert r.status_code == 200 and r.json()["account"]["pw_override"] is False
    assert c2.get("/api/projects").status_code == 401                      # sessions coupées aussi
    assert login(app, "carol", PW2).status_code == 401 and login(app, "carol", PW).status_code == 200
    acts = [(e["action"], e["actor"]) for e in alice.get("/api/admin/audit").json()["entries"] if e["target"] == "carol"][::-1]
    assert acts == [("reset_password", "alice"), ("change_password", "carol"), ("revert_password", "alice")]


def test_other_attributes_of_config_accounts_stay_managed_by_the_config(app):
    alice = U(app, "alice")
    for url, kw in (("disable", {}), ("enable", {}), ("admin", {"json": {"admin": True}})):
        assert alice.post(f"/api/admin/accounts/carol/{url}", **kw).json()["code"] == "managed_by_config"
    assert alice.req("DELETE", "/api/admin/accounts/carol").json()["code"] == "managed_by_config"
    U(app, "carol").change(PW, PW2)
    row = {a["login"]: a for a in alice.get("/api/admin/accounts").json()["accounts"]}["carol"]
    assert row["admin"] is False and row["active"] is True and row["managed"] is True


def test_interface_account_can_still_not_revert(app):
    alice = U(app, "alice")
    alice.post("/api/admin/accounts", json={"login": "erin"})
    assert alice.post("/api/admin/accounts/erin/revert-password").json()["code"] == "not_config_account"


def test_non_admin_cannot_touch_another_account(app):
    carol = U(app, "carol")
    for path in ("dave/reset-password", "dave/revert-password", "dave/disable"):
        assert carol.post(f"/api/admin/accounts/{path}").status_code == 403
    assert login(app, "dave", PW).status_code == 200                       # dave n'a pas bougé
    # la route de changement n'agit que sur la session courante : un identifiant dans le corps est ignoré
    r = carol.post("/api/auth/password", json={"current": PW, "new": PW2, "login": "dave", "user": "dave"})
    assert r.status_code == 200 and login(app, "dave", PW).status_code == 200 and login(app, "carol", PW2).status_code == 200


def test_session_without_csrf_cannot_change_a_config_password(app):
    carol = U(app, "carol")
    assert carol.c.post("/api/auth/password", json={"current": PW, "new": PW2}).status_code == 403
    assert login(app, "carol", PW).status_code == 200


# ---- 2. L42-01 : hachage hors verrou, relecture sous verrou, limiteur ---------------------------------------------------------------

def _dir(tmp_path, monkeypatch):
    monkeypatch.setenv("ONTOFORGE_DATA", str(tmp_path))
    return AccountDirectory(AuthConfig(enabled=True, users={"cfg": HASH}, admins=frozenset({"cfg"})))


def test_l42_01_directory_is_not_blocked_while_hashing(tmp_path, monkeypatch):
    d = _dir(tmp_path, monkeypatch)
    d.create("t", "uma", PW, admin=False)
    orig = passwords.hash_password
    started, release = threading.Event(), threading.Event()

    def slow(pw, scheme="argon2"):
        started.set()
        release.wait(5)                      # hachage « long » : tant que ce n'est pas relâché, le garde ne doit pas être gêné
        return orig(pw, scheme)

    monkeypatch.setattr(passwords, "hash_password", slow)
    out: list = []
    t = threading.Thread(target=lambda: out.append(d.change_password("uma", PW, PW2)))
    t.start()
    assert started.wait(5)
    t0 = time.perf_counter()
    for _ in range(50):
        assert d.get("uma") is not None and d.get("cfg") is not None and d.session_ok("uma", d.get("uma").gen)
    elapsed = time.perf_counter() - t0
    release.set()
    t.join(10)
    assert elapsed < 0.5, f"annuaire bloqué pendant le hachage : {elapsed:.2f} s"
    assert out and passwords.verify_password(d.get("uma").hash, PW2)


def test_l42_01_change_refused_if_the_account_changed_meanwhile(tmp_path, monkeypatch):
    d = _dir(tmp_path, monkeypatch)
    d.create("t", "vic", PW)
    orig = passwords.hash_password
    done = []

    def reset_in_between(pw, scheme="argon2"):
        if not done:
            done.append(1)
            d.reset_password("t", "vic", PW3)          # réinitialisation par un administrateur pendant le hachage
        return orig(pw, scheme)

    monkeypatch.setattr(passwords, "hash_password", reset_in_between)
    with pytest.raises(AccountError) as e:
        d.change_password("vic", PW, PW2)
    assert e.value.status_code == 409 and e.value.payload["code"] == "password_changed_meanwhile"
    assert passwords.verify_password(d.get("vic").hash, PW3) and d.get("vic").must_change     # la réinitialisation n'est pas écrasée


def test_l42_01_config_change_refused_if_config_account_changed_meanwhile(tmp_path, monkeypatch):
    d = _dir(tmp_path, monkeypatch)
    orig = passwords.hash_password
    done = []

    def other_change(pw, scheme="argon2"):
        if not done:
            done.append(1)
            d.reset_password("t", "cfg", PW3)
        return orig(pw, scheme)

    monkeypatch.setattr(passwords, "hash_password", other_change)
    with pytest.raises(AccountError) as e:
        d.change_password("cfg", PW, PW2)
    assert e.value.payload["code"] == "password_changed_meanwhile"


def test_l42_01_successful_changes_are_rate_limited_per_account(app):
    c = U(app, "carol")
    pws = [PW, PW2, PW3, PW2 + "a", PW3 + "b", PW2 + "c"]
    codes = []
    for old, new in zip(pws, pws[1:] + [PW2 + "d"]):
        codes.append(c.change(old, new).status_code)
    assert codes[:5] == [200] * 5 and codes[5] == 429                      # 6e changement de la minute : refusé
    assert U(app, "dave").change(PW, PW2).status_code == 200               # un autre compte n'est pas gêné


# ---- 3. L42-03 : rotation du journal, échec d'écriture -----------------------------------------------------------------------------

def test_l42_03_audit_rotates_into_archives_without_losing_lines(tmp_path, monkeypatch):
    import ontoforge.auth.accounts as acc
    monkeypatch.setattr(acc, "AUDIT_MAX", 5)
    monkeypatch.setenv("ONTOFORGE_AUDIT_ARCHIVES", "3")
    d = _dir(tmp_path, monkeypatch)
    for i in range(17):
        d.audit("a", "x", f"t{i}")
    names = sorted(p.name for p in tmp_path.iterdir() if p.name.startswith("admin-audit"))
    assert names == ["admin-audit.1.jsonl", "admin-audit.2.jsonl", "admin-audit.3.jsonl", "admin-audit.jsonl"]
    assert all(stat.S_IMODE((tmp_path / n).stat().st_mode) == 0o600 for n in names)
    assert [r["target"] for r in d.audit_rows(100)] == [f"t{i}" for i in range(16, -1, -1)]     # 17 lignes, 5 par fichier : rien de perdu
    assert len((tmp_path / "admin-audit.jsonl").read_text().splitlines()) == 2
    for i in range(17, 22):
        d.audit("a", "x", f"t{i}")
    assert [r["target"] for r in d.audit_rows(100)] == [f"t{i}" for i in range(21, 4, -1)]      # t0 à t4 ont dépassé les 3 archives (seule perte, réglable)
    assert not (tmp_path / "admin-audit.4.jsonl").exists()
    monkeypatch.setenv("ONTOFORGE_AUDIT_ARCHIVES", "5")
    for i in range(22, 32):
        d.audit("a", "x", f"t{i}")
    rows = d.audit_rows(100)
    assert rows[0]["target"] == "t31" and rows[-1]["target"] == "t5" and len(rows) == 27         # avec plus de rangs plus rien ne se perd


def test_l42_03_1000_banal_actions_do_not_erase_the_first_entry(tmp_path, monkeypatch):
    d = _dir(tmp_path, monkeypatch)
    d.audit("a", "first", "premier")
    for i in range(1040):
        d.audit("a", "disable" if i % 2 else "enable", "x")
    assert d.audit_rows(2000)[-1]["target"] == "premier"
    assert (tmp_path / "admin-audit.1.jsonl").is_file()


def test_l42_03_failed_audit_write_fails_the_action_and_restores_the_store(tmp_path, monkeypatch):
    d = _dir(tmp_path, monkeypatch)
    d.create("t", "wes", PW, admin=True)
    d.create("t", "xia", PW)
    before = (tmp_path / "accounts.json").read_text()

    def boom(self, line):
        raise OSError("disque plein")

    monkeypatch.setattr(AccountDirectory, "_audit_append", boom)
    for op in (lambda: d.set_active("t", "xia", False), lambda: d.set_admin("t", "xia", True), lambda: d.reset_password("t", "xia"),
               lambda: d.create("t", "yan", PW), lambda: d.reset_password("t", "cfg"), lambda: d.change_password("xia", PW, PW2),
               lambda: d.delete("t", "xia")):
        with pytest.raises(AccountError) as e:
            op()
        assert e.value.status_code == 500 and e.value.payload["code"] == "audit_write_failed"
    assert (tmp_path / "accounts.json").read_text() == before                          # magasin rétabli
    assert d.get("xia").active and not d.get("xia").admin and passwords.verify_password(d.get("xia").hash, PW)
    assert d.get("yan") is None and not d.get("cfg").pw_override


def test_l42_03_admin_api_answers_500_cleanly(app, monkeypatch):
    alice = U(app, "alice")
    alice.post("/api/admin/accounts", json={"login": "zoe"})
    with monkeypatch.context() as m:
        m.setattr(AccountDirectory, "_audit_append", lambda self, line: (_ for _ in ()).throw(OSError("x")))
        r = alice.post("/api/admin/accounts/zoe/disable")
        assert r.status_code == 500 and r.json()["code"] == "audit_write_failed" and "Traceback" not in r.text
        r = alice.post("/api/admin/accounts/carol/reset-password")
        assert r.status_code == 500 and login(app, "carol", PW).status_code == 200      # le mot de passe de la configuration n'a pas été masqué
    rows = {a["login"]: a for a in alice.get("/api/admin/accounts").json()["accounts"]}
    assert rows["zoe"]["active"] is True and rows["carol"]["pw_override"] is False
