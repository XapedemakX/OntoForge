"""Routes d'authentification ``/api/auth/*`` (L27, CONTRACTS §10). Toujours montées ; sans authentification activée elles
répondent que l'accès est libre."""
from __future__ import annotations

import time

from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from ..auth import accounts as accounts_mod, limiter, passwords, session as sess
from ..auth.accounts import AccountDirectory, AccountError
from ..auth.config import AuthConfig
from ..auth.middleware import current_session, origin_ok

router = APIRouter(prefix="/api/auth", tags=["auth"])
NOSTORE = {"Cache-Control": "no-store"}


def _cfg(request: Request) -> AuthConfig:
    return request.app.state.auth


def _dir(request: Request) -> AccountDirectory:
    return request.app.state.accounts


def _lang() -> str:
    try:
        from .. import localize
        return localize.ui_lang()
    except Exception:  # noqa: BLE001
        return "fr"


class LoginBody(BaseModel):
    username: str = Field(max_length=128)
    password: str = Field(max_length=passwords.MAX_LEN)


def _info(cfg: AuthConfig, s: sess.Session | None, accounts: AccountDirectory | None = None) -> dict:
    if not cfg.enabled:
        return {"enabled": False, "authenticated": True, "user": None, "csrf": None, "expires_at": None, "lang": _lang(), "admin": True}
    acc = accounts.get(s.user) if (accounts is not None and s) else None
    lang = (acc.lang if acc and acc.lang else None) or _lang()   # L42 : langue du compte, sinon langue par défaut de l'instance
    return {"enabled": True, "authenticated": s is not None, "user": s.user if s else None, "csrf": s.csrf if s else None,
            "expires_at": int(s.exp) if s else None, "lang": lang, "session_hours": cfg.session_hours,
            "admin": bool(acc and acc.active and acc.admin), "must_change": bool(acc and acc.must_change),
            "source": acc.source if acc else None}


def _session(request: Request):
    """Session valide + compte, ou une réponse d'erreur (routes publiques pour le garde, qui font donc leur propre contrôle, comme la déconnexion)."""
    cfg = _cfg(request)
    if not cfg.enabled:
        return None, None, JSONResponse({"detail": "Authentification désactivée.", "code": "auth_disabled"}, status_code=409, headers=NOSTORE)
    s = current_session(request.scope, cfg)
    acc = _dir(request).session_ok(s.user, s.gen) if s else None
    if s is None or acc is None:
        return None, None, JSONResponse({"detail": "Connexion requise.", "code": "auth_required"}, status_code=401, headers=NOSTORE)
    if not origin_ok(request.scope) or not sess.csrf_ok(s, request.headers.get("x-csrf-token")):
        return None, None, JSONResponse({"detail": "Jeton CSRF absent ou invalide.", "code": "csrf"}, status_code=403, headers=NOSTORE)
    return s, acc, None


@router.get("/session")
def get_session(request: Request) -> JSONResponse:
    cfg = _cfg(request)
    s = current_session(request.scope, cfg) if cfg.enabled else None
    if s is not None and _dir(request).session_ok(s.user, s.gen) is None:
        s = None   # compte supprimé, désactivé ou mot de passe changé ailleurs
    return JSONResponse(_info(cfg, s, _dir(request)), headers=NOSTORE)


@router.post("/login")
def login(body: LoginBody, request: Request) -> JSONResponse:
    cfg = _cfg(request)
    if not cfg.enabled:
        return JSONResponse(_info(cfg, None), headers=NOSTORE)
    accounts = _dir(request)
    if not origin_ok(request.scope):
        return JSONResponse({"detail": "Origine refusée.", "code": "bad_origin"}, status_code=403, headers=NOSTORE)
    ip = limiter.client_ip(request.headers, request.client.host if request.client else None, cfg.proxy_hops)
    wait = limiter.retry_after(ip)
    if wait > 0:
        n = int(wait) + 1
        return JSONResponse({"detail": f"Trop de tentatives. Réessayez dans {n} s.", "code": "rate_limited", "retry_after": n},
                            status_code=429, headers={**NOSTORE, "Retry-After": str(n)})
    name = body.username.strip().lower()
    stored = accounts.hash_for(name)   # None : inconnu ou désactivé (même réponse qu'un mauvais mot de passe)
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
    acc = accounts.get(name)
    accounts.record_login(name)
    token, s = sess.issue(cfg.key, name, cfg.session_hours, acc.gen if acc else "")
    resp = JSONResponse({**_info(cfg, s, accounts), "ok": True}, headers=NOSTORE)
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


class PasswordBody(BaseModel):
    current: str = Field(max_length=passwords.MAX_LEN)
    new: str = Field(max_length=passwords.MAX_LEN)


class PrefsBody(BaseModel):
    lang: str = Field(max_length=8)


@router.post("/password")
def change_password(body: PasswordBody, request: Request) -> JSONResponse:
    """Changer son propre mot de passe (ancien requis), pour tout compte, y compris ceux de la configuration (D-L43-01) et le mot de passe
    provisoire. Deux limiteurs : celui de la connexion (une erreur sur l'ancien mot de passe compte comme un échec, par adresse) et, depuis L43
    (L42-01), ``pwd:<compte>`` : 5 tentatives par minute et par compte, réussies ou non, vérifiées avant tout calcul de hachage. Les autres
    sessions du compte sont coupées ; celle-ci est renouvelée."""
    cfg = _cfg(request)
    s, acc, err = _session(request)
    if err is not None:
        return err
    ip = limiter.client_ip(request.headers, request.client.host if request.client else None, cfg.proxy_hops)
    wait = limiter.retry_after(ip)
    if wait > 0:
        n = int(wait) + 1
        return JSONResponse({"detail": f"Trop de tentatives. Réessayez dans {n} s.", "code": "rate_limited", "retry_after": n}, status_code=429, headers={**NOSTORE, "Retry-After": str(n)})
    if not limiter.allow("pwd:" + s.user, accounts_mod.PWD_LIMIT):
        return JSONResponse({"detail": "Trop de changements de mot de passe pour ce compte : réessayez dans une minute.", "code": "rate_limited", "retry_after": 60},
                            status_code=429, headers={**NOSTORE, "Retry-After": "60"})
    accounts = _dir(request)
    try:
        new = accounts.change_password(s.user, body.current, body.new)
    except AccountError as exc:
        if exc.payload.get("code") == "bad_current_password":
            limiter.failure(ip)
        return JSONResponse({"detail": exc.detail, **exc.payload}, status_code=exc.status_code, headers=NOSTORE)
    limiter.success(ip)
    token, ns = sess.issue(cfg.key, s.user, cfg.session_hours, new.gen)
    resp = JSONResponse({**_info(cfg, ns, accounts), "ok": True}, headers=NOSTORE)
    resp.set_cookie(cfg.cookie_name, token, max_age=cfg.max_age, httponly=True, secure=cfg.cookie_secure, samesite="lax", path="/")
    return resp


@router.put("/preferences")
def set_preferences(body: PrefsBody, request: Request) -> JSONResponse:
    """Langue d'interface du compte (fr / en), enregistrée côté serveur ; disponible pour tout compte, y compris géré par la configuration."""
    s, acc, err = _session(request)
    if err is not None:
        return err
    try:
        _dir(request).set_lang(s.user, body.lang)
    except AccountError as exc:
        return JSONResponse({"detail": exc.detail, **exc.payload}, status_code=exc.status_code, headers=NOSTORE)
    return JSONResponse(_info(_cfg(request), s, _dir(request)), headers=NOSTORE)
