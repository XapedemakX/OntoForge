"""Requêtage interactif façon Sparnatural (L15, CONTRACTS §6) : suggestions, génération, exécution, requêtes sauvegardées."""
from __future__ import annotations

import re
from typing import Any, Callable, Literal, Optional, Union

from fastapi import APIRouter, Body, HTTPException, Query
from pydantic import BaseModel, Field, ValidationError

from .. import localize
from ..core.onto_model import RDFS, local_name
from ..queries import builder, endpoint as ep_mod, options as opt_mod, saved
from ..localstore import runner as local_runner, store as local_store
from ..queries.builder import GuidedError, GuidedQuery
from ..settings import store as settings_store
from ..settings.models import EndpointConfig
from ._common import check_target, dump, load_project

router = APIRouter(prefix="/api/projects/{pid}", tags=["query-builder"])
_NAMEISH = re.compile(r"(name|label|title|designation|libelle|nom)", re.I)


class BuildRequest(BaseModel):
    guided: GuidedQuery
    target: Optional[str] = None


class NLRequest(BaseModel):
    question: str
    provider_id: Optional[str] = None
    lang: Optional[str] = None
    target: Optional[str] = None


class InlineEndpoint(BaseModel):
    """Endpoint temporaire (L17) : fourni en ligne, jamais enregistré ni journalisé ; le secret reste en mémoire le temps de l'appel."""
    url: str
    auth: str = "none"
    username: Optional[str] = None
    secret: Optional[str] = None
    default_graph: Optional[str] = None
    timeout_s: float = 30.0


class LocalEndpoint(BaseModel):
    """Triplestore local du projet (L19) : `endpoint: {kind: "local"}`. Lecture seule, sans réseau, délai et lignes plafonnés."""
    kind: Literal["local"]
    timeout_s: Optional[float] = Field(None, ge=1, le=120)


class RunRequest(BaseModel):
    guided: Optional[GuidedQuery] = None
    sparql: Optional[str] = None
    endpoint_id: Optional[str] = None
    endpoint: Optional[Union[LocalEndpoint, InlineEndpoint]] = None
    limit: int = 100


class ValuesRequest(BaseModel):
    class_: Optional[str] = Field(None, alias="class")
    property: Optional[str] = None
    q: str = ""
    endpoint_id: Optional[str] = None
    endpoint: Optional[Union[LocalEndpoint, InlineEndpoint]] = None
    model_config = {"populate_by_name": True}


def _lang(lang: Optional[str]) -> str:
    return lang if lang in ("fr", "en") else settings_store.load().language.labels


def _endpoint(eid: Optional[str], inline: Optional[InlineEndpoint] = None):
    if inline is not None:
        try:
            return EndpointConfig(id="temporaire", name="Temporaire", url=inline.url, auth=inline.auth,  # type: ignore[arg-type]
                                  username=inline.username, secret=inline.secret or None,
                                  default_graph=inline.default_graph or None, timeout_s=inline.timeout_s)
        except ValidationError as exc:
            raise HTTPException(status_code=422, detail="Endpoint temporaire invalide — " + "; ".join(
                str(e["msg"]).removeprefix("Value error, ") for e in exc.errors()[:3])) from None
    s = settings_store.load()
    ep = s.endpoint(eid) if eid else s.active_endpoint()
    if ep is None:
        raise HTTPException(status_code=404 if eid else 409,
                            detail=f"Endpoint « {eid} » introuvable." if eid else
                            "Aucun endpoint SPARQL actif : configurez-en un dans les paramètres.")
    return ep


def _ep_error(exc: ep_mod.EndpointError) -> HTTPException:
    return HTTPException(status_code=exc.status, detail=str(exc))


def _executor(p: Any, eid: Optional[str], inline: Optional[Union[LocalEndpoint, InlineEndpoint]]) -> tuple[str, Callable[[str, int], ep_mod.QueryResult]]:
    """(identifiant d'endpoint, fonction (sparql, limite) -> résultat) : triplestore local, endpoint temporaire ou enregistré."""
    if isinstance(inline, LocalEndpoint):
        return "local", lambda q, n: local_runner.run_local(p, q, n, inline.timeout_s)
    ep = _endpoint(eid, inline)
    return ep.id, lambda q, n: ep_mod.run_select(ep, q, n)


