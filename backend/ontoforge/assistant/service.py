"""Assistant IA de conception d'ontologies (L6) : status, draft, propose_shapes, explain.

Les propositions ne sont jamais appliquées ici : le front les soumet à revue humaine.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Optional

from fastapi import HTTPException

from ontoforge.core.onto_model import OntoModel, local_name
from ontoforge.core.shapes_model import NodeShape, PropertyShape, ShapesModel, Path
from ontoforge.shacl.owl_to_shacl import generate_shapes

from ..settings.models import DEFAULT_MODELS
from .analyzers import analyze_csv, analyze_sql
from .convert import extract_json, normalize_base, to_onto
from .providers import LLMError, get_provider
from .texts import fallback_explain

log = logging.getLogger("ontoforge.assistant")

DRAFT_SYSTEM = """[TASK:draft]
Tu es un ontologue expert (OWL 2 DL, SKOS, schema.org, PROV-O) qui aide à concevoir rapidement une ontologie utilisable ensuite
pour générer un modèle de graphe de propriétés (Curiosity, Neo4j). Méthode :
1. Déduis 5 à 10 questions de compétence de la description, et ne modélise que ce qui permet d'y répondre (pas de sur-modélisation).
2. Réutilise des vocabulaires connus quand c'est pertinent (skos:Concept, schema.org/Person, prov:Activity...) via exact_match / close_match (IRI complète).
3. Classes en PascalCase (singulier), propriétés en camelCase ; propriétés d'objet = verbes ou relations (ownedBy, hasEngine), propriétés de données = noms.
4. Libellés label_fr ET label_en pour chaque élément, comment court (une phrase).
5. Domaine et portée explicites ; "functional": true quand au plus une valeur ; "required": true pour une cardinalité minimale 1 ; "max"/"min" entiers sinon.
6. Clés naturelles : "key": [noms de propriétés de données] sur la classe (identifiant métier).
7. Hiérarchie : sous-classes seulement si le comportement ou les propriétés diffèrent ; déclare disjoint_with entre sœurs exclusives.
8. OWL 2 DL : types de données parmi string, integer, decimal, double, boolean, dateTime, anyURI ; PAS de xsd:date ni gYear (utilise dateTime / integer).
9. Les rôles (propriétaire, technicien) sont à signaler en warnings s'ils sont modélisés en sous-classes.
Réponds par un unique objet JSON de forme :
{"ontology":{"label_fr","label_en","comment"},
 "classes":[{"name","label_fr","label_en","comment","parent","disjoint_with":[],"key":[],"exact_match","close_match"}],
 "object_properties":[{"name","label_fr","label_en","domain","range","functional","required","min","max","inverse","characteristics":[]}],
 "datatype_properties":[{"name","label_fr","label_en","domain","range","functional","required"}],
 "explanation":"choix de modélisation en français, questions de compétence couvertes", "warnings":["points à arbitrer par l'humain"]}
