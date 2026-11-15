"""Modèles pydantic des paramètres. Les secrets (``api_key``, ``auth.secret``) n'existent qu'en mémoire serveur :
les vues publiques (``public_view``) n'exposent que ``has_key`` / ``key_last4``."""
from __future__ import annotations

import contextvars
import logging
import re
from typing import Any, Literal, Optional
from urllib.parse import urlsplit

from pydantic import BaseModel, Field, field_validator, model_validator

from ..standards import TargetVersions

Kind = Literal["anthropic", "openai_compat", "ollama", "mock"]
DEFAULT_MODELS = {"anthropic": "claude-sonnet-5-5", "openai_compat": "gpt-4o", "ollama": "llama3.1", "mock": "mock"}
_ID = re.compile(r"^[a-z0-9][a-z0-9_-]{0,47}$")
log = logging.getLogger("ontoforge.settings")

# L39-secu (SEC-03) : un secret est lié à l'origine (schéma, hôte, port) pour laquelle il a été saisi. Si une configuration
# validée change cette origine sans fournir un NOUVEAU secret, le secret enregistré est effacé : il ne peut ni partir vers une
# autre adresse (routes de test, conversation) ni être récupéré en changeant l'URL. Pendant la lecture du disque, le contrôle est suspendu.
LOADING: contextvars.ContextVar[bool] = contextvars.ContextVar("ontoforge_settings_loading", default=False)


def origin(url: Optional[str]) -> str:
    """Origine normalisée d'une URL (``https://hôte:port``) ; chaîne vide si absente (adresse par défaut du fournisseur)."""
    u = (url or "").strip()
    if not u:
        return ""
    try:
        sp = urlsplit(u)
        port = sp.port or {"http": 80, "https": 443}.get(sp.scheme.lower())
        return f"{sp.scheme.lower()}://{(sp.hostname or '').lower()}:{port}"
    except ValueError:
        return u.lower()


def _registered():
    from . import store  # import tardif : store importe ce module
    return store.registered()


