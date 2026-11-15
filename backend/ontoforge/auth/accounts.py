"""Comptes de l'instance (L42, D-L42-01) : magasin persistant fusionné avec les comptes de la configuration.

Deux sources de comptes :
- ``config``    : ``ONTOFORGE_AUTH_USERS`` / ``ONTOFORGE_AUTH_USERS_FILE`` (administrateurs : ``ONTOFORGE_AUTH_ADMINS``). Affichés « gérés par la
  configuration », jamais modifiables depuis l'interface (ni mot de passe, ni activation, ni suppression, ni rôle) ; seules leurs préférences
  (langue) et leur dernière connexion sont tenues dans le magasin ;
- ``interface`` : comptes créés par un administrateur, dans ``$ONTOFORGE_DATA/accounts.json`` (ou ``ONTOFORGE_ACCOUNTS_FILE``), fichier en 600,
  écriture atomique. Un identifiant de la configuration l'emporte sur un compte du magasin de même nom.

Chaque compte du magasin porte ``gen`` : un jeton tiré au hasard à la création, renouvelé à chaque réinitialisation, changement de mot de passe
ou désactivation. Le cookie de session porte le ``gen`` de l'émission ; un ``gen`` différent, un compte absent ou désactivé = session coupée
immédiatement (le garde d'authentification relit le compte à chaque requête).

Le journal d'administration ``admin-audit.jsonl`` (même dossier, 600) garde qui a fait quoi sur quel compte : jamais un mot de passe, un
hachage, un secret ni un jeton (les clés de ce genre sont écartées avant l'écriture).
"""
from __future__ import annotations

import json
import logging
import os
import re
import secrets
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from fastapi import HTTPException

from .. import fsutil
from . import passwords
from .config import AuthConfig

log = logging.getLogger("ontoforge.auth")

MIN_PASSWORD = 10          # règle existante (python -m ontoforge.auth hash)
LOGIN_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{1,63}$")
RESERVED = {"local"}
LANGS = ("fr", "en")
AUDIT_MAX = 1000
_SECRET_KEY = re.compile(r"pass|hash|secret|token|csrf|cookie|key", re.I)
_ALPHABET = "abcdefghjkmnpqrstuvwxyz23456789"   # sans 0/o, 1/l/i : lisible au téléphone


def _iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def msg(fr: str, en: str) -> str:
    try:
        from .. import localize
        return en if localize.ui_lang() == "en" else fr
    except Exception:  # noqa: BLE001
        return fr


class AccountError(HTTPException):
    """Refus d'une opération sur les comptes : code stable pour le front et les tests, message dans la langue du compte connecté."""

    def __init__(self, status: int, code: str, fr: str, en: str, **extra: Any) -> None:
        super().__init__(status_code=status, detail=msg(fr, en))
        self.payload = {"code": code, **extra}


def provisional_password() -> str:
    """Mot de passe provisoire : 16 caractères lisibles en 4 groupes (≈ 79 bits), tirés par ``secrets``."""
    raw = "".join(secrets.choice(_ALPHABET) for _ in range(16))
    return "-".join(raw[i:i + 4] for i in range(0, 16, 4))


def check_password(pw: str) -> None:
    if not isinstance(pw, str) or len(pw) < MIN_PASSWORD:
        raise AccountError(422, "password_too_short", f"Mot de passe trop court : {MIN_PASSWORD} caractères au moins (une phrase de passe est préférable).",
                           f"Password too short: at least {MIN_PASSWORD} characters (a passphrase is better).")
    if len(pw) > passwords.MAX_LEN:
        raise AccountError(422, "password_too_long", f"Mot de passe trop long : {passwords.MAX_LEN} caractères au plus.", f"Password too long: {passwords.MAX_LEN} characters at most.")


@dataclass(frozen=True)
class Account:
    login: str
    source: str            # "config" | "interface"
    admin: bool
    active: bool
    must_change: bool
    gen: str
    created_at: Optional[str]
    last_login: Optional[str]
    lang: Optional[str]
    hash: str = ""

    @property
    def managed(self) -> bool:
        return self.source == "config"

    def public(self) -> dict:
        """Vue pour l'API : jamais le hachage."""
        return {"login": self.login, "source": self.source, "managed": self.managed, "admin": self.admin, "active": self.active,
                "must_change": self.must_change, "created_at": self.created_at, "last_login": self.last_login, "lang": self.lang}


