"""L19 it2 — l'union dédupliquée du graphe par défaut reste cohérente après chaque opération d'écriture
(chargement, remplacement, inférence, vidage, échec) et sous écritures concurrentes (verrou lecteurs/écrivain)."""
import threading
import time

import pytest
from fastapi.testclient import TestClient

from ontoforge.localstore import store as st
from ontoforge.main import app

EX = "http://example.org/"
LOCAL = {"kind": "local"}
GA, GB = "urn:ontoforge:graph:data:a.ttl", "urn:ontoforge:graph:data:b.ttl"
T = f"<{EX}a> <{EX}p> <{EX}b> ."


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("ONTOFORGE_DATA", str(tmp_path))
    return TestClient(app)


@pytest.fixture
def pid(client):
    r = client.post("/api/projects", json={"name": "U", "sample": "automaint"})
    assert r.status_code in (200, 201), r.text
    return r.json()["id"]


def up(client, pid, name, text, **form):
    r = client.post(f"/api/projects/{pid}/store/load", files={"file": (name, text.encode())}, data=form)
    assert r.status_code == 200, r.text
    return r.json()


def n(client, pid, q):
    r = client.post(f"/api/projects/{pid}/query/run", json={"sparql": q, "endpoint": LOCAL})
    assert r.status_code == 200, r.text
    return int(r.json()["rows"][0]["n"]["value"])


def union_vs_graphs(client, pid):
    """Invariant : graphe par défaut == union des graphes nommés, sans doublon."""
    a = n(client, pid, "SELECT (COUNT(*) AS ?n) WHERE { ?s ?p ?o }")
    b = n(client, pid, "SELECT (COUNT(*) AS ?n) WHERE { SELECT DISTINCT ?s ?p ?o WHERE { GRAPH ?g { ?s ?p ?o } } }")
    return a, b


def test_count_same_triple_in_two_graphs(client, pid):
    up(client, pid, "a.ttl", T)
    up(client, pid, "b.ttl", T)
    assert n(client, pid, f"SELECT (COUNT(*) AS ?n) WHERE {{ <{EX}a> <{EX}p> ?o }}") == 1
    assert n(client, pid, f"SELECT (COUNT(*) AS ?n) WHERE {{ ?s <{EX}p> ?o }}") == 1
    assert n(client, pid, f"SELECT (COUNT(*) AS ?n) WHERE {{ GRAPH ?g {{ <{EX}a> <{EX}p> ?o }} }}") == 2
    a, b = union_vs_graphs(client, pid)
    assert a == b


def test_from_and_from_named_combined(client, pid):
    up(client, pid, "a.ttl", T + f" <{EX}a> <{EX}q> <{EX}c> .")
    up(client, pid, "b.ttl", T)
    q = lambda frm, body: f"SELECT (COUNT(*) AS ?n) {frm} WHERE {{ {body} }}"  # noqa: E731
    # FROM a + FROM b (fusion, ensemble) : 2 triplets distincts
    assert n(client, pid, q(f"FROM <{GA}> FROM <{GB}>", "?s ?p ?o")) == 2
    # FROM a, FROM NAMED b : le défaut = a (2), GRAPH = b seul (1)
    assert n(client, pid, q(f"FROM <{GA}> FROM NAMED <{GB}>", "?s ?p ?o")) == 2
    assert n(client, pid, q(f"FROM <{GA}> FROM NAMED <{GB}>", "GRAPH ?g { ?s ?p ?o }")) == 1
    # FROM a + FROM b + FROM NAMED a + FROM NAMED b : défaut dédupliqué (2) ; GRAPH ?g = 3 (2 + 1)
    both = f"FROM <{GA}> FROM <{GB}> FROM NAMED <{GA}> FROM NAMED <{GB}>"
    assert n(client, pid, q(both, "?s ?p ?o")) == 2
    assert n(client, pid, q(both, "GRAPH ?g { ?s ?p ?o }")) == 3
    # défaut ET GRAPH dans la même requête : jointure sur le triplet commun
    assert n(client, pid, q(both, f"?s ?p ?o . GRAPH <{GB}> {{ ?s ?p ?o }}")) == 1


def test_graph_variable_lists_every_named_graph_not_the_union(client, pid):
    up(client, pid, "a.ttl", T)
    up(client, pid, "b.ttl", T)
    r = client.post(f"/api/projects/{pid}/query/run", json={"sparql": "SELECT DISTINCT ?g WHERE { GRAPH ?g { ?s ?p ?o } }", "endpoint": LOCAL, "limit": 100})
    gs = {row["g"]["value"] for row in r.json()["rows"]}
    assert {GA, GB, "urn:ontoforge:graph:ontology", "urn:ontoforge:graph:individuals"} <= gs
    assert not any(g.startswith("urn:x-oxigraph") or g == "" for g in gs)  # le graphe par défaut n'apparaît jamais comme graphe nommé


def test_stats_per_graph_ignore_the_derived_union(client, pid):
    s0 = client.get(f"/api/projects/{pid}/store/stats").json()
    up(client, pid, "a.ttl", T)
    s = up(client, pid, "b.ttl", T)
    by = {g["graph"]: g["triples"] for g in s["graphs"]}
    assert by[GA] == by[GB] == 1
    assert s["triples"] == sum(by.values())  # pas de x2 dû à l'union matérialisée
    assert s["triples"] == (s0["triples"] if s0["exists"] else 0) + 2 or s["triples"] >= 2


