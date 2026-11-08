"""Stockage des paramètres : ``$ONTOFORGE_DATA/settings.json``, secrets chiffrés, écriture atomique."""
from __future__ import annotations

import json
import logging
import os
import re
import tempfile
import threading
from pathlib import Path
from typing import Any

from .. import fsutil
from . import crypto
from .models import DEFAULT_MODELS, EndpointConfig, ProviderConfig, Settings, SparqlAuth

log = logging.getLogger("ontoforge.settings")
_LOCK = threading.RLock()
MOCK_ID = "mock"


def path() -> Path:
    return crypto.data_dir() / "settings.json"


def exists() -> bool:
    return path().exists()


def mock_provider() -> ProviderConfig:
    return ProviderConfig(id=MOCK_ID, name="Mock (démonstration)", kind="mock", model="mock")


def from_env() -> Settings:
    """Réglages initiaux déduits des variables d'environnement historiques ; le mock est toujours présent."""
    env = os.environ
    want = (env.get("ONTOFORGE_LLM_PROVIDER") or "").strip().lower()
    model = env.get("ONTOFORGE_LLM_MODEL") or ""
    provs: list[ProviderConfig] = []
    if env.get("ANTHROPIC_API_KEY") or want == "anthropic":
        provs.append(ProviderConfig(id="anthropic", name="Anthropic", kind="anthropic",
                                    model=model if want in ("anthropic", "") else "" or DEFAULT_MODELS["anthropic"],
                                    api_key=env.get("ANTHROPIC_API_KEY") or None))
    if env.get("OPENAI_BASE_URL") or want == "openai_compat":
        provs.append(ProviderConfig(id="openai", name="Compatible OpenAI", kind="openai_compat",
                                    base_url=env.get("OPENAI_BASE_URL") or None,
                                    model=model if want == "openai_compat" else DEFAULT_MODELS["openai_compat"],
                                    api_key=env.get("OPENAI_API_KEY") or None))
    if env.get("OLLAMA_BASE_URL") or want == "ollama":
        provs.append(ProviderConfig(id="ollama", name="Ollama", kind="ollama", base_url=env.get("OLLAMA_BASE_URL") or None,
                                    model=model if want == "ollama" else DEFAULT_MODELS["ollama"]))
    for p in provs:
        p.model = p.model or DEFAULT_MODELS[p.kind]
    provs.append(mock_provider())
    ids = {"anthropic": "anthropic", "openai_compat": "openai", "ollama": "ollama", "mock": MOCK_ID}
    default = ids.get(want) if ids.get(want) in {p.id for p in provs} else provs[0].id
    return Settings(llm_providers=provs, default_provider_id=default)


def _ensure_mock(s: Settings) -> Settings:
    if s.provider(MOCK_ID) is None:
        s.llm_providers.append(mock_provider())
    if s.provider(s.default_provider_id) is None:
        s.default_provider_id = MOCK_ID
    return s


def _to_disk(s: Settings, secret: str | None = None) -> dict[str, Any]:
    d = s.model_dump(mode="json")
    for raw, p in zip(d["llm_providers"], s.llm_providers):
        raw.pop("api_key", None)
        raw.pop("key_unreadable", None)
        if p.api_key:
            raw["api_key_enc"] = crypto.encrypt(p.api_key, secret)
    auth = d["sparql_endpoint"].get("auth")
    if auth is not None:
        auth.pop("secret", None)
        if s.sparql_endpoint.auth and s.sparql_endpoint.auth.secret:
            auth["secret_enc"] = crypto.encrypt(s.sparql_endpoint.auth.secret, secret)
    for raw, e in zip(d["sparql_endpoints"], s.sparql_endpoints):
        raw.pop("secret", None)
        raw.pop("secret_unreadable", None)
        if e.secret:
            raw["secret_enc"] = crypto.encrypt(e.secret, secret)
    return d


