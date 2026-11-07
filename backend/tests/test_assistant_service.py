"""Assistant L6 : fournisseurs, pré-analyseurs, conversion JSON → OntoModel, service (fournisseur mock, aucun réseau)."""
import json

import httpx
import pytest
from fastapi import HTTPException

from ontoforge.assistant import service
from ontoforge.assistant.analyzers import analyze_csv, analyze_sql
from ontoforge.assistant.convert import extract_json, to_onto
from ontoforge.assistant.providers import LLMError, get_provider
from ontoforge.core.onto_model import XSD, OntoModel

B = "https://example.org/auto#"

SQL = """
-- parc automobile
CREATE TABLE owners (id SERIAL PRIMARY KEY, full_name VARCHAR(100) NOT NULL);
CREATE TABLE vehicles (
  id SERIAL PRIMARY KEY, vin VARCHAR(17) NOT NULL UNIQUE, mileage INT, registered DATE,
  owner_id INT REFERENCES owners(id)
);
CREATE TABLE parts (part_no VARCHAR(20) PRIMARY KEY, unit_price DECIMAL(10,2));
CREATE TABLE repair_orders (
  order_no VARCHAR(20) PRIMARY KEY, vehicle_id INT NOT NULL, opened_at TIMESTAMP,
  CONSTRAINT fk_v FOREIGN KEY (vehicle_id) REFERENCES vehicles(id)
);
CREATE TABLE order_parts (order_no VARCHAR(20), part_no VARCHAR(20), qty INT,
  PRIMARY KEY (order_no, part_no),
  FOREIGN KEY (order_no) REFERENCES repair_orders(order_no),
  FOREIGN KEY (part_no) REFERENCES parts(part_no));
"""
CSV = "# table: vehicles\nvin;mileage;registered_on;electric;owner_id\nVF1AAA;12000;2020-01-02;false;7\nVF1BBB;300;2021-05-06;true;8\n"


@pytest.fixture(autouse=True)
def mock_env(monkeypatch):
    monkeypatch.setenv("ONTOFORGE_LLM_PROVIDER", "mock")


def test_status_mock_and_unconfigured(monkeypatch):
    st = service.status()
    assert {k: st[k] for k in ("provider", "model", "configured")} == {"provider": "mock", "model": "mock", "configured": True}
    assert any(p["id"] == "mock" for p in st["providers"])
    monkeypatch.setenv("ONTOFORGE_LLM_PROVIDER", "anthropic")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ONTOFORGE_LLM_MODEL", raising=False)
    st = service.status()
    assert {k: st[k] for k in ("provider", "model", "configured")} == {"provider": "anthropic", "model": "claude-sonnet-5-5", "configured": False}
    monkeypatch.setenv("ONTOFORGE_LLM_PROVIDER", "nimporte")
    assert service.status()["configured"] is False


def test_sql_analyzer():
    sk = analyze_sql(SQL)
    names = {c["name"] for c in sk["classes"]}
    assert names == {"Owner", "Vehicle", "Part", "RepairOrder", "OrderPart"}
    veh = next(c for c in sk["classes"] if c["name"] == "Vehicle")
    assert veh["key"] == ["id"]
    ops = {(o["domain"], o["range"]) for o in sk["object_properties"]}
    assert ("Vehicle", "Owner") in ops and ("RepairOrder", "Vehicle") in ops and ("OrderPart", "Part") in ops
    dps = {(d["domain"], d["name"]): d for d in sk["datatype_properties"]}
    assert ("Vehicle", "ownerId") not in dps  # FK -> relation, pas attribut
    assert dps[("Vehicle", "mileage")]["range"] == "integer" and dps[("Part", "unitPrice")]["range"] == "decimal"
    assert dps[("RepairOrder", "openedAt")]["range"] == "dateTime"
    assert any("jointure" in w for w in sk["warnings"])


def test_csv_analyzer():
    sk = analyze_csv(CSV)
    assert sk["classes"][0]["name"] == "Vehicle"
    d = {x["name"]: x for x in sk["datatype_properties"]}
    assert d["mileage"]["range"] == "integer" and d["electric"]["range"] == "boolean" and d["registeredOn"]["range"] == "dateTime"
    assert sk["object_properties"][0]["range"] == "Owner"
    assert any("xsd:date" in w for w in sk["warnings"])


def test_draft_sql_with_mock_is_valid_onto():
    r = service.draft(SQL, "sql", B)
    onto = r["proposal"]
    assert isinstance(onto, OntoModel) and B + "RepairOrder" in onto.classes
    assert onto.object_properties[B + "hasOwner"].domain == [B + "Vehicle"]
    assert onto.classes[B + "Vehicle"].labels.get("fr")  # le mock ajoute le libellé fr
    assert r["explanation"] and isinstance(r["warnings"], list)


