"""Fournisseurs LLM. Sélection : ``provider_id`` explicite, sinon fournisseur par défaut des paramètres
(``$ONTOFORGE_DATA/settings.json``), sinon — tant que ce fichier n'existe pas — variables d'environnement
historiques (``ONTOFORGE_LLM_PROVIDER`` : anthropic | openai_compat | ollama | mock)."""
from __future__ import annotations

import os
from typing import Optional

from .anthropic import AnthropicProvider
from .base import LLMError, Provider
from .mock import MockProvider
from .ollama import OllamaProvider
from .openai_compat import OpenAICompatProvider

PROVIDERS = {"anthropic": AnthropicProvider, "openai_compat": OpenAICompatProvider,
             "ollama": OllamaProvider, "mock": MockProvider}


def from_config(cfg) -> Provider:
    return PROVIDERS[cfg.kind](cfg)


def get_provider(provider_id: Optional[str] = None) -> Provider:
    from ...settings import store
    if provider_id or store.exists():
        s = store.load()
        pid = provider_id or s.default_provider_id
        cfg = s.provider(pid)
        if cfg is None:
            raise LLMError(f"Fournisseur « {pid} » inconnu ; configurez-le dans Paramètres.")
        return from_config(cfg)
    name = (os.environ.get("ONTOFORGE_LLM_PROVIDER") or "anthropic").strip().lower()
    if name not in PROVIDERS:
        raise LLMError(f"Fournisseur LLM inconnu « {name} » ; valeurs possibles : {', '.join(PROVIDERS)}.")
    return PROVIDERS[name]()


__all__ = ["get_provider", "from_config", "LLMError", "Provider", "PROVIDERS"]
