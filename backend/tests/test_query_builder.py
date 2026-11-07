"""L15 — requêtage guidé : suggestions, génération, exécution (endpoint rdflib simulé), refus UPDATE, secrets, sauvegardes."""
import json

import httpx
import pytest
import rdflib
from fastapi.testclient import TestClient
from rdflib.plugins.sparql import prepareQuery

from ontoforge.main import app
from ontoforge.queries import builder, endpoint as ep_mod
from ontoforge.queries.builder import GuidedQuery

AM = "https://w3id.org/ontoforge/automaint#"
SECRET = "tok-SECRET-endpoint-123456"


@pytest.fixture
def data_graph(samples_dir):
    g = rdflib.Graph()
    g.parse(samples_dir / "automaint" / "automaint-data.ttl")
    return g


@pytest.fixture
def client(tmp_path, monkeypatch, data_graph):
    monkeypatch.setenv("ONTOFORGE_DATA", str(tmp_path))
    monkeypatch.setenv("ONTOFORGE_SECRET_KEY", "master-test-key")
    seen = []

    def handler(req: httpx.Request) -> httpx.Response:
        seen.append(req)
        form = dict(x.split("=", 1) for x in req.content.decode().split("&"))
        from urllib.parse import unquote_plus
        q = unquote_plus(form["query"])
        r = data_graph.query(q)
        return httpx.Response(200, content=r.serialize(format="json"), headers={"content-type": "application/sparql-results+json"})

    monkeypatch.setattr(ep_mod, "make_client", lambda timeout: httpx.Client(transport=httpx.MockTransport(handler), timeout=timeout))
    c = TestClient(app)
    c.requests_seen = seen
    return c


@pytest.fixture
def pid(client):
    r = client.post("/api/projects", json={"name": "AM", "sample": "automaint"})
    assert r.status_code in (200, 201), r.text
    return r.json()["id"]


@pytest.fixture
def endpoint(client):
    r = client.post("/api/settings/endpoints", json={"name": "Local", "url": "http://sparql.test/query", "auth": "bearer", "secret": SECRET})
    assert r.status_code == 201, r.text
    return r.json()


def guided_repair():
    return GuidedQuery.model_validate({
        "root": {"var": "ro", "class_iri": AM + "RepairOrder"},
        "steps": [{"from_var": "ro", "property_iri": AM + "concerns", "to_var": "v", "to_class_iri": AM + "Vehicle"}],
        "filters": [{"var": "v", "kind": "text_contains", "property_iri": AM + "vin", "value": "abc"}],
        "select": [{"var": "ro", "property_iri": AM + "orderNumber"}, {"var": "v", "property_iri": AM + "vin"}],
        "order_by": [{"var": "v", "property_iri": AM + "vin"}], "limit": 50})


def test_sparql_parses_and_runs_locally(data_graph, samples_dir):
    from ontoforge.io.rdf_import import parse_ontology
    onto, _ = parse_ontology((samples_dir / "automaint" / "automaint.ttl").read_text(), filename="a.ttl")
    sp = builder.to_sparql(guided_repair(), onto)
    prepareQuery(sp)
    assert "PREFIX am:" in sp and "am:concerns" in sp and "LIMIT 50" in sp
    q = GuidedQuery.model_validate({"root": {"var": "v", "class_iri": AM + "Vehicle"}, "steps": [
        {"from_var": "v", "property_iri": AM + "ofModel", "to_var": "m", "to_class_iri": AM + "VehicleModel"}],
        "filters": [{"var": "v", "kind": "text_contains", "property_iri": AM + "vin", "value": "abcdefgh1"}]})
    assert len(list(data_graph.query(builder.to_sparql(q, onto)))) == 2  # veh_ok et veh_bad_vin (veh_no_model exclu)


