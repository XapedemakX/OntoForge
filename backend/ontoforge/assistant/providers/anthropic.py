"""Fournisseur Anthropic (API Messages)."""
from __future__ import annotations

import os
from typing import Any, Optional

from .base import Configured, LLMError, post_json, schema_hint

URL = "https://api.anthropic.com/v1/messages"


class AnthropicProvider(Configured):
    name = "anthropic"

    @property
    def model(self) -> str:
        return self._get("model", "ONTOFORGE_LLM_MODEL") or "claude-sonnet-5-5"

    @property
    def configured(self) -> bool:
        return bool(self._get("api_key", "ANTHROPIC_API_KEY"))

    def complete(self, system: str, messages: list[dict[str, str]], max_tokens: int = 4096,
                 json_schema: Optional[dict[str, Any]] = None) -> str:
        key = self._get("api_key", "ANTHROPIC_API_KEY")
        if not key:
            raise LLMError("Anthropic : aucune clé d'API configurée.")
        data = post_json("Anthropic", self._get("base_url", "ANTHROPIC_BASE_URL").rstrip("/") + "/v1/messages" if self._get("base_url", "ANTHROPIC_BASE_URL") else URL, {"x-api-key": key, "anthropic-version": "2023-06-01",
                                            "content-type": "application/json"},
                         {"model": self.model, "max_tokens": max_tokens,
                          "system": schema_hint(system, json_schema), "messages": messages}, self.timeout_s)
        parts = [b.get("text", "") for b in data.get("content", []) if isinstance(b, dict) and b.get("type") == "text"]
        if not parts:
            raise LLMError("Anthropic : réponse vide.")
        return "".join(parts)
