"""Chiffrement des secrets (Fernet). Clé maître : ``ONTOFORGE_SECRET_KEY`` (toute chaîne ; dérivée par HKDF-SHA256),
sinon clé générée au premier démarrage dans ``$ONTOFORGE_SECRET_FILE`` ou, à défaut, ``$ONTOFORGE_DATA/.secret`` (permissions 600).

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


def key_file() -> Path:
    """Emplacement du fichier de clé maître : ``ONTOFORGE_SECRET_FILE`` (à placer HORS du dossier des données, par exemple sur un
    volume séparé), sinon ``$ONTOFORGE_DATA/.secret`` (comportement historique)."""
    env = os.environ.get("ONTOFORGE_SECRET_FILE", "").strip()
    return Path(env) if env else data_dir() / ".secret"


def _same_dir(a: Path, b: Path) -> bool:
    try:
        return a.resolve().parent == b.resolve().parent
    except OSError:
        return False


def _write_key(f: Path, key: str) -> None:
    f.parent.mkdir(parents=True, exist_ok=True)
    if not _same_dir(f.parent / "x", data_dir() / "x"):
        fsutil.try_chmod(f.parent, 0o700)  # dossier dédié à la clé : lisible par le seul propriétaire
    fd = os.open(f, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(key)
    fsutil.try_chmod(f, 0o600)  # FUSE (Cloud Storage) : chmod peut être refusé


def _tighten(f: Path) -> None:
    """L41 (L39-05) : un fichier de clé déjà présent avec des droits larges est signalé, puis resserré à 600 (lisible par son seul propriétaire)."""
    try:
        mode = f.stat().st_mode & 0o777
    except OSError:
        return
    if mode & 0o077:
        log.warning("Le fichier de clé maître %s était lisible par d'autres comptes (droits %o) : droits ramenés à 600.", f, mode)
        fsutil.try_chmod(f, 0o600)


def master_secret() -> str:
    """Clé maître : ``ONTOFORGE_SETTINGS_KEY`` (clé dédiée aux secrets enregistrés), sinon ``ONTOFORGE_SECRET_KEY``, sinon le fichier
    de clé (créé en 600 au premier démarrage). Avec ``ONTOFORGE_SECRET_FILE``, un ancien ``$ONTOFORGE_DATA/.secret`` est recopié à
    la nouvelle adresse puis supprimé, de sorte que la clé ne reste pas à côté de ``settings.json``."""
    for var in ("ONTOFORGE_SETTINGS_KEY", "ONTOFORGE_SECRET_KEY"):
        env = os.environ.get(var, "").strip()
        if env:
            return env
    f = key_file()
    if f.exists():
        _tighten(f)
        return f.read_text(encoding="utf-8").strip()
    legacy = data_dir() / ".secret"
    if f != legacy and legacy.exists():
        key = legacy.read_text(encoding="utf-8").strip()
        _write_key(f, key)
        if f.read_text(encoding="utf-8").strip() == key:
            try:
                legacy.unlink()
            except OSError:
                log.warning("Ancienne clé maître %s à supprimer à la main (une copie existe dans %s).", legacy, f)
        log.warning("Clé maître déplacée de %s vers %s.", legacy, f)
        return key
    key = Fernet.generate_key().decode()
    _write_key(f, key)
    log.warning("ONTOFORGE_SECRET_KEY absente : clé maître générée dans %s. Définissez ONTOFORGE_SECRET_KEY dans .env "
                "pour maîtriser la clé (et sauvegardez-la : sans elle les clés d'API enregistrées sont perdues).", f)
    if _same_dir(f, data_dir() / "settings.json"):
        log.warning("La clé maître est dans le même dossier que settings.json : ne sauvegardez pas les deux ensemble. "
                    "ONTOFORGE_SECRET_FILE=<chemin hors du dossier de données> la place ailleurs.")
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