def test_all_filter_kinds_parse(samples_dir):
    from ontoforge.io.rdf_import import parse_ontology
    onto, _ = parse_ontology((samples_dir / "automaint" / "automaint.ttl").read_text(), filename="a.ttl")
    base = {"root": {"var": "x", "class_iri": AM + "RepairOrder"}}
    fl = [{"kind": "equals", "property_iri": AM + "orderNumber", "value": "O1"},
          {"kind": "regex", "property_iri": AM + "orderNumber", "value": "^O"},
          {"kind": "lang", "property_iri": AM + "orderNumber", "lang": "fr"},
          {"kind": "date_range", "property_iri": AM + "openedAt", "value": "2024-01-01", "value2": "2024-12-31"},
          {"kind": "in_values", "property_iri": AM + "orderNumber", "values": ["a", "b"]},
          {"kind": "number_range", "property_iri": AM + "orderNumber", "value": 1, "value2": 5, "negate": True}]
    for f in fl:
        q = GuidedQuery.model_validate({**base, "filters": [{"var": "x", **f}]})
        prepareQuery(builder.to_sparql(q, onto))
    q = GuidedQuery.model_validate({**base, "steps": [
        {"from_var": "x", "property_iri": AM + "performedAt", "to_var": "g", "optional": True},
        {"from_var": "x", "property_iri": AM + "assignedTo", "to_var": "t", "negated": True},
        {"from_var": "x", "property_iri": AM + "hasRepairOrder", "inverse": True, "to_var": "w"}],
        "select": [{"var": "x", "label": True}, {"var": "g"}], "subclasses": True})
    prepareQuery(builder.to_sparql(q, onto))


def test_invalid_structure():
    with pytest.raises(builder.GuidedError):
        builder.to_sparql(GuidedQuery.model_validate({"root": {"var": "a"}, "steps": [
            {"from_var": "zz", "property_iri": AM + "x", "to_var": "b"}]}))


def test_suggest_class(client, pid):
    r = client.get(f"/api/projects/{pid}/query/suggest", params={"class": AM + "Vehicle"}).json()
    out = {e["iri"].split("#")[1]: e for e in r["outgoing"]}
    inc = {e["iri"].split("#")[1] for e in r["incoming"]}
    assert {"ofModel", "ownedBy", "hasEngine", "hasRepairOrder", "hasMileageReading", "hasActiveCode"} <= set(out)
    assert {"concerns", "readingOf", "installedIn", "covers"} <= inc
    assert "performedAt" not in out
    assert {t["iri"] for t in out["ofModel"]["targets"]} == {AM + "VehicleModel"}
    dp = {e["iri"].split("#")[-1]: e for e in r["data_properties"]}
    assert dp["vin"]["value_kind"] == "text" and "text_contains" in dp["vin"]["filter_kinds"]
    assert dp["firstRegistrationDate"]["filter_kinds"][0] == "date_range" and "label" in dp
    # héritage : un sous-type d'Engine hérite des propriétés d'Engine
    sub = client.get(f"/api/projects/{pid}/query/suggest", params={"class": AM + "ElectricMotor"}).json()
    assert "usesFuel" in {e["iri"].split("#")[1] for e in sub["outgoing"]}
    assert next(e for e in sub["outgoing"] if e["iri"].endswith("usesFuel"))["inherited_from"] == AM + "Engine"
    # Party : sous-classes comprises dans les cibles de portée
    assert client.get(f"/api/projects/{pid}/query/suggest", params={"class": AM + "Nope"}).status_code == 404


def test_suggest_targets(client, pid):
    r = client.get(f"/api/projects/{pid}/query/suggest", params={"property": AM + "worksAt", "from": AM + "Technician"}).json()
    assert {t["iri"] for t in r["targets"]} == {AM + "Garage"} and r["restricted"]
    r = client.get(f"/api/projects/{pid}/query/suggest", params={"property": AM + "madeBy", "inverse": "true"}).json()
    assert {t["iri"] for t in r["targets"]} == {AM + "VehicleModel"}


def test_build_all_targets(client, pid):
    for tgt in ("neo4j", "curiosity"):
        r = client.post(f"/api/projects/{pid}/query/build", json={"guided": guided_repair().model_dump(mode="json"), "target": tgt})
        assert r.status_code == 200, r.text
        b = r.json()
        prepareQuery(b["sparql"])
        assert b["cypher"] and "MATCH" in b["cypher"] and b["supported"]
        assert b["curiosity"] is not None
    bad = client.post(f"/api/projects/{pid}/query/build", json={"guided": {"root": {"var": "a"}, "steps": [
        {"from_var": "q", "property_iri": AM + "x", "to_var": "b"}]}})
    assert bad.status_code == 422


