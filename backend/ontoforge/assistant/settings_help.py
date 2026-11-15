"""Krakie sur l'écran Paramètres (L38) : aide à la configuration, sans projet.

``run(messages, context, provider_id)`` -> ``{reply, actions, warnings, proposal: None}``.
Actions propres à ce mode (jamais appliquées par le serveur, l'utilisateur les déclenche) :
``settings_goto`` {section}, ``settings_test`` {target: llm|sparql, id, name}, ``help`` {screen, page, anchor, title}.

Confidentialité (test_settings_assistant.py) : seul l'instantané NON sensible de la configuration (``snapshot``) entre dans le contexte
envoyé au LLM. Aucune clé d'API, aucun mot de passe, aucun jeton, aucun identifiant d'utilisateur ; les URL sont débarrassées de leurs
identifiants et de leurs paramètres. Les messages de l'utilisateur et la réponse passent par ``redact`` (secrets enregistrés et formes
usuelles de clés). Sans LLM (fournisseur mock ou non configuré) ou si le LLM échoue : réponses déterministes par section.
"""
from __future__ import annotations

import json
import re
from typing import Any, Optional
from urllib.parse import urlsplit

from fastapi import HTTPException

from .agent import help_section, is_help_request, reply_lang
from .providers import LLMError
from .untrusted import fence, guard

SECTIONS = ("llm", "lang", "defaults", "versions", "display", "sparql")
LABELS = {"llm": ("Fournisseurs LLM", "LLM providers"), "lang": ("Langues", "Languages"), "defaults": ("Valeurs par défaut", "Defaults"),
          "versions": ("Versions", "Versions"), "display": ("Affichage", "Display"), "sparql": ("Endpoints SPARQL", "SPARQL endpoints")}
MASK = "[secret masqué]"

# ----------------------------------------------------------------------------- confidentialité
_SECRET_FORMS = [re.compile(p) for p in (
    r"(?<![A-Za-z0-9])sk-ant-[A-Za-z0-9_\-]{8,}", r"(?<![A-Za-z0-9])sk-[A-Za-z0-9_\-]{16,}", r"(?i)\bbearer\s+[A-Za-z0-9._~+/=\-]{12,}", r"\bgh[pousr]_[A-Za-z0-9]{20,}",
    r"\bAKIA[0-9A-Z]{16}\b", r"\bxox[abpr]-[A-Za-z0-9\-]{10,}", r"\beyJ[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{4,}",
    r"(?i)\b(?:api[_-]?key|apikey|token|secret|password|mot de passe|mdp)\s*[:=]\s*\S{6,}")]


def stored_secrets() -> list[str]:
    """Valeurs secrètes enregistrées (clés d'API, mots de passe, jetons) : servent uniquement à les masquer, jamais à les transmettre."""
    from ..settings import store
    s = store.load(persist=False)
    vals = [p.api_key for p in s.llm_providers] + [e.secret for e in s.sparql_endpoints]
    if s.sparql_endpoint.auth is not None:
        vals.append(s.sparql_endpoint.auth.secret)
    return sorted({v for v in vals if v and len(v) >= 4}, key=len, reverse=True)


def redact(text: str, known: Optional[list[str]] = None) -> tuple[str, bool]:
    """Masque les secrets enregistrés et les formes usuelles de clés. Renvoie (texte, quelque chose a été masqué)."""
    known = stored_secrets() if known is None else known
    out, hit = text or "", False
    for v in known:
        pat = re.escape(v) if len(v) >= 8 else rf"(?<![\w]){re.escape(v)}(?![\w])"
        out, n = re.subn(pat, MASK, out)
        hit = hit or n > 0
    for rx in _SECRET_FORMS:
        out, n = rx.subn(MASK, out)
        hit = hit or n > 0
    return out, hit


_OPAQUE = re.compile(r"^(?=.*\d)(?=.*[A-Za-z])[A-Za-z0-9_\-.~+=]{16,}$|^[0-9a-fA-F]{20,}$")


def _origin(u: str):
    """(schéma, hôte, port) ou None si l'adresse est invalide (port hors limites compris)."""
    try:
        p = urlsplit(u)
        host = p.hostname or ""
        if not p.scheme or not host:
            return None
        port = f":{p.port}" if p.port else ""
        return p, f"{p.scheme}://{host}{port}"
    except ValueError:
        return None


def safe_url(url: Optional[str]) -> str:
    """Adresse d'un service (endpoint, fournisseur) réduite à schéma, hôte et port : ni identifiants, ni chemin (il peut porter un
    jeton), ni paramètres, ni fragment. Un chemin non vide est signalé par « /… ». Adresse invalide : chaîne vide, jamais la valeur brute."""
    u = (url or "").strip()
    r = _origin(u) if u else None
    if not r:
        return ""
    p, origin = r
    return origin + ("/…" if p.path.strip("/") else "")


