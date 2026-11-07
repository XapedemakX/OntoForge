"""Contrat d'API : tous les chemins de CONTRACTS.md §2 existent ; 501 lisible quand un module de service manque."""
import sys
import types

import pytest
from fastapi.testclient import TestClient

from ontoforge.main import app

CONTRACT = [
    ("GET", "/api/health"), ("GET", "/api/samples"),
    ("GET", "/api/projects"), ("POST", "/api/projects"),
    ("GET", "/api/projects/{pid}"), ("PUT", "/api/projects/{pid}"), ("DELETE", "/api/projects/{pid}"),
    ("POST", "/api/projects/{pid}/import"),
    ("PUT", "/api/projects/{pid}/onto"), ("PUT", "/api/projects/{pid}/shapes"),
    ("POST", "/api/projects/{pid}/dsl"),
    ("GET", "/api/projects/{pid}/export/ontology"), ("GET", "/api/projects/{pid}/export/shapes"),
    ("GET", "/api/projects/{pid}/conformance"),
    ("POST", "/api/projects/{pid}/shacl/generate"), ("POST", "/api/projects/{pid}/shacl/validate"),
    ("POST", "/api/projects/{pid}/analyze"),
    ("PUT", "/api/projects/{pid}/decisions/{target}"),
    ("POST", "/api/projects/{pid}/decisions/{target}/accept-recommended"),
    ("GET", "/api/projects/{pid}/generate/{target}"), ("GET", "/api/projects/{pid}/generate/{target}/zip"),
    ("POST", "/api/projects/{pid}/queries/translate"), ("GET", "/api/projects/{pid}/queries/competency"),
    ("POST", "/api/assistant/draft"), ("POST", "/api/assistant/shapes"), ("POST", "/api/assistant/explain"),
    ("GET", "/api/assistant/status"),
]

ALL_SERVICES = ["io.rdf_import", "io.rdf_export", "io.dsl", "conformance.profiles", "shacl.import_shapes",
                "shacl.export_shapes", "shacl.validate", "shacl.owl_to_shacl", "mapping.engine",
                "targets.curiosity", "targets.neo4j", "targets.graphql", "targets.report", "queries.translate", "queries.competency",
                "assistant.service"]


def test_all_contract_routes_exist():
    paths = app.openapi()["paths"]
    missing = [(m, p) for m, p in CONTRACT if p not in paths or m.lower() not in paths[p]]
    assert not missing, missing


@pytest.fixture
def bare(tmp_path, monkeypatch):
    """Aucun module de service disponible."""
    monkeypatch.setenv("ONTOFORGE_DATA", str(tmp_path))
    for name in ALL_SERVICES:
        monkeypatch.setitem(sys.modules, f"ontoforge.{name}", None)
    c = TestClient(app)
    c.pid = c.post("/api/projects", json={"name": "Vide"}).json()["id"]
    return c


def _calls(pid):
    f = {"file": ("x.ttl", "<a> <b> <c> .")}
    return [
        ("io.rdf_import", "post", f"/api/projects/{pid}/import", dict(files=f, data={"kind": "ontology"})),
        ("io.rdf_import", "post", f"/api/projects/{pid}/import", dict(files=f)),
        ("shacl.import_shapes", "post", f"/api/projects/{pid}/import", dict(files=f, data={"kind": "shapes"})),
        ("io.dsl", "post", f"/api/projects/{pid}/dsl", dict(json={"text": "Car < Vehicle", "merge": True})),
        ("io.rdf_export", "get", f"/api/projects/{pid}/export/ontology", {}),
        ("shacl.export_shapes", "get", f"/api/projects/{pid}/export/shapes", {}),
        ("conformance.profiles", "get", f"/api/projects/{pid}/conformance", {}),
        ("shacl.owl_to_shacl", "post", f"/api/projects/{pid}/shacl/generate", dict(json={"merge": True})),
        ("shacl.validate", "post", f"/api/projects/{pid}/shacl/validate", dict(files=f)),
        ("mapping.engine", "post", f"/api/projects/{pid}/analyze?target=curiosity", {}),
        ("mapping.engine", "put", f"/api/projects/{pid}/decisions/curiosity", dict(json={"a": "b"})),
        ("mapping.engine", "post", f"/api/projects/{pid}/decisions/neo4j/accept-recommended", {}),
        ("mapping.engine", "get", f"/api/projects/{pid}/generate/curiosity", {}),
        ("mapping.engine", "get", f"/api/projects/{pid}/generate/neo4j/zip", {}),
        ("queries.translate", "post", f"/api/projects/{pid}/queries/translate", dict(json={"sparql": "SELECT *"})),
        ("queries.competency", "get", f"/api/projects/{pid}/queries/competency", {}),
        ("assistant.service", "get", "/api/assistant/status", {}),
        ("assistant.service", "post", "/api/assistant/draft", dict(json={"text": "un garage répare des véhicules"})),
        ("assistant.service", "post", "/api/assistant/shapes", dict(json={"project_id": pid})),
        ("assistant.service", "post", "/api/assistant/explain",
         dict(json={"project_id": pid, "target": "curiosity", "finding_id": "C02:x"})),
    ]


def test_501_when_module_missing(bare):
    for module, method, url, kw in _calls(bare.pid):
        r = getattr(bare, method)(url, **kw)
        assert r.status_code == 501, (url, r.status_code, r.text)
        assert r.json() == {"detail": f"module {module} pas encore disponible"}, url


def test_decisions_not_persisted_when_engine_missing(bare):
    bare.put(f"/api/projects/{bare.pid}/decisions/curiosity", json={"a": "b"})
    assert bare.get(f"/api/projects/{bare.pid}").json()["decisions"]["curiosity"] == {}


def test_501_when_function_missing(bare, monkeypatch):
    monkeypatch.setitem(sys.modules, "ontoforge.mapping.engine", types.ModuleType("ontoforge.mapping.engine"))
    r = bare.post(f"/api/projects/{bare.pid}/analyze")
    assert r.status_code == 501 and r.json()["detail"] == "module mapping.engine pas encore disponible"


def test_generate_501_when_no_generator(bare, monkeypatch):
    from ontoforge.core.pg_model import PGModel
    mod = types.ModuleType("ontoforge.mapping.engine")
    mod.analyze = lambda onto, shapes, target, decisions=None: PGModel(target=target)
    monkeypatch.setitem(sys.modules, "ontoforge.mapping.engine", mod)
    r = bare.get(f"/api/projects/{bare.pid}/generate/neo4j")
    assert r.status_code == 501 and r.json()["detail"] == "module targets.neo4j pas encore disponible"


def test_crud_works_without_any_service(bare):
    assert bare.get("/api/health").status_code == 200
    assert bare.get(f"/api/projects/{bare.pid}").json()["name"] == "Vide"
    onto = bare.get(f"/api/projects/{bare.pid}").json()["onto"]
    assert bare.put(f"/api/projects/{bare.pid}/onto", json=onto).status_code == 200
    shapes = {"shapes": {}, "property_shapes": {}, "prefixes": {}, "warnings": []}
    assert bare.put(f"/api/projects/{bare.pid}/shapes", json=shapes).status_code == 200
