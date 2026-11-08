"""L19 — triplestore local embarqué : chargement, requête guidée Diesel (10 lignes), refus d'UPDATE / SERVICE, inférence,
formats, plafonds, délai, persistance, validation SHACL, valeurs possibles. Aucune dépendance réseau."""
import http.server
import json
import threading

import pytest
from fastapi.testclient import TestClient

from ontoforge.main import app

AM = "https://w3id.org/ontoforge/automaint#"
LOCAL = {"kind": "local"}


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("ONTOFORGE_DATA", str(tmp_path))
    return TestClient(app)


@pytest.fixture
def pid(client):
    r = client.post("/api/projects", json={"name": "AM", "sample": "automaint"})
    assert r.status_code in (200, 201), r.text
    return r.json()["id"]


@pytest.fixture
def spy():
    """Petit serveur HTTP de boucle locale : toute requête reçue prouve un accès réseau sortant."""
    hits: list[str] = []

    class H(http.server.BaseHTTPRequestHandler):
        def _any(self):
            hits.append(self.path)
            self.send_response(200)
            self.send_header("content-type", "application/ld+json")
            self.end_headers()
            self.wfile.write(b'{"@context": {"x": "http://example.org/"}}')
        do_GET = do_POST = _any

        def log_message(self, *a):
            pass

    srv = http.server.HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield srv.server_port, hits
    srv.shutdown()


def load_demo(client, pid, **form):
    r = client.post(f"/api/projects/{pid}/store/load", data={"sample": "demo", **form})
    assert r.status_code == 200, r.text
    return r.json()


def run(client, pid, sparql=None, guided=None, **extra):
    body = {"endpoint": LOCAL, **extra}
    body.update({"guided": guided} if guided else {"sparql": sparql})
    return client.post(f"/api/projects/{pid}/query/run", json=body)


def diesel():
    return {"root": {"var": "v", "class_iri": AM + "Vehicle"},
            "steps": [{"from_var": "v", "property_iri": AM + "hasEngine", "to_var": "m", "to_class_iri": AM + "Engine"},
                      {"from_var": "m", "property_iri": AM + "usesFuel", "to_var": "f", "to_class_iri": AM + "FuelType"}],
            "filters": [{"var": "f", "kind": "in_values", "is_iri": True, "values": [AM + "Diesel"]}],
            "select": [{"var": "v"}, {"var": "v", "property_iri": AM + "registrationNumber"}, {"var": "m"}, {"var": "f"}], "limit": 10}


def test_stats_before_any_load(client, pid):
    s = client.get(f"/api/projects/{pid}/store/stats").json()
    assert s["exists"] is False and s["triples"] == 0 and s["demo"] == {"sample": "automaint", "file": "automaint-demo-data.ttl"}
    assert s["limits"]["max_triples"] >= 1000 and s["engine"].startswith("pyoxigraph")


def test_load_demo_and_guided_diesel_ten_rows(client, pid):
    s = load_demo(client, pid)
    kinds = {g["kind"]: g["triples"] for g in s["graphs"]}
    assert s["exists"] and s["triples"] == 4719 and kinds["data"] == 4136 and kinds["ontology"] > 400 and kinds["individuals"] > 0
    r = run(client, pid, guided=diesel())
    assert r.status_code == 200, r.text
    d = r.json()
    assert len(d["rows"]) == 10 and d["columns"] == ["v", "v_registrationNumber", "m", "f"] and d["endpoint_id"] == "local"
    assert all(row["f"]["value"] == AM + "Diesel" for row in d["rows"])
    assert d["graph"]["nodes"] and "LIMIT 10" in d["sparql"]


def test_store_is_created_with_ontology_and_individuals_on_first_query(client, pid):
    r = run(client, pid, f"SELECT ?c WHERE {{ ?c a <http://www.w3.org/2002/07/owl#Class> }}", limit=1000)
    assert r.status_code == 200 and len(r.json()["rows"]) >= 20
    # l'individu énuméré de l'éditeur (am:Diesel) est dans le triplestore avant tout chargement
    assert run(client, pid, f"ASK {{ <{AM}Diesel> a <{AM}FuelType> }}").json()["boolean"] is True