def safe_iri(iri: Optional[str]) -> str:
    """IRI de base (espace de noms) : schéma, hôte, port et chemin, sans identifiants, paramètres ni fragment ; les segments de
    chemin opaques (jetons probables : longue suite de lettres et chiffres, ou d'hexadécimal) sont remplacés par « … ».
    Adresse invalide : chaîne vide, jamais la valeur brute."""
    u = (iri or "").strip()
    r = _origin(u) if u else None
    if not r:
        return ""
    p, origin = r
    segs = ["…" if _OPAQUE.match(x) else x for x in p.path.split("/")]
    return origin + "/".join(segs) + ("#" if u.endswith("#") else "")


def snapshot(admin: bool = True) -> dict[str, Any]:
    """Configuration NON sensible : fournisseurs (type, modèle, URL nettoyée, configuré, clé présente oui/non), langues, défauts,
    versions, endpoints SPARQL (URL nettoyée, type d'authentification, secret présent oui/non). Ni clé, ni 4 derniers caractères,
    ni nom d'utilisateur, ni ``extra``. Pour un compte non administrateur (``admin=False``, L41) : aucune adresse de fournisseur ni
    d'endpoint (ni hôte, ni port) : il les utilise sans les voir."""
    from .. import standards
    from ..settings import store
    from ..settings.models import DEFAULT_MODELS
    s = store.load(persist=False)
    chk = standards.check(None, "en", base=s.versions.model_dump())
    return {
        "llm": {"default_provider_id": s.default_provider_id,
                "providers": [{"id": p.id, "name": p.name, "kind": p.kind, "model": p.model or DEFAULT_MODELS[p.kind], "base_url": safe_url(p.base_url) if admin else "",
                               "configured": p.configured, "has_key": bool(p.api_key), "key_unreadable": p.key_unreadable,
                               "default": p.id == s.default_provider_id} for p in s.llm_providers]},
        "language": s.language.model_dump(),
        "defaults": {"base_iri": safe_iri(s.defaults.base_iri), "target": s.defaults.target,
                     "naming": s.defaults.naming, "prefixes": sorted(s.defaults.prefixes)},
        "versions": {"values": s.versions.model_dump(), "needs_attention": chk["needs_attention"],
                     "gaps": [g["message"] for g in chk["gaps"] if g["severity"] != "info"], "recommended": chk["recommended"]},
        "sparql": {"active_endpoint_id": s.active_endpoint_id,
                   "endpoints": [{"id": e.id, "name": e.name, "url": safe_url(e.url) if admin else "", "auth": e.auth, "has_secret": bool(e.secret),
                                  "secret_unreadable": e.secret_unreadable, "default_graph": e.default_graph, "timeout_s": e.timeout_s,
                                  "active": e.id == s.active_endpoint_id} for e in s.sparql_endpoints]},
    }


# ----------------------------------------------------------------------------- sujet de la question
def _flat(text: str) -> str:
    import unicodedata
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()


_TOPICS: dict[str, list[tuple[str, int]]] = {
    "sparql": [(r"sparql|endpoint|triplestore|fuseki|graphdb|virtuoso|stardog|point d.acces", 2), (r"requetes? distant", 1)],
    "versions": [(r"version", 2), (r"neo4j|cypher|curiosity\.?library|shacl|norme|standard|obsolete|recommand", 1)],
    "lang": [(r"langue|language|francais|french|anglais|english|traduc|translat", 2), (r"libelle|label", 1)],
    "defaults": [(r"defaut|default|\biri\b|prefixe|prefix|nommage|naming|pascal|camel|espace de noms|namespace", 2)],
    "display": [(r"affichage|display|bandeau|sidebar|barre laterale|replie|theme|sombre|dark mode|mode clair", 2)],
    "llm": [(r"\bllm\b|fournisseur|provider|anthropic|claude|openai|gpt|ollama|mistral|azure|vllm|lm studio|mock|\bapi\b", 2), (r"\bcle\b|\bkey\b|modele|\bmodel\b|\bia\b|\bai\b", 1)],
}


def topic_of(message: str, section: Optional[str]) -> str:
    """Section dont la question parle ; sinon la section affichée ; sinon les fournisseurs LLM."""
    t = _flat(message)
    score = {k: sum(w for rx, w in pats if re.search(rx, t)) for k, pats in _TOPICS.items()}
    best = max(score.values())
    if best == 0:
        return section if section in SECTIONS else "llm"
    tied = [k for k, v in score.items() if v == best]
    return section if section in tied else next(k for k in _TOPICS if k in tied)


def kind_of(message: str) -> Optional[str]:
    t = _flat(message)
    if re.search(r"ollama|\blocal(?:e|ement)?\b|sans cle|on.?prem|hors ligne|offline", t):
        return "ollama"
    if re.search(r"anthropic|claude", t):
        return "anthropic"
    if re.search(r"openai|\bgpt|azure|vllm|lm studio|compatible|mistral|groq|together|openrouter", t):
        return "openai_compat"
    return None


_ASKS_SECRET = re.compile(r"(?:montre|affiche|donne|dis|revele|lis|quel(?:le)?\s+est|what\s+is|show|reveal|tell|print|display|give).{0,40}"
                          r"(?:\bcle\b|\bkey\b|mot de passe|password|jeton|token|secret)", re.I)
