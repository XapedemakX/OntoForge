"""L31 : versions de normes et de cibles (référence standards.json, versions par projet, générateurs, contrôle local, Krakie)."""
import json
import re
import socket
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from ontoforge import standards
from ontoforge.core.pg_model import PGModel
from ontoforge.main import app
from ontoforge.targets import curiosity, neo4j, report

FIX = Path(__file__).parent / "fixtures" / "pg_neo4j_automaint.json"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("ONTOFORGE_DATA", str(tmp_path))
    monkeypatch.setenv("ONTOFORGE_LLM_PROVIDER", "mock")
    return TestClient(app)


@pytest.fixture
def pid(client):
    r = client.post("/api/projects", json={"name": "versions", "sample": "automaint"})
    assert r.status_code in (200, 201), r.text
    return r.json()["id"]


def _pg(**versions):
    pg = PGModel.model_validate(json.loads(FIX.read_text(encoding="utf-8")))
    pg.meta.target_versions = {**standards.defaults(), **versions}
    return pg


def _statements(text):
    """Requêtes d'un fichier Cypher : lignes hors commentaires, découpées sur les « ; » de fin de ligne."""
    body = "\n".join(l for l in text.splitlines() if not l.strip().startswith("//"))
    return [x.strip() for x in re.split(r";[ \t]*\n", body + "\n") if x.strip()]


# ---- référence ---------------------------------------------------------------------------------------

def test_reference_covers_the_families_and_statuses():
    ref = standards.reference("fr")
    assert ref["updated"] and ref["defaults"]["curiosity_library"] == "26.11.7740"
    assert {v["id"] for v in ref["w3c"]["rdf"]["versions"]} == {"1.1", "1.2"}
    assert {v["id"] for v in ref["w3c"]["sparql"]["versions"]} == {"1.1", "1.2"}
    assert {v["id"] for v in ref["w3c"]["shacl"]["versions"]} == {"1.0", "1.2"}
    assert {v["id"] for v in ref["neo4j"]["versions"]} == {"4.4", "5.26", "2026.10"}
    assert {v["id"] for v in ref["curiosity"]["versions"]} >= {"26.11.7740"}
    assert {i["id"] for i in ref["libraries"]["items"]} == {"rdflib", "pyshacl", "owlrl", "pyoxigraph", "pypdf"}
    sup = {v["support"] for fam in (ref["neo4j"], ref["curiosity"]) for v in fam["versions"]}
    assert sup <= {"recommended", "supported", "obsolete", "end_of_support"}
    for fam in ("rdf", "shacl", "sparql"):
        for v in ref["w3c"][fam]["versions"]:
            assert v["maturity"] in ("REC", "CR", "WD") and v["date"]


def test_reference_is_localised_and_has_no_untranslated_suffix_keys():
    en = standards.reference("en")
    blob = json.dumps(en)
    assert "_en\"" not in blob
    assert "Out of support" in en["neo4j"]["versions"][0]["note"] and en["legend"]["end_of_support"] == "end of support"


def test_status_rules_for_neo4j_and_aliases():
    assert standards.status("neo4j", "5.26") == "recommended"
    assert standards.status("neo4j", "5.13") == "obsolete"
    assert standards.status("neo4j", "4.4") == "end_of_support"
    assert standards.status("neo4j", "2026.10") == "supported"
    assert standards.status("neo4j", "2025.06") == "obsolete"
    assert standards.status("curiosity_library", "26.99.1") == "unknown"
    assert standards.normalize("shacl", "1.1") == "1.0"


# ---- contrôle local ---------------------------------------------------------------------------------

def test_default_versions_have_no_gap():
    c = standards.check({}, "fr", base=standards.defaults())
    assert c["gaps"] == [] and c["ok"] and not c["needs_attention"] and c["recommended"] == {}


