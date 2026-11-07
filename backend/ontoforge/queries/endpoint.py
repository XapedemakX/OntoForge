"""Accès aux endpoints SPARQL (lecture seule) — propriétaire : query (L15).

Garde-fous : refus des mises à jour (UPDATE), LIMIT forcé, délai d'attente par endpoint, aucune fuite de secret.
Les tests substituent `make_client` (transport httpx simulé ou endpoint rdflib local) : pas de réseau.
"""
from __future__ import annotations

import re
import time
from typing import Any, Optional

import httpx
from pydantic import BaseModel, Field

from ..settings.models import EndpointConfig

ACCEPT = "application/sparql-results+json"
HARD_LIMIT = 5000


class EndpointError(Exception):
    """Erreur lisible (message français, sans secret). `status` = code HTTP proposé pour l'API."""

    def __init__(self, message: str, status: int = 502):
        super().__init__(message)
        self.status = status


def make_client(timeout: float) -> httpx.Client:
    return httpx.Client(timeout=timeout)


# ---------------------------------------------------------------------------- lecture seule / LIMIT

def _scan(q: str):
    """Itère (index, caractère, profondeur d'accolades) hors commentaires, chaînes et IRIs."""
    i, n, depth = 0, len(q), 0
    while i < n:
        c = q[i]
        if c == "#":
            while i < n and q[i] != "\n":
                i += 1
            continue
        if c in "\"'":
            long = q[i:i + 3] == c * 3
            end = c * 3 if long else c
            i += 3 if long else 1
            while i < n and not q.startswith(end, i):
                i += 2 if q[i] == "\\" else 1
            i += len(end)
            continue
        if c == "<" and re.match(r"<[^\s<>\"{}|^`\\]*>", q[i:i + 400]):
            i += q.index(">", i) + 1 - i
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
        yield i, c, depth
        i += 1


def query_form(sparql: str) -> str:
    """SELECT | ASK | CONSTRUCT | DESCRIBE. Lève EndpointError pour une mise à jour ou une syntaxe invalide."""
    from rdflib.plugins.sparql import parser
    try:
        parsed = parser.parseQuery(sparql)
    except Exception as exc:  # noqa: BLE001
        try:
            parser.parseUpdate(sparql)
        except Exception:  # noqa: BLE001
            raise EndpointError(f"SPARQL invalide : {str(exc).splitlines()[0][:200]}", 422) from None
        raise EndpointError("Requête refusée : seules les requêtes en lecture (SELECT, ASK, CONSTRUCT, DESCRIBE) "
                            "sont autorisées, pas les mises à jour (UPDATE).", 403) from None
    return str(parsed[1].name).replace("Query", "").upper()


def force_limit(sparql: str, n: int) -> tuple[str, Optional[int]]:
    """Plafonne le LIMIT de niveau supérieur à `n` (l'ajoute s'il manque). Renvoie (requête, LIMIT utilisateur)."""
    m = None
    for m in re.finditer(r"\bLIMIT\s+(\d+)", _top_level(sparql), re.I):
        pass
    if m:
        user = int(m.group(1))
        if user <= n:
            return sparql, user
        return sparql[:m.start(1)] + str(n) + sparql[m.end(1):], user
    return sparql.rstrip().rstrip(";") + f"\nLIMIT {n}\n", None


def _top_level(q: str) -> str:
    """Copie de la requête où tout ce qui n'est pas au niveau 0 (hors accolades, chaînes, commentaires) est blanchi."""
    out = [" "] * len(q)
    for i, c, d in _scan(q):
        if d == 0 and c not in "{}":
            out[i] = c
    return "".join(out)


# ---------------------------------------------------------------------------------------- exécution

class QueryResult(BaseModel):
    columns: list[str] = Field(default_factory=list)
    rows: list[dict[str, Optional[dict[str, str]]]] = Field(default_factory=list)
    truncated: bool = False
    elapsed_ms: int = 0
    boolean: Optional[bool] = None
    sparql: str = ""


def _auth(ep: EndpointConfig) -> tuple[dict[str, str], Optional[tuple[str, str]]]:
    headers = {"Accept": ACCEPT}
    auth = None
    if ep.auth == "basic":
        auth = (ep.username or "", ep.secret or "")
    elif ep.auth == "bearer" and ep.secret:
        headers["Authorization"] = "Bearer " + ep.secret
    return headers, auth