_TEST = re.compile(r"\b(?:teste|tester|test|verifie la connexion|check the connection|try the connection|ping)\b", re.I)
_DIAG = re.compile(r"ne (?:marche|fonctionne) pas|marche pas|erreur|echec|probleme|diagnos|pourquoi|bloque|ca ne|doesn.?t work|not working|fails?|failed|error|broken|"
                   r"why|wrong|debug|etat|ou en suis|status|where am i|configur(?:e|ation) actuelle|current config|\bok\b\s*\?", re.I)


# ----------------------------------------------------------------------------- textes (fr / en)
def _L(lang: str, fr: str, en: str) -> str:
    return en if lang == "en" else fr


def _label(sec: str, lang: str) -> str:
    return LABELS[sec][1 if lang == "en" else 0]


def _llm_state(snap: dict, lang: str) -> tuple[str, bool]:
    """(phrase d'état, tout va bien)."""
    provs = snap["llm"]["providers"]
    real = [p for p in provs if p["kind"] != "mock"]
    default = next((p for p in provs if p["default"]), None)
    ok_real = [p for p in real if p["configured"]]
    if default and default["kind"] != "mock" and default["configured"]:
        s = _L(lang, f"Le fournisseur par défaut est « {default['name']} » ({default['kind']}, modèle {default['model']}) : il est configuré. "
                     "La connexion n'a pas été vérifiée ici : utilisez « Tester la connexion ».",
               f"The default provider is “{default['name']}” ({default['kind']}, model {default['model']}): it is configured. "
               "The connection has not been checked here: use “Test connection”.")
        if default.get("key_unreadable"):
            return s + _L(lang, " Attention : sa clé est illisible (clé maître changée), ressaisissez-la.", " Warning: its key is unreadable (master key changed), enter it again."), False
        return s, True
    if default and default["kind"] != "mock":
        miss = _L(lang, "il manque la clé d'API", "the API key is missing") if default["kind"] == "anthropic" else _L(lang, "il manque l'URL de base", "the base URL is missing")
        return _L(lang, f"Le fournisseur par défaut « {default['name']} » n'est pas configuré : {miss}. Tant que c'est le cas, je réponds avec mes explications intégrées.",
                  f"The default provider “{default['name']}” is not configured: {miss}. Until then I answer with my built-in explanations."), False
    if ok_real:
        n = ok_real[0]["name"]
        return _L(lang, f"Le fournisseur par défaut est la démonstration (mock), sans appel réseau, alors que « {n} » est configuré : définissez-le par défaut pour qu'un vrai modèle réponde.",
                  f"The default provider is the demo (mock), with no network call, while “{n}” is configured: make it the default so a real model answers."), False
    if real:
        return _L(lang, "Aucun fournisseur réel n'est configuré : je réponds avec mes explications intégrées (fournisseur de démonstration, aucun appel réseau).",
                  "No real provider is configured: I answer with my built-in explanations (demo provider, no network call)."), False
    return _L(lang, "Aucun LLM n'est configuré : seul le fournisseur de démonstration (mock) existe, sans appel réseau. Je réponds donc avec mes explications intégrées, "
                    "ce qui suffit pour configurer le reste.",
              "No LLM is configured: only the demo provider (mock) exists, with no network call. I answer with my built-in explanations, which is enough to set up the rest."), False


def _steps(lang: str, items: list[tuple[str, str]]) -> str:
    return "\n".join(f"{i}. {_L(lang, fr, en)}" for i, (fr, en) in enumerate(items, 1))


_LLM_STEPS: dict[str, list[tuple[str, str]]] = {
    "anthropic": [
        ("Section « Fournisseurs LLM » : cliquez « Ajouter un fournisseur » et choisissez le type « Anthropic ».", "In “LLM providers”, click “Add a provider” and pick the type “Anthropic”."),
        ("Donnez un nom et un modèle (par défaut {model}).", "Give it a name and a model (default {model})."),
        ("Collez votre clé d'API dans le champ « Clé d'API » (créée dans votre console Anthropic). Elle est chiffrée sur le serveur et jamais réaffichée : ne la collez pas dans ce chat.",
         "Paste your API key in the “API key” field (created in your Anthropic console). It is encrypted on the server and never shown again: do not paste it in this chat."),
        ("Enregistrez, puis cliquez « Tester la connexion » (15 s au plus).", "Save, then click “Test connection” (15 s at most)."),
        ("Si le test réussit, cliquez « Définir par défaut » : c'est ce fournisseur qui me fera répondre avec un vrai modèle.", "If the test passes, click “Make default”: this provider will make me answer with a real model."),
    ],
    "openai_compat": [
        ("Section « Fournisseurs LLM » : « Ajouter un fournisseur », type « Compatible OpenAI » (OpenAI, Azure OpenAI, vLLM, LM Studio, passerelle d'entreprise…).",
         "In “LLM providers”: “Add a provider”, type “OpenAI-compatible” (OpenAI, Azure OpenAI, vLLM, LM Studio, company gateway…)."),
        ("URL de base : l'adresse de l'API jusqu'à « /v1 » (par exemple https://api.example.org/v1) ; OntoForge ajoute « /chat/completions ».",
         "Base URL: the API address up to “/v1” (for example https://api.example.org/v1); OntoForge appends “/chat/completions”."),
        ("Modèle : le nom exact attendu par le serveur (par défaut {model}).", "Model: the exact name the server expects (default {model})."),
        ("Clé d'API : seulement si le serveur en exige une, dans le champ prévu (jamais dans ce chat).", "API key: only if the server requires one, in the field provided (never in this chat)."),
        ("Enregistrez, « Tester la connexion », puis « Définir par défaut ».", "Save, “Test connection”, then “Make default”."),
    ],
    "ollama": [
        ("Sur la machine qui héberge le modèle : installez Ollama et récupérez un modèle, par exemple « ollama pull {model} ».", "On the machine hosting the model: install Ollama and pull a model, for example “ollama pull {model}”."),
        ("Section « Fournisseurs LLM » : « Ajouter un fournisseur », type « Ollama (local) ».", "In “LLM providers”: “Add a provider”, type “Ollama (local)”."),
        ("URL de base : http://localhost:11434 par défaut. Si OntoForge tourne dans Docker, « localhost » désigne le conteneur : utilisez l'adresse de la machine (par exemple http://host.docker.internal:11434).",
         "Base URL: http://localhost:11434 by default. If OntoForge runs in Docker, “localhost” means the container: use the host address (for example http://host.docker.internal:11434)."),
        ("Modèle : le nom du modèle récupéré (par défaut {model}). Aucune clé n'est nécessaire.", "Model: the name of the pulled model (default {model}). No key is needed."),
        ("Enregistrez, « Tester la connexion », puis « Définir par défaut ». Les données restent sur votre réseau.", "Save, “Test connection”, then “Make default”. Your data stays on your network."),
    ],
}


