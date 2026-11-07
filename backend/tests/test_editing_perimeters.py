"""L9 — périmètres : CRUD, restriction de l'analyse / génération sur automaint, décisions partagées."""
import pytest
from fastapi.testclient import TestClient

from ontoforge.io.rdf_import import parse_ontology
from ontoforge.main import app

AM = "https://w3id.org/ontoforge/automaint#"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("ONTOFORGE_DATA", str(tmp_path))
    return TestClient(app)


@pytest.fixture
def pid(client, samples_dir):
    pid = client.post("/api/projects", json={"name": "Périmètres"}).json()["id"]
    text = (samples_dir / "automaint" / "automaint.ttl").read_text(encoding="utf-8")
    onto, _ = parse_ontology(text, filename="automaint.ttl")
    r = client.put(f"/api/projects/{pid}/onto", json=onto.model_dump(mode="json"))
    assert r.status_code == 200, r.text
    return pid


def onto_of(client, pid):
    return client.get(f"/api/projects/{pid}").json()["onto"]


def pick(client, pid):
    o = onto_of(client, pid)
    classes = sorted(o["classes"])
    objs = [(i, p) for i, p in o["object_properties"].items() if p["domain"] and p["range"]]
    return o, classes, objs


def test_crud_and_validation(client, pid):
    o, classes, objs = pick(client, pid)
    r = client.post(f"/api/projects/{pid}/perimeters", json={"name": "Parc", "classes": classes[:3]})
    assert r.status_code == 201, r.text
    per = r.json()
    assert per["id"] == "parc" and per["include_descendants"] is False
    assert client.post(f"/api/projects/{pid}/perimeters", json={"name": "Parc"}).json()["id"] == "parc-2"
    assert client.post(f"/api/projects/{pid}/perimeters", json={"name": "X", "classes": [AM + "Nope"]}).status_code == 422
    assert client.post(f"/api/projects/{pid}/perimeters", json={"name": "Parc", "id": "parc"}).status_code == 409
    assert len(client.get(f"/api/projects/{pid}/perimeters").json()) == 2
    r = client.put(f"/api/projects/{pid}/perimeters/parc", json={"name": "Parc 2", "classes": classes[:2], "include_descendants": True})
    assert r.json()["name"] == "Parc 2" and r.json()["include_descendants"] is True
    assert client.put(f"/api/projects/{pid}/perimeters/active", json={"id": "parc"}).json() == {"active_perimeter": "parc"}
    assert client.put(f"/api/projects/{pid}/perimeters/active", json={"id": "zzz"}).status_code == 404
    assert client.get(f"/api/projects/{pid}").json()["active_perimeter"] == "parc"
    assert client.delete(f"/api/projects/{pid}/perimeters/parc").json()["active_perimeter"] is None
    assert client.get(f"/api/projects/{pid}/perimeters/parc").status_code == 404
    # annuler la suppression
    assert client.post(f"/api/projects/{pid}/ops/undo").status_code == 200
    assert client.get(f"/api/projects/{pid}/perimeters/parc").status_code == 200


def test_analyze_restricted(client, pid):
    o, classes, objs = pick(client, pid)
    full = client.post(f"/api/projects/{pid}/analyze", params={"target": "neo4j"})
    assert full.status_code == 200, full.text
    full = full.json()
    # périmètre : une propriété d'objet, ses classes de domaine et de portée
    iri, p = objs[0]
    keep = sorted(set(p["domain"]) | set(p["range"]))
    per = client.post(f"/api/projects/{pid}/perimeters", json={"name": "Mini", "classes": keep}).json()
    r = client.post(f"/api/projects/{pid}/analyze", params={"target": "neo4j", "perimeter": per["id"]})
    assert r.status_code == 200, r.text
    sub = r.json()
    assert len(sub["node_types"]) < len(full["node_types"])
    assert len(sub["edge_types"]) < len(full["edge_types"])
    # nœuds du sous-modèle ⊆ nœuds du modèle complet
    assert set(sub["node_types"]) <= set(full["node_types"])
    ids = {f["id"] for f in sub["findings"]}
    assert "P00:" + per["id"] in ids
    info = [f for f in sub["findings"] if f["rule"].startswith("P")]
    assert info and all(f["severity"] == "info" and f["detail"] for f in info)
    # une relation exclue est expliquée
    assert any(f["rule"] == "P01" for f in info) or len(sub["edge_types"]) >= 1
    # aucun IRI hors périmètre dans les types de nœuds
    for nt in sub["node_types"].values():
        assert all(s in keep for s in nt["source"]), nt["source"]
    # défaut = ontologie complète
    again = client.post(f"/api/projects/{pid}/analyze", params={"target": "neo4j"}).json()
    assert len(again["node_types"]) == len(full["node_types"])
    assert client.post(f"/api/projects/{pid}/analyze", params={"perimeter": "nope"}).status_code == 404
    assert client.post(f"/api/projects/{pid}/analyze", params={"target": "neo4j", "perimeter": "all"}).json()["node_types"].keys() == full["node_types"].keys()


