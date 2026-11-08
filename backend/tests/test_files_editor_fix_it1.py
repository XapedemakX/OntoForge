"""L22 — corrections de la revue it1 : préfixes conservés, texte source conservé, compteur de réécritures, limites."""
import re

import pytest
from fastapi.testclient import TestClient

from ontoforge.main import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("ONTOFORGE_DATA", str(tmp_path))
    return TestClient(app)


@pytest.fixture
def pid(client):
    r = client.post("/api/projects", json={"name": "Fix it1", "sample": "automaint"})
    assert r.status_code == 201
    return r.json()["id"]


def U(pid):
    return f"/api/projects/{pid}/files"


def get(client, pid, path):
    return client.get(f"{U(pid)}/{path}").json()


def put(client, pid, path, content, **kw):
    return client.put(f"{U(pid)}/{path}", json={"content": content, **kw})


# ---- 3. préfixes ----------------------------------------------------------------------------------------------

def test_sample_keeps_source_prefixes_in_all_views(client, pid):
    prj = client.get(f"/api/projects/{pid}").json()
    assert prj["onto"]["meta"]["prefixes"].get("am") == "https://w3id.org/ontoforge/automaint#"
    onto = get(client, pid, "onto.ttl")["content"]
    assert "@prefix am: <https://w3id.org/ontoforge/automaint#>" in onto
    assert len(re.findall(r"<https://w3id\.org/ontoforge/automaint#", onto)) < 10
    exp = client.get(f"/api/projects/{pid}/export/ontology?format=turtle").text
    assert "@prefix am:" in exp and len(re.findall(r"<https://w3id\.org/ontoforge/automaint#", exp)) < 10
    shapes = get(client, pid, "shapes.ttl")["content"]
    assert "@prefix am:" in shapes and "@prefix ams:" in shapes
    assert len(re.findall(r"<https://w3id\.org/ontoforge/automaint", shapes)) < 10
    exps = client.get(f"/api/projects/{pid}/export/shapes?format=turtle").text
    assert "@prefix am:" in exps and "@prefix ams:" in exps


def test_prefixless_source_gets_a_derived_prefix(client):
    """Un RDF/XML sans préfixe pour l'espace de noms de l'ontologie : un préfixe dérivé de l'IRI d'ontologie est lié."""
    xml = open("../samples/automaint/automaint.owl", encoding="utf-8").read()
    r = client.post("/api/projects", json={"name": "Xml"}).json()
    from ontoforge.editing import files as fm
    from ontoforge.io.rdf_import import parse_ontology
    m, _ = parse_ontology(xml, "xml")
    text = fm.canonical_turtle(fm.onto_graph(m))
    assert "@prefix automaint: <https://w3id.org/ontoforge/automaint#>" in text
    assert len(re.findall(r"<https://w3id\.org/ontoforge/automaint#", text)) < 10
    assert r["id"]


# ---- 1. commentaires : texte source conservé -------------------------------------------------------------------

def _with_comments(txt):
    return "# En-tête de l'utilisateur\n" + txt.replace("\n\n", "\n\n# bloc commenté\n", 3) + "\nex:Z a ex:Z . # fin\n".replace("ex:Z a ex:Z . # fin\n", "")


def test_typed_text_and_comments_are_kept_when_graph_is_isomorphic(client, pid):
    cur = get(client, pid, "onto.ttl")
    typed = _with_comments(cur["content"])
    d = client.post(f"{U(pid)}/diff", json={"path": "onto.ttl", "content": typed}).json()
    s = d["summary"]
    assert (s["added"], s["removed"]) == (0, 0) and s["rewritten"]["count"] == 0
    assert s["source_kept"] is True and s["comment_lines"] == 4 and s["comments_lost"] == 0
    assert d["after"] == typed
    r = put(client, pid, "onto.ttl", typed, base_etag=cur["etag"])
    assert r.status_code == 200 and r.json()["changed"] is True
    back = get(client, pid, "onto.ttl")
    assert back["content"] == typed and back["source"]["state"] == "source"
    assert get(client, pid, "onto.ttl")["etag"] == back["etag"]
    # le modèle n'a pas bougé : pas d'entrée d'historique, l'ontologie est identique
    assert client.get(f"/api/projects/{pid}").json()["onto"]["classes"]


