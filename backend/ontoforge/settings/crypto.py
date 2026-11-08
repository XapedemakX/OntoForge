"""Chiffrement des secrets (Fernet). Clé maître : ``ONTOFORGE_SECRET_KEY`` (toute chaîne ; dérivée par HKDF-SHA256),
sinon clé générée au premier démarrage dans ``$ONTOFORGE_DATA/.secret`` (permissions 600).

Rotation : voir ``rotate()`` / ``python -m ontoforge.settings rotate`` (docs/CONTRACTS.md §4)."""
from __future__ import annotations

import base64
import logging
import os
from pathlib import Path

from .. import fsutil
from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

log = logging.getLogger("ontoforge.settings")
PREFIX = "enc:v1:"
_SALT = b"ontoforge-settings-v1"


class SecretError(Exception):
    """Secret indéchiffrable (clé maître différente de celle qui a chiffré)."""


def data_dir() -> Path:
    return Path(os.environ.get("ONTOFORGE_DATA", "./data"))


def derive(secret: str) -> bytes:
    raw = HKDF(algorithm=hashes.SHA256(), length=32, salt=_SALT, info=b"fernet").derive(secret.encode("utf-8"))
    return base64.urlsafe_b64encode(raw)


def master_secret() -> str:
    env = os.environ.get("ONTOFORGE_SECRET_KEY", "").strip()
    if env:
        return env
    f = data_dir() / ".secret"
    if f.exists():
        return f.read_text(encoding="utf-8").strip()
    f.parent.mkdir(parents=True, exist_ok=True)
    key = Fernet.generate_key().decode()
    fd = os.open(f, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(key)
    fsutil.try_chmod(f, 0o600)  # FUSE (Cloud Storage) : chmod peut être refusé
    log.warning("ONTOFORGE_SECRET_KEY absente : clé maître générée dans %s. Définissez ONTOFORGE_SECRET_KEY dans .env "
                "pour maîtriser la clé (et sauvegardez-la : sans elle les clés d'API enregistrées sont perdues).", f)
    return key


def encrypt(plain: str, secret: str | None = None) -> str:
    return PREFIX + Fernet(derive(secret or master_secret())).encrypt(plain.encode("utf-8")).decode("ascii")


def decrypt(token: str, secret: str | None = None) -> str:
    if not token.startswith(PREFIX):
        raise SecretError("format de secret inconnu")
    try:
        return Fernet(derive(secret or master_secret())).decrypt(token[len(PREFIX):].encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError):
        raise SecretError("secret indéchiffrable avec la clé maître actuelle") from None
