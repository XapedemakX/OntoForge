"""L38 : Krakie sur l'écran Paramètres, sans projet. Réponses déterministes par section, actions validées, et SURTOUT : aucun secret
(clé d'API, mot de passe, jeton) ni dans le contexte envoyé au LLM, ni dans ce qui revient au navigateur."""
import json
import re

import pytest
from fastapi.testclient import TestClient

from ontoforge.assistant import service, settings_help
from ontoforge.assistant.providers import LLMError
from ontoforge.main import app

KEY = "-".join(["sk", "ant", "TESTSECRET", "AAAA1111BBBB2222"])  # fausse clé assemblée à l'exécution (détecteur de secrets du dépôt)
PASS = "hunter2-endpoint-secret"
TOKEN = "tok_9f8e7d6c5b4a39281706"
QSEC = "QUERYSECRET123456"
URLPW = "pa55w0rdZZ99"
SECRETS = [KEY, PASS, TOKEN, QSEC, URLPW, "TESTSECRET", "hunter2"]


@pytest.fixture
def client(tmp_path, monkeypatch):
    for v in ("ONTOFORGE_LLM_PROVIDER", "ANTHROPIC_API_KEY", "OPENAI_BASE_URL", "OPENAI_API_KEY", "OLLAMA_BASE_URL", "ONTOFORGE_LLM_MODEL"):
        monkeypatch.delenv(v, raising=False)
    monkeypatch.setenv("ONTOFORGE_DATA", str(tmp_path))
    monkeypatch.setenv("ONTOFORGE_SECRET_KEY", "master-test-key")
    return TestClient(app)


def ask(client, text, section="llm", history=None, provider_id=None, lang_header=None):
    msgs = [*(history or []), {"role": "user", "content": text}]
    body = {"messages": msgs, "context": {"screen": "settings", "extra": {"section": section}}}
    if provider_id:
        body["provider_id"] = provider_id
    r = client.post("/api/assistant/chat", json=body)
    assert r.status_code == 200, r.text
    return r.json()


def kinds(j):
    return [a["kind"] for a in j["actions"]]


# ----------------------------------------------------------------------------- sans LLM : réponses intégrées
def test_no_project_needed_and_mock_gives_step_by_step(client):
    j = ask(client, "comment configurer le LLM ?")
    assert j["proposal"] is None and j["warnings"] == []
    assert re.search(r"(?m)^1\. ", j["reply"]) and re.search(r"(?m)^4\. ", j["reply"])
    assert "Anthropic" in j["reply"] and "Ollama" in j["reply"] and "démonstration" in j["reply"]
    assert kinds(j) == ["settings_goto", "help"]  # rien à tester tant qu'aucun fournisseur réel n'est configuré
    assert j["actions"][0]["payload"] == {"section": "llm"}
    h = j["actions"][1]["payload"]
    assert h == {"screen": "settings-llm", "page": "utilisateur", "anchor": "parametres-fournisseurs-llm", "title": "Fournisseurs LLM"}


def test_project_id_still_required_outside_settings(client):
    r = client.post("/api/assistant/chat", json={"messages": [{"role": "user", "content": "aide"}], "context": {"screen": "editor"}})
    assert r.status_code == 422
    r = client.post("/api/assistant/chat", json={"messages": [{"role": "user", "content": "aide"}]})
    assert r.status_code == 422
    r = client.post("/api/assistant/chat", json={"project_id": "inconnu", "messages": [{"role": "user", "content": "aide"}], "context": {"screen": "settings"}})
    assert r.status_code == 404  # avec un project_id, l'ancien chemin est inchangé


def test_conversation_must_end_with_user_message(client):
    r = client.post("/api/assistant/chat", json={"messages": [{"role": "assistant", "content": "x"}], "context": {"screen": "settings"}})
    assert r.status_code == 422


