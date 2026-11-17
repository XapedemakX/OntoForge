"""Conformité, SHACL, analyse / arbitrage, génération, requêtes (CONTRACTS.md §2)."""
from __future__ import annotations

import io
import zipfile
from typing import Any, Optional

from starlette.concurrency import run_in_threadpool
from fastapi import APIRouter, Body, File, HTTPException, Query, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel

from .. import localize, standards
from ..core.lang import LABEL_LANG
from ..localize import gen
from ..core.pg_model import PGModel
from ..core.project import GenerationRecord, Project
from ..mapping import notes as dec_notes
from ..projects import generations as gen_log, store
from ..shacl.validate import ShaclBusyError
from ._common import check_target, dump, load_project, not_available, optional_service, parse_error, service

router = APIRouter(prefix="/api/projects/{pid}", tags=["analysis"])

DATA_FORMATS = {".ttl": "turtle", ".owl": "xml", ".rdf": "xml", ".xml": "xml", ".jsonld": "json-ld",
                ".json": "json-ld", ".nt": "nt", ".n3": "n3", ".trig": "trig"}




class MergeRequest(BaseModel):
    merge: bool = True
    dry_run: bool = False  # aperçu : renvoie les shapes générées sans enregistrer le projet


class TranslateRequest(BaseModel):
    sparql: str


# ---- helpers ---------------------------------------------------------------------------------

def _scope(p: Project, perimeter: Optional[str]):
    """Ontologie / shapes / constats d'information du périmètre demandé (L9) ; 404 si inconnu."""
    from ..editing import perimeter as per_mod
    try:
        return per_mod.scope(p, perimeter)
    except per_mod.PerimeterNotFound:
        raise HTTPException(status_code=404, detail=f"Périmètre « {perimeter} » introuvable") from None


def run_analysis(p: Project, target: str, perimeter: Optional[str] = None) -> PGModel:
    analyze = service("mapping.engine", "analyze")
    onto, shapes, notes = _scope(p, perimeter)
    token = LABEL_LANG.set(localize.labels_lang())  # libellés lus par les règles : langue des libellés des paramètres
    try:
        pg = analyze(onto, shapes, target, dict(p.decisions.get(target, {})))
    finally:
        LABEL_LANG.reset(token)
    if notes:
        pg.findings.extend(notes)
    pg.decision_notes = dec_notes.notes_for(p, target)  # L47 : qui, quand, pourquoi (vide pour un ancien projet)
    pg.meta.target_versions = standards.for_project(p)  # L31 : en-têtes et rapport affichent les versions utilisées
    for nt in pg.node_types.values():  # D-L9-02 : icône de la première classe source qui en a une
        nt.icon = next((p.view.icons[c] for c in nt.source if c in p.view.icons), None)
    return pg


def _ui(pg: PGModel) -> PGModel:
    """Traduit les textes générés quand ``settings.language.ui`` vaut ``en`` (uniquement pour les réponses d'API affichées)."""
    return localize.localize_pg(pg, localize.ui_lang())


def _target_or_default(p: Project, target: Optional[str]) -> str:
    return check_target(target or p.target)


def _as_files(result: Any) -> dict[str, str]:
    """Accepte dict[nom, contenu] (CONTRACTS) ou list[GeneratedFile{path, content}] (D-017)."""
    if isinstance(result, dict):
        return {str(k): v if isinstance(v, str) else str(v) for k, v in result.items()}
    out: dict[str, str] = {}
    for f in result or []:
        path = getattr(f, "path", None) or (f.get("path") if isinstance(f, dict) else None)
        content = getattr(f, "content", None) if not isinstance(f, dict) else f.get("content")
        if path:
            out[path] = content or ""
    return out


def _gen_lang(lang: Optional[str]) -> str:
    """Langue de génération : ``lang`` demandée (fr/en), sinon langue de l'interface ; 422 si la valeur est inconnue."""
    if lang and gen.normalize(lang) is None:
        raise HTTPException(status_code=422, detail=f"Langue de génération inconnue « {lang} » (fr ou en) / unknown generation language \"{lang}\" (fr or en)")
    return gen.resolve(lang)


def generate_files(p: Project, target: str, perimeter: Optional[str] = None, lang: Optional[str] = None) -> tuple[dict[str, str], list[str]]:
    files, missing, _ = _generate(p, target, perimeter, lang)
    return files, missing