Aucun texte hors du JSON."""

SHAPES_SYSTEM = """[TASK:shapes]
Tu es un expert SHACL. On te donne les propriétés candidates d'une ontologie. Propose uniquement des contraintes de valeur utiles et sûres :
pattern (regex), min_length, max_length, min_inclusive, max_inclusive, in (liste de valeurs). N'invente pas de contrainte douteuse ; ignore une propriété si rien n'est évident.
Réponds par un JSON : {"enrichments":[{"class":"<IRI>","property":"<IRI>","pattern":"..","min_length":0,"max_length":0,"min_inclusive":"..","max_inclusive":"..","in":[],"message_fr":".."}],"explanation":".."}"""

EXPLAIN_SYSTEM = """[TASK:explain]
Tu es un ontologue pédagogue. Explique à un utilisateur non expert, dans la langue indiquée par « LANGUAGE: » (français sinon) et en moins de 250 mots, un constat de transposition ontologie vers graphe de propriétés :
1) ce que dit l'ontologie et ce qui est perdu ou à risque ; 2) pourquoi ce n'est pas trivial pour la cible (Curiosity ou Neo4j) ; 3) les options et l'argument de la recommandation pour cette cible ;
4) un conseil concret. Reste factuel, sans inventer de fonctionnalité de la cible."""

CHAR_LIMIT = 40000


def _provider(provider_id: Optional[str] = None):
    try:
        return get_provider(provider_id) if provider_id else get_provider()
    except LLMError as exc:
        raise HTTPException(status_code=404 if provider_id else 503, detail=str(exc)) from None


def _assistant_lang() -> str:
    from ..settings import store
    return store.load(persist=False).language.assistant


def _default_base() -> Optional[str]:
    """IRI de base par défaut des paramètres (None si aucun fichier de paramètres)."""
    from ..settings import store
    return store.load(persist=False).defaults.base_iri if store.exists() else None


def status() -> dict[str, Any]:
    """Fournisseur par défaut (clés historiques provider/model/configured) + liste des fournisseurs disponibles."""
    from ..settings import store
    s = store.load(persist=False)
    en = s.language.ui == "en"
    listing = [{"id": c.id, "name": "Mock (demo)" if en and c.kind == "mock" and c.name == "Mock (démonstration)" else c.name, "kind": c.kind, "model": c.model or DEFAULT_MODELS[c.kind], "configured": c.configured,
                "default": c.id == s.default_provider_id} for c in s.llm_providers]
    try:
        p = get_provider()
    except LLMError as exc:
        return {"provider": "inconnu", "model": "", "configured": False, "detail": str(exc),
                "default_provider_id": s.default_provider_id, "providers": listing}
    return {"provider": p.name, "model": p.model, "configured": p.configured,
            "default_provider_id": s.default_provider_id, "providers": listing}



def _ask_json(p, system: str, user: str, max_tokens: int = 6000) -> dict[str, Any]:
    """Appelle le LLM et exige du JSON ; une relance maximum en cas de JSON invalide."""
    msgs = [{"role": "user", "content": user}]
    raw = p.complete(system, msgs, max_tokens)
    try:
        return extract_json(raw)
    except ValueError as exc:
        log.info("JSON invalide (%s), relance", exc)
        msgs += [{"role": "assistant", "content": raw[:6000]},
                 {"role": "user", "content": f"Ta réponse n'est pas un JSON valide ({exc}). Renvoie uniquement l'objet JSON complet, sans texte autour."}]
        raw = p.complete(system, msgs, max_tokens)
        try:
            return extract_json(raw)
        except ValueError as exc2:
            raise HTTPException(status_code=502, detail=f"L'assistant n'a pas produit de JSON exploitable après relance : {exc2}") from None


def draft(text: str, kind: str = "text", base_iri: Optional[str] = None, provider_id: Optional[str] = None,
          filename: Optional[str] = None) -> dict[str, Any]:
    text = (text or "").strip()
    if not text:
        raise HTTPException(status_code=422, detail="Le texte à analyser est vide.")
    if len(text) > CHAR_LIMIT:
        raise HTTPException(status_code=413, detail=f"Texte trop long ({len(text)} caractères ; maximum {CHAR_LIMIT}).")
    if kind not in ("text", "csv", "sql"):
        raise HTTPException(status_code=422, detail=f"Type de source inconnu « {kind} ».")
    base = normalize_base(base_iri or _default_base())
    skeleton = analyze_csv(text, filename) if kind == "csv" else analyze_sql(text) if kind == "sql" else None
    p = _provider(provider_id)
    if not p.configured:
        if skeleton is None:
            raise HTTPException(status_code=503, detail="Assistant non configuré : définissez ONTOFORGE_LLM_PROVIDER et la clé/URL associée "
                                "(ou fournissez une source CSV/SQL, analysée sans LLM).")
        data = dict(skeleton)
        data["explanation"] = ("Assistant IA non configuré : squelette produit par l'analyse déterministe de la source "
                               f"({'CSV' if kind == 'csv' else 'SQL'}). Libellés français et hiérarchie à compléter.")
        data["warnings"] = [*skeleton["warnings"], "Libellés français absents (analyse sans LLM)."]
        onto, warns = to_onto(data, base)
        return {"proposal": onto, "explanation": data["explanation"], "warnings": warns}
    user = f"Base IRI : {base}\nType de source : {kind}\n\nSOURCE :\n{text}\n"
    if skeleton:
        user += "\nSQUELETTE\n```json\n" + json.dumps({k: v for k, v in skeleton.items() if k != "source"}, ensure_ascii=False) + "\n```\n" \
                "Améliore ce squelette (noms, libellés fr/en, hiérarchie, cardinalités) sans perdre de table/colonne sans justification.\n"
    try:
        data = _ask_json(p, DRAFT_SYSTEM, user)
    except LLMError as exc:
        if skeleton is None:
            raise HTTPException(status_code=502, detail=str(exc)) from None
        data = dict(skeleton)
        data["warnings"] = [*skeleton["warnings"], f"{exc} Repli sur l'analyse déterministe."]
        data["explanation"] = "Fournisseur LLM en erreur : squelette déterministe de la source."
    onto, warns = to_onto(data, base)
    return {"proposal": onto, "explanation": str(data.get("explanation") or ""), "warnings": warns}


# ----------------------------------------------------------------------------- shapes
def _split_args(a: Any, b: Any = None) -> tuple[OntoModel, Optional[ShapesModel]]:
    if hasattr(a, "onto"):  # Project
        return a.onto, getattr(a, "shapes", None)
    return a, b


def _candidates(onto: OntoModel, sm: ShapesModel) -> list[dict[str, str]]:
    out = []
    for sh in sm.shapes.values():
        for ps in sh.properties:
            if ps.path.kind == "predicate" and ps.path.iri and (ps.datatype or ps.path.iri in onto.datatype_properties):
                for cls in sh.targets.target_class[:1]:
                    out.append({"class": cls, "property": ps.path.iri, "name": local_name(ps.path.iri), "datatype": local_name(ps.datatype or "")})
    return out[:150]


def _apply(sm: ShapesModel, enrichments: list[Any], notes: list[str]) -> int:
    n = 0
    for e in enrichments:
        if not isinstance(e, dict):
            continue
        node = next((s for s in sm.shapes.values() if e.get("class") in s.targets.target_class), None)
        if node is None:
            notes.append(f"Enrichissement ignoré : classe inconnue {e.get('class')}.")
            continue
        ps = next((x for x in node.properties if x.path.iri == e.get("property")), None)
        if ps is None:
            ps = PropertyShape(id=f"{node.id}-{local_name(str(e.get('property')))}", path=Path(kind="predicate", iri=e.get("property")))
            node.properties.append(ps)
        pat = e.get("pattern")
        if pat:
            try:
                re.compile(pat)
                ps.pattern = pat
            except re.error:
                notes.append(f"Motif invalide ignoré pour {local_name(str(e.get('property')))} : {pat}")
        for k in ("min_length", "max_length"):
            if isinstance(e.get(k), int) and not isinstance(e.get(k), bool) and e[k] >= 0:
                setattr(ps, k, e[k])
        for k in ("min_inclusive", "max_inclusive"):
            if e.get(k) not in (None, ""):
                setattr(ps, k, str(e[k]))
        if isinstance(e.get("in"), list) and e["in"]:
            ps.in_ = [str(v) for v in e["in"]]
        if e.get("message_fr"):
            ps.messages["fr"] = str(e["message_fr"])
        n += 1
    return n


def propose_shapes(onto: Any, shapes: Optional[ShapesModel] = None, provider_id: Optional[str] = None) -> dict[str, Any]:
    """propose_shapes(onto, shapes) ou propose_shapes(project) → {proposal: ShapesModel, explanation}."""
    onto, current = _split_args(onto, shapes)
    sm, notes = generate_shapes(onto)
    if current is not None and (current.shapes or current.property_shapes):
        sm = current.model_copy(deep=True)  # on enrichit l'existant sans l'écraser
        notes.append("Shapes existantes conservées ; enrichissement ajouté dessus.")
    p = _provider(provider_id)
    expl = "Shapes générées depuis l'ontologie (domaines, portées, cardinalités, clés)."
    if p.configured:
        cands = _candidates(onto, sm)
        try:
            data = _ask_json(p, SHAPES_SYSTEM, "CANDIDATS\n```json\n" + json.dumps({"properties": cands}, ensure_ascii=False) + "\n```\n")
            n = _apply(sm, data.get("enrichments", []) if isinstance(data.get("enrichments"), list) else [], notes)
            expl += f" Enrichissement par l'assistant : {n} propriété(s). {data.get('explanation', '')}".rstrip()
        except (LLMError, HTTPException) as exc:
            notes.append(f"Enrichissement LLM indisponible ({getattr(exc, 'detail', exc)}) ; shapes générées seules.")
    else:
        notes.append("Assistant non configuré : pas d'enrichissement (patterns, plages).")
    sm.warnings = [*sm.warnings, *[n for n in notes if n not in sm.warnings]]
    return {"proposal": sm, "explanation": expl}


# ----------------------------------------------------------------------------- explain
def explain(finding: Any, target: Any, onto: Any = None, provider_id: Optional[str] = None) -> dict[str, str]:
    """explain(finding, target, onto) ou explain(project, target, finding) → {text}."""
    if hasattr(finding, "onto"):
        finding, onto = onto, finding.onto
    f = finding.model_dump() if hasattr(finding, "model_dump") else dict(finding)
    p = _provider(provider_id)
    lang = _assistant_lang()
    if not p.configured:
        return {"text": fallback_explain(f, target, lang)}
    ctx = {}
    if isinstance(onto, OntoModel):
        for iri in [f.get("subject"), *f.get("related", [])][:6]:
            if iri:
                ctx[iri] = onto.label(iri)
    user = ("LANGUAGE: English\n" if lang == "en" else "") + f"CIBLE : {target}\n\nCONSTAT\n```json\n{json.dumps(f, ensure_ascii=False)}\n```\n\nLibellés : {json.dumps(ctx, ensure_ascii=False)}\n"
    try:
        return {"text": p.complete(EXPLAIN_SYSTEM, [{"role": "user", "content": user}], 1200).strip()}
    except LLMError as exc:
        return {"text": fallback_explain(f, target, lang) + (f"\n\n(Assistant unavailable: {exc})" if lang == "en" else f"\n\n(Assistant indisponible : {exc})")}


# ----------------------------------------------------------------------------- chat
CHAT_SYSTEM = """[TASK:chat]
Tu es l'assistant de conception d'OntoForge : tu aides à concevoir une ontologie (OWL 2) destinée à être transposée en property graph
(Curiosity, Neo4j). Tu converses avec l'utilisateur, tu poses une question seulement si elle est bloquante, et tu proposes un modèle quand c'est utile.
Réponds par UN objet JSON : {"reply":"réponse en langage naturel","ontology":null ou le JSON d'ontologie du format ci-dessous (éléments à AJOUTER ou modifier uniquement),"warnings":[]}.
Format d'ontologie : {"ontology":{"label_fr","label_en","comment"},"classes":[{"name","label_fr","label_en","comment","parent","key":[],"disjoint_with":[]}],
 "object_properties":[{"name","label_fr","label_en","domain","range","functional","required","inverse"}],"datatype_properties":[{"name","label_fr","label_en","domain","range","functional","required"}]}
