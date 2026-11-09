"""Paramètres (CONTRACTS §4) : fournisseurs LLM chiffrés, langues, valeurs par défaut, endpoint SPARQL.
Aucune réponse ne contient de secret : seulement ``has_key`` / ``key_last4``."""
from __future__ import annotations

import logging
import time
from typing import Any, Optional

import httpx
from fastapi import APIRouter, Body, HTTPException
from pydantic import ValidationError

from .. import netguard
from ..assistant.providers import LLMError, from_config
from .. import standards
from ..settings import store
from ..settings.models import DEFAULT_MODELS, EndpointConfig, ProviderConfig, Settings, SparqlAuth, SparqlEndpoint

log = logging.getLogger("ontoforge.settings")
router = APIRouter(prefix="/api/settings", tags=["settings"])
TEST_TIMEOUT = 15.0
_RO = ("has_key", "key_last4", "key_unreadable", "configured")  # champs de la vue publique, ignorés en entrée


def _invalid(exc: ValidationError) -> HTTPException:
    parts = [f"{'.'.join(str(x) for x in e['loc'])} : {e['msg']}" for e in exc.errors()[:5]]
    return HTTPException(status_code=422, detail="Paramètres invalides — " + " ; ".join(parts))


def _secret_patch(current: Optional[str], patch: dict[str, Any], key: str) -> Optional[str]:
    """Absent ou chaîne vide = inchangé ; null explicite = supprimé ; chaîne = remplacé."""
    if key not in patch or patch[key] == "":
        return current
    return patch[key] if patch[key] is None else str(patch[key])


def _patch_provider(cur: Optional[ProviderConfig], patch: dict[str, Any], taken: set[str]) -> ProviderConfig:
    d = cur.model_dump() if cur else {"id": "", "name": "", "kind": "", "extra": {}}
    for f in ("name", "kind", "base_url", "model", "extra"):
        if f in patch:
            if cur is not None and cur.kind == "mock" and f == "kind" and patch[f] != "mock":
                raise HTTPException(status_code=409, detail="Le fournisseur mock ne peut pas changer de type.")
            d[f] = patch[f]
    if cur is None:
        d["id"] = patch.get("id") or store.slug_id(str(patch.get("name") or d["kind"]), taken)
        if d["id"] in taken:
            raise HTTPException(status_code=409, detail=f"Un fournisseur « {d['id']} » existe déjà.")
    d["api_key"] = _secret_patch(cur.api_key if cur else None, patch, "api_key")
    d["key_unreadable"] = bool(cur and cur.key_unreadable and d["api_key"] == cur.api_key)
    if isinstance(d.get("base_url"), str):
        d["base_url"] = d["base_url"].strip() or None
    try:
        p = ProviderConfig.model_validate(d)
    except ValidationError as exc:
        raise _invalid(exc) from None
    if not p.model:
        p.model = DEFAULT_MODELS[p.kind]
    if p.base_url and not p.base_url.startswith(("http://", "https://")):
        raise HTTPException(status_code=422, detail="L'URL du fournisseur doit commencer par http:// ou https://.")
    return p


def _view() -> dict[str, Any]:
    s = store.load()
    view = s.public()
    if s.language.ui == "en":  # nom du fournisseur de démonstration créé en français par défaut
        for p in view["llm_providers"]:
            if p["kind"] == "mock" and p["name"] == "Mock (démonstration)":
                p["name"] = "Mock (demo)"
    view["versions_view"] = standards.describe(None, base=view["versions"])  # L31 : statut de chaque version du défaut global
    view["versions_check"] = {k: v for k, v in standards.check(None, base=view["versions"]).items() if k in ("gaps", "needs_attention", "recommended", "updated")}
    return view


@router.get("")
def get_settings() -> Any:
    return _view()


