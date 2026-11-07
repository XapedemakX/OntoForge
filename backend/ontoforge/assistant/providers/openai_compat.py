"""Fournisseur compatible OpenAI (Azure OpenAI, vLLM, LM Studio...)."""
from __future__ import annotations

import os
from typing import Any, Optional

from .base import Configured, LLMError, post_json, schema_hint


class OpenAICompatProvider(Configured):
    name = "openai_compat"

    @property
    def model(self) -> str:
        return self._get("model", "ONTOFORGE_LLM_MODEL") or "gpt-4o"

    @property
    def configured(self) -> bool:
        return bool(self._get("base_url", "OPENAI_BASE_URL"))

    def complete(self, system: str, messages: list[dict[str, str]], max_tokens: int = 4096,
                 json_schema: Optional[dict[str, Any]] = None) -> str:
        base = self._get("base_url", "OPENAI_BASE_URL").rstrip("/")
        if not base:
            raise LLMError("OpenAI-compatible : aucune URL configurée.")
        headers = {"content-type": "application/json"}
        key = self._get("api_key", "OPENAI_API_KEY")
        if key:
            headers["authorization"] = "Bearer " + key
        payload: dict[str, Any] = {"model": self.model, "max_tokens": max_tokens,
                                   "messages": [{"role": "system", "content": schema_hint(system, json_schema)}, *messages]}
        if json_schema:
            payload["response_format"] = {"type": "json_object"}
        data = post_json("OpenAI-compatible", f"{base}/chat/completions", headers, payload, self.timeout_s)
        try:
            return data["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, TypeError):
            raise LLMError("OpenAI-compatible : format de réponse inattendu.") from None
