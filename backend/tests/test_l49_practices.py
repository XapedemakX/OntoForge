"""L49 : bonnes pratiques (BP08–BP16, complétude), dépréciation de bout en bout, versions SemVer, en-tête d'ontologie."""
import pathlib

import pytest
from fastapi.testclient import TestClient

from ontoforge.conformance import practices as bp
from ontoforge.conformance.lint import lint
from ontoforge.conformance.profiles import check_conformance
from ontoforge.core.onto_model import (Annotation, DatatypeProperty, ObjectProperty, OntClass, OntologyMeta, OntoModel)
from ontoforge.core.project import Project
from ontoforge.editing.ops import apply_ops
from ontoforge.io.rdf_export import serialize
from ontoforge.io.rdf_import import parse_ontology
from ontoforge.main import app
from ontoforge.mapping.engine import analyze
from ontoforge.projects import releases
from ontoforge.targets import curiosity, neo4j, report

ROOT = pathlib.Path(__file__).resolve().parents[2]
NS = "https://example.org/fleet#"
SKOS, DCT, VS = bp.SKOS, bp.DCT, bp.VS


def _onto(**kw) -> OntoModel:
    o = OntoModel(meta=OntologyMeta(iri="https://example.org/fleet", prefixes={"ex": NS}))
    o.classes[NS + "Vehicle"] = OntClass(iri=NS + "Vehicle", labels={"fr": "Véhicule", "en": "Vehicle"})
    o.classes[NS + "Car"] = OntClass(iri=NS + "Car", labels={"fr": "Voiture", "en": "Car"}, sub_class_of=[NS + "Vehicle"])
    o.classes[NS + "Garage"] = OntClass(iri=NS + "Garage", labels={"fr": "Garage", "en": "Garage"})
    o.object_properties[NS + "servicedBy"] = ObjectProperty(iri=NS + "servicedBy", labels={"fr": "entretenu par", "en": "serviced by"},
                                                            domain=[NS + "Vehicle"], range=[NS + "Garage"], characteristics=["functional"])
    o.datatype_properties[NS + "vin"] = DatatypeProperty(iri=NS + "vin", labels={"fr": "NIV", "en": "VIN"}, domain=[NS + "Vehicle"],
                                                         range=["http://www.w3.org/2001/XMLSchema#string"])
    return o


def _codes(issues, code):
    return [i for i in issues if i.code == code]


def _project(o: OntoModel) -> Project:
    return Project(id="p", name="p", created_at="", updated_at="", onto=o)


def _ops(o: OntoModel, ops):
    p = _project(o)
    r = apply_ops(p, ops)
    assert not r.errors, r.errors
    return p.onto, r


# ---- BP08–BP16 -------------------------------------------------------------------------------------------------------

def test_new_rules_are_never_errors():
    o = _onto()
    o.classes[NS + "Car"].deprecated = True
    o.classes[NS + "Car"].annotations.append(Annotation(property=VS + "term_status", value="bogus"))
    issues = [i for i in lint(o, include_dl=False) if i.code >= "BP08"]
    assert issues and all(i.level in ("info", "warning") for i in issues)
    assert {"BP08", "BP09", "BP10", "BP11", "BP12", "BP14", "BP16"} <= {i.code for i in issues}


def test_bp08_definition_by_comment_or_skos_definition():
    o = _onto()
    o.classes[NS + "Vehicle"].comments["fr"] = "Moyen de transport."
    o.classes[NS + "Car"].annotations.append(Annotation(property=SKOS + "definition", value="Voiture.", lang="fr"))
    subj = {i.subject for i in _codes(lint(o, include_dl=False), "BP08")}
    assert NS + "Vehicle" not in subj and NS + "Car" not in subj and NS + "Garage" in subj