@router.get("/query/suggest")
def suggest(pid: str, class_: Optional[str] = Query(None, alias="class"), property: Optional[str] = None,
            from_: Optional[str] = Query(None, alias="from"), inverse: bool = False, lang: Optional[str] = None) -> Any:
    p = load_project(pid)
    sg = builder.Suggester(p.onto, p.shapes, _lang(lang))
    if class_:
        try:
            res = sg.for_class(class_)
        except KeyError:
            raise HTTPException(status_code=404, detail=f"Classe « {class_} » inconnue de l'ontologie.") from None
        cache: dict[str, int] = {}
        for e in [*res["outgoing"], *res["incoming"]]:  # L17 : nombre d'individus connus de chaque cible
            for tg in e["targets"]:
                tg["known"] = cache.setdefault(tg["iri"], opt_mod.known_count(p.onto, tg["iri"]))
        return res
    if property:
        if property not in p.onto.object_properties:
            raise HTTPException(status_code=404, detail=f"Propriété objet « {property} » inconnue de l'ontologie.")
        return sg.target_classes(property, from_, inverse=inverse)
    # sans paramètre : classes racines possibles
    return {"classes": [{"iri": c, "label": sg.label(c), "parents": p.onto.classes[c].sub_class_of, "known": opt_mod.known_count(p.onto, c)}
                        for c in sorted(p.onto.classes, key=lambda x: sg.label(x).lower())]}


@router.post("/query/build")
def build(pid: str, body: BuildRequest) -> Any:
    from .analysis import run_analysis
    p = load_project(pid)
    target = check_target(body.target or p.target)
    try:
        pg = run_analysis(p, target)
        out = dump(builder.build_all(body.guided, p.onto, pg, p.onto.meta.prefixes))
        lg = localize.ui_lang()
        for k in ("notes", "warnings"):
            if k in out:
                out[k] = localize.tr_deep(out[k], lg)
        return out
    except GuidedError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None


@router.post("/query/run")
def run(pid: str, body: RunRequest) -> Any:
    p = load_project(pid)
    if (body.guided is None) == (body.sparql is None):
        raise HTTPException(status_code=422, detail="Fournir exactement l'un de « guided » ou « sparql ».")
    ep_id, execute = _executor(p, body.endpoint_id, body.endpoint)
    edges: list[tuple[str, str, str]] = []
    try:
        if body.guided is not None:
            sparql = builder.to_sparql(body.guided, p.onto, p.onto.meta.prefixes)
            edges = [((s.to_var, s.from_var) if s.inverse else (s.from_var, s.to_var)) + (s.property_iri,)
                     for s in body.guided.steps if not s.negated]
            limit = min(body.limit, body.guided.limit or body.limit)
        else:
            sparql, limit = body.sparql or "", body.limit
        res = execute(sparql, limit)
    except GuidedError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    except ep_mod.EndpointError as exc:
        raise _ep_error(exc) from None
    out = res.model_dump(mode="json")
    out["graph"] = ep_mod.graph_preview(res, edges)
    out["endpoint_id"] = ep_id
    return out


@router.get("/query/values")
def values(pid: str, class_: Optional[str] = Query(None, alias="class"), property: Optional[str] = None,
           q: str = "", endpoint_id: Optional[str] = None) -> Any:
    """Autocomplétion : valeurs (ou libellés d'entités) de `property` sur les instances de `class`, 20 maximum."""
    return _values(pid, class_, property, q, _endpoint_lazy(pid, endpoint_id, None))


@router.post("/query/values")
def values_post(pid: str, body: ValuesRequest) -> Any:
    """Idem GET, avec un endpoint temporaire en ligne (le secret ne transite pas par l'URL)."""
    return _values(pid, body.class_, body.property, body.q, _endpoint_lazy(pid, body.endpoint_id, body.endpoint))


def _endpoint_lazy(pid: str, eid: Optional[str], inline: Optional[Union[LocalEndpoint, InlineEndpoint]]):
    return lambda: _executor(load_project(pid), eid, inline)[1]


