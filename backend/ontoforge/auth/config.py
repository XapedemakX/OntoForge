"""Configuration de l'authentification, lue dans l'environnement.

ONTOFORGE_AUTH            ``password`` pour activer (toute autre valeur : désactivée)
ONTOFORGE_AUTH_USERS      comptes ``utilisateur:hachage`` séparés par ``;`` ou par des retours à la ligne
ONTOFORGE_AUTH_USERS_FILE même format dans un fichier (secret monté par Cloud Run) ; les deux sources sont fusionnées
ONTOFORGE_SECRET_KEY      clé maître (32 caractères au moins) dont la clé de session est dérivée
ONTOFORGE_SESSION_HOURS   durée d'une session (8 par défaut, 0,25 à 720)
ONTOFORGE_COOKIE_SECURE   ``0`` pour tester en http sans TLS (défaut : cookie Secure)
ONTOFORGE_PROXY_HOPS      nombre de proxys de confiance devant l'application pour lire X-Forwarded-For
                          (1 par défaut avec ONTOFORGE_PUBLIC=1 : Cloud Run ajoute l'IP du client ; 0 sinon)
"""
from __future__ import annotations

import hashlib
import hmac
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping, Optional

_TRUE = ("1", "true", "yes", "on")


class AuthConfigError(RuntimeError):
    """Configuration d'authentification invalide : le serveur refuse de démarrer plutôt que de s'ouvrir par erreur."""


@dataclass(frozen=True)
class AuthConfig:
    enabled: bool = False
    users: dict[str, str] = field(default_factory=dict)   # nom (minuscules) -> hachage
    session_hours: float = 8.0
    cookie_secure: bool = True
    proxy_hops: int = 0
    key: bytes = b""

    @property
    def cookie_name(self) -> str:
        return "__Host-ontoforge_session" if self.cookie_secure else "ontoforge_session"

    @property
    def max_age(self) -> int:
        return int(self.session_hours * 3600)


def derive_key(secret: str) -> bytes:
    """Clé de signature des sessions, distincte de la clé de chiffrement des réglages (même secret, contexte différent)."""
    return hmac.new(secret.encode("utf-8"), b"ontoforge/session-cookie/v1", hashlib.sha256).digest()


def parse_users(raw: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for item in re.split(r"[;\s]+", raw or ""):
        item = item.strip()
        if not item:
            continue
        name, sep, h = item.partition(":")
        name = name.strip().lower()
        if not sep or not name or not (h.startswith("$argon2") or h.startswith("$2")):
            raise AuthConfigError("ONTOFORGE_AUTH_USERS : format attendu « utilisateur:hachage » (hachage argon2 ou bcrypt, "
                                  "voir `python -m ontoforge.auth hash`).")
        out[name] = h
    return out


def _num(e: Mapping[str, str], name: str, default: float, lo: float, hi: float) -> float:
    try:
        return min(hi, max(lo, float(e.get(name, default))))
    except (TypeError, ValueError):
        return default


def public(env: Optional[Mapping[str, str]] = None) -> bool:
    return str((os.environ if env is None else env).get("ONTOFORGE_PUBLIC", "")).strip().lower() in _TRUE


def load_config(env: Optional[Mapping[str, str]] = None) -> AuthConfig:
    e = os.environ if env is None else env
    mode = str(e.get("ONTOFORGE_AUTH", "") or "").strip().lower()
    pub = public(e)
    hops = int(_num(e, "ONTOFORGE_PROXY_HOPS", 1 if pub else 0, 0, 5))
    if mode != "password":
        if pub and str(e.get("ONTOFORGE_ALLOW_PUBLIC_NOAUTH", "")) != "1":
            raise AuthConfigError("ONTOFORGE_PUBLIC=1 sans authentification : définissez ONTOFORGE_AUTH=password "
                                  "(ou ONTOFORGE_ALLOW_PUBLIC_NOAUTH=1 si l'accès est filtré en amont).")
        return AuthConfig(enabled=False, proxy_hops=hops)
    users = parse_users(str(e.get("ONTOFORGE_AUTH_USERS", "")))
    f = str(e.get("ONTOFORGE_AUTH_USERS_FILE", "") or "").strip()
    if f:
        try:
            users.update(parse_users(Path(f).read_text(encoding="utf-8")))
        except OSError as exc:
            raise AuthConfigError(f"ONTOFORGE_AUTH_USERS_FILE illisible : {exc.__class__.__name__}") from None
    if not users:
        raise AuthConfigError("ONTOFORGE_AUTH=password sans compte : renseignez ONTOFORGE_AUTH_USERS (utilisateur:hachage).")
    secret = str(e.get("ONTOFORGE_SECRET_KEY", "") or "").strip()
    if len(secret) < 32:
        raise AuthConfigError("ONTOFORGE_AUTH=password demande ONTOFORGE_SECRET_KEY (32 caractères au moins) pour signer les sessions. "
                              "Générer : python -m ontoforge.auth secret")
    secure = str(e.get("ONTOFORGE_COOKIE_SECURE", "1") or "1").strip().lower() not in ("0", "false", "no", "off")
    return AuthConfig(enabled=True, users=users, session_hours=_num(e, "ONTOFORGE_SESSION_HOURS", 8, 0.25, 720),
                      cookie_secure=secure, proxy_hops=hops, key=derive_key(secret))
