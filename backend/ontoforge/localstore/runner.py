"""Exécution des requêtes SPARQL sur le triplestore local (L19) : lecture seule, délai, plafond de lignes, aucun réseau.

Chaque requête tourne dans un PROCESSUS FILS (`_worker.py`) qui ouvre la base en lecture seule :
- délai tenu pour de vrai (le fils est tué à l'échéance, ce qu'un thread ne permettrait pas) ;
- mémoire plafonnée (RLIMIT_AS) et temps CPU plafonné (RLIMIT_CPU) ;
- SELECT, ASK, CONSTRUCT et DESCRIBE seulement : UPDATE -> 403, `SERVICE` (requête fédérée = accès réseau) -> 403.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Optional

from ..queries import endpoint as ep_mod
from ..queries.endpoint import EndpointError, HARD_LIMIT, QueryResult
from . import store as st

WORKER = Path(__file__).with_name("_worker.py")
_LITERALS = re.compile(r"""(\"\"\"(?:.|\n)*?\"\"\"|'''(?:.|\n)*?'''|"(?:\\.|[^"\\\n])*"|'(?:\\.|[^'\\\n])*'|<[^\s<>"{}|^`\\]*>|\#[^\n]*)""")


def _has_service(sparql: str) -> bool:
    """`SERVICE` (fédération) : détecté dans l'algèbre rdflib, avec un second filet lexical hors chaînes, IRI et commentaires."""
    stripped = _LITERALS.sub(" ", sparql)
    # mot-clé seul : pas une variable (?service, $service) ni un nom préfixé (am:Service) — faux positifs relevés en revue it1
    if re.search(r"(?<![\w?$:])SERVICE(?![\w:-])", stripped, re.I):
        return True
    try:
        from rdflib.plugins.sparql import algebra, parser
        found: list[bool] = []
        algebra.traverse(algebra.translateQuery(parser.parseQuery(sparql)).algebra,
                         visitPost=lambda n: found.append(True) if getattr(n, "name", "") in ("Service", "ServiceGraphPattern") else None)
        return bool(found)
    except Exception:  # noqa: BLE001 - une requête illisible est déjà refusée par query_form
        return False


def guard(sparql: str) -> str:
    """Forme de la requête (SELECT | ASK | CONSTRUCT | DESCRIBE) ou EndpointError (UPDATE 403, syntaxe 422, SERVICE 403)."""
    form = ep_mod.query_form(sparql)
    if _has_service(sparql):
        raise EndpointError("Requête refusée : SERVICE (requête fédérée) n'est pas autorisé sur le triplestore local, "
                            "qui n'a aucun accès réseau.", 403)
    return form


def dataset_clause(sparql: str) -> Optional[dict[str, list[str]]]:
    """Jeu de données déclaré par la requête (`FROM` / `FROM NAMED`, SPARQL 1.1 §13.2) ou None. Le fils fusionne plusieurs `FROM`
    en ensemble (Oxigraph 0.5.13 les fusionne en multi-ensemble) et ignore le graphe par défaut matérialisé."""
    from rdflib.plugins.sparql import parser
    try:
        q = parser.parseQuery(sparql)[1]  # CompValue.get renvoie le nom de la clé quand elle manque : tester la présence
        clauses = q["datasetClause"] if "datasetClause" in q else None
    except Exception:  # noqa: BLE001 - déjà refusé par query_form
        return None
    if not clauses:
        return None
    return {"default": [str(c["default"]) for c in clauses if "default" in c],
            "named": [str(c["named"]) for c in clauses if "named" in c]}


def _limits(mem_mb: int, cpu_s: int):
    def apply() -> None:  # exécuté dans le fils, avant exec
        import resource
        resource.setrlimit(resource.RLIMIT_AS, (mem_mb << 20, mem_mb << 20))
        resource.setrlimit(resource.RLIMIT_CPU, (cpu_s, cpu_s + 1))
        resource.setrlimit(resource.RLIMIT_FSIZE, (0, 0))  # la base est ouverte en lecture seule : aucune écriture de fichier
    return apply


def run_local(p: Any, sparql: str, limit: int = 100, timeout_s: Optional[float] = None) -> QueryResult:
    """Exécute `sparql` sur le triplestore local du projet `p` (créé à la volée avec l'ontologie et les individus)."""
    lim = st.limits()
    limit = max(1, min(int(limit), HARD_LIMIT))
    timeout = float(min(max(timeout_s or lim["query_timeout_s"], 1), 120))
    form = guard(sparql)
    q = sparql
    if form in ("SELECT", "CONSTRUCT", "DESCRIBE"):
        q, user_limit = ep_mod.force_limit(sparql, limit + 1)
    else:
        user_limit = None
    try:
        st.ensure(p.id, p)
    except st.StoreError as exc:
        raise EndpointError(str(exc), exc.status) from None
    payload = json.dumps({"path": str(st.db_path(p.id)), "query": q, "limit": limit, "dataset": dataset_clause(sparql)})
    t0 = time.perf_counter()
    with st.lock(p.id).read():
        try:
            proc = subprocess.run([sys.executable, "-I", str(WORKER)], input=payload.encode("utf-8"), capture_output=True,
                                  timeout=timeout, cwd="/", preexec_fn=_limits(lim["query_memory_mb"], int(timeout) + 2))
        except subprocess.TimeoutExpired:
            raise EndpointError(f"Délai dépassé ({timeout:.0f} s) : la requête a été interrompue sur le triplestore local.", 504) from None
    ms = int((time.perf_counter() - t0) * 1000)
    if proc.returncode != 0 or not proc.stdout:
        why = "mémoire ou temps CPU plafonnés" if proc.returncode < 0 or b"MemoryError" in proc.stderr else "erreur interne"
        raise EndpointError(f"La requête a été arrêtée sur le triplestore local ({why}, code {proc.returncode}). "
                            "Simplifiez-la ou ajoutez un LIMIT.", 502)
    out = json.loads(proc.stdout)
    if "error" in out:
        raise EndpointError(("SPARQL invalide : " if out["error"] == "syntax" else "Triplestore local : ") + out["message"], 422 if out["error"] == "syntax" else 502)
    if out["form"] == "ASK":
        return QueryResult(boolean=out["boolean"], elapsed_ms=ms, sparql=q)
    truncated = out["truncated"] or (user_limit is not None and user_limit > limit and len(out["rows"]) >= limit)
    return QueryResult(columns=out["columns"], rows=out["rows"], truncated=truncated, elapsed_ms=ms, sparql=q)
