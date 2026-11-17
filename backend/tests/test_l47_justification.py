"""L47 : reclassement « auto », trace des décisions (qui, quand, pourquoi), arbitrage par branche, dossier de justification."""
import re

import pytest
from fastapi.testclient import TestClient

from ontoforge.main import app as main_app

AM = "https://w3id.org/ontoforge/automaint#"


@pytest.fixture
def c(tmp_path, monkeypatch):
    monkeypatch.setenv("ONTOFORGE_DATA", str(tmp_path))
    return TestClient(main_app)


@pytest.fixture
def pid(c):
    return c.post("/api/projects", json={"name": "L47 test", "sample": "automaint"}).json()["id"]


def pending(pg):
    return [f for f in pg["findings"] if f["severity"] in ("review", "lost") and not f["chosen"]]


def test_reclassement_auto_par_cible(c, pid):
    neo = c.post(f"/api/projects/{pid}/analyze?target=neo4j").json()
    cur = c.post(f"/api/projects/{pid}/analyze?target=curiosity").json()
    assert len(pending(neo)) < 25
    assert {f["rule"] for f in neo["findings"] if f["auto_reason"]} == {"D13", "O09", "O10", "D09"}
    # Curiosity : D13, O10 et O09 (exactly/min) restent un vrai choix (le connecteur échoue sur violation)
    assert {f["rule"] for f in cur["findings"] if f["auto_reason"]} == {"D09"}
    assert {"D13", "O10", "O09"} <= {f["rule"] for f in pending(cur)}
    for pg in (neo, cur):
        assert all(f["severity"] == "auto" and f["options"] for f in pg["findings"] if f["auto_reason"])


def test_lost_jamais_reclasse(c, pid):
    pg = c.post(f"/api/projects/{pid}/analyze?target=neo4j").json()
    lost = [f for f in pg["findings"] if f["severity"] == "lost"]
    assert lost and all(not f["auto_reason"] for f in lost)
    pg = c.post(f"/api/projects/{pid}/decisions/neo4j/accept-recommended").json()
    assert all(not f["chosen"] for f in pg["findings"] if f["severity"] == "lost")


def test_single_option_hook(monkeypatch):
    from ontoforge.io.rdf_import import parse_ontology
    from ontoforge.mapping.engine import analyze
    from ontoforge.mapping.rules import catalog
    onto, _ = parse_ontology(open("../samples/trap/trap.ttl", "rb").read(), filename="trap.ttl")
    assert any(f.rule == "R02" and f.severity == "review" for f in analyze(onto, None, "neo4j").findings)
    monkeypatch.setattr(catalog, "SINGLE_OPTION_AUTO", {"R02"})
    got = [f for f in analyze(onto, None, "neo4j").findings if f.rule == "R02"]
    assert got and all(f.severity == "auto" and f.auto_reason for f in got)


def test_ancien_format_et_raison(c, pid):
    pg = c.post(f"/api/projects/{pid}/analyze?target=neo4j").json()
    f = next(x for x in pending(pg) if x["rule"] == "C08")
    opt = f["recommended"]
    # ancien format plat : choix sans raison, auteur local
    pg = c.put(f"/api/projects/{pid}/decisions/neo4j", json={f["id"]: opt}).json()
    assert pg["decisions"][f["id"]] == opt
    n = pg["decision_notes"][f["id"]]
    assert n["reason"] == "" and n["by"] == "local" and n["at"]
    # raison fournie, mise sur une ligne
    pg = c.put(f"/api/projects/{pid}/decisions/neo4j", json={"decisions": {f["id"]: opt}, "reason": "  a\n b\t c "}).json()
    assert pg["decision_notes"][f["id"]]["reason"] == "a b c"
    # rejouer sans raison : conservée
    pg = c.put(f"/api/projects/{pid}/decisions/neo4j", json={f["id"]: opt}).json()
    assert pg["decision_notes"][f["id"]]["reason"] == "a b c"
    # autre option sans raison : raison effacée
    other = next(o["id"] for o in f["options"] if o["id"] != opt)
    pg = c.put(f"/api/projects/{pid}/decisions/neo4j", json={f["id"]: other}).json()
    assert pg["decision_notes"][f["id"]]["reason"] == "" and pg["decision_notes"][f["id"]]["option"] == other
    # retrait : la trace disparaît
    pg = c.put(f"/api/projects/{pid}/decisions/neo4j", json={f["id"]: None}).json()
    assert f["id"] not in pg["decision_notes"] and f["id"] not in pg["decisions"]


