"""Administration des comptes (L42, D-L42-01, CONTRACTS §17) : ``/api/admin/*``, administrateurs seulement (403 ``admin_only`` par le garde).

Les comptes de la configuration sont listés « gérés par la configuration » et refusent toute modification (409 ``managed_by_config``). Chaque
action est écrite dans le journal d'administration, sans mot de passe ni hachage. Un mot de passe provisoire généré n'est renvoyé qu'une fois,
dans la réponse qui le crée ; le compte doit le changer à sa première connexion.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from ..auth import passwords
from ..auth.accounts import AccountDirectory, AccountError, LANGS
from ..collab import access

router = APIRouter(prefix="/api/admin", tags=["admin"])
NOSTORE = {"Cache-Control": "no-store"}


class CreateBody(BaseModel):
    login: str = Field(max_length=128)
    password: Optional[str] = Field(default=None, max_length=passwords.MAX_LEN)   # absent : mot de passe provisoire généré
    admin: bool = False


class ResetBody(BaseModel):
    password: Optional[str] = Field(default=None, max_length=passwords.MAX_LEN)


class AdminBody(BaseModel):
    admin: bool


def _ctx(request: Request) -> tuple[AccountDirectory, str]:
    """Annuaire et acteur ; sans authentification il n'y a pas de comptes à administrer (409)."""
    cfg = request.app.state.auth
    c = access.current()
    if not cfg.enabled or c is None or not c.identity.auth:
        raise AccountError(409, "auth_required_for_accounts", "L'administration des comptes demande l'authentification activée (ONTOFORGE_AUTH=password).",
                           "Account administration needs authentication to be enabled (ONTOFORGE_AUTH=password).")
    return request.app.state.accounts, c.identity.user


def _row(d: AccountDirectory, a, first_admin: Optional[str]) -> dict:
    out = a.public()
    out["projects"] = len(access.owned_by(a.login, first_admin))
    return out


def _json(status: int, body: dict) -> JSONResponse:
    return JSONResponse(body, status_code=status, headers=NOSTORE)


@router.get("/accounts")
def list_accounts(request: Request) -> JSONResponse:
    d, _ = _ctx(request)
    fa = request.app.state.auth.first_admin
    return _json(200, {"accounts": [_row(d, a, fa) for a in d.accounts()], "min_password": 10})


@router.post("/accounts")
def create_account(body: CreateBody, request: Request) -> JSONResponse:
    d, actor = _ctx(request)
    from .. import localize
    from ..settings import store as settings_store
    try:
        default_lang = settings_store.load(persist=False).language.ui   # langue par défaut des nouveaux comptes = réglage global (D-L42-01)
    except Exception:  # noqa: BLE001
        default_lang = "fr"
    acc, provisional = d.create(actor, body.login, body.password, body.admin, default_lang if default_lang in LANGS else "fr")
    return _json(201, {"account": acc.public(), "provisional_password": provisional})


@router.post("/accounts/{login}/reset-password")
def reset_password(login: str, request: Request, body: ResetBody = ResetBody()) -> JSONResponse:
    d, actor = _ctx(request)
    acc, provisional = d.reset_password(actor, login.strip().lower(), body.password)
    return _json(200, {"account": acc.public(), "provisional_password": provisional})


@router.post("/accounts/{login}/disable")
def disable(login: str, request: Request) -> JSONResponse:
    d, actor = _ctx(request)
    return _json(200, {"account": d.set_active(actor, login.strip().lower(), False).public()})


@router.post("/accounts/{login}/enable")
def enable(login: str, request: Request) -> JSONResponse:
    d, actor = _ctx(request)
    return _json(200, {"account": d.set_active(actor, login.strip().lower(), True).public()})


@router.post("/accounts/{login}/admin")
def set_admin(login: str, body: AdminBody, request: Request) -> JSONResponse:
    d, actor = _ctx(request)
    return _json(200, {"account": d.set_admin(actor, login.strip().lower(), body.admin).public()})


@router.delete("/accounts/{login}")
def delete_account(login: str, request: Request, transfer_to: Optional[str] = Query(default=None, max_length=128)) -> JSONResponse:
    """Supprime un compte. S'il possède des projets, ``transfer_to`` (compte actif existant) est obligatoire : ils lui sont transférés."""
    d, actor = _ctx(request)
    login = login.strip().lower()
    fa = request.app.state.auth.first_admin
    with d.lock:
        d.check_deletable(login)
        owned = access.owned_by(login, fa)
        target = (transfer_to or "").strip().lower()
        if owned:
            t = d.get(target) if target else None
            if t is None or not t.active or t.login == login:
                raise AccountError(409, "transfer_required", f"Ce compte possède {len(owned)} projet(s) : choisissez un autre compte actif qui les reçoit.",
                                   f"This account owns {len(owned)} project(s): choose another active account to receive them.", projects=len(owned))
        moved = access.reassign_account(login, target if owned else actor, actor, fa)
        d.delete(actor, login, projects_moved=moved, transferred_to=target if owned else None)
    return _json(200, {"ok": True, "projects_moved": moved, "transferred_to": target if owned else None})


@router.get("/audit")
def audit(request: Request, limit: int = Query(default=200, ge=1, le=1000)) -> JSONResponse:
    d, _ = _ctx(request)
    return _json(200, {"entries": d.audit_rows(limit)})
