"""Partage et collaboration d'un projet (L40, CONTRACTS §12) : accès, présence, journal d'activité."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from ..auth import limiter
from ..collab import access
from ..collab.access import CollabError, Identity

router = APIRouter(prefix="/api/projects/{pid}", tags=["sharing"])
SEARCH_PER_MINUTE = 10   # recherches d'identifiants par compte et par minute (anti-énumération)


class MemberIn(BaseModel):
    login: str = Field(max_length=128)
    role: str = Field(default="reader", max_length=16)


class TransferIn(BaseModel):
    login: str = Field(max_length=128)


def _ident() -> Identity:
    c = access.current()
    return c.identity if c else Identity()


def _view(pid: str, ident: Identity) -> dict:
    d = access.members_view(pid, ident)
    return {**d, "role": access.role_for(pid, ident), "me": ident.user, "sharing_available": ident.auth, "admin": ident.is_admin}


def _target(pid: str, login: str, ident: Identity) -> str:
    """Compte visé par un partage : limite les tentatives ; « inconnu » et « déjà propriétaire » donnent la MÊME réponse (L41, L40-04), après
    le même travail (lecture de l'état de partage sous verrou) pour que le temps de réponse ne les distingue pas non plus."""
    if not ident.auth:
        raise CollabError(409, access.msg("Le partage demande l'authentification activée (ONTOFORGE_AUTH=password).",
                                          "Sharing needs authentication to be enabled (ONTOFORGE_AUTH=password)."), "auth_required_for_sharing")
    if not limiter.allow("share:" + ident.user, SEARCH_PER_MINUTE):
        raise CollabError(429, access.msg("Trop de tentatives : réessayez dans une minute.", "Too many attempts: try again in a minute."), "rate_limited")
    name = login.strip().lower()
    if name not in ident.accounts:
        with access._lock:   # noqa: SLF001 — même chemin de lecture que ``share`` / ``transfer`` (compte connu)
            access.read(pid)
        raise access.share_refused()
    return name


@router.get("/access")
def get_access(pid: str) -> dict:
    return _view(pid, _ident())


@router.post("/access/members")
def add_member(pid: str, body: MemberIn) -> dict:
    ident = _ident()
    login = _target(pid, body.login, ident)
    access.share(pid, login, body.role, ident.user, ident)
    return _view(pid, ident)


@router.delete("/access/members/{login}")
def remove_member(pid: str, login: str) -> dict:
    ident = _ident()
    login = login.strip().lower()
    role = access.role_for(pid, ident)
    c = access.current()
    if c is not None and access.admin_override(pid, ident):
        c.admin_for.add(pid)   # L42 : retrait fait en tant qu'administrateur, tracé comme tel
    if role != "owner" and login != ident.user:
        raise CollabError(403, access.msg("Seul le propriétaire peut retirer l'accès d'un autre compte.", "Only the owner can remove another account's access."), "owner_only")
    access.unshare(pid, login, ident.user)
    out = _view(pid, ident)
    return out


@router.post("/access/transfer")
def transfer(pid: str, body: TransferIn) -> dict:
    ident = _ident()
    login = _target(pid, body.login, ident)
    access.transfer(pid, login, ident.user, ident)
    return _view(pid, ident)


@router.post("/presence")
def presence(pid: str) -> JSONResponse:
    ident = _ident()
    d = access.read(pid)
    owner = d["owner"] or ident.first_admin
    who = access.beat(pid, ident.user)
    present = [{"user": w["user"], "role": access.role_for(pid, ident) if w["user"] == ident.user else ("owner" if w["user"] == owner else d["members"].get(w["user"], "reader")),
                "me": w["user"] == ident.user} for w in who]
    return JSONResponse({"present": present, "rev": d["rev"], "last_actor": d["last_actor"], "last_at": d["last_at"],
                         "role": access.role_for(pid, ident), "me": ident.user, "auth": ident.auth}, headers={"Cache-Control": "no-store"})


@router.get("/activity")
def get_activity(pid: str, limit: Optional[int] = 100) -> list[dict]:
    return access.activity(pid, max(1, min(int(limit or 100), 200)))
