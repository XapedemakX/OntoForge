"""L52 : tests de non-régression des défauts DF-B01 à DF-B11, DF-F03 relevés par L51 (journal/L51/defauts.md).

Chaque test échouait avant la correction (voir journal/L52/corrections-backend.md)."""
from __future__ import annotations


# ---- DF-B01 : une seule variable LABEL_LANG (core/lang.py)
def test_b01_label_lang_has_a_single_definition():
    from ontoforge import localize
    from ontoforge.core import lang
    assert not hasattr(localize, "LABEL_LANG"), "doublon mort de core.lang.LABEL_LANG"
    assert lang.LABEL_LANG.get() == "fr"


# ---- DF-B02 : export de l'ontologie en n3 et trig (500 avant)
import os  # noqa: E402

import pytest  # noqa: E402
import rdflib  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from rdflib.compare import isomorphic  # noqa: E402


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("ONTOFORGE_DATA", str(tmp_path))
    monkeypatch.setenv("ONTOFORGE_LLM_PROVIDER", "mock")
    from ontoforge.main import app
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def pid(client):
    r = client.post("/api/projects", json={"name": "t", "sample": "automaint"})
    assert r.status_code in (200, 201), r.text
    return r.json()["id"]


def test_b02_every_advertised_format_is_serializable():
    from ontoforge.api.projects import ONTO_MEDIA
    from ontoforge.io.rdf_export import FORMATS
    assert set(ONTO_MEDIA) <= set(FORMATS)


@pytest.mark.parametrize("fmt,media", [("n3", "text/n3"), ("trig", "application/trig")])
def test_b02_export_n3_and_trig_are_faithful(client, pid, fmt, media):
    ref = rdflib.Graph().parse(data=client.get(f"/api/projects/{pid}/export/ontology?format=nt").text, format="nt")
    r = client.get(f"/api/projects/{pid}/export/ontology?format={fmt}")
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith(media)
    assert r.headers["content-disposition"].endswith(f'.{fmt}"')
    if fmt == "trig":
        ds = rdflib.Dataset()
        ds.parse(data=r.text, format="trig")
        got = rdflib.Graph()
        for s, p, o, _ in ds.quads((None, None, None, None)):
            got.add((s, p, o))
    else:
        got = rdflib.Graph().parse(data=r.text, format="n3")
    assert len(got) == len(ref) and isomorphic(got, ref)


# ---- DF-B03 : owlrl en processus fils tué au délai (avant : fil daemon qui continuait après le délai)
def _transitive_chain(n: int) -> rdflib.Graph:
    from rdflib import OWL, RDF, URIRef
    g, ex = rdflib.Graph(), "http://example.org/b03#"
    p = URIRef(ex + "p")
    g.add((p, RDF.type, OWL.ObjectProperty))
    g.add((p, RDF.type, OWL.TransitiveProperty))
    for i in range(n):
        g.add((URIRef(f"{ex}i{i}"), p, URIRef(f"{ex}i{i + 1}")))
    return g


def _owlrl_children() -> list[str]:
    """Fils owlrl de CE processus encore présents (vivants ou zombies)."""
    out = []
    for d in os.listdir("/proc"):
        if d.isdigit():
            try:
                with open(f"/proc/{d}/stat", "rb") as f:
                    ppid = int(f.read().rsplit(b")", 1)[1].split()[1])
                with open(f"/proc/{d}/cmdline", "rb") as f:
                    if ppid == os.getpid() and b"_owlrl_worker.py" in f.read():
                        out.append(d)
            except (OSError, ValueError, IndexError):
                pass
    return out


def test_b03_owlrl_timeout_is_enforced_and_child_killed():
    import threading
    import time
    from ontoforge.conformance.reasoner import reason
    g = _transitive_chain(400)  # mesuré : bien plus de 30 s de calcul owlrl
    threads = threading.active_count()
    t0 = time.monotonic()
    info = reason(g, timeout=2)
    elapsed = time.monotonic() - t0
    assert info.used == "none" and info.consistent is None
    assert any("délai de 2 s dépassé" in n for n in info.notes)
    assert elapsed < 4.0, f"délai non tenu : {elapsed:.2f} s"
    assert threading.active_count() == threads  # plus de fil abandonné
    time.sleep(0.2)
    assert _owlrl_children() == []  # le fils a été tué