def test_run_on_local_endpoint(client, pid, endpoint):
    r = client.post(f"/api/projects/{pid}/query/run", json={"guided": {
        "root": {"var": "v", "class_iri": AM + "Vehicle"},
        "steps": [{"from_var": "v", "property_iri": AM + "ofModel", "to_var": "m"}],
        "select": [{"var": "v"}, {"var": "v", "property_iri": AM + "vin"}, {"var": "m"}], "limit": 10}, "limit": 10})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["columns"] == ["v", "v_vin", "m"] and len(d["rows"]) == 2 and not d["truncated"]
    assert {n["id"] for n in d["graph"]["nodes"]} >= {AM + "veh_ok", AM + "model_alpha_city"}
    assert d["graph"]["edges"] and d["graph"]["edges"][0]["iri"] == AM + "ofModel"
    sent = client.requests_seen[-1]
    assert sent.headers["authorization"] == "Bearer " + SECRET  # secret transmis à l'endpoint, jamais renvoyé au client
    assert SECRET not in r.text


def test_run_truncation_and_forced_limit(client, pid, endpoint):
    r = client.post(f"/api/projects/{pid}/query/run", json={"sparql": f"SELECT ?s WHERE {{ ?s a <{AM}Vehicle> }}", "limit": 2}).json()
    assert len(r["rows"]) == 2 and r["truncated"] and r["sparql"].rstrip().endswith("LIMIT 3")
    big = client.post(f"/api/projects/{pid}/query/run", json={"sparql": f"SELECT ?s WHERE {{ ?s ?p ?o }} LIMIT 99999", "limit": 5}).json()
    assert len(big["rows"]) == 5 and big["truncated"] and "LIMIT 6" in big["sparql"]
    assert ep_mod.force_limit("SELECT * WHERE { { SELECT ?a WHERE {?a ?b ?c} LIMIT 1 } }", 10)[1] is None


def test_refuse_update(client, pid, endpoint):
    for q in ("INSERT DATA { <urn:a> <urn:b> <urn:c> }", "DELETE WHERE { ?s ?p ?o }", "CLEAR ALL", "DROP GRAPH <urn:g>"):
        r = client.post(f"/api/projects/{pid}/query/run", json={"sparql": q})
        assert r.status_code == 403 and "UPDATE" in r.json()["detail"], q
    assert client.requests_seen == []  # rien n'est parti vers l'endpoint
    assert client.post(f"/api/projects/{pid}/query/run", json={"sparql": "SELEC nope"}).status_code == 422
    assert client.post(f"/api/projects/{pid}/query/run", json={"sparql": "ASK { ?s ?p ?o }"}).json()["boolean"] is True


def test_no_active_endpoint(client, pid):
    assert client.post(f"/api/projects/{pid}/query/run", json={"sparql": "ASK {}"}).status_code == 409


def test_values_autocomplete(client, pid, endpoint):
    r = client.get(f"/api/projects/{pid}/query/values", params={"class": AM + "Vehicle", "property": AM + "vin", "q": "12o"}).json()
    assert [v["value"] for v in r["values"]] == ["VF1ABCDEFGH12O456"] and not r["values"][0]["is_iri"]
    r = client.get(f"/api/projects/{pid}/query/values", params={"class": AM + "Garage", "q": "nord"}).json()
    assert r["values"][0]["is_iri"] and r["values"][0]["label"] == "Garage Nord"


