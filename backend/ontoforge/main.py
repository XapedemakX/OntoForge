"""OntoForge API — point d'entrée FastAPI. Les routers sont dans ``ontoforge.api``.

Variables de déploiement (L27) : ONTOFORGE_AUTH, ONTOFORGE_PUBLIC, ONTOFORGE_STATIC_DIR, ONTOFORGE_MAX_BODY_MB, ONTOFORGE_CORS_ORIGINS
(voir docs/guide/deploiement.md).
"""
import os

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.gzip import GZipMiddleware

from . import hardening, security
from .api import ROUTERS
from .api.system import VERSION
from .auth.accounts import AccountDirectory
from .auth.config import load_config, public
from .auth.middleware import AuthMiddleware
from .collab import access as collab_access
from .collab.middleware import CollabMiddleware
from .shacl.validate import ShaclBusyError


def create_app() -> FastAPI:
    cfg = load_config()  # lève AuthConfigError si la configuration est dangereuse : le serveur ne démarre pas
    pub = public()
    # /docs et /openapi.json décrivent toute l'API : fermés sur une instance publique
    app = FastAPI(title="OntoForge API", version=VERSION, docs_url=None if pub else "/docs",
                  redoc_url=None if pub else "/redoc", openapi_url=None if pub else "/openapi.json")
    app.state.auth = cfg
    accounts = AccountDirectory(cfg)   # L42 : comptes de la configuration + magasin d'interface
    app.state.accounts = accounts
    collab_access.admin_audit = accounts.audit
    _handlers(app)
    for r in ROUTERS:
        app.include_router(r)
    static = security.static_dir()
    if static is not None:
        app.mount("/", GZipMiddleware(security.SpaStatic(static), minimum_size=1024))
    # L40 : cloisonnement des projets, rôles, versions ; derrière l'authentification (qui fournit l'identité)
    app.add_middleware(CollabMiddleware, cfg=cfg, router=app.router, accounts=accounts)
    if cfg.enabled:
        collab_access.migrate(cfg.first_admin)   # projets sans propriétaire -> premier administrateur (idempotent)
    # Ordre : le dernier ajouté est le plus extérieur (corps limité d'abord, puis en-têtes, CORS, authentification).
    if cfg.enabled:
        app.add_middleware(AuthMiddleware, cfg=cfg, accounts=accounts)
    # CORS fermé par défaut (SEC-02) : seules les origines listées dans ONTOFORGE_CORS_ORIGINS sont autorisées.
    hardening.add_cors(app)
    if pub or cfg.enabled or static is not None:
        app.add_middleware(security.SecurityHeaders)
    app.add_middleware(security.BodyLimit, max_bytes=security.max_body_bytes())
    hardening.install(app, cfg, pub)  # limitation de débit (SEC-10, le plus extérieur) et avertissements de démarrage (SEC-01, SEC-13, SEC-16)
    return app


def _handlers(app: FastAPI) -> None:
    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        """Messages d'erreur dans la langue de l'interface (settings.language.ui)."""
        from . import localize
        detail = exc.detail
        if isinstance(detail, str) and localize.ui_lang() == "en":
            detail = localize.tr(detail, "en")
        return JSONResponse(status_code=exc.status_code, content={"detail": detail, **getattr(exc, "payload", {})}, headers=getattr(exc, "headers", None))


    @app.exception_handler(ShaclBusyError)
    async def _shacl_busy(_: Request, exc: ShaclBusyError) -> JSONResponse:
        """L41 (L39-01) : plafond de validations SHACL simultanées atteint : 503 propre, à réessayer."""
        msg = collab_access.msg("Trop de validations SHACL en cours : réessayez dans quelques secondes.",
                                "Too many SHACL validations running: try again in a few seconds.")
        return JSONResponse(status_code=503, content={"detail": msg, "code": "busy", "retry_after": exc.retry_after},
                            headers={"Retry-After": str(exc.retry_after)})

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        parts = []
        for e in exc.errors()[:10]:
            loc = ".".join(str(x) for x in e.get("loc", ()) if x not in ("body", "query", "path"))
            parts.append(f"{loc or 'entrée'} : {e.get('msg', '')}")
        from . import localize
        en = localize.ui_lang() == "en"
        if en:
            parts = [localize.tr(x, "en") for x in parts]
        return JSONResponse(status_code=422, content={"detail": ("Invalid input — " if en else "Entrée invalide — ") + " ; ".join(parts),
                                                      # L42-04 : sans « input » ni « ctx » (un mot de passe trop long reviendrait dans la réponse)
                                                      "errors": jsonable([{k: v for k, v in e.items() if k not in ("input", "ctx", "url")} for e in exc.errors()])})


def jsonable(errors: list) -> list:
    from fastapi.encoders import jsonable_encoder
    return jsonable_encoder(errors, custom_encoder={Exception: str})


app = create_app()