class ProviderConfig(BaseModel):
    id: str
    name: str
    kind: Kind
    base_url: Optional[str] = None
    model: str = ""
    api_key: Optional[str] = Field(default=None, repr=False)  # jamais sérialisée vers l'API
    extra: dict[str, Any] = Field(default_factory=dict)  # réglages non secrets (ex. api-version)
    key_unreadable: bool = False  # clé stockée mais indéchiffrable (clé maître changée)

    @field_validator("id")
    @classmethod
    def _id_ok(cls, v: str) -> str:
        if not _ID.match(v):
            raise ValueError("identifiant invalide (minuscules, chiffres, - et _, 48 caractères maximum)")
        return v

    @field_validator("name")
    @classmethod
    def _name_ok(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("le nom est obligatoire")
        return v

    @model_validator(mode="after")
    def _bind_key_to_origin(self) -> "ProviderConfig":
        if self.api_key and not LOADING.get():
            cur = (_registered() or Settings()).provider(self.id)
            if cur is not None and cur.api_key == self.api_key and origin(cur.base_url) != origin(self.base_url):
                log.warning("Fournisseur « %s » : l'adresse a changé, la clé d'API enregistrée est effacée (à ressaisir).", self.id)
                self.api_key = None
        return self

    @property
    def configured(self) -> bool:
        if self.kind == "mock":
            return True
        if self.kind == "anthropic":
            return bool(self.api_key)
        return bool(self.base_url)

    def public(self) -> dict[str, Any]:
        k = self.api_key or ""
        return {"id": self.id, "name": self.name, "kind": self.kind, "base_url": self.base_url, "model": self.model,
                "extra": self.extra, "has_key": bool(k), "key_last4": k[-4:] if len(k) >= 12 else "",
                "key_unreadable": self.key_unreadable, "configured": self.configured}


class Language(BaseModel):
    ui: Literal["fr", "en"] = "fr"
    labels: Literal["fr", "en"] = "fr"
    assistant: Literal["fr", "en"] = "fr"


class Defaults(BaseModel):
    base_iri: str = "https://example.org/onto#"
    prefixes: dict[str, str] = Field(default_factory=dict)
    target: Literal["curiosity", "neo4j"] = "curiosity"
    naming: dict[str, str] = Field(default_factory=lambda: {"class": "PascalCase", "property": "camelCase"})


class SparqlAuth(BaseModel):
    type: Literal["none", "basic", "bearer"] = "none"
    username: Optional[str] = None
    secret: Optional[str] = Field(default=None, repr=False)  # mot de passe (basic) ou jeton (bearer)


class SparqlEndpoint(BaseModel):
    url: str = ""
    auth: Optional[SparqlAuth] = None

    @model_validator(mode="after")
    def _bind_secret_to_origin(self) -> "SparqlEndpoint":
        if self.auth is not None and self.auth.secret and not LOADING.get():
            cur = (_registered() or Settings()).sparql_endpoint
            if cur.auth is not None and cur.auth.secret == self.auth.secret and origin(cur.url) != origin(self.url):
                log.warning("Endpoint SPARQL : l'adresse a changé, le secret enregistré est effacé (à ressaisir).")
                self.auth = self.auth.model_copy(update={"secret": None})
        return self

    def public(self) -> dict[str, Any]:
        a = self.auth
        return {"url": self.url, "auth": None if a is None else
                {"type": a.type, "username": a.username, "has_secret": bool(a.secret)}}


class EndpointConfig(BaseModel):
    """Endpoint SPARQL nommé (L15). Le secret n'existe qu'en mémoire serveur (chiffré sur disque)."""
    id: str
    name: str
    url: str
    auth: Literal["none", "basic", "bearer"] = "none"
    username: Optional[str] = None
    secret: Optional[str] = Field(default=None, repr=False)
    default_graph: Optional[str] = None
    timeout_s: float = 30.0
    secret_unreadable: bool = False

    @field_validator("id")
    @classmethod
    def _id_ok(cls, v: str) -> str:
        if not _ID.match(v):
            raise ValueError("identifiant invalide (minuscules, chiffres, - et _, 48 caractères maximum)")
        return v

    @field_validator("name")
    @classmethod
    def _name_ok(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("le nom est obligatoire")
        return v

    @field_validator("url")
    @classmethod
    def _url_ok(cls, v: str) -> str:
        v = v.strip()
        if not v.startswith(("http://", "https://")):
            raise ValueError("l'URL de l'endpoint SPARQL doit commencer par http:// ou https://")
        return v

    @field_validator("timeout_s")
    @classmethod
    def _to_ok(cls, v: float) -> float:
        if not 1 <= v <= 300:
            raise ValueError("le délai doit être compris entre 1 et 300 secondes")
        return v

    @model_validator(mode="after")
    def _bind_secret_to_origin(self) -> "EndpointConfig":
        if self.secret and not LOADING.get():
            cur = (_registered() or Settings()).endpoint(self.id)
            if cur is not None and cur.secret == self.secret and origin(cur.url) != origin(self.url):
                log.warning("Endpoint « %s » : l'adresse a changé, le secret enregistré est effacé (à ressaisir).", self.id)
                self.secret = None
        return self

    def public(self) -> dict[str, Any]:
        return {"id": self.id, "name": self.name, "url": self.url, "auth": self.auth, "username": self.username,
                "has_secret": bool(self.secret), "secret_unreadable": self.secret_unreadable,
                "default_graph": self.default_graph, "timeout_s": self.timeout_s}


class Settings(BaseModel):
    llm_providers: list[ProviderConfig] = Field(default_factory=list)
    default_provider_id: str = "mock"
    language: Language = Field(default_factory=Language)
    defaults: Defaults = Field(default_factory=Defaults)
    sparql_endpoint: SparqlEndpoint = Field(default_factory=SparqlEndpoint)  # historique (L8), migré vers sparql_endpoints
    sparql_endpoints: list[EndpointConfig] = Field(default_factory=list)  # L15
    active_endpoint_id: Optional[str] = None
    versions: TargetVersions = Field(default_factory=TargetVersions)  # L31 : défaut global des versions de normes et de cibles

    def endpoint(self, eid: Optional[str]) -> Optional[EndpointConfig]:
        return next((e for e in self.sparql_endpoints if e.id == eid), None)

    def active_endpoint(self) -> Optional[EndpointConfig]:
        return self.endpoint(self.active_endpoint_id)

    def provider(self, pid: str) -> Optional[ProviderConfig]:
        return next((p for p in self.llm_providers if p.id == pid), None)

    def public(self) -> dict[str, Any]:
        return {"llm_providers": [p.public() for p in self.llm_providers], "default_provider_id": self.default_provider_id,
                "language": self.language.model_dump(), "defaults": self.defaults.model_dump(),
                "sparql_endpoint": self.sparql_endpoint.public(),
                "sparql_endpoints": [e.public() for e in self.sparql_endpoints], "active_endpoint_id": self.active_endpoint_id,
                "versions": self.versions.model_dump()}
