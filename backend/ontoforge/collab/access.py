"""Droits d'accès, version et activité d'un projet. État dans ``<projet>/collab.json`` et ``<projet>/activity.jsonl``.

Ces fichiers sont à côté de ``project.json`` mais hors du modèle ``Project`` : un client qui renvoie un projet complet (PUT) ne peut
donc ni s'attribuer un projet ni modifier les partages. Sans authentification (mode local) l'identité implicite « local » est
propriétaire de tout et rien n'est cloisonné.
"""
from __future__ import annotations

import json
import logging
import threading
import time
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any, Optional

from fastapi import HTTPException

from .. import fsutil
from ..projects import store

LOCAL_USER = "local"
ROLES = ("reader", "editor")
LEVELS = ("read", "write", "owner")
PRESENCE_TTL = 60.0
ACTIVITY_MAX = 500

log_ = logging.getLogger("ontoforge.collab")
_reported: set[tuple] = set()   # (projet, signature du fichier) déjà signalés au journal du serveur
_lock = threading.RLock()
_presence: dict[str, dict[str, float]] = {}


admin_audit: Any = None   # fonction (acteur, action, cible, **détail) du journal d'administration, posée par main.create_app (L42)


def now() -> float:
    return time.time()


def iso() -> str:
    return store.now_iso()


def msg(fr: str, en: str) -> str:
    try:
        from .. import localize
        return en if localize.ui_lang() == "en" else fr
    except Exception:  # noqa: BLE001
        return fr


# ---- identité et contexte de requête --------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class Identity:
    user: str = LOCAL_USER
    is_admin: bool = True
    auth: bool = False
    first_admin: Optional[str] = None   # propriétaire par défaut des projets sans propriétaire (migration)
    accounts: frozenset = frozenset()


@dataclass
class Ctx:
    identity: Identity
    if_match: Optional[str] = None
    before: dict[str, tuple] = field(default_factory=dict)   # projet écrit pendant la requête -> signature de project.json avant
    action: str = "edit"
    admin_for: set = field(default_factory=set)   # projets d'un autre compte touchés en tant qu'administrateur (L42) : tracés « en tant qu'administrateur »


_CTX: ContextVar[Optional[Ctx]] = ContextVar("ontoforge_collab_ctx", default=None)


def current() -> Optional[Ctx]:
    return _CTX.get()


def set_ctx(c: Optional[Ctx]):
    return _CTX.set(c)


def reset_ctx(token) -> None:
    _CTX.reset(token)


class CollabError(HTTPException):
    """HTTPException qui porte des champs supplémentaires (code, version courante) dans la réponse JSON."""

    def __init__(self, status: int, detail: str, code: str, **extra: Any) -> None:
        super().__init__(status_code=status, detail=detail)
        self.payload = {"code": code, **extra}


def not_found(pid: str) -> CollabError:
    return CollabError(404, msg(f"Projet « {pid} » introuvable", f"Project « {pid} » not found"), "not_found")


# ---- fichiers --------------------------------------------------------------------------------------------------------------------

def _dir(pid: str):
    return store.project_dir(pid)


def _empty(corrupt: bool = False) -> dict:
    return {"owner": None, "members": {}, "rev": 0, "last_actor": None, "last_at": None, "corrupt": corrupt}


def read(pid: str) -> dict:
    """État de partage. Fichier ABSENT : projet sans propriétaire (repris par le premier administrateur). Fichier PRÉSENT mais illisible
    ou incohérent (L41, L40-05) : ``corrupt`` vaut vrai ; le projet est alors verrouillé (voir ``role_for``), jamais réattribué en silence."""
    try:
        f = _dir(pid) / "collab.json"
    except store.ProjectNotFound:
        return _empty()
    try:
        raw = f.read_text(encoding="utf-8")
    except FileNotFoundError:
        return _empty()
    except OSError as exc:
        return _corrupt(pid, f, f"lecture impossible ({exc.__class__.__name__})")
    try:
        d = json.loads(raw)
        if not isinstance(d, dict):
            raise ValueError("objet JSON attendu")
        members = d.get("members") or {}
        owner = d.get("owner")
        if not isinstance(members, dict) or not all(isinstance(k, str) and v in ROLES for k, v in members.items()) \
                or not (owner is None or isinstance(owner, str)):
            raise ValueError("propriétaire ou membres invalides")
        return {"owner": owner, "members": dict(members), "rev": int(d.get("rev") or 0),
                "last_actor": d.get("last_actor"), "last_at": d.get("last_at"), "corrupt": False}
    except (ValueError, TypeError) as exc:
        return _corrupt(pid, f, f"contenu invalide ({exc.__class__.__name__})")