def test_draft_text_mock_automotive():
    r = service.draft("Un garage répare des véhicules pour des propriétaires.", "text", "https://example.org/auto")
    o = r["proposal"]
    assert B + "Vehicle" in o.classes and o.classes[B + "Car"].sub_class_of == [B + "Vehicle"]
    assert o.classes[B + "Vehicle"].has_keys == [[B + "vin"]]
    assert o.datatype_properties[B + "registrationDate"].range == [XSD + "dateTime"]  # pas de xsd:date (OWL 2 DL)
    assert any(r_.kind == "min" and r_.property == B + "vin" for r_ in o.classes[B + "Vehicle"].restrictions)
    assert o.object_properties[B + "ownedBy"].inverse_of == B + "owns" and B + "owns" in o.object_properties
    assert o.classes[B + "Person"].annotations[0].value == "https://schema.org/Person"
    assert any("xsd:date" in w for w in r["warnings"])


def test_draft_validation_errors():
    with pytest.raises(HTTPException) as e:
        service.draft("  ", "text")
    assert e.value.status_code == 422
    with pytest.raises(HTTPException):
        service.draft("x", "xml")


def test_draft_unconfigured_fallback(monkeypatch):
    monkeypatch.setenv("ONTOFORGE_LLM_PROVIDER", "anthropic")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    r = service.draft(SQL, "sql", B)  # repli déterministe
    assert B + "Vehicle" in r["proposal"].classes and "non configuré" in r["explanation"]
    with pytest.raises(HTTPException) as e:
        service.draft("un garage", "text")
    assert e.value.status_code == 503 and "non configuré" in e.value.detail


# ---- conversion et robustesse ------------------------------------------------------------
def test_extract_json_variants():
    assert extract_json('Voici :\n```json\n{"a": 1}\n```') == {"a": 1}
    for bad in ("pas de json", '{"a": ', "[1,2]"):
        with pytest.raises(ValueError):
            extract_json(bad)


def test_to_onto_cleanup():
    data = {"classes": [{"name": "my class", "parent": "Missing", "key": ["nope"]}, {"name": "A", "parent": "A2"}, {"name": "A2", "parent": "A"}],
            "object_properties": [{"name": "rel", "domain": "Ghost", "range": "A", "max": 1, "characteristics": ["transitive", "bogus"]}],
            "datatype_properties": [{"name": "when", "domain": "A", "range": "gYear"}, {"name": "x", "domain": "A", "range": "weird"}]}
    onto, w = to_onto(data, B)
    assert B + "MyClass" in onto.classes and B + "Missing" in onto.classes and B + "Ghost" in onto.classes
    assert onto.object_properties[B + "rel"].characteristics == ["transitive"]
    assert onto.classes[B + "Ghost"].restrictions[0].kind == "max"
    assert onto.datatype_properties[B + "when"].range == [XSD + "integer"]
    assert onto.datatype_properties[B + "x"].range == [XSD + "string"]
    text = " ".join(w)
    assert "Cycle" in text and "Clé" in text and "gYear" in text and "inconnu" in text
    assert not onto.classes[B + "A"].sub_class_of or not onto.classes[B + "A2"].sub_class_of


class Flaky:
    name, model, configured = "flaky", "f", True

    def __init__(self, outs):
        self.outs, self.calls = list(outs), 0

    def complete(self, system, messages, max_tokens=4096, json_schema=None):
        self.calls += 1
        return self.outs.pop(0)


def test_invalid_json_retry_once(monkeypatch):
    good = json.dumps({"classes": [{"name": "Vehicle"}], "explanation": "ok"})
    p = Flaky(["désolé, voici du texte", good])
    monkeypatch.setattr(service, "get_provider", lambda: p)
    r = service.draft("un véhicule", "text", B)
    assert p.calls == 2 and B + "Vehicle" in r["proposal"].classes
    p2 = Flaky(["pas json", "toujours pas"])
    monkeypatch.setattr(service, "get_provider", lambda: p2)
    with pytest.raises(HTTPException) as e:
        service.draft("un véhicule", "text", B)
    assert p2.calls == 2 and e.value.status_code == 502 and "JSON" in e.value.detail


def test_llm_error_falls_back_on_skeleton(monkeypatch):
    class Boom(Flaky):
        def complete(self, *a, **k):
            raise LLMError("Anthropic : délai dépassé (120 s).")
    monkeypatch.setattr(service, "get_provider", lambda: Boom([]))
    r = service.draft(CSV, "csv", B)
    assert B + "Vehicle" in r["proposal"].classes and any("délai" in w for w in r["warnings"])
    with pytest.raises(HTTPException) as e:
        service.draft("un texte", "text")
    assert e.value.status_code == 502


