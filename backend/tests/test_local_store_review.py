"""L19 — relecture croisée w3c + query (it1) : contournements de SERVICE, LOAD, limites (y compris CONSTRUCT / DESCRIBE),
union des graphes nommés et clauses FROM, format des résultats, inférence (bruit, nœuds anonymes, incohérences, sameAs),
JSON-LD à graphes nommés, contextes distants, persistance. Aucune dépendance réseau (serveur espion en boucle locale)."""
import http.server
import json
import threading

import pytest
from fastapi.testclient import TestClient

from ontoforge.localstore import runner
from ontoforge.main import app
from ontoforge.queries.endpoint import EndpointError

AM = "https://w3id.org/ontoforge/automaint#"
LOCAL = {"kind": "local"}
EX = "http://example.org/"


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
    yield f"http://127.0.0.1:{srv.server_port}", hits
    srv.shutdown()


def run(client, pid, sparql, **extra):
    return client.post(f"/api/projects/{pid}/query/run", json={"sparql": sparql, "endpoint": LOCAL, **extra})


def up(client, pid, name, text, **form):
    r = client.post(f"/api/projects/{pid}/store/load", files={"file": (name, text.encode("utf-8"))}, data=form)
    assert r.status_code == 200, r.text
    return r.json()


def count(client, pid, sparql):
    r = run(client, pid, sparql)
    assert r.status_code == 200, r.text
    return int(r.json()["rows"][0]["n"]["value"])


# ------------------------------------------------------------------------------------------- SERVICE

def service_variants(u: str) -> dict[str, str]:
    return {
        "casse": f"SELECT * WHERE {{ sErViCe <{u}/a> {{ ?s ?p ?o }} }}",
        "commentaire entre mot et IRI": f"SELECT * WHERE {{ SERVICE#x\n<{u}/b> {{ ?s ?p ?o }} }}",
        "après un point": f"SELECT * WHERE {{ ?s ?p ?o .SERVICE <{u}/m> {{ ?s ?p ?o }} }}",
        "variable": f"SELECT * WHERE {{ VALUES ?e {{ <{u}/c> }} SERVICE ?e {{ ?s ?p ?o }} }}",
        "nom préfixé": f"PREFIX r: <{u}/> SELECT * WHERE {{ SERVICE r:d {{ ?s ?p ?o }} }}",
        "sous-select": f"SELECT * WHERE {{ {{ SELECT ?s WHERE {{ SERVICE <{u}/e> {{ ?s ?p ?o }} }} }} }}",
        "FILTER EXISTS": f"SELECT * WHERE {{ ?s ?p ?o FILTER EXISTS {{ SERVICE <{u}/f> {{ ?s ?p ?o }} }} }}",
        "MINUS": f"SELECT * WHERE {{ ?s ?p ?o MINUS {{ SERVICE <{u}/g> {{ ?s ?p ?o }} }} }}",
        "CONSTRUCT": f"CONSTRUCT {{ ?s ?p ?o }} WHERE {{ SERVICE <{u}/h> {{ ?s ?p ?o }} }}",
        "ASK": f"ASK {{ SERVICE SILENT <{u}/i> {{ ?s ?p ?o }} }}",
        "DESCRIBE": f"DESCRIBE ?s WHERE {{ SERVICE <{u}/j> {{ ?s ?p ?o }} }}",
        # échappement \\u (SPARQL 1.1 §19.2) : invisible au filet lexical ; rdflib le développe, l'algèbre doit l'attraper
        "échappement unicode": f"SELECT * WHERE {{ \\u0053ERVICE <{u}/k> {{ ?s ?p ?o }} }}",
        # \\# dans un nom local (PN_LOCAL_ESC) : le filet lexical y voit un commentaire ; rdflib la refuse (422) — refusée quand même
        "nom local échappé": f"PREFIX ex: <{EX}> SELECT * WHERE {{ ?s ex:a\\#b ?o . SERVICE <{u}/l> {{ ?s ?p ?o }} }}",
    }