def _corrupt(pid: str, f: Any, why: str) -> dict:
    try:
        st = f.stat()
        key: tuple = (pid, st.st_mtime_ns, st.st_size)
    except OSError:
        key = (pid, 0, 0)
    if key not in _reported:   # une ligne par état du fichier, pas une par requête
        _reported.add(key)
        log_.error("collab.json illisible pour le projet %s (%s) : projet verrouillé en lecture, réservé à l'administrateur ; "
                   "restaurez le fichier depuis une sauvegarde ou supprimez-le pour que le projet revienne au premier administrateur.", pid, why)
    return _empty(True)


def _write(pid: str, d: dict) -> None:
    fsutil.atomic_write(_dir(pid) / "collab.json", json.dumps({k: v for k, v in d.items() if k != "corrupt"}, ensure_ascii=False, indent=2))


def signature(pid: str) -> tuple:
    try:
        st = (_dir(pid) / "project.json").stat()
        return (st.st_mtime_ns, st.st_size)
    except (OSError, store.ProjectNotFound):
        return (0, 0)


def owner_of(pid: str, ident: Identity) -> Optional[str]:
    return read(pid)["owner"] or ident.first_admin


def role_for(pid: str, ident: Identity) -> Optional[str]:
    """``owner``, ``editor``, ``reader`` ou ``None`` (aucun accès : le projet est alors « introuvable »)."""
    if not ident.auth:
        return "owner"
    d = read(pid)
    if d["corrupt"]:   # L41 : fichier de partage illisible : lecture seule, administrateur seul ; les autres comptes ne voient pas le projet
        return "reader" if ident.is_admin else None
    owner = d["owner"] or ident.first_admin
    if ident.user == owner:
        return "owner"
    return d["members"].get(ident.user) or ("owner" if ident.is_admin else None)   # L42 : un administrateur a les droits du propriétaire sur tout projet


def real_role(pid: str, ident: Identity) -> Optional[str]:
    """Rôle propre du compte (propriétaire, éditeur, lecteur), sans la prérogative d'administrateur."""
    if not ident.auth:
        return "owner"
    d = read(pid)
    if d["corrupt"]:
        return None
    if ident.user == (d["owner"] or ident.first_admin):
        return "owner"
    return d["members"].get(ident.user)


def admin_override(pid: str, ident: Identity) -> bool:
    """Vrai si l'accès de ce compte à ce projet ne tient qu'à son statut d'administrateur."""
    return bool(ident.auth and ident.is_admin and real_role(pid, ident) is None)


def init_project(pid: str, owner: str) -> None:
    with _lock:
        d = read(pid)
        d["owner"] = owner
        d["last_actor"], d["last_at"] = owner, iso()
        _write(pid, d)


def bump(pid: str, actor: str) -> int:
    with _lock:
        d = read(pid)
        d["rev"] += 1
        d["last_actor"], d["last_at"] = actor, iso()
        _write(pid, d)
        return d["rev"]


def log(pid: str, actor: str, action: str, **detail: Any) -> None:
    c = current()
    if c is not None and pid in c.admin_for and actor == c.identity.user:
        detail["as_admin"] = True
    with _lock:
        try:
            f = _dir(pid) / "activity.jsonl"
            lines = f.read_text(encoding="utf-8").splitlines() if f.is_file() else []
            lines.append(json.dumps({"at": iso(), "user": actor, "action": action, **({"detail": detail} if detail else {})}, ensure_ascii=False))
            fsutil.atomic_write(f, "\n".join(lines[-ACTIVITY_MAX:]) + "\n")
        except (OSError, store.ProjectNotFound):
            pass


def activity(pid: str, n: int = 100) -> list[dict]:
    try:
        lines = (_dir(pid) / "activity.jsonl").read_text(encoding="utf-8").splitlines()
    except (OSError, store.ProjectNotFound):
        return []
    out = []
    for ln in reversed(lines[-n:]):
        try:
            out.append(json.loads(ln))
        except ValueError:
            continue
    return out