def test_b03_owlrl_result_unchanged_in_child():
    from rdflib import OWL, RDF, RDFS, URIRef
    from ontoforge.conformance.reasoner import reason
    ex = "http://example.org/b03#"
    g = rdflib.Graph()
    a, b, c = (URIRef(ex + x) for x in "ABC")
    for x in (a, b, c):
        g.add((x, RDF.type, OWL.Class))
    g.add((a, OWL.disjointWith, b))
    g.add((c, RDFS.subClassOf, a))
    g.add((c, RDFS.subClassOf, b))
    info = reason(g, timeout=30)
    assert info.used == "owlrl" and info.unsatisfiable == [ex + "C"]


def test_b03_owlrl_busy_slots_give_a_note(monkeypatch):
    import threading
    from ontoforge.conformance import reasoner
    monkeypatch.setattr(reasoner, "_SLOTS", threading.BoundedSemaphore(1))
    reasoner._SLOTS.acquire()
    info = reasoner.reason(_transitive_chain(3), timeout=5)
    assert info.used == "none" and any("trop de raisonnements" in n for n in info.notes)


# ---- DF-B04 : variables HermiT non numériques → valeur par défaut + journal (avant : 500 ou module impossible à importer)
def test_b04_invalid_hermit_timeouts_fall_back_with_a_log(monkeypatch, caplog):
    import logging
    from ontoforge.conformance import hermit
    monkeypatch.setenv("ONTOFORGE_HERMIT_TIMEOUT", "abc")
    monkeypatch.setenv("ONTOFORGE_HERMIT_MAX_TIMEOUT", "beaucoup")
    monkeypatch.setenv("ONTOFORGE_HERMIT_MAX_MB", "nan")
    with caplog.at_level(logging.WARNING, logger="ontoforge.conformance.hermit"):
        assert hermit.configured_timeout() == hermit.DEFAULT_TIMEOUT
        assert hermit.configured_timeout(500) == hermit.MAX_TIMEOUT
        assert hermit.configured_memory() == hermit.DEFAULT_MAX_MB
    assert "ONTOFORGE_HERMIT_TIMEOUT" in caplog.text and "ONTOFORGE_HERMIT_MAX_TIMEOUT" in caplog.text
    monkeypatch.setenv("ONTOFORGE_HERMIT_TIMEOUT", "nan")
    assert hermit.configured_timeout() == hermit.DEFAULT_TIMEOUT
    monkeypatch.setenv("ONTOFORGE_HERMIT_TIMEOUT", "12")
    assert hermit.configured_timeout() == 12.0