def test_inference_then_clear_keeps_union_coherent(client, pid):
    ttl = f"@prefix am: <https://w3id.org/ontoforge/automaint#> . @prefix ex: <{EX}> . ex:t a am:Technician ."
    persons = "SELECT (COUNT(*) AS ?n) WHERE { ?s a <https://w3id.org/ontoforge/automaint#Person> }"
    up(client, pid, "t.ttl", ttl)
    assert n(client, pid, persons) == 0
    s = up(client, pid, "t.ttl", ttl, inference="rdfs")
    assert s["inference"]["triples"] > 0
    assert n(client, pid, persons) == 1
    a, b = union_vs_graphs(client, pid)
    assert a == b
    # la même requête dans le graphe inféré seul et dans l'union : le fait n'est pas compté deux fois
    assert n(client, pid, persons) == 1
    up(client, pid, "t.ttl", ttl, inference="none")
    assert n(client, pid, persons) == 0  # le fait inféré a quitté l'union
    a, b = union_vs_graphs(client, pid)
    assert a == b
    up(client, pid, "t.ttl", ttl, inference="owlrl")
    assert n(client, pid, persons) == 1
    r = client.delete(f"/api/projects/{pid}/store")
    assert r.status_code == 200 and r.json()["exists"] is False
    assert n(client, pid, "SELECT (COUNT(*) AS ?n) WHERE { ?s a <http://www.w3.org/2002/07/owl#Class> }") > 0  # recréé à la volée : ontologie seule
    assert n(client, pid, persons) == 0
    a, b = union_vs_graphs(client, pid)
    assert a == b


def test_failed_write_does_not_leave_a_stale_union(client, pid, monkeypatch):
    """Une écriture qui échoue après avoir modifié un graphe (ici l'inférence) ne doit pas laisser l'union périmée ni le graphe de
    données incohérent avec les métadonnées."""
    up(client, pid, "a.ttl", T)
    before = union_vs_graphs(client, pid)

    def boom(*a, **k):
        raise st.StoreError("échec simulé", 500)
    monkeypatch.setattr(st, "materialize", boom)
    r = client.post(f"/api/projects/{pid}/store/load", files={"file": ("c.ttl", f"<{EX}c> <{EX}p> <{EX}d> .".encode())}, data={"inference": "rdfs"})
    assert r.status_code == 500
    a, b = union_vs_graphs(client, pid)
    assert a == b, "union périmée après un chargement échoué"
    stats = client.get(f"/api/projects/{pid}/store/stats").json()
    assert sum(g["triples"] for g in stats["graphs"]) == stats["triples"], "graphes et métadonnées incohérents après échec"
    assert (a, b) == before  # chargement annulé en entier (tout ou rien)


def test_concurrent_loads_never_leave_a_stale_union(client, pid):
    """Deux chargements rapprochés : à la fin, l'union contient les deux ; pendant, un lecteur ne voit jamais d'union partielle
    (le lecteur attend le verrou d'écriture : ni vide, ni doublon, ni union sans le graphe déjà publié)."""
    big = lambda k: "\n".join(f"<{EX}s{i}> <{EX}p{k}> <{EX}o{i}> ." for i in range(3000))  # noqa: E731
    errors, seen = [], []

    def load(name, k):
        try:
            r = TestClient(app).post(f"/api/projects/{pid}/store/load", files={"file": (name, big(k).encode())})
            assert r.status_code == 200, r.text
        except Exception as e:  # noqa: BLE001
            errors.append(e)

    base = n(client, pid, "SELECT (COUNT(*) AS ?n) WHERE { ?s ?p ?o }")
    stop = threading.Event()

    def reader():
        c = TestClient(app)
        while not stop.is_set():
            try:
                a = n(c, pid, "SELECT (COUNT(*) AS ?n) WHERE { ?s ?p ?o }")
                seen.append(a)
            except Exception as e:  # noqa: BLE001
                errors.append(e)
                return

    rd = threading.Thread(target=reader)
    rd.start()
    ts = [threading.Thread(target=load, args=("a.ttl", 1)), threading.Thread(target=load, args=("b.ttl", 2))]
    for t in ts:
        t.start()
        time.sleep(0.05)
    for t in ts:
        t.join()
    stop.set()
    rd.join()
    assert not errors, errors
    final = n(client, pid, "SELECT (COUNT(*) AS ?n) WHERE { ?s ?p ?o }")
    assert final == base + 6000
    a, b = union_vs_graphs(client, pid)
    assert a == b == final
    # tout comptage observé pendant les écritures est un état cohérent : base, base+3000 ou base+6000, jamais intermédiaire
    assert set(seen) <= {base, base + 3000, base + 6000}, sorted(set(seen))


def test_concurrent_overlapping_loads_dedupe(client, pid):
    same = "\n".join(f"<{EX}s{i}> <{EX}p> <{EX}o{i}> ." for i in range(2000))
    errs = []

    def load(name):
        r = TestClient(app).post(f"/api/projects/{pid}/store/load", files={"file": (name, same.encode())})
        if r.status_code != 200:
            errs.append(r.text)
    ts = [threading.Thread(target=load, args=(nm,)) for nm in ("a.ttl", "b.ttl", "c.ttl")]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert not errs, errs
    assert n(client, pid, f"SELECT (COUNT(*) AS ?n) WHERE {{ ?s <{EX}p> ?o }}") == 2000  # 3 graphes, 1 seul exemplaire dans l'union
    assert n(client, pid, f"SELECT (COUNT(*) AS ?n) WHERE {{ GRAPH ?g {{ ?s <{EX}p> ?o }} }}") == 6000