def _generate(p: Project, target: str, perimeter: Optional[str] = None, lang: Optional[str] = None) -> tuple[dict[str, str], list[str], PGModel]:
    gl = _gen_lang(lang)
    pg = run_analysis(p, target, perimeter)
    onto = _scope(p, perimeter)[0]
    if gl == "en":  # constats, validations et descriptions générés par le moteur : traduits ; identifiants et libellés d'ontologie inchangés
        localize.localize_pg_for_export(pg, "en")
    files: dict[str, str] = {}
    missing: list[str] = []
    for mod in (f"targets.{target}", "targets.graphql", "targets.report"):
        fn = optional_service(mod, "generate")
        if fn is None:
            missing.append(mod)
            continue
        with gen.using_lang(gl):
            files.update(_as_files(fn(pg, onto)))
    if len(missing) == 3:
        raise not_available(f"targets.{target}")
    return files, missing, pg


# ---- conformité ------------------------------------------------------------------------------

@router.get("/conformance")
def conformance(pid: str) -> Any:
    p = load_project(pid)
    check = service("conformance.profiles", "check_conformance")
    return localize.localize_conformance(dump(check(p.onto, None)), localize.ui_lang())


class ReasonRequest(BaseModel):
    reasoner: str = "hermit"  # extensible : seul « hermit » existe aujourd'hui
    timeout: Optional[float] = None  # secondes ; défaut ONTOFORGE_HERMIT_TIMEOUT (30), plafond ONTOFORGE_HERMIT_MAX_TIMEOUT


@router.post("/reason")
def reason(pid: str, body: ReasonRequest = Body(default_factory=ReasonRequest)) -> Any:
    """Raisonnement OWL 2 DL (HermiT) : cohérence, classes insatisfiables, inférences, individus reclassés. 501 si Java/owlready2 manquent."""
    from ..conformance import hermit as hm
    if body.reasoner != "hermit":
        raise HTTPException(status_code=422, detail=f"Raisonneur inconnu « {body.reasoner} » : attendu hermit")
    p = load_project(pid)
    lang = localize.ui_lang()
    from ..io.rdf_export import model_to_graph
    try:
        return hm.run_hermit(model_to_graph(p.onto), timeout=body.timeout, lang=lang)
    except hm.HermitUnavailable as exc:
        raise HTTPException(status_code=501, detail=hm.unavailable_message(exc, lang)) from None
    except hm.HermitBusy as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from None


# ---- SHACL -----------------------------------------------------------------------------------

@router.post("/shacl/generate")
def shacl_generate(pid: str, body: MergeRequest = Body(default_factory=MergeRequest)) -> dict:
    p = load_project(pid)
    generate_shapes = service("shacl.owl_to_shacl", "generate_shapes")
    generated, notes = generate_shapes(p.onto)
    if body.dry_run:
        return {"project": dump(p), "generated": dump(generated), "notes": list(notes), "dry_run": True}
    if body.merge:
        merged = p.shapes.model_copy(deep=True)
        for k, v in generated.shapes.items():
            merged.shapes.setdefault(k, v)
        for k, v in generated.property_shapes.items():
            merged.property_shapes.setdefault(k, v)
        for k, v in generated.prefixes.items():
            merged.prefixes.setdefault(k, v)
        p.shapes = merged
    else:
        p.shapes = generated
    store.save(p)
    return {"project": dump(p), "notes": list(notes)}


@router.post("/shacl/validate")
async def shacl_validate(pid: str, file: UploadFile = File(...)) -> Any:
    p = load_project(pid)
    validate = service("shacl.validate", "validate")
    raw = await file.read()
    if not raw.strip():
        raise HTTPException(status_code=422, detail="Fichier de données vide")
    name = (file.filename or "").lower()
    fmt = next((f for ext, f in DATA_FORMATS.items() if name.endswith(ext)), None)
    try:
        report = await run_in_threadpool(validate, raw, p.shapes, p.onto, fmt)  # hors boucle d'événements : l'API reste réactive (SEC-05)
    except (HTTPException, ShaclBusyError):
        raise
    except Exception as exc:
        raise parse_error(f"les données « {file.filename or 'fichier'} »", exc) from None
    return dump(report)


# ---- analyse et arbitrage ----------------------------------------------------------------------

@router.post("/analyze", response_model=PGModel)
def analyze(pid: str, target: Optional[str] = Query(None), perimeter: Optional[str] = Query(None)) -> PGModel:
    p = load_project(pid)
    return _ui(run_analysis(p, _target_or_default(p, target), perimeter))