def test_bp09_grouped_when_nobody_has_a_card_then_per_entity():
    o = _onto()
    one = _codes(lint(o, include_dl=False), "BP09")
    assert len(one) == 1 and one[0].subject == o.meta.iri
    o.classes[NS + "Car"].annotations += [Annotation(property=DCT + "creator", value="Équipe flotte"),
                                          Annotation(property=DCT + "source", value="https://example.org/spec", is_iri=True),
                                          Annotation(property=VS + "term_status", value="stable")]
    per = _codes(lint(o, include_dl=False), "BP09")
    assert len(per) == 4 and NS + "Car" not in {i.subject for i in per}


def test_bp10_bp11_status_and_justification():
    o = _onto()
    o.classes[NS + "Car"].annotations.append(Annotation(property=VS + "term_status", value="draft"))
    iss = lint(o, include_dl=False)
    assert [i.subject for i in _codes(iss, "BP10")] == [NS + "Car"]
    assert {i.subject for i in _codes(iss, "BP11")} == {NS + "servicedBy"}
    o.object_properties[NS + "servicedBy"].annotations.append(Annotation(property=SKOS + "editorialNote", value="Un seul garage référent.", lang="fr"))
    assert not _codes(lint(o, include_dl=False), "BP11")


def test_bp12_bp13_deprecation_checks():
    o = _onto()
    o.classes[NS + "Garage"].deprecated = True
    iss = lint(o, include_dl=False)
    assert [i.subject for i in _codes(iss, "BP12")] == [NS + "Garage"]
    assert [i.subject for i in _codes(iss, "BP13")] == [NS + "servicedBy"]  # portée dépréciée encore utilisée
    o.classes[NS + "Garage"].annotations.append(Annotation(property=DCT + "isReplacedBy", value=NS + "Workshop", is_iri=True))
    msgs = [i.message for i in _codes(lint(o, include_dl=False), "BP12")]
    assert len(msgs) == 1 and "introuvable" in msgs[0]


def test_bp14_bp15_semver_and_version_iri():
    o = _onto()
    assert _codes(lint(o, include_dl=False), "BP14")
    o.meta.annotations.append(Annotation(property=bp.VERSION_INFO, value="v1.2"))
    assert "SemVer" in _codes(lint(o, include_dl=False), "BP14")[0].message
    o.meta.annotations = [Annotation(property=bp.VERSION_INFO, value="1.2.0-rc.1+build.5")]
    assert not _codes(lint(o, include_dl=False), "BP14")
    o.meta.version_iri = o.meta.iri
    assert any("égale" in i.message for i in _codes(lint(o, include_dl=False), "BP15"))
    o2 = _onto()
    o2.meta.iri = "https://example.org/fleet/2.0/"
    assert any("numéro de version" in i.message for i in _codes(lint(o2, include_dl=False), "BP15"))
    o3 = _onto()
    o3.meta.iri = "https://example.org/2004/fleet"  # une année n'est pas un numéro de version
    assert not _codes(lint(o3, include_dl=False), "BP15")


def test_w07_accepts_skos_preflabel():
    o = _onto()
    o.classes[NS + "Garage"].labels = {"fr": "Garage"}
    assert any(i.subject == NS + "Garage" for i in _codes(lint(o, include_dl=False), "W07"))
    o.classes[NS + "Garage"].annotations.append(Annotation(property=SKOS + "prefLabel", value="Garage", lang="en"))
    assert not any(i.subject == NS + "Garage" for i in _codes(lint(o, include_dl=False), "W07"))


def test_completeness_scores():
    o = _onto()
    c = bp.completeness(o)
    car = c["entities"][NS + "Car"]
    assert car["score"] == 33 and set(car["missing"]) == {"definition", "creator", "source", "status"}
    assert "justification" in c["entities"][NS + "servicedBy"]["criteria"]
    assert "justification" not in car["criteria"]
    assert 0 < c["score"] < 100 and c["header"]["score"] < 100
    full = bp.entity_card("class", OntClass(iri=NS + "X", labels={"fr": "x", "en": "x"}, comments={"fr": "x"}, annotations=[
        Annotation(property=DCT + "creator", value="a"), Annotation(property=DCT + "source", value="b"),
        Annotation(property=VS + "term_status", value="testing")]))
    assert full["score"] == 100 and not full["missing"]


