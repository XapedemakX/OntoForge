import json
import sys
import types

import pytest

from ontoforge.core.onto_model import OntClass, OntologyMeta, OntoModel
from ontoforge.projects import store

AUTO = "https://example.org/auto#"


@pytest.fixture(autouse=True)
def data_env(tmp_path, monkeypatch):
    monkeypatch.setenv("ONTOFORGE_DATA", str(tmp_path))
    # par défaut : pas de modules d'export (indépendant de l'avancement des autres lots)
    monkeypatch.setitem(sys.modules, "ontoforge.io.rdf_export", None)
    monkeypatch.setitem(sys.modules, "ontoforge.shacl.export_shapes", None)
    return tmp_path


def test_slug_and_id():
    assert store.slugify("Maintenance Auto — Été 2026 !") == "maintenance-auto-ete-2026"
    assert store.slugify("???") == "projet"
    pid = store.new_id("Mon Projet")
    assert pid.startswith("mon-projet-") and len(pid) == len("mon-projet-") + 6
    assert store.ID_RE.match(pid)


def test_crud_cycle(data_env):
    p = store.create("Garage", "démo")
    p.onto = OntoModel(meta=OntologyMeta(iri=AUTO), classes={AUTO + "Vehicle": OntClass(iri=AUTO + "Vehicle")})
    store.save(p)
    d = data_env / "projects" / p.id
    assert (d / "project.json").is_file() and (d / "decisions.json").is_file()
    assert not list(d.glob(".*.tmp")), "fichier temporaire résiduel"
    assert not (d / "onto.ttl").exists()  # module d'export absent → ignoré

    got = store.get(p.id)
    assert got.onto.classes[AUTO + "Vehicle"].iri == AUTO + "Vehicle"
    assert "T" in got.updated_at and got.updated_at.endswith("+00:00")
    assert [x.id for x in store.list_projects()] == [p.id]

    got.decisions["curiosity"]["C02:auto:Car"] = "flatten"
    store.save(got)
    assert json.loads((d / "decisions.json").read_text())["curiosity"] == {"C02:auto:Car": "flatten"}

    store.delete(p.id)
    assert not d.exists()
    with pytest.raises(store.ProjectNotFound):
        store.get(p.id)


def test_invalid_ids_rejected():
    for bad in ("../etc", "A B", "", "x/y"):
        with pytest.raises(store.ProjectNotFound):
            store.get(bad)


def test_list_skips_corrupted(data_env):
    p = store.save(store.create("ok"))
    bad = data_env / "projects" / "broken-000000"
    bad.mkdir(parents=True)
    (bad / "project.json").write_text("{pas du json")
    assert [x.id for x in store.list_projects()] == [p.id]


def test_side_files_exported_when_modules_exist(data_env, monkeypatch):
    onto_mod = types.ModuleType("ontoforge.io.rdf_export")
    onto_mod.serialize = lambda m, fmt="turtle": f"# onto {m.meta.iri} {fmt}\n"
    sh_mod = types.ModuleType("ontoforge.shacl.export_shapes")
    sh_mod.serialize_shapes = lambda s, fmt="turtle": "# shapes\n"
    monkeypatch.setitem(sys.modules, "ontoforge.io.rdf_export", onto_mod)
    monkeypatch.setitem(sys.modules, "ontoforge.shacl.export_shapes", sh_mod)
    p = store.save(store.create("export"))
    d = data_env / "projects" / p.id
    assert (d / "onto.ttl").read_text().startswith("# onto https://w3id.org/ontoforge/new# turtle")
    assert (d / "shapes.ttl").read_text() == "# shapes\n"


def test_export_failure_does_not_break_save(data_env, monkeypatch):
    mod = types.ModuleType("ontoforge.io.rdf_export")

    def boom(m, fmt="turtle"):
        raise RuntimeError("bug export")

    mod.serialize = boom
    monkeypatch.setitem(sys.modules, "ontoforge.io.rdf_export", mod)
    p = store.save(store.create("robuste"))
    assert store.get(p.id).name == "robuste"


def test_write_file_guard():
    p = store.save(store.create("files"))
    store.write_file(p.id, "data.ttl", "x")
    assert store.read_file(p.id, "data.ttl") == "x"
    with pytest.raises(ValueError):
        store.write_file(p.id, "../evil", "x")
