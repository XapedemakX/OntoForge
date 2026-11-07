"""Fournisseur Ollama local."""
from __future__ import annotations

import os
from typing import Any, Optional

from .base import Configured, LLMError, post_json, schema_hint


class OllamaProvider(Configured):
    name = "ollama"

    @property
    def model(self) -> str:
        return self._get("model", "ONTOFORGE_LLM_MODEL") or "llama3.1"

    @property
    def configured(self) -> bool:
        return bool(self._get("base_url", "OLLAMA_BASE_URL"))

    def complete(self, system: str, messages: list[dict[str, str]], max_tokens: int = 4096,
                 json_schema: Optional[dict[str, Any]] = None) -> str:
        base = self._get("base_url", "OLLAMA_BASE_URL").rstrip("/")
        if not base:
            raise LLMError("Ollama : aucune URL configurée.")
        payload: dict[str, Any] = {"model": self.model, "stream": False,
                                   "messages": [{"role": "system", "content": schema_hint(system, json_schema)}, *messages],
                                   "options": {"num_predict": max_tokens}}
        if json_schema:
            payload["format"] = "json"
        data = post_json("Ollama", f"{base}/api/chat", {"content-type": "application/json"}, payload, self.timeout_s)
        try:
            return data["message"]["content"] or ""
        except (KeyError, TypeError):
            raise LLMError("Ollama : format de réponse inattendu.") from None
