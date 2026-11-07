"""OntoForge API — point d'entrée FastAPI. Les routers sont dans ``ontoforge.api``."""
import os

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from .api import ROUTERS
from .api.system import VERSION

app = FastAPI(title="OntoForge API", version=VERSION)

# CORS ouvert en dev (le front Docker passe par le proxy nginx /api, même origine).
_origins = os.environ.get("ONTOFORGE_CORS_ORIGINS", "*")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _origins.split(",")] if _origins != "*" else ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


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


for _r in ROUTERS:
    app.include_router(_r)