def test_samples_stay_dl_and_without_errors():
    for f in ("automaint/automaint.ttl", "trap/trap.ttl"):
        p = ROOT / "samples" / f
        o, _ = parse_ontology(p.read_text(encoding="utf-8"), filename=p.name)
        rep = check_conformance(o, run_reasoner=False)
        assert rep.profiles["DL"], f
        assert not [i for i in rep.issues if i.level == "error" and i.code >= "BP"], f
        assert rep.completeness and 0 <= rep.completeness["score"] <= 100


# ---- opérations et aller-retour Turtle -------------------------------------------------------------------------------

def test_ops_card_fields_and_round_trip():
    o, _ = _ops(_onto(), [
        {"op": "set_annotations", "iri": NS + "Car", "property": SKOS + "definition", "values": ["Véhicule léger."], "lang": "fr"},
        {"op": "set_annotations", "iri": NS + "Car", "property": DCT + "creator", "values": ["Équipe flotte", "Atelier"]},
        {"op": "set_annotations", "iri": NS + "Car", "property": DCT + "source", "values": ["Norme interne n° 4"]},
        {"op": "set_annotations", "iri": NS + "Car", "property": VS + "term_status", "values": ["testing"]},
        {"op": "set_annotations", "iri": NS + "servicedBy", "property": SKOS + "editorialNote", "values": [{"value": "Un garage référent.", "lang": "fr"}]},
        {"op": "set_deprecated", "iri": NS + "Garage", "value": True, "replaced_by": [NS + "Vehicle"]},
        {"op": "set_annotations", "iri": "https://example.org/fleet", "property": DCT + "title", "values": ["Flotte"], "lang": "fr"},
        {"op": "set_annotations", "iri": "https://example.org/fleet", "property": DCT + "license",
         "values": ["https://creativecommons.org/licenses/by/4.0/"]},
        {"op": "set_annotations", "iri": "https://example.org/fleet", "property": DCT + "created", "values": ["2026-11-17"]},
        {"op": "set_annotations", "iri": "https://example.org/fleet", "property": bp.VERSION_INFO, "values": ["1.0.0"]},
        {"op": "set_version_iri", "version_iri": "https://example.org/fleet/1.0.0"},
    ])
    car = bp.entity_card("class", o.classes[NS + "Car"])
    assert car["missing"] == ["definition"] or car["criteria"]["definition"]
    assert car["criteria"]["creator"] and car["criteria"]["status"]
    g = o.classes[NS + "Garage"]
    assert g.deprecated and bp.replaced_by(g) == [NS + "Vehicle"] and bp.status_of(g) == "archaic"
    assert {DCT + "isReplacedBy", VS + "term_status", SKOS + "definition", DCT + "creator"} <= set(o.annotation_properties)
    created = [a for a in o.meta.annotations if a.property == DCT + "created"][0]
    assert created.datatype.endswith("dateTime") and created.value.startswith("2026-11-17T")
    # aller-retour Turtle sans perte
    ttl = serialize(o, "turtle")
    back, _ = parse_ontology(ttl, filename="x.ttl")
    for iri in (NS + "Car", NS + "Garage", NS + "servicedBy"):
        a = {k: v for k, v in (back.classes.get(iri) or back.object_properties[iri]).model_dump().items()}
        b = (o.classes.get(iri) or o.object_properties[iri]).model_dump()
        assert a["deprecated"] == b["deprecated"]
        key = lambda x: (x["property"], x["value"], x["lang"] or "")  # noqa: E731
        assert sorted(map(key, a["annotations"])) == sorted(map(key, b["annotations"]))
    assert back.meta.version_iri == "https://example.org/fleet/1.0.0"
    assert sorted((x.property, x.value) for x in back.meta.annotations) == sorted((x.property, x.value) for x in o.meta.annotations)
    assert serialize(back, "turtle") == ttl
    rep = check_conformance(back, run_reasoner=False)
    assert rep.profiles["DL"], rep.profile_violations["DL"]
    assert not [i for i in rep.issues if i.code == "W02"]


