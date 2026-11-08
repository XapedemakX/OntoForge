"""L22 — revue it2 (w3c) : texte saisi conservé, préfixe de repli, ordre .ttl/.owl des exemples."""
import re

import pytest
import rdflib
from fastapi.testclient import TestClient
from rdflib.compare import isomorphic

from ontoforge import samples
from ontoforge.api.projects import _parse_onto, _parse_shapes
from ontoforge.editing import files as fm
from ontoforge.main import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("ONTOFORGE_DATA", str(tmp_path))
    return TestClient(app)


@pytest.fixture
def pid(client):
    return client.post("/api/projects", json={"name": "it2", "sample": "automaint"}).json()["id"]


def U(pid):
    return f"/api/projects/{pid}/files"


def get(client, pid, path="onto.ttl"):
    return client.get(f"{U(pid)}/{path}").json()


def commented(txt):
    return "# En-tête\n" + txt.replace("\n\n", "\n\n# bloc\n", 2)


def ops(client, pid, o):
    r = client.post(f"/api/projects/{pid}/ops", json={"ops": o}).json()
    assert r["ok"], r
    return r


# ---- texte saisi conservé « tant qu'il est isomorphe » -------------------------------------------------------

def test_source_survives_noop_then_returns_after_undo_of_foreign_edit(client, pid):
    cur = get(client, pid)
    typed = commented(cur["content"])
    assert client.put(f"{U(pid)}/onto.ttl", json={"content": typed, "base_etag": cur["etag"]}).status_code == 200
    assert get(client, pid)["content"] == typed
    # modification venue de /ops : note canonique avec le nombre de lignes perdues
    ops(client, pid, [{"op": "add_class", "iri": "http://e.org/Nouv", "label": "Nouv"}])
    g = get(client, pid)
    assert g["source"] == {"state": "canonical", "comment_lines": 3} and "# En-tête" not in g["content"]
    # l'annulation ramène un graphe isomorphe : le texte saisi revient (l'invariant est l'etag canonique)
    client.post(f"/api/projects/{pid}/ops/undo")
    g2 = get(client, pid)
    assert g2["content"] == typed and g2["source"]["state"] == "source"
    # refaire : de nouveau canonique, sans fuite du texte saisi
    client.post(f"/api/projects/{pid}/ops/redo")
    assert get(client, pid)["source"]["state"] == "canonical"


def test_foreign_edit_then_save_from_editor_does_not_resurrect_old_source(client, pid):
    cur = get(client, pid)
    typed = commented(cur["content"])
    client.put(f"{U(pid)}/onto.ttl", json={"content": typed, "base_etag": cur["etag"]})
    ops(client, pid, [{"op": "add_class", "iri": "http://e.org/Nouv", "label": "Nouv"}])
    canon = get(client, pid)
    assert client.put(f"{U(pid)}/onto.ttl", json={"content": canon["content"], "base_etag": canon["etag"]}).status_code == 200
    after = get(client, pid)
    assert after["content"] == canon["content"]
    # même graphe, texte neuf : plus de commentaires, et l'annulation de /ops n'en ramène pas l'ancien texte par erreur
    assert "# En-tête" not in after["content"]


def test_file_apply_with_model_change_then_undo_gives_canonical_and_redo_gives_source(client, pid):
    cur = get(client, pid)
    typed = commented(cur["content"]) + '\n<http://e.org/Q> a <http://www.w3.org/2002/07/owl#Class> .\n'
    r = client.put(f"{U(pid)}/onto.ttl", json={"content": typed, "base_etag": cur["etag"]})
    assert r.status_code == 200 and r.json()["source"]["state"] == "source"
    client.post(f"/api/projects/{pid}/ops/undo")
    u = get(client, pid)
    assert u["source"]["state"] == "canonical" and "http://e.org/Q" not in u["content"]
    client.post(f"/api/projects/{pid}/ops/redo")
    assert get(client, pid)["content"] == typed


