"""Cycle projet complet via l'API, avec des services factices injectés (indépendant des autres lots)."""
import io
import sys
import types
import zipfile

import pytest
from fastapi.testclient import TestClient

from ontoforge.core.onto_model import DatatypeProperty, OntClass, ObjectProperty, OntologyMeta, OntoModel, XSD
from ontoforge.core.pg_model import EdgeType, Finding, NodeType, Option, PGModel, PGProperty
from ontoforge.core.shapes_model import NodeShape, ShapesModel, Targets
from ontoforge.main import app

AUTO = "https://example.org/auto#"
SH = "http://www.w3.org/ns/shacl#"
SHAPES_TTL = f"@prefix sh: <{SH}> .\n@prefix auto: <{AUTO}> .\nauto:VehicleShape a sh:NodeShape ; sh:targetClass auto:Vehicle .\n"
ONTO_TTL = f"@prefix owl: <http://www.w3.org/2002/07/owl#> .\n<{AUTO}Vehicle> a owl:Class .\n"


def mini_onto() -> OntoModel:
    return OntoModel(
        meta=OntologyMeta(iri="https://example.org/auto", prefixes={"auto": AUTO}),
        classes={
            AUTO + "Vehicle": OntClass(iri=AUTO + "Vehicle", labels={"fr": "Véhicule"}, has_keys=[[AUTO + "vin"]]),
            AUTO + "Car": OntClass(iri=AUTO + "Car", sub_class_of=[AUTO + "Vehicle"]),
            AUTO + "Garage": OntClass(iri=AUTO + "Garage"),
        },
        object_properties={AUTO + "servicedAt": ObjectProperty(iri=AUTO + "servicedAt", domain=[AUTO + "Vehicle"],
                                                              range=[AUTO + "Garage"])},
        datatype_properties={AUTO + "vin": DatatypeProperty(iri=AUTO + "vin", domain=[AUTO + "Vehicle"],
                                                            range=[XSD + "string"], functional=True)},
    )


def fake_analyze(onto, shapes, target, decisions=None):
    decisions = decisions or {}
    f = Finding(id="C02:auto:Car", rule="C02", severity="review", title="Sous-classe", detail="Car ⊑ Vehicle",
                subject=AUTO + "Car", options=[Option(id="flatten", label="Aplatir", impact="discriminant"),
                                               Option(id="separate", label="Séparer", impact="2 types")],
                recommended="flatten" if target == "curiosity" else "separate",
                chosen=decisions.get("C02:auto:Car"))
    lost = Finding(id="X00:auto:x", rule="X00", severity="lost", title="Non traité", detail="-", subject=AUTO + "x")
    pg = PGModel(target=target, node_types={
        "Vehicle": NodeType(name="Vehicle", labels=["Vehicle"], key=["vin"], properties=[PGProperty(name="vin", unique=True)]),
        "Garage": NodeType(name="Garage", labels=["Garage"])},
        edge_types=[EdgeType(name="ServicedAt", **{"from": "Vehicle"}, to="Garage", reverse="ServicedVehicle")],
        findings=[f, lost], decisions=dict(decisions))
    pg.meta.name = "shapes" if shapes else "noshapes"
    return pg


def module(name, **funcs):
    m = types.ModuleType(f"ontoforge.{name}")
    for k, v in funcs.items():
        setattr(m, k, v)
    return m


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("ONTOFORGE_DATA", str(tmp_path))
    seen = {}

    def parse_ontology(data, format=None, filename=None):
        text = data.decode() if isinstance(data, bytes) else data
        if "SYNTAX ERROR" in text:
            raise ValueError("ligne 1 : jeton inattendu")
        seen["onto_file"] = filename
        return mini_onto(), ["avertissement factice"]

    def parse_shapes(data, format=None, filename=None):
        seen["shapes_file"] = filename
        return ShapesModel(shapes={AUTO + "VehicleShape": NodeShape(
            id=AUTO + "VehicleShape", targets=Targets(target_class=[AUTO + "Vehicle"]))}), []

    fakes = {
        "io.rdf_import": module("io.rdf_import", parse_ontology=parse_ontology),
        "io.rdf_export": module("io.rdf_export", serialize=lambda m, format="turtle": f"# {format} {len(m.classes)}\n"),
        "shacl.import_shapes": module("shacl.import_shapes", parse_shapes=parse_shapes),
        "shacl.export_shapes": module("shacl.export_shapes", serialize_shapes=lambda s, format="turtle": "# shapes\n"),
        "mapping.engine": module("mapping.engine", analyze=fake_analyze),
        "targets.curiosity": module("targets.curiosity", generate=lambda pg, onto=None: {"Schema.cs": "class Vehicle {}"}),
        "targets.report": module("targets.report", generate=lambda pg, onto=None: {"rapport-transposition.md": "# R"}),
        "targets.graphql": None,  # absent → ignoré dans l'agrégat
    }
    for name, mod in fakes.items():
        monkeypatch.setitem(sys.modules, f"ontoforge.{name}", mod)
    c = TestClient(app)
    c.seen = seen
    c.data_dir = tmp_path
    return c


