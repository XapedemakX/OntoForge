"""L53 (DF-B17) : l'analyseur SPARQL de rdflib (pyparsing) n'est pas réentrant ; des analyses simultanées échouaient au hasard.

Avant : « SPARQL invalide : Param.postParse2() missing 1 required positional argument » en 422 sur des requêtes valides."""
from __future__ import annotations

import threading

import pytest
from fastapi.testclient import TestClient

QUERIES = ["SELECT ?s WHERE { ?s ?p ?o } LIMIT 5",
           "ASK { ?s a ?c }",
           "PREFIX ex: <http://e/> SELECT ?a ?b WHERE { ?a ex:p ?b . OPTIONAL { ?b ex:q ?c } FILTER(?a != ?b) } ORDER BY ?a",
           "SELECT (COUNT(*) AS ?n) WHERE { ?s ?p ?o }"]


def _hammer(fn, threads=8, rounds=40):
    """`threads` fils appellent `fn(requête)` `rounds` fois, départ simultané ; renvoie les erreurs relevées."""
    errors, barrier = [], threading.Barrier(threads)

    def go(k):
        barrier.wait()
        for i in range(rounds):
            try:
                fn(QUERIES[(k + i) % len(QUERIES)])
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{type(exc).__name__}: {str(exc)[:120]}")

    ts = [threading.Thread(target=go, args=(k,)) for k in range(threads)]
    [t.start() for t in ts]
    [t.join(120) for t in ts]
    return errors


def test_b17_query_form_is_safe_under_concurrency():
    from ontoforge.queries import endpoint
    errors = _hammer(endpoint.query_form)
    assert not errors, f"{len(errors)} erreurs, par exemple {errors[0]}"  # avant : plusieurs dizaines


def test_b17_prepare_query_is_safe_under_concurrency():
    from ontoforge.queries import sparql_lock
    errors = _hammer(lambda q: sparql_lock.prepare_query(q))
    assert not errors, f"{len(errors)} erreurs, par exemple {errors[0]}"


def test_b17_service_check_and_dataset_clause_are_safe_under_concurrency():
    from ontoforge.localstore import runner
    # ces deux fonctions avalent les erreurs d'analyse (rendent False / None) : on compare donc leurs réponses à celles d'un appel isolé
    federated = "SELECT * WHERE { { SERVICE <http://e/s> { ?a ?b ?c } } }".replace("SERVICE", "SERV" + "ICE")
    from_q = "SELECT * FROM <http://e/g> FROM NAMED <http://e/n> WHERE { ?s ?p ?o }"
    assert runner._has_service(federated) and runner.dataset_clause(from_q) == {"default": ["http://e/g"], "named": ["http://e/n"]}

    def check(q):
        assert runner.dataset_clause(from_q) == {"default": ["http://e/g"], "named": ["http://e/n"]}
        assert runner.dataset_clause(q) is None
        assert not runner._has_service(q)
    errors = _hammer(check)
    assert not errors, f"{len(errors)} erreurs, par exemple {errors[0]}"


# Scripts des processus fils : ils ont leur propre processus (donc leur propre copie du parseur), sans objet pour le verrou.
CHILD_SCRIPTS = {"localstore/_worker.py", "localstore/_infer_worker.py", "shacl/_worker.py", "conformance/_owlrl_worker.py"}
# Seuls fichiers du serveur autorisés à importer des morceaux de `rdflib.plugins.sparql` (l'algèbre, jamais l'analyse) : ils reçoivent un
# résultat déjà analysé par `sparql_lock`.
ALGEBRA_IMPORTERS = {"queries/sparql_lock.py", "queries/translate.py", "localstore/runner.py"}
# Seuls fichiers qui appellent `.query(` : sur un magasin Oxigraph (Rust, sans pyparsing), pas sur un `rdflib.Graph`.
OXIGRAPH_QUERY = {"businessmap/counts.py"}
PARSER_NAMES = {"parseQuery", "parseUpdate", "prepareQuery", "prepareUpdate", "translateQuery", "translateUpdate", "processUpdate", "evalQuery"}