def test_raison_refusee(c, pid):
    f = pending(c.post(f"/api/projects/{pid}/analyze?target=neo4j").json())[0]
    r = c.put(f"/api/projects/{pid}/decisions/neo4j", json={"decisions": {f["id"]: f["recommended"]}, "reason": "x" * 400})
    assert r.status_code == 422
    r = c.put(f"/api/projects/{pid}/decisions/neo4j", json={"decisions": {f["id"]: f["recommended"]}, "reason": 5})
    assert r.status_code == 422
    assert c.get(f"/api/projects/{pid}").json()["decisions"]["neo4j"] == {}


def test_projet_sans_notes_se_charge(c, pid):
    import json
    from ontoforge.projects import store
    path = store.project_dir(pid) / "project.json"
    d = json.loads(path.read_text(encoding="utf-8"))
    d.pop("decision_notes", None)
    d["decisions"]["neo4j"] = {"C08:" + AM + "Fuel": "reference_nodes"}
    path.write_text(json.dumps(d), encoding="utf-8")
    pg = c.post(f"/api/projects/{pid}/analyze?target=neo4j")
    assert pg.status_code == 200 and pg.json()["decision_notes"] == {}


def test_branche(c, pid):
    pg = c.post(f"/api/projects/{pid}/analyze?target=neo4j").json()
    rooted = [f for f in pg["findings"] if f["root"]]
    assert {f["rule"] for f in rooted} <= {"C02", "C03", "C04", "C10"} and rooted
    root = rooted[0]["root"]
    r = c.post(f"/api/projects/{pid}/decisions/neo4j/branch", json={"root": root, "reason": "cohérence de la branche"})
    assert r.status_code == 200
    body = r.json()
    ids = {f["id"] for f in rooted if f["root"] == root}
    assert set(body["applied"]) == ids
    notes = body["model"]["decision_notes"]
    assert all(notes[i]["via"] == "branch" and notes[i]["reason"] == "cohérence de la branche" for i in ids)
    # option imposée : exige la règle
    assert c.post(f"/api/projects/{pid}/decisions/neo4j/branch", json={"root": root, "option": "node_type"}).status_code == 422
    r = c.post(f"/api/projects/{pid}/decisions/neo4j/branch", json={"root": root, "rule": "C02", "option": "node_type"}).json()
    assert r["applied"] and all(i.startswith("C02:") for i in r["applied"])
    # décision d'un autre compte (ou sans auteur connu) : protégée sans `overwrite`
    import json
    from ontoforge.projects import store
    path = store.project_dir(pid) / "project.json"
    d = json.loads(path.read_text(encoding="utf-8"))
    for n in d["decision_notes"]["neo4j"].values():
        n["by"] = "autre"
    path.write_text(json.dumps(d), encoding="utf-8")
    r = c.post(f"/api/projects/{pid}/decisions/neo4j/branch", json={"root": root, "rule": "C02", "option": "multi_label"}).json()
    assert r["applied"] == [] and r["skipped"]
    r = c.post(f"/api/projects/{pid}/decisions/neo4j/branch", json={"root": root, "rule": "C02", "option": "multi_label", "overwrite": True}).json()
    assert r["applied"]
    assert c.post(f"/api/projects/{pid}/decisions/neo4j/branch", json={"root": "urn:inconnu"}).status_code == 404


def _prepare(c, pid):
    f = next(x for x in pending(c.post(f"/api/projects/{pid}/analyze?target=neo4j").json()) if x["severity"] == "review")
    c.put(f"/api/projects/{pid}/decisions/neo4j", json={"decisions": {f["id"]: f["options"][-1]["id"]}, "reason": "choix <b>perso</b> | [x](javascript:alert(1))"})
    c.post(f"/api/projects/{pid}/decisions/neo4j/accept-recommended")
    return f


