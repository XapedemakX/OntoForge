"""Relecture croisée L25 (w3c + scout, it1) : sortie LLM piégée, IRI, libellés et langue, punning, fusion, traçabilité, confidentialité."""
import importlib.util
import json
import pathlib

import pytest
from fastapi.testclient import TestClient

from ontoforge.assistant import docdraft, document
from ontoforge.assistant.convert import to_onto
from ontoforge.assistant.naming import camel, pascal
from ontoforge.assistant.providers import get_provider
from ontoforge.core.onto_model import ObjectProperty, OntClass, OntoModel, OntologyMeta
from ontoforge.main import app

ROOT = pathlib.Path(__file__).resolve().parents[2]
BASE = "https://example.org/auto#"
DEMO = ROOT / "samples/automaint/automaint-cahier-des-charges.pdf"


@pytest.fixture(autouse=True)
def mock_env(monkeypatch):
    monkeypatch.setenv("ONTOFORGE_LLM_PROVIDER", "mock")


@pytest.fixture
def doc():
    return document.extract("cdc.pdf", DEMO.read_bytes())


class P:
    def __init__(self, onto=None):
        self.onto = onto or OntoModel(meta=OntologyMeta(iri=BASE.rstrip("#")))


class FakeLLM:
    name, model, configured = "anthropic", "fake", True

    def __init__(self, drafts):
        self.drafts, self.calls = list(drafts), 0

    def complete(self, system, messages, max_tokens=4096, json_schema=None):
        self.calls += 1
        if "[TASK:docquestions]" in system:
            return json.dumps({"questions": ["Quels pneus équipent un véhicule donné ?"]})
        return json.dumps(self.drafts.pop(0) if self.drafts else {})


def S(page, ex):
    return {"page": page, "excerpt": ex}


EX = S(1, "Garage : atelier qui accueille les véhicules")


def _existing():
    o = OntoModel(meta=OntologyMeta(iri=BASE.rstrip("#")))
    o.classes[BASE + "Vehicule"] = OntClass(iri=BASE + "Vehicule", labels={"fr": "Véhicule"})
    o.classes[BASE + "Voiture"] = OntClass(iri=BASE + "Voiture", labels={"fr": "Voiture"}, sub_class_of=[BASE + "Vehicule"])
    o.object_properties[BASE + "marque"] = ObjectProperty(iri=BASE + "marque", labels={"fr": "marque"})
    return o


def _all_iris(prop):
    return [*prop.classes, *prop.object_properties, *prop.datatype_properties]


# ----------------------------------------------------------------------------- sortie LLM piégée
def test_trapped_llm_output_duplicate_cycle_invalid_iri(doc):
    trap = {"classes": [
        {"name": "Véhicules", "label_fr": "Véhicule", "source": EX},          # doublon de l'existant (pluriel, accent)
        {"name": "Moteur", "parent": "Organe", "source": EX},                 # cycle à trois : Moteur -> Organe -> Piece -> Moteur
        {"name": "Organe", "parent": "Piece", "source": EX},
        {"name": "Piece", "parent": "Moteur", "source": EX},
        {"name": "!!!", "source": EX},                                        # nom sans lettre : refusé
        {"name": "車", "source": EX}, {"name": "車車", "label_fr": "Kuruma", "source": EX},  # ne fusionnent pas en une classe « X »
    ], "datatype_properties": [
        {"name": "httpUrl", "domain": "Moteur", "range": "anyURI", "source": EX},  # nom local commençant par « http »
        {"name": "marque", "domain": "Moteur", "source": EX},                       # punning avec la propriété objet existante
        {"name": "compte", "domain": "Moteur", "source": EX},                       # punning dans le brouillon même
    ], "object_properties": [{"name": "compte", "domain": "Moteur", "range": "Piece", "source": EX}]}
    r = docdraft.draft_document(P(_existing()), doc, FakeLLM([trap]), "fr", confirm_hosted=True)
    prop = r["proposal"]
    # aucune IRI relative, aucune classe « X »
    assert all(i.startswith(BASE) for i in _all_iris(prop)), _all_iris(prop)
    assert BASE + "httpUrl" in prop.datatype_properties and BASE + "X" not in prop.classes
    # doublon de l'existant : non recréé, cité dans skipped
    assert {"name": "Vehicules", "iri": BASE + "Vehicule", "reason": "existing"} in r["skipped"]
    assert prop.classes.get(BASE + "Vehicule") is None or prop.classes[BASE + "Vehicule"].labels == {"fr": "Véhicule"}
    # cycle cassé : exactement une arête retirée
    sub = {k: v.sub_class_of for k, v in prop.classes.items() if k in {BASE + "Moteur", BASE + "Organe", BASE + "Piece"}}
    assert sum(1 for v in sub.values() if v) == 2
    for c in prop.classes:
        assert c not in prop.ancestors(c)
    # punning : refusé avec un message explicite, la propriété objet reste
    assert BASE + "marque" not in prop.datatype_properties
    assert BASE + "compte" in prop.object_properties and BASE + "compte" not in prop.datatype_properties
    w = " ".join(r["warnings"])
    assert "Cycle" in w and "punning" in w and w.count("nom non valide") == 3
    assert not [i for i in r["lint"] if i["level"] == "error"]


