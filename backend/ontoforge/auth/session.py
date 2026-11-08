"""Cookie de session signé, sans état serveur : ``v1.<charge utile base64url>.<HMAC-SHA256 base64url>``.

La charge utile (JSON) porte l'utilisateur, l'émission, l'expiration, un identifiant de session et le jeton CSRF. La déconnexion
inscrit l'identifiant dans une liste de révocation EN MÉMOIRE (perdue au redémarrage de l'instance : un cookie volé reste alors
valable jusqu'à son expiration ; la durée courte et la rotation de ONTOFORGE_SECRET_KEY sont les remèdes).
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import threading
import time
from dataclasses import dataclass
from typing import Optional

_REVOKED: dict[str, float] = {}
_LOCK = threading.Lock()


def now() -> float:
    return time.time()


@dataclass(frozen=True)
class Session:
    user: str
    sid: str
    csrf: str
    iat: float
    exp: float


def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode("ascii")


def _unb64(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def _sign(key: bytes, body: str) -> str:
    return _b64(hmac.new(key, ("v1." + body).encode("ascii"), hashlib.sha256).digest())


def issue(key: bytes, user: str, hours: float) -> tuple[str, Session]:
    t = now()
    s = Session(user=user, sid=secrets.token_urlsafe(12), csrf=secrets.token_urlsafe(24), iat=t, exp=t + hours * 3600)
    body = _b64(json.dumps({"u": s.user, "s": s.sid, "c": s.csrf, "i": int(s.iat), "e": int(s.exp)}, separators=(",", ":")).encode("utf-8"))
    return f"v1.{body}.{_sign(key, body)}", s


def verify(key: bytes, token: Optional[str]) -> Optional[Session]:
    if not token or len(token) > 1024:
        return None
    try:
        ver, body, sig = token.split(".")
        if ver != "v1" or not hmac.compare_digest(sig, _sign(key, body)):
            return None
        d = json.loads(_unb64(body))
        s = Session(user=str(d["u"]), sid=str(d["s"]), csrf=str(d["c"]), iat=float(d["i"]), exp=float(d["e"]))
    except Exception:  # noqa: BLE001 — jeton mal formé
        return None
    if s.exp <= now() or s.iat > now() + 60:
        return None
    with _LOCK:
        if s.sid in _REVOKED:
            return None
    return s


def revoke(s: Session) -> None:
    with _LOCK:
        t = now()
        for k in [k for k, e in _REVOKED.items() if e <= t]:
            del _REVOKED[k]
        _REVOKED[s.sid] = s.exp


def csrf_ok(s: Session, header: Optional[str]) -> bool:
    return bool(header) and hmac.compare_digest(header.encode("utf-8"), s.csrf.encode("utf-8"))