def test_endpoints_crud_and_secret_encrypted(client, tmp_path, endpoint):
    assert endpoint["has_secret"] and "secret" not in endpoint and SECRET not in json.dumps(endpoint)
    raw = (tmp_path / "settings.json").read_text()
    assert SECRET not in raw and "secret_enc" in raw and "enc:v1:" in raw
    s = client.get("/api/settings").json()
    assert s["active_endpoint_id"] == endpoint["id"] and SECRET not in json.dumps(s)
    two = client.post("/api/settings/endpoints", json={"name": "Autre", "url": "http://x.test/sparql", "timeout_s": 5}).json()
    assert client.put("/api/settings/endpoints/active", json={"id": two["id"]}).json()["active_endpoint_id"] == two["id"]
    assert client.put("/api/settings/endpoints/active", json={"id": "nope"}).status_code == 404
    up = client.put(f"/api/settings/endpoints/{endpoint['id']}", json={"name": "Renommé"}).json()
    assert up["name"] == "Renommé" and up["has_secret"]  # secret conservé
    t = client.post(f"/api/settings/endpoints/{endpoint['id']}/test").json()
    assert t["ok"] is True
    assert client.post("/api/settings/endpoints", json={"name": "Z", "url": "ftp://x"}).status_code == 422
    d = client.delete(f"/api/settings/endpoints/{two['id']}").json()
    assert d["deleted"] == two["id"]
    assert [e["id"] for e in client.get("/api/settings/endpoints").json()["endpoints"]] == [endpoint["id"]]


def test_legacy_endpoint_migration(tmp_path, monkeypatch):
    monkeypatch.setenv("ONTOFORGE_DATA", str(tmp_path))
    monkeypatch.setenv("ONTOFORGE_SECRET_KEY", "k")
    from ontoforge.settings import store
    s = store.load()
    s.sparql_endpoint.url = "http://old.test/sparql"
    store.save(s)
    s2 = store.load()
    assert [e.id for e in s2.sparql_endpoints] == ["default"] and s2.active_endpoint_id == "default"
    assert s2.active_endpoint().url == "http://old.test/sparql"


def test_saved_queries_crud(client, pid):
    base = f"/api/projects/{pid}/queries/saved"
    body = {"name": "OR par véhicule", "description": "d", "guided": guided_repair().model_dump(mode="json")}
    c = client.post(base, json=body)
    assert c.status_code == 201
    qid = c.json()["id"]
    assert client.get(base).json()[0]["name"] == "OR par véhicule"
    u = client.put(f"{base}/{qid}", json={**body, "name": "Autre"}).json()
    assert u["name"] == "Autre" and u["created_at"] == c.json()["created_at"]
    assert client.post(base, json={"name": "x"}).status_code == 422
    assert client.delete(f"{base}/{qid}").json() == {"deleted": qid}
    assert client.get(f"{base}/{qid}").status_code == 404


def test_competency_become_guided(client, pid):
    r = client.get(f"/api/projects/{pid}/queries/competency/guided", params={"target": "neo4j"}).json()
    ok = [x for x in r if x["guided"]]
    assert len(ok) >= 4
    for x in ok:
        prepareQuery(builder.to_sparql(GuidedQuery.model_validate(x["guided"])))
    assert any(not x["guided"] and x["reason"] for x in r)  # comptage / transitif : expliqué


# ---- L15 : langage naturel ---------------------------------------------------------------------

QUESTIONS = {
    "quels véhicules ont eu une réparation par le technicien Martin ?": "Technician",
    "liste des garages à Toulouse": "Garage",
    "ordres de réparation ouverts après le 1er octobre": "RepairOrder",
}


@pytest.mark.parametrize("question", list(QUESTIONS))
def test_nl_mock_deterministic(client, pid, question):
    r = client.post(f"/api/projects/{pid}/query/nl", json={"question": question, "provider_id": "mock"})
    assert r.status_code == 200, r.text
    d = r.json()
    g = GuidedQuery.model_validate(d["guided"])
    prepareQuery(d["sparql"])
    assert d["mode"] == "deterministic" and d["unmatched"] == [] and d["confidence"] > 0.5
    assert d["cypher"] and AM + QUESTIONS[question] in {g.root.class_iri, *[s.to_class_iri for s in g.steps]}