def test_service_bypass_attempts_all_refused_without_network(client, pid, spy):
    u, hits = spy
    for name, q in service_variants(u).items():
        r = run(client, pid, q)
        assert r.status_code in (403, 422), (name, r.status_code, r.text)
    assert hits == []


def test_service_algebra_net_catches_unicode_escape():
    """Revue it1 : le nœud d'algèbre rdflib s'appelle ServiceGraphPattern ; le test `== "Service"` ne trouvait jamais rien."""
    q = "SELECT * WHERE { \\u0053ERVICE <http://127.0.0.1:9/> { ?s ?p ?o } }"
    with pytest.raises(EndpointError) as exc:
        runner.guard(q)
    assert exc.value.status == 403


@pytest.mark.parametrize("q", ['SELECT * WHERE { ?s ?p "SERVICE <http://x> { }" }', f"SELECT * WHERE {{ ?s <{EX}SERVICE> ?o }}",
                               "SELECT * WHERE { ?s ?p ?o } # SERVICE <http://x>", "SELECT ?service WHERE { ?service ?p ?o }",
                               "PREFIX am: <http://e/> SELECT $service WHERE { $service a am:Service . ?x am:service-de ?y }"])
def test_service_word_outside_keyword_is_allowed(q):
    assert runner.guard(q) == "SELECT"


def test_from_remote_iri_is_not_fetched(client, pid, spy):
    u, hits = spy
    r = run(client, pid, f"SELECT * FROM <{u}/remote.ttl> WHERE {{ ?s ?p ?o }}")
    assert r.status_code == 200 and r.json()["rows"] == []  # FROM désigne un graphe du magasin, jamais un téléchargement
    assert hits == []


# ----------------------------------------------------------------------------------------- UPDATE / LOAD

@pytest.mark.parametrize("q", ["LOAD <http://127.0.0.1:9/x.ttl>", "LOAD SILENT <http://127.0.0.1:9/x> INTO GRAPH <urn:g>",
                               "load <http://127.0.0.1:9/x>", "# commentaire\nLOAD <http://127.0.0.1:9/x>",
                               "PREFIX ex: <http://e/> LOAD <http://127.0.0.1:9/x>",
                               "SELECT * WHERE { ?s ?p ?o } ; LOAD <http://127.0.0.1:9/x>",
                               "CREATE GRAPH <urn:g>", "COPY DEFAULT TO <urn:g>", "WITH <urn:g> DELETE { ?s ?p ?o } WHERE { ?s ?p ?o }"])
def test_load_and_other_updates_refused(client, pid, spy, q):
    u, hits = spy
    q = q.replace("http://127.0.0.1:9", u)
    before = client.get(f"/api/projects/{pid}/store/stats").json()["triples"]
    r = run(client, pid, q)
    assert r.status_code in (403, 422), r.text
    assert client.get(f"/api/projects/{pid}/store/stats").json()["triples"] == before
    assert hits == []


# ----------------------------------------------------------------------------------------------- limites

def test_row_cap_applies_to_construct_with_many_triples_per_solution(client, pid):
    up(client, pid, "d.ttl", "@prefix ex: <%s> .\n" % EX + "\n".join(f"ex:s{i} ex:p {i} ." for i in range(50)))
    # 3 triplets par solution : le LIMIT forcé porte sur les solutions, le plafond de lignes sur les triplets renvoyés
    r = run(client, pid, f"CONSTRUCT {{ ?s <{EX}a> ?o . ?s <{EX}b> ?o . ?s <{EX}c> ?o }} WHERE {{ ?s <{EX}p> ?o }}", limit=7)
    d = r.json()
    assert r.status_code == 200 and len(d["rows"]) == 7 and d["truncated"] is True and "LIMIT 8" in d["sparql"]
    r = run(client, pid, f"DESCRIBE ?s WHERE {{ ?s <{EX}p> ?o }}", limit=4)
    assert r.status_code == 200 and len(r.json()["rows"]) == 4 and r.json()["truncated"] is True


