"""Hachage et vérification des mots de passe : argon2id (argon2-cffi) de préférence, bcrypt (bcrypt) accepté."""
from __future__ import annotations

import secrets

MAX_LEN = 256


def hash_password(password: str, scheme: str = "argon2") -> str:
    if not password:
        raise ValueError("mot de passe vide")
    if scheme == "bcrypt":
        import bcrypt
        raw = password.encode("utf-8")
        if len(raw) > 72:
            raise ValueError("bcrypt est limité à 72 octets : choisissez argon2 ou un mot de passe plus court")
        return bcrypt.hashpw(raw, bcrypt.gensalt(rounds=12)).decode("ascii")
    from argon2 import PasswordHasher
    return PasswordHasher().hash(password)


def verify_password(stored: str, password: str) -> bool:
    """Vrai si ``password`` correspond au hachage. Jamais d'exception : tout échec est « faux »."""
    if not password or len(password) > MAX_LEN:
        return False
    try:
        if stored.startswith("$argon2"):
            from argon2 import PasswordHasher
            return bool(PasswordHasher().verify(stored, password))
        if stored.startswith("$2"):
            import bcrypt
            raw = password.encode("utf-8")
            return len(raw) <= 72 and bcrypt.checkpw(raw, stored.encode("ascii"))
    except Exception:  # noqa: BLE001 — mauvais mot de passe, hachage corrompu, bibliothèque absente
        return False
    return False


_DUMMY: str | None = None


def dummy_hash() -> str:
    """Hachage jetable pour vérifier quelque chose quand l'identifiant est inconnu (même durée que pour un vrai compte)."""
    global _DUMMY
    if _DUMMY is None:
        _DUMMY = hash_password(secrets.token_urlsafe(16))
    return _DUMMY