def _values(pid: str, class_: Optional[str], property: Optional[str], q: str, get_exec) -> Any:
    p = load_project(pid)
    if not class_ and not property:
        raise HTTPException(status_code=422, detail="Indiquer « class » et/ou « property ».")
    o = p.onto
    t = builder._Terms(builder.default_prefixes(o, o.meta.prefixes))
    needle = t.string(q.strip().lower())
    typing = f"?s a {t.iri(class_)} ." if class_ else ""
    label_props = [RDFS + "label", builder.SKOS_PREF] + [
        i for i, d in o.datatype_properties.items() if _NAMEISH.search(local_name(i)) and (not d.range or d.range[0].endswith(("string", "langString")))]
    lp = " ".join(t.iri(i) for i in label_props)
    if property and property in o.datatype_properties:
        body = f"{typing} ?s {t.iri(property)} ?value ."
        flt = f"FILTER(CONTAINS(LCASE(STR(?value)), {needle}))" if q.strip() else ""
        sparql = f"SELECT DISTINCT ?value WHERE {{ {body} {flt} }} ORDER BY ?value"
    else:
        link = f"?s {t.iri(property)} ?value ." if property else "BIND(?s AS ?value)"
        flt = f"FILTER(CONTAINS(LCASE(STR(?label)), {needle}))" if q.strip() else ""
        sparql = (f"SELECT DISTINCT ?value ?label WHERE {{ {typing} {link} VALUES ?lp {{ {lp} }} "
                  f"?value ?lp ?label . {flt} }} ORDER BY ?label")
    try:
        res = get_exec()(t.header() + sparql, 20)
    except ep_mod.EndpointError as exc:
        raise _ep_error(exc) from None
    items = []
    for r in res.rows:
        v = r.get("value") or {}
        lab = r.get("label") or {}
        items.append({"value": v.get("value"), "label": lab.get("value") or v.get("value"), "is_iri": v.get("type") == "uri",
                      "datatype": v.get("datatype"), "lang": v.get("xml:lang") or lab.get("xml:lang")})
    return {"values": items, "truncated": res.truncated, "sparql": sparql}


@router.get("/query/options")
def options(pid: str, class_: Optional[str] = Query(None, alias="class"), property: Optional[str] = None,
            q: str = "", lang: Optional[str] = None, local: bool = False) -> Any:
    """Valeurs possibles connues de l'ontologie, SANS endpoint : individus (classes énumérées ou peuplées), sh:in, DataOneOf, enum PG.
    `local=true` (L19) complète avec les valeurs présentes dans le triplestore local du projet (source `local`) ; `local: {triples, added}` ou `{error}`."""
    from .analysis import run_analysis
    p = load_project(pid)
    if not class_ and not property:
        raise HTTPException(status_code=422, detail="Indiquer « class » et/ou « property ».")
    if class_ and class_ not in p.onto.classes:
        raise HTTPException(status_code=404, detail=f"Classe « {class_} » inconnue de l'ontologie.")
    pg = None
    if property in p.onto.datatype_properties:
        try:
            pg = run_analysis(p, check_target(p.target))
        except Exception:  # noqa: BLE001 - l'enum du modèle est un complément facultatif
            pg = None
    res = opt_mod.options(p.onto, p.shapes, pg, class_, property, q, _lang(lang))
    if local:
        res["local"] = _local_options(p, res, class_, property, q)
    return res


def _local_options(p: Any, res: dict[str, Any], class_: Optional[str], property: Optional[str], q: str) -> dict[str, Any]:
    """Ajoute à `res["values"]` les valeurs trouvées dans le triplestore local (sans doublon) ; ne lève jamais."""
    try:
        got = _values(p.id, class_, property, q, lambda: (lambda s, n: local_runner.run_local(p, s, n)))
    except HTTPException as exc:
        return {"error": str(exc.detail)}
    have = {v["value"] for v in res["values"]}
    added = 0
    for v in got["values"]:
        if v["value"] and v["value"] not in have and len(res["values"]) < opt_mod.MAX_VALUES:
            res["values"].append({"value": v["value"], "label": v["label"], "is_iri": v["is_iri"], "source": "local",
                                  **({"lang": v["lang"]} if v.get("lang") else {})})
            have.add(v["value"])
            added += 1
    res["known_count"] += added
    return {"triples": local_store.stats(p.id, p)["triples"], "added": added}


@router.post("/query/endpoint-test")
def endpoint_test(pid: str, body: InlineEndpoint) -> Any:
    """`ASK {}` sur un endpoint temporaire (sans l'enregistrer)."""
    load_project(pid)
    return ep_mod.ping(_endpoint(None, body))