def test_check_reports_obsolete_end_of_support_newer_unknown_and_incompatible():
    d = standards.defaults()
    c = standards.check({"neo4j": "5.13"}, "fr", base=d)
    g = c["gaps"][0]
    assert (g["key"], g["kind"], g["severity"]) == ("neo4j", "obsolete", "warning") and "n'est plus recommandée" in g["message"]
    assert c["needs_attention"] and c["recommended"] == {"neo4j": "5.26"}
    c = standards.check({"neo4j": "4.4"}, "en", base=d)
    assert c["gaps"][0]["kind"] == "end_of_support" and "out of support" in c["gaps"][0]["message"]
    c = standards.check({"curiosity_library": "26.10.6546"}, "fr", base=d)
    assert [(g["kind"], g["severity"]) for g in c["gaps"]] == [("newer", "info")] and not c["needs_attention"]
    assert c["recommended"] == {"curiosity_library": "26.11.7740"}
    c = standards.check({"curiosity_library": "27.1.1"}, "fr", base=d)
    assert c["gaps"][0]["kind"] == "unknown" and "À VÉRIFIER" in c["gaps"][0]["message"] and not c["needs_attention"]
    c = standards.check({"neo4j": "5.26", "cypher": "25"}, "fr", base=d)
    assert [(g["kind"], g["severity"]) for g in c["gaps"]] == [("incompatible", "error")] and c["recommended"] == {"cypher": "5"}
    c = standards.check({"sparql": "1.2", "rdf": "1.2"}, "fr", base=d)
    assert {g["kind"] for g in c["gaps"]} == {"draft"} and not c["needs_attention"]


def test_check_never_touches_the_network(client, pid, monkeypatch):
    def boom(*a, **k):
        raise AssertionError("appel réseau interdit")
    monkeypatch.setattr(socket.socket, "connect", boom)
    monkeypatch.setattr(socket, "getaddrinfo", boom)
    client.put(f"/api/projects/{pid}/versions", json={"neo4j": "4.4"})
    r = client.get(f"/api/projects/{pid}/versions/check")
    assert r.status_code == 200 and r.json()["needs_attention"]


# ---- API --------------------------------------------------------------------------------------------

def test_standards_endpoint(client):
    r = client.get("/api/standards")
    assert r.status_code == 200
    j = r.json()
    assert j["w3c"]["shacl"]["features"][0]["since"] == "1.2" and j["libraries"]["items"]
    client.put("/api/settings", json={"language": {"ui": "en", "labels": "en", "assistant": "en"}})
    assert client.get("/api/standards").json()["lang"] == "en"


def test_project_versions_get_put_and_validation(client, pid):
    j = client.get(f"/api/projects/{pid}/versions").json()
    assert j["versions"] == standards.defaults() and j["explicit"] == {} and len(j["rows"]) == 6
    r = client.put(f"/api/projects/{pid}/versions", json={"neo4j": "2026.10", "cypher": "25", "shacl": "1.1"})
    assert r.status_code == 200
    assert r.json()["explicit"] == {"neo4j": "2026.10", "cypher": "25", "shacl": "1.0"}
    assert client.get(f"/api/projects/{pid}").json()["target_versions"]["neo4j"] == "2026.10"
    assert client.put(f"/api/projects/{pid}/versions", json={"cypher": None}).json()["explicit"] == {"neo4j": "2026.10", "shacl": "1.0"}
    for bad in ({"neo4j": "cinq"}, {"cypher": "7"}, {"mongo": "1"}, {"curiosity_library": "26.11"}, {"rdf": "2.0"}):
        assert client.put(f"/api/projects/{pid}/versions", json=bad).status_code == 422
    assert client.get("/api/projects/inconnu/versions").status_code == 404