def _server_files():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1] / "ontoforge"
    for f in sorted(root.rglob("*.py")):
        rel = str(f.relative_to(root))
        if rel not in CHILD_SCRIPTS:
            yield rel, f


def _violations(source: str, rel: str) -> list[str]:
    import ast
    out = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.ImportFrom) and (node.module or "").startswith("rdflib.plugins.sparql"):
            if rel not in ALGEBRA_IMPORTERS:
                out.append(f"{rel}:{node.lineno} import de {node.module}")
            names = {a.name for a in node.names} | ({node.module.rsplit(".", 1)[-1]} if node.module else set())
            if names & PARSER_NAMES and rel != "queries/sparql_lock.py":
                out.append(f"{rel}:{node.lineno} import du parseur ({', '.join(sorted(names & PARSER_NAMES))}), même renommé")
        elif isinstance(node, ast.Import):
            for a in node.names:
                if a.name.startswith("rdflib.plugins.sparql") and rel not in ALGEBRA_IMPORTERS:
                    out.append(f"{rel}:{node.lineno} import de {a.name}")
        elif isinstance(node, ast.Call):
            fn = node.func
            name = fn.attr if isinstance(fn, ast.Attribute) else fn.id if isinstance(fn, ast.Name) else ""
            if name in PARSER_NAMES and rel != "queries/sparql_lock.py":
                out.append(f"{rel}:{node.lineno} appel de {name}")
            if isinstance(fn, ast.Attribute) and fn.attr == "query" and rel not in OXIGRAPH_QUERY:
                out.append(f"{rel}:{node.lineno} .query( hors d'un magasin Oxigraph")
            if isinstance(fn, ast.Attribute) and fn.attr == "update" and isinstance(fn.value, ast.Name) and fn.value.id in ("g", "graph", "dg", "sg", "og", "rg"):
                out.append(f"{rel}:{node.lineno} Graph.update(")
    return out


def test_b17_no_sparql_parser_call_outside_the_lock():
    """Tout appel au parseur SPARQL de rdflib dans le processus du serveur passe par `queries/sparql_lock.py` (un seul verrou pour tout le
    processus). Couvre tous les fichiers du serveur, `__init__.py` et `conformance/_owlrl_core.py` compris (chargé par `reasoner.py` dans
    le serveur) ; seuls les quatre scripts de processus fils sont exclus, par leur nom."""
    bad = []
    for rel, f in _server_files():
        bad += _violations(f.read_text(encoding="utf-8"), rel)
    assert not bad, bad


def test_b17_guard_sees_what_it_claims_to_see():
    """Le test de garde lui-même : il repère les variantes (import renommé, prepareUpdate, Graph.query / update) et couvre les fichiers voulus."""
    assert _violations("from rdflib.plugins.sparql.parser import parseQuery as pq\npq('x')", "x.py")
    assert _violations("from rdflib.plugins.sparql import prepareQuery as p", "x.py")
    assert _violations("from rdflib.plugins.sparql import algebra", "x.py")
    assert _violations("import rdflib.plugins.sparql.parser", "x.py")
    assert _violations("x.prepareUpdate('a')", "x.py") and _violations("translateUpdate(a)", "x.py")
    assert _violations("g = Graph()\ng.query('SELECT * {}')", "x.py") and _violations("g.update('INSERT DATA {}')", "x.py")
    assert not _violations("from rdflib.plugins.sparql import algebra", "queries/translate.py")
    assert not _violations("d = {}\nd.update(a=1)", "x.py")
    seen = {rel for rel, _ in _server_files()}
    assert {"conformance/_owlrl_core.py", "localstore/__init__.py", "shacl/__init__.py", "conformance/__init__.py", "queries/__init__.py"} <= seen
    assert not (seen & CHILD_SCRIPTS)


