"""Import déterministe SQL DDL / CSV / JSON Schema (L48) : orchestration, aperçu, application.

Aucun LLM, aucun accès réseau. ``run`` est pur (mêmes entrées → mêmes sorties, ``digest`` identique) : l'aperçu et l'application rejouent le même
calcul, et l'application refuse (409) si le résultat a changé depuis l'aperçu (``expect_digest``).
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Any, Optional

from ..core.onto_model import OWL, RDFS, OntoModel
from ..core.shapes_model import ShapesModel
from . import csv_import, json_schema, sql_ddl, sql_to_entities
from .builder import Built, build
from .ir import Draft
from .limits import MAX_FILES, Budget, ImportRefused, max_bytes

KINDS = ("sql", "csv", "json-schema")
DIALECTS = ("auto", "postgresql", "mysql", "sqlserver", "generic")
_BASE_OK = re.compile(r"^(?:https?://|urn:)[^\s<>\"{}|\\^`]{1,280}$")
# détection linéaire : liste fermée de mots entre CREATE et TABLE (aucune répétition imbriquée, donc aucun retour arrière quadratique)
_CREATE_TABLE = re.compile(r"\bcreate[ \t\r\n]+(?:or[ \t\r\n]+replace[ \t\r\n]+)?(?:(?:global|local|temporary|temp|unlogged|external|virtual|memory|volatile)[ \t\r\n]+){0,3}table\b", re.I)
DEFAULT_BASE = "https://w3id.org/ontoforge/import#"


@dataclass
class ImportResult:
    kind: str
    files: list[str]
    draft: Draft
    built: Built
    base_iri: str
    options: dict[str, Any] = field(default_factory=dict)


def decode_text(data: bytes) -> str:
    """UTF-8 (avec ou sans BOM), UTF-16 (BOM, fréquent pour les scripts SQL Server), sinon Latin-1. Refuse les fichiers binaires."""
    if data[:2] in (b"\xff\xfe", b"\xfe\xff"):
        try:
            return data.decode("utf-16")
        except UnicodeError:
            pass
    if b"\x00" in data[:4096]:
        raise ImportRefused("not_text", 415)
    for enc in ("utf-8-sig", "cp1252"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("latin-1")


def sniff_kind(name: str, text: str) -> Optional[str]:
    ext = os.path.splitext(name.lower())[1]
    if ext in (".sql", ".ddl"):
        return "sql"
    if ext in (".csv", ".tsv"):
        return "csv"
    head = text.lstrip()[:4000]
    if ext in (".json", ".schema") or head.startswith("{"):
        return "json-schema" if head.startswith("{") else None
    if _CREATE_TABLE.search(text[:200_000]):
        return "sql"
    lines = [ln for ln in text.splitlines()[:12] if ln.strip()]
    if len(lines) >= 2:
        for d in (",", ";", "\t", "|"):
            if lines[0].count(d) >= 1 and len({ln.count(d) for ln in lines}) <= 2:
                return "csv"
    return None


def clean_options(raw: Optional[dict[str, Any]]) -> dict[str, Any]:
    raw = raw if isinstance(raw, dict) else {}
    out: dict[str, Any] = {
        "singularize": bool(raw.get("singularize", True)),
        "required_from_sample": bool(raw.get("required_from_sample", False)),
    }
    d = raw.get("dialect", "auto")
    out["dialect"] = d if d in DIALECTS else "auto"
    de = raw.get("delimiter")
    out["delimiter"] = de if de in (",", ";", "\t", "|") else None
    ex = raw.get("exclude") or []
    out["exclude"] = [str(x)[:128] for x in ex[:800]] if isinstance(ex, list) else []
    ch = raw.get("choices") or {}
    out["choices"] = {str(k)[:300]: str(v)[:40] for k, v in list(ch.items())[:800]} if isinstance(ch, dict) else {}
    return out


def check_base(base: Optional[str]) -> str:
    b = (base or "").strip()
    if not b:
        return DEFAULT_BASE
    if not _BASE_OK.match(b) or "#" in b[:-1]:   # RFC 3987 : un fragment n'admet pas « # » ; la base n'a qu'un « # », en dernier caractère
        raise ImportRefused("bad_base_iri", 422)
    return b


def run(files: list[tuple[str, bytes]], kind: Optional[str], options: Optional[dict[str, Any]], base_iri: Optional[str]) -> ImportResult:
    if not files:
        raise ImportRefused("no_file", 422)
    if len(files) > MAX_FILES:
        raise ImportRefused("too_many_files", 413, max=MAX_FILES)
    opts = clean_options(options)
    base = check_base(base_iri)
    lim = max_bytes()
    texts: list[tuple[str, str]] = []
    for name, data in files:
        name = os.path.basename((name or "fichier").replace("\\", "/"))[:200] or "fichier"
        if len(data) > lim:
            raise ImportRefused("too_big", 413, max=lim // (1024 * 1024), file=name)
        if not data.strip():
            raise ImportRefused("empty_file", 422, file=name)
        texts.append((name, decode_text(data)))
    if kind not in KINDS:
        kinds = {sniff_kind(n, t) for n, t in texts}
        if None in kinds:
            raise ImportRefused("unknown_kind", 422)
        if len(kinds) != 1:
            raise ImportRefused("mixed_kinds", 422)
        kind = kinds.pop()
    budget = Budget()
    draft = Draft(kind=kind, files=[n for n, _ in texts])
    if kind == "sql":
        schema = sql_ddl.parse_ddl(texts, opts["dialect"], draft, budget)
        if not schema.tables:
            raise ImportRefused("sql_no_table", 422)
        sql_to_entities.to_draft(schema, draft, opts)
    elif kind == "csv":
        csv_import.parse_csv(texts, draft, opts, budget)
    else:
        for name, text in texts:
            doc = json_schema.load_json(text, budget)
            if not json_schema.looks_like_json_schema(doc):
                raise ImportRefused("json_not_schema", 422, file=name)
        json_schema.parse_json_schema(texts, draft, opts, budget)
    if not draft.entities:
        raise ImportRefused("nothing_found", 422)
    built = build(draft, base, opts)
    return ImportResult(kind=kind, files=draft.files, draft=draft, built=built, base_iri=base, options=opts)


def conformance(onto: OntoModel) -> dict[str, Any]:
    from ..conformance.profiles import check_conformance
    rep = check_conformance(onto)
    return {"profiles": dict(rep.profiles),
            "errors": [{"code": i.code, "message": i.message, "subject": i.subject} for i in rep.issues if i.level == "error"][:50]}


# ---- application au projet -------------------------------------------------------------------------------

def merge_into(project, result: ImportResult) -> dict[str, Any]:
    """Ajoute au projet ce que l'import produit ; ce qui existe déjà (même IRI) n'est jamais modifié. Retourne le compte rendu de fusion."""
    onto: OntoModel = project.onto
    new = result.built.onto
    sh_new: ShapesModel = result.built.shapes
    existing = set(onto.classes) | set(onto.object_properties) | set(onto.datatype_properties) | set(onto.annotation_properties) | set(onto.individuals)
    if not (onto.classes or onto.object_properties or onto.datatype_properties or onto.individuals):
        onto.meta.iri = result.base_iri.rstrip("#/")   # projet vide : l'import fixe l'espace de noms de l'ontologie
        onto.meta.prefixes["ex"] = result.base_iri
    added = {"classes": 0, "object_properties": 0, "datatype_properties": 0, "shapes": 0}
    skipped: list[str] = []
    skip_classes = {i for i in new.classes if i in existing}
    for iri, c in new.classes.items():
        if iri in skip_classes:
            skipped.append(iri)
            continue
        onto.classes[iri] = c
        added["classes"] += 1
    for coll, name in ((new.object_properties, "object_properties"), (new.datatype_properties, "datatype_properties")):
        for iri, p in coll.items():
            if iri in existing or any(d in skip_classes for d in p.domain):
                skipped.append(iri)
                continue
            getattr(onto, name)[iri] = p
            added[name] += 1
    for sid, sh in sh_new.shapes.items():
        if any(t in skip_classes for t in sh.targets.target_class) or sid in project.shapes.shapes:
            continue
        project.shapes.shapes[sid] = sh
        added["shapes"] += 1
    for pre, ns in new.meta.prefixes.items():
        if pre not in onto.meta.prefixes and ns not in onto.meta.prefixes.values():
            onto.meta.prefixes[pre] = ns
    for pre, ns in sh_new.prefixes.items():
        project.shapes.prefixes.setdefault(pre, ns)
    return {"added": added, "skipped": skipped[:200], "skipped_count": len(skipped)}


# ---- réponse JSON ----------------------------------------------------------------------------------------

def describe(result: ImportResult, lang: str, project=None) -> dict[str, Any]:
    """Aperçu : tout ce qui sera créé, les décisions, les avis, les éléments ignorés. Rien n'est écrit."""
    from . import messages as M
    d, b = result.draft, result.built
    conflicts: list[str] = []
    if project is not None:
        existing = set(project.onto.classes) | set(project.onto.object_properties) | set(project.onto.datatype_properties)
        conflicts = [c["name"] for c in b.classes if c["iri"] in existing]
    return {
        "kind": result.kind, "dialect": d.dialect, "files": result.files, "digest": b.digest, "base_iri": result.base_iri,
        "summary": b.stats, "classes": b.classes, "conflicts": conflicts,
        "decisions": [{"id": x.id, "type": x.type, "subject": x.subject, "options": x.options, "default": x.default, "chosen": x.chosen, "params": x.params,
                       "message": M.fmt(M.DECISIONS, x.type, lang, x.params)} for x in d.decisions],
        "notices": [{"code": n.code, "level": n.level, "subject": n.subject, "params": n.params, "message": M.notice(n.code, lang, n.params)} for n in d.notices],
        "ignored": [{"category": k, "count": v["count"], "examples": v["examples"], "message": M.fmt(M.IGNORED, k, lang)} for k, v in d.ignored.items()],
        "conformance": conformance(b.onto),
        "options": result.options,
    }