def test_hard_limit_and_subquery_limit(client, pid):
    up(client, pid, "d.ttl", "@prefix ex: <%s> .\n" % EX + "\n".join(f"ex:s{i} ex:p {i} ." for i in range(30)))
    r = run(client, pid, f"SELECT ?s WHERE {{ {{ SELECT ?s WHERE {{ ?s <{EX}p> ?o }} LIMIT 20 }} }}", limit=999999)
    assert r.status_code == 200 and len(r.json()["rows"]) == 20 and "LIMIT 5001" in r.json()["sparql"]


def test_timeout_also_applies_to_construct_and_ask(client, pid):
    client.post(f"/api/projects/{pid}/store/load", data={"sample": "demo"})
    heavy = "?a ?p ?x . ?b ?q ?y . ?c ?r ?z . ?d ?s ?w"
    agg = f"{{ SELECT (COUNT(*) AS ?n) WHERE {{ {heavy} }} }}"  # l'agrégat oblige à tout énumérer (pas de court-circuit par LIMIT)
    for q in (f"CONSTRUCT {{ <urn:x> <urn:n> ?n }} WHERE {agg}", f"ASK {{ {agg} FILTER(?n < 0) }}"):
        r = client.post(f"/api/projects/{pid}/query/run", json={"sparql": q, "endpoint": {"kind": "local", "timeout_s": 1}})
        assert r.status_code == 504, (q, r.text)
    assert run(client, pid, "ASK {}").status_code == 200


def test_timeout_bounds_are_validated(client, pid):
    for t in (0, 121):
        r = client.post(f"/api/projects/{pid}/query/run", json={"sparql": "ASK {}", "endpoint": {"kind": "local", "timeout_s": t}})
        assert r.status_code == 422


def test_upload_is_read_with_a_bound(client, pid, monkeypatch):
    monkeypatch.setenv("ONTOFORGE_LOCAL_STORE_MAX_UPLOAD_MB", "1")
    ok = b"@prefix ex: <http://example.org/> . ex:a ex:p 1 .\n" + b"#" * (1024 * 1024 - 200) + b"\n"
    assert client.post(f"/api/projects/{pid}/store/load", files={"file": ("ok.ttl", ok)}).status_code == 200
    big = ok + b"#" * 400
    r = client.post(f"/api/projects/{pid}/store/load", files={"file": ("big.ttl", big)})
    assert r.status_code == 413 and "1 Mo" in r.json()["detail"]


# ------------------------------------------------------------------------------- graphes nommés et union

def test_default_graph_is_union_of_named_graphs(client, pid):
    up(client, pid, "d.ttl", f"<{EX}a> <{EX}p> <{EX}b> .")
    up(client, pid, "tech.ttl", f"<{EX}t> a <{AM}Technician> .", inference="rdfs")
    graphs = {r["g"]["value"] for r in run(client, pid, "SELECT DISTINCT ?g WHERE { GRAPH ?g { ?s ?p ?o } }").json()["rows"]}
    assert {"urn:ontoforge:graph:ontology", "urn:ontoforge:graph:individuals", "urn:ontoforge:graph:data:d.ttl",
            "urn:ontoforge:graph:inferred"} <= graphs
    # sans GRAPH : TBox, individus, données et inféré sont visibles ensemble
    q = (f"ASK {{ <{AM}Technician> <http://www.w3.org/2000/01/rdf-schema#subClassOf> ?x . <{AM}Diesel> a <{AM}FuelType> . "
         f"<{EX}a> <{EX}p> <{EX}b> . <{EX}t> a <{AM}Person> }}")
    assert run(client, pid, q).json()["boolean"] is True
    # le graphe par défaut n'existe pas comme graphe nommé : aucun triplet n'est stocké hors des graphes nommés
    assert count(client, pid, "SELECT (COUNT(*) AS ?n) WHERE { ?s ?p ?o }") == count(
        client, pid, "SELECT (COUNT(*) AS ?n) WHERE { GRAPH ?g { ?s ?p ?o } }")


