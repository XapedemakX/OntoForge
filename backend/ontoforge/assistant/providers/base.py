"""Interface commune des fournisseurs LLM de l'assistant."""
from __future__ import annotations

import json
import os
from typing import Any, Optional, Protocol


class LLMError(Exception):
    """Erreur du fournisseur LLM ; le message est en français et ne contient jamais de clé d'API."""


class Provider(Protocol):
    name: str

    @property
    def model(self) -> str: ...

    @property
    def configured(self) -> bool: ...

    def complete(self, system: str, messages: list[dict[str, str]], max_tokens: int = 4096,
                 json_schema: Optional[dict[str, Any]] = None) -> str: ...


class Configured:
    """Base commune : configuration explicite (réglages) ou, à défaut, variables d'environnement historiques."""
    timeout_s: Optional[float] = None

    def __init__(self, cfg: Any = None) -> None:
        self.cfg = cfg

    def _get(self, field: str, env: str, default: str = "") -> str:
        if self.cfg is not None:
            return (getattr(self.cfg, field, None) or "").strip() if field != "model" else (self.cfg.model or default)
        return os.environ.get(env, "") or default


def timeout() -> float:
    try:
        return float(os.environ.get("ONTOFORGE_LLM_TIMEOUT", "120"))
    except ValueError:
        return 120.0


def schema_hint(system: str, json_schema: Optional[dict[str, Any]]) -> str:
    if not json_schema:
        return system
    return (system + "\n\nRéponds UNIQUEMENT par un objet JSON valide (sans texte autour, sans balises) "
            "conforme à ce schéma :\n" + json.dumps(json_schema, ensure_ascii=False))


def _detail(body: str, secrets: tuple[str, ...] = ()) -> str:
    """Message d'erreur renvoyé par le service (champ error.message si JSON), tronqué, sans aucun secret."""
    msg = ""
    try:
        import json as _json
        d = _json.loads(body)
        e = d[0] if isinstance(d, list) and d else d
        e = e.get("error", e) if isinstance(e, dict) else e
        msg = str(e.get("message") or e.get("status") or "") if isinstance(e, dict) else str(e)
    except Exception:  # noqa: BLE001 — corps non JSON
        msg = body or ""
    msg = " ".join(msg.split())
    for sec in secrets:
        if sec and len(sec) >= 6:
            msg = msg.replace(sec, "***")
    return msg[:240]


def http_error(provider: str, status: int, body: str = "", secrets: tuple[str, ...] = ()) -> LLMError:
    d = _detail(body, secrets)
    err = _http_error(provider, status)
    return LLMError(f"{err} Détail du service : {d}") if d else err


def _http_error(provider: str, status: int) -> LLMError:
    if status in (401, 403):
        return LLMError(f"{provider} : authentification refusée (HTTP {status}) ; vérifiez la clé d'API configurée.")
    if status == 404:
        return LLMError(f"{provider} : point d'accès ou modèle introuvable (HTTP 404) ; vérifiez l'URL et le nom du modèle.")
    if status == 429:
        return LLMError(f"{provider} : limite de débit atteinte (HTTP 429) ; réessayez dans un instant.")
    if status >= 500:
        return LLMError(f"{provider} : le service est indisponible (HTTP {status}).")
    return LLMError(f"{provider} : requête refusée (HTTP {status}).")


def post_json(provider: str, url: str, headers: dict[str, str], payload: dict[str, Any], timeout_s: Optional[float] = None) -> dict[str, Any]:
    """POST JSON avec gestion d'erreurs en français (aucun en-tête n'est jamais journalisé ni renvoyé)."""
    import httpx
    from ... import netguard as _ng
    try:
        tmo = timeout_s if timeout_s else timeout()
        r = _ng.post(url, headers=headers, json=payload, timeout=tmo)
    except _ng.NetGuardError as exc:
        raise LLMError(f"{provider} : {exc}") from None
    except httpx.TimeoutException:
        raise LLMError(f"{provider} : délai dépassé ({tmo:.0f} s) en attendant la réponse.") from None
    except httpx.HTTPError as exc:
        raise LLMError(f"{provider} : connexion impossible ({type(exc).__name__}).") from None
    if r.status_code >= 400:
        secrets = tuple(v.split(" ", 1)[-1] for k, v in headers.items() if k.lower() in ("authorization", "x-api-key", "api-key", "x-goog-api-key"))
        raise http_error(provider, r.status_code, r.text, secrets)
    try:
        return r.json()
    except ValueError:
        raise LLMError(f"{provider} : réponse non JSON du service.") from None