def test_ops_refuse_unsafe_values():
    p = _project(_onto())
    for op, frag in (({"op": "set_annotations", "iri": NS + "Car", "property": "http://www.w3.org/2000/01/rdf-schema#subClassOf", "values": ["x"]}, "non modifiable"),
                     ({"op": "set_annotations", "iri": NS + "Car", "property": VS + "term_status", "values": ["draft"]}, "Statut de revue inconnu"),
                     ({"op": "set_annotations", "iri": NS + "Car", "property": DCT + "license", "values": ["pas une iri"]}, "invalide"),
                     ({"op": "set_annotations", "iri": NS + "Nope", "property": DCT + "creator", "values": ["a"]}, "inconnue"),
                     ({"op": "set_deprecated", "iri": NS + "Car", "replaced_by": [NS + "Car"]}, "elle-même"),
                     ({"op": "set_version_iri", "version_iri": "https://example.org/fleet"}, "différer")):
        r = apply_ops(p, [op])
        assert r.errors and frag in r.errors[0]["message"], (op, r.errors)
    assert not p.onto.classes[NS + "Car"].deprecated


def test_undeprecate_removes_replacement():
    o, _ = _ops(_onto(), [{"op": "set_deprecated", "iri": NS + "Car", "replaced_by": [NS + "Vehicle"]}])
    o, _ = _ops(o, [{"op": "set_deprecated", "iri": NS + "Car", "value": False}])
    assert not o.classes[NS + "Car"].deprecated and not bp.replaced_by(o.classes[NS + "Car"])


# ---- dépréciation dans l'analyse et les cibles -----------------------------------------------------------------------

@pytest.mark.parametrize("target", ["curiosity", "neo4j"])
def test_deprecated_entity_end_to_end(target):
    o, _ = _ops(_onto(), [{"op": "set_deprecated", "iri": NS + "Garage", "replaced_by": [NS + "Vehicle"]},
                          {"op": "set_deprecated", "iri": NS + "vin"}])
    pg = analyze(o, None, target)
    f = {x.id: x for x in pg.findings}
    a03 = f[f"A03:{NS}Garage"]
    assert a03.severity == "review" and a03.recommended == "exclude" and a03.chosen is None
    assert {x.id for x in a03.options} == {"exclude", "flag_deprecated"}
    # revue it1 : remplaçant d'abord, puis ce qu'emporte l'exclusion (servicedBy vise Garage) ; plus de perte silencieuse
    assert a03.related == [NS + "Vehicle", NS + "servicedBy"] and "Exclure entraîne la perte de : " in a03.detail
    o01 = f[f"O01:{NS}servicedBy"]
    assert o01.severity == "lost" and "dépréciée et exclue" in o01.detail
    assert "Remplacée par" in a03.detail
    assert not any(NS + "Garage" in nt.source for nt in pg.node_types.values())
    assert not any(p.source == NS + "vin" for nt in pg.node_types.values() for p in nt.properties)
    rep = report.generate(pg, o)["rapport-transposition.md"]
    assert "## Entités dépréciées — 2" in rep and "non générée" in rep
    assert any(l.startswith("| ex:Garage | ex:Vehicle | non générée | ex:servicedBy |") for l in rep.splitlines()), rep
    # arbitrage humain : garder avec drapeau
    pg2 = analyze(o, None, target, {f"A03:{NS}Garage": "flag_deprecated", f"A03:{NS}vin": "flag_deprecated"})
    nt = next(nt for nt in pg2.node_types.values() if NS + "Garage" in nt.source)
    assert nt.description.startswith("[DÉPRÉCIÉ]")
    vin = [p for n in pg2.node_types.values() for p in n.properties if p.source == NS + "vin"]
    assert vin and all(p.description.startswith("[DÉPRÉCIÉ]") for p in vin)
    rep2 = report.generate(pg2, o, lang="en")["rapport-transposition.md"]
    assert "## Deprecated entities — 2" in rep2 and "flagged [DEPRECATED]" in rep2
    files = (curiosity if target == "curiosity" else neo4j).generate(pg, o)
    assert not any("Garage" in name for name in files)
    assert pg.summary()["pending"] >= 2  # A03 compte désormais parmi les points à arbitrer


