"""L25 : amorcer une ontologie depuis un document (txt, md, pdf natif) : extraction, découpage, traçabilité, contrôles, repli sans LLM."""
import importlib.util
import io
import json
import pathlib

import httpx
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from ontoforge.assistant import docdraft, document, docheur
from ontoforge.assistant.providers import get_provider
from ontoforge.assistant.providers.base import LLMError
from ontoforge.core.onto_model import OntClass, OntoModel, OntologyMeta
from ontoforge.main import app

ROOT = pathlib.Path(__file__).resolve().parents[2]
BASE = "https://example.org/auto#"


def _gen():
    spec = importlib.util.spec_from_file_location("make_cdc", ROOT / "samples/automaint/make_cahier_des_charges.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def pdf_bytes():
    return _gen().build_pdf()  # PDF écrit à la main (aucune dépendance), 2 pages


@pytest.fixture
def doc(pdf_bytes):
    return document.extract("cdc.pdf", pdf_bytes)


class P:
    def __init__(self, onto=None):
        self.onto = onto or OntoModel(meta=OntologyMeta(iri=BASE.rstrip("#")))


@pytest.fixture(autouse=True)
def mock_env(monkeypatch):
    monkeypatch.setenv("ONTOFORGE_LLM_PROVIDER", "mock")


@pytest.fixture
def no_network(monkeypatch):
    """httpx remplacé par un faux qui échoue s'il est appelé."""
    calls = []

    def boom(*a, **k):
        calls.append(a)
        raise AssertionError("appel réseau interdit")
    monkeypatch.setattr(httpx, "post", boom)
    monkeypatch.setattr(httpx, "get", boom)
    real_send = httpx.Client.send

    def send(self, request, **k):  # le TestClient (hôte « testserver ») reste autorisé, tout le reste échoue
        if request.url.host != "testserver":
            return boom(request)
        return real_send(self, request, **k)
    monkeypatch.setattr(httpx.Client, "send", send)
    return calls


# ----------------------------------------------------------------------------- extraction
def test_pdf_two_pages_native_text(doc, pdf_bytes):
    assert pdf_bytes.startswith(b"%PDF") and len(doc.pages) == 2
    assert "Garage" in doc.pages[0].text and "Pneu" in doc.pages[1].text
    assert "é" in doc.pages[0].text  # accents conservés


def test_demo_pdf_is_committed_and_readable():
    d = document.extract("x.pdf", (ROOT / "samples/automaint/automaint-cahier-des-charges.pdf").read_bytes())
    assert len(d.pages) == 2


def test_scanned_pdf_is_refused():
    from pypdf import PdfWriter
    w = PdfWriter()
    w.add_blank_page(595, 842)
    w.add_blank_page(595, 842)
    b = io.BytesIO()
    w.write(b)
    with pytest.raises(document.DocumentError) as e:
        document.extract("scan.pdf", b.getvalue())
    assert e.value.status == 422 and "scann" in e.value.fr and "scanned" in e.value.en


def test_unsupported_empty_and_limits(monkeypatch, pdf_bytes):
    with pytest.raises(document.DocumentError) as e:
        document.extract("a.docx", b"x")
    assert e.value.status == 415
    with pytest.raises(document.DocumentError):
        document.extract("a.txt", b"  \n")
    monkeypatch.setenv("ONTOFORGE_DOC_MAX_PAGES", "1")
    with pytest.raises(document.DocumentError) as e:
        document.extract("cdc.pdf", pdf_bytes)
    assert e.value.status == 413
    monkeypatch.delenv("ONTOFORGE_DOC_MAX_PAGES")
    monkeypatch.setenv("ONTOFORGE_DOC_MAX_CHARS", "50")
    with pytest.raises(document.DocumentError):
        document.extract("a.txt", b"x" * 200)


def test_chunking_keeps_pages_and_paragraphs():
    text = "\n\n".join(f"Paragraphe {i}. " + "mot " * 60 for i in range(30))
    d = document.extract("long.md", text.encode())
    chunks = document.chunk(d, 2000)
    assert len(chunks) > 3 and all(c.chars <= 2300 for c in chunks)
    assert sum(len(c.segments) for c in chunks) == 30  # aucun paragraphe perdu ni coupé
    assert "[[p 1]]" in chunks[0].text


def test_locate_returns_real_page_and_short_excerpt(doc):
    page, ex = document.locate(doc, "un pneu est une pièce.", page_hint=1)  # indice de page faux, casse différente
    assert page == 2 and "Pneu est une Pièce" in ex and len(ex) <= 300
    assert document.locate(doc, "phrase totalement inventée par le modèle") is None


# ----------------------------------------------------------------------------- repli sans LLM + traçabilité
def test_heuristic_draft_on_demo_pdf(doc, no_network):
    r = docdraft.draft_document(P(), doc, get_provider(), "fr")
    assert r["engine"] == "heuristic" and r["approximate"] is True and r["stats"]["calls"] == 0
    labels = {c.labels.get("fr") for c in r["proposal"].classes.values()}
    assert {"Véhicule", "Garage", "Pneu", "Contrôle technique"} <= labels
    # chaque élément a une source, un extrait ≤ 300 retrouvé dans le document, et une page réelle
    all_iris = set(r["proposal"].classes) | set(r["proposal"].object_properties) | set(r["proposal"].datatype_properties)
    assert all_iris <= set(r["provenance"])
    for iri, src in r["provenance"].items():
        assert src["document"] == "cdc.pdf" and src["page"] in (1, 2) and 0 < len(src["excerpt"]) <= 300
        assert document.locate(doc, src["excerpt"]) is not None
    assert "Pneu" in r["provenance"][BASE + "Pneu"]["excerpt"]
    assert r["proposal"].classes[BASE + "Pneu"].sub_class_of == [BASE + "Piece"]
    assert any("approximatif" in w.lower() for w in r["warnings"])


def test_competency_questions_and_coverage(doc):
    r = docdraft.draft_document(P(), doc, get_provider(), "fr")
    qs = r["questions"]
    assert 5 <= len(qs) <= 10
    by = {q["text"]: q for q in qs}
    assert by["Quels pneus équipent un véhicule donné ?"]["covered"] is True
    assert by["Quel mécanicien a réalisé chaque intervention ?"]["covered"] is False
    assert by["Quel mécanicien a réalisé chaque intervention ?"]["terms"] == []


def test_heuristic_templates_when_document_has_no_questions():
    d = document.Document("n.txt", [document.Page(1, "Un Pneu est une Pièce. Un Pneu a une référence et une pression. Le Pneu est monté. La Pièce est stockée.")])
    r = docdraft.draft_document(P(), d, get_provider(), "en")
    assert len(r["questions"]) >= 3 and all("?" in q["text"] for q in r["questions"])


def test_lint_is_run_and_warnings_returned(doc):
    r = docdraft.draft_document(P(), doc, get_provider(), "fr")
    assert r["lint"] and {"level", "code", "message", "subject"} <= set(r["lint"][0])
    assert any(i["code"] == "W07" for i in r["lint"])
    en = docdraft.draft_document(P(), doc, get_provider(), "en")
    assert all("manquant" not in i["message"] for i in en["lint"] if i["code"] == "W07")


def test_existing_ontology_not_duplicated(doc):
    onto = OntoModel(meta=OntologyMeta(iri=BASE.rstrip("#")), classes={BASE + "Garage": OntClass(iri=BASE + "Garage", labels={"fr": "Garage"})})
    r = docdraft.draft_document(P(onto), doc, get_provider(), "fr")
    assert BASE + "Garage" not in r["provenance"]
    assert any(s["name"] == "Garage" for s in r["skipped"])
    # la relation remplacePneu cite Garage : référence conservée, pas de classe parasite ni de « modification »
    op = r["proposal"].object_properties[BASE + "remplacePneu"]
    assert op.domain == [BASE + "Garage"]
    assert r["proposal"].classes[BASE + "Garage"].labels == {"fr": "Garage"}


# ----------------------------------------------------------------------------- aucun envoi réseau
def test_mock_makes_no_network_call(doc, no_network):
    docdraft.draft_document(P(), doc, get_provider(), "fr")
    assert no_network == []
    pl = docdraft.plan(doc, get_provider())
    assert pl["hosted"] is False and pl["chars_sent"] == 0 and pl["engine"] == "heuristic"


def test_ollama_only_calls_configured_local_url(doc, monkeypatch):
    monkeypatch.setenv("ONTOFORGE_LLM_PROVIDER", "ollama")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
    urls = []

    def fake_post(url, headers=None, json=None, timeout=None):
        urls.append(url)
        sys = json["messages"][0]["content"]
        if "[TASK:docquestions]" in sys:
            body = {"questions": ["Quels pneus équipent un véhicule ?", "Quel garage remplace quels pneus ?"]}
        else:
            body = {"classes": [{"name": "Pneu", "label_fr": "Pneu", "source": {"page": 2, "excerpt": "Un Pneu est une Pièce."}}]}
        return httpx.Response(200, json={"message": {"content": __import__("json").dumps(body)}}, request=httpx.Request("POST", url))
    monkeypatch.setattr(httpx, "post", fake_post)
    p = get_provider()
    pl = docdraft.plan(doc, p)
    assert pl["hosted"] is False and pl["engine"] == "llm"
    r = docdraft.draft_document(P(), doc, p, "fr")  # pas de confirmation exigée en local
    assert r["engine"] == "llm" and urls and all(u.startswith("http://127.0.0.1:11434/") for u in urls)
    assert BASE + "Pneu" in r["provenance"]


class FakeLLM:
    """Fournisseur « hébergé » factice : renvoie des réponses prédéfinies, sans réseau."""
    name = "anthropic"
    model = "fake"
    configured = True

    def __init__(self, drafts, questions=None, fail=False):
        self.drafts, self.qs, self.fail, self.calls = list(drafts), questions or ["Quels pneus équipent un véhicule ?"], fail, 0

    def complete(self, system, messages, max_tokens=4096, json_schema=None):
        self.calls += 1
        if self.fail:
            raise LLMError("indisponible")
        if "[TASK:docquestions]" in system:
            return json.dumps({"questions": self.qs})
        return json.dumps(self.drafts.pop(0) if self.drafts else {})


def S(page, ex):
    return {"page": page, "excerpt": ex}


def test_hosted_requires_confirmation_and_sends_nothing_before(doc):
    llm = FakeLLM([{}])
    pl = docdraft.plan(doc, llm)
    assert pl["hosted"] and pl["chars_sent"] > 1000 and pl["calls"] == 1 + pl["chunks"]
    with pytest.raises(HTTPException) as e:
        docdraft.draft_document(P(), doc, llm, "fr")
    assert e.value.status_code == 409 and llm.calls == 0
    docdraft.draft_document(P(), doc, llm, "fr", confirm_hosted=True)
    assert llm.calls == 2


# ----------------------------------------------------------------------------- contrôles déterministes sur la sortie LLM
def test_llm_controls(doc, monkeypatch):
    monkeypatch.setenv("ONTOFORGE_DOC_CHUNK_CHARS", "900")  # plusieurs morceaux : le doublon vient d'un 2e appel
    good = {"classes": [
        {"name": "pneu", "label_fr": "Pneu", "parent": "Pièce", "source": S(2, "Un Pneu est une Pièce.")},
        {"name": "Piece", "label_fr": "Pièce", "parent": "Pneu", "source": S(2, "Un Pneu est une Pièce.")},  # cycle Pneu <-> Pièce
        {"name": "Licorne", "source": S(1, "Une licorne vole au-dessus du garage.")},  # extrait inventé
        {"name": "Garage", "label_fr": "Garage", "inconnu": 1, "source": S(1, "Garage : atelier qui accueille")},  # clé hors schéma
        {"name": "Thing", "source": S(1, "Garage : atelier")},  # nom réservé
        {"name": "Véhicule", "label_fr": "Véhicule", "source": S(1, "Véhicule : engin routier")},
    ], "datatype_properties": [
        {"name": "pression", "domain": "Pneu", "range": "decimal", "source": S(2, "une dimension, une pression")},
    ], "object_properties": [
        {"name": "equipe", "domain": "Véhicule", "range": "Pneus", "source": S(1, "Un Véhicule est équipé de Pneus.")},
    ]}
    dup = {"classes": [{"name": "Pneus", "label_en": "Tyre", "source": S(2, "Un Pneu a une référence")}]}  # doublon (pluriel) dans un 2e morceau
    r = docdraft.draft_document(P(), doc, FakeLLM([good, dup]), "fr", confirm_hosted=True)
    cl = r["proposal"].classes
    names = {k.split("#")[1] for k in cl}
    assert names == {"Pneu", "Piece", "Vehicule"}  # Licorne (extrait inventé), Garage (schéma strict), Thing écartés
    assert cl[BASE + "Pneu"].labels.get("en") == "Tyre"  # doublon fusionné
    assert not (cl[BASE + "Pneu"].sub_class_of and cl[BASE + "Piece"].sub_class_of)  # cycle cassé
    w = " ".join(r["warnings"])
    assert "introuvable" in w and "schéma invalide" in w and "Cycle" in w
    assert r["stats"]["merged"] >= 1 and r["stats"]["dropped"] >= 3
    assert r["provenance"][BASE + "pression"]["page"] == 2 and r["engine"] == "llm" and not r["approximate"]
    assert BASE + "equipe" in r["proposal"].object_properties
    assert r["proposal"].object_properties[BASE + "equipe"].range == [BASE + "Pneu"]  # « Pneus » résolu vers la classe fusionnée


def test_llm_error_falls_back_to_heuristic(doc):
    r = docdraft.draft_document(P(), doc, FakeLLM([], fail=True), "fr", confirm_hosted=True)
    assert r["engine"] == "heuristic" and r["approximate"] and BASE + "Pneu" in r["proposal"].classes
    assert any("repli" in w for w in r["warnings"])


def test_long_document_is_split_and_merged(monkeypatch):
    monkeypatch.setenv("ONTOFORGE_DOC_CHUNK_CHARS", "1200")
    paras = [f"Paragraphe {i} : le Garage entretient les véhicules avec soin et rigueur, jour après jour, sans exception." for i in range(40)]
    d = document.extract("long.txt", "\n\n".join(paras).encode())
    llm = FakeLLM([{"classes": [{"name": "Garage", "source": S(1, "le Garage entretient les véhicules")}]} for _ in range(20)])
    r = docdraft.draft_document(P(), d, llm, "fr", confirm_hosted=True)
    assert r["stats"]["chunks"] > 2 and llm.calls == 1 + r["stats"]["chunks"]
    assert len(r["proposal"].classes) == 1 and r["stats"]["merged"] == r["stats"]["chunks"] - 1


# ----------------------------------------------------------------------------- API
@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("ONTOFORGE_DATA", str(tmp_path))
    return TestClient(app)


def test_api_flow_never_applies_anything(client, pdf_bytes, no_network):
    pid = client.post("/api/projects", json={"name": "doc"}).json()["id"]
    before = client.get(f"/api/projects/{pid}").json()["onto"]
    up = client.post("/api/assistant/document/upload", files={"file": ("cdc.pdf", pdf_bytes, "application/pdf")})
    assert up.status_code == 200, up.text
    j = up.json()
    assert j["page_count"] == 2 and j["limits"]["max_pages"] >= 1
    docp = {"name": j["name"], "pages": j["pages"]}
    est = client.post("/api/assistant/document/estimate", json={"document": docp}).json()
    assert est["hosted"] is False and est["chars_sent"] == 0
    r = client.post("/api/assistant/document/draft", json={"project_id": pid, "document": docp})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["questions"] and d["provenance"] and d["proposal"]["classes"]
    assert client.get(f"/api/projects/{pid}").json()["onto"] == before  # rien d'appliqué sans acceptation
    assert no_network == []


def test_api_errors(client):
    assert client.post("/api/assistant/document/upload", files={"file": ("a.exe", b"MZ", "application/octet-stream")}).status_code == 415
    assert client.post("/api/assistant/document/upload", files={"file": ("a.txt", b" ", "text/plain")}).status_code == 422
    r = client.post("/api/assistant/document/draft", json={"project_id": "nope", "document": {"name": "a", "pages": [{"page": 1, "text": "x"}]}})
    assert r.status_code == 404


def test_api_error_language_follows_ui(client):
    client.put("/api/settings", json={"language": {"ui": "en", "labels": "en", "assistant": "en"}})
    r = client.post("/api/assistant/document/upload", files={"file": ("a.exe", b"MZ", "application/octet-stream")})
    assert "Unsupported" in r.json()["detail"]


def test_docheur_english():
    segs = [(1, "A Tyre is a Part. A Tyre has a pressure and a reference. The Tyre is mounted on a Vehicle. A Vehicle has a mileage. The Vehicle is old. The Part is stored.")]
    d = docheur.extract(segs)
    assert {c["name"] for c in d["classes"]} >= {"Tyre", "Part", "Vehicle"}
    assert any(c.get("parent") == "Part" for c in d["classes"])
    assert d["classes"][0].get("label_en")