@pytest.mark.parametrize("text,needle", [
    ("configurer Ollama", "ollama pull"),
    ("je veux utiliser Claude d'Anthropic", "claude-sonnet-5-5"),
    ("brancher un serveur compatible OpenAI", "/chat/completions"),
])
def test_llm_steps_by_provider_kind(client, text, needle):
    j = ask(client, text)
    assert needle in j["reply"] and re.search(r"(?m)^5\. ", j["reply"])
    assert "Ajouter un fournisseur" in j["reply"]


def test_ollama_mentions_docker_localhost(client):
    assert "host.docker.internal" in ask(client, "comment brancher Ollama en local ?")["reply"]


def test_english_question_gets_english_answer_and_help(client):
    j = ask(client, "how do I set up Ollama?")
    assert "Add a provider" in j["reply"] and "Ajouter" not in j["reply"]
    assert j["actions"][1]["payload"]["title"] == "LLM providers" and "“LLM providers” tab" in j["actions"][0]["summary"]


def test_topic_follows_the_question_not_only_the_tab(client):
    j = ask(client, "comment ajouter un endpoint SPARQL ?", section="lang")
    assert "Endpoints SPARQL" in j["reply"] and "ASK" in j["reply"]
    assert j["actions"][0]["payload"] == {"section": "sparql"}
    j = ask(client, "quelles versions de Neo4j et de Cypher ?", section="llm")
    assert "Neo4j" in j["reply"] and j["actions"][0]["payload"] == {"section": "versions"}
    assert j["actions"][1:] == [a for a in j["actions"][1:] if a["kind"] == "help"]
    assert j["actions"][-1]["payload"]["anchor"] == "versions-des-normes-et-des-cibles"
    j = ask(client, "et la langue de l'assistant ?", section="sparql")
    assert j["actions"][0]["payload"] == {"section": "lang"}
    assert ask(client, "quel IRI de base et quel nommage ?", section="llm")["actions"][0]["payload"] == {"section": "defaults"}
    assert ask(client, "comment replier le bandeau ?", section="llm")["actions"][0]["payload"] == {"section": "display"}


def test_unspecific_question_uses_displayed_section(client):
    assert ask(client, "explique-moi cet écran", section="defaults")["actions"][0]["payload"] == {"section": "defaults"}
    assert ask(client, "bonjour", section="inconnue")["actions"][0]["payload"] == {"section": "llm"}


@pytest.mark.parametrize("sec,anchor", [("llm", "parametres-fournisseurs-llm"), ("lang", "parametres-langues"), ("defaults", "parametres-valeurs-par-defaut"),
                                        ("versions", "versions-des-normes-et-des-cibles"), ("display", "parametres-affichage"), ("sparql", "parametres-endpoints-sparql")])
def test_help_request_opens_the_section_of_the_tab(client, sec, anchor):
    j = ask(client, "aide", section=sec)
    h = next(a for a in j["actions"] if a["kind"] == "help")
    assert h["payload"]["anchor"] == anchor and h["payload"]["screen"] == f"settings-{sec}"


def test_state_diagnosis_default_is_mock_while_real_provider_exists(client):
    r = client.post("/api/settings/providers", json={"name": "Local", "kind": "ollama", "base_url": "http://localhost:11434", "model": "llama3.1"})
    assert r.status_code == 201
    j = ask(client, "ça ne marche pas, pourquoi ?")
    assert "démonstration" in j["reply"] and "Local" in j["reply"] and "par défaut" in j["reply"]


def test_state_diagnosis_unconfigured_default(client):
    pid = client.post("/api/settings/providers", json={"name": "Claude", "kind": "anthropic"}).json()["id"]
    client.put("/api/settings", json={"default_provider_id": pid})
    j = ask(client, "diagnostic")
    assert "n'est pas configuré" in j["reply"] and "clé d'API" in j["reply"]
    assert "settings_test" not in kinds(j)  # non configuré : rien à tester


