"""Limitation de débit de l'API (L39-secu, SEC-10) : fenêtre glissante de 60 s, par adresse IP et par session.

Trois familles de plafonds (requêtes par minute, réglables par variable d'environnement) :
- ``ONTOFORGE_RATE_GLOBAL_PER_MIN``    (900)  toute l'API, hors /api/health ;
- ``ONTOFORGE_RATE_ASSISTANT_PER_MIN`` (20)   assistant et routes qui appellent un LLM facturé ;
- ``ONTOFORGE_RATE_HEAVY_PER_MIN``     (120)  import, analyse, génération, validation, triplestore, conformité, graphe, opérations d'édition,
                                      exports, éditeur de fichiers, valeurs et options de requête (L41, L39-04) ; le raisonneur est plafonné à 10.
``ONTOFORGE_RATE_LIMIT=0`` désactive le limiteur (essais de charge).

Au-delà : réponse 429 avec ``Retry-After``. La clé « session » est l'empreinte du cookie de session reçu (non vérifiée ici : un cookie
inventé ne contourne rien, puisque le plafond par IP s'applique toujours). L'état est en mémoire (une instance, comme le limiteur de connexion).
Ce module ne modifie pas ``auth/limiter.py``.
"""
from __future__ import annotations

import hashlib
import math
import os
import re
import threading
import time
from collections import deque
from typing import Any, Optional

from .auth import limiter as _login_limiter
from .auth.middleware import cookie_value, header, send_json

WINDOW = 60.0
MAX_KEYS = 20000


def _num(name: str, default: int) -> int:
    try:
        return max(1, int(os.environ.get(name, default)))
    except ValueError:
        return default


def enabled() -> bool:
    return os.environ.get("ONTOFORGE_RATE_LIMIT", "1").strip().lower() not in ("0", "false", "no", "off")


_P = r"^/api/projects/[^/]+"
RULES: list[tuple[re.Pattern, str]] = [
    (re.compile(r"^/api/assistant/(chat|draft|shapes|explain|upload|shapes/apply|document/(upload|estimate|draft))$"), "assistant"),
    (re.compile(_P + r"/query/nl$"), "assistant"),
    (re.compile(_P + r"/reason$"), "reason"),
    (re.compile(_P + r"/(import|dsl|analyze|shacl/generate|shacl/validate|store/load|store/validate|files/validate|files/diff|business-map/(suggest-zones|suggest-frames|layout))$"), "heavy"),
    (re.compile(_P + r"/import/schema/(preview|apply)$"), "heavy"),   # L48
    (re.compile(r"^/api/import/schema/preview$"), "heavy"),
    (re.compile(_P + r"/generate/[^/]+(/zip)?$"), "heavy"),
    (re.compile(_P + r"/(query/run|queries/translate)$"), "heavy"),
    # L41 (L39-04) : lectures et écritures coûteuses qui n'étaient limitées que par le plafond global
    (re.compile(_P + r"/(conformance|graph|ops|ops/(undo|redo|history)|export/[^/]+|files|files/.+|query/(values|options))$"), "heavy"),
]


def category(path: str) -> Optional[str]:
    for rx, cat in RULES:
        if rx.match(path):
            return cat
    return None


def limits() -> dict[str, int]:
    heavy = _num("ONTOFORGE_RATE_HEAVY_PER_MIN", 120)
    return {"global": _num("ONTOFORGE_RATE_GLOBAL_PER_MIN", 900), "assistant": _num("ONTOFORGE_RATE_ASSISTANT_PER_MIN", 20),
            "heavy": heavy, "reason": min(10, heavy)}


class Windows:
    """Fenêtres glissantes par clé ; ``hit`` renvoie 0 (accepté) ou le nombre de secondes avant la prochaine place libre."""

    def __init__(self) -> None:
        self._d: dict[str, deque] = {}
        self._lock = threading.Lock()

    def reset(self) -> None:
        with self._lock:
            self._d.clear()

    def hit(self, key: str, limit: int, now: Optional[float] = None) -> float:
        t = time.monotonic() if now is None else now
        with self._lock:
            if len(self._d) >= MAX_KEYS:
                for k in [k for k, v in self._d.items() if not v or t - v[-1] > WINDOW]:
                    del self._d[k]
                if len(self._d) >= MAX_KEYS:
                    self._d.pop(next(iter(self._d)))
            q = self._d.setdefault(key, deque())
            while q and t - q[0] >= WINDOW:
                q.popleft()
            if len(q) >= limit:
                return max(0.1, WINDOW - (t - q[0]))
            q.append(t)
            return 0.0


WINDOWS = Windows()


def reset() -> None:
    WINDOWS.reset()


class RateLimit:
    def __init__(self, app: Any, hops: int = 0, cookie_name: str = "") -> None:
        self.app, self.hops, self.cookie = app, hops, cookie_name

    async def __call__(self, scope: dict, receive: Any, send: Any) -> None:
        path = scope.get("path", "")
        if scope["type"] != "http" or not path.startswith("/api/") or path == "/api/health" or scope.get("method") == "OPTIONS" or not enabled():
            return await self.app(scope, receive, send)
        headers = {"x-forwarded-for": header(scope, "x-forwarded-for")}
        peer = (scope.get("client") or (None,))[0]
        ip = _login_limiter.client_ip(headers, peer, self.hops)
        raw = cookie_value(scope, self.cookie) if self.cookie else None
        sess = hashlib.sha256(raw.encode("utf-8", "replace")).hexdigest()[:24] if raw else None
        lim = limits()
        checks = [("g:ip:" + ip, lim["global"])] + ([("g:s:" + sess, lim["global"])] if sess else [])
        cat = category(path)
        if cat:
            checks += [(f"{cat}:ip:{ip}", lim[cat])] + ([(f"{cat}:s:{sess}", lim[cat])] if sess else [])
        wait = max((WINDOWS.hit(k, n) for k, n in checks), default=0.0)
        if wait:
            secs = max(1, math.ceil(wait))
            try:
                from . import localize
                en = localize.ui_lang() == "en"
            except Exception:  # noqa: BLE001
                en = False
            msg = (f"Too many requests: please retry in {secs} s." if en else f"Trop de requêtes : réessayez dans {secs} s.")
            return await send_json(send, 429, {"detail": msg, "code": "rate_limited", "retry_after": secs}, [(b"retry-after", str(secs).encode())])
        await self.app(scope, receive, send)
