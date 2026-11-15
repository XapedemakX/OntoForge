"""Comptes de l'instance (L42, D-L42-01) : magasin persistant fusionné avec les comptes de la configuration.

Deux sources de comptes :
- ``config``    : ``ONTOFORGE_AUTH_USERS`` / ``ONTOFORGE_AUTH_USERS_FILE`` (administrateurs : ``ONTOFORGE_AUTH_ADMINS``). Affichés « gérés par la
  configuration » : leur existence, leur rôle et leur état restent ceux de la configuration (ni activation, ni suppression, ni rôle depuis
  l'interface). Depuis L43 (D-L43-01) leur MOT DE PASSE peut être changé depuis l'interface : le nouveau hachage est écrit dans le magasin
  (``config.<login>.hash``) et MASQUE celui de la configuration, tant que l'administrateur ne « revient pas au mot de passe de la configuration » ;
  le masque reste prioritaire même si le hachage de la configuration change ensuite (un avertissement le signale). Le magasin tient aussi leur
  langue, leur dernière connexion et leur ``gen`` ;
- ``interface`` : comptes créés par un administrateur, dans ``$ONTOFORGE_DATA/accounts.json`` (ou ``ONTOFORGE_ACCOUNTS_FILE``), fichier en 600,
  écriture atomique. Un identifiant de la configuration l'emporte sur un compte du magasin de même nom.

Chaque compte du magasin porte ``gen`` : un jeton tiré au hasard à la création, renouvelé à chaque réinitialisation, changement de mot de passe
ou désactivation. Le cookie de session porte le ``gen`` de l'émission ; un ``gen`` différent, un compte absent ou désactivé = session coupée
immédiatement (le garde d'authentification relit le compte à chaque requête).

Le journal d'administration ``admin-audit.jsonl`` (même dossier, 600) garde qui a fait quoi sur quel compte : jamais un mot de passe, un
hachage, un secret ni un jeton (les clés de ce genre sont écartées avant l'écriture). Il tourne par archivage (L43, L42-03) : à ``AUDIT_MAX``
lignes, ``admin-audit.jsonl`` devient ``admin-audit.1.jsonl`` (les archives glissent d'un rang, 600, ``ONTOFORGE_AUDIT_ARCHIVES`` archives,
10 par défaut). Une trace qui ne peut pas être écrite fait échouer l'action (500 ``audit_write_failed``, magasin rétabli).
"""
from __future__ import annotations

