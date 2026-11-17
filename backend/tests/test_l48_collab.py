"""L48 : droits de l'import déterministe (L40 / L42) : création et import réservés aux comptes qui peuvent écrire."""
import pathlib

import pytest

from test_collab import User, add, app, users  # noqa: F401  (fixtures du module de référence)
from ontoforge.auth import limiter

F = pathlib.Path(__file__).parent / "fixtures" / "l48"
SQL = [("files", ("a.sql", (F / "mysql.sql").read_bytes()))]


@pytest.fixture(autouse=True)
def _fresh():
    limiter.reset()


@pytest.fixture
def pid(users):
    r = users[0].post("/api/projects", json={"name": "Import"}, rev=None)
    assert r.status_code == 201
    return r.json()["id"]


def test_reader_cannot_preview_or_apply(users, pid):
    a, b, c = users
    add(a, pid, "bob", "reader")
    for path in ("preview", "apply"):
        r = b.post(f"/api/projects/{pid}/import/schema/{path}", files=SQL)
        assert r.status_code == 403
    assert len(a.get(f"/api/projects/{pid}").json()["onto"]["classes"]) == 0


def test_editor_can_import_and_it_is_logged(users, pid):
    a, b, c = users
    add(a, pid, "bob", "editor")
    pv = b.post(f"/api/projects/{pid}/import/schema/preview", files=SQL)
    assert pv.status_code == 200
    r = b.post(f"/api/projects/{pid}/import/schema/apply", files=SQL, data={"expect_digest": pv.json()["digest"]})
    assert r.status_code == 200, r.text
    assert r.json()["merged"]["added"]["classes"] == 4
    acts = a.get(f"/api/projects/{pid}/activity").json()
    assert any(x.get("action") == "import" and x.get("actor", x.get("user")) == "bob" for x in acts), acts


def test_stranger_gets_404_and_no_session_gets_401(users, pid, app):
    from fastapi.testclient import TestClient
    a, b, c = users
    for path in ("preview", "apply"):
        assert c.post(f"/api/projects/{pid}/import/schema/{path}", files=SQL).status_code == 404
    anon = TestClient(app, base_url="https://testserver")
    assert anon.post("/api/import/schema/preview", files=SQL).status_code == 401
    assert anon.post(f"/api/projects/{pid}/import/schema/apply", files=SQL).status_code == 401


def test_csrf_required_and_free_preview_for_any_account(users, pid):
    a, b, c = users
    r = a.c.post(f"/api/projects/{pid}/import/schema/apply", files=SQL, headers={"If-Match": "*"})   # sans jeton CSRF
    assert r.status_code in (401, 403)
    r = c.post("/api/import/schema/preview", files=SQL, rev=None)
    assert r.status_code == 200 and r.json()["summary"]["classes"] == 4


def test_shared_project_requires_if_match_for_apply(users, pid):
    a, b, c = users
    add(a, pid, "bob", "editor")
    r = b.post(f"/api/projects/{pid}/import/schema/apply", files=SQL, rev=None)
    assert r.status_code == 428