def _llm_reply(snap: dict, message: str, lang: str) -> str:
    from ..settings.models import DEFAULT_MODELS
    state, ok = _llm_state(snap, lang)
    kind = kind_of(message)
    if kind is None and not ok:
        return state + "\n\n" + _L(lang, "Pour brancher un vrai modèle :", "To connect a real model:") + "\n" + _steps(lang, [
            ("Choisissez le type : Anthropic (clé d'API), Compatible OpenAI (OpenAI, Azure OpenAI, vLLM, LM Studio… : URL et clé éventuelle) ou Ollama (local, sans clé, vos données restent chez vous).",
             "Pick the type: Anthropic (API key), OpenAI-compatible (OpenAI, Azure OpenAI, vLLM, LM Studio…: URL and optional key) or Ollama (local, no key, your data stays with you)."),
            ("« Ajouter un fournisseur », renseignez le nom, le modèle, puis l'URL ou la clé selon le type.", "“Add a provider”, fill in the name, the model, then the URL or the key depending on the type."),
            ("Enregistrez, puis « Tester la connexion ».", "Save, then “Test connection”."),
            ("« Définir par défaut » pour que ce fournisseur serve à l'assistant.", "“Make default” so this provider serves the assistant."),
        ]) + "\n\n" + _L(lang, "Dites-moi le type (par exemple « configurer Ollama ») pour le pas à pas détaillé.", "Tell me the type (for example “set up Ollama”) for the detailed steps.")
    if kind is None:
        return state + "\n\n" + _L(lang, "Rien d'obligatoire à changer. Pour vérifier la connexion, utilisez la carte « Tester la connexion » ci-dessous ; pour changer de fournisseur, dites-moi lequel "
                                        "(Anthropic, Compatible OpenAI, Ollama).",
                                   "Nothing mandatory to change. To check the connection, use the “Test connection” card below; to switch provider, tell me which one (Anthropic, OpenAI-compatible, Ollama).")
    head = {"anthropic": ("Pas à pas pour Anthropic :", "Steps for Anthropic:"), "openai_compat": ("Pas à pas pour un serveur compatible OpenAI :", "Steps for an OpenAI-compatible server:"),
            "ollama": ("Pas à pas pour Ollama (local) :", "Steps for Ollama (local):")}[kind]
    steps = _steps(lang, [(fr.replace("{model}", DEFAULT_MODELS[kind]), en.replace("{model}", DEFAULT_MODELS[kind])) for fr, en in _LLM_STEPS[kind]])
    return state + "\n\n" + _L(lang, *head) + "\n" + steps


