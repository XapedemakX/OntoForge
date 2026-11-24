"""Garde ASGI : toute route ``/api/*`` exige une session valide, sauf ``/api/health`` et ``/api/auth/*``.

Les méthodes qui modifient (POST, PUT, PATCH, DELETE) exigent en plus l'en-tête ``X-CSRF-Token`` égal au jeton de la session, et
un ``Origin`` (s'il est présent) qui correspond à l'hôte demandé. Les fichiers statiques du front restent publics (page de connexion).
"""
from __future__ import annotations

import json
from http.cookies import SimpleCookie
from typing import Any, Optional
from urllib.parse import urlsplit

from . import session as sess
import re

from .config import AuthConfig

SAFE = {"GET", "HEAD", "OPTIONS"}


# L42 : routes de lecture (GET) qui écrivent (génération : historique) : elles exigent le jeton CSRF comme une écriture
_WRITE_GET = re.compile(r"^/api/projects/[^/]+/generate/[^/]+(/zip)?$")


def csrf_required(method: str, path: str) -> bool:
    return method not in SAFE or bool(_WRITE_GET.match(path))


def is_public_path(path: str) -> bool:
    return path == "/api/health" or path == "/api/auth" or path.startswith("/api/auth/")


def header(scope: dict, name: str) -> str:
    n = name.lower().encode("latin-1")
    for k, v in scope.get("headers", []):
        if k == n:
            return v.decode("latin-1")
    return ""


def cookie_value(scope: dict, name: str) -> Optional[str]:
    raw = header(scope, "cookie")
    if not raw:
        return None
    try:
        c: SimpleCookie = SimpleCookie()
        c.load(raw)
        m = c.get(name)
        return m.value if m else None
    except Exception:  # noqa: BLE001
        return None


def origin_ok(scope: dict, extra: tuple[str, ...] = ()) -> bool:
    """Origin absent (client non navigateur) ou même hôte que la requête."""
    o = header(scope, "origin")
    if not o:
        return True
    if o in extra:
        return True
    host = header(scope, "x-forwarded-host").split(",")[0].strip() or header(scope, "host")
    try:
        return urlsplit(o).netloc.lower() == host.lower()
    except ValueError:
        return False


def current_session(scope: dict, cfg: AuthConfig) -> Optional[sess.Session]:
    return sess.verify(cfg.key, cookie_value(scope, cfg.cookie_name))


async def send_json(send: Any, status: int, body: dict, headers: Optional[list[tuple[bytes, bytes]]] = None) -> None:
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    h = [(b"content-type", b"application/json"), (b"content-length", str(len(data)).encode()), (b"cache-control", b"no-store")]
    await send({"type": "http.response.start", "status": status, "headers": h + (headers or [])})
    await send({"type": "http.response.body", "body": data})


def localized(text: str, lang: Optional[str] = None) -> str:
    """Message d'un refus écrit par une couche ASGI, dans la langue de la requête (L52, DF-F03) : même mécanisme que
    ``main.py::_http_error`` (``localize.tr`` vers l'anglais), car ces réponses ne passent pas par les gestionnaires d'exceptions.
    ``lang`` : langue du compte si elle est déjà connue ; sinon ``localize.ui_lang()`` (compte de la requête, puis réglage global)."""
    try:
        from .. import localize
        lang = lang if lang in ("fr", "en") else localize.ui_lang()
        if lang != "en":
            return text
        return localize.tr(text, "en") or text
    except Exception:  # noqa: BLE001 - une traduction n'échoue jamais
        return text


class AuthMiddleware:
    def __init__(self, app: Any, cfg: AuthConfig, accounts: Any = None) -> None:
        self.app, self.cfg, self.accounts = app, cfg, accounts

    async def __call__(self, scope: dict, receive: Any, send: Any) -> None:
        if scope["type"] not in ("http", "websocket") or not scope.get("path", "").startswith("/api") or is_public_path(scope["path"]):
            return await self.app(scope, receive, send)
        if scope["type"] == "websocket":
            return await send({"type": "websocket.close", "code": 1008})
        if scope["method"] == "OPTIONS":
            return await self.app(scope, receive, send)
        s = current_session(scope, self.cfg)
        if s is None:
            return await send_json(send, 401, {"detail": localized("Connexion requise."), "code": "auth_required"})
        acc = None
        if self.accounts is not None:   # L42 : compte supprimé, désactivé ou mot de passe changé = session coupée sur-le-champ
            acc = self.accounts.session_ok(s.user, s.gen)
            if acc is None:
                return await send_json(send, 401, {"detail": localized("Session terminée : reconnectez-vous."), "code": "auth_required"})
            if acc.must_change:
                return await send_json(send, 403, {"detail": localized("Changez d'abord votre mot de passe provisoire.", acc.lang),
                                                   "code": "password_change_required"})
        if csrf_required(scope["method"], scope["path"]):
            lang = acc.lang if acc is not None else None
            if not origin_ok(scope):
                return await send_json(send, 403, {"detail": localized("Origine refusée.", lang), "code": "bad_origin"})
            if not sess.csrf_ok(s, header(scope, "x-csrf-token")):
                return await send_json(send, 403, {"detail": localized("Jeton CSRF absent ou invalide : rechargez la page.", lang), "code": "csrf"})
        scope.setdefault("state", {})["auth_user"] = s.user
        from .. import localize
        tok = localize.REQUEST_LANG.set(acc.lang if acc is not None else None)   # langue du compte pour toute la requête
        try:
            await self.app(scope, receive, send)
        finally:
            localize.REQUEST_LANG.reset(tok)