def _parse_decisions(body: dict[str, Any]) -> tuple[dict[str, Optional[str]], Optional[str], dict[str, str], str]:
    """Corps de `PUT /decisions/{target}` : ancien format plat `{id: option|null}` ou (L47) `{decisions, reason?, reasons?, via?}`.

    Un identifiant de constat n'est jamais « decisions » (il commence par une règle et une IRI) : pas d'ambiguïté."""
    extended = isinstance(body.get("decisions"), dict)
    changes = body["decisions"] if extended else body
    for fid, opt in changes.items():
        if not isinstance(fid, str) or not (opt is None or isinstance(opt, str)):
            raise HTTPException(status_code=422, detail="Décisions : attendu {identifiant de constat: identifiant d'option ou null}")
    if not extended:
        return changes, None, {}, "manual"
    reasons = body.get("reasons") or {}
    if not isinstance(reasons, dict) or any(not isinstance(k, str) for k in reasons):
        raise HTTPException(status_code=422, detail="Décisions : « reasons » doit être {identifiant de constat: raison}")
    via = body.get("via", "manual")
    if via not in dec_notes.VIAS:
        raise HTTPException(status_code=422, detail=f"Décisions : « via » inconnu (attendu {', '.join(dec_notes.VIAS)})")
    return changes, body.get("reason"), reasons, via


def _apply(p: Project, target: str, changes: dict[str, Optional[str]], *, reason: Any = None, reasons: Optional[dict] = None, via: str = "manual") -> None:
    try:
        dec_notes.apply_changes(p, target, changes, reason=reason, reasons=reasons, via=via, now=store.now_iso())
    except dec_notes.ReasonTooLong:
        raise HTTPException(status_code=422, detail=f"La raison d'une décision tient en une ligne de {dec_notes.MAX_REASON} caractères au plus.") from None
    except ValueError:
        raise HTTPException(status_code=422, detail="La raison d'une décision doit être un texte.") from None


@router.put("/decisions/{target}", response_model=PGModel)
def put_decisions(pid: str, target: str, body: dict[str, Any] = Body(...)) -> PGModel:
    """Enregistre des décisions. Corps : `{id de constat: option | null}` (ancien format, sans raison) ou, depuis L47,
    `{decisions: {…}, reason?: str, reasons?: {id: str}, via?: manual|recommended|rule|branch}` ; la raison tient en une ligne."""
    check_target(target)
    changes, reason, reasons, via = _parse_decisions(body)
    p = load_project(pid)
    _apply(p, target, changes, reason=reason, reasons=reasons, via=via)
    pg = run_analysis(p, target)  # 501 avant toute écriture si le moteur manque
    store.save(p)
    return _ui(pg)


class BranchRequest(BaseModel):
    root: str  # IRI de la racine de la hiérarchie
    rule: Optional[str] = None  # restreint à une règle (C02, C03, C04, C10) ; obligatoire avec `option`
    option: Optional[str] = None  # option imposée à toute la branche ; absente = recommandation de chaque constat
    reason: Optional[str] = None
    overwrite: bool = False  # avec `option` : remplacer aussi les décisions d'un autre compte (ou sans auteur connu) ; sinon elles sont ignorées


@router.post("/decisions/{target}/branch")
def decide_branch(pid: str, target: str, body: BranchRequest) -> dict:
    """Arbitrage par racine de hiérarchie (L47, P-02) : applique une décision à tous les constats d'une branche.

    Avec `option` : tous les constats de `rule` de la branche qui la proposent ; une décision déjà prise par un autre compte (ou sans auteur
    connu, ancien format) n'est remplacée qu'avec `overwrite: true` (geste explicite « Imposer ») ; les autres constats vont dans `skipped`.
    Sans `option` : la recommandation de chaque constat non décidé ; les constats « lost » ne sont jamais acceptés ainsi (D-L14-02)."""
    check_target(target)
    if body.option and not body.rule:
        raise HTTPException(status_code=422, detail="Une option imposée à une branche exige la règle concernée (« rule »).")
    p = load_project(pid)
    pg = run_analysis(p, target)
    branch = [f for f in pg.findings if f.root == body.root and (not body.rule or f.rule == body.rule) and f.options]
    if not branch:
        raise HTTPException(status_code=404, detail="Aucun constat d'héritage pour cette racine.")
    changes: dict[str, Optional[str]] = {}
    skipped: list[str] = []
    for f in branch:
        if body.option:
            note = pg.decision_notes.get(f.id)
            foreign = bool(f.chosen) and f.chosen != body.option and (note is None or note.by != dec_notes.current_user())
            if body.option in {o.id for o in f.options} and not (foreign and not body.overwrite):
                changes[f.id] = body.option
            else:
                skipped.append(f.id)
        elif f.severity != "lost" and not f.chosen and f.recommended:
            changes[f.id] = f.recommended
        else:
            skipped.append(f.id)
    if changes:
        _apply(p, target, changes, reason=body.reason, via="branch")
        store.save(p)
        pg = run_analysis(p, target)
    return {"model": dump(_ui(pg)), "applied": sorted(changes), "skipped": sorted(skipped)}