def test_nl_paths_and_filters(client, pid):
    def ask(q):
        return client.post(f"/api/projects/{pid}/query/nl", json={"question": q}).json()
    g = ask("quels véhicules ont eu une réparation par le technicien Martin ?")["guided"]
    assert g["root"]["class_iri"] == AM + "Vehicle"
    assert [(s["property_iri"].split("#")[1], s["inverse"]) for s in g["steps"]] == [("hasRepairOrder", False), ("assignedTo", False)]
    assert g["filters"][0]["kind"] == "text_contains" and g["filters"][0]["value"] == "Martin"
    g = ask("ordres de réparation ouverts après le 1er octobre 2025")["guided"]
    f = g["filters"][0]
    assert f["kind"] == "date_range" and f["property_iri"] == AM + "openedAt" and f["value"] == "2025-10-01" and not f["value2"]
    g = ask("garages sans technicien")["guided"]
    assert g["root"]["class_iri"] == AM + "Garage" and g["steps"][0]["negated"] and g["steps"][0]["inverse"]
    d = ask("blabla zorglub")
    assert d["confidence"] == 0 and d["unmatched"]
    assert client.post(f"/api/projects/{pid}/query/nl", json={"question": "x", "provider_id": "nope"}).status_code == 404
    assert client.post(f"/api/projects/{pid}/query/nl", json={"question": "  "}).status_code == 422


def test_nl_llm_validation(client, pid, monkeypatch):
    """Un LLM qui invente une relation, inverse un sens et cite une classe invalide : correction ou retrait, mention dans unmatched."""
    import ontoforge.assistant.providers as prov

    class Fake:
        name, model, configured = "fake", "fake", True
        calls = []

        def complete(self, system, messages, max_tokens=0, json_schema=None):
            Fake.calls.append((system, messages[-1]["content"]))
            return json.dumps({"explanation": "ok", "guided": {
                "root": {"var": "g", "class_iri": "Garage"},
                "steps": [{"from_var": "g", "property_iri": "worksAt", "inverse": False, "to_var": "t", "to_class_iri": "Technician"},
                          {"from_var": "g", "property_iri": "flyingTo", "to_var": "z"},
                          {"from_var": "t", "property_iri": "assignedTo", "to_var": "w", "to_class_iri": "Vehicle"}],
                "filters": [{"var": "t", "kind": "equals", "property_iri": "nope", "value": "x"}],
                "select": [{"var": "t", "property_iri": "displayName"}]}})

    monkeypatch.setattr(prov, "get_provider", lambda pid=None: Fake())
    d = client.post(f"/api/projects/{pid}/query/nl", json={"question": "garages et techniciens"}).json()
    assert d["mode"] == "llm" and d["provider"] == "fake"
    st = d["guided"]["steps"]
    assert len(st) == 2 and st[0]["inverse"] is True  # worksAt corrigé (Technician -> Garage, donc sens inverse depuis Garage)
    assert "flyingTo" in d["unmatched"] and "nope" in d["unmatched"]
    assert d["guided"]["filters"] == [] and d["guided"]["select"][0]["property_iri"] == AM + "displayName"
    prepareQuery(d["sparql"])
    assert "SCHÉMA" in Fake.calls[0][1] and "worksAt" in Fake.calls[0][1] and "[TASK:nl]" in Fake.calls[0][0]


def test_nl_llm_garbage_falls_back(client, pid, monkeypatch):
    import ontoforge.assistant.providers as prov

    class Bad:
        name, model, configured = "bad", "bad", True

        def complete(self, *a, **k):
            return "pas du json"

    monkeypatch.setattr(prov, "get_provider", lambda pid=None: Bad())
    d = client.post(f"/api/projects/{pid}/query/nl", json={"question": "liste des garages"}).json()
    assert d["mode"] == "deterministic" and "LLM" in d["explanation"] and d["guided"]["root"]["class_iri"] == AM + "Garage"


# ---- L15 : corrections de la revue W3C it1 -----------------------------------------------------

import re as _re  # noqa: E402

from ontoforge.core.onto_model import ObjectProperty, OntClass, OntoModel, OntologyMeta  # noqa: E402
from ontoforge.queries import nl  # noqa: E402


