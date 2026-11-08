"""OntoForge API — point d'entrée FastAPI. Les routers sont dans ``ontoforge.api``.

Variables de déploiement (L27) : ONTOFORGE_AUTH, ONTOFORGE_PUBLIC, ONTOFORGE_STATIC_DIR, ONTOFORGE_MAX_BODY_MB, ONTOFORGE_CORS_ORIGINS
(voir docs/guide/deploiement.md).
"""
import os

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.gzip import GZipMiddleware

from . import security
from .api import ROUTERS
from .api.system import VERSION
from .auth.config import load_config, public
from .auth.middleware import AuthMiddleware


def create_app() -> FastAPI:
    cfg = load_config()  # lève AuthConfigError si la configuration est dangereuse : le serveur ne démarre pas
    pub = public()
    # /docs et /openapi.json décrivent toute l'API : fermés sur une instance publique
    app = FastAPI(title="OntoForge API", version=VERSION, docs_url=None if pub else "/docs",
                  redoc_url=None if pub else "/redoc", openapi_url=None if pub else "/openapi.json")
    app.state.auth = cfg
    _handlers(app)
    for r in ROUTERS:
        app.include_router(r)
    static = security.static_dir()
    if static is not None:
        app.mount("/", GZipMiddleware(security.SpaStatic(static), minimum_size=1024))
    # Ordre : le dernier ajouté est le plus extérieur (corps limité d'abord, puis en-têtes, CORS, authentification).
    if cfg.enabled:
        app.add_middleware(AuthMiddleware, cfg=cfg)
    # CORS ouvert en dev (le front Docker passe par le proxy nginx /api, même origine) ; fermé sur une instance publique.
    origins = os.environ.get("ONTOFORGE_CORS_ORIGINS", "" if pub else "*")
    if origins:
        app.add_middleware(CORSMiddleware, allow_origins=[o.strip() for o in origins.split(",")] if origins != "*" else ["*"],
                           allow_methods=["*"], allow_headers=["*"])
    if pub or cfg.enabled or static is not None:
        app.add_middleware(security.SecurityHeaders)
    app.add_middleware(security.BodyLimit, max_bytes=security.max_body_bytes())
    return app


def _handlers(app: FastAPI) -> None:
    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        """Messages d'erreur dans la langue de l'interface (settings.language.ui)."""
        from . import localize
        detail = exc.detail
        if isinstance(detail, str) and localize.ui_lang() == "en":
            detail = localize.tr(detail, "en")
        return JSONResponse(status_code=exc.status_code, content={"detail": detail}, headers=getattr(exc, "headers", None))


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
                                                      "errors": jsonable(exc.errors())})


def jsonable(errors: list) -> list:
    from fastapi.encoders import jsonable_encoder
    return jsonable_encoder(errors, custom_encoder={Exception: str})


app = create_app()