# ---- diff SemVer --------------------------------------------------------------------------------------------------

def test_diff_levels_follow_contract():
    a = _onto()
    b, _ = _ops(a, [{"op": "set_label", "iri": NS + "Car", "text": "Automobile", "lang": "fr"}])
    assert releases.level_of(releases.diff(a, b)) == "minor"
    c, _ = _ops(a, [{"op": "set_annotations", "iri": NS + "Car", "property": DCT + "creator", "values": ["x"]}])
    assert releases.level_of(releases.diff(a, c)) == "patch"
    d, _ = _ops(a, [{"op": "add_class", "iri": NS + "Truck", "label": "Camion"}])
    assert releases.level_of(releases.diff(a, d)) == "major"
    e, _ = _ops(a, [{"op": "set_domain_range", "iri": NS + "servicedBy", "range": [NS + "Vehicle"]}])
    assert [x["field"] for x in releases.diff(a, e)] == ["range"] and releases.level_of(releases.diff(a, e)) == "major"
    f, _ = _ops(a, [{"op": "set_deprecated", "iri": NS + "Garage"}])
    ch = releases.diff(a, f)  # dépréciation seule (mineure) : statut archaic et déclarations rattachés, pas de ligne en plus
    assert [(x["level"], x["change"]) for x in ch] == [("minor", "deprecated")], ch
    g, _ = _ops(a, [{"op": "delete_entity", "iri": NS + "vin"}])
    assert releases.level_of(releases.diff(a, g)) == "major"
    h, _ = _ops(a, [{"op": "set_annotations", "iri": NS + "Car", "property": SKOS + "definition", "values": ["déf"], "lang": "fr"}])
    assert releases.level_of(releases.diff(a, h)) == "minor"
    assert releases.diff(a, a) == []


def test_bump_and_check():
    assert releases.bump("1.4.2", "major") == "2.0.0"
    assert releases.bump("1.4.2", "minor") == "1.5.0"
    assert releases.bump("1.4.2", "patch") == "1.4.3"
    assert releases.bump("1.4.2-rc.1", "patch") == "1.4.3"
    assert releases.bump(None, "minor") == "1.0.0"
    with pytest.raises(releases.ReleaseError):
        releases.check_version("1.4.2", "1.4.2")
    with pytest.raises(releases.ReleaseError):
        releases.check_version("1.5", None)
    assert releases.check_version("2.0.0", "1.9.9") == "2.0.0"


def test_release_note_lists_changes_by_level():
    a = _onto()
    b, _ = _ops(a, [{"op": "add_class", "iri": NS + "Truck", "label": "Camion"},
                    {"op": "set_deprecated", "iri": NS + "Garage", "replaced_by": [NS + "Vehicle"]}])
    ch = releases.diff(a, b)
    note = releases.release_note("2.0.0", ch, previous="1.0.0", proposed="2.0.0", level="major", onto=b, date="2026-11-17")
    assert note.startswith("# Version 2.0.0 (2026-11-17)")
    assert "## Changements majeurs (incompatibles) (1)" in note and "Classe Camion" in note
    assert "dépréciée, remplacée par" in note
    en = releases.release_note("2.0.0", ch, previous="1.0.0", proposed="2.0.0", level="major", onto=b, lang="en")
    assert "## Major changes (breaking) (1)" in en and "Class" in en


# ---- API -------------------------------------------------------------------------------------------------------------

@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("ONTOFORGE_DATA", str(tmp_path))
    monkeypatch.setenv("ONTOFORGE_LLM_PROVIDER", "mock")
    return TestClient(app)


@pytest.fixture
def pid(client):
    r = client.post("/api/projects", json={"name": "l49", "sample": "automaint"})
    assert r.status_code in (200, 201), r.text
    return r.json()["id"]