def test_health(client):
    assert client.get("/api/health").json() == {"status": "ok", "version": "0.1.0"}


def test_full_project_cycle(client):
    r = client.post("/api/projects", json={"name": "Garage Démo", "description": "test"})
    assert r.status_code == 201, r.text
    p = r.json()
    pid = p["id"]
    assert pid.startswith("garage-demo-")
    assert client.get("/api/projects").json()[0]["id"] == pid

    # import ontologie (auto) puis shapes (auto)
    r = client.post(f"/api/projects/{pid}/import", files={"file": ("auto.ttl", ONTO_TTL, "text/turtle")})
    assert r.status_code == 200, r.text
    assert r.json()["kind"] == "ontology" and r.json()["warnings"] == ["avertissement factice"]
    r = client.post(f"/api/projects/{pid}/import", files={"file": ("auto-shapes.ttl", SHAPES_TTL)}, data={"kind": "auto"})
    assert r.json()["kind"] == "shapes"
    assert client.seen == {"onto_file": "auto.ttl", "shapes_file": "auto-shapes.ttl"}

    summary = client.get("/api/projects").json()[0]
    assert summary["stats"]["classes"] == 3 and summary["stats"]["shapes"] == 1
    d = client.data_dir / "projects" / pid
    assert (d / "project.json").is_file() and (d / "onto.ttl").read_text() == "# turtle 3\n"

    # édition onto
    onto = client.get(f"/api/projects/{pid}").json()["onto"]
    del onto["classes"][AUTO + "Garage"]
    r = client.put(f"/api/projects/{pid}/onto", json=onto)
    assert r.status_code == 200 and len(r.json()["onto"]["classes"]) == 2

    # export
    r = client.get(f"/api/projects/{pid}/export/ontology?format=turtle")
    assert r.status_code == 200 and r.text == "# turtle 2\n" and r.headers["content-type"].startswith("text/turtle")
    assert client.get(f"/api/projects/{pid}/export/shapes").text == "# shapes\n"

    # analyse + arbitrage
    pg = client.post(f"/api/projects/{pid}/analyze?target=curiosity").json()
    assert pg["target"] == "curiosity" and pg["meta"]["name"] == "shapes"
    assert pg["edge_types"][0]["from"] == "Vehicle"
    assert pg["findings"][0]["chosen"] is None

    pg = client.put(f"/api/projects/{pid}/decisions/curiosity", json={"C02:auto:Car": "separate"}).json()
    assert pg["findings"][0]["chosen"] == "separate"
    assert client.get(f"/api/projects/{pid}").json()["decisions"]["curiosity"] == {"C02:auto:Car": "separate"}
    pg = client.put(f"/api/projects/{pid}/decisions/curiosity", json={"C02:auto:Car": None}).json()
    assert pg["findings"][0]["chosen"] is None

    pg = client.post(f"/api/projects/{pid}/decisions/neo4j/accept-recommended").json()
    assert pg["target"] == "neo4j" and pg["decisions"] == {"C02:auto:Car": "separate"}
    assert client.get(f"/api/projects/{pid}").json()["decisions"]["neo4j"] == {"C02:auto:Car": "separate"}

    # génération (graphql absent → listé dans missing)
    g = client.get(f"/api/projects/{pid}/generate/curiosity").json()
    assert g["files"] == {"Schema.cs": "class Vehicle {}", "rapport-transposition.md": "# R"}
    assert g["missing"] == ["targets.graphql"]
    r = client.get(f"/api/projects/{pid}/generate/curiosity/zip")
    assert r.status_code == 200 and r.headers["content-type"] == "application/zip"
    names = zipfile.ZipFile(io.BytesIO(r.content)).namelist()
    assert f"{pid}-curiosity/Schema.cs" in names

    # PUT projet complet : id et created_at protégés
    full = client.get(f"/api/projects/{pid}").json()
    full["name"] = "Renommé"
    full["id"] = "pirate"
    r = client.put(f"/api/projects/{pid}", json=full)
    assert r.json()["id"] == pid and r.json()["name"] == "Renommé" and r.json()["created_at"] == p["created_at"]

    # suppression
    assert client.delete(f"/api/projects/{pid}").json()["id"] == pid
    assert client.get(f"/api/projects/{pid}").status_code == 404
    assert not d.exists()