def strict(sparql: str) -> None:
    """Analyse stricte : tout nom préfixé du corps doit être déclaré par un PREFIX (comme Fuseki), puis rdflib."""
    head = dict(_re.findall(r"PREFIX\s+(\w*):\s*<([^>]*)>", sparql))
    body = sparql[sparql.index("SELECT"):]
    body = _re.sub(r'"(?:[^"\\]|\\.)*"(?:\^\^<[^>]*>|@[\w-]+)?', '""', body)
    body = _re.sub(r"<[^>]*>", "<>", body)
    for pfx in _re.findall(r"(?<![\w?:<])([A-Za-z][\w-]*)?:[A-Za-z_][\w-]*", body):
        assert pfx in head, f"préfixe non déclaré « {pfx} » dans :\n{sparql}"
    from rdflib.plugins.sparql import parser, algebra
    algebra.translateQuery(parser.parseQuery(sparql), initNs={})  # aucun espace de noms prédéfini


@pytest.fixture
def onto(samples_dir):
    from ontoforge.io.rdf_import import parse_ontology
    return parse_ontology((samples_dir / "automaint" / "automaint.ttl").read_text(), filename="a.ttl")[0]


def test_w3c_prefixes_declared(onto):
    q = GuidedQuery.model_validate({"root": {"var": "v", "class_iri": AM + "Vehicle"}, "subclasses": True,
                                    "select": [{"var": "v", "label": True}], "label_lang": "fr"})
    sp = builder.to_sparql(q, onto, {})
    assert "PREFIX rdf:" in sp and "PREFIX rdfs:" in sp
    strict(sp)


def test_w3c_optional_scoping(onto, data_graph):
    q = GuidedQuery.model_validate({
        "root": {"var": "ro", "class_iri": AM + "RepairOrder"},
        "steps": [{"from_var": "ro", "property_iri": AM + "performedAt", "to_var": "g", "to_class_iri": AM + "Garage", "optional": True},
                  {"from_var": "g", "property_iri": AM + "worksAt", "inverse": True, "to_var": "t"}],
        "filters": [{"var": "g", "kind": "text_contains", "property_iri": AM + "displayName", "value": "nord"}],
        "select": [{"var": "ro"}, {"var": "g"}, {"var": "t"}]})
    sp = builder.to_sparql(q, onto)
    strict(sp)
    opt = sp[sp.index("OPTIONAL"):]
    assert "displayName" in opt and "worksAt" in opt and sp.count("OPTIONAL") == 1  # tout dépend de ?g : dans l'OPTIONAL
    rows = list(data_graph.query(sp))
    assert {str(r.ro).split("#")[1] for r in rows} == {"ro_ok", "ro_no_garage"}  # jointure gauche, pas de produit cartésien


def test_w3c_injection_refused(onto, client, pid):
    bad = [{"kind": "equals", "is_iri": True, "value": "x> . ?s ?p ?o } #"},
           {"kind": "equals", "value": "a", "lang": "fr) } UNION { ?s ?p ?o"},
           {"kind": "date_range", "value": "2024-01-01", "datatype": "http://x/> } #"},
           {"kind": "in_values", "is_iri": True, "values": ["http://ok/a", "b c"]}]
    for f in bad:
        q = GuidedQuery.model_validate({"root": {"var": "v", "class_iri": AM + "Vehicle"}, "filters": [{"var": "v", **f}]})
        with pytest.raises(builder.GuidedError):
            builder.to_sparql(q, onto)
    r = client.post(f"/api/projects/{pid}/query/build", json={"guided": {"root": {"var": "v"}, "filters": [{"var": "v", **bad[0]}]}})
    assert r.status_code == 422
    # littéraux : guillemets, retours à la ligne et accolades restent dans la chaîne
    q = GuidedQuery.model_validate({"root": {"var": "v", "class_iri": AM + "Vehicle"}, "filters": [
        {"var": "v", "kind": "equals", "property_iri": AM + "vin", "value": 'a") } UNION { ?s ?p ?o #\n\x01'}]})
    sp = builder.to_sparql(q, onto)
    strict(sp)
    assert sp.count("UNION") == 1 and '\\"' in sp and "\\u0001" in sp