def test_b04_invalid_hermit_slots_does_not_break_import():
    import subprocess
    import sys
    env = dict(os.environ, ONTOFORGE_HERMIT_SLOTS="deux", PYTHONPATH=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    r = subprocess.run([sys.executable, "-c", "from ontoforge.conformance import hermit; print(hermit._SLOTS._initial_value)"],
                       env=env, capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip() == "2" and "ONTOFORGE_HERMIT_SLOTS" in r.stderr


def test_b04_reason_route_survives_invalid_timeout(client, pid, monkeypatch):
    monkeypatch.setenv("ONTOFORGE_HERMIT_TIMEOUT", "abc")
    r = client.post(f"/api/projects/{pid}/reason", json={"reasoner": "hermit"})
    assert r.status_code in (200, 501, 503), r.text  # 501 sans Java : jamais 500


# ---- DF-B05 : condition toujours vraie retirée (le bloc Curiosity reste toujours exécuté)
def test_b05_no_always_true_condition_in_translate():
    import inspect
    from ontoforge.queries import translate as tr
    assert "or True" not in inspect.getsource(tr.translate)


def test_b05_no_always_true_condition_anywhere_in_backend():
    """Revue L52 it1 : le motif « … or True » (condition toujours vraie, reste d'essai) ne doit revenir nulle part dans le code."""
    import io
    import tokenize
    from pathlib import Path
    root = Path(__file__).resolve().parents[1] / "ontoforge"
    found = []
    for path in sorted(root.rglob("*.py")):
        toks = [t for t in tokenize.generate_tokens(io.StringIO(path.read_text(encoding="utf-8")).readline)
                if t.type not in (tokenize.COMMENT, tokenize.NL, tokenize.NEWLINE, tokenize.INDENT, tokenize.DEDENT)]
        for a, b in zip(toks, toks[1:]):
            if a.string == "or" and b.string == "True":
                found.append(f"{path.relative_to(root)}:{a.start[0]}")
    assert not found, found


# ---- DF-B06 : classe portée par plusieurs types de nœuds partageant un label (avant : MATCH (v), tous les nœuds)
AM = "https://w3id.org/ontoforge/automaint#"


def _cypher(client, pid, sparql, target="neo4j"):
    r = client.post(f"/api/projects/{pid}/queries/translate?target={target}", json={"sparql": sparql})
    assert r.status_code == 200, r.text
    return r.json()


def test_b06_shared_label_is_kept_on_neo4j(client, pid):
    j = _cypher(client, pid, f"PREFIX am: <{AM}> SELECT ?v WHERE {{ ?v a am:Vehicle }}")
    assert j["cypher"].startswith("MATCH (v:Vehicle)\n"), j["cypher"]
    assert not j["lossy"]
    j = _cypher(client, pid, f"PREFIX am: <{AM}> SELECT ?o ?v WHERE {{ ?o am:concerns ?v . ?v a am:Vehicle }}")
    assert "(v:Vehicle)" in j["cypher"], j["cypher"]
    j = _cypher(client, pid, f"PREFIX am: <{AM}> SELECT ?v WHERE {{ ?v a am:Vehicle . ?v a am:ElectricVehicle }}")
    assert j["cypher"].startswith("MATCH (v:ElectricVehicle)\n"), j["cypher"]


def test_b06_union_of_labels_and_discriminators():
    from ontoforge.queries.translate import ClassRef, NodeVar, _Translator
    from ontoforge.core.pg_model import PGModel
    t = _Translator(PGModel(target="neo4j"), None)
    t.nodes["v"] = NodeVar(name="v", sparql="v", types=[ClassRef("A", "A"), ClassRef("B", "B")])
    assert t.node_pat("v", set()) == ("(v)", ["(v:A OR v:B)"])
    t.nodes["w"] = NodeVar(name="w", sparql="w", types=[ClassRef("A", "X", "kind", "a1"), ClassRef("B", "X")])
    assert t.node_pat("w", set()) == ("(w:X)", [])  # la référence sans discriminant absorbe l'autre
    t.nodes["z"] = NodeVar(name="z", sparql="z", types=[ClassRef("A", "X", "kind", "a1"), ClassRef("B", "Y")])
    assert t.node_pat("z", set()) == ("(z)", ["(z:Y OR (z:X AND z.kind = 'a1'))"])


def test_b06_type_without_label_gives_an_explicit_loss():
    """Garde-fou de node_pat (revue query it1) : un type possible sans label → motif non filtré, mais note [perte] explicite."""
    from ontoforge.core.pg_model import PGModel
    from ontoforge.queries.translate import ClassRef, NodeVar, _Translator
    t = _Translator(PGModel(target="neo4j"), None)
    t.nodes["v"] = NodeVar(name="v", sparql="v", types=[ClassRef("A", None), ClassRef("B", "B")])
    assert t.node_pat("v", set()) == ("(v)", [])
    assert [lvl for lvl, _ in t.notes] == ["perte"]
    assert "n'a pas de label" in t.notes[0][1] and "?v" in t.notes[0][1]


def test_b06_curiosity_target_output_unchanged(client, pid):
    """Revue query it1 : la cible curiosity (type aplati avec discriminant) garde la même sortie qu'avant DF-B06."""
    j = _cypher(client, pid, f"PREFIX am: <{AM}> SELECT ?v WHERE {{ ?v a am:Vehicle }}", target="curiosity")
    assert j["cypher"] == "MATCH (v:Vehicle)\nRETURN v.Uri AS v"
    j = _cypher(client, pid, f"PREFIX am: <{AM}> SELECT ?v WHERE {{ ?v a am:ElectricVehicle }}", target="curiosity")
    assert j["cypher"] == "MATCH (v:Vehicle)\nWHERE v.VehicleKind = 'ElectricVehicle'\nRETURN v.Uri AS v"


# ---- DF-B07 : inférence du triplestore local par childproc.run_limited (avant : subprocess.run, environnement complet, sans plafond)
INFER_TTL = ("@prefix am: <https://w3id.org/ontoforge/automaint#> .\n"
             "<http://example.org/t1> a am:Technician .\n")


def _load(client, pid, name, text, **form):
    return client.post(f"/api/projects/{pid}/store/load", files={"file": (name, text.encode("utf-8"))}, data=form)


def test_b07_inference_child_is_limited_and_gets_no_secret(client, pid, monkeypatch):
    import subprocess
    calls = []
    real = subprocess.run

    def spy(cmd, *a, **kw):
        calls.append((cmd, kw))
        return real(cmd, *a, **kw)

    monkeypatch.setenv("ONTOFORGE_FAKE_SECRET_L52", "ne-doit-pas-sortir")
    monkeypatch.setattr(subprocess, "run", spy)
    r = _load(client, pid, "t.ttl", INFER_TTL, inference="rdfs")
    assert r.status_code == 200, r.text
    assert r.json()["inference"]["triples"] > 0
    infer = [(c, kw) for c, kw in calls if any(str(x).endswith("_infer_worker.py") for x in c)]
    assert infer, calls
    cmd, kw = infer[0]
    assert "-I" in cmd and any("RLIMIT_AS" in str(x) for x in cmd)  # lanceur de childproc : plafonds posés
    assert kw.get("env") is not None and "ONTOFORGE_FAKE_SECRET_L52" not in kw["env"]
    assert kw.get("start_new_session") is True and cmd[-1] == "rdfs"


@pytest.mark.parametrize("rc,err", [(-9, b""), (-24, b""), (3, b"MemoryError\n")])  # SIGKILL, SIGXCPU (RLIMIT_CPU), MemoryError (RLIMIT_AS)
def test_b07_inference_killed_by_a_cap_gives_a_clean_413(client, pid, monkeypatch, rc, err):
    import subprocess
    from ontoforge import childproc
    monkeypatch.setattr(childproc, "run_limited", lambda *a, **k: subprocess.CompletedProcess(a, rc, b"", err))
    r = _load(client, pid, "t.ttl", INFER_TTL, inference="owlrl")
    assert r.status_code == 413, r.text  # avant : 500 (stderr vide → IndexError)
    assert "mémoire ou temps de calcul plafonnés" in r.json()["detail"]


# ---- DF-B08 : chargement du triplestore local passé par io/safe_parse.py (avant : entités internes développées, 200)
ENTITY_XML = ('<?xml version="1.0"?><!DOCTYPE rdf:RDF [<!ENTITY a "aaaaaaaaaa"><!ENTITY b "&a;&a;&a;&a;&a;&a;&a;&a;&a;&a;">'
              '<!ENTITY c "&b;&b;&b;&b;&b;&b;&b;&b;&b;&b;">]>'
              '<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#" xmlns:ex="http://example.org/">'
              '<rdf:Description rdf:about="http://example.org/a"><ex:p>&c;</ex:p></rdf:Description></rdf:RDF>')


def test_b08_rdfxml_with_internal_entities_is_refused(client, pid):
    r = _load(client, pid, "x.rdf", ENTITY_XML)
    assert r.status_code == 422, r.text
    assert "DOCTYPE" in r.json()["detail"]
    s = client.get(f"/api/projects/{pid}/store/stats").json()
    assert not any(g["name"] == "x.rdf" for g in s["graphs"])  # rien n'a été écrit


def test_b08_refusal_is_translated(client, pid):
    assert client.put("/api/settings", json={"language": {"ui": "en", "labels": "en", "assistant": "en"}}).status_code == 200
    r = _load(client, pid, "x.owl", ENTITY_XML)
    assert r.status_code == 422 and "RDF/XML file refused" in r.json()["detail"], r.text


def test_b08_deep_jsonld_is_refused_and_plain_rdfxml_still_loads(client, pid):
    deep = '{"@context": {"ex": "http://example.org/"}, "@id": "ex:a", "ex:p": ' + "[" * 300 + '"v"' + "]" * 300 + "}"
    r = _load(client, pid, "d.jsonld", deep)
    assert r.status_code == 422 and "imbrication" in r.json()["detail"], r.text
    ok = ('<?xml version="1.0"?><rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#" xmlns:ex="http://example.org/">'
          '<rdf:Description rdf:about="http://example.org/a"><ex:p>v</ex:p></rdf:Description></rdf:RDF>')
    r = _load(client, pid, "ok.rdf", ok)
    assert r.status_code == 200, r.text
    assert next(g for g in r.json()["graphs"] if g["name"] == "ok.rdf")["triples"] == 1


# ---- DF-F03 : refus des couches ASGI traduits (avant : français seulement)
PW = "correct horse battery"


def _auth_app(monkeypatch, tmp_path, **env):
    from ontoforge.auth import limiter, passwords
    from ontoforge.main import create_app
    base = {"ONTOFORGE_AUTH": "password", "ONTOFORGE_AUTH_USERS": f"demo:{passwords.hash_password(PW)}",
            "ONTOFORGE_SECRET_KEY": "k" * 48, "ONTOFORGE_DATA": str(tmp_path)}
    base.update(env)
    for k in ("ONTOFORGE_AUTH_USERS_FILE", "ONTOFORGE_PUBLIC", "ONTOFORGE_SESSION_HOURS", "ONTOFORGE_MAX_BODY_MB"):
        monkeypatch.delenv(k, raising=False)
    for k, v in base.items():
        monkeypatch.setenv(k, v)
    limiter.reset()
    c = TestClient(create_app(), base_url="https://testserver")
    csrf = c.post("/api/auth/login", json={"username": "demo", "password": PW}).json()["csrf"]
    return c, csrf


def test_f03_csrf_and_origin_refusals_follow_the_account_language(monkeypatch, tmp_path):
    c, csrf = _auth_app(monkeypatch, tmp_path)
    r = c.post("/api/projects", json={"name": "x"})
    assert r.json() == {"detail": "Jeton CSRF absent ou invalide : rechargez la page.", "code": "csrf"}  # français par défaut
    assert c.put("/api/auth/preferences", json={"lang": "en"}, headers={"X-CSRF-Token": csrf}).status_code == 200
    r = c.post("/api/projects", json={"name": "x"})
    assert r.status_code == 403 and r.json() == {"detail": "Missing or invalid CSRF token: reload the page.", "code": "csrf"}
    r = c.post("/api/projects", json={"name": "x"}, headers={"X-CSRF-Token": csrf, "Origin": "https://evil.example"})
    assert r.status_code == 403 and r.json() == {"detail": "Origin refused.", "code": "bad_origin"}


def test_f03_unclassified_and_413_follow_the_interface_language(monkeypatch, tmp_path):
    from ontoforge.auth.middleware import localized
    from ontoforge.localize import REQUEST_LANG
    tok = REQUEST_LANG.set("en")
    try:
        assert localized("Route non classée.") == "Unclassified route."
        assert localized("Connexion requise.") == "Sign-in required."
        assert localized("Route non classée.", "fr") == "Route non classée."
    finally:
        REQUEST_LANG.reset(tok)
    c, csrf = _auth_app(monkeypatch, tmp_path, ONTOFORGE_MAX_BODY_MB="1")
    big = b"x" * (1024 * 1024 + 10)
    h = {"content-type": "application/json", "X-CSRF-Token": csrf}
    assert c.post("/api/projects", content=big, headers=h).json()["detail"] == "Requête trop volumineuse (plafond 1 Mo)."
    r = c.put("/api/settings", json={"language": {"ui": "en", "labels": "en", "assistant": "en"}}, headers={"X-CSRF-Token": csrf})
    assert r.status_code == 200, r.text
    r = c.post("/api/projects", content=big, headers=h)
    assert r.status_code == 413 and r.json()["detail"] == "Request too large (limit 1 MB)."
    r = c.post("/api/projects", content=(big[i:i + 65536] for i in range(0, len(big), 65536)), headers=h)  # sans Content-Length
    assert r.status_code == 413 and r.json()["detail"] == "Request too large (limit 1 MB)."


# ---- DF-B08, revue secu it1 : la garde RDF/XML du triplestore local échoue fermée (avant : en-tête mal formé → 200, entités développées)
_ENT = ('<!DOCTYPE rdf:RDF [<!ENTITY a "aaaaaaaaaa"><!ENTITY b "&a;&a;&a;&a;&a;&a;&a;&a;&a;&a;"><!ENTITY c "&b;&b;&b;&b;&b;&b;&b;&b;&b;&b;">]>'
        '<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#" xmlns:ex="http://example.org/">'
        '<rdf:Description rdf:about="http://example.org/a"><ex:p>&c;</ex:p></rdf:Description></rdf:RDF>')
_DECL = '<?xml version="1.0"?>'


@pytest.mark.parametrize("name,doc", [
    ("canonique", _DECL + _ENT),
    ("ligne_vide", "\n" + _DECL + _ENT),
    ("espace", " " + _DECL + _ENT),
    ("commentaire_tirets", _DECL + "<!-- a -- b -->" + _ENT),
    ("standalone", '<?xml version="1.0" standalone="maybe"?>' + _ENT),
    ("nul", _DECL + "<!-- \x00 -->" + _ENT),
    ("controle", _DECL + "<!-- \x01 -->" + _ENT),
    ("fin_tirets", _DECL + "<!-- a --->" + _ENT),
    ("encodage_inconnu", '<?xml version="1.0" encoding="x-inconnu"?>' + _ENT),
])
def test_b08_malformed_rdfxml_header_fails_closed(client, pid, name, doc):
    r = _load(client, pid, "x.rdf", doc)
    assert r.status_code == 422, (name, r.status_code, r.text[:200])
    assert "RDF/XML refusé" in r.json()["detail"]
    s = client.get(f"/api/projects/{pid}/store/stats").json()
    assert not any(g["name"] == "x.rdf" for g in s["graphs"])


def test_b08_valid_rdfxml_still_loads_in_the_store(client, pid):
    from pathlib import Path
    owl = (Path(__file__).resolve().parents[2] / "samples" / "automaint" / "automaint.owl").read_bytes()
    r = client.post(f"/api/projects/{pid}/store/load", files={"file": ("automaint.owl", owl)})
    assert r.status_code == 200, r.text[:300]
    bom = "﻿" + _DECL + ('<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#" xmlns:ex="http://example.org/">'
                             '<!-- commentaire --><rdf:Description rdf:about="http://example.org/b"><ex:p>w</ex:p></rdf:Description></rdf:RDF>')
    r = _load(client, pid, "bom.rdf", bom)
    assert r.status_code == 200, r.text[:300]


def test_b08_parse_into_is_unchanged_for_malformed_headers():
    from ontoforge.io import safe_parse
    safe_parse.check_xml("\n" + _DECL + "<a/>")  # non strict : ne juge pas (rdflib refusera lui-même)
    with pytest.raises(safe_parse.UnsafeRdfError):
        safe_parse.check_xml("\n" + _DECL + "<a/>", strict=True)


# ---- revue secu it1 : littéral ou IRI de plus de 16 Mio au chargement du triplestore local (avant : MemoryError, 500)
@pytest.mark.parametrize("name,doc", [
    ("big.ttl", b'<http://e/a> <http://e/p> "' + b"x" * (17 * 1024 * 1024) + b'" .\n'),
    ("big.nt", b"<http://e/" + b"y" * (17 * 1024 * 1024) + b'> <http://e/p> "v" .\n'),
])
def test_store_oversized_element_gives_a_clean_413(client, pid, name, doc):
    r = client.post(f"/api/projects/{pid}/store/load", files={"file": (name, doc)})
    assert r.status_code == 413, r.text[:200]
    assert "trop gros pour le lecteur RDF" in r.json()["detail"]
    assert client.post(f"/api/projects/{pid}/store/load", files={"file": ("ok.ttl", b'<http://e/a> <http://e/p> "v" .\n')}).status_code == 200