@router.post("/decisions/{target}/accept-recommended", response_model=PGModel)
def accept_recommended(pid: str, target: str, include_lost: bool = Query(False)) -> PGModel:
    """Accepte les recommandations ; les constats « lost » restent à arbitrer par l'humain sauf include_lost=true."""
    check_target(target)
    p = load_project(pid)
    pg = run_analysis(p, target)
    dec = dict(p.decisions.get(target, {}))
    changes: dict[str, Optional[str]] = {}
    for f in pg.findings:
        if f.severity in (("review", "lost") if include_lost else ("review",)) and not f.chosen and f.id not in dec and f.recommended:
            changes[f.id] = f.recommended
    if not changes:
        return _ui(pg)
    _apply(p, target, changes, via="recommended")
    store.save(p)
    return _ui(run_analysis(p, target))


# ---- génération ------------------------------------------------------------------------------

@router.get("/generate/{target}")
def generate(pid: str, target: str, perimeter: Optional[str] = Query(None),
             lang: Optional[str] = Query(None, description="Langue des fichiers générés : fr ou en (défaut : langue de l'interface)")) -> dict:
    check_target(target)
    p = load_project(pid)
    files, missing, pg = _generate(p, target, perimeter, lang)
    summary = {"auto": 0, "review": 0, "lost": 0, "pending": 0}
    for f in pg.findings:
        if f.severity in summary:
            summary[f.severity] += 1
        if f.severity in ("review", "lost") and not f.chosen:
            summary["pending"] += 1
    # L41 (L40-02) : l'historique va dans un fichier annexe, sous verrou ; project.json n'est jamais réécrit par une route de lecture
    gen_log.append(p, GenerationRecord(target=target, perimeter=perimeter, at=store.now_iso(), files=sorted(files),
                                          findings_summary=summary, project_updated_at=p.updated_at))
    return {"files": files, "missing": missing}


@router.get("/justification/{target}")
def justification(pid: str, target: str, format: str = Query("html", description="html (autonome, sans script) ou md"),
                  lang: Optional[str] = Query(None, description="Langue du dossier : fr ou en (défaut : langue de l'interface)")) -> Response:
    """Dossier de justification de la transposition (L47, P-05) : modèle retenu, perdu, compensé, décisions (qui, quand, pourquoi),
    recommandations non suivies. Lecture seule : accessible au lecteur ; n'écrit ni projet ni historique de génération."""
    from ..targets import justification as just
    check_target(target)
    if format not in ("html", "md"):
        raise HTTPException(status_code=422, detail="Format inconnu : attendu html ou md")
    gl = _gen_lang(lang)
    p = load_project(pid)
    pg = run_analysis(p, target)
    onto = p.onto
    if gl == "en":
        localize.localize_pg_for_export(pg, "en")
    text = just.generate(pg, onto, project_name=p.name, fmt=format, generated_at=store.now_iso(), lang=gl)
    headers = {"Content-Disposition": f'attachment; filename="justification-{p.id}-{target}.{format}"', "X-Content-Type-Options": "nosniff"}
    if format == "html":
        headers["Content-Security-Policy"] = just.CSP
        return Response(content=text, media_type="text/html; charset=utf-8", headers=headers)
    return Response(content=text, media_type="text/markdown; charset=utf-8", headers=headers)


@router.get("/generations")
def generations(pid: str) -> list[dict]:
    """Historique des générations du projet, la plus récente d'abord."""
    p = load_project(pid)
    return list(reversed(gen_log.history(p)))


@router.get("/generate/{target}/zip")
def generate_zip(pid: str, target: str, perimeter: Optional[str] = Query(None),
                 lang: Optional[str] = Query(None, description="Langue des fichiers générés : fr ou en (défaut : langue de l'interface)")) -> Response:
    check_target(target)
    p = load_project(pid)
    files, _ = generate_files(p, target, perimeter, lang)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, content in sorted(files.items()):
            zf.writestr(f"{p.id}-{target}/{name}", content)
    return Response(content=buf.getvalue(), media_type="application/zip",
                    headers={"Content-Disposition": f'attachment; filename="{p.id}-{target}.zip"'})


# ---- requêtes --------------------------------------------------------------------------------

@router.post("/queries/translate")
def translate(pid: str, body: TranslateRequest, target: Optional[str] = Query(None)) -> Any:
    p = load_project(pid)
    fn = service("queries.translate", "translate")
    pg = run_analysis(p, _target_or_default(p, target))
    return dump(fn(body.sparql, pg, p.onto))


@router.get("/queries/competency")
def competency(pid: str, target: Optional[str] = Query(None)) -> Any:
    p = load_project(pid)
    fn = service("queries.competency", "competency_questions")
    pg = run_analysis(p, _target_or_default(p, target))
    lang = localize.ui_lang()
    return localize.tr_deep(dump(fn(pg, p.onto, lang)), lang)