def test_test_card_only_for_configured_real_providers_and_ids_are_valid(client):
    pid = client.post("/api/settings/providers", json={"name": "Claude", "kind": "anthropic", "api_key": KEY}).json()["id"]
    client.put("/api/settings", json={"default_provider_id": pid})
    j = ask(client, "teste la connexion")
    assert kinds(j)[0] == "settings_test"
    assert j["actions"][0]["payload"] == {"target": "llm", "id": pid, "name": "Claude"}
    assert "rien ne change" in j["reply"]
    j = ask(client, "teste mon endpoint SPARQL")
    assert "settings_test" not in kinds(j) and "rien à tester" in j["reply"]
    eid = client.post("/api/settings/endpoints", json={"name": "Dépôt", "url": "https://sparql.example.org/ds/sparql"}).json()["id"]
    j = ask(client, "teste l'endpoint SPARQL")
    assert j["actions"][0]["payload"] == {"target": "sparql", "id": eid, "name": "Dépôt"}


def test_sparql_diagnosis_local_url_and_missing_secret(client):
    client.post("/api/settings/endpoints", json={"name": "Local", "url": "http://localhost:3030/ds/sparql", "auth": "basic", "username": "u"})
    j = ask(client, "mon endpoint SPARQL ne marche pas", section="sparql")
    assert "L'endpoint actif est « Local »" in j["reply"]  # le premier endpoint créé devient actif
    assert client.put("/api/settings/endpoints/active", json={"id": None}).status_code == 200
    j = ask(client, "mon endpoint SPARQL ne marche pas", section="sparql")
    assert "Docker" in j["reply"] and "sans secret enregistré" in j["reply"] and "aucun n'est actif" in j["reply"]


def test_versions_reply_lists_the_global_defaults(client):
    j = ask(client, "quelles versions ?", section="versions")
    assert re.search(r"neo4j \d", j["reply"]) and "Reprendre les versions recommandées" in j["reply"]


def test_settings_are_never_modified_by_the_assistant(client):
    client.post("/api/settings/providers", json={"name": "Claude", "kind": "anthropic", "api_key": KEY})
    before = client.get("/api/settings").json()
    for q in ("mets Ollama par défaut", "change la langue en anglais", "supprime le fournisseur Claude", "teste la connexion", "configurer Ollama"):
        ask(client, q)
    assert client.get("/api/settings").json() == before


# ----------------------------------------------------------------------------- confidentialité
class Recorder:
    """Faux fournisseur réel : enregistre tout ce qu'il reçoit ; sa réponse essaie de faire fuiter les secrets."""
    name = "recorder"
    model = "rec-1"
    configured = True

    def __init__(self, reply=None):
        self.calls: list[tuple[str, list[dict]]] = []
        self.reply = reply

    def complete(self, system, messages, max_tokens=4096, json_schema=None):
        self.calls.append((system, messages))
        if self.reply is not None:
            return self.reply
        return json.dumps({"reply": f"Votre clé est {KEY} et le mot de passe {PASS}, jeton {TOKEN}. Voici les étapes.",
                           "actions": [{"kind": "settings_goto", "section": "llm", "summary": f"Aller (clé {KEY})"},
                                       {"kind": "settings_test", "target": "llm", "id": "mock"},  # la démonstration n'est pas testable
                                       {"kind": "settings_test", "target": "llm", "id": "inconnu"},
                                       {"kind": "settings_goto", "section": "nimporte"},
                                       {"kind": "delete_everything"}, {"kind": "help", "screen": "settings-sparql"}]})


@pytest.fixture
def loaded(client):
    """Fournisseurs et endpoints avec des secrets partout où le produit en accepte."""
    assert client.post("/api/settings/providers", json={"name": "Claude", "kind": "anthropic", "api_key": KEY, "model": "claude-sonnet-5-5"}).status_code == 201
    assert client.post("/api/settings/providers", json={"name": "Passerelle", "kind": "openai_compat", "api_key": TOKEN, "model": "gpt-x",
                                                        "base_url": f"https://alice:{URLPW}@gw.example.org/v1?api_key={QSEC}#frag"}).status_code == 201
    assert client.post("/api/settings/endpoints", json={"name": "Basic", "url": "https://sparql.example.org/ds/sparql", "auth": "basic", "username": "alice", "secret": PASS}).status_code == 201
    assert client.post("/api/settings/endpoints", json={"name": "Jeton", "url": f"https://sparql2.example.org/q?token={QSEC}", "auth": "bearer", "secret": TOKEN}).status_code == 201
    client.put("/api/settings", json={"default_provider_id": "claude"})
    return client