def test_descendants_and_properties_filter(client, pid):
    o, classes, objs = pick(client, pid)
    parent = next(c for c in classes if o["classes"][c] and any(c in x["sub_class_of"] for x in o["classes"].values()))
    desc = {k for k, v in o["classes"].items() if parent in v["sub_class_of"]}
    a = client.post(f"/api/projects/{pid}/perimeters", json={"name": "Sans", "classes": [parent]}).json()
    b = client.post(f"/api/projects/{pid}/perimeters", json={"name": "Avec", "classes": [parent], "include_descendants": True}).json()
    ga = client.get(f"/api/projects/{pid}/graph", params={"perimeter": a["id"]}).json()
    gb = client.get(f"/api/projects/{pid}/graph", params={"perimeter": b["id"]}).json()
    assert {n["id"] for n in ga["nodes"]} == {parent}
    assert {n["id"] for n in gb["nodes"]} >= {parent} | desc
    # liste explicite de propriétés : seules celles-ci (et dont les extrémités sont dans le périmètre)
    iri, p = objs[0]
    keep = sorted(set(p["domain"]) | set(p["range"]) | {x for _, q in objs for x in q["domain"] + q["range"]})
    c = client.post(f"/api/projects/{pid}/perimeters", json={"name": "Une", "classes": keep, "properties": [iri]}).json()
    g = client.get(f"/api/projects/{pid}/graph", params={"perimeter": c["id"]}).json()
    assert {e["iri"] for e in g["edges"] if e["kind"] == "objectProperty"} == {iri}
    prev = client.get(f"/api/projects/{pid}/perimeters/{c['id']}/preview").json()
    assert prev["counts"]["object_properties"] == 1 and prev["excluded"]


def test_decisions_shared_between_perimeters(client, pid):
    full = client.post(f"/api/projects/{pid}/analyze", params={"target": "neo4j"}).json()
    pending = [f for f in full["findings"] if f["severity"] != "auto" and f["options"]]
    if not pending:
        pytest.skip("aucun constat à arbitrer dans automaint")
    o = onto_of(client, pid)
    # périmètre = toute l'ontologie : mêmes constats, mêmes ids
    per = client.post(f"/api/projects/{pid}/perimeters", json={"name": "Tout", "classes": sorted(o["classes"])}).json()
    f = pending[0]
    opt = f["options"][0]["id"]
    r = client.put(f"/api/projects/{pid}/decisions/neo4j", json={f["id"]: opt})
    assert r.status_code == 200
    sub = client.post(f"/api/projects/{pid}/analyze", params={"target": "neo4j", "perimeter": per["id"]}).json()
    got = {x["id"]: x for x in sub["findings"]}
    assert got[f["id"]]["chosen"] == opt
    base_ids = {x["id"] for x in client.post(f"/api/projects/{pid}/analyze", params={"target": "neo4j"}).json()["findings"]}
    assert base_ids <= set(got)  # mêmes ids de constats


def test_generate_with_perimeter(client, pid):
    o, classes, objs = pick(client, pid)
    iri, p = objs[0]
    keep = sorted(set(p["domain"]) | set(p["range"]))
    per = client.post(f"/api/projects/{pid}/perimeters", json={"name": "Mini", "classes": keep}).json()
    full = client.get(f"/api/projects/{pid}/generate/neo4j")
    sub = client.get(f"/api/projects/{pid}/generate/neo4j", params={"perimeter": per["id"]})
    assert full.status_code == 200 and sub.status_code == 200, sub.text
    assert sum(len(v) for v in sub.json()["files"].values()) < sum(len(v) for v in full.json()["files"].values())
    z = client.get(f"/api/projects/{pid}/generate/neo4j/zip", params={"perimeter": per["id"]})
    assert z.status_code == 200 and z.headers["content-type"] == "application/zip"
    assert client.get(f"/api/projects/{pid}/generate/neo4j", params={"perimeter": "nope"}).status_code == 404


def test_delete_entity_prunes_perimeters(client, pid):
    o, classes, objs = pick(client, pid)
    per = client.post(f"/api/projects/{pid}/perimeters", json={"name": "P", "classes": classes[:2]}).json()
    r = client.post(f"/api/projects/{pid}/ops", json={"ops": [{"op": "delete_entity", "iri": classes[0]}]}).json()
    assert r["ok"]
    assert classes[0] not in client.get(f"/api/projects/{pid}/perimeters/{per['id']}").json()["classes"]
    client.post(f"/api/projects/{pid}/ops/undo")
    assert classes[0] in client.get(f"/api/projects/{pid}/perimeters/{per['id']}").json()["classes"]