def test_dossier_html_et_md(c, pid):
    f = _prepare(c, pid)
    c.put(f"/api/projects/{pid}", json={"name": "<img src=x onerror=alert(1)>"})
    h = c.get(f"/api/projects/{pid}/justification/neo4j?format=html")
    assert h.status_code == 200 and h.headers["content-type"].startswith("text/html")
    assert "default-src 'none'" in h.headers["content-security-policy"] and "script" not in h.headers["content-security-policy"]
    t = h.text
    assert 'http-equiv="Content-Security-Policy" content="default-src &#x27;none&#x27;' in t
    for bad in ("<script", "<img", "onerror=", "javascript:alert(1)</", "@import", "url(", "<iframe", "<link"):
        assert bad not in t, bad
    assert not re.search(r"(src|href)=[\"']?(https?:|//)", t)
    assert "&lt;b&gt;perso&lt;/b&gt;" in t and f["id"].split(":")[0] in t
    for sec in ("Ce qui est perdu", "Ce qui est compensé", "Décisions humaines", "Recommandations non suivies", "Reclassés sans choix"):
        assert sec in t
    m = c.get(f"/api/projects/{pid}/justification/neo4j?format=md")
    assert m.status_code == 200 and m.headers["content-type"].startswith("text/markdown")
    assert "\\<b\\>perso" in m.text and "\\[x\\]" in m.text and "<img" not in m.text   # mise en forme et liens neutralisés
    rows = [l for l in m.text.splitlines() if l.startswith("|")]
    assert rows and all(len(re.findall(r"(?<!\\)\|", l)) >= 3 for l in rows)
    assert c.get(f"/api/projects/{pid}/justification/neo4j?format=pdf").status_code == 422
    assert c.get(f"/api/projects/{pid}/justification/autre").status_code == 422


def test_dossier_anglais_et_lecture_seule(c, pid):
    _prepare(c, pid)
    en = c.get(f"/api/projects/{pid}/justification/curiosity?format=md&lang=en").text
    assert "Justification file" in en and "Dossier de justification" not in en
    assert "What is lost" in en
    assert c.get(f"/api/projects/{pid}/justification/curiosity?lang=de").status_code == 422
    n = len(c.get(f"/api/projects/{pid}/generations").json())
    c.get(f"/api/projects/{pid}/justification/curiosity")
    assert len(c.get(f"/api/projects/{pid}/generations").json()) == n  # lecture : aucune trace de génération


def test_routes_classees():
    from ontoforge.collab.routes import ROUTES
    assert ROUTES[("GET", "/api/projects/{pid}/justification/{target}")][0] == "read"
    assert ROUTES[("POST", "/api/projects/{pid}/decisions/{target}/branch")][0] == "write"


# ---- droits (L40/L42) : le lecteur lit le dossier, n'écrit aucune décision -------------------------------------------------------
from test_collab import _fresh_limits, add, users  # noqa: E402,F401
from test_collab import app  # noqa: E402,F401,F811  (fixture module, requis par `users`)


def test_lecteur_lit_le_dossier_sans_ecrire(users):
    a, b = users[0], users[1]
    pid = a.post("/api/projects", json={"name": "Droits", "sample": "automaint"}, rev=None).json()["id"]
    add(a, pid, b.name, "reader")
    f = next(x for x in a.post(f"/api/projects/{pid}/analyze?target=neo4j", rev=None).json()["findings"] if x["severity"] == "review")
    body = {"decisions": {f["id"]: f["recommended"]}, "reason": "ok"}
    assert b.put(f"/api/projects/{pid}/decisions/neo4j", json=body).status_code == 403
    assert b.post(f"/api/projects/{pid}/decisions/neo4j/branch", json={"root": "x"}).status_code == 403
    assert a.put(f"/api/projects/{pid}/decisions/neo4j", json=body).status_code == 200
    r = b.get(f"/api/projects/{pid}/justification/neo4j?format=md", rev=None)
    assert r.status_code == 200 and a.name in r.text
    # projet inaccessible à un tiers : 404
    assert users[2].get(f"/api/projects/{pid}/justification/neo4j", rev=None).status_code == 404