def test_api_release_cycle(client, pid):
    pv = client.get(f"/api/projects/{pid}/releases/preview").json()
    assert pv["previous"] is None and pv["proposed"] == "1.0.0"
    r = client.post(f"/api/projects/{pid}/releases", json={})
    assert r.status_code == 201, r.text
    proj = r.json()["project"]
    meta = proj["onto"]["meta"]
    iri = meta["iri"]
    assert meta["version_iri"] == iri.rstrip("#/") + "/1.0.0"
    assert any(a["property"] == bp.VERSION_INFO and a["value"] == "1.0.0" for a in meta["annotations"])
    # changement mineur : libellé
    cls = next(iter(proj["onto"]["classes"]))
    ok = client.post(f"/api/projects/{pid}/ops", json={"ops": [{"op": "set_label", "iri": cls, "text": "Nouveau libellé", "lang": "fr"}]})
    assert ok.json()["ok"]
    pv = client.get(f"/api/projects/{pid}/releases/preview").json()
    assert pv["previous"] == "1.0.0" and pv["level"] == "minor" and pv["proposed"] == "1.1.0" and pv["counts"]["minor"] == 1
    assert "Changements mineurs" in pv["note"]
    assert client.post(f"/api/projects/{pid}/releases", json={"version": "1.0.0"}).status_code == 422
    r2 = client.post(f"/api/projects/{pid}/releases", json={})
    assert r2.status_code == 201 and r2.json()["release"]["version"] == "1.1.0"
    meta2 = r2.json()["project"]["onto"]["meta"]
    assert any(a["property"] == bp.PRIOR_VERSION and a["value"] == meta["version_iri"] for a in meta2["annotations"])
    lst = client.get(f"/api/projects/{pid}/releases").json()["releases"]
    assert [x["version"] for x in lst] == ["1.1.0", "1.0.0"] and "snapshot" not in lst[0]
    one = client.get(f"/api/projects/{pid}/releases/1.1.0").json()
    assert one["note"].startswith("# Version 1.1.0") and one["level"] == "minor"
    assert client.get(f"/api/projects/{pid}/releases/9.9.9").status_code == 404
    # l'enregistrement est annulable (journal d'opérations)
    assert client.post(f"/api/projects/{pid}/ops/undo").status_code == 200
    # export Turtle : versionInfo, versionIRI, priorVersion présents
    ttl = client.get(f"/api/projects/{pid}/export/ontology").text
    assert "owl:versionIRI" in ttl and "owl:versionInfo" in ttl


def test_api_metadata_and_conformance(client, pid):
    m = client.get(f"/api/projects/{pid}/metadata").json()
    assert m["header"]["title"]["fr"] and "license" in m["card"]["missing"]
    assert m["fields"]["license"]["iri"] is True
    c = client.get(f"/api/projects/{pid}/conformance").json()
    assert c["completeness"]["score"] >= 0 and c["completeness"]["entities"]
    assert any(i["code"] == "BP16" for i in c["issues"])


def test_english_messages_for_new_rules():
    from ontoforge.localize import tr
    o = _onto()
    o.classes[NS + "Garage"].deprecated = True
    for i in lint(o, include_dl=False):
        if i.code >= "BP08":
            en = tr(i.message, "en")
            assert not any(w in en for w in ("manquante", "dépréciée", "fiche", "manque", "sans ", "Classe ", "Propriété")), en


# ---- revue it1 -------------------------------------------------------------------------------------------------------