@router.put("")
def put_settings(body: dict[str, Any] = Body(...)) -> Any:
    s = store.load()
    for patch in body.get("llm_providers") or []:
        if not isinstance(patch, dict) or not patch.get("id"):
            raise HTTPException(status_code=422, detail="Chaque fournisseur modifié doit porter un « id ».")
        patch = {k: v for k, v in patch.items() if k not in _RO}
        cur = s.provider(patch["id"])
        new = _patch_provider(cur, patch, {p.id for p in s.llm_providers})
        s.llm_providers = [new if p.id == new.id else p for p in s.llm_providers] if cur else [*s.llm_providers, new]
    if "default_provider_id" in body:
        if s.provider(body["default_provider_id"]) is None:
            raise HTTPException(status_code=422, detail=f"Fournisseur par défaut inconnu « {body['default_provider_id']} ».")
        s.default_provider_id = body["default_provider_id"]
    try:
        for key, model in (("language", s.language), ("defaults", s.defaults)):
            if isinstance(body.get(key), dict):
                setattr(s, key, type(model).model_validate({**model.model_dump(), **body[key]}))
        if isinstance(body.get("versions"), dict):  # L31 : défaut global des versions
            patch_v: dict[str, str] = {}
            for k, v in body["versions"].items():
                err = standards.check_format(k, v)
                if err:
                    raise HTTPException(status_code=422, detail=err)
                patch_v[k] = standards.normalize(k, v)
            s.versions = type(s.versions).model_validate({**s.versions.model_dump(), **patch_v})
        if "sparql_endpoint" in body:
            s.sparql_endpoint = _patch_sparql(s.sparql_endpoint, body["sparql_endpoint"])
            _sync_legacy(s)
        for patch in body.get("sparql_endpoints") or []:
            if not isinstance(patch, dict) or not patch.get("id"):
                raise HTTPException(status_code=422, detail="Chaque endpoint modifié doit porter un « id ».")
            patch = {k: v for k, v in patch.items() if k not in _EP_RO}
            cur = s.endpoint(patch["id"])
            new = _patch_endpoint(cur, patch, {e.id for e in s.sparql_endpoints})
            s.sparql_endpoints = [new if e.id == new.id else e for e in s.sparql_endpoints] if cur else [*s.sparql_endpoints, new]
            s.active_endpoint_id = s.active_endpoint_id or new.id
        if "active_endpoint_id" in body:
            if body["active_endpoint_id"] is not None and s.endpoint(body["active_endpoint_id"]) is None:
                raise HTTPException(status_code=422, detail=f"Endpoint actif inconnu « {body['active_endpoint_id']} ».")
            s.active_endpoint_id = body["active_endpoint_id"]
    except ValidationError as exc:
        raise _invalid(exc) from None
    store.save(s)
    return s.public()


def _sync_legacy(s: Settings) -> None:
    """L'ancien champ unique alimente l'endpoint « default » (compatibilité L8)."""
    old = s.sparql_endpoint
    cur = s.endpoint("default")
    if not old.url:
        return
    a = old.auth
    patch = {"url": old.url, "auth": a.type if a else "none", "username": a.username if a else None, "secret": a.secret if a else None}
    if cur is None:
        patch.update(id="default", name="Endpoint SPARQL")
    new = _patch_endpoint(cur, patch, {e.id for e in s.sparql_endpoints})
    s.sparql_endpoints = [new if e.id == "default" else e for e in s.sparql_endpoints] if cur else [*s.sparql_endpoints, new]
    s.active_endpoint_id = s.active_endpoint_id or "default"


def _patch_sparql(cur: SparqlEndpoint, patch: Any) -> SparqlEndpoint:
    if patch is None:
        return SparqlEndpoint()
    url = str(patch.get("url", cur.url)).strip()
    if url and not url.startswith(("http://", "https://")):
        raise HTTPException(status_code=422, detail="L'URL de l'endpoint SPARQL doit commencer par http:// ou https://.")
    auth = cur.auth
    if "auth" in patch:
        ap = patch["auth"]
        if ap is None:
            auth = None
        else:
            ap = {k: v for k, v in ap.items() if k != "has_secret"}
            base = cur.auth or SparqlAuth()
            auth = SparqlAuth(type=ap.get("type", base.type), username=ap.get("username", base.username),
                              secret=_secret_patch(base.secret, ap, "secret"))
            if auth.type == "none":
                auth = None
    return SparqlEndpoint(url=url, auth=auth)


@router.post("/providers", status_code=201)
def add_provider(body: dict[str, Any] = Body(...)) -> Any:
    s = store.load()
    p = _patch_provider(None, {k: v for k, v in body.items() if k not in _RO}, {x.id for x in s.llm_providers})
    s.llm_providers.append(p)
    store.save(s)
    return p.public()


@router.put("/providers/{pid}")
def update_provider(pid: str, body: dict[str, Any] = Body(...)) -> Any:
    s = store.load()
    cur = s.provider(pid)
    if cur is None:
        raise HTTPException(status_code=404, detail=f"Fournisseur « {pid} » introuvable.")
    patch = {k: v for k, v in body.items() if k not in _RO and k != "id"}
    new = _patch_provider(cur, patch, {x.id for x in s.llm_providers})
    s.llm_providers = [new if x.id == pid else x for x in s.llm_providers]
    store.save(s)
    return new.public()


