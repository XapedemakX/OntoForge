"""En-têtes de sécurité, limite de taille des requêtes et service du front compilé (L27)."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Optional

# Le front est une SPA Vite : scripts et styles du même domaine ; styles en ligne (attributs style de React, CodeMirror) ;
# images data: / blob: (Krakie, export) ; aucune ressource externe.
CSP = ("default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; font-src 'self' data:; "
       "connect-src 'self'; worker-src 'self' blob:; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'")


def _truthy(v: str) -> bool:
    return v.strip().lower() in ("1", "true", "yes", "on")


class SecurityHeaders:
    """Ajoute CSP, HSTS (derrière HTTPS), nosniff, frame-ancestors/X-Frame-Options, Referrer-Policy, Permissions-Policy.
    Les réponses /api/* ne sont jamais mises en cache."""

    def __init__(self, app: Any, hsts: bool = True) -> None:
        self.app, self.hsts = app, hsts

    async def __call__(self, scope: dict, receive: Any, send: Any) -> None:
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        path = scope.get("path", "")
        proto = dict(scope.get("headers", [])).get(b"x-forwarded-proto", b"").decode().split(",")[0].strip() or scope.get("scheme", "http")

        async def wrapped(msg: dict) -> None:
            if msg["type"] == "http.response.start":
                h = [(k, v) for k, v in msg.get("headers", []) if k.lower() not in
                     (b"content-security-policy", b"x-content-type-options", b"x-frame-options", b"referrer-policy", b"permissions-policy")]
                h += [(b"content-security-policy", CSP.encode()), (b"x-content-type-options", b"nosniff"), (b"x-frame-options", b"DENY"),
                      (b"referrer-policy", b"same-origin"), (b"permissions-policy", b"camera=(), microphone=(), geolocation=()")]
                if self.hsts and proto == "https":
                    h.append((b"strict-transport-security", b"max-age=31536000; includeSubDomains"))
                if path.startswith("/api/") and not any(k.lower() == b"cache-control" for k, _ in h):
                    h.append((b"cache-control", b"no-store"))
                msg = {**msg, "headers": h}
            await send(msg)

        await self.app(scope, receive, wrapped)


class BodyLimit:
    """Refuse (413) toute requête dont le corps dépasse ``max_bytes`` : Content-Length d'abord, puis comptage des octets reçus
    (corps en morceaux sans Content-Length)."""

    def __init__(self, app: Any, max_bytes: int) -> None:
        self.app, self.max = app, max_bytes

    async def __call__(self, scope: dict, receive: Any, send: Any) -> None:
        if scope["type"] != "http" or scope["method"] in ("GET", "HEAD", "OPTIONS"):
            return await self.app(scope, receive, send)
        from .auth.middleware import header, send_json
        cl = header(scope, "content-length")
        if cl.isdigit() and int(cl) > self.max:
            return await send_json(send, 413, {"detail": f"Requête trop volumineuse (plafond {self.max // (1024 * 1024)} Mo)."})
        seen = 0
        state = {"started": False, "refused": False}
        text = f"Requête trop volumineuse (plafond {self.max // (1024 * 1024)} Mo)."

        async def counting() -> dict:
            nonlocal seen
            if state["refused"]:
                return {"type": "http.disconnect"}
            msg = await receive()
            if msg["type"] == "http.request":
                seen += len(msg.get("body", b""))
                if seen > self.max:
                    state["refused"] = True
                    if not state["started"]:
                        state["started"] = True
                        await send_json(send, 413, {"detail": text})
                    return {"type": "http.disconnect"}
            return msg

        async def tracked(msg: dict) -> None:
            if state["refused"]:
                return  # la réponse 413 est déjà partie : on ignore ce que l'application tente d'envoyer
            state["started"] = True
            await send(msg)

        try:
            await self.app(scope, counting, tracked)
        except Exception:
            if not state["refused"]:
                raise


def max_body_bytes() -> int:
    try:
        mb = float(os.environ.get("ONTOFORGE_MAX_BODY_MB", "32"))
    except ValueError:
        mb = 32
    return int(max(1, mb) * 1024 * 1024)


class SpaStatic:
    """Sert le front compilé : fichier s'il existe, sinon index.html (routes du front). ``/api/*`` inconnu : 404 JSON."""

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.index = self.root / "index.html"

    async def __call__(self, scope: dict, receive: Any, send: Any) -> None:
        from starlette.responses import FileResponse, JSONResponse, Response
        if scope["type"] != "http":
            return
        path = scope["path"]
        if path.startswith("/api/") or path == "/api":
            return await JSONResponse({"detail": "Not Found"}, status_code=404)(scope, receive, send)
        if scope["method"] not in ("GET", "HEAD"):
            return await Response(status_code=405)(scope, receive, send)
        rel = path.lstrip("/")
        target: Optional[Path] = None
        if rel:
            cand = (self.root / rel).resolve()
            if cand.is_file() and (cand == self.root or self.root in cand.parents):
                target = cand
        if target is None:
            if "." in Path(rel).name and rel:  # fichier statique absent : vrai 404, pas de repli SPA
                return await Response(status_code=404)(scope, receive, send)
            target = self.index
        headers = {"Cache-Control": "public, max-age=31536000, immutable"} if rel.startswith("assets/") else {"Cache-Control": "no-cache"}
        await FileResponse(target, headers=headers)(scope, receive, send)


def static_dir() -> Optional[Path]:
    v = os.environ.get("ONTOFORGE_STATIC_DIR", "").strip()
    if v and (Path(v) / "index.html").is_file():
        return Path(v)
    return None