def _sparql_reply(snap: dict, message: str, lang: str) -> str:
    eps = snap["sparql"]["endpoints"]
    act = next((e for e in eps if e["active"]), None)
    notes: list[str] = []
    if not eps:
        state = _L(lang, "Aucun endpoint SPARQL n'est enregistré : les requêtes ne peuvent interroger que le magasin local du projet.", "No SPARQL endpoint is registered: queries can only use the project's local store.")
    elif act is None:
        state = _L(lang, f"{len(eps)} endpoint(s) enregistré(s), mais aucun n'est actif : activez-en un pour qu'il soit interrogé.", f"{len(eps)} endpoint(s) registered, but none is active: activate one so it gets queried.")
    else:
        at = f"{act['url']}, " if act["url"] else ""
        state = _L(lang, f"L'endpoint actif est « {act['name']} » ({at}authentification {act['auth']}, délai {act['timeout_s']:g} s). Sa joignabilité n'a pas été vérifiée ici.",
                   f"The active endpoint is “{act['name']}” ({at}{act['auth']} authentication, {act['timeout_s']:g} s timeout). Its reachability has not been checked here.")
    for e in eps:
        if e["auth"] != "none" and not e["has_secret"]:
            notes.append(_L(lang, f"« {e['name']} » est en authentification {e['auth']} sans secret enregistré : ressaisissez le mot de passe ou le jeton.", f"“{e['name']}” uses {e['auth']} authentication with no stored secret: enter the password or token again."))
        if e["secret_unreadable"]:
            notes.append(_L(lang, f"Le secret de « {e['name']} » est illisible (clé maître changée) : ressaisissez-le.", f"The secret of “{e['name']}” is unreadable (master key changed): enter it again."))
        if e["url"] and re.match(r"https?://(localhost|127\.|0\.0\.0\.0|\[::1\])", e["url"]):
            notes.append(_L(lang, f"« {e['name']} » vise une adresse locale : si OntoForge tourne dans Docker, « localhost » désigne le conteneur ; sur une instance publique, les adresses locales sont refusées par la protection SSRF.",
                            f"“{e['name']}” targets a local address: if OntoForge runs in Docker, “localhost” means the container; on a public instance, local addresses are refused by SSRF protection."))
    steps = _steps(lang, [
        ("Section « Endpoints SPARQL » : « Ajouter un endpoint ».", "In “SPARQL endpoints”: “Add an endpoint”."),
        ("Nom lisible et URL complète du service de requête (http:// ou https://, souvent terminée par « /sparql »).", "A readable name and the full URL of the query service (http:// or https://, often ending in “/sparql”)."),
        ("Authentification : aucune, Basic (utilisateur + mot de passe) ou Bearer (jeton). Le secret se saisit dans son champ, jamais dans ce chat.", "Authentication: none, Basic (user + password) or Bearer (token). The secret goes in its own field, never in this chat."),
        ("Facultatif : graphe par défaut et délai (1 à 300 s).", "Optional: default graph and timeout (1 to 300 s)."),
        ("Enregistrez, puis « Tester » (requête « ASK {} »).", "Save, then “Test” (an “ASK {}” query)."),
        ("Activez l'endpoint : un seul est actif à la fois, il s'affiche en haut de l'écran.", "Activate the endpoint: only one is active at a time, shown at the top of the screen."),
    ])
    return "\n\n".join([state, *notes, _L(lang, "Pour en ajouter ou en corriger un :", "To add or fix one:") + "\n" + steps])


def _versions_reply(snap: dict, message: str, lang: str) -> str:
    v = snap["versions"]
    vals = v["values"]
    line = ", ".join(f"{k} {x}" for k, x in vals.items())
    state = _L(lang, f"Défaut global des versions visées par les générateurs : {line}.", f"Global default of the versions the generators aim for: {line}.")
    gaps = (" " + _L(lang, "À regarder : ", "To look at: ") + " ".join(v["gaps"])) if v["needs_attention"] and v["gaps"] else (" " + _L(lang, "Aucun écart avec la référence embarquée.", "No gap with the embedded reference."))
    steps = _steps(lang, [
        ("Section « Versions » : choisissez, pour chaque famille (Neo4j, Cypher, Curiosity.Library, SHACL, SPARQL, RDF), la version visée ; chaque choix affiche son statut (recommandée, supportée, obsolète…).",
         "In “Versions”: for each family (Neo4j, Cypher, Curiosity.Library, SHACL, SPARQL, RDF) choose the target version; each choice shows its status (recommended, supported, obsolete…)."),
        ("« Reprendre les versions recommandées » remplit les valeurs conseillées, sans rien enregistrer.", "“Use recommended versions” fills in the advised values without saving anything."),
        ("« Enregistrer » fixe le défaut ; un projet qui n'a rien choisi le suit. Chaque projet peut garder ses propres versions dans son écran Versions.", "“Save” sets the default; a project that chose nothing follows it. Each project can keep its own versions in its Versions screen."),
    ])
    return state + gaps + "\n\n" + steps + "\n\n" + _L(lang, "Rien n'est lu sur Internet : les statuts viennent de la référence embarquée.", "Nothing is read from the Internet: statuses come from the embedded reference.")


def _lang_reply(snap: dict, message: str, lang: str) -> str:
    lg = snap["language"]
    state = _L(lang, f"Réglages actuels : interface {lg['ui']}, libellés {lg['labels']}, assistant {lg['assistant']}.", f"Current settings: interface {lg['ui']}, labels {lg['labels']}, assistant {lg['assistant']}.")
    return state + "\n\n" + _steps(lang, [
        ("Interface : la langue des menus et messages ; elle s'applique tout de suite.", "Interface: the language of menus and messages; it applies immediately."),
        ("Libellés : la langue préférée des libellés d'ontologie affichés dans le graphe et les listes (une ontologie peut porter un libellé fr et un libellé en).", "Labels: the preferred language of ontology labels shown in the graph and lists (an ontology can carry both an fr and an en label)."),
        ("Assistant : la langue de mes réponses ; une question posée en anglais reçoit une réponse en anglais.", "Assistant: the language of my answers; a question asked in English gets an English answer."),
        ("« Enregistrer » les mémorise pour les prochaines sessions.", "“Save” remembers them for future sessions."),
    ])