def test_other_screen_edit_falls_back_to_canonical_with_note(client, pid):
    cur = get(client, pid, "onto.ttl")
    typed = _with_comments(cur["content"])
    assert put(client, pid, "onto.ttl", typed, base_etag=cur["etag"]).status_code == 200
    # modification par un autre écran (API d'édition du modèle)
    prj = client.get(f"/api/projects/{pid}").json()
    prj["onto"]["meta"]["label"] = None
    first = next(iter(prj["onto"]["classes"].values()))
    first["annotations"] = list(first.get("annotations") or []) + [{"property": "http://www.w3.org/2000/01/rdf-schema#comment", "value": "ajout externe", "lang": "fr"}]
    assert client.put(f"/api/projects/{pid}", json=prj).status_code == 200
    back = get(client, pid, "onto.ttl")
    assert back["source"]["state"] == "canonical" and back["source"]["comment_lines"] == 4
    assert "# En-tête de l'utilisateur" not in back["content"]


def test_rewritten_triples_are_counted_and_comments_loss_announced(client, pid):
    ttl = """# note
@prefix ex: <http://e.org/> . @prefix owl: <http://www.w3.org/2002/07/owl#> .
ex:A a owl:Class . ex:B a owl:Class . ex:C a owl:Class . # trailing
[] a owl:AllDisjointClasses ; owl:members ( ex:A ex:B ex:C ) .
"""
    d = client.post(f"{U(pid)}/diff", json={"path": "onto.ttl", "content": ttl}).json()
    s = d["summary"]
    assert s["rewritten"]["count"] > 0 and s["rewritten"]["samples"]["from"] and s["rewritten"]["samples"]["to"]
    assert s["source_kept"] is False and s["comment_lines"] == 2 and s["comments_lost"] == 2
    assert "# note" not in d["after"]
    r = put(client, pid, "onto.ttl", ttl)
    assert r.status_code == 200
    assert "# note" not in r.json()["content"] and r.json()["source"] is None


def test_comment_lines_ignores_hash_in_strings_and_iris():
    from ontoforge.editing.files import comment_lines
    t = '@prefix ex: <http://e.org/ns#> .\nex:a ex:p "no # comment" .\n# yes\nex:b ex:p "x" . # yes\n'
    assert comment_lines(t) == 2


# ---- non-bloquants --------------------------------------------------------------------------------------------

def test_shacl_meta_messages_are_localized_and_deduplicated(client, pid):
    txt = ('@prefix sh: <http://www.w3.org/ns/shacl#> .\n@prefix ex: <http://e.org/> .\n'
           'ex:S a sh:NodeShape ; sh:property [ sh:path ex:q ; sh:in ex:a ] .\n')
    d = client.post(f"{U(pid)}/validate", json={"path": "shapes.ttl", "content": txt}).json()["diagnostics"]
    meta = [x for x in d if x["code"] == "shacl-shacl"]
    assert len(meta) == 1 and "liste RDF" in meta[0]["message"] and "ListShape" not in meta[0]["message"]


def test_nodeshape_with_path_is_flagged(client, pid):
    txt = '@prefix sh: <http://www.w3.org/ns/shacl#> .\n@prefix ex: <http://e.org/> .\nex:S a sh:NodeShape ;\n  sh:path ex:p .\n'
    d = client.post(f"{U(pid)}/validate", json={"path": "shapes.ttl", "content": txt}).json()["diagnostics"]
    w = [x for x in d if x["code"] == "shacl-nodeshape-path"]
    assert len(w) == 1 and w[0]["severity"] == "warning" and w[0]["line"] == 3


def test_body_size_limit(client, pid):
    big = "x" * 9_000_000
    r = client.put(f"{U(pid)}/onto.ttl", content=('{"content": "' + big + '"}').encode(), headers={"content-type": "application/json"})
    assert r.status_code == 413
    r = client.post(f"{U(pid)}/validate", json={"path": "onto.ttl", "content": big})
    assert r.status_code == 413
