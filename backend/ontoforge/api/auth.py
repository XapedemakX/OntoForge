"""Routes d'authentification ``/api/auth/*`` (L27, CONTRACTS §10). Toujours montées ; sans authentification activée elles
répondent que l'accès est libre."""
from __future__ import annotations

import time

from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from ..auth import limiter, passwords, session as sess
from ..auth.config import AuthConfig
from ..auth.middleware import current_session, origin_ok

router = APIRouter(prefix="/api/auth", tags=["auth"])
NOSTORE = {"Cache-Control": "no-store"}


def _cfg(request: Request) -> AuthConfig:
    return request.app.state.auth


def _lang() -> str:
    try:
        from .. import localize
        return localize.ui_lang()
    except Exception:  # noqa: BLE001
        return "fr"


class LoginBody(BaseModel):
    username: str = Field(max_length=128)
    password: str = Field(max_length=passwords.MAX_LEN)


def _info(cfg: AuthConfig, s: sess.Session | None) -> dict:
    if not cfg.enabled:
        return {"enabled": False, "authenticated": True, "user": None, "csrf": None, "expires_at": None, "lang": _lang()}
    return {"enabled": True, "authenticated": s is not None, "user": s.user if s else None, "csrf": s.csrf if s else None,
            "expires_at": int(s.exp) if s else None, "lang": _lang(), "session_hours": cfg.session_hours}


@router.get("/session")
def get_session(request: Request) -> JSONResponse:
    cfg = _cfg(request)
    s = current_session(request.scope, cfg) if cfg.enabled else None
    return JSONResponse(_info(cfg, s), headers=NOSTORE)


@router.post("/login")
def login(body: LoginBody, request: Request) -> JSONResponse:
    cfg = _cfg(request)
    if not cfg.enabled:
        return JSONResponse(_info(cfg, None), headers=NOSTORE)
    if not origin_ok(request.scope):
        return JSONResponse({"detail": "Origine refusée.", "code": "bad_origin"}, status_code=403, headers=NOSTORE)
    ip = limiter.client_ip(request.headers, request.client.host if request.client else None, cfg.proxy_hops)
    wait = limiter.retry_after(ip)
    if wait > 0:
        n = int(wait) + 1
        return JSONResponse({"detail": f"Trop de tentatives. Réessayez dans {n} s.", "code": "rate_limited", "retry_after": n},
                            status_code=429, headers={**NOSTORE, "Retry-After": str(n)})
    name = body.username.strip().lower()
    stored = cfg.users.get(name)
    ok = passwords.verify_password(stored or passwords.dummy_hash(), body.password) and stored is not None
    if not ok:
        delay = limiter.failure(ip)
        out: dict = {"detail": "Identifiant ou mot de passe incorrect.", "code": "bad_credentials"}
        headers = dict(NOSTORE)
        if delay > 0:
            out["retry_after"] = int(delay) + 1
            headers["Retry-After"] = str(int(delay) + 1)
        return JSONResponse(out, status_code=401, headers=headers)
    limiter.success(ip)
    token, s = sess.issue(cfg.key, name, cfg.session_hours)
    resp = JSONResponse({**_info(cfg, s), "ok": True}, headers=NOSTORE)
    resp.set_cookie(cfg.cookie_name, token, max_age=cfg.max_age, httponly=True, secure=cfg.cookie_secure, samesite="lax", path="/")
    return resp


@router.post("/logout")
def logout(request: Request) -> JSONResponse:
    cfg = _cfg(request)
    if not cfg.enabled:
        return JSONResponse({"ok": True}, headers=NOSTORE)
    s = current_session(request.scope, cfg)
    if s is not None:
        if not origin_ok(request.scope) or not sess.csrf_ok(s, request.headers.get("x-csrf-token")):
            return JSONResponse({"detail": "Jeton CSRF absent ou invalide.", "code": "csrf"}, status_code=403, headers=NOSTORE)
        sess.revoke(s)
    resp = JSONResponse({"ok": True}, headers=NOSTORE)
    resp.delete_cookie(cfg.cookie_name, path="/", secure=cfg.cookie_secure, httponly=True, samesite="lax")
    return resp