def test_from_clause_restricts_the_default_graph(client, pid):
    """Revue it1 : Oxigraph ignorait FROM quand l'union était demandée (SPARQL 1.1 §13.2 : FROM définit le graphe par défaut)."""
    up(client, pid, "d.ttl", f"<{EX}a> <{EX}p> <{EX}b> .")
    fuel = f"?f a <{AM}FuelType>"
    assert count(client, pid, f"SELECT (COUNT(*) AS ?n) WHERE {{ {fuel} }}") == 4
    assert count(client, pid, f"SELECT (COUNT(*) AS ?n) FROM <urn:ontoforge:graph:ontology> WHERE {{ {fuel} }}") == 0
    assert count(client, pid, f"SELECT (COUNT(*) AS ?n) FROM <urn:ontoforge:graph:individuals> WHERE {{ {fuel} }}") == 4
    assert count(client, pid, f"SELECT (COUNT(*) AS ?n) FROM <urn:ontoforge:graph:data:d.ttl> WHERE {{ ?s ?p ?o }}") == 1
    # FROM NAMED seul : graphe par défaut vide, GRAPH limité aux graphes nommés cités
    assert count(client, pid, "SELECT (COUNT(*) AS ?n) FROM NAMED <urn:ontoforge:graph:data:d.ttl> WHERE { ?s ?p ?o }") == 0
    assert count(client, pid, "SELECT (COUNT(*) AS ?n) FROM NAMED <urn:ontoforge:graph:data:d.ttl> WHERE { GRAPH ?g { ?s ?p ?o } }") == 1


def test_union_is_a_deduplicated_set(client, pid):
    """Bloquant it1 corrigé : le graphe par défaut est l'union DÉDUPLIQUÉE (SPARQL 1.1 §13.1), COUNT vaut 1 pour un triplet présent
    dans deux graphes ; GRAPH ?g voit toujours les deux ; plusieurs FROM sont fusionnés en ensemble (§13.2.1)."""
    up(client, pid, "a.ttl", f"<{EX}a> <{EX}p> <{EX}b> .")
    up(client, pid, "b.ttl", f"<{EX}a> <{EX}p> <{EX}b> .")
    q = f"SELECT (COUNT(*) AS ?n) WHERE {{ <{EX}a> <{EX}p> ?o }}"
    assert count(client, pid, q) == 1
    assert count(client, pid, f"SELECT (COUNT(*) AS ?n) WHERE {{ GRAPH ?g {{ <{EX}a> <{EX}p> ?o }} }}") == 2
    ga, gb = "urn:ontoforge:graph:data:a.ttl", "urn:ontoforge:graph:data:b.ttl"
    assert count(client, pid, f"SELECT (COUNT(*) AS ?n) FROM <{ga}> FROM <{gb}> WHERE {{ <{EX}a> <{EX}p> ?o }}") == 1
    assert count(client, pid, f"SELECT (COUNT(*) AS ?n) FROM <{ga}> WHERE {{ <{EX}a> <{EX}p> ?o }}") == 1
    assert count(client, pid, f"SELECT (COUNT(*) AS ?n) FROM <{ga}> FROM <{gb}> FROM NAMED <{gb}> WHERE {{ GRAPH ?g {{ ?s ?p ?o }} }}") == 1
    assert count(client, pid, f"SELECT (COUNT(*) AS ?n) FROM <{ga}> WHERE {{ GRAPH ?g {{ ?s ?p ?o }} }}") == 0
    st = client.get(f"/api/projects/{pid}/store/stats").json()
    by = {g["graph"]: g["triples"] for g in st["graphs"]}
    assert by[ga] == by[gb] == 1 and st["triples"] == sum(by.values())  # les statistiques par graphe ignorent l'union dérivée
    # vidage d'un fichier : l'union est reconstruite
    client.post(f"/api/projects/{pid}/store/load", files={"file": ("a.ttl", b"<%sz> <%sp> <%sy> ." % (EX.encode(), EX.encode(), EX.encode()), "text/turtle")})
    assert count(client, pid, f"SELECT (COUNT(*) AS ?n) WHERE {{ <{EX}a> <{EX}p> ?o }}") == 1  # reste dans b.ttl
    assert count(client, pid, f"SELECT (COUNT(*) AS ?n) WHERE {{ <{EX}z> <{EX}p> ?o }}") == 1