def test_global_default_in_settings_and_old_projects_follow_it(client, pid):
    s = client.get("/api/settings").json()
    assert s["versions"] == standards.defaults() and len(s["versions_view"]) == 6 and s["versions_check"]["gaps"] == []
    assert client.put("/api/settings", json={"versions": {"neo4j": "foo"}}).status_code == 422
    assert client.put("/api/settings", json={"versions": {"curiosity_library": "26.10.6546"}}).status_code == 200
    # le projet n'a rien de propre : il suit le défaut global
    j = client.get(f"/api/projects/{pid}/versions").json()
    assert j["versions"]["curiosity_library"] == "26.10.6546" and j["explicit"] == {}
    assert client.get(f"/api/projects/{pid}/versions/check").json()["versions"]["curiosity_library"] == "26.10.6546"
    # une valeur propre l'emporte
    client.put(f"/api/projects/{pid}/versions", json={"curiosity_library": "26.11.7740"})
    assert client.get(f"/api/projects/{pid}/versions").json()["versions"]["curiosity_library"] == "26.11.7740"
    s = client.get("/api/settings").json()
    assert s["versions_check"]["recommended"] == {"curiosity_library": "26.11.7740"}


def test_old_project_without_target_versions_loads_with_defaults(client, pid, tmp_path):
    pj = tmp_path / "projects" / pid / "project.json"
    d = json.loads(pj.read_text(encoding="utf-8"))
    d.pop("target_versions", None)
    pj.write_text(json.dumps(d), encoding="utf-8")
    assert client.get(f"/api/projects/{pid}").json()["target_versions"] == {}
    assert client.get(f"/api/projects/{pid}/versions").json()["versions"] == standards.defaults()
    assert client.get(f"/api/projects/{pid}/generate/neo4j").status_code == 200
    # un ancien settings.json sans « versions » reprend les valeurs d'usine
    sp = tmp_path / "settings.json"
    if sp.exists():
        s = json.loads(sp.read_text(encoding="utf-8"))
        s.pop("versions", None)
        sp.write_text(json.dumps(s), encoding="utf-8")
    assert client.get("/api/settings").json()["versions"] == standards.defaults()


def test_changing_versions_makes_previous_generation_obsolete_and_is_used_by_generate(client, pid):
    client.get(f"/api/projects/{pid}/generate/neo4j")
    before = client.get(f"/api/projects/{pid}").json()["updated_at"]
    client.put(f"/api/projects/{pid}/versions", json={"neo4j": "2026.10", "cypher": "25"})
    assert client.get(f"/api/projects/{pid}").json()["updated_at"] >= before
    files = client.get(f"/api/projects/{pid}/generate/neo4j").json()["files"]
    assert "Cypher 25" in files["schema.cypher"] and "CYPHER 25 CREATE CONSTRAINT" in files["schema.cypher"]
    assert "| Neo4j | 2026.10 | supportée |" in files["rapport-transposition.md"] and "| Cypher | 25 | supportée |" in files["rapport-transposition.md"]


# ---- générateur Neo4j -------------------------------------------------------------------------------

def test_neo4j_default_versions_keep_the_output_unprefixed():
    out = neo4j.generate(_pg())
    for name in ("schema.cypher", "ingest.cypher", "validation.cypher"):
        assert "CYPHER 5 " not in out[name] and "CYPHER 25 " not in out[name]
        assert "Cible : Neo4j 5.26 · Cypher 5" in out[name]
    assert "Neo4j 5.26 · Cypher 5" in out["README-neo4j.md"]


@pytest.mark.parametrize("cypher,neo", [("25", "2026.10"), ("5", "2026.10")])
def test_neo4j_prefix_on_every_statement(cypher, neo):
    out = neo4j.generate(_pg(neo4j=neo, cypher=cypher))
    pre = f"CYPHER {cypher} "
    for name in ("schema.cypher", "ingest.cypher", "validation.cypher"):
        stmts = _statements(out[name])
        assert stmts, name
        assert all(s.startswith(pre) for s in stmts), [s[:60] for s in stmts if not s.startswith(pre)][:3]
        assert out[name].count("CYPHER " + ("5" if cypher == "25" else "25") + " ") == 0
    # les contraintes Enterprise commentées portent aussi le préfixe (elles seront décommentées telles quelles)
    assert any(l.startswith("// " + pre + "CREATE CONSTRAINT") for l in out["schema.cypher"].splitlines())
    assert "// CREATE CONSTRAINT" not in out["schema.cypher"]


