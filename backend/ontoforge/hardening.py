"""Durcissement au démarrage (L39-secu) : CORS fermé par défaut, limitation de débit, avertissements de configuration.

``install(app, cfg, pub)`` est appelé par ``main.create_app`` ; les contrôles de démarrage n'arrêtent jamais le serveur (ils journalisent).
"""
from __future__ import annotations

import logging
import os
import stat
import sys
from pathlib import Path
from typing import Any, Mapping, Optional

log = logging.getLogger("ontoforge.security")
LOOPBACK = ("127.", "localhost", "::1", "[::1]")
CORS_METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]
CORS_HEADERS = ["Content-Type", "X-CSRF-Token", "Accept", "Accept-Language"]


def cors_origins(env: Optional[Mapping[str, str]] = None) -> list[str]:
    """Origines autorisées : uniquement celles listées dans ONTOFORGE_CORS_ORIGINS (séparées par des virgules). Vide = même origine seulement."""
    raw = str((os.environ if env is None else env).get("ONTOFORGE_CORS_ORIGINS", "") or "")
    return [o.strip().rstrip("/") for o in raw.split(",") if o.strip()]


def add_cors(app: Any) -> list[str]:
    origins = cors_origins()
    if origins:
        from fastapi.middleware.cors import CORSMiddleware
        if "*" in origins:
            log.warning("ONTOFORGE_CORS_ORIGINS=* : toutes les pages web peuvent lire l'API. Listez plutôt les origines voulues "
                        "(par exemple http://localhost:5173).")
        app.add_middleware(CORSMiddleware, allow_origins=origins, allow_methods=CORS_METHODS, allow_headers=CORS_HEADERS)
    return origins


def _is_loopback(host: str) -> bool:
    h = host.strip().lower()
    return h.startswith(LOOPBACK)


def exposure_warning(env: Mapping[str, str], auth_enabled: bool, argv: Optional[list[str]] = None) -> Optional[str]:
    """Message si l'instance écoute hors de la boucle locale sans authentification. ``ONTOFORGE_BIND_HOST`` est l'adresse publiée par
    docker compose (127.0.0.1 par défaut) ; hors conteneur, l'option ``--host`` d'uvicorn est lue."""
    if auth_enabled:
        return None
    host = str(env.get("ONTOFORGE_BIND_HOST", "") or "").strip()
    if not host and not os.path.exists("/.dockerenv"):
        a = argv if argv is not None else sys.argv
        for i, x in enumerate(a):
            if x == "--host" and i + 1 < len(a):
                host = a[i + 1]
            elif x.startswith("--host="):
                host = x.split("=", 1)[1]
    if host and not _is_loopback(host):
        return (f"L'instance écoute sur {host} (hors de cette machine) SANS authentification : toute personne qui atteint ce port peut lire et "
                "modifier les projets et utiliser les clés enregistrées. Activez ONTOFORGE_AUTH=password (voir le guide, section "
                "« Ouvrir l'instance »), ou revenez à 127.0.0.1.")
    return None


def env_file_warning(paths: Optional[list[Path]] = None) -> Optional[str]:
    """Avertit si un fichier .env est lisible par d'autres comptes. Le contenu n'est jamais lu."""
    cands = paths if paths is not None else [Path(".env"), Path(__file__).resolve().parents[2] / ".env"]
    for p in cands:
        try:
            if p.is_file() and p.stat().st_mode & (stat.S_IRGRP | stat.S_IROTH):
                return f"Le fichier {p} est lisible par d'autres comptes : exécutez « chmod 600 {p} » (il contient vos secrets)."
        except OSError:
            continue
    return None


def egress_warning(env: Mapping[str, str], pub: bool) -> Optional[str]:
    if pub and not str(env.get("ONTOFORGE_EGRESS_ALLOW", "") or "").strip():
        return ("ONTOFORGE_PUBLIC=1 sans ONTOFORGE_EGRESS_ALLOW : tout hôte public est joignable par les appels sortants (fournisseur LLM, "
                "endpoints SPARQL). Renseignez la liste des hôtes autorisés.")
    return None


def startup_checks(cfg: Any, pub: bool, env: Optional[Mapping[str, str]] = None) -> list[str]:
    e = os.environ if env is None else env
    msgs = [m for m in (exposure_warning(e, bool(getattr(cfg, "enabled", False))), env_file_warning(), egress_warning(e, pub)) if m]
    for m in msgs:
        log.warning(m)
        print("[ontoforge] ATTENTION : " + m, file=sys.stderr, flush=True)
    return msgs


def install(app: Any, cfg: Any, pub: bool) -> None:
    """À appeler en dernier : le limiteur de débit est le middleware le plus extérieur."""
    from .ratelimit import RateLimit
    app.add_middleware(RateLimit, hops=getattr(cfg, "proxy_hops", 0), cookie_name=getattr(cfg, "cookie_name", "") if getattr(cfg, "enabled", False) else "")
    startup_checks(cfg, pub)