def test_guided_query_uses_distinct_and_no_graph_clause(client, pid):
    from test_local_store import diesel
    client.post(f"/api/projects/{pid}/store/load", data={"sample": "demo"})
    d = client.post(f"/api/projects/{pid}/query/run", json={"guided": diesel(), "endpoint": LOCAL}).json()
    assert "SELECT DISTINCT" in d["sparql"] and "GRAPH" not in d["sparql"] and "FROM" not in d["sparql"]
    rows = [json.dumps(r, sort_keys=True) for r in d["rows"]]
    assert len(rows) == len(set(rows)) == 10


# ------------------------------------------------------------------------------ format des résultats

def test_result_terms_follow_sparql_json_results(client, pid):
    q = ('SELECT ?l ?i ?s ?d ?b ?u ?iri WHERE { BIND("chat"@fr AS ?l) BIND(42 AS ?i) BIND("brut" AS ?s) '
         'BIND("2026-11-07"^^<http://www.w3.org/2001/XMLSchema#date> AS ?d) BIND(BNODE() AS ?b) BIND(<http://example.org/x> AS ?iri) '
         'OPTIONAL { ?nope <urn:none> ?u } }')
    r = run(client, pid, q).json()
    assert r["columns"] == ["l", "i", "s", "d", "b", "u", "iri"]
    row = r["rows"][0]
    assert row["l"] == {"type": "literal", "value": "chat", "xml:lang": "fr"}  # pas de datatype rdf:langString
    assert row["i"] == {"type": "literal", "value": "42", "datatype": "http://www.w3.org/2001/XMLSchema#integer"}
    assert row["s"] == {"type": "literal", "value": "brut"}  # xsd:string implicite, comme un littéral simple
    assert row["d"]["datatype"] == "http://www.w3.org/2001/XMLSchema#date"
    assert row["b"]["type"] == "bnode" and row["b"]["value"]
    assert row["iri"] == {"type": "uri", "value": "http://example.org/x"}
    assert row["u"] is None  # variable non liée


def test_ask_result_and_language_tags_are_lowercased(client, pid):
    up(client, pid, "l.ttl", f'<{EX}a> <{EX}label> "colour"@en-GB .')
    r = run(client, pid, f"SELECT ?l WHERE {{ <{EX}a> <{EX}label> ?l }}").json()
    # Oxigraph normalise en minuscules (RDF 1.1 Concepts §3.3 le permet) ; langMatches reste insensible à la casse
    assert r["rows"][0]["l"]["xml:lang"] == "en-gb"
    assert run(client, pid, f'ASK {{ <{EX}a> <{EX}label> ?l FILTER(langMatches(lang(?l), "EN-GB")) }}').json()["boolean"] is True


# --------------------------------------------------------------------------------------------- inférence

INCONSISTENT = f"""@prefix ex: <{EX}> . @prefix owl: <http://www.w3.org/2002/07/owl#> . @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
ex:A a owl:Class . ex:B a owl:Class . ex:A owl:disjointWith ex:B . ex:C a owl:Class ; rdfs:subClassOf ex:A .
ex:x a ex:C, ex:B .
ex:fp a owl:ObjectProperty, owl:FunctionalProperty . ex:y ex:fp ex:z1, ex:z2 .
"""