# ---- requêtes sauvegardées ---------------------------------------------------------------------

def _model(body: dict[str, Any]) -> saved.SavedQuery:
    try:
        return saved.SavedQuery.model_validate({k: v for k, v in body.items() if k in ("name", "description", "guided", "sparql")})
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail="Requête invalide — " + "; ".join(
            f"{'.'.join(str(x) for x in e['loc'])} : {e['msg']}" for e in exc.errors()[:4])) from None


@router.get("/queries/saved")
def saved_list(pid: str) -> Any:
    load_project(pid)
    return dump(saved.list_saved(pid))


@router.post("/queries/saved", status_code=201)
def saved_create(pid: str, body: dict[str, Any] = Body(...)) -> Any:
    load_project(pid)
    return dump(saved.create(pid, _model(body)))


@router.get("/queries/saved/{qid}")
def saved_get(pid: str, qid: str) -> Any:
    load_project(pid)
    try:
        return dump(saved.get(pid, qid))
    except saved.SavedQueryNotFound:
        raise HTTPException(status_code=404, detail="Requête sauvegardée introuvable.") from None


@router.put("/queries/saved/{qid}")
def saved_update(pid: str, qid: str, body: dict[str, Any] = Body(...)) -> Any:
    load_project(pid)
    try:
        return dump(saved.update(pid, qid, _model(body)))
    except saved.SavedQueryNotFound:
        raise HTTPException(status_code=404, detail="Requête sauvegardée introuvable.") from None


@router.delete("/queries/saved/{qid}")
def saved_delete(pid: str, qid: str) -> Any:
    load_project(pid)
    try:
        saved.delete(pid, qid)
    except saved.SavedQueryNotFound:
        raise HTTPException(status_code=404, detail="Requête sauvegardée introuvable.") from None
    return {"deleted": qid}


@router.get("/queries/competency/guided")
def competency_guided(pid: str, target: Optional[str] = None) -> Any:
    """Questions de compétence existantes, converties en requêtes guidées quand c'est possible."""
    from ..queries.competency import competency_questions
    from .analysis import run_analysis
    p = load_project(pid)
    pg = run_analysis(p, check_target(target or p.target))
    out = []
    lang = localize.ui_lang()
    for cq in competency_questions(pg, p.onto, lang):
        g, why = builder.guided_from_sparql(cq.sparql, p.onto)
        out.append({"id": cq.id, "question": cq.question, "pattern": cq.pattern, "sparql": cq.sparql,
                    "guided": dump(g) if g else None, "reason": localize.tr(why, lang)})
    return out


@router.post("/query/nl")
def natural_language(pid: str, body: NLRequest) -> Any:
    """Question en langage naturel -> requête guidée modifiable (LLM + validation stricte, repli déterministe)."""
    from ..assistant.providers import LLMError, get_provider
    from ..queries import nl
    from .analysis import run_analysis
    p = load_project(pid)
    if not body.question.strip():
        raise HTTPException(status_code=422, detail="La question est vide.")
    try:
        prov = get_provider(body.provider_id) if body.provider_id else get_provider()
    except LLMError as exc:
        if body.provider_id:
            raise HTTPException(status_code=404, detail=str(exc)) from None
        prov = None  # aucun fournisseur par défaut exploitable : repli déterministe
    msg_lang = body.lang if body.lang in ("fr", "en") else localize.ui_lang()  # langue de l'explication et des notes
    res = nl.interpret(body.question.strip(), p.onto, p.shapes, prov, _lang(body.lang), msg_lang)
    try:
        gq = GuidedQuery.model_validate(res["guided"])
        built = builder.build_all(gq, p.onto, run_analysis(p, check_target(body.target or p.target)), p.onto.meta.prefixes)
        res.update(sparql=built.sparql, cypher=built.cypher, curiosity=built.curiosity, notes=built.notes, lossy=built.lossy,
                   warnings=built.warnings)
    except GuidedError as exc:
        res.update(sparql=None, cypher=None, curiosity=None, notes=[f"Génération impossible : {exc}"], lossy=True, warnings=[])
    for k in ("explanation", "notes", "warnings"):
        if k in res:
            res[k] = localize.tr_deep(res[k], msg_lang)
    return dump(res)
