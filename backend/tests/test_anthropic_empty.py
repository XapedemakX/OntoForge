"""Réponse Anthropic sans bloc texte (réflexion seule, max_tokens atteint) : message explicite ; le test de connexion demande assez de jetons."""
import pytest

from ontoforge.assistant.providers import anthropic, base


def test_thinking_only_response_gives_explicit_error(monkeypatch):
    monkeypatch.setattr(anthropic, "post_json", lambda *a, **k: {"content": [{"type": "thinking", "thinking": "…"}], "stop_reason": "max_tokens"})
    from types import SimpleNamespace
    p = anthropic.AnthropicProvider(SimpleNamespace(api_key="-".join(["k", "test"]), model="claude-sonnet-5-5", base_url=""))
    with pytest.raises(base.LLMError, match="stop_reason=max_tokens"):
        p.complete("s", [{"role": "user", "content": "ping"}], 16)


def test_connection_test_uses_enough_tokens():
    from ontoforge.api import settings as api_settings
    assert api_settings.TEST_MAX_TOKENS >= 256


def test_pasted_key_with_invisible_chars_is_cleaned_and_bad_chars_refused():
    from fastapi import HTTPException
    from ontoforge.api.settings import clean_secret
    raw = "﻿ sk-" + "abc123" + " ​\n"
    assert clean_secret(raw) == "sk-abc123"
    with pytest.raises(HTTPException) as ei:
        clean_secret("sk-abc•••")
    assert ei.value.status_code == 422 and "U+2022" in ei.value.detail


def test_stored_key_with_invisible_char_does_not_crash_headers():
    from types import SimpleNamespace
    p = anthropic.AnthropicProvider(SimpleNamespace(api_key="sk-abc​", model="m", base_url=""))
    assert p._get("api_key", "X") == "sk-abc"


def test_gemini_openai_compat_defaults_to_low_reasoning(monkeypatch):
    from types import SimpleNamespace
    from ontoforge.assistant.providers import openai_compat
    sent = {}
    def fake(name, url, headers, payload, timeout):
        sent.update(payload); return {"choices": [{"message": {"content": "OK"}}]}
    monkeypatch.setattr(openai_compat, "post_json", fake)
    p = openai_compat.OpenAICompatProvider(SimpleNamespace(api_key="k", model="gemini-3.8-flash", extra={},
                                                           base_url="https://generativelanguage.googleapis.com/v1beta/openai"))
    assert p.complete("s", [{"role": "user", "content": "ping"}], 16) == "OK"
    assert sent["reasoning_effort"] == "low"
    p2 = openai_compat.OpenAICompatProvider(SimpleNamespace(api_key="k", model="m", extra={"reasoning_effort": "high"}, base_url="https://x.example/v1"))
    p2.complete("s", [{"role": "user", "content": "ping"}], 16)
    assert sent["reasoning_effort"] == "high"
