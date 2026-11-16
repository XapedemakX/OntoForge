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