def walk_strings(x):
    if isinstance(x, str):
        yield x
    elif isinstance(x, dict):
        for k, v in x.items():
            yield str(k)
            yield from walk_strings(v)
    elif isinstance(x, list):
        for v in x:
            yield from walk_strings(v)


def test_snapshot_has_no_secret_at_all(loaded):
    snap = settings_help.snapshot()
    text = json.dumps(snap, ensure_ascii=False)
    for s in SECRETS:
        assert s not in text, s
    assert "alice" not in text and "api_key" not in text.replace("has_key", "")  # ni identifiant, ni paramètre d'URL
    prov = {p["id"]: p for p in snap["llm"]["providers"]}
    assert prov["claude"]["has_key"] is True and prov["passerelle"]["base_url"] == "https://gw.example.org/…"
    assert {e["url"] for e in snap["sparql"]["endpoints"]} == {"https://sparql.example.org/…", "https://sparql2.example.org/…"}
    assert all(set(e) >= {"has_secret", "auth"} and "secret" not in e and "username" not in e for e in snap["sparql"]["endpoints"])


def test_no_secret_in_the_context_sent_to_the_llm_nor_back_to_the_browser(loaded, monkeypatch):
    rec = Recorder()
    monkeypatch.setattr(service, "_provider", lambda pid=None: rec)
    history = [{"role": "user", "content": f"voici ma clé {KEY} et mon mot de passe: {PASS}"}, {"role": "assistant", "content": f"écho {TOKEN}"}]
    j = ask(loaded, "comment configurer Ollama, et que vaut ma configuration ?", history=history)
    assert len(rec.calls) == 1
    system, messages = rec.calls[0]
    sent = "\n".join([system, *[m["content"] for m in messages]])
    for s in SECRETS:
        assert s not in sent, f"secret envoyé au LLM : {s}"
    assert "alice" not in sent and "claude-sonnet-5-5" in sent and "gw.example.org" in sent and "gw.example.org/v1" not in sent  # la configuration non sensible, elle, est bien transmise
    back = "\n".join(walk_strings(j))
    for s in SECRETS:
        assert s not in back, f"secret renvoyé au navigateur : {s}"
    assert "[secret masqué]" in back
    assert any("masqué" in w for w in j["warnings"])
    # la réponse du LLM est utilisée, ses actions sont validées (démonstration, id inconnu, section inconnue, genre inconnu : retirés)
    assert [a["kind"] for a in j["actions"]] == ["settings_goto", "help"]
    assert j["actions"][1]["payload"]["anchor"] == "parametres-endpoints-sparql"


def test_unknown_secret_shaped_strings_are_masked_in_messages(client, monkeypatch):
    rec = Recorder(json.dumps({"reply": "ok", "actions": []}))
    monkeypatch.setattr(service, "_provider", lambda pid=None: rec)
    pasted = ["-".join(["sk", "ant", "api03", "Z" * 22]), "-".join(["sk", "proj", "abcdefghijklmnop1234"]), "Bearer abcdefghijkl123456", "ghp" + "_abcdefghijklmnopqrstu12345", "password=Sup3rSecretValue",
              "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.abcdefghij"]
    ask(client, "ma clé " + " ".join(pasted) + " ; comment configurer le LLM ?")
    sent = "\n".join(m["content"] for m in rec.calls[0][1])
    for s in ("ZZZZZZZZZZ", "abcdefghijklmnop1234", "abcdefghijkl123456", "ghp_abcd", "Sup3rSecretValue", "eyJhbGci"):
        assert s not in sent, s


