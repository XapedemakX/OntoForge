"""L39-secu : parseurs RDF durcis (SEC-04 entités XML, SEC-05 sh:pattern, SEC-06 canonisation, SEC-07 contexte JSON-LD distant).

Tests de non-régression : chaque fichier de test est minuscule ; ce qui est vérifié est le REFUS (ou la borne), pas une charge.
"""
import http.server
import threading
import time

import pytest
from fastapi.testclient import TestClient

from ontoforge.io import safe_parse
from ontoforge.io.rdf_import import RdfImportError, parse_ontology

RDFXML = """<?xml version="1.0"?>
<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#" xmlns:owl="http://www.w3.org/2002/07/owl#"
         xmlns:rdfs="http://www.w3.org/2000/01/rdf-schema#">
  <owl:Class rdf:about="http://ex.org/A"><rdfs:label>Alpha</rdfs:label></owl:Class>
</rdf:RDF>"""
WITH_ENTITIES = """<?xml version="1.0"?>
<!DOCTYPE rdf:RDF [<!ENTITY a "x"><!ENTITY b "&a;&a;"><!ENTITY c "&b;&b;">]>
<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#" xmlns:owl="http://www.w3.org/2002/07/owl#"
         xmlns:rdfs="http://www.w3.org/2000/01/rdf-schema#">
  <owl:Class rdf:about="http://ex.org/A"><rdfs:label>&c;</rdfs:label></owl:Class>
</rdf:RDF>"""
DOCTYPE_ONLY = RDFXML.replace("<rdf:RDF", "<!DOCTYPE rdf:RDF>\n<rdf:RDF", 1)


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("ONTOFORGE_DATA", str(tmp_path))
    monkeypatch.setenv("ONTOFORGE_SECRET_KEY", "k" * 40)
    from ontoforge.main import create_app
    return TestClient(create_app(), raise_server_exceptions=False)


def new_project(c) -> str:
    return c.post("/api/projects", json={"name": "sec"}).json()["id"]


def post_import(c, pid, name, content, kind="ontology"):
    return c.post(f"/api/projects/{pid}/import", files={"file": (name, content, "application/octet-stream")}, data={"kind": kind})


# ---- SEC-04 : entités XML -------------------------------------------------------------------------------------------
def test_sec04_xml_entities_and_doctype_refused_fast(client):
    pid = new_project(client)
    for doc in (WITH_ENTITIES, DOCTYPE_ONLY):
        t0 = time.perf_counter()
        r = post_import(client, pid, "x.owl", doc)
        assert r.status_code == 422, r.text
        assert "DOCTYPE" in r.json()["detail"] and time.perf_counter() - t0 < 1.0


def test_sec04_encoded_variants_refused():
    for enc in ("utf-16", "utf-16-le", "utf-8"):
        with pytest.raises(RdfImportError, match="DOCTYPE"):
            parse_ontology(WITH_ENTITIES.encode(enc), "xml")


def test_sec04_plain_rdfxml_still_imported(client):
    pid = new_project(client)
    r = post_import(client, pid, "x.owl", RDFXML)
    assert r.status_code == 200, r.text
    with pytest.raises(RdfImportError):
        parse_ontology(WITH_ENTITIES, "xml")
    assert len(parse_ontology(RDFXML, "xml")[0].classes) == 1


def test_sec04_shapes_and_validation_data_also_refuse_entities(client):
    from ontoforge.shacl.import_shapes import parse_shapes
    from ontoforge.shacl.validate import validate
    from ontoforge.core.shapes_model import ShapesModel
    with pytest.raises(safe_parse.UnsafeRdfError):
        parse_shapes(WITH_ENTITIES, "xml")
    rep = validate(WITH_ENTITIES, ShapesModel(), data_format="xml")
    assert rep.conforms is False and any("DOCTYPE" in w for w in rep.warnings)


# ---- SEC-07 : contexte JSON-LD distant ------------------------------------------------------------------------------
class _Rec(http.server.BaseHTTPRequestHandler):
    hits: list = []

    def do_GET(self):
        _Rec.hits.append(self.path)
        out = b'{"@context": {"ex": "http://example.org/"}}'
        self.send_response(200)
        self.send_header("content-type", "application/ld+json")
        self.send_header("content-length", str(len(out)))
        self.end_headers()
        self.wfile.write(out)

    def log_message(self, *a):
        pass


@pytest.fixture
def recorder():
    _Rec.hits = []
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Rec)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield srv.server_address[1]
    srv.shutdown()


def test_sec07_remote_jsonld_context_refused_nothing_fetched(client, recorder):
    import json
    remote = json.dumps({"@context": f"http://127.0.0.1:{recorder}/c", "@id": "http://ex.org/a", "@type": "http://www.w3.org/2002/07/owl#Class"})
    nested = json.dumps({"@context": [{"ex": "http://ex.org/"}, f"http://127.0.0.1:{recorder}/c2"], "@graph": []})
    imp = json.dumps({"@context": {"@import": f"http://127.0.0.1:{recorder}/c3"}, "@graph": []})
    pid = new_project(client)
    for doc in (remote, nested, imp):
        assert post_import(client, pid, "x.jsonld", doc).status_code == 422
        assert post_import(client, pid, "x.jsonld", doc, kind="shapes").status_code == 422
        r = client.post(f"/api/projects/{pid}/shacl/validate", files={"file": ("d.jsonld", doc, "application/ld+json")})
        assert r.status_code == 200 and r.json()["conforms"] is False and "contexte" in " ".join(r.json()["warnings"])
    time.sleep(0.2)
    assert _Rec.hits == [], "le serveur a émis une requête pendant la lecture"