def test_ask_construct_select_forms(client, pid):
    load_demo(client, pid)
    assert run(client, pid, "ASK { ?s a <%sVehicle> }" % AM).json()["boolean"] is True
    c = run(client, pid, "CONSTRUCT { ?s a <%sVehicle> } WHERE { ?s a <%sVehicle> }" % (AM, AM)).json()
    assert c["columns"] == ["s", "p", "o"] and 0 < len(c["rows"]) <= 100
    t = run(client, pid, "SELECT ?s WHERE { ?s a <%sVehicle> }" % AM, limit=5).json()
    assert len(t["rows"]) == 5 and t["truncated"] is True and t["sparql"].rstrip().endswith("LIMIT 6")
    big = run(client, pid, "SELECT ?s ?p ?o WHERE { ?s ?p ?o } LIMIT 99999", limit=7).json()
    assert len(big["rows"]) == 7 and big["truncated"] and "LIMIT 8" in big["sparql"]


@pytest.mark.parametrize("q", ["INSERT DATA { <urn:a> <urn:b> <urn:c> }", "DELETE WHERE { ?s ?p ?o }", "CLEAR ALL",
                               "DROP GRAPH <urn:g>", "LOAD <http://127.0.0.1:9/x>"])
def test_update_refused(client, pid, q):
    load_demo(client, pid)
    before = client.get(f"/api/projects/{pid}/store/stats").json()["triples"]
    r = run(client, pid, q)
    assert r.status_code == 403 and "UPDATE" in r.json()["detail"]
    assert client.get(f"/api/projects/{pid}/store/stats").json()["triples"] == before
    assert run(client, pid, "SELEC nope").status_code == 422


def test_service_federation_refused_no_network(client, pid, spy):
    port, hits = spy
    for q in (f"SELECT * WHERE {{ SERVICE <http://127.0.0.1:{port}/sparql> {{ ?s ?p ?o }} }}",
              f"SELECT * WHERE {{ OPTIONAL {{ SERVICE SILENT <http://127.0.0.1:{port}/x> {{ ?s ?p ?o }} }} }}",
              f"SELECT * WHERE {{ {{ SELECT * WHERE {{ service <http://127.0.0.1:{port}/y> {{ ?s ?p ?o }} }} }} }}"):
        r = run(client, pid, q)
        assert r.status_code == 403 and "SERVICE" in r.json()["detail"], q
    # le mot « service » dans un littéral ou un IRI n'est PAS refusé
    ok = run(client, pid, 'SELECT * WHERE { ?s ?p ?o FILTER(CONTAINS(STR(?o), "service")) } LIMIT 3')
    assert ok.status_code == 200, ok.text
    assert hits == []


INFERENCE_TTL = f"""@prefix am: <{AM}> .
@prefix ex: <http://example.org/> .
ex:tech_sub a am:Technician .
"""
PERSONS = f"SELECT ?s WHERE {{ ?s a <{AM}Person> . FILTER(?s = <http://example.org/tech_sub>) }}"


def up(client, pid, name, text, **form):
    r = client.post(f"/api/projects/{pid}/store/load", files={"file": (name, text.encode("utf-8"))}, data=form)
    assert r.status_code == 200, r.text
    return r.json()


def test_inference_finds_subclass_individual_only_with_inference(client, pid):
    up(client, pid, "tech.ttl", INFERENCE_TTL)  # Technician est sous-classe de Person dans l'ontologie
    assert run(client, pid, PERSONS).json()["rows"] == []
    for sem in ("rdfs", "owlrl", "both"):
        s = up(client, pid, "tech.ttl", INFERENCE_TTL, inference=sem)
        assert s["inference"]["semantics"] == sem and s["inference"]["triples"] > 0
        assert any(g["kind"] == "inferred" for g in s["graphs"])
        rows = run(client, pid, PERSONS).json()["rows"]
        assert [r["s"]["value"] for r in rows] == ["http://example.org/tech_sub"], sem
    # le bruit (rdfs:Resource, owl:Thing) n'est pas matérialisé ; owl:hasKey est signalé comme ignoré
    assert run(client, pid, "ASK { ?s a <http://www.w3.org/2000/01/rdf-schema#Resource> }").json()["boolean"] is False
    assert any("hasKey" in n for n in s["inference"]["notes"])
    off = up(client, pid, "tech.ttl", INFERENCE_TTL, inference="none")
    assert off["inference"] is None and not any(g["kind"] == "inferred" for g in off["graphs"])
    assert run(client, pid, PERSONS).json()["rows"] == []


def test_inference_is_kept_and_recomputed_on_next_load(client, pid):
    up(client, pid, "tech.ttl", INFERENCE_TTL, inference="rdfs")
    up(client, pid, "autre.ttl", INFERENCE_TTL.replace("tech_sub", "tech_two"))  # inference absente du formulaire : conservée
    ids = {r["s"]["value"] for r in run(client, pid, f"SELECT ?s WHERE {{ ?s a <{AM}Person> . FILTER(STRSTARTS(STR(?s), 'http://example.org/')) }}").json()["rows"]}
    assert ids == {"http://example.org/tech_sub", "http://example.org/tech_two"}