def test_served_source_is_isomorphic_to_project_graph(client, pid):
    cur = get(client, pid)
    typed = commented(cur["content"])
    client.put(f"{U(pid)}/onto.ttl", json={"content": typed, "base_etag": cur["etag"]})
    for step in ("edit", "undo", "redo", "undo"):
        if step == "edit":
            ops(client, pid, [{"op": "add_class", "iri": "http://e.org/Nouv", "label": "Nouv"}])
        else:
            client.post(f"/api/projects/{pid}/ops/{step}")
        served = get(client, pid)
        from ontoforge.api._common import load_project
        p = load_project(pid)
        g_served = rdflib.Graph().parse(data=served["content"], format="turtle")
        assert isomorphic(g_served, fm.onto_graph(p.onto)), step


# ---- préfixe de repli -------------------------------------------------------------------------------------------

def _model(iri_onto, ents, prefixes=None):
    ttl = ""
    if prefixes:
        ttl = "".join(f"@prefix {k}: <{v}> .\n" for k, v in prefixes.items())
    ttl += "@prefix owl: <http://www.w3.org/2002/07/owl#> .\n"
    ttl += f"<{iri_onto}> a owl:Ontology .\n" + "".join(f"<{e}> a owl:Class .\n" for e in ents)
    from ontoforge.io.rdf_import import parse_ontology
    m, _ = parse_ontology(ttl, "turtle")
    return fm.canonical_turtle(fm.onto_graph(m))


@pytest.mark.parametrize("onto,sep,expected", [
    ("http://e.org/ns/garage", "#", "garage"),
    ("http://e.org/ns/garage#", "#", "garage"),
    ("http://e.org/ns/garage", "/", "garage"),
    ("http://e.org/ns/garage/", "/", "garage"),
    ("http://e.org/ns/1.0", "#", "onto"),
])
def test_fallback_prefix_for_hash_and_slash(onto, sep, expected):
    base = onto.rstrip("#/")
    text = _model(onto, [f"{base}{sep}{n}" for n in ("A", "B", "C")])
    assert f"@prefix {expected}: <{base}{sep}>" in text, text
    assert len(re.findall(re.escape("<" + base + sep), text)) <= 1 + (1 if onto.rstrip("#/") + sep == onto else 0)


def test_fallback_does_not_mask_declared_prefix():
    text = _model("http://e.org/ns/garage", [f"http://e.org/ns/garage#{n}" for n in "ABC"], {"gar": "http://e.org/ns/garage#"})
    assert "@prefix gar: <http://e.org/ns/garage#>" in text
    assert "@prefix garage:" not in text


def test_fallback_avoids_collision_with_declared_name():
    text = _model("http://e.org/ns/garage", [f"http://e.org/ns/garage#{n}" for n in "ABC"] + ["http://autre.org/x#Z"], {"garage": "http://autre.org/x#"})
    assert "@prefix garage: <http://autre.org/x#>" in text
    assert "@prefix garage2: <http://e.org/ns/garage#>" in text


# ---- ordre .ttl avant .owl dans les exemples --------------------------------------------------------------

def test_sample_ttl_first_is_isomorphic_to_former_owl_first():
    s = samples.get_sample("automaint")
    assert s["ontology"][0].endswith(".ttl") and any(f.endswith(".owl") for f in s["ontology"])
    new_name = s["ontology"][0]
    old_name = next(f for f in sorted(s["ontology"]) if f.endswith(".owl"))  # ancien ordre alphabétique : .owl avant .ttl
    new, _ = _parse_onto((s["dir"] / new_name).read_bytes(), new_name)
    old, _ = _parse_onto((s["dir"] / old_name).read_bytes(), old_name)
    assert isomorphic(fm.onto_graph(new), fm.onto_graph(old))
    # seuls les préfixes déclarés diffèrent
    assert set(old.meta.prefixes) <= set(new.meta.prefixes)


@pytest.mark.parametrize("name", ["automaint", "trap"])
def test_sample_roles_order_is_stable_per_role(name):
    s = samples.get_sample(name)
    for role in ("ontology", "shapes", "data"):
        files = s[role]
        assert files == sorted(files, key=lambda n: (0 if n.endswith(".ttl") else 1, n))
    assert not any("nondl" in f for f in s["ontology"])


def test_trap_and_shapes_unchanged_by_order():
    s = samples.get_sample("trap")
    assert s["ontology"] == ["trap.ttl"] and s["shapes"] == ["trap-shapes.ttl"]
    a = samples.get_sample("automaint")
    assert a["shapes"] == ["automaint-shapes.ttl"] and a["data"][0] == "automaint-data.ttl"
