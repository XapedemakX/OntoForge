"""L28 : table écran -> section du guide (ancres existantes) et intention « aide » de Krakie sur trois écrans."""
import json
import re
import unicodedata
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from ontoforge.assistant.agent import help_map, help_section, is_help_request
from ontoforge.main import app

GUIDE = Path(__file__).resolve().parents[2] / "docs" / "guide"


def slugify(text: str) -> str:
    """Même algorithme que frontend/src/lib/docs.ts : sans accents, sans numéro de section, minuscules, tirets."""
    t = re.sub(r"`|\*|_", "", re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text))
    t = unicodedata.normalize("NFD", t)
    t = "".join(c for c in t if not unicodedata.combining(c)).lower().replace("œ", "oe").replace("æ", "ae")
    t = re.sub(r"^\d+(?:\.\d+)*\.?\s+", "", t.strip())
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")


def anchors(md: str) -> dict[str, str]:
    out: dict[str, str] = {}
    seen: dict[str, int] = {}
    fence = False
    for line in md.splitlines():
        if line.lstrip().startswith("```"):
            fence = not fence
            continue
        m = None if fence else re.match(r"^(#{1,6})\s+(.+?)\s*#*\s*$", line)
        if not m:
            continue
        ex = re.search(r"\s*\{#([\w-]+)\}\s*$", m.group(2))  # L33 : identifiant explicite, commun aux versions fr et en
        title = m.group(2)[: ex.start()] if ex else m.group(2)
        base = ex.group(1) if ex else (slugify(title) or "section")
        n = seen.get(base, 0)
        seen[base] = n + 1
        out[base if n == 0 else f"{base}-{n + 1}"] = re.sub(r"`|\*", "", title)
    return out


def test_every_screen_points_to_an_existing_anchor():
    tbl = help_map()
    assert {"dashboard", "editor", "shapes", "analysis", "queries", "default"} <= set(tbl)
    for screen, e in tbl.items():
        f = GUIDE / f"{e['page']}.md"
        assert f.exists(), f"{screen}: page {e['page']} introuvable"
        found = anchors(f.read_text(encoding="utf-8"))
        assert e["anchor"] in found, f"{screen}: ancre #{e['anchor']} absente de {f.name}"
        for lang in ("fr", "en"):
            assert e["title"][lang].strip() and 20 < len(e["summary"][lang]) < 400, f"{screen}/{lang}"


def test_every_anchor_exists_in_the_english_version_too():
    """L33 : le bouton « ? » et Krakie ouvrent la bonne section en mode anglais : mêmes ancres dans <page>.en.md."""
    for screen, e in help_map().items():
        en = GUIDE / f"{e['page']}.en.md"
        assert en.exists(), f"{screen}: {en.name} manquant"
        assert e["anchor"] in anchors(en.read_text(encoding="utf-8")), f"{screen}: ancre #{e['anchor']} absente de {en.name}"


@pytest.mark.parametrize("fr", ["utilisateur", "limites", "contribuer", "api", "CHANGELOG"])
def test_english_guide_has_the_same_anchors_as_french(fr):
    a = list(anchors((GUIDE / f"{fr}.md").read_text(encoding="utf-8")))
    b = list(anchors((GUIDE / f"{fr}.en.md").read_text(encoding="utf-8")))
    assert a == b, f"{fr}: ancres fr/en différentes : {set(a) ^ set(b)}"


def test_anchor_slugs_are_stable_and_unique():
    found = anchors((GUIDE / "utilisateur.md").read_text(encoding="utf-8"))
    assert "analyse-arbitrage" in found and "ontologie-l-editeur-graphique" in found
    assert len(found) == len(set(found))


@pytest.mark.parametrize("text", ["aide", "Aide ?", "doc", "documentation", "comment ça marche ici", "Comment ça marche ?", "à quoi sert cet écran",
                                  "ouvre la doc", "help", "Help me", "how does this work", "How does this work here?", "open the documentation", "what is this screen"])
def test_help_intent_recognized(text):
    assert is_help_request(text)


@pytest.mark.parametrize("text", ["aide-moi à ajouter la classe Pneu", "ajoute la classe Pneu", "open the shapes", "ouvre les shapes", "delete Tyre", "cherche les véhicules"])
def test_help_intent_not_overreaching(text):
    assert not is_help_request(text)


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("ONTOFORGE_DATA", str(tmp_path))
    monkeypatch.setenv("ONTOFORGE_LLM_PROVIDER", "mock")
    return TestClient(app)


@pytest.fixture
def pid(client):
    r = client.post("/api/projects", json={"name": "AM", "sample": "automaint"})
    return r.json()["id"]


def ask(client, pid, text, screen):
    r = client.post("/api/assistant/chat", json={"project_id": pid, "messages": [{"role": "user", "content": text}],
                                                 "context": {"screen": screen, "projectId": pid}})
    assert r.status_code == 200, r.text
    return r.json()


@pytest.mark.parametrize("screen,text,anchor,title", [
    ("shapes", "aide", "shacl", "Shapes SHACL"),
    ("editor", "comment ça marche ici", "ontologie-l-editeur-graphique", "L'éditeur graphique"),
    ("analysis", "doc", "analyse-arbitrage", "Analyse et arbitrage"),
])
def test_help_action_fr_on_three_screens(client, pid, screen, text, anchor, title):
    j = ask(client, pid, text, screen)
    assert len(j["actions"]) == 1
    a = j["actions"][0]
    assert a["kind"] == "help"
    assert a["payload"] == {"screen": screen, "page": "utilisateur", "anchor": anchor, "title": title}
    assert 20 < len(a["summary"]) < 400 and "\n" not in a["summary"]
    assert title in j["reply"]


@pytest.mark.parametrize("screen,anchor", [("queries", "requetes-requetage-interactif"), ("exports", "exports"), ("model", "modele-cible")])
def test_help_action_en(client, pid, screen, anchor):
    j = ask(client, pid, "how does this work", screen)
    a = j["actions"][0]
    assert a["kind"] == "help" and a["payload"]["anchor"] == anchor
    assert a["payload"]["title"].isascii() and a["summary"].isascii()  # réponse en anglais


def test_help_unknown_screen_falls_back_to_overview(client, pid):
    a = ask(client, pid, "help", "unknown")["actions"][0]
    assert a["payload"]["screen"] == "default" and a["payload"]["page"] == "utilisateur"


def test_help_section_matches_map():
    s = help_section("shacl", "en")
    assert s["anchor"] == "shacl" and s["title"] == "SHACL validation"
    assert json.dumps(s)