# ---- shapes / explain --------------------------------------------------------------------
def test_propose_shapes_mock():
    onto = service.draft("Un garage répare des véhicules", "text", B)["proposal"]
    r = service.propose_shapes(onto, None)
    sm = r["proposal"]
    vin = next(p for s in sm.shapes.values() for p in s.properties if p.path.iri == B + "vin")
    assert vin.pattern == "^[A-HJ-NPR-Z0-9]{17}$" and vin.messages.get("fr")
    miles = next(p for s in sm.shapes.values() for p in s.properties if p.path.iri == B + "mileage")
    assert miles.min_inclusive == "0"
    assert "Enrichissement" in r["explanation"]


def test_explain_mock_and_unconfigured(monkeypatch):
    from ontoforge.core.pg_model import Finding, Option
    f = Finding(id="C02:x", rule="C02", severity="review", title="Sous-classe", detail="Car sous-classe de Vehicle", subject=B + "Car",
                options=[Option(id="flatten", label="Aplatir", impact="x")], recommended="flatten", rationale="un seul label suffit")
    t = service.explain(f, "curiosity", OntoModel.model_validate({"meta": {"iri": B}}))["text"]
    assert "C02" in t and "flatten" in t and "Curiosity" in t
    monkeypatch.setenv("ONTOFORGE_LLM_PROVIDER", "ollama")
    monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)
    assert "C02" in service.explain(f, "neo4j", None)["text"]


# ---- vrais fournisseurs (httpx simulé) ---------------------------------------------------
def test_anthropic_request(monkeypatch):
    seen = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        seen.update(url=url, headers=headers, json=json)
        return httpx.Response(200, json={"content": [{"type": "text", "text": "{\"ok\":1}"}]}, request=httpx.Request("POST", url))
    monkeypatch.setattr(httpx, "post", fake_post)
    monkeypatch.setenv("ONTOFORGE_LLM_PROVIDER", "anthropic")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-secret")
    p = get_provider()
    assert p.configured and p.complete("sys", [{"role": "user", "content": "x"}], 100, {"type": "object"}) == '{"ok":1}'
    assert seen["url"] == "https://api.anthropic.com/v1/messages" and seen["headers"]["anthropic-version"] == "2023-06-01"
    assert seen["headers"]["x-api-key"] == "sk-secret" and seen["json"]["model"] == "claude-sonnet-5-5" and "JSON" in seen["json"]["system"]


def test_openai_and_ollama_requests(monkeypatch):
    urls = []

    def fake_post(url, headers=None, json=None, timeout=None):
        urls.append(url)
        body = {"choices": [{"message": {"content": "A"}}]} if "chat/completions" in url else {"message": {"content": "B"}}
        return httpx.Response(200, json=body, request=httpx.Request("POST", url))
    monkeypatch.setattr(httpx, "post", fake_post)
    monkeypatch.setenv("ONTOFORGE_LLM_PROVIDER", "openai_compat")
    monkeypatch.setenv("OPENAI_BASE_URL", "http://llm.local/v1/")
    assert get_provider().complete("s", [{"role": "user", "content": "x"}]) == "A"
    monkeypatch.setenv("ONTOFORGE_LLM_PROVIDER", "ollama")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://ollama:11434")
    assert get_provider().complete("s", [{"role": "user", "content": "x"}]) == "B"
    assert urls == ["http://llm.local/v1/chat/completions", "http://ollama:11434/api/chat"]


def test_provider_errors_in_french_without_key(monkeypatch):
    monkeypatch.setenv("ONTOFORGE_LLM_PROVIDER", "anthropic")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-secret")
    for resp, frag in ((httpx.Response(401, text="bad sk-secret"), "authentification"), (httpx.Response(429), "limite"), (httpx.Response(503), "indisponible")):
        monkeypatch.setattr(httpx, "post", lambda url, headers=None, json=None, timeout=None, r=resp: r)
        with pytest.raises(LLMError) as e:
            get_provider().complete("s", [{"role": "user", "content": "x"}])
        assert frag in str(e.value) and "sk-secret" not in str(e.value)

    def timeout(*a, **k):
        raise httpx.ReadTimeout("t")
    monkeypatch.setattr(httpx, "post", timeout)
    with pytest.raises(LLMError, match="délai"):
        get_provider().complete("s", [{"role": "user", "content": "x"}])


def test_csv_class_name_from_filename():
    from ontoforge.assistant.analyzers import analyze_csv
    sk = analyze_csv("marque;km\nRenault;1200\n", "vehicules.csv")
    assert [c["name"] for c in sk["classes"]] == ["Vehicule"]
    assert not any("Record" in w for w in sk["warnings"])
    assert [c["name"] for c in analyze_csv("marque;km\nR;1\n")["classes"]] == ["Record"]
