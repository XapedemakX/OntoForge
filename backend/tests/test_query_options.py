"""L17 — valeurs possibles sans endpoint, endpoint temporaire en ligne (garde-fous identiques, secret jamais renvoyé)."""
import httpx
import pytest
import rdflib
from fastapi.testclient import TestClient

from ontoforge.core.onto_model import DataRange, DatatypeProperty, LiteralValue, OntClass, OntologyMeta, OntoModel
from ontoforge.core.pg_model import NodeType, PGModel, PGProperty
from ontoforge.core.shapes_model import NodeShape, Path, PropertyShape, ShapesModel, Targets
from ontoforge.main import app
from ontoforge.queries import endpoint as ep_mod, options

AM = "https://w3id.org/ontoforge/automaint#"
SECRET = "tok-INLINE-SECRET-987654"
INLINE = {"url": "http://temp.test/sparql", "auth": "bearer", "secret": SECRET}


@pytest.fixture
def client(tmp_path, monkeypatch, samples_dir):
    monkeypatch.setenv("ONTOFORGE_DATA", str(tmp_path))
    monkeypatch.setenv("ONTOFORGE_SECRET_KEY", "master-test-key")
    g = rdflib.Graph()
    g.parse(samples_dir / "automaint" / "automaint-data.ttl")
    g.parse(samples_dir / "automaint" / "automaint.ttl")
    seen = []

    def handler(req: httpx.Request) -> httpx.Response:
        from urllib.parse import unquote_plus
        seen.append(req)
        form = dict(x.split("=", 1) for x in req.content.decode().split("&"))
        return httpx.Response(200, content=g.query(unquote_plus(form["query"])).serialize(format="json"),
                              headers={"content-type": "application/sparql-results+json"})

    monkeypatch.setattr(ep_mod, "make_client", lambda timeout: httpx.Client(transport=httpx.MockTransport(handler), timeout=timeout))
    c = TestClient(app)
    c.seen = seen
    return c


@pytest.fixture
def pid(client):
    r = client.post("/api/projects", json={"name": "AM", "sample": "automaint"})
    assert r.status_code in (200, 201), r.text
    return r.json()["id"]


def test_options_enum_class_without_endpoint(client, pid):
    r = client.get(f"/api/projects/{pid}/query/options", params={"class": AM + "FuelType", "lang": "fr"})
    assert r.status_code == 200, r.text
    js = r.json()
    assert js["enumerated"] is True and js["known_count"] == 4
    assert {v["label"] for v in js["values"]} >= {"Diesel", "Électrique"} or len(js["values"]) == 4
    assert all(v["is_iri"] and v["value"].startswith(AM) for v in js["values"])
    assert not client.seen  # aucun appel réseau


def test_options_object_property_uses_range(client, pid):
    js = client.get(f"/api/projects/{pid}/query/options", params={"class": AM + "Engine", "property": AM + "usesFuel"}).json()
    assert js["kind"] == "object" and js["known_count"] == 4
    assert client.get(f"/api/projects/{pid}/query/options", params={"class": AM + "FuelType", "q": "dies"}).json()["known_count"] == 1


def test_options_validation(client, pid):
    assert client.get(f"/api/projects/{pid}/query/options").status_code == 422
    assert client.get(f"/api/projects/{pid}/query/options", params={"class": AM + "Nope"}).status_code == 404


def test_suggest_and_roots_carry_known_counts(client, pid):
    roots = client.get(f"/api/projects/{pid}/query/suggest").json()["classes"]
    assert next(c for c in roots if c["iri"] == AM + "FuelType")["known"] == 4
    eng = client.get(f"/api/projects/{pid}/query/suggest", params={"class": AM + "Engine"}).json()
    tg = next(o for o in eng["outgoing"] if o["iri"] == AM + "usesFuel")["targets"]
    assert tg[0]["known"] == 4


def test_data_values_sources():
    o = OntoModel(meta=OntologyMeta(iri="http://x/o"), classes={"http://x/C": OntClass(iri="http://x/C")},
                  datatype_properties={"http://x/p": DatatypeProperty(iri="http://x/p", domain=["http://x/C"],
                                                                      range_expr=DataRange(one_of=[LiteralValue(value="rouge"), LiteralValue(value="bleu")])),
                                       "http://x/q": DatatypeProperty(iri="http://x/q", domain=["http://x/C"])})
    ps = PropertyShape(id="s1", path=Path(kind="predicate", iri="http://x/q"), **{"in": [LiteralValue(value="A"), LiteralValue(value="B")]})
    sh = ShapesModel(shapes={"S": NodeShape(id="S", targets=Targets(target_class=["http://x/C"]), properties=[ps])})
    pg = PGModel(target="neo4j", node_types={"C": NodeType(name="C", source=["http://x/C"], properties=[PGProperty(name="z", source="http://x/z", enum=["u", "v"])])})
    assert [v["value"] for v in options.data_values(o, None, None, "http://x/C", "http://x/p")] == ["rouge", "bleu"]
    assert [v["value"] for v in options.data_values(o, sh, None, "http://x/C", "http://x/q")] == ["A", "B"]
    assert [v["source"] for v in options.data_values(o, sh, None, "http://x/C", "http://x/q")] == ["sh:in", "sh:in"]
    assert [v["value"] for v in options.data_values(o, None, pg, "http://x/C", "http://x/z")] == ["u", "v"]


def test_inline_endpoint_run_values_and_guards(client, pid):
    base = f"/api/projects/{pid}"
    r = client.post(base + "/query/run", json={"sparql": f"SELECT ?s WHERE {{ ?s a <{AM}Vehicle> }}", "endpoint": INLINE, "limit": 5})
    assert r.status_code == 200, r.text
    assert SECRET not in r.text and r.json()["endpoint_id"] == "temporaire"
    assert client.seen[-1].headers["authorization"] == f"Bearer {SECRET}"
    assert client.post(base + "/query/run", json={"sparql": "DELETE WHERE { ?s ?p ?o }", "endpoint": INLINE}).status_code == 403
    assert client.post(base + "/query/run", json={"sparql": "ASK {}", "endpoint": {"url": "ftp://x"}}).status_code == 422
    v = client.post(base + "/query/values", json={"class": AM + "Engine", "property": AM + "usesFuel", "endpoint": INLINE})
    assert v.status_code == 200 and SECRET not in v.text
    t = client.post(base + "/query/endpoint-test", json=INLINE)
    assert t.status_code == 200 and t.json()["ok"] is True and SECRET not in t.text
    # rien n'est persisté dans les paramètres
    assert client.get("/api/settings/endpoints").json()["endpoints"] == []
    assert SECRET not in client.get("/api/settings").text


def test_options_label_property_proposes_individual_labels(client, pid):
    js = client.get(f"/api/projects/{pid}/query/options", params={"class": AM + "FuelType", "property": "http://www.w3.org/2000/01/rdf-schema#label"}).json()
    assert js["kind"] == "label" and {"Diesel", "Électricité"} <= {v["value"] for v in js["values"]} and not any(v["is_iri"] for v in js["values"])