def test_w3c_sanitize_filters(onto):
    lookup = {local_name: iri for iri, local_name in ((AM + "Vehicle", "Vehicle"), (AM + "vin", "vin"))}
    base = {"root": {"var": "v", "class_iri": "Vehicle"}}
    cases = [{"kind": "equals", "is_iri": True, "value": "http://invented/X"},
             {"kind": "equals", "property_iri": "vin", "value": "a", "lang": "fr) } #"},
             {"kind": "date_range", "property_iri": "vin", "value": "2024-01-01", "datatype": "http://invented/dt"},
             {"kind": "equals", "property_iri": "vin", "value": {"a": 1}}]
    for f in cases:
        gq, unmatched, notes = nl.sanitize({**base, "filters": [{"var": "v", **f}]}, onto, None, lookup)
        assert gq is not None and gq.filters == [] and unmatched, f
    gq, _, _ = nl.sanitize({**base, "filters": [{"var": "v", "kind": "equals", "property_iri": "vin", "value": "x", "lang": "fr-CA",
                                                  "datatype": None}]}, onto, None, lookup)
    assert len(gq.filters) == 1


def test_w3c_negation_not_exists(onto, data_graph):
    q = GuidedQuery.model_validate({"root": {"var": "v", "class_iri": AM + "Vehicle"}, "filters": [
        {"var": "v", "kind": "text_contains", "property_iri": AM + "vin", "value": "12o", "negate": True}]})
    sp = builder.to_sparql(q, onto)
    strict(sp)
    assert "FILTER NOT EXISTS" in sp and "!(" not in sp
    assert {str(r.v).split("#")[1] for r in data_graph.query(sp)} == {"veh_ok", "veh_no_model"}


def test_w3c_equals_langstring_and_dates(onto):
    g = rdflib.Graph()
    g.add((rdflib.URIRef(AM + "g1"), rdflib.RDF.type, rdflib.URIRef(AM + "Garage")))
    g.add((rdflib.URIRef(AM + "g1"), rdflib.URIRef(AM + "displayName"), rdflib.Literal("Clio", lang="fr")))
    q = GuidedQuery.model_validate({"root": {"var": "g", "class_iri": AM + "Garage"}, "filters": [
        {"var": "g", "kind": "equals", "property_iri": AM + "displayName", "value": "Clio"}]})
    sp = builder.to_sparql(q, onto)
    strict(sp)
    assert len(list(g.query(sp))) == 1 and "STR(" in sp
    def dated(rng, **kw):
        o = onto.model_copy(deep=True)
        o.datatype_properties[AM + "openedAt"].range = [rng]
        f = {"var": "r", "kind": "date_range", "property_iri": AM + "openedAt", "value": "2024-03-05T10:00:00", "value2": "2024-12-31", **kw}
        sp = builder.to_sparql(GuidedQuery.model_validate({"root": {"var": "r", "class_iri": AM + "RepairOrder"}, "filters": [f]}), o)
        strict(sp)
        return sp
    assert '"2024-03-05T10:00:00"^^xsd:dateTime' in dated("http://www.w3.org/2001/XMLSchema#dateTimeStamp")
    assert '"2024"^^xsd:gYear' in dated("http://www.w3.org/2001/XMLSchema#gYear")
    assert '"2024-12-31"^^xsd:date' in dated("http://www.w3.org/2001/XMLSchema#date")
    assert '"2024-12-31T23:59:59"^^xsd:dateTime' in dated("http://www.w3.org/2001/XMLSchema#dateTime")


def test_w3c_domain_on_superproperty_chain():
    n = "urn:t#"
    o = OntoModel(meta=OntologyMeta(iri=n), classes={n + c: OntClass(iri=n + c) for c in "ABT"},
                  object_properties={n + "p1": ObjectProperty(iri=n + "p1", domain=[n + "A"], range=[n + "T"]),
                                     n + "p2": ObjectProperty(iri=n + "p2", domain=[n + "B"], range=[n + "T"], sub_property_of=[n + "p1"])})
    sg = builder.Suggester(o)
    assert sg.applies(n + "p2", n + "A") is False and sg.applies(n + "p2", n + "B") is False  # dom(p2) ⊑ A ET ⊑ B
    o.classes[n + "B"].sub_class_of = [n + "A"]
    assert builder.Suggester(o).applies(n + "p2", n + "B") is True