Langue de la réponse : {LANG}. Aucun texte hors du JSON."""

ATT_LIMIT = 12000
MSG_LIMIT = 40


def _onto_digest(onto: OntoModel) -> str:
    cls = [local_name(i) for i in list(onto.classes)[:60]]
    ops = [local_name(i) for i in list(onto.object_properties)[:60]]
    dps = [local_name(i) for i in list(onto.datatype_properties)[:60]]
    return f"Classes : {', '.join(cls) or '(aucune)'}\nPropriétés d'objet : {', '.join(ops) or '(aucune)'}\nPropriétés de données : {', '.join(dps) or '(aucune)'}"


def chat(project: Any, messages: list[dict[str, Any]], provider_id: Optional[str] = None,
         attachments: Optional[list[dict[str, Any]]] = None, lang: Optional[str] = None) -> dict[str, Any]:
    """Conversation par projet → {reply, proposal: OntoModel | None, warnings}. La proposition n'est jamais appliquée ici."""
    msgs = [{"role": "assistant" if m.get("role") == "assistant" else "user", "content": str(m.get("content", ""))}
            for m in (messages or []) if str(m.get("content", "")).strip()][-MSG_LIMIT:]
    if not msgs or msgs[-1]["role"] != "user":
        raise HTTPException(status_code=422, detail="La conversation doit se terminer par un message de l'utilisateur.")
    onto = getattr(project, "onto", None)
    base = (onto.meta.iri if isinstance(onto, OntoModel) and onto.meta.iri else None) or _default_base()
    warns: list[str] = []
    skeleton = None
    ctx = ""
    for a in attachments or []:
        content = str(a.get("content", ""))[:ATT_LIMIT]
        kind = a.get("kind", "text")
        if len(str(a.get("content", ""))) > ATT_LIMIT:
            warns.append(f"Pièce jointe « {a.get('name')} » tronquée à {ATT_LIMIT} caractères.")
        ctx += f"\n--- PIÈCE JOINTE {a.get('name')} ({kind}) ---\n{content}\n"
        if skeleton is None and kind in ("csv", "sql"):
            skeleton = analyze_csv(content, str(a.get("name") or "")) if kind == "csv" else analyze_sql(content)
    p = _provider(provider_id)
    if not p.configured:
        if skeleton is None:
            raise HTTPException(status_code=503, detail=f"Le fournisseur « {p.name} » n'est pas configuré : renseignez-le dans Paramètres.")
        onto_p, w = to_onto(dict(skeleton), normalize_base(base))
        return {"reply": "Fournisseur non configuré : squelette produit par l'analyse déterministe de la pièce jointe.",
                "proposal": onto_p, "warnings": [*warns, *w]}
    lang = "English" if (lang or _assistant_lang()) == "en" else "français"
    user = msgs[-1]["content"]
    if onto is not None and isinstance(onto, OntoModel):
        user += "\n\nMODÈLE ACTUEL\n" + _onto_digest(onto)
    if ctx:
        user += "\n" + ctx
    if skeleton:
        user += "\nSQUELETTE\n```json\n" + json.dumps({k: v for k, v in skeleton.items() if k != "source"}, ensure_ascii=False) + "\n```\n"
    system = CHAT_SYSTEM.replace("{LANG}", lang)
    try:
        raw = p.complete(system, [*msgs[:-1], {"role": "user", "content": user}], 6000)
    except LLMError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from None
    try:
        data = extract_json(raw)
    except ValueError:
        return {"reply": raw.strip(), "proposal": None, "warnings": warns}
    proposal = None
    ont = data.get("ontology")
    if isinstance(ont, dict) and (ont.get("classes") or ont.get("object_properties") or ont.get("datatype_properties")):
        proposal, w = to_onto(ont, normalize_base(base))
        warns += w
    if isinstance(data.get("warnings"), list):
        warns += [str(x) for x in data["warnings"] if x]
    return {"reply": str(data.get("reply") or ""), "proposal": proposal, "warnings": warns}