def _count_sparql_parses(monkeypatch):
    """Compte les analyses SPARQL de rdflib en remplaçant les POINTS D'ENTRÉE DE LA GRAMMAIRE (`Query.parseString`, `UpdateUnit.parseString`),
    que `parser.parseQuery`, `processor.parseQuery` (importé par nom) et toute autre copie partagent : remplacer seulement `parser.parseQuery`
    laissait `Graph.query` à zéro appel (it2, devback B1)."""
    from rdflib.plugins.sparql import parser
    calls = []
    for name in ("Query", "UpdateUnit"):
        elt = getattr(parser, name)
        real = elt.parseString
        monkeypatch.setattr(elt, "parseString", lambda *a, _r=real, _n=name, **k: (calls.append(_n), _r(*a, **k))[1])
    return calls


def test_b17_counter_sees_graph_query_calls(monkeypatch):
    """Témoin positif : sous le même remplacement, un `Graph().query` DOIT compter au moins un appel, sinon le test pySHACL ci-dessous serait muet."""
    import rdflib
    calls = _count_sparql_parses(monkeypatch)
    rdflib.Graph().query("ASK {}")
    assert len(calls) >= 1, "le compteur ne voit pas Graph.query : le test pySHACL ne prouverait rien"


def test_b17_pyshacl_in_the_server_does_not_reach_the_sparql_parser(monkeypatch):
    """Cas pySHACL : `editing/files.py::_shacl_shacl` valide en processus un graphe de shapes contre la méta-shape ; pySHACL interroge par
    `Graph.query` (donc par le parseur) pour SHACL-SPARQL. Mesuré le 24/11 : zéro appel au parseur pour ces entrées (shapes utilisateur
    = données, méta-shape sans contrainte SPARQL, `advanced=False`). Hors du test de garde (une bibliothèque tierce) : ce test échoue si cela
    change, et son témoin positif (`test_b17_counter_sees_graph_query_calls`, même compteur) garantit qu'il peut échouer."""
    import rdflib
    import os
    import pyshacl
    calls = _count_sparql_parses(monkeypatch)
    g = rdflib.Graph().parse(data="""@prefix sh: <http://www.w3.org/ns/shacl#> . @prefix e: <http://e/> .
e:S a sh:NodeShape ; sh:targetClass e:C ; sh:closed true ; sh:property [ sh:path e:p ; sh:class e:D ; sh:equals e:q ; sh:disjoint e:r ; sh:lessThan e:s ] ;
  sh:sparql [ a sh:SPARQLConstraint ; sh:select "SELECT $this WHERE { $this ?p ?o }" ] .""", format="turtle")
    meta = rdflib.Graph().parse(os.path.join(os.path.dirname(pyshacl.__file__), "assets", "shacl-shacl.ttl"), format="turtle")
    pyshacl.validate(g, shacl_graph=meta, inference=None, advanced=False, inplace=False)  # mêmes arguments que editing/files.py::_shacl_shacl
    assert calls == [], calls


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("ONTOFORGE_DATA", str(tmp_path))
    monkeypatch.setenv("ONTOFORGE_LLM_PROVIDER", "mock")
    from ontoforge.main import app
    return TestClient(app, raise_server_exceptions=False)


def test_b17_simultaneous_run_requests_on_different_projects_all_succeed(client, monkeypatch):
    """Cinq `POST /query/run` simultanés (non échelonnés) sur cinq projets, tous valides : cinq 200 (avant : 422 au hasard)."""
    import subprocess
    from ontoforge import childproc
    monkeypatch.setattr(childproc, "run_limited", lambda *a, **k: subprocess.CompletedProcess([], 0, b'{"form": "ASK", "boolean": true}', b""))
    from ontoforge.localstore import store as st
    monkeypatch.setattr(st, "_SLOTS", threading.BoundedSemaphore(32))
    ids = [client.post("/api/projects", json={"name": f"p{i}", "sample": "automaint"}).json()["id"] for i in range(5)]
    bad = []
    for rnd in range(6):
        out, barrier = [None] * 5, threading.Barrier(5)

        def go(i):
            barrier.wait()
            out[i] = client.post(f"/api/projects/{ids[i]}/query/run", json={"sparql": QUERIES[1], "endpoint": {"kind": "local"}})

        ts = [threading.Thread(target=go, args=(i,)) for i in range(5)]
        [t.start() for t in ts]
        [t.join(60) for t in ts]
        bad += [r.text[:120] for r in out if r.status_code != 200]
    assert not bad, bad