def test_flagged_deprecated_relation_is_marked_in_curiosity_and_neo4j_files():
    o, _ = _ops(_onto(), [{"op": "set_deprecated", "iri": NS + "servicedBy"}, {"op": "set_deprecated", "iri": NS + "vin"},
                          {"op": "set_deprecated", "iri": NS + "Garage"}])
    dec = {f"A03:{NS}{x}": "flag_deprecated" for x in ("servicedBy", "vin", "Garage")}
    cur = curiosity.generate(analyze(o, None, "curiosity", dec), o)
    edges = cur["Edges.cs"]
    marked = [l.strip() for l in edges.splitlines() if "[DÉPRÉCIÉ]" in l]
    assert any(l.startswith("// [DÉPRÉCIÉ] ") and "-[ServicedBy]->" in l for l in marked), edges  # arête aller
    assert any("retour de ServicedBy" in l for l in marked), edges  # arête retour
    neo = neo4j.generate(analyze(o, None, "neo4j", dec), o)
    for name in ("schema.cypher", "ingest.cypher", "README-neo4j.md", "model.mmd"):
        assert "[DÉPRÉCIÉ]" in neo[name] or "deprecated" in neo[name], name
    assert "<<deprecated>>" in neo["model.mmd"]
    assert "// [DÉPRÉCIÉ] :Garage" in neo["ingest.cypher"] and "// [DÉPRÉCIÉ] [:SERVICED_BY]" in neo["ingest.cypher"]
    en = neo4j.generate(analyze(o, None, "neo4j", dec), o, lang="en")
    assert "[DEPRECATED]" in en["schema.cypher"]
    # sans drapeau (exclusion par défaut) : rien de déprécié n'est généré, donc aucune marque
    plain = neo4j.generate(analyze(o, None, "neo4j"), o)
    assert "[DÉPRÉCIÉ]" not in plain["schema.cypher"] and "Garage" not in plain["ingest.cypher"]


def test_deprecated_property_shape_is_deactivated():
    from ontoforge.core.onto_model import Restriction
    from ontoforge.shacl.owl_to_shacl import generate_shapes
    o = _onto()
    o.classes[NS + "Car"].restrictions.append(Restriction(property=NS + "vin", kind="min", n=1))
    o.datatype_properties[NS + "vin"].deprecated = True
    sh, notes = generate_shapes(o)
    hits = [ps for ns in sh.shapes.values() for ps in ns.properties if ps.path.iri == NS + "vin"] + \
           [ps for ps in sh.property_shapes.values() if ps.path.iri == NS + "vin"]
    assert hits and all(ps.deactivated for ps in hits)
    assert any("propriété dépréciée" in n for n in notes)
    o.datatype_properties[NS + "vin"].deprecated = False
    sh2, _ = generate_shapes(o)
    assert not any(ps.deactivated for ns in sh2.shapes.values() for ps in ns.properties if ps.path.iri == NS + "vin")


def test_api_undo_release_removes_entry_and_allows_rerecording(client, pid):
    assert client.post(f"/api/projects/{pid}/releases", json={}).status_code == 201
    assert [r["version"] for r in client.get(f"/api/projects/{pid}/releases").json()["releases"]] == ["1.0.0"]
    assert client.post(f"/api/projects/{pid}/ops/undo").json()["label"] == "version 1.0.0"
    assert client.get(f"/api/projects/{pid}/releases").json()["releases"] == []
    pv = client.get(f"/api/projects/{pid}/releases/preview").json()
    assert pv["previous"] is None and pv["proposed"] == "1.0.0"
    meta = client.get(f"/api/projects/{pid}").json()["onto"]["meta"]
    assert not any(a["property"].endswith("/modified") for a in meta["annotations"])  # l'exemple n'a pas de dcterms:modified : annulé
    # rétablir remet l'entrée ; annuler à nouveau la retire ; réenregistrer le même numéro est accepté
    assert client.post(f"/api/projects/{pid}/ops/redo").status_code == 200
    assert [r["version"] for r in client.get(f"/api/projects/{pid}/releases").json()["releases"]] == ["1.0.0"]
    client.post(f"/api/projects/{pid}/ops/undo")
    r = client.post(f"/api/projects/{pid}/releases", json={"version": "1.0.0"})
    assert r.status_code == 201, r.text
    assert [x["version"] for x in client.get(f"/api/projects/{pid}/releases").json()["releases"]] == ["1.0.0"]
    # plus rien à rétablir côté versions : une nouvelle version vide releases-undone.json
    pv = client.get(f"/api/projects/{pid}/releases/preview").json()
    assert pv["unchanged"] is True and pv["level"] is None