@router.delete("/providers/{pid}")
def delete_provider(pid: str) -> Any:
    s = store.load()
    if s.provider(pid) is None:
        raise HTTPException(status_code=404, detail=f"Fournisseur « {pid} » introuvable.")
    if pid == store.MOCK_ID:
        raise HTTPException(status_code=409, detail="Le fournisseur mock est toujours disponible et ne peut pas être supprimé.")
    s.llm_providers = [x for x in s.llm_providers if x.id != pid]
    if s.default_provider_id == pid:
        s.default_provider_id = store.MOCK_ID
    store.save(s)
    return {"deleted": pid, "default_provider_id": s.default_provider_id}


@router.post("/providers/{pid}/test")
def test_provider(pid: str, body: Optional[dict[str, Any]] = Body(default=None)) -> Any:
    """Appel minimal (timeout 15 s). Le corps optionnel (api_key, base_url, model) teste des modifications non enregistrées."""
    s = store.load()
    cur = s.provider(pid)
    if cur is None:
        raise HTTPException(status_code=404, detail=f"Fournisseur « {pid} » introuvable.")
    cfg = _patch_provider(cur, {k: v for k, v in (body or {}).items() if k in ("api_key", "base_url", "model")}, {x.id for x in s.llm_providers})
    prov = from_config(cfg)
    prov.timeout_s = TEST_TIMEOUT
    if not prov.configured:
        why = "aucune clé d'API" if cfg.kind == "anthropic" else "aucune URL"
        return {"ok": False, "latency_ms": 0, "model": cfg.model, "message": f"Fournisseur non configuré : {why} renseignée."}
    t0 = time.perf_counter()
    try:
        prov.complete("Test de connexion. Réponds uniquement par : OK", [{"role": "user", "content": "ping"}], 16)
    except LLMError as exc:
        ms = int((time.perf_counter() - t0) * 1000)
        return {"ok": False, "latency_ms": ms, "model": cfg.model, "message": str(exc)}
    except Exception as exc:  # défensif : jamais de fuite de clé dans le message
        log.warning("test fournisseur %s : %s", pid, type(exc).__name__)
        return {"ok": False, "latency_ms": int((time.perf_counter() - t0) * 1000), "model": cfg.model,
                "message": f"Échec inattendu du test ({type(exc).__name__})."}
    ms = int((time.perf_counter() - t0) * 1000)
    return {"ok": True, "latency_ms": ms, "model": cfg.model, "message": f"Connexion réussie au modèle « {cfg.model} » en {ms} ms."}


@router.post("/sparql/test")
def test_sparql(body: Optional[dict[str, Any]] = Body(default=None)) -> Any:
    """Requête ``ASK {}`` sur l'endpoint enregistré (ou sur ``{url, auth}`` fourni, non enregistré)."""
    s = store.load()
    ep = _patch_sparql(s.sparql_endpoint, {k: v for k, v in (body or {}).items() if k in ("url", "auth")})
    if not ep.url:
        return {"ok": False, "latency_ms": 0, "message": "Aucune URL d'endpoint SPARQL renseignée."}
    headers = {"Accept": "application/sparql-results+json"}
    auth = None
    if ep.auth and ep.auth.type == "basic":
        auth = (ep.auth.username or "", ep.auth.secret or "")
    elif ep.auth and ep.auth.type == "bearer" and ep.auth.secret:
        headers["Authorization"] = "Bearer " + ep.auth.secret
    t0 = time.perf_counter()
    try:
        r = netguard.post(ep.url, data={"query": "ASK {}"}, headers=headers, auth=auth, timeout=TEST_TIMEOUT)
    except netguard.NetGuardError as exc:
        return {"ok": False, "latency_ms": 0, "message": str(exc)}
    except httpx.TimeoutException:
        return {"ok": False, "latency_ms": int(TEST_TIMEOUT * 1000), "message": f"Délai dépassé ({TEST_TIMEOUT:.0f} s) en attendant l'endpoint SPARQL."}
    except httpx.HTTPError as exc:
        return {"ok": False, "latency_ms": int((time.perf_counter() - t0) * 1000), "message": f"Connexion impossible à l'endpoint SPARQL ({type(exc).__name__})."}
    ms = int((time.perf_counter() - t0) * 1000)
    if r.status_code in (401, 403):
        return {"ok": False, "latency_ms": ms, "message": f"Authentification refusée par l'endpoint (HTTP {r.status_code})."}
    if r.status_code >= 400:
        return {"ok": False, "latency_ms": ms, "message": f"L'endpoint a répondu HTTP {r.status_code}."}
    return {"ok": True, "latency_ms": ms, "message": f"Endpoint SPARQL joignable (HTTP {r.status_code}) en {ms} ms."}