def migrate_endpoints(s: Settings) -> Settings:
    """L15 : l'ancien champ unique ``sparql_endpoint`` devient l'endpoint « default » (actif) s'il n'y a pas encore de liste."""
    old = s.sparql_endpoint
    if not s.sparql_endpoints and old.url:
        a = old.auth
        s.sparql_endpoints = [EndpointConfig(id="default", name="Endpoint SPARQL", url=old.url,
                                             auth=a.type if a else "none", username=a.username if a else None,
                                             secret=a.secret if a else None)]
        s.active_endpoint_id = s.active_endpoint_id or "default"
    if s.active_endpoint_id and s.endpoint(s.active_endpoint_id) is None:
        s.active_endpoint_id = s.sparql_endpoints[0].id if s.sparql_endpoints else None
    return s


def _from_disk(d: dict[str, Any], secret: str | None = None) -> Settings:
    unreadable: set[str] = set()
    for raw in d.get("llm_providers", []):
        tok = raw.pop("api_key_enc", None)
        raw.pop("api_key", None)  # jamais de clé en clair acceptée depuis le disque
        if tok:
            try:
                raw["api_key"] = crypto.decrypt(tok, secret)
            except crypto.SecretError:
                unreadable.add(raw.get("id", ""))
                log.warning("Clé d'API du fournisseur « %s » indéchiffrable : clé maître modifiée ?", raw.get("id"))
    auth = (d.get("sparql_endpoint") or {}).get("auth")
    if isinstance(auth, dict):
        tok = auth.pop("secret_enc", None)
        auth.pop("secret", None)
        if tok:
            try:
                auth["secret"] = crypto.decrypt(tok, secret)
            except crypto.SecretError:
                log.warning("Secret de l'endpoint SPARQL indéchiffrable.")
    ep_unreadable: set[str] = set()
    for raw in d.get("sparql_endpoints", []):
        tok = raw.pop("secret_enc", None)
        raw.pop("secret", None)
        if tok:
            try:
                raw["secret"] = crypto.decrypt(tok, secret)
            except crypto.SecretError:
                ep_unreadable.add(raw.get("id", ""))
                log.warning("Secret de l'endpoint « %s » indéchiffrable.", raw.get("id"))
    s = Settings.model_validate(d)
    for p in s.llm_providers:
        p.key_unreadable = p.id in unreadable
    for e in s.sparql_endpoints:
        e.secret_unreadable = e.id in ep_unreadable
    return migrate_endpoints(_ensure_mock(s))


def save(s: Settings, secret: str | None = None) -> None:
    with _LOCK:
        s = _ensure_mock(s)
        p = path()
        p.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(_to_disk(s, secret), ensure_ascii=False, indent=2)
        fsutil.atomic_write(p, payload, mode=0o600, prefix=".settings-")


def load(persist: bool = True) -> Settings:
    """Charge les réglages. Premier démarrage : déduits de l'environnement (et écrits si ``persist``)."""
    with _LOCK:
        p = path()
        if p.exists():
            try:
                return _from_disk(json.loads(p.read_text(encoding="utf-8")))
            except (ValueError, OSError) as exc:
                raise RuntimeError(f"settings.json illisible : {exc}") from None
        s = from_env()
        if persist:
            save(s)
            log.info("settings.json créé depuis l'environnement (%d fournisseur(s)).", len(s.llm_providers))
        return s


def slug_id(name: str, taken: set[str]) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:40] or "fournisseur"
    cand, i = base, 2
    while cand in taken:
        cand = f"{base}-{i}"
        i += 1
    return cand


def rotate(old_secret: str, new_secret: str) -> int:
    """Rechiffre tous les secrets de settings.json : lit avec ``old_secret``, écrit avec ``new_secret``."""
    with _LOCK:
        d = json.loads(path().read_text(encoding="utf-8"))
        s = _from_disk(d, old_secret)
        if any(p.key_unreadable for p in s.llm_providers) or any(e.secret_unreadable for e in s.sparql_endpoints):
            raise crypto.SecretError("Ancienne clé maître incorrecte : rotation annulée, rien n'a été modifié.")
        save(s, new_secret)
        return sum(1 for p in s.llm_providers if p.api_key) + (1 if s.sparql_endpoint.auth and s.sparql_endpoint.auth.secret else 0) \
            + sum(1 for e in s.sparql_endpoints if e.secret)