# ---- contrôle d'accès ----------------------------------------------------------------------------------------------------------

def parse_etag(v: Optional[str]) -> Optional[int]:
    if v is None:
        return None
    v = v.strip()
    if v == "*":
        return -1
    if v.startswith("W/"):
        v = v[2:]
    try:
        return int(v.strip('"'))
    except ValueError:
        return -2


def check_precondition(pid: str, ident: Identity, if_match: Optional[str]) -> None:
    d = read(pid)
    want = parse_etag(if_match)
    if want is None:
        if ident.auth and d["members"]:   # projet partagé : jamais d'écriture « à l'aveugle »
            raise CollabError(428, msg("Cette écriture doit indiquer la version du projet (en-tête If-Match).",
                                       "This write must state the project version (If-Match header)."), "precondition_required", current_rev=d["rev"])
        return
    if want == -1 or want == d["rev"]:
        return
    who = d["last_actor"] or "?"
    raise CollabError(409, msg(f"Le projet a été modifié par {who} depuis votre dernier chargement. Rechargez-le, puis réappliquez votre changement : rien n'a été enregistré.",
                               f"The project was changed by {who} since you last loaded it. Reload it, then reapply your change: nothing was saved."),
                      "conflict", current_rev=d["rev"], last_actor=d["last_actor"], last_at=d["last_at"])


def require(pid: str, level: str, ident: Identity, if_match: Optional[str] = None, check_rev: bool = True) -> str:
    """Vérifie l'accès ; renvoie le rôle. 404 si le projet est inaccessible ou inconnu, 403 si le rôle ne suffit pas."""
    c = current()
    if c is not None and level in ("write", "owner") and admin_override(pid, ident):
        c.admin_for.add(pid)   # tracé dans le journal du projet : « en tant qu'administrateur »
    try:
        exists = store.exists(pid)
    except Exception:  # noqa: BLE001
        exists = False
    role = role_for(pid, ident) if exists else None
    if role is None:
        raise not_found(pid)
    if level in ("write", "owner") and role == "reader" and ident.auth and read(pid)["corrupt"]:
        raise CollabError(403, msg("Le fichier de partage de ce projet est illisible : le projet est verrouillé en lecture seule (administrateur uniquement). "
                                   "Restaurez le fichier collab.json depuis une sauvegarde, ou supprimez-le pour rendre le projet au premier administrateur.",
                                   "This project's sharing file is unreadable: the project is locked read-only (administrators only). "
                                   "Restore collab.json from a backup, or delete it to give the project back to the first administrator."),
                          "collab_corrupt", role=role)
    if level in ("write", "owner") and role == "reader":
        raise CollabError(403, msg("Ce projet est en lecture seule pour vous.", "This project is read-only for you."), "read_only", role=role)
    if level == "owner" and role != "owner":
        raise CollabError(403, msg("Seul le propriétaire peut faire cela.", "Only the owner can do this."), "owner_only", role=role)
    if level == "write" and check_rev:
        check_precondition(pid, ident, if_match)
    return role


def enforce(pid: str, level: str) -> None:
    """Appel depuis les handlers dont l'identifiant de projet est dans le corps (assistant) : lecture ou écriture du projet ``pid``."""
    c = current()
    if c is None:
        return
    require(pid, level, c.identity, c.if_match)
    if level == "write" and pid not in c.before:
        c.before[pid] = signature(pid)


def visible_projects(ident: Identity) -> dict[str, str]:
    """Identifiants de projets accessibles -> rôle."""
    out: dict[str, str] = {}
    root = store.projects_dir()
    if not root.is_dir():
        return out
    for d in root.iterdir():
        if (d / "project.json").is_file():
            r = role_for(d.name, ident)
            if r:
                out[d.name] = r
    return out


# ---- partage ----------------------------------------------------------------------------------------------------------------------

def members_view(pid: str, ident: Identity) -> dict:
    d = read(pid)
    return {"owner": d["owner"] or ident.first_admin, "members": [{"login": k, "role": v} for k, v in sorted(d["members"].items())],
            "rev": d["rev"], "last_actor": d["last_actor"], "last_at": d["last_at"]}