def _defaults_reply(snap: dict, message: str, lang: str) -> str:
    d = snap["defaults"]
    state = _L(lang, f"Valeurs actuelles : IRI de base {d['base_iri']}, cible {d['target']}, {len(d['prefixes'])} préfixe(s).", f"Current values: base IRI {d['base_iri']}, target {d['target']}, {len(d['prefixes'])} prefix(es).")
    warn = ""
    if "example.org" in d["base_iri"]:
        warn = " " + _L(lang, "L'IRI de base est encore celle d'exemple (example.org) : remplacez-la par un espace de noms que vous maîtrisez avant de publier une ontologie.",
                        "The base IRI is still the example one (example.org): replace it with a namespace you control before publishing an ontology.")
    return state + warn + "\n\n" + _steps(lang, [
        ("IRI de base : le début des IRI créées (nouveaux projets et brouillons de l'assistant). Elle doit être absolue et finir par # ou /.", "Base IRI: the start of created IRIs (new projects and assistant drafts). It must be absolute and end with # or /."),
        ("Cible par défaut : Curiosity ou Neo4j pour les nouveaux projets.", "Default target: Curiosity or Neo4j for new projects."),
        ("Nommage : la convention des classes (types de nœuds) et des propriétés.", "Naming: the convention for classes (node types) and properties."),
        ("Préfixes : les abréviations d'espaces de noms (rdfs, skos…) ; chaque préfixe pointe vers une IRI absolue.", "Prefixes: the namespace abbreviations (rdfs, skos…); each prefix points to an absolute IRI."),
        ("« Enregistrer » : cela ne change pas les projets existants.", "“Save”: this does not change existing projects."),
    ])


def _display_reply(snap: dict, message: str, lang: str) -> str:
    return _L(lang, "L'affichage règle le bandeau latéral : « Automatique » le replie sur les écrans de plein canevas (éditeur, vue liste, fichiers, documentation), « Ouvert » le garde déplié, "
                    "« Replié » le garde en icônes. Ce réglage est mémorisé dans ce navigateur, pas sur le serveur ; Ctrl+B le bascule. Le thème (clair, sombre, système) se change avec le bouton de la barre du haut.",
              "Display sets the side bar: “Automatic” folds it on full-canvas screens (editor, list view, files, documentation), “Open” keeps it unfolded, “Folded” keeps it as icons. "
              "This setting is remembered in this browser, not on the server; Ctrl+B toggles it. The theme (light, dark, system) is changed with the button in the top bar.")


_REPLY = {"llm": _llm_reply, "sparql": _sparql_reply, "versions": _versions_reply, "lang": _lang_reply, "defaults": _defaults_reply, "display": _display_reply}


def _secret_reply(lang: str) -> str:
    return _L(lang, "Je n'ai pas accès à vos clés, mots de passe ni jetons, et personne ne peut les relire : ils sont chiffrés sur le serveur et jamais renvoyés au navigateur "
                    "(le tableau n'affiche que les quatre derniers caractères d'une clé longue). Pour en changer, utilisez « Remplacer la clé » dans le champ prévu ; "
                    "ne les collez jamais dans ce chat, je les masquerais de toute façon.",
              "I have no access to your keys, passwords or tokens, and nobody can read them back: they are encrypted on the server and never sent to the browser "
              "(the table only shows the last four characters of a long key). To change one, use “Replace the key” in the field provided; never paste them in this chat, I would mask them anyway.")


# ----------------------------------------------------------------------------- actions
def _goto_summary(sec: str, lang: str) -> str:
    return _L(lang, f"Onglet « {_label(sec, lang)} »", f"“{_label(sec, lang)}” tab")


def _test_action(snap: dict, topic: str, lang: str) -> Optional[dict[str, Any]]:
    if topic == "llm":
        provs = [p for p in snap["llm"]["providers"] if p["kind"] != "mock" and p["configured"]]
        p = next((x for x in provs if x["default"]), provs[0] if provs else None)
        if p:
            return {"kind": "settings_test", "target": "llm", "id": p["id"], "summary": _L(lang, f"Fournisseur « {p['name']} » ({p['kind']}, modèle {p['model']})", f"Provider “{p['name']}” ({p['kind']}, model {p['model']})")}
    if topic == "sparql":
        eps = snap["sparql"]["endpoints"]
        e = next((x for x in eps if x["active"]), eps[0] if eps else None)
        if e:
            return {"kind": "settings_test", "target": "sparql", "id": e["id"], "summary": _L(lang, f"Endpoint « {e['name']} »" + (f" ({e['url']})" if e["url"] else ""), f"Endpoint “{e['name']}”" + (f" ({e['url']})" if e["url"] else ""))}
    return None


def default_actions(snap: dict, topic: str, lang: str, test: bool = True) -> list[dict[str, Any]]:
    acts: list[dict[str, Any]] = [{"kind": "settings_goto", "section": topic, "summary": _goto_summary(topic, lang)}]
    t = _test_action(snap, topic, lang) if test else None
    if t:
        acts.append(t)
    acts.append({"kind": "help", "screen": f"settings-{topic}"})
    return acts