def test_formats_turtle_ntriples_jsonld_rdfxml(client, pid):
    up(client, pid, "a.nt", '<http://example.org/n1> <http://example.org/p> "un" .\n')
    jl = {"@context": {"ex": "http://example.org/"}, "@id": "ex:j1", "ex:p": "deux"}
    up(client, pid, "b.jsonld", json.dumps(jl))
    up(client, pid, "c.rdf", '<?xml version="1.0"?><rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#" xmlns:ex="http://example.org/">'
       '<rdf:Description rdf:about="http://example.org/x1"><ex:p>trois</ex:p></rdf:Description></rdf:RDF>')
    s = up(client, pid, "d.ttl", '@prefix ex: <http://example.org/> . ex:t1 ex:p "quatre" .')
    assert {g["name"]: g["format"] for g in s["graphs"] if g["kind"] == "data"} == {"a.nt": "n-triples", "b.jsonld": "json-ld", "c.rdf": "rdf/xml", "d.ttl": "turtle"}
    vals = {r["o"]["value"] for r in run(client, pid, "SELECT ?o WHERE { ?s <http://example.org/p> ?o }").json()["rows"]}
    assert vals == {"un", "deux", "trois", "quatre"}


def test_jsonld_remote_context_refused_without_network(client, pid, spy):
    port, hits = spy
    doc = json.dumps({"@context": f"http://127.0.0.1:{port}/ctx.jsonld", "@id": "http://example.org/a", "http://example.org/p": "v"})
    r = client.post(f"/api/projects/{pid}/store/load", files={"file": ("ctx.jsonld", doc.encode())})
    assert r.status_code == 422 and "contexte JSON-LD distant" in r.json()["detail"]
    assert hits == []


def test_bad_files(client, pid):
    r = client.post(f"/api/projects/{pid}/store/load", files={"file": ("x.ttl", b"ceci n'est pas du turtle")})
    assert r.status_code == 422 and "illisible" in r.json()["detail"]
    assert client.post(f"/api/projects/{pid}/store/load", files={"file": ("vide.ttl", b"  ")}).status_code == 422
    assert client.post(f"/api/projects/{pid}/store/load", data={"sample": "inconnu"}).status_code == 404
    assert client.post(f"/api/projects/{pid}/store/load", data={"sample": "demo", "inference": "magie"}).status_code == 422
    assert client.get("/api/projects/nope/store/stats").status_code == 404


def test_replace_same_name_and_clear(client, pid):
    up(client, pid, "d.ttl", '@prefix ex: <http://example.org/> . ex:a ex:p "1" . ex:b ex:p "2" .')
    n1 = client.get(f"/api/projects/{pid}/store/stats").json()["triples"]
    s = up(client, pid, "d.ttl", '@prefix ex: <http://example.org/> . ex:a ex:p "1" .')
    assert s["triples"] == n1 - 1 and len([g for g in s["graphs"] if g["kind"] == "data"]) == 1
    r = client.delete(f"/api/projects/{pid}/store")
    assert r.status_code == 200 and r.json()["exists"] is False and r.json()["triples"] == 0
    assert client.delete(f"/api/projects/{pid}/store").status_code == 200  # idempotent


def test_persistence_in_project_folder(client, pid, tmp_path):
    load_demo(client, pid, inference="rdfs")
    db = tmp_path / "projects" / pid / "triplestore" / "db"
    assert db.is_dir() and any(db.iterdir())
    from ontoforge.localstore import store as st
    st._LOCKS.clear()  # comme après un redémarrage du serveur : tout vient du disque
    s = TestClient(app).get(f"/api/projects/{pid}/store/stats").json()
    assert s["triples"] > 4719 and s["inference"]["semantics"] == "rdfs" and s["size_kb"] > 0
    assert len(run(TestClient(app), pid, guided=diesel()).json()["rows"]) == 10
    client.delete(f"/api/projects/{pid}")  # supprimer le projet supprime son triplestore
    assert not db.exists()