def test_parse_error_is_422_in_french(client):
    pid = client.post("/api/projects", json={"name": "x"}).json()["id"]
    r = client.post(f"/api/projects/{pid}/import", files={"file": ("bad.ttl", "SYNTAX ERROR")}, data={"kind": "ontology"})
    assert r.status_code == 422
    assert r.json()["detail"].startswith("Impossible de lire l'ontologie « bad.ttl »")
    r = client.post(f"/api/projects/{pid}/import", files={"file": ("vide.ttl", "")})
    assert r.status_code == 422


def test_unknown_project_and_target(client):
    assert client.get("/api/projects/nope-123456").status_code == 404
    assert "introuvable" in client.get("/api/projects/nope-123456").json()["detail"]
    pid = client.post("/api/projects", json={"name": "x"}).json()["id"]
    r = client.post(f"/api/projects/{pid}/analyze?target=tigergraph")
    assert r.status_code == 422 and "Cible inconnue" in r.json()["detail"]
    assert client.get(f"/api/projects/{pid}/export/ontology?format=docx").status_code == 422


def test_request_validation_message_in_french(client):
    r = client.post("/api/projects", json={"description": "sans nom"})
    assert r.status_code == 422 and r.json()["detail"].startswith("Entrée invalide")


def test_create_from_sample(client, tmp_path, monkeypatch):
    sdir = tmp_path / "samples" / "mini"
    sdir.mkdir(parents=True)
    (sdir / "mini.ttl").write_text(ONTO_TTL)
    (sdir / "mini-shapes.ttl").write_text(SHAPES_TTL)
    (sdir / "mini-data.ttl").write_text("# data\n")
    (sdir / "README.md").write_text("# Mini exemple\n")
    monkeypatch.setenv("ONTOFORGE_SAMPLES", str(tmp_path / "samples"))
    lst = client.get("/api/samples").json()
    assert lst == [{"name": "mini", "title": "Mini exemple",
                    "files": ["README.md", "mini-data.ttl", "mini-shapes.ttl", "mini.ttl"],
                    "ontology": ["mini.ttl"], "shapes": ["mini-shapes.ttl"], "data": ["mini-data.ttl"]}]
    r = client.post("/api/projects", json={"name": "Depuis exemple", "sample": "mini"})
    assert r.status_code == 201, r.text
    p = r.json()
    assert len(p["onto"]["classes"]) == 3 and len(p["shapes"]["shapes"]) == 1
    assert p["source_files"] == ["mini.ttl", "mini-shapes.ttl", "mini-data.ttl"]
    assert (client.data_dir / "projects" / p["id"] / "data.ttl").read_text() == "# data\n"
    assert client.post("/api/projects", json={"name": "x", "sample": "inconnu"}).status_code == 404


def test_repo_samples_listed(client, monkeypatch):
    monkeypatch.delenv("ONTOFORGE_SAMPLES", raising=False)
    trap = next(s for s in client.get("/api/samples").json() if s["name"] == "trap")
    assert trap["ontology"] == ["trap.ttl"] and trap["shapes"] == ["trap-shapes.ttl"] and trap["data"] == ["trap-data.ttl"]


def test_cors_open(client):
    r = client.options("/api/projects", headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "GET"})
    assert r.headers.get("access-control-allow-origin") in ("*", "http://localhost:5173")


def test_shacl_generate_dry_run_does_not_save(tmp_path, monkeypatch):
    monkeypatch.setenv("ONTOFORGE_DATA", str(tmp_path))
    from fastapi.testclient import TestClient
    from ontoforge.main import app
    c = TestClient(app)
    pid = c.post("/api/projects", json={"name": "dry", "sample": "automaint"}).json()["id"]
    before = c.get(f"/api/projects/{pid}").json()["shapes"]
    r = c.post(f"/api/projects/{pid}/shacl/generate", json={"merge": True, "dry_run": True}).json()
    assert r["dry_run"] is True and r["generated"]["shapes"]
    assert c.get(f"/api/projects/{pid}").json()["shapes"] == before
