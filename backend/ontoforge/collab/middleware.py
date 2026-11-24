"""Garde ASGI du cloisonnement des projets (L40). Placée juste derrière ``AuthMiddleware``.

Pour chaque requête /api :
1. identité : compte de la session, ou « local » sans authentification (propriétaire de tout) ;
2. /api/settings en écriture : administrateurs seulement ;
3. route portant ``{pid}`` : niveau lu dans ``routes.ROUTES`` (inconnue = refusée), 404 si le projet est inaccessible, 403 si le rôle ne
   suffit pas, ``If-Match`` contrôlé pour les écritures (409 si le projet a changé), écritures d'un même projet sérialisées ;
4. après une écriture réussie : version +1 si ``project.json`` a changé, journal d'activité ; en-tête ``ETag`` sur les réponses réussies.
"""
from __future__ import annotations

import asyncio
import json
from typing import Any, Optional

from starlette.routing import Match

from ..auth.config import AuthConfig
from ..auth.middleware import localized
from . import access
from .access import CollabError, Ctx, Identity
from .routes import ADMIN_PREFIX, BODY_PROJECT_ROUTES, SETTINGS_PREFIX, classify

SAFE = ("GET", "HEAD", "OPTIONS")


def _header(scope: dict, name: str) -> str:
    n = name.lower().encode("latin-1")
    for k, v in scope.get("headers", []):
        if k == n:
            return v.decode("latin-1")
    return ""


async def _send_json(send: Any, status: int, body: dict) -> None:
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    await send({"type": "http.response.start", "status": status, "headers": [
        (b"content-type", b"application/json"), (b"content-length", str(len(data)).encode()), (b"cache-control", b"no-store")]})
    await send({"type": "http.response.body", "body": data})


def identity_for(cfg: AuthConfig, scope: dict, accounts: Any = None) -> Optional[Identity]:
    if not cfg.enabled:
        return Identity()
    user = (scope.get("state") or {}).get("auth_user")
    if not user:
        return None
    if accounts is None:
        return Identity(user=user, is_admin=cfg.is_admin(user), auth=True, first_admin=cfg.first_admin, accounts=frozenset(cfg.users))
    return Identity(user=user, is_admin=accounts.is_admin(user), auth=True, first_admin=cfg.first_admin, accounts=accounts.active_logins())


class CollabMiddleware:
    def __init__(self, app: Any, cfg: AuthConfig, router: Any, accounts: Any = None) -> None:
        self.app, self.cfg, self.router, self.accounts = app, cfg, router, accounts
        self._locks: dict[tuple, asyncio.Lock] = {}   # (projet, boucle d'événements) : un verrou asyncio ne se partage pas entre boucles

    def _match(self, scope: dict) -> tuple[Optional[str], dict]:
        for r in self.router.routes:
            m, child = r.matches(scope)
            if m == Match.FULL:
                return getattr(r, "path", None), child.get("path_params", {})
        return None, {}

    async def __call__(self, scope: dict, receive: Any, send: Any) -> None:
        path = scope.get("path", "")
        if scope["type"] != "http" or not path.startswith("/api") or scope["method"] == "OPTIONS":
            return await self.app(scope, receive, send)
        method = scope["method"]
        ident = identity_for(self.cfg, scope, self.accounts)
        if ident is None:
            if path == "/api/health" or path.startswith("/api/auth"):
                return await self.app(scope, receive, send)
            return await _send_json(send, 401, {"detail": localized("Connexion requise."), "code": "auth_required"})
        if (path == SETTINGS_PREFIX or path.startswith(SETTINGS_PREFIX + "/")) and method not in SAFE and not ident.is_admin:
            return await _send_json(send, 403, {"detail": access.msg("Les réglages sont réservés aux administrateurs.", "Settings are reserved for administrators."),
                                                "code": "admin_only"})
        if (path == ADMIN_PREFIX or path.startswith(ADMIN_PREFIX + "/")) and not ident.is_admin:   # L42 : administration des comptes
            return await _send_json(send, 403, {"detail": access.msg("L'administration est réservée aux administrateurs.", "Administration is reserved for administrators."),
                                                "code": "admin_only"})
        template, params = self._match(scope)
        pid = params.get("pid") if template and template.startswith("/api/projects/{pid}") else None   # /api/settings/providers/{pid} est un fournisseur, pas un projet
        ctx = Ctx(identity=ident, if_match=_header(scope, "if-match") or None)
        entry = classify(method, template) if pid is not None else None
        body_level = BODY_PROJECT_ROUTES.get((method, template or ""))
        if pid is None and body_level is None:
            token = access.set_ctx(ctx)
            try:
                return await self.app(scope, receive, send)
            finally:
                access.reset_ctx(token)
        if pid is not None and entry is None:   # route avec projet non classée : refus (échec fermé)
            return await _send_json(send, 403, {"detail": localized("Route non classée."), "code": "unclassified"})
        level, action = entry if entry else (body_level, "")
        ctx.action = action or _body_action(template)
        lock = self._locks.setdefault((pid, id(asyncio.get_running_loop())), asyncio.Lock()) if pid is not None and level in ("write", "owner") else None
        written = level == "write"
        token = access.set_ctx(ctx)

        async def wrapped(msg: dict) -> None:
            if msg["type"] == "http.response.start" and msg["status"] < 400:
                touched = [p2 for p2 in ctx.before if store_exists(p2)]
                if written:
                    for p2 in touched:
                        if access.signature(p2) != ctx.before[p2]:
                            access.bump(p2, ident.user)
                        if ctx.action:
                            access.log(p2, ident.user, ctx.action)
                tag = pid if pid is not None and store_exists(pid) else (touched[0] if touched else None)
                if tag:
                    msg = {**msg, "headers": list(msg.get("headers", [])) + [(b"etag", f'"{access.read(tag)["rev"]}"'.encode())]}
            await send(msg)

        async def run() -> None:
            if pid is not None:
                try:
                    access.require(pid, level, ident, ctx.if_match)
                except CollabError as exc:
                    return await _send_json(send, exc.status_code, {"detail": exc.detail, **exc.payload})
                if level in ("write", "owner"):
                    ctx.before[pid] = access.signature(pid)
            await self.app(scope, receive, wrapped)

        try:
            if lock is not None:
                async with lock:
                    await run()
            else:
                await run()
        finally:
            access.reset_ctx(token)


def store_exists(pid: str) -> bool:
    from ..projects import store
    return store.exists(pid)


def _body_action(template: Optional[str]) -> str:
    return "shapes" if template and template.endswith("shapes/apply") else ""