def test_diff_has_keys_and_chains_order_and_downgrade_flag(client, pid):
    from ontoforge.core.onto_model import OntClass as C
    a = _onto()
    a.classes[NS + "Vehicle"].has_keys = [[NS + "vin", NS + "servicedBy"], [NS + "vin"]]
    b = a.model_copy(deep=True)
    b.classes[NS + "Vehicle"].has_keys = [[NS + "vin"], [NS + "servicedBy", NS + "vin"]]
    assert releases.diff(a, b) == []
    x, y = NS + "servicedBy", NS + "partOf"
    a.object_properties[NS + "servicedBy"].chains = [[x, y], [y, x]]
    c = a.model_copy(deep=True)
    c.object_properties[NS + "servicedBy"].chains = [[y, x], [x, y]]  # deux axiomes permutés : même sens
    assert releases.diff(a, c) == []
    d = a.model_copy(deep=True)
    d.object_properties[NS + "servicedBy"].chains = [[y, x]]  # un axiome retiré : changement (majeur)
    assert releases.level_of(releases.diff(a, d)) == "major"
    e = a.model_copy(deep=True)
    e.object_properties[NS + "servicedBy"].chains = [[y, x], [y, x]]  # ordre intérieur inversé : autre chaîne
    assert releases.diff(a, e)
    # version saisie plus faible que le niveau des changements : signalée
    client.post(f"/api/projects/{pid}/releases", json={})
    client.post(f"/api/projects/{pid}/ops", json={"ops": [{"op": "add_class", "name": "Trottinette", "label": "Trottinette"}]})
    r = client.post(f"/api/projects/{pid}/releases", json={"version": "1.0.1"}).json()["release"]
    assert r["downgraded"] is True and "Attention" in r["note"]



@pytest.mark.parametrize("target", ["curiosity", "neo4j"])
def test_losses_follow_resolution_o02_and_partial_union(target):
    """Revue it2 : une relation sans domaine ni portée, résolue par restriction (O02), vers une classe exclue est une perte
    explicite ; une portée en union dont une branche seulement est exclue est une perte partielle (le reste est généré)."""
    from ontoforge.core.onto_model import Restriction
    o, _ = _ops(_onto(), [{"op": "set_deprecated", "iri": NS + "Garage"}])
    o.object_properties[NS + "locatedNear"] = ObjectProperty(iri=NS + "locatedNear", labels={"fr": "près de", "en": "near"})
    o.classes[NS + "Car"].restrictions.append(Restriction(property=NS + "locatedNear", kind="some", filler=NS + "Garage"))
    o.object_properties[NS + "parkedAt"] = ObjectProperty(iri=NS + "parkedAt", labels={"fr": "garé à", "en": "parked at"},
                                                          domain=[NS + "Car"], range_union=[NS + "Garage", NS + "Vehicle"])
    pg = analyze(o, None, target)
    f = {x.id: x for x in pg.findings}
    a03 = f[f"A03:{NS}Garage"]
    assert NS + "locatedNear" in a03.related and "locatedNear" in a03.detail.split("Exclure entraîne la perte de : ")[1]
    o02 = [x for x in pg.findings if x.subject == NS + "locatedNear" and x.rule == "O02"]
    assert o02 and o02[0].severity == "lost" and "dépréciée et exclue" in o02[0].detail
    assert not any(e.source == NS + "locatedNear" for e in pg.edge_types)
    # union partielle : arête vers Vehicle générée, pas de « lost », note « en partie »
    assert NS + "parkedAt" not in a03.related and "En partie : ex:parkedAt" in a03.detail
    base = [x for x in pg.findings if x.subject == NS + "parkedAt" and x.rule == "O03"]
    assert base and base[0].severity != "lost" and "Générée en partie" in base[0].detail
    assert any(e.source == NS + "parkedAt" for e in pg.edge_types)
    rep = report.generate(pg, o)["rapport-transposition.md"]
    line = next(l for l in rep.splitlines() if l.startswith("| ex:Garage |"))
    assert "ex:locatedNear" in line and "en partie : ex:parkedAt" in line, line