def build_actions(snap: dict, raw: Any, lang: str) -> list[dict[str, Any]]:
    """Valide les actions brutes (LLM ou repli) : sections connues, fournisseur / endpoint existants (jamais la démonstration), au plus 4."""
    out: list[dict[str, Any]] = []
    seen: set[tuple] = set()
    for a in (raw if isinstance(raw, list) else [])[:6]:
        if not isinstance(a, dict):
            continue
        kind = a.get("kind")
        if kind == "settings_goto" and a.get("section") in SECTIONS:
            sec = a["section"]
            key: tuple = ("goto", sec)
            act = {"kind": "settings_goto", "payload": {"section": sec}, "summary": str(a.get("summary") or "") or _goto_summary(sec, lang)}
        elif kind == "settings_test":
            tgt = a.get("target")
            ids = {p["id"]: p["name"] for p in snap["llm"]["providers"] if p["kind"] != "mock" and p["configured"]} if tgt == "llm" else \
                  {e["id"]: e["name"] for e in snap["sparql"]["endpoints"]} if tgt == "sparql" else {}
            ident = a.get("id")
            if ident not in ids:
                continue
            key = ("test", tgt, ident)
            act = {"kind": "settings_test", "payload": {"target": tgt, "id": ident, "name": ids[ident]},
                   "summary": str(a.get("summary") or "") or ids[ident]}
        elif kind == "help":
            sec = help_section(a.get("screen") if str(a.get("screen", "")).startswith("settings") else "settings", lang)
            key = ("help", sec["screen"])
            act = {"kind": "help", "payload": {k: sec[k] for k in ("screen", "page", "anchor", "title")}, "summary": sec["summary"]}
        else:
            continue
        if key not in seen:
            seen.add(key)
            out.append(act)
    return out[:4]


# ----------------------------------------------------------------------------- réponse
SETTINGS_SYSTEM = """[TASK:settings]
Tu es Krakie, l'assistante d'OntoForge, sur l'écran Paramètres (aucun projet ouvert). Tu aides à configurer : fournisseurs LLM (anthropic, openai_compat, ollama, mock),
langues, valeurs par défaut, versions des normes et des cibles, endpoints SPARQL, affichage. Tu connais la configuration NON sensible fournie ci-dessous.
Règles : tu n'as jamais accès aux clés d'API, mots de passe ni jetons, n'en demande pas et ne les répète pas ; dis de les saisir uniquement dans le champ prévu de l'écran.
Tu ne modifies rien : tu expliques, diagnostiques et recommandes ; les actions sont des cartes que l'utilisateur déclenche lui-même. Ne prétends pas avoir testé une connexion.
Réponds en {LANG}, de façon concise, avec des étapes numérotées quand on demande comment faire. Réponds par UN objet JSON :
{"reply":"...","actions":[{"kind":"settings_goto","section":"llm|lang|defaults|versions|display|sparql"},{"kind":"settings_test","target":"llm|sparql","id":"<id d'un fournisseur ou d'un endpoint de la configuration>"},{"kind":"help","screen":"settings-llm|settings-lang|settings-defaults|settings-versions|settings-display|settings-sparql"}]}
Aucun texte hors du JSON."""


def stored_addresses() -> list[str]:
    """Adresses enregistrées (fournisseurs, endpoints) : URL, ``hôte:port`` et hôte, pour les masquer à un compte non administrateur."""
    from ..settings import store
    s = store.load(persist=False)
    out: set[str] = set()
    for u in [p.base_url for p in s.llm_providers] + [e.url for e in s.sparql_endpoints] + [s.sparql_endpoint.url]:
        u = (u or "").strip()
        if not u:
            continue
        out.add(u.rstrip("/"))
        try:
            pr = urlsplit(u)
            host = pr.hostname or ""
            if host:
                out.add(f"{host}:{pr.port}" if pr.port else host)
                if host != "localhost":
                    out.add(host)
        except ValueError:
            pass
    return sorted((a for a in out if len(a) >= 4), key=len, reverse=True)


def _hide_addresses(text: str, addrs: list[str]) -> str:
    for a in addrs:
        text = re.sub(re.escape(a), "[adresse masquée]", text, flags=re.I)
    return text


def _drop_mentions(reply: str, known: list[str], addrs: Optional[list[str]] = None) -> str:
    return _hide_addresses(redact(reply, known)[0], addrs or [])


def deterministic(snap: dict, message: str, section: Optional[str], lang: str) -> dict[str, Any]:
    """Réponse intégrée : {reply, actions(brutes)}."""
    if _ASKS_SECRET.search(_flat(message)):
        topic = topic_of(message, section)
        return {"reply": _secret_reply(lang), "actions": default_actions(snap, topic, lang, test=False)}
    if is_help_request(message):
        sec = section if section in SECTIONS else "llm"
        h = help_section(f"settings-{sec}", lang)
        return {"reply": f"{h['title']} : {h['summary']}", "actions": [{"kind": "help", "screen": f"settings-{sec}"}, {"kind": "settings_goto", "section": sec}]}
    topic = topic_of(message, section)
    reply = _REPLY[topic](snap, message, lang)
    acts = default_actions(snap, topic, lang)
    if _TEST.search(_flat(message)) and topic in ("llm", "sparql"):
        t = _test_action(snap, topic, lang)
        if t:
            reply = (_L(lang, "Voici la carte pour tester la connexion : rien ne change tant que vous ne cliquez pas.", "Here is the card to test the connection: nothing changes until you click.")
                     + "\n\n" + reply.split("\n\n")[0])
            acts = [a for a in acts if a["kind"] == "settings_test"] + [a for a in acts if a["kind"] != "settings_test"]
        else:
            reply = _L(lang, "Il n'y a encore rien à tester.", "There is nothing to test yet.") + "\n\n" + reply
    return {"reply": reply, "actions": acts}