def test_ontology_change_resyncs_store(client, pid):
    load_demo(client, pid)
    assert client.get(f"/api/projects/{pid}/store/stats").json()["ontology_stale"] is False
    p = client.get(f"/api/projects/{pid}").json()
    p["onto"]["classes"][AM + "Vehicle"]["labels"]["fr"] = "Véhicule modifié"
    assert client.put(f"/api/projects/{pid}", json=p).status_code == 200
    assert client.get(f"/api/projects/{pid}/store/stats").json()["ontology_stale"] is True
    r = run(client, pid, f'ASK {{ <{AM}Vehicle> <http://www.w3.org/2000/01/rdf-schema#label> "Véhicule modifié"@fr }}')
    assert r.json()["boolean"] is True  # resynchronisé à la requête
    assert client.get(f"/api/projects/{pid}/store/stats").json()["ontology_stale"] is False


def test_timeout_kills_the_query(client, pid):
    load_demo(client, pid)
    heavy = "SELECT (COUNT(*) AS ?n) WHERE { ?a ?p ?x . ?b ?q ?y . ?c ?r ?z . ?d ?s ?w }"
    r = client.post(f"/api/projects/{pid}/query/run", json={"sparql": heavy, "endpoint": {"kind": "local", "timeout_s": 1}})
    assert r.status_code == 504 and "Délai dépassé" in r.json()["detail"]
    assert run(client, pid, "ASK {}").status_code == 200  # le service reste disponible


def test_quotas(client, pid, monkeypatch):
    monkeypatch.setenv("ONTOFORGE_LOCAL_STORE_MAX_TRIPLES", "4000")
    r = client.post(f"/api/projects/{pid}/store/load", data={"sample": "demo"})
    assert r.status_code == 413 and "Plafond" in r.json()["detail"]
    monkeypatch.setenv("ONTOFORGE_LOCAL_STORE_MAX_TRIPLES", "1000000")
    monkeypatch.setenv("ONTOFORGE_LOCAL_STORE_MAX_UPLOAD_MB", "1")
    big = b"# " + b"x" * (1024 * 1024 + 10)
    assert client.post(f"/api/projects/{pid}/store/load", files={"file": ("big.ttl", big)}).status_code == 413
    monkeypatch.setenv("ONTOFORGE_LOCAL_STORE_MAX_INFERENCE_TRIPLES", "100")
    r = client.post(f"/api/projects/{pid}/store/load", data={"sample": "demo", "inference": "rdfs"})
    assert r.status_code == 413 and "Inférence limitée" in r.json()["detail"]


def test_shacl_validation_of_store(client, pid):
    base = client.post(f"/api/projects/{pid}/store/validate", json={})
    assert base.status_code == 200 and base.json()["validated_triples"] > 0  # individus du projet seuls
    load_demo(client, pid)
    rep = client.post(f"/api/projects/{pid}/store/validate", json={}).json()
    assert rep["validated_triples"] > 4000 and rep["conforms"] is True, rep
    # un véhicule sans VIN (obligatoire) ne se conforme plus
    up(client, pid, "mauvais.ttl", f"@prefix am: <{AM}> . am:veh_sans_vin a am:Vehicle .")
    rep = client.post(f"/api/projects/{pid}/store/validate", json={}).json()
    assert rep["conforms"] is False and rep["results"]


def test_options_local_adds_values_from_store(client, pid):
    up(client, pid, "regs.ttl", f'@prefix am: <{AM}> . am:veh_zz a am:Vehicle ; am:registrationNumber "ZZ-123-ZZ" .')
    base = client.get(f"/api/projects/{pid}/query/options", params={"class": AM + "Vehicle", "property": AM + "registrationNumber"}).json()
    assert "local" not in base and "ZZ-123-ZZ" not in {v["value"] for v in base["values"]}
    js = client.get(f"/api/projects/{pid}/query/options", params={"class": AM + "Vehicle", "property": AM + "registrationNumber", "local": "true"}).json()
    assert js["local"]["added"] >= 1 and js["local"]["triples"] > 0
    assert any(v["value"] == "ZZ-123-ZZ" and v["source"] == "local" for v in js["values"])


def test_values_autocomplete_on_local(client, pid):
    load_demo(client, pid)
    r = client.post(f"/api/projects/{pid}/query/values", json={"class": AM + "Vehicle", "property": AM + "registrationNumber", "q": "NF-", "endpoint": LOCAL})
    assert r.status_code == 200 and any(v["value"] == "NF-982-XB" for v in r.json()["values"])


def test_inline_remote_endpoint_still_works_next_to_local(client, pid):
    r = client.post(f"/api/projects/{pid}/query/run", json={"sparql": "ASK {}", "endpoint": {"url": "notaurl"}})
    assert r.status_code == 422  # l'endpoint temporaire distant garde sa validation propre
    assert client.post(f"/api/projects/{pid}/query/run", json={"sparql": "ASK {}", "endpoint": {"kind": "inconnu"}}).status_code == 422