def test_lint_reports_punning_on_existing_iri():
    """Le lint du brouillon ne doit pas masquer une erreur DL sur une IRI déjà présente sous une autre sorte."""
    onto = _existing()
    prop, _ = to_onto({"datatype_properties": [{"name": "marque", "label_fr": "marque", "label_en": "brand"}]}, BASE)
    issues = docdraft._lint(onto, prop, "fr")
    assert any(i["code"] == "W04" and i["subject"] == BASE + "marque" and i["level"] == "error" for i in issues)


def test_to_onto_never_makes_relative_iris():
    prop, _ = to_onto({"classes": [{"name": "HttpServer"}], "object_properties": [{"name": "httpsEndpoint", "domain": "HttpServer"}],
                       "datatype_properties": [{"name": "httpUrl", "range": "anyURI"}]}, BASE)
    assert set(_all_iris(prop)) == {BASE + "HttpServer", BASE + "httpsEndpoint", BASE + "httpUrl"}
    assert prop.datatype_properties[BASE + "httpUrl"].range == ["http://www.w3.org/2001/XMLSchema#anyURI"]


def test_ligatures_are_transliterated():
    assert pascal("Main d'œuvre") == "MainDOeuvre" and camel("Cœur de métier") == "coeurDeMetier" and pascal("Straße") == "Strasse"


# ----------------------------------------------------------------------------- libellés et langue
def test_labels_follow_document_language_not_ui(doc):
    """Document en français, interface en anglais : libellés @fr (pas le nom local en @en), stub compris."""
    out = {"classes": [{"name": "Garage", "source": EX}],
           "object_properties": [{"name": "accueille", "domain": "Garage", "range": "Véhicule", "source": EX}]}
    r = docdraft.draft_document(P(), doc, FakeLLM([out]), "en", confirm_hosted=True)
    cl = r["proposal"].classes
    assert cl[BASE + "Garage"].labels == {"fr": "Garage"}
    assert cl[BASE + "Vehicule"].labels == {"fr": "Véhicule"}  # classe créée depuis la portée citée : accent gardé, langue du document
    assert r["proposal"].object_properties[BASE + "accueille"].labels == {"fr": "accueille"}


def test_english_document_comment_is_tagged_en():
    d = document.extract("spec.txt", b"A Garage is a workshop that hosts each Vehicle. The Garage has a name and an address.")
    out = {"classes": [{"name": "Garage", "comment": "A workshop.", "source": S(1, "A Garage is a workshop")}]}
    r = docdraft.draft_document(P(), d, FakeLLM([out]), "fr", confirm_hosted=True)
    g = r["proposal"].classes[BASE + "Garage"]
    assert g.labels == {"en": "Garage"} and g.comments == {"en": "A workshop."}