# ---- endpoints SPARQL multiples (L15) ------------------------------------------------------------

def _patch_endpoint(cur: Optional[EndpointConfig], patch: dict[str, Any], taken: set[str]) -> EndpointConfig:
    d = cur.model_dump() if cur else {"id": "", "name": "", "url": ""}
    for f in ("name", "url", "auth", "username", "default_graph", "timeout_s"):
        if f in patch:
            d[f] = patch[f]
    if cur is None:
        d["id"] = patch.get("id") or store.slug_id(str(patch.get("name") or "endpoint"), taken)
        if d["id"] in taken:
            raise HTTPException(status_code=409, detail=f"Un endpoint « {d['id']} » existe déjà.")
    d["secret"] = _secret_patch(cur.secret if cur else None, patch, "secret")
    if d.get("auth") == "none":
        d["secret"], d["username"] = None, None
    d["secret_unreadable"] = bool(cur and cur.secret_unreadable and d["secret"] == cur.secret)
    if isinstance(d.get("default_graph"), str):
        d["default_graph"] = d["default_graph"].strip() or None
    try:
        return EndpointConfig.model_validate(d)
    except ValidationError as exc:
        raise _invalid(exc) from None


_EP_RO = ("has_secret", "secret_unreadable")


@router.get("/endpoints")
def list_endpoints() -> Any:
    s = store.load()
    return {"endpoints": [e.public() for e in s.sparql_endpoints], "active_endpoint_id": s.active_endpoint_id}


@router.post("/endpoints", status_code=201)
def add_endpoint(body: dict[str, Any] = Body(...)) -> Any:
    s = store.load()
    e = _patch_endpoint(None, {k: v for k, v in body.items() if k not in _EP_RO}, {x.id for x in s.sparql_endpoints})
    s.sparql_endpoints.append(e)
    if s.active_endpoint_id is None:
        s.active_endpoint_id = e.id
    store.save(s)
    return e.public()


@router.put("/endpoints/active")
def set_active_endpoint(body: dict[str, Any] = Body(...)) -> Any:
    s = store.load()
    eid = body.get("id")
    if eid is not None and s.endpoint(eid) is None:
        raise HTTPException(status_code=404, detail=f"Endpoint « {eid} » introuvable.")
    s.active_endpoint_id = eid
    store.save(s)
    return {"active_endpoint_id": eid}


@router.put("/endpoints/{eid}")
def update_endpoint(eid: str, body: dict[str, Any] = Body(...)) -> Any:
    s = store.load()
    cur = s.endpoint(eid)
    if cur is None:
        raise HTTPException(status_code=404, detail=f"Endpoint « {eid} » introuvable.")
    new = _patch_endpoint(cur, {k: v for k, v in body.items() if k not in _EP_RO and k != "id"}, {x.id for x in s.sparql_endpoints})
    s.sparql_endpoints = [new if x.id == eid else x for x in s.sparql_endpoints]
    store.save(s)
    return new.public()


@router.delete("/endpoints/{eid}")
def delete_endpoint(eid: str) -> Any:
    s = store.load()
    if s.endpoint(eid) is None:
        raise HTTPException(status_code=404, detail=f"Endpoint « {eid} » introuvable.")
    s.sparql_endpoints = [x for x in s.sparql_endpoints if x.id != eid]
    if s.active_endpoint_id == eid:
        s.active_endpoint_id = s.sparql_endpoints[0].id if s.sparql_endpoints else None
    if not s.sparql_endpoints:
        s.sparql_endpoint = SparqlEndpoint()  # évite la re-migration de l'ancien champ
    store.save(s)
    return {"deleted": eid, "active_endpoint_id": s.active_endpoint_id}


@router.post("/endpoints/{eid}/test")
def test_endpoint(eid: str, body: Optional[dict[str, Any]] = Body(default=None)) -> Any:
    """`ASK {}` sur l'endpoint ; le corps optionnel (url, auth, secret, username…) teste sans enregistrer."""
    from ..queries import endpoint as ep_mod
    s = store.load()
    cur = s.endpoint(eid)
    if cur is None:
        raise HTTPException(status_code=404, detail=f"Endpoint « {eid} » introuvable.")
    patch = {k: v for k, v in (body or {}).items() if k in ("url", "auth", "username", "secret", "default_graph", "timeout_s")}
    return ep_mod.ping(_patch_endpoint(cur, patch, set()))