import hashlib
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
AUDIT_MAX = 1000            # lignes du journal courant avant rotation
AUDIT_ARCHIVES_DEFAULT = 10
PWD_LIMIT = 5                # L42-01 : changements de mot de passe (tentatives) par compte et par minute
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
    pw_override: bool = False   # L43 : compte de la configuration dont le mot de passe est redéfini dans l'interface (masque)
    cfg_changed: bool = False   # L43 : le hachage de la configuration a changé depuis la pose du masque (le masque reste prioritaire)

    @property
    def managed(self) -> bool:
        return self.source == "config"

    def public(self) -> dict:
        """Vue pour l'API : jamais le hachage."""
        return {"login": self.login, "source": self.source, "managed": self.managed, "admin": self.admin, "active": self.active,
                "must_change": self.must_change, "created_at": self.created_at, "last_login": self.last_login, "lang": self.lang,
                "pw_override": self.pw_override, "cfg_changed": self.cfg_changed}


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

    @staticmethod
    def _fp(h: str) -> str:
        """Empreinte (non secrète, le hachage lui-même n'est pas recopié) du hachage de la configuration au moment où un masque est posé."""
        return hashlib.sha256(h.encode("utf-8")).hexdigest()[:16]

    def _config_account(self, login: str, d: dict) -> Account:
        meta = d["config"].get(login)
        meta = meta if isinstance(meta, dict) else {}
        cfg_hash = self.cfg.users[login]
        masked = isinstance(meta.get("hash"), str) and bool(meta.get("hash"))
        return Account(login=login, source="config", admin=login in self.cfg.admins, active=True, must_change=masked and bool(meta.get("must_change")),
                       gen=str(meta.get("gen") or ""), created_at=None, last_login=meta.get("last_login"),
                       lang=meta.get("lang") if meta.get("lang") in LANGS else None, hash=meta["hash"] if masked else cfg_hash,
                       pw_override=masked, cfg_changed=masked and bool(meta.get("cfg_fp")) and meta.get("cfg_fp") != self._fp(cfg_hash))

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

    # ---- écriture + trace --------------------------------------------------------------------------------------------------

    def _commit(self, d: dict, before: str, actor: str, action: str, target: str = "", **detail: Any) -> None:
        """Écrit le magasin puis la trace. Si la trace ne peut pas être écrite (L42-03), le magasin est rétabli et l'action échoue (500) : jamais
        d'action d'administration sans trace. ``before`` est la sérialisation du magasin prise AVANT la modification."""
        self._save(d)
        try:
            self.audit(actor, action, target, **detail)
        except AccountError:
            try:
                fsutil.atomic_write(self.path, before, mode=0o600)
            except OSError as exc:
                log.error("magasin des comptes non rétabli après l'échec du journal (%s)", exc.__class__.__name__)
            finally:
                self._cache = None
            raise

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
            before = json.dumps(d, ensure_ascii=False, indent=2)
            if login in self.cfg.users or login in d["accounts"]:
                raise AccountError(409, "login_taken", "Cet identifiant existe déjà.", "That identifier already exists.")
            d["accounts"][login] = {"hash": h, "admin": bool(admin), "active": True, "must_change": True, "gen": secrets.token_hex(6), "created_at": _iso(),
                                    "created_by": actor, "last_login": None, "lang": lang if lang in LANGS else "fr"}
            self._commit(d, before, actor, "create", login, admin=bool(admin), generated=generated)
            return self._store_account(login, d["accounts"][login]), (pw if generated else None)

    def reset_password(self, actor: str, login: str, password: Optional[str] = None) -> tuple[Account, Optional[str]]:
        """Réinitialise un mot de passe (provisoire, à changer à la connexion). Compte de la configuration (L43) : pose un masque dans le magasin."""
        generated = password is None or password == ""
        pw = provisional_password() if generated else password
        if not generated:
            check_password(pw)
        h = passwords.hash_password(pw)
        with self.lock:
            d = self._state()
            before = json.dumps(d, ensure_ascii=False, indent=2)
            if login in self.cfg.users:
                m = d["config"].get(login)
                m = d["config"][login] = m if isinstance(m, dict) else {}
                m.update({"hash": h, "must_change": True, "gen": secrets.token_hex(6), "cfg_fp": self._fp(self.cfg.users[login]), "pw_at": _iso()})
                self._commit(d, before, actor, "reset_password", login, generated=generated, source="config")
                return self._config_account(login, d), (pw if generated else None)
            a = self._must_be_editable(login, d)
            a.update({"hash": h, "must_change": True, "gen": secrets.token_hex(6)})   # nouveau gen : les sessions ouvertes sont coupées
            self._commit(d, before, actor, "reset_password", login, generated=generated)
            return self._store_account(login, a), (pw if generated else None)

    def revert_password(self, actor: str, login: str) -> Account:
        """Compte de la configuration : retire le masque, le mot de passe de la configuration redevient celui du compte (sessions coupées)."""
        with self.lock:
            d = self._state()
            before = json.dumps(d, ensure_ascii=False, indent=2)
            if login not in self.cfg.users:
                if isinstance(d["accounts"].get(login), dict):
                    raise AccountError(409, "not_config_account", "Ce compte n'est pas déclaré dans la configuration : il n'a pas de mot de passe de configuration.",
                                       "This account is not declared in the configuration: it has no configuration password.")
                raise AccountError(404, "no_such_account", "Compte introuvable.", "Account not found.")
            m = d["config"].get(login)
            if not isinstance(m, dict) or not m.get("hash"):
                raise AccountError(409, "no_override", "Ce compte utilise déjà le mot de passe de la configuration.", "This account already uses the configuration password.")
            for k in ("hash", "must_change", "cfg_fp", "pw_at"):
                m.pop(k, None)
            m["gen"] = secrets.token_hex(6)
            self._commit(d, before, actor, "revert_password", login, source="config")
            return self._config_account(login, d)

    def set_active(self, actor: str, login: str, active: bool) -> Account:
        with self.lock:
            d = self._state()
            before = json.dumps(d, ensure_ascii=False, indent=2)
            a = self._must_be_editable(login, d)
            if not active:
                self._last_admin_guard(d, login)
                a["gen"] = secrets.token_hex(6)
            a["active"] = bool(active)
            self._commit(d, before, actor, "enable" if active else "disable", login)
            return self._store_account(login, a)

    def set_admin(self, actor: str, login: str, admin: bool) -> Account:
        with self.lock:
            d = self._state()
            before = json.dumps(d, ensure_ascii=False, indent=2)
            a = self._must_be_editable(login, d)
            if not admin:
                self._last_admin_guard(d, login)
            a["admin"] = bool(admin)
            self._commit(d, before, actor, "promote" if admin else "demote", login)
            return self._store_account(login, a)

    def check_deletable(self, login: str) -> None:
        with self.lock:
            d = self._state()
            self._must_be_editable(login, d)
            self._last_admin_guard(d, login)

    def delete(self, actor: str, login: str, **detail: Any) -> None:
        with self.lock:
            d = self._state()
            before = json.dumps(d, ensure_ascii=False, indent=2)
            self._must_be_editable(login, d)
            self._last_admin_guard(d, login)
            del d["accounts"][login]
            self._commit(d, before, actor, "delete", login, **detail)

    # ---- compte courant -------------------------------------------------------------------------------------------------------

    def _pw_snapshot(self, login: str) -> tuple[str, str, bool]:
        """(hachage effectif, gen, compte de la configuration) d'un compte actif ; 404 sinon."""
        with self.lock:
            a = self.get(login)
            if a is None or not a.active or not a.hash:
                raise AccountError(404, "no_such_account", "Compte introuvable.", "Account not found.")
            return a.hash, a.gen, a.managed

    def change_password(self, login: str, current: str, new: str) -> Account:
        """Changement de son propre mot de passe (ancien requis), pour tout compte (L43, D-L43-01). Compte de la configuration : le nouveau hachage
        est écrit dans le magasin et masque celui de la configuration.

        L42-01 : la vérification de l'ancien mot de passe et le hachage du nouveau (argon2, ~100 ms) se font HORS du verrou de l'annuaire, que le
        garde d'authentification prend à chaque requête. Sous verrou, on relit hachage et ``gen`` : s'ils ont changé entre-temps (réinitialisation,
        autre changement), le changement est refusé (409 ``password_changed_meanwhile``) plutôt que d'écraser le résultat."""
        login = str(login).strip().lower()
        stored, gen, managed = self._pw_snapshot(login)
        if not passwords.verify_password(stored, current):
            raise AccountError(403, "bad_current_password", "Mot de passe actuel incorrect.", "Current password is incorrect.")
        check_password(new)
        if new == current:
            raise AccountError(422, "password_unchanged", "Le nouveau mot de passe doit différer de l'ancien.", "The new password must differ from the current one.")
        new_hash = passwords.hash_password(new)
        with self.lock:
            d = self._state()
            before = json.dumps(d, ensure_ascii=False, indent=2)
            a = self.get(login)
            if a is None or not a.active or a.hash != stored or a.gen != gen:
                raise AccountError(409, "password_changed_meanwhile", "Le compte a été modifié pendant l'opération (mot de passe réinitialisé ou changé ailleurs) : reconnectez-vous.",
                                   "The account was modified meanwhile (password reset or changed elsewhere): sign in again.")
            ng = secrets.token_hex(6)
            if managed:
                m = d["config"].get(login)
                m = d["config"][login] = m if isinstance(m, dict) else {}
                m.update({"hash": new_hash, "must_change": False, "gen": ng, "cfg_fp": self._fp(self.cfg.users[login]), "pw_at": _iso()})
                self._commit(d, before, login, "change_password", login, source="config")
                return self._config_account(login, d)
            a2 = d["accounts"][login]
            a2.update({"hash": new_hash, "must_change": False, "gen": ng})
            self._commit(d, before, login, "change_password", login)
            return self._store_account(login, a2)

    def set_lang(self, login: str, lang: str) -> None:
        if lang not in LANGS:
            raise AccountError(422, "bad_lang", "Langue inconnue : « fr » ou « en ».", "Unknown language: \"fr\" or \"en\".")
        with self.lock:
            d = self._state()
            if login in self.cfg.users:
                m = d["config"].get(login)
                m = d["config"][login] = m if isinstance(m, dict) else {}
                m["lang"] = lang
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
                m = d["config"].get(login)
                m = d["config"][login] = m if isinstance(m, dict) else {}
                m["last_login"] = _iso()
            elif isinstance(d["accounts"].get(login), dict):
                d["accounts"][login]["last_login"] = _iso()
            else:
                return
            try:
                self._save(d)
            except OSError as exc:   # une connexion ne doit jamais échouer parce que la date n'a pu être notée
                log.warning("dernière connexion non enregistrée (%s)", exc.__class__.__name__)

    # ---- journal d'administration ---------------------------------------------------------------------------------------------

    @staticmethod
    def audit_keep() -> int:
        """Nombre d'archives conservées (``ONTOFORGE_AUDIT_ARCHIVES``, 1 à 100, 10 par défaut)."""
        try:
            return min(100, max(1, int(os.environ.get("ONTOFORGE_AUDIT_ARCHIVES", AUDIT_ARCHIVES_DEFAULT))))
        except ValueError:
            return AUDIT_ARCHIVES_DEFAULT

    def audit_archive(self, n: int) -> Path:
        return self.audit_path.with_name(f"{self.audit_path.stem}.{n}{self.audit_path.suffix}")

    def _rotate_audit(self) -> None:
        """``admin-audit.jsonl`` → ``.1.jsonl`` → ``.2.jsonl`` … ; au-delà de ``audit_keep()`` la plus ancienne est supprimée (seule perte, réglable)."""
        keep = self.audit_keep()
        for n in range(keep + 1, keep + 20):   # archives en trop si le réglage a été réduit
            self.audit_archive(n).unlink(missing_ok=True)
        for n in range(keep, 1, -1):
            src = self.audit_archive(n - 1)
            if src.exists():
                os.replace(src, self.audit_archive(n))
        os.replace(self.audit_path, self.audit_archive(1))
        fsutil.try_chmod(self.audit_archive(1), 0o600)

    def _audit_append(self, line: str) -> None:
        f = self.audit_path
        f.parent.mkdir(parents=True, exist_ok=True)
        try:
            raw = f.read_bytes()
        except FileNotFoundError:
            raw = b""
        if raw.count(b"\n") >= AUDIT_MAX:
            self._rotate_audit()
            raw = b""
        fd = os.open(f, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
        try:
            os.write(fd, (b"\n" if raw and not raw.endswith(b"\n") else b"") + line.encode("utf-8") + b"\n")
            try:
                os.fsync(fd)
            except OSError:
                pass
        finally:
            os.close(fd)
        fsutil.try_chmod(f, 0o600)

    def audit_ready(self) -> None:
        """Vérifie, avant une opération en plusieurs temps, que le journal peut être écrit (500 ``audit_write_failed`` sinon)."""
        with self.lock:
            try:
                self.audit_path.parent.mkdir(parents=True, exist_ok=True)
                os.close(os.open(self.audit_path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600))
            except OSError as exc:
                log.error("journal d'administration non écrivable (%s)", exc.__class__.__name__)
                raise self._audit_error() from None

    @staticmethod
    def _audit_error() -> AccountError:
        return AccountError(500, "audit_write_failed", "Le journal d'administration n'a pas pu être écrit : l'action est annulée.",
                            "The administration journal could not be written: the action was cancelled.")

    def audit(self, actor: str, action: str, target: str = "", **detail: Any) -> None:
        clean = {k: v for k, v in detail.items() if not _SECRET_KEY.search(k)}
        row = {"at": _iso(), "actor": actor, "action": action, "target": target, **({"detail": clean} if clean else {})}
        with self.lock:
            try:
                self._audit_append(json.dumps(row, ensure_ascii=False))
            except OSError as exc:
                log.error("journal d'administration non écrit (%s)", exc.__class__.__name__)
                raise self._audit_error() from None

    def audit_rows(self, limit: int = 200) -> list[dict]:
        """Entrées les plus récentes d'abord ; complète avec les archives si le journal courant ne suffit pas."""
        out: list[dict] = []
        files = [self.audit_path] + [self.audit_archive(n) for n in range(1, self.audit_keep() + 1)]
        for f in files:
            try:
                lines = f.read_text(encoding="utf-8").splitlines()
            except OSError:
                continue
            for ln in reversed(lines):
                try:
                    out.append(json.loads(ln))
                except ValueError:
                    continue
                if len(out) >= limit:
                    return out
        return out