# ----------------------------------------------------------------------------- fusion entre morceaux
def test_merge_signals_conflicting_domains(doc, monkeypatch):
    monkeypatch.setenv("ONTOFORGE_DOC_CHUNK_CHARS", "900")
    a = {"classes": [{"name": "Pneu", "source": S(2, "Un Pneu est une Pièce.")}],
         "datatype_properties": [{"name": "date", "domain": "Pneu", "range": "dateTime", "source": S(2, "une pression et une date")}]}
    b = {"classes": [{"name": "Contrôle technique", "source": S(2, "Un Contrôle technique concerne")}],
         "datatype_properties": [{"name": "date", "domain": "Contrôle technique", "range": "dateTime", "source": S(2, "Un Contrôle technique a une date")}]}
    r = docdraft.draft_document(P(), doc, FakeLLM([a, b]), "fr", confirm_hosted=True)
    assert r["stats"]["chunks"] >= 2 and r["stats"]["merged"] == 1
    assert r["proposal"].datatype_properties[BASE + "date"].domain == [BASE + "Pneu"]
    assert any("date" in w and "Contrôle technique" in w and "ignoré" in w for w in r["warnings"])


# ----------------------------------------------------------------------------- traçabilité et qualité du repli sur la démo
def test_demo_excerpts_are_verbatim_on_their_page(doc):
    r = docdraft.draft_document(P(), doc, get_provider(), "fr")
    assert r["provenance"]
    pages = {p.page: document.squash(p.text) for p in doc.pages}
    for iri, src in r["provenance"].items():
        assert len(src["excerpt"]) <= document.EXCERPT_MAX and src["document"] == "cdc.pdf"
        assert document.squash(src["excerpt"]).strip("…") in pages[src["page"]], (iri, src)
    assert r["provenance"][BASE + "remplacePneu"]["page"] == 2 and r["provenance"][BASE + "Voiture"]["page"] == 1


def test_demo_owl_quality(doc):
    r = docdraft.draft_document(P(), doc, get_provider(), "fr")
    prop = r["proposal"]
    XSD = "http://www.w3.org/2001/XMLSchema#"
    assert prop.classes[BASE + "Voiture"].sub_class_of == [BASE + "Vehicule"]
    assert prop.classes[BASE + "Pneu"].sub_class_of == [BASE + "Piece"]  # « est une Pièce » : sous-classe
    # « est équipé de » : partie-tout, donc une relation et pas une sous-classe
    assert BASE + "Pneu" not in prop.classes[BASE + "Vehicule"].sub_class_of + prop.classes[BASE + "Vehicule"].sub_class_of
    eq = prop.object_properties[BASE + "possedePneu"]
    assert eq.domain == [BASE + "Vehicule"] and eq.range == [BASE + "Pneu"]
    dt = {local: prop.datatype_properties[BASE + local].range for local in ("kilometrage", "pression", "dimension", "dateDeFabrication")}
    assert dt == {"kilometrage": [XSD + "integer"], "pression": [XSD + "decimal"], "dimension": [XSD + "string"],
                  "dateDeFabrication": [XSD + "dateTime"]}
    for c in prop.classes:
        assert c not in prop.ancestors(c)
    for e in [*prop.classes.values(), *prop.object_properties.values(), *prop.datatype_properties.values()]:
        assert list(e.labels) == ["fr"], e.iri  # document français : libellés @fr seulement
    # le lint est appliqué au brouillon : W07 « label manquant en en » une fois par élément, et rien d'autre ici
    w07 = [i for i in r["lint"] if i["code"] == "W07"]
    assert len(w07) == r["stats"]["items"] == len(r["lint"])
    assert {i["subject"] for i in w07} == set(_all_iris(prop))