def test_owlrl_reports_inconsistency_and_sameas(client, pid):
    s = up(client, pid, "inc.ttl", INCONSISTENT, inference="owlrl")
    notes = " ".join(s["inference"]["notes"])
    assert "Incohérence OWL RL" in notes and "ex" in notes and "Disjoint" in notes
    assert "owl:sameAs déduits" in notes
    assert run(client, pid, f"ASK {{ <{EX}z1> <http://www.w3.org/2002/07/owl#sameAs> <{EX}z2> }}").json()["boolean"] is True
    # pas de réflexivité sameAs ni de owl:Thing matérialisés
    assert run(client, pid, "ASK { ?s <http://www.w3.org/2002/07/owl#sameAs> ?s }").json()["boolean"] is False
    assert run(client, pid, "ASK { GRAPH <urn:ontoforge:graph:inferred> { ?s a <http://www.w3.org/2002/07/owl#Thing> } }").json()["boolean"] is False
    # le schéma n'est pas fermé dans l'inféré (pas de subClassOf / equivalentClass déduits)
    assert run(client, pid, "ASK { GRAPH <urn:ontoforge:graph:inferred> { ?s <http://www.w3.org/2000/01/rdf-schema#subClassOf> ?o } }").json()["boolean"] is False


def test_haskey_note_only_for_owl_semantics_and_accurate(client, pid):
    s = up(client, pid, "t.ttl", f"<{EX}t> a <{AM}Technician> .", inference="rdfs")
    assert not any("hasKey" in n for n in s["inference"]["notes"])  # RDFS ignore owl:hasKey
    s = up(client, pid, "t.ttl", f"<{EX}t> a <{AM}Technician> .", inference="owlrl")
    note = next(n for n in s["inference"]["notes"] if "hasKey" in n)
    assert "owl:sameAs" in note and "sh:maxCount" not in note  # prp-key déduit sameAs ; SHACL Core ne teste pas l'unicité


def test_inferred_facts_never_point_to_orphan_blank_nodes(client, pid):
    ttl = f"""@prefix ex: <{EX}> . @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> . @prefix owl: <http://www.w3.org/2002/07/owl#> .
ex:sub a owl:ObjectProperty ; rdfs:subPropertyOf ex:sup . ex:sup a owl:ObjectProperty .
ex:i ex:sub [ rdfs:label "adresse" ] ; ex:sub ex:j ."""
    up(client, pid, "bn.ttl", ttl, inference="rdfs")
    rows = run(client, pid, f"SELECT ?x ?l WHERE {{ <{EX}i> <{EX}sup> ?x OPTIONAL {{ ?x <http://www.w3.org/2000/01/rdf-schema#label> ?l }} }}").json()["rows"]
    assert [r["x"]["value"] for r in rows] == [EX + "j"]  # le fait vers ex:j est déduit ; aucun fait vers un nœud anonyme orphelin
    assert run(client, pid, "ASK { GRAPH <urn:ontoforge:graph:inferred> { ?s ?p ?o FILTER(isBlank(?o) || isBlank(?s)) } }").json()["boolean"] is False


def test_useful_filter_unit():
    import importlib.util
    import sys
    from pathlib import Path

    from rdflib import OWL, RDF, RDFS, BNode, Literal, URIRef
    path = Path(runner.__file__).with_name("_infer_worker.py")
    src = path.read_text(encoding="utf-8").replace("\nmain()\n", "\n")
    mod = type(sys)("_iw")
    exec(compile(src, str(path), "exec"), mod.__dict__)  # noqa: S102 - module local du dépôt, sans l'appel à main()
    i, j, c = URIRef(EX + "i"), URIRef(EX + "j"), URIRef(EX + "C")
    schema = {c}
    assert mod.useful(i, RDF.type, c, schema)
    for noise in (RDFS.Resource, OWL.Thing, OWL.NamedIndividual, RDFS.Class):
        assert not mod.useful(i, RDF.type, noise, schema)
    assert not mod.useful(i, OWL.sameAs, i, schema) and mod.useful(i, OWL.sameAs, j, schema)
    assert not mod.useful(c, RDFS.subClassOf, c, schema) and not mod.useful(BNode(), RDF.type, c, schema)
    assert not mod.useful(Literal("x"), RDF.type, RDFS.Literal, schema)
    assert not mod.useful(i, URIRef(EX + "p"), BNode(), schema)
    assert mod.useful(i, URIRef(EX + "p"), Literal("v"), schema)
    assert importlib.util is not None