def _post(ep: EndpointConfig, query: str, timeout: Optional[float] = None) -> httpx.Response:
    headers, auth = _auth(ep)
    data = {"query": query}
    if ep.default_graph:
        data["default-graph-uri"] = ep.default_graph
    t = timeout or ep.timeout_s
    try:
        with make_client(t) as c:
            return c.post(ep.url, data=data, headers=headers, auth=auth)
    except httpx.TimeoutException:
        raise EndpointError(f"Délai dépassé ({t:.0f} s) en attendant l'endpoint SPARQL « {ep.name} ».", 504) from None
    except httpx.HTTPError as exc:
        raise EndpointError(f"Connexion impossible à l'endpoint « {ep.name} » ({type(exc).__name__}).", 502) from None


def ping(ep: EndpointConfig, timeout: float = 15.0) -> dict[str, Any]:
    t0 = time.perf_counter()
    try:
        r = _post(ep, "ASK {}", timeout)
    except EndpointError as exc:
        return {"ok": False, "latency_ms": int((time.perf_counter() - t0) * 1000), "message": str(exc)}
    ms = int((time.perf_counter() - t0) * 1000)
    if r.status_code in (401, 403):
        return {"ok": False, "latency_ms": ms, "message": f"Authentification refusée par l'endpoint (HTTP {r.status_code})."}
    if r.status_code >= 400:
        return {"ok": False, "latency_ms": ms, "message": f"L'endpoint a répondu HTTP {r.status_code}."}
    return {"ok": True, "latency_ms": ms, "message": f"Endpoint SPARQL joignable (HTTP {r.status_code}) en {ms} ms."}


def run_select(ep: EndpointConfig, sparql: str, limit: int = 100) -> QueryResult:
    """Exécute une requête en lecture seule avec LIMIT forcé (limit+1 pour détecter la troncature)."""
    limit = max(1, min(int(limit), HARD_LIMIT))
    form = query_form(sparql)
    q, user_limit = (sparql, None)
    if form in ("SELECT", "CONSTRUCT", "DESCRIBE"):
        q, user_limit = force_limit(sparql, limit + 1)
    t0 = time.perf_counter()
    r = _post(ep, q)
    ms = int((time.perf_counter() - t0) * 1000)
    if r.status_code in (401, 403):
        raise EndpointError(f"Authentification refusée par l'endpoint (HTTP {r.status_code}).", 502)
    if r.status_code >= 400:
        raise EndpointError(f"L'endpoint a répondu HTTP {r.status_code} : {r.text[:200].strip()}", 502)
    try:
        js = r.json()
    except ValueError:
        raise EndpointError("Réponse de l'endpoint illisible (JSON SPARQL attendu).", 502) from None
    if "boolean" in js:
        return QueryResult(boolean=bool(js["boolean"]), elapsed_ms=ms, sparql=q)
    cols = list(js.get("head", {}).get("vars", []))
    rows = [{c: (b.get(c) if c in b else None) for c in cols} for b in js.get("results", {}).get("bindings", [])]
    truncated = len(rows) > limit or (user_limit is not None and user_limit > limit and len(rows) >= limit)
    return QueryResult(columns=cols, rows=rows[:limit], truncated=truncated, elapsed_ms=ms, sparql=q)


def graph_preview(res: QueryResult, edges_spec: list[tuple[str, str, str]] | None = None, max_nodes: int = 300) -> dict[str, Any]:
    """Aperçu graphe : nœuds = valeurs IRI des colonnes ; arêtes = (colonne source, colonne cible, IRI propriété) par ligne."""
    from ..core.onto_model import local_name
    nodes: dict[str, dict[str, Any]] = {}
    edges: dict[str, dict[str, Any]] = {}
    labels = {c[:-6]: c for c in res.columns if c.endswith("_label")}
    for row in res.rows:
        for c in res.columns:
            cell = row.get(c)
            if cell and cell.get("type") == "uri" and len(nodes) < max_nodes:
                lab = row.get(labels.get(c, ""), None)
                nodes.setdefault(cell["value"], {"id": cell["value"], "column": c,
                                                 "label": (lab or {}).get("value") or local_name(cell["value"])})
        for a, b, p in edges_spec or []:
            ca, cb = row.get(a), row.get(b)
            if ca and cb and ca["value"] in nodes and cb["value"] in nodes:
                eid = f"{ca['value']}|{p}|{cb['value']}"
                edges.setdefault(eid, {"id": eid, "source": ca["value"], "target": cb["value"], "iri": p, "label": local_name(p)})
    return {"nodes": list(nodes.values()), "edges": list(edges.values())}
