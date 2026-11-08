"""L22 — éditeur de fichiers : validation (ligne/colonne), application, annulation, conflit de version."""
import pytest
from fastapi.testclient import TestClient

from ontoforge.main import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("ONTOFORGE_DATA", str(tmp_path))
    return TestClient(app)


@pytest.fixture
def pid(client):
    r = client.post("/api/projects", json={"name": "Fichiers", "sample": "automaint"})
    assert r.status_code == 201
    return r.json()["id"]


def U(pid):
    return f"/api/projects/{pid}/files"


def get(client, pid, path):
    r = client.get(f"{U(pid)}/{path}")
    assert r.status_code == 200, r.text
    return r.json()


def test_tree_and_read(client, pid):
    t = client.get(U(pid)).json()
    paths = {f["path"]: f for f in t["files"]}
    assert {"onto.ttl", "shapes.ttl", "decisions.json"} <= set(paths)
    assert paths["onto.ttl"]["editable"] and not paths["onto.ttl"]["generated"]
    gen = [f for f in t["files"] if f["generated"]]
    assert gen and all(not f["editable"] for f in gen)
    a, b = get(client, pid, "onto.ttl"), get(client, pid, "onto.ttl")
    assert a["content"] == b["content"] and a["etag"] == b["etag"]  # texte canonique stable


def test_validate_invalid_turtle_reports_line(client, pid):
    txt = '@prefix ex: <http://e.org/> .\nex:A a ex:B ;\n   ex:p "x"\nex:C a ex:D .\n'
    d = client.post(f"{U(pid)}/validate", json={"path": "onto.ttl", "content": txt}).json()["diagnostics"]
    assert len(d) == 1 and d[0]["severity"] == "error" and d[0]["line"] == 4 and d[0]["col"] == 1
    d = client.post(f"{U(pid)}/validate", json={"path": "onto.ttl", "content": "@prefix ex: <http://e.org/> .\nex:A a foo:B .\n"}).json()["diagnostics"]
    assert d[0]["line"] == 2 and "foo" in d[0]["message"]


def test_validate_valid_onto_gives_warnings_on_subject_line(client, pid):
    txt = get(client, pid, "onto.ttl")["content"]
    d = client.post(f"{U(pid)}/validate", json={"path": "onto.ttl", "content": txt}).json()["diagnostics"]
    assert d and all(x["severity"] != "error" for x in d)
    w07 = [x for x in d if x["code"] == "W07" and x.get("subject", "").endswith("hasMileageReading")]
    assert w07
    assert "hasMileageReading" in txt.splitlines()[w07[0]["line"] - 1]


def test_validate_json_and_shapes(client, pid):
    d = client.post(f"{U(pid)}/validate", json={"path": "decisions.json", "content": '{"a": '}).json()["diagnostics"]
    assert d[0]["severity"] == "error" and d[0]["code"] == "json-syntax"
    bad = ('@prefix sh: <http://www.w3.org/ns/shacl#> .\n@prefix ex: <http://e.org/> .\n'
           'ex:S a sh:NodeShape ; sh:targetClass ex:A ;\n  sh:property [ sh:path ex:p ; sh:minCount "x" ] .\n')
    d = client.post(f"{U(pid)}/validate", json={"path": "shapes.ttl", "content": bad}).json()["diagnostics"]
    assert any(x["code"] == "shacl-shacl" for x in d)
    d = client.post(f"{U(pid)}/validate", json={"path": "shapes.ttl", "content": "ex:S a"}).json()["diagnostics"]
    assert d[0]["code"] == "turtle-syntax"


def test_put_invalid_is_422_with_diagnostics(client, pid):
    before = get(client, pid, "onto.ttl")
    r = client.put(f"{U(pid)}/onto.ttl", json={"content": "ex:A a ex:B ;\n"})
    assert r.status_code == 422
    j = r.json()
    assert j["diagnostics"][0]["severity"] == "error" and isinstance(j["detail"], str)
    assert get(client, pid, "onto.ttl")["etag"] == before["etag"]