# ------------------------------------------------------------------------------- fichiers et JSON-LD

def test_jsonld_named_graphs_are_kept_in_file_graph(client, pid):
    doc = {"@context": {"ex": EX}, "@id": "ex:g", "@graph": [{"@id": "ex:a", "ex:p": "v"}, {"@id": "ex:b", "ex:p": "w"}]}
    s = up(client, pid, "g.jsonld", json.dumps(doc))
    assert next(g for g in s["graphs"] if g["name"] == "g.jsonld")["triples"] == 2
    vals = {r["o"]["value"] for r in run(client, pid, f"SELECT ?o WHERE {{ ?s <{EX}p> ?o }}").json()["rows"]}
    assert vals == {"v", "w"}


@pytest.mark.parametrize("ctx", ["array", "import", "scoped"])
def test_jsonld_remote_context_variants_never_fetched(client, pid, spy, ctx):
    u, hits = spy
    doc = {"array": {"@context": [{"ex": EX}, f"{u}/c"], "@id": EX + "a", "ex:p": "v"},
           "import": {"@context": {"@version": 1.1, "@import": f"{u}/i"}, "@id": EX + "a", EX + "p": "v"},
           "scoped": {"@context": {"ex": EX, "ex:p": {"@context": f"{u}/s"}}, "@id": EX + "a", "ex:p": {"@id": EX + "b"}}}[ctx]
    r = client.post(f"/api/projects/{pid}/store/load", files={"file": ("c.jsonld", json.dumps(doc).encode())})
    assert r.status_code == 422 and "distant" in r.json()["detail"]
    assert hits == []


def test_rdfxml_external_entity_not_resolved(client, pid, spy):
    u, hits = spy
    xml = (f'<?xml version="1.0"?><!DOCTYPE rdf:RDF [<!ENTITY e SYSTEM "{u}/xxe">]>'
           '<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#" xmlns:ex="http://example.org/">'
           '<rdf:Description rdf:about="http://example.org/a"><ex:p>&e;</ex:p></rdf:Description></rdf:RDF>')
    r = client.post(f"/api/projects/{pid}/store/load", files={"file": ("x.rdf", xml.encode())})
    assert r.status_code == 422
    assert hits == []


# ----------------------------------------------------------------------------------------- persistance

def test_store_lives_in_project_folder_and_is_removed_with_it(client, pid, tmp_path):
    up(client, pid, "d.ttl", f"<{EX}a> <{EX}p> <{EX}b> .")
    root = tmp_path / "projects" / pid / "triplestore"
    assert (root / "db").is_dir() and (root / "meta.json").is_file()
    other = client.post("/api/projects", json={"name": "B", "sample": "automaint"}).json()["id"]
    assert run(client, other, f"ASK {{ <{EX}a> <{EX}p> <{EX}b> }}").json()["boolean"] is False  # un magasin par projet
    assert client.delete(f"/api/projects/{pid}").status_code in (200, 204)
    assert not root.exists()
    assert client.get(f"/api/projects/{pid}/store/stats").status_code == 404


def test_project_deletion_drops_store_and_lock(client, pid):
    from ontoforge.localstore import store as st
    up(client, pid, "a.ttl", f"<{EX}a> <{EX}p> <{EX}b> .")
    assert pid in st._LOCKS and st.exists(pid)
    assert client.delete(f"/api/projects/{pid}").status_code == 200
    assert pid not in st._LOCKS and not st.exists(pid)


def test_parse_stops_at_triple_cap(client, pid, monkeypatch):
    monkeypatch.setenv("ONTOFORGE_LOCAL_STORE_MAX_TRIPLES", "50")
    ttl = f"<{EX}a> <{EX}p> " + ",".join(str(i) for i in range(500)) + " ."
    r = client.post(f"/api/projects/{pid}/store/load", files={"file": ("big.ttl", ttl.encode())})
    assert r.status_code == 413 and "analyse interrompue" in r.json()["detail"]