def test_sec07_inline_jsonld_context_still_imported(client):
    import json
    doc = json.dumps({"@context": {"owl": "http://www.w3.org/2002/07/owl#", "rdfs": "http://www.w3.org/2000/01/rdf-schema#"},
                      "@id": "http://ex.org/A", "@type": "owl:Class", "rdfs:label": "Alpha"})
    pid = new_project(client)
    assert post_import(client, pid, "x.jsonld", doc).status_code == 200


# ---- SEC-06 : canonisation plafonnée --------------------------------------------------------------------------------
def _list_ttl(n: int) -> str:
    return ("@prefix ex: <http://ex.org/> .\n@prefix owl: <http://www.w3.org/2002/07/owl#> .\nex:O a owl:Ontology .\n"
            "ex:Z ex:values ( " + " ".join("1" for _ in range(n)) + " ) .\n")


def test_sec06_huge_list_refused_fast_with_clear_message(client):
    pid = new_project(client)
    t0 = time.perf_counter()
    r = post_import(client, pid, "big.ttl", _list_ttl(20000))
    assert r.status_code == 422 and "triplets non reconnus" in r.json()["detail"], r.text[:300]
    assert time.perf_counter() - t0 < 5.0
    assert client.get("/api/health").status_code == 200


def test_sec06_long_list_over_canon_cap_imported_without_canonisation(client):
    pid = new_project(client)
    t0 = time.perf_counter()
    r = post_import(client, pid, "mid.ttl", _list_ttl(2500))
    assert r.status_code == 200, r.text[:300]
    assert time.perf_counter() - t0 < 5.0
    assert any("unmapped_not_canonical" in w for w in r.json().get("warnings", [])), r.json().get("warnings")


def test_sec06_small_graphs_still_canonical():
    import rdflib
    g = rdflib.Graph().parse(data="@prefix ex: <http://ex.org/> . ex:a ex:p ( 1 2 3 ) .", format="turtle")
    cg, canon = safe_parse.canonical_or_same(g)
    assert canon is True and len(cg) == len(g)
    big = rdflib.Graph()
    for i in range(safe_parse.max_canon_triples() + 1):
        big.add((rdflib.URIRef(f"http://ex.org/{i}"), rdflib.URIRef("http://ex.org/p"), rdflib.Literal(i)))
    assert safe_parse.canonical_or_same(big)[1] is False


# ---- SEC-05 : validation SHACL isolée ------------------------------------------------------------------------------
SHAPES_TTL = """@prefix sh: <http://www.w3.org/ns/shacl#> . @prefix ex: <http://ex.org/> . @prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
ex:S a sh:NodeShape ; sh:targetClass ex:T ; sh:property [ sh:path ex:code ; sh:pattern "%s" ] .
"""


def test_sec05_pathological_pattern_times_out_and_api_stays_responsive(client, monkeypatch):
    monkeypatch.setenv("ONTOFORGE_SHACL_TIMEOUT_S", "3")
    pid = new_project(client)
    assert post_import(client, pid, "s.ttl", SHAPES_TTL % "^(a+)+$", kind="shapes").status_code == 200
    data = "@prefix ex: <http://ex.org/> . ex:i a ex:T ; ex:code \"" + "a" * 40 + "!\" .\n"
    out = {}

    def run():
        t0 = time.perf_counter()
        out["r"] = client.post(f"/api/projects/{pid}/shacl/validate", files={"file": ("d.ttl", data, "text/turtle")})
        out["dt"] = time.perf_counter() - t0

    th = threading.Thread(target=run)
    th.start()
    time.sleep(0.8)
    t0 = time.perf_counter()
    assert client.get("/api/health").status_code == 200
    assert time.perf_counter() - t0 < 1.0, "l'API ne répond pas pendant la validation"
    th.join(30)
    assert out["dt"] < 20
    rep = out["r"].json()
    assert rep["conforms"] is False and any("interrompue" in w for w in rep["warnings"])


def test_sec05_normal_validation_unchanged(client):
    pid = new_project(client)
    assert post_import(client, pid, "s.ttl", SHAPES_TTL % "^[0-9]+$", kind="shapes").status_code == 200
    bad = "@prefix ex: <http://ex.org/> . ex:i a ex:T ; ex:code \"abc\" .\n"
    good = "@prefix ex: <http://ex.org/> . ex:i a ex:T ; ex:code \"123\" .\n"
    r = client.post(f"/api/projects/{pid}/shacl/validate", files={"file": ("d.ttl", bad, "text/turtle")}).json()
    assert r["conforms"] is False and len(r["results"]) == 1
    r = client.post(f"/api/projects/{pid}/shacl/validate", files={"file": ("d.ttl", good, "text/turtle")}).json()
    assert r["conforms"] is True