# ----------------------------------------------------------------------------- confidentialité par l'API
@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("ONTOFORGE_DATA", str(tmp_path))
    return TestClient(app)


def test_api_hosted_provider_409_without_confirmation(client, monkeypatch):
    from ontoforge.assistant import service
    fake = FakeLLM([{}])
    monkeypatch.setattr(service, "_provider", lambda provider_id=None: fake)
    pid = client.post("/api/projects", json={"name": "doc"}).json()["id"]
    docp = {"name": "a.txt", "pages": [{"page": 1, "text": "Un Garage entretient les Véhicules. Le Garage a un nom."}]}
    est = client.post("/api/assistant/document/estimate", json={"document": docp}).json()
    assert est["hosted"] and est["chars_sent"] > 0 and est["calls"] == 2 and fake.calls == 0
    r = client.post("/api/assistant/document/draft", json={"project_id": pid, "document": docp})
    assert r.status_code == 409 and fake.calls == 0
    r = client.post("/api/assistant/document/draft", json={"project_id": pid, "document": docp, "confirm_hosted": True})
    assert r.status_code == 200 and fake.calls == 2


@pytest.mark.parametrize("url,hosted", [("http://127.0.0.1:11434", False), ("http://localhost:11434/", False), ("http://ollama:11434", False),
                                        ("http://host.docker.internal:11434", False), ("https://llm.example.com", True),
                                        ("http://10.0.0.5:11434", True), ("http://[2001:db8::1]:11434", True)])
def test_remote_ollama_counts_as_hosted(monkeypatch, url, hosted):
    """Un Ollama distant fait sortir le texte de la machine : même avertissement et même 409 qu'un fournisseur hébergé."""
    monkeypatch.setenv("ONTOFORGE_LLM_PROVIDER", "ollama")
    monkeypatch.setenv("OLLAMA_BASE_URL", url)
    p = get_provider()
    assert docdraft.is_hosted(p) is hosted
    if hosted:
        d = document.extract("a.txt", b"Un Garage entretient les Vehicules.")
        with pytest.raises(Exception) as e:
            docdraft.draft_document(P(), d, p, "fr")
        assert getattr(e.value, "status_code", None) == 409


def test_inverse_label_in_document_language(doc):
    out = {"classes": [{"name": "Garage", "source": EX}, {"name": "Véhicule", "source": EX}],
           "object_properties": [{"name": "accueille", "domain": "Garage", "range": "Véhicule", "inverse": "estAccueilliPar", "source": EX}]}
    r = docdraft.draft_document(P(), doc, FakeLLM([out]), "fr", confirm_hosted=True)
    inv = r["proposal"].object_properties[BASE + "estAccueilliPar"]
    assert inv.labels == {"fr": "est accueilli par"} and inv.inverse_of == BASE + "accueille"
    assert BASE + "estAccueilliPar" in r["provenance"]


def test_demo_document_route_is_read_only_pdf(client):
    """Le lien « Essayer avec le cahier des charges de démo » : PDF fixe servi en lecture seule, lisible par la route d'import."""
    r = client.get("/api/assistant/document/demo")
    assert r.status_code == 200 and r.headers["content-type"] == "application/pdf" and r.content.startswith(b"%PDF")
    up = client.post("/api/assistant/document/upload", files={"file": ("automaint-cahier-des-charges.pdf", r.content, "application/pdf")})
    assert up.status_code == 200 and up.json()["page_count"] == 2
    assert client.post("/api/assistant/document/demo").status_code == 405  # aucune écriture


def test_draft_reports_document_language(client):
    pid = client.post("/api/projects", json={"name": "doc"}).json()["id"]
    docp = {"name": "a.txt", "pages": [{"page": 1, "text": "Un Garage entretient les Véhicules. Le Garage a un nom."}]}
    r = client.post("/api/assistant/document/draft", json={"project_id": pid, "document": docp})
    assert r.status_code == 200 and r.json()["document"]["lang"] == "fr"