def share_refused() -> CollabError:
    """Réponse unique pour « compte inconnu » et « déjà propriétaire » (L41, L40-04) : un propriétaire ne peut pas lister les comptes."""
    return CollabError(422, msg("Impossible de partager avec cet identifiant : compte inconnu, ou déjà propriétaire de ce projet.",
                                "Cannot share with that identifier: unknown account, or already the owner of this project."), "share_refused")


def share(pid: str, login: str, role: str, actor: str, ident: Identity) -> str:
    if role not in ROLES:
        raise CollabError(422, msg("Rôle inconnu : « éditeur » ou « lecteur ».", "Unknown role: \"editor\" or \"reader\"."), "bad_role")
    with _lock:
        d = read(pid)
        owner = d["owner"] or ident.first_admin
        if login == owner:
            raise share_refused()
        prev = d["members"].get(login)
        d["owner"] = owner
        d["members"][login] = role
        _write(pid, d)
    log(pid, actor, "share" if prev is None else "role", login=login, role=role)
    return "added" if prev is None else "changed"


def unshare(pid: str, login: str, actor: str) -> None:
    with _lock:
        d = read(pid)
        if login not in d["members"]:
            raise CollabError(404, msg("Cet accès n'existe pas.", "That access does not exist."), "no_such_member")
        del d["members"][login]
        _write(pid, d)
    log(pid, actor, "unshare" if actor != login else "leave", login=login)


def transfer(pid: str, login: str, actor: str, ident: Identity) -> None:
    with _lock:
        d = read(pid)
        old = d["owner"] or ident.first_admin
        if login == old:
            raise share_refused()
        d["members"].pop(login, None)
        if old:
            d["members"][old] = "editor"   # l'ancien propriétaire garde la main en tant qu'éditeur
        d["owner"] = login
        _write(pid, d)
    log(pid, actor, "transfer", login=login)


def owned_by(login: str, first_admin: Optional[str]) -> list[str]:
    """Projets dont ``login`` est propriétaire (un projet sans propriétaire revient au premier administrateur)."""
    out: list[str] = []
    root = store.projects_dir()
    if not root.is_dir():
        return out
    for d in sorted(root.iterdir()):
        if (d / "project.json").is_file():
            st = read(d.name)
            if not st["corrupt"] and (st["owner"] or first_admin) == login:
                out.append(d.name)
    return out


def reassign_account(login: str, to: str, actor: str, first_admin: Optional[str]) -> int:
    """Suppression d'un compte (L42) : ses projets passent à ``to`` (qui devient propriétaire, sans doublon dans les membres), et son accès aux
    projets des autres est retiré. Renvoie le nombre de projets transférés."""
    n = 0
    root = store.projects_dir()
    if not root.is_dir():
        return 0
    for d in sorted(root.iterdir()):
        if not (d / "project.json").is_file():
            continue
        with _lock:
            st = read(d.name)
            if st["corrupt"]:
                continue
            if (st["owner"] or first_admin) == login:
                st["owner"] = to
                st["members"].pop(to, None)
                st["members"].pop(login, None)
                _write(d.name, st)
                n += 1
                log(d.name, actor, "transfer", login=to, account_deleted=login)
            elif login in st["members"]:
                del st["members"][login]
                _write(d.name, st)
                log(d.name, actor, "unshare", login=login, account_deleted=True)
    return n


def migrate(default_owner: Optional[str]) -> int:
    """Attribue les projets sans propriétaire à ``default_owner``. Idempotent : un projet déjà attribué n'est jamais touché."""
    if not default_owner:
        return 0
    n = 0
    root = store.projects_dir()
    if not root.is_dir():
        return 0
    for d in sorted(root.iterdir()):
        if not (d / "project.json").is_file():
            continue
        st = read(d.name)
        if st["owner"] or st["corrupt"]:   # un fichier de partage illisible n'est jamais écrasé par la migration
            continue
        init_project(d.name, default_owner)
        log(d.name, default_owner, "migrate")
        n += 1
    return n


# ---- présence ---------------------------------------------------------------------------------------------------------------------

def beat(pid: str, user: str) -> list[dict]:
    t = now()
    with _lock:
        pr = _presence.setdefault(pid, {})
        pr[user] = t
        for u in [u for u, ts in pr.items() if t - ts > PRESENCE_TTL]:
            del pr[u]
        return [{"user": u, "seen": round(t - ts, 1)} for u, ts in sorted(pr.items())]


def forget(pid: str) -> None:
    with _lock:
        _presence.pop(pid, None)