def test_put_valid_adds_class_then_undo(client, pid):
    cur = get(client, pid, "onto.ttl")
    ns = "https://w3id.org/ontoforge/automaint#"
    new = cur["content"] + f'\n<{ns}Pneu> a <http://www.w3.org/2002/07/owl#Class> .\n'
    df = client.post(f"{U(pid)}/diff", json={"path": "onto.ttl", "content": new}).json()
    assert df["changed"] and df["summary"]["added"] == 1 and df["summary"]["removed"] == 0
    r = client.put(f"{U(pid)}/onto.ttl", json={"content": new, "base_etag": cur["etag"]})
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["changed"] and j["can_undo"] and f"{ns}Pneu" in j["project"]["onto"]["classes"]
    assert f"{ns}Pneu" in client.get(f"/api/projects/{pid}").json()["onto"]["classes"]
    u = client.post(f"/api/projects/{pid}/ops/undo")
    assert u.status_code == 200
    assert f"{ns}Pneu" not in client.get(f"/api/projects/{pid}").json()["onto"]["classes"]
    assert get(client, pid, "onto.ttl")["etag"] == cur["etag"]


def test_put_same_content_is_noop(client, pid):
    cur = get(client, pid, "onto.ttl")
    r = client.put(f"{U(pid)}/onto.ttl", json={"content": cur["content"], "base_etag": cur["etag"]}).json()
    assert r["changed"] is False
    assert client.get(f"/api/projects/{pid}/ops/history").json()["undo"] == []


def test_conflict_when_project_changed_elsewhere(client, pid):
    cur = get(client, pid, "onto.ttl")
    ns = "https://w3id.org/ontoforge/automaint#"
    r = client.post(f"/api/projects/{pid}/ops", json={"ops": [{"op": "add_class", "iri": ns + "Autre"}]}).json()
    assert r["ok"]
    new = cur["content"] + f"\n<{ns}Pneu> a <http://www.w3.org/2002/07/owl#Class> .\n"
    c = client.put(f"{U(pid)}/onto.ttl", json={"content": new, "base_etag": cur["etag"]})
    assert c.status_code == 409 and c.json()["current_etag"] != cur["etag"]
    f = client.put(f"{U(pid)}/onto.ttl", json={"content": new, "base_etag": cur["etag"], "force": True})
    assert f.status_code == 200


def test_shapes_and_decisions_apply_and_generated_readonly(client, pid):
    s = get(client, pid, "shapes.ttl")
    r = client.put(f"{U(pid)}/shapes.ttl", json={"content": s["content"], "base_etag": s["etag"]})
    assert r.status_code == 200
    d = client.put(f"{U(pid)}/decisions.json", json={"content": '{"curiosity": {"x": "y"}, "neo4j": {}}'})
    assert d.status_code == 200 and d.json()["changed"]
    assert client.get(f"/api/projects/{pid}").json()["decisions"]["curiosity"] == {"x": "y"}
    assert client.post(f"/api/projects/{pid}/ops/undo").status_code == 200
    assert client.get(f"/api/projects/{pid}").json()["decisions"]["curiosity"] != {"x": "y"}
    gen = [f["path"] for f in client.get(U(pid)).json()["files"] if f["generated"]][0]
    assert client.put(f"{U(pid)}/{gen}", json={"content": "x"}).status_code == 403
    assert get(client, pid, gen)["editable"] is False
    assert client.get(f"{U(pid)}/nope.ttl").status_code == 404


def test_error_position_is_exact_with_accents(client, pid):
    """rdflib donne un indice de caractère : avec des accents (offset ≠ octets) la ligne reste exacte."""
    txt = get(client, pid, "onto.ttl")["content"]
    n = txt.count("\n")
    assert any(ord(ch) > 127 for ch in txt)
    for extra, expect_line in (("<http://x/a> a <http://x/B>\n<http://x/c> a <http://x/D> .\n", n + 2),
                               ("foo:Bar a .\n", n + 1)):
        d = client.post(f"{U(pid)}/validate", json={"path": "onto.ttl", "content": txt + extra}).json()["diagnostics"]
        assert d[0]["severity"] == "error" and d[0]["line"] == expect_line and d[0]["col"] == 1, (extra, d)