class AccountDirectory:
    def __init__(self, cfg: AuthConfig) -> None:
        self.cfg = cfg
        self.lock = threading.RLock()
        self._cache: Optional[tuple[tuple, dict]] = None

    # ---- fichiers -------------------------------------------------------------------------------------------------------------

    @property
    def path(self) -> Path:
        f = os.environ.get("ONTOFORGE_ACCOUNTS_FILE", "").strip()
        return Path(f) if f else Path(os.environ.get("ONTOFORGE_DATA", "./data")) / "accounts.json"

    @property
    def audit_path(self) -> Path:
        return self.path.with_name("admin-audit.jsonl")

    def _empty(self) -> dict:
        return {"version": 1, "accounts": {}, "config": {}}

    def _state(self) -> dict:
        """État du magasin ; relu quand le fichier change (taille, date). Fichier illisible : magasin vide + erreur au journal (les comptes de la
        configuration restent utilisables, un administrateur n'est jamais enfermé dehors)."""
        p = self.path
        try:
            st = p.stat()
        except OSError:
            self._cache = None
            return self._empty()
        key = (st.st_mtime_ns, st.st_size, str(p))
        if self._cache and self._cache[0] == key:
            return self._cache[1]
        if st.st_mode & 0o077:
            fsutil.try_chmod(p, 0o600)   # fichier de secrets (hachages) : jamais lisible par le groupe ou les autres
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
            if not isinstance(d, dict) or not isinstance(d.get("accounts", {}), dict):
                raise ValueError("objet attendu")
            d.setdefault("accounts", {})
            d.setdefault("config", {})
        except (OSError, ValueError) as exc:
            log.error("accounts.json illisible (%s) : seuls les comptes de la configuration sont utilisables jusqu'à sa restauration.", exc.__class__.__name__)
            return self._empty()
        self._cache = (key, d)
        return d

    def _save(self, d: dict) -> None:
        try:
            fsutil.atomic_write(self.path, json.dumps(d, ensure_ascii=False, indent=2), mode=0o600)
        finally:
            self._cache = None   # L42-02 : écriture échouée ou non, le cache est relu depuis le fichier (jamais d'état en mémoire divergent)

    # ---- lecture --------------------------------------------------------------------------------------------------------------

    def _config_account(self, login: str, d: dict) -> Account:
        meta = d["config"].get(login) or {}
        return Account(login=login, source="config", admin=login in self.cfg.admins, active=True, must_change=False, gen="", created_at=None,
                       last_login=meta.get("last_login"), lang=meta.get("lang") if meta.get("lang") in LANGS else None, hash=self.cfg.users[login])

    def _store_account(self, login: str, a: dict) -> Account:
        return Account(login=login, source="interface", admin=bool(a.get("admin")), active=bool(a.get("active", True)), must_change=bool(a.get("must_change")),
                       gen=str(a.get("gen") or ""), created_at=a.get("created_at"), last_login=a.get("last_login"),
                       lang=a.get("lang") if a.get("lang") in LANGS else None, hash=str(a.get("hash") or ""))

    def get(self, login: Optional[str]) -> Optional[Account]:
        if not login:
            return None
        login = str(login).strip().lower()
        with self.lock:
            d = self._state()
            if login in self.cfg.users:
                return self._config_account(login, d)
            a = d["accounts"].get(login)
            return self._store_account(login, a) if isinstance(a, dict) else None

    def accounts(self) -> list[Account]:
        with self.lock:
            d = self._state()
            out = [self._config_account(u, d) for u in self.cfg.users]
            out += [self._store_account(u, a) for u, a in sorted(d["accounts"].items()) if u not in self.cfg.users and isinstance(a, dict)]
            return out

    def hash_for(self, login: str) -> Optional[str]:
        """Hachage d'un compte actif, ``None`` si le compte n'existe pas ou est désactivé (la connexion échoue alors comme pour un mauvais mot de passe)."""
        a = self.get(login)
        return a.hash if a and a.active and a.hash else None

    def is_admin(self, login: Optional[str]) -> bool:
        a = self.get(login)
        return bool(a and a.active and a.admin)

    def active_logins(self) -> frozenset:
        return frozenset(a.login for a in self.accounts() if a.active)

    def lang_of(self, login: Optional[str]) -> Optional[str]:
        a = self.get(login)
        return a.lang if a else None

    def session_ok(self, login: str, gen: str) -> Optional[Account]:
        """Compte à qui appartient une session valide, ``None`` si la session doit être coupée (compte supprimé, désactivé, mot de passe changé)."""
        a = self.get(login)
        if a is None or not a.active or a.gen != (gen or ""):
            return None
        return a

    # ---- règles ---------------------------------------------------------------------------------------------------------------

    def _active_admins(self, d: dict, minus: Optional[str] = None, plus: Optional[str] = None) -> set:
        out = {u for u in self.cfg.users if u in self.cfg.admins}
        out |= {u for u, a in d["accounts"].items() if u not in self.cfg.users and isinstance(a, dict) and a.get("admin") and a.get("active", True)}
        if minus:
            out.discard(minus)
        if plus:
            out.add(plus)
        return out

    def _must_be_editable(self, login: str, d: dict) -> dict:
        if login in self.cfg.users:
            raise AccountError(409, "managed_by_config", "Ce compte est géré par la configuration (ONTOFORGE_AUTH_USERS) : modifiez-le là.",
                               "This account is managed by the configuration (ONTOFORGE_AUTH_USERS): change it there.")
        a = d["accounts"].get(login)
        if not isinstance(a, dict):
            raise AccountError(404, "no_such_account", "Compte introuvable.", "Account not found.")
        return a

    def _last_admin_guard(self, d: dict, login: str) -> None:
        if login in self._active_admins(d) and not self._active_admins(d, minus=login):
            raise AccountError(409, "last_admin", "Il doit rester au moins un administrateur actif : l'opération est refusée.",
                               "At least one active administrator must remain: the operation is refused.")

    # ---- administration -------------------------------------------------------------------------------------------------------

    def create(self, actor: str, login: str, password: Optional[str] = None, admin: bool = False, lang: str = "fr") -> tuple[Account, Optional[str]]:
        """Crée un compte du magasin. Mot de passe saisi (non renvoyé) ou provisoire généré (renvoyé UNE fois). Dans les deux cas : à changer à la
        première connexion."""
        login = str(login or "").strip().lower()
        if not LOGIN_RE.match(login) or login in RESERVED:
            raise AccountError(422, "bad_login", "Identifiant invalide : 2 à 64 caractères, minuscules, chiffres, point, tiret ou soulignement (sans espace).",
                               "Invalid identifier: 2 to 64 characters, lowercase letters, digits, dot, hyphen or underscore (no spaces).")
        generated = password is None or password == ""
        pw = provisional_password() if generated else password
        if not generated:
            check_password(pw)
        h = passwords.hash_password(pw)
        with self.lock:
            d = self._state()
            if login in self.cfg.users or login in d["accounts"]:
                raise AccountError(409, "login_taken", "Cet identifiant existe déjà.", "That identifier already exists.")
            d["accounts"][login] = {"hash": h, "admin": bool(admin), "active": True, "must_change": True, "gen": secrets.token_hex(6), "created_at": _iso(),
                                    "created_by": actor, "last_login": None, "lang": lang if lang in LANGS else "fr"}
            self._save(d)
            self.audit(actor, "create", login, admin=bool(admin), generated=generated)
            return self._store_account(login, d["accounts"][login]), (pw if generated else None)

    def reset_password(self, actor: str, login: str, password: Optional[str] = None) -> tuple[Account, Optional[str]]:
        generated = password is None or password == ""
        pw = provisional_password() if generated else password
        if not generated:
            check_password(pw)
        h = passwords.hash_password(pw)
        with self.lock:
            d = self._state()
            a = self._must_be_editable(login, d)
            a.update({"hash": h, "must_change": True, "gen": secrets.token_hex(6)})   # nouveau gen : les sessions ouvertes sont coupées
            self._save(d)
            self.audit(actor, "reset_password", login, generated=generated)
            return self._store_account(login, a), (pw if generated else None)

    def set_active(self, actor: str, login: str, active: bool) -> Account:
        with self.lock:
            d = self._state()
            a = self._must_be_editable(login, d)
            if not active:
                self._last_admin_guard(d, login)
                a["gen"] = secrets.token_hex(6)
            a["active"] = bool(active)
            self._save(d)
            self.audit(actor, "enable" if active else "disable", login)
            return self._store_account(login, a)

    def set_admin(self, actor: str, login: str, admin: bool) -> Account:
        with self.lock:
            d = self._state()
            a = self._must_be_editable(login, d)
            if not admin:
                self._last_admin_guard(d, login)
            a["admin"] = bool(admin)
            self._save(d)
            self.audit(actor, "promote" if admin else "demote", login)
            return self._store_account(login, a)

    def check_deletable(self, login: str) -> None:
        with self.lock:
            d = self._state()
            self._must_be_editable(login, d)
            self._last_admin_guard(d, login)

    def delete(self, actor: str, login: str, **detail: Any) -> None:
        with self.lock:
            d = self._state()
            self._must_be_editable(login, d)
            self._last_admin_guard(d, login)
            del d["accounts"][login]
            self._save(d)
            self.audit(actor, "delete", login, **detail)

    # ---- compte courant -------------------------------------------------------------------------------------------------------

    def change_password(self, login: str, current: str, new: str) -> Account:
        """Changement de son propre mot de passe (ancien requis). Compte de la configuration : refusé (son mot de passe vit dans la configuration)."""
        with self.lock:
            d = self._state()
            if login in self.cfg.users:
                raise AccountError(409, "managed_by_config", "Ce compte est géré par la configuration : son mot de passe se change là (python -m ontoforge.auth hash).",
                                   "This account is managed by the configuration: change its password there (python -m ontoforge.auth hash).")
            a = d["accounts"].get(login)
            if not isinstance(a, dict) or not a.get("active", True):
                raise AccountError(404, "no_such_account", "Compte introuvable.", "Account not found.")
            if not passwords.verify_password(str(a.get("hash") or ""), current):
                raise AccountError(403, "bad_current_password", "Mot de passe actuel incorrect.", "Current password is incorrect.")
            check_password(new)
            if new == current:
                raise AccountError(422, "password_unchanged", "Le nouveau mot de passe doit différer de l'ancien.", "The new password must differ from the current one.")
            a.update({"hash": passwords.hash_password(new), "must_change": False, "gen": secrets.token_hex(6)})
            self._save(d)
            self.audit(login, "change_password", login)
            return self._store_account(login, a)

    def set_lang(self, login: str, lang: str) -> None:
        if lang not in LANGS:
            raise AccountError(422, "bad_lang", "Langue inconnue : « fr » ou « en ».", "Unknown language: \"fr\" or \"en\".")
        with self.lock:
            d = self._state()
            if login in self.cfg.users:
                d["config"].setdefault(login, {})["lang"] = lang
            else:
                a = d["accounts"].get(login)
                if not isinstance(a, dict):
                    raise AccountError(404, "no_such_account", "Compte introuvable.", "Account not found.")
                a["lang"] = lang
            self._save(d)

    def record_login(self, login: str) -> None:
        with self.lock:
            d = self._state()
            if login in self.cfg.users:
                d["config"].setdefault(login, {})["last_login"] = _iso()
            elif isinstance(d["accounts"].get(login), dict):
                d["accounts"][login]["last_login"] = _iso()
            else:
                return
            try:
                self._save(d)
            except OSError as exc:   # une connexion ne doit jamais échouer parce que la date n'a pu être notée
                log.warning("dernière connexion non enregistrée (%s)", exc.__class__.__name__)

    # ---- journal d'administration ---------------------------------------------------------------------------------------------

    def audit(self, actor: str, action: str, target: str = "", **detail: Any) -> None:
        clean = {k: v for k, v in detail.items() if not _SECRET_KEY.search(k)}
        row = {"at": _iso(), "actor": actor, "action": action, "target": target, **({"detail": clean} if clean else {})}
        with self.lock:
            try:
                f = self.audit_path
                lines = f.read_text(encoding="utf-8").splitlines() if f.is_file() else []
                lines.append(json.dumps(row, ensure_ascii=False))
                fsutil.atomic_write(f, "\n".join(lines[-AUDIT_MAX:]) + "\n", mode=0o600)
            except OSError as exc:
                log.error("journal d'administration non écrit (%s)", exc.__class__.__name__)

    def audit_rows(self, limit: int = 200) -> list[dict]:
        try:
            lines = self.audit_path.read_text(encoding="utf-8").splitlines()
        except OSError:
            return []
        out: list[dict] = []
        for ln in reversed(lines[-limit:]):
            try:
                out.append(json.loads(ln))
            except ValueError:
                continue
        return out