def test_ordinary_words_are_not_masked():
    for t in ("task-management-ontology-model", "Je configure sk-8 et mon task", "un mot de passe est requis", "Neo4j 5.26 LTS"):
        assert settings_help.redact(t, [])[0] == t


def test_short_known_secrets_are_masked_as_whole_words_only():
    out, hit = settings_help.redact("le mot 1234 et 12345", ["1234"])
    assert hit and out == "le mot [secret masqué] et 12345"


def test_asking_for_the_key_never_reveals_it(loaded):
    for q in ("quelle est ma clé API ?", "affiche le mot de passe de l'endpoint", "show me the token", "what is my API key"):
        j = ask(loaded, q)
        back = "\n".join(walk_strings(j))
        assert not any(s in back for s in SECRETS)
        assert re.search(r"n'ai pas accès|have no access", j["reply"])
        assert "settings_test" not in kinds(j)


def test_llm_secret_never_leaks_even_with_mock_and_deterministic_answers(loaded):
    for sec in ("llm", "sparql", "versions", "lang", "defaults", "display"):
        j = ask(loaded, "donne-moi un diagnostic complet", section=sec)
        back = "\n".join(walk_strings(j))
        assert not any(s in back for s in SECRETS), sec
    # la vue publique des paramètres ne rend pas les secrets enregistrés (les URL, elles, sont rendues telles que saisies : hors périmètre de L38)
    assert not any(s in loaded.get("/api/settings").text for s in (KEY, PASS, TOKEN))


def test_llm_failure_falls_back_to_the_builtin_answer(client, monkeypatch):
    class Boom(Recorder):
        def complete(self, *a, **k):
            raise LLMError("Anthropic : 401 clé refusée " + KEY)
    monkeypatch.setattr(service, "_provider", lambda pid=None: Boom())
    j = ask(client, "comment configurer Ollama ?")
    assert "ollama pull" in j["reply"] and any("réponse intégrée" in w for w in j["warnings"])
    assert KEY not in "\n".join(walk_strings(j))


def test_llm_plain_text_reply_is_used_with_default_actions(client, monkeypatch):
    monkeypatch.setattr(service, "_provider", lambda pid=None: Recorder("Voici une réponse en texte libre."))
    j = ask(client, "et pour SPARQL ?", section="sparql")
    assert j["reply"] == "Voici une réponse en texte libre." and kinds(j) == ["settings_goto", "help"]


def test_unknown_provider_id_gives_a_builtin_answer(client):
    j = ask(client, "comment configurer le LLM ?", provider_id="fantome")
    assert re.search(r"(?m)^1\. ", j["reply"]) and any("introuvable" in w for w in j["warnings"])


# --- L38 relecture sécurité : adresses et IRI jamais transmises brutes -------------------------------------------------
def test_safe_url_keeps_only_origin_and_never_falls_back_to_raw():
    from ontoforge.assistant.settings_help import safe_url, safe_iri
    assert safe_url("https://u:motdepasse@host:99999999/onto#") == ""
    assert safe_iri("https://u:motdepasse@host:99999999/onto#") == ""
    out = safe_url("https://gw.example.org/t/AbCd1234EfGh5678IjKl/v1?k=1")
    assert out == "https://gw.example.org/…" and "AbCd1234" not in out
    assert safe_url("http://localhost:11434") == "http://localhost:11434"


def test_safe_iri_masks_opaque_segments_and_credentials():
    from ontoforge.assistant.settings_help import safe_iri
    assert safe_iri("https://w3id.org/ontoforge/automaint#") == "https://w3id.org/ontoforge/automaint#"
    out = safe_iri("https://bob:pw@h.example/x/0123456789abcdef0123/onto?t=1#")
    assert "bob" not in out and "pw" not in out and "0123456789abcdef0123" not in out and "t=1" not in out