def test_neo4j_cypher25_incompatible_with_5_26_omits_the_prefix_and_warns():
    out = neo4j.generate(_pg(neo4j="5.26", cypher="25"))
    assert "CYPHER 25 " not in out["schema.cypher"].replace("préfixe CYPHER omis", "")
    assert "ATTENTION : Cypher 25 n'existe pas sur Neo4j 5.26" in out["schema.cypher"] and "À VÉRIFIER" in out["schema.cypher"]


def test_neo4j_constraint_syntax_follows_the_version():
    modern = neo4j.generate(_pg(neo4j="5.26"))["schema.cypher"]
    assert "IS :: " in modern and "REQUIRE" in modern
    old = neo4j.generate(_pg(neo4j="5.5"))["schema.cypher"]
    assert "IS :: " not in old.replace("IS :: <TYPE>", "") and "contrainte(s) de type" in old and "5.9+" in old
    assert "REQUIRE" in old
    mid = neo4j.generate(_pg(neo4j="5.9"))["schema.cypher"]
    assert re.search(r"IS :: (?!LIST)", mid)
    legacy = neo4j.generate(_pg(neo4j="4.4"))["schema.cypher"]
    assert "REQUIRE" not in "\n".join(l for l in legacy.splitlines() if l.lstrip("/ ").startswith("CREATE CONSTRAINT"))
    assert re.search(r"CREATE CONSTRAINT \S+ IF NOT EXISTS ON \(n:\w+\) ASSERT n\.\w+ IS UNIQUE;", legacy)
    assert "FOR (n:" in legacy and "hors support" in legacy and "À VÉRIFIER" in legacy
    assert "IS ::" not in "\n".join(l for l in legacy.splitlines() if l.startswith(("CREATE", "// CREATE")))


def test_neo4j_scoped_call_hint_depends_on_version():
    assert "CALL (row) {" in neo4j.generate(_pg(neo4j="5.26"))["ingest.cypher"]
    assert "CALL { WITH row" in neo4j.generate(_pg(neo4j="5.20"))["ingest.cypher"]


# ---- générateur Curiosity, rapport, SHACL ----------------------------------------------------------

def test_curiosity_version_in_headers_and_readme():
    files = curiosity.generate(_pg(curiosity_library="26.10.6546"))
    for name in ("Schema.cs", "Edges.cs", "RegisterSchema.cs", "Connector.cs"):
        assert "Version ciblée : Curiosity.Library 26.10.6546" in files[name]
    assert "dotnet add package Curiosity.Library --version 26.10.6546" in files["README-curiosity.md"]
    assert "Version ciblée : Curiosity.Library 26.10.6546" in files["README-curiosity.md"]
    unk = curiosity.generate(_pg(curiosity_library="27.1.1"))["Schema.cs"]
    assert "version absente de la référence — À VÉRIFIER" in unk
    assert "Curiosity.Library 26.11.7740" in curiosity.generate(_pg())["Schema.cs"]


def test_report_lists_versions_status_and_gaps():
    pg = _pg(neo4j="5.13")
    pg.target = "neo4j"
    md = report.generate(pg)["rapport-transposition.md"]
    assert "## Versions utilisées" in md and "| Neo4j | 5.13 | obsolète |" in md and "| Cypher | 5 | recommandée |" in md
    assert "n'est plus recommandée" in md and "Passer à Neo4j 5.26." in md
    pg.target = "curiosity"
    md = report.generate(pg)["rapport-transposition.md"]
    assert "| Curiosity.Library | 26.11.7740 | recommandée |" in md and "| Neo4j |" not in md