def run(messages: list[dict[str, Any]], context: dict[str, Any], provider_id: Optional[str] = None) -> dict[str, Any]:
    from . import service
    extra = context.get("extra") if isinstance(context.get("extra"), dict) else {}
    section = extra.get("section") if extra.get("section") in SECTIONS else None
    known = stored_secrets()
    msgs: list[dict[str, str]] = []
    masked = False
    for m in (messages or [])[-service.MSG_LIMIT:]:
        txt, hit = redact(str(m.get("content", "")), known)
        masked = masked or hit
        if txt.strip():
            msgs.append({"role": "assistant" if m.get("role") == "assistant" else "user", "content": txt})
    if not msgs or msgs[-1]["role"] != "user":
        raise HTTPException(status_code=422, detail="La conversation doit se terminer par un message de l'utilisateur.")
    last = msgs[-1]["content"]
    lang = reply_lang(last)
    from ..collab import access
    ctx = access.current()
    admin = ctx is not None and ctx.identity.is_admin   # échec fermé : sans contexte (appel hors middleware), traité comme non administrateur
    addrs = [] if admin else stored_addresses()  # L41 (L40-01) : un compte non administrateur ne reçoit aucune adresse, même par le LLM
    snap = snapshot(admin)
    warns: list[str] = []
    if masked:
        warns.append(_L(lang, "Un secret semblait figurer dans la conversation : je l'ai masqué avant tout traitement. Saisissez clés, mots de passe et jetons uniquement dans leur champ.",
                        "A secret seemed to be in the conversation: I masked it before any processing. Enter keys, passwords and tokens only in their own field."))
    try:
        p = service._provider(provider_id)
    except HTTPException:
        p = None
        if provider_id:
            warns.append(_L(lang, "Fournisseur introuvable : réponse intégrée.", "Provider not found: built-in answer."))
    real = p is not None and p.configured and getattr(p, "name", "mock") != "mock"
    asks_secret = bool(_ASKS_SECRET.search(_flat(last)))
    if real and not asks_secret and not is_help_request(last):
        topic = topic_of(last, section)
        user = (f"ÉCRAN : Paramètres (aucun projet)\nSECTION AFFICHÉE : {section or 'inconnue'}\nCONFIGURATION (non sensible) :\n"
                + fence("configuration non sensible", json.dumps(snap, ensure_ascii=False)) + "\n\nDEMANDE\n" + last)
        user, _ = redact(user, known)  # ceinture et bretelles : rien de secret ne part, même si une valeur enregistrée se retrouve dans une URL
        try:
            raw = p.complete(guard(SETTINGS_SYSTEM.replace("{LANG}", "français" if lang == "fr" else "English")), [*msgs[:-1], {"role": "user", "content": user}], 2000)
        except LLMError as exc:
            warns.append(_L(lang, "Le fournisseur LLM n'a pas répondu (", "The LLM provider did not answer (") + _hide_addresses(redact(str(exc), known)[0], addrs)[:160] + _L(lang, ") : réponse intégrée à la place.", "): built-in answer instead."))
        except Exception as exc:  # noqa: BLE001 — jamais de fuite : seul le type d'erreur est dit
            warns.append(_L(lang, f"Échec inattendu du fournisseur LLM ({type(exc).__name__}) : réponse intégrée à la place.", f"Unexpected LLM provider failure ({type(exc).__name__}): built-in answer instead."))
        else:
            from .convert import extract_json
            try:
                data = extract_json(raw)
                reply = str(data.get("reply") or "").strip()
                raw_actions = data.get("actions")
            except ValueError:
                reply, raw_actions = raw.strip(), None
            if reply:
                actions = build_actions(snap, raw_actions, lang) or build_actions(snap, default_actions(snap, topic, lang), lang)
                return {"reply": _drop_mentions(reply, known, addrs), "actions": _clean_actions(actions, known, addrs), "warnings": warns, "proposal": None}
    det = deterministic(snap, last, section, lang)
    actions = build_actions(snap, det["actions"], lang)
    return {"reply": _drop_mentions(det["reply"], known, addrs), "actions": _clean_actions(actions, known, addrs), "warnings": warns, "proposal": None}


def _clean_actions(actions: list[dict[str, Any]], known: list[str], addrs: Optional[list[str]] = None) -> list[dict[str, Any]]:
    """Dernier filet : aucune chaîne secrète (ni adresse, pour un non-administrateur) dans les cartes renvoyées au navigateur."""
    return json.loads(_hide_addresses(redact(json.dumps(actions, ensure_ascii=False), known)[0], addrs or []))
