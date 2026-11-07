"""Modèles pydantic des paramètres. Les secrets (``api_key``, ``auth.secret``) n'existent qu'en mémoire serveur :
les vues publiques (``public_view``) n'exposent que ``has_key`` / ``key_last4``."""
from __future__ import annotations

import re
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, field_validator

Kind = Literal["anthropic", "openai_compat", "ollama", "mock"]
DEFAULT_MODELS = {"anthropic": "claude-sonnet-5-5", "openai_compat": "gpt-4o", "ollama": "llama3.1", "mock": "mock"}
_ID = re.compile(r"^[a-z0-9][a-z0-9_-]{0,47}$")


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
                "sparql_endpoints": [e.public() for e in self.sparql_endpoints], "active_endpoint_id": self.active_endpoint_id}