def test_shacl_features_are_marked_and_disabled_in_1_0(client, pid):
    f10 = standards.shacl_features("1.0", "fr")
    assert {x["state"] for x in f10} == {"disabled"} and all(x["since"] == "1.2" for x in f10)
    f12 = standards.shacl_features("1.2", "en")
    assert {x["state"] for x in f12} == {"unavailable"}
    ttl = client.get(f"/api/projects/{pid}/export/shapes").text
    assert not ttl.startswith("# Shapes SHACL")  # SHACL 1.0 : export inchangé octet pour octet
    client.put(f"/api/projects/{pid}/versions", json={"shacl": "1.2"})
    ttl = client.get(f"/api/projects/{pid}/export/shapes").text
    assert "SHACL 1.2" in ttl.splitlines()[0] and "À VÉRIFIER" in ttl.splitlines()[1]
    body = "\n".join(l for l in ttl.splitlines() if not l.startswith("#"))
    assert not any(k in body for k in ("sh:values", "sh:targetWhere", "sh:ShapeClass", "sh:entailment"))
    assert standards.shacl_header("1.1") == ""


# ---- Krakie ----------------------------------------------------------------------------------------

def chat(c, pid, msg):
    r = c.post("/api/assistant/chat", json={"project_id": pid, "messages": [{"role": "user", "content": msg}], "context": {"screen": "tableau"}})
    assert r.status_code == 200, r.text
    return r.json()


@pytest.mark.parametrize("msg", ["quelles versions ?", "Quelles sont les versions", "versions", "quelle version de Neo4j", "which versions?", "What versions are used", "show the versions"])
def test_krakie_answers_which_versions(client, pid, msg):
    client.put(f"/api/projects/{pid}/versions", json={"neo4j": "5.13"})
    j = chat(client, pid, msg)
    assert "Neo4j 5.13" in j["reply"] and "obsol" in j["reply"].lower()
    assert [(a["kind"], a["payload"]["screen"]) for a in j["actions"]] == [("navigate", "versions")]
    assert j["actions"][0]["summary"] in ("Ouvrir les versions", "Open the versions")
    assert not any(a["kind"] == "guided_query" for a in j["actions"])


def test_krakie_answers_in_english_without_french(client, pid):
    client.put("/api/settings", json={"language": {"ui": "en", "labels": "en", "assistant": "en"}})
    client.put(f"/api/projects/{pid}/versions", json={"neo4j": "4.4"})
    j = chat(client, pid, "which versions?")
    assert "Versions targeted by this project" in j["reply"] and "end of support" in j["reply"]
    assert not re.search(r"[éèàçùêâîôûëïœ]", j["reply"])
    assert j["actions"][0]["summary"] == "Open the versions"


@pytest.mark.parametrize("msg", ["mets à jour les versions", "Mettre à jour les versions", "update the versions", "apply recommended versions"])
def test_krakie_proposes_the_recommended_update_but_does_not_apply_it(client, pid, msg):
    client.put(f"/api/projects/{pid}/versions", json={"neo4j": "5.13", "curiosity_library": "26.10.6546"})
    j = chat(client, pid, msg)
    a = j["actions"][0]
    assert a["kind"] == "versions" and a["payload"]["patch"] == {"neo4j": "5.26", "curiosity_library": "26.11.7740"}
    assert [c["to"] for c in a["payload"]["changes"]] == ["5.26", "26.11.7740"] and a["payload"]["before"] == {"neo4j": "5.13", "curiosity_library": "26.10.6546"}
    assert client.get(f"/api/projects/{pid}/versions").json()["explicit"]["neo4j"] == "5.13"  # rien n'est appliqué par le serveur


def test_krakie_update_when_already_recommended(client, pid):
    j = chat(client, pid, "mets à jour les versions")
    assert "déjà" in j["reply"] and [a["kind"] for a in j["actions"]] == ["navigate"]


def test_krakie_open_the_versions_screen_by_name(client, pid):
    j = chat(client, pid, "ouvre les versions")
    assert [(a["kind"], a["payload"]["screen"]) for a in j["actions"]] == [("navigate", "versions")]
