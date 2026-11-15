"""L41-R1 : l'erreur d'un fournisseur LLM refusé par netguard ne cite ni l'hôte ni l'adresse résolue."""
import pytest

from ontoforge import netguard
from ontoforge.assistant.providers import base


@pytest.mark.parametrize("url", ["http://ollama-interne.corp.example:11434/api/chat", "http://10.12.34.56:8000/v1/chat/completions"])
def test_provider_netguard_refusal_is_generic(monkeypatch, url):
    host = url.split("//", 1)[1].split(":", 1)[0]

    def refuse(u, **kw):
        raise netguard.NetGuardError(f"adresse refusée : {host} (10.12.34.56)")

    monkeypatch.setattr(netguard, "post", refuse)
    with pytest.raises(base.LLMError) as ei:
        base.post_json("Ollama", url, {}, {"x": 1})
    msg = str(ei.value)
    assert host not in msg and "10.12.34.56" not in msg
    assert "protection des adresses" in msg
