"""Brouillon (entités) → OntoModel + ShapesModel (L48).

Contraintes de sortie : OWL 2 DL (datatypes de la table OWL 2, ``owl:hasKey`` sur des propriétés déclarées, cardinalités sur des propriétés
simples, aucune propriété à la fois d'objet et de données) et SHACL Core valide (shapes produites par ``shacl.owl_to_shacl.generate_shapes``
puis enrichies des facettes relevées : longueurs, bornes, motifs).
"""
from __future__ import annotations

import hashlib
import json
import datetime
import re
from dataclasses import dataclass, field
from typing import Any, Optional

from ..assistant.convert import normalize_base
from ..assistant.naming import camel, humanize, pascal
from ..core.onto_model import (XSD, DataRange, DatatypeProperty, LiteralValue, ObjectProperty, OntClass, OntoModel,
                               OntologyMeta, Restriction)
from ..core.shapes_model import ShapesModel
from .ir import Draft, Entity, Prop, Rel

_FACET_FIELDS = ("min_length", "max_length", "pattern", "min_inclusive", "max_inclusive", "min_exclusive", "max_exclusive")
_NUMERIC = {"integer", "int", "long", "short", "byte", "unsignedInt", "unsignedLong", "unsignedShort", "unsignedByte", "decimal", "double", "float",
            "nonNegativeInteger", "positiveInteger"}


@dataclass
class Built:
    onto: OntoModel
    shapes: ShapesModel
    classes: list[dict[str, Any]] = field(default_factory=list)
    stats: dict[str, int] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)
    digest: str = ""


_INT_RE = re.compile(r"^[+-]?\d{1,40}$")
_DEC_RE = re.compile(r"^[+-]?(?:\d{1,40}(?:\.\d{0,40})?|\.\d{1,40})(?:[eE][+-]?\d{1,4})?$")
_DT_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,9})?(?:Z|[+-]\d{2}:\d{2})?$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_INTEGRAL = {"integer", "int", "long", "short", "byte", "unsignedInt", "unsignedLong", "unsignedShort", "unsignedByte", "nonNegativeInteger", "positiveInteger"}


def _valid_date(s: str) -> bool:
    try:
        datetime.date.fromisoformat(s[:10])
        return True
    except ValueError:
        return False


def _valid_dt(s: str) -> bool:
    """Forme lexicale et calendrier : mois, jour, heure, minute, seconde (60 toléré pour une seconde intercalaire) et décalage horaire."""
    if not _valid_date(s[:10]):
        return False
    h, m, sec = int(s[11:13]), int(s[14:16]), int(s[17:19])
    if h > 24 or m > 59 or sec > 60 or (h == 24 and (m or sec or re.search(r"\.0*[1-9]", s[19:]))):
        return False
    tz = re.search(r"([+-])(\d{2}):(\d{2})$", s)
    return not tz or (int(tz.group(2)) <= 14 and int(tz.group(3)) <= 59)


def _typed_bound(xsd: str, v: Any, tz: bool = False) -> Optional[str]:
    """Borne SHACL typée comme la colonne (xsd:date et xsd:dateTime, ou texte et nombre, ne sont pas comparables : la contrainte échouerait toujours).
    Renvoie un littéral N-Triples, ou None si la valeur n'est pas une forme lexicale valide du type de la colonne."""
    s = str(v).strip()
    if xsd in _INTEGRAL and _INT_RE.match(s):
        lex = s.lstrip("+")
    elif xsd in _NUMERIC and xsd not in _INTEGRAL and _DEC_RE.match(s):
        lex = s.lstrip("+")
    elif xsd == "dateTime" and _DT_RE.match(s) and _valid_dt(s):
        lex = s
    elif xsd == "dateTime" and _DATE_RE.match(s) and _valid_date(s):
        lex = s + "T00:00:00" + ("Z" if tz else "")   # colonne avec fuseau : borne en UTC, même convention que la colonne
    else:
        return None
    return f'"{lex}"^^<{XSD}{xsd}>'


def _human(name: str, cap: bool) -> str:
    h = humanize(name) or name
    return h[:1].upper() + h[1:] if cap else h


def _prov(source: str, lang: str) -> str:
    return f"Importé depuis {source}." if lang == "fr" else f"Imported from {source}."


def build(draft: Draft, base_iri: Optional[str], options: Optional[dict[str, Any]] = None) -> Built:
    options = options or {}
    base = normalize_base(base_iri)
    exclude = {str(x) for x in (options.get("exclude") or [])}   # identifiants stables (clé d'entité), jamais le nom affiché (dédoublonné)
    ents: dict[str, Entity] = {k: e for k, e in draft.entities.items() if e.key not in exclude and k not in exclude}
    for k, e in draft.entities.items():
        if k not in ents:
            draft.notice("excluded", "info", e.name, name=e.name)
    # --- noms de classes uniques
    used: set[str] = set()
    cname: dict[str, str] = {}
    for k, e in ents.items():
        n = pascal(e.name) or "Class"
        cand, i = n, 2
        while cand.lower() in used:
            cand = f"{n}{i}"
            i += 1
        if cand != n:
            draft.notice("class_renamed", "warning", e.name, name=e.name, to=cand)
        used.add(cand.lower())
        cname[k] = cand
    civ = {k: base + n for k, n in cname.items()}
    # --- noms de propriétés : court si unique dans tout le brouillon, sinon préfixé par la classe (indépendant de l'ordre des tables)
    wanted: list[tuple[str, str, str, str]] = []     # (clé entité, 'p'|'r', clé élément, nom souhaité)
    for k, e in ents.items():
        for p in e.props:
            wanted.append((k, "p", p.key, p.hint or camel(p.key) or "value"))
        for r in e.rels:
            if r.target not in ents and not any(x in ents for x in r.union):   # union : la relation survit tant qu'un membre reste
                draft.notice("relation_dropped", "warning", e.name, entity=e.name, relation=r.key.replace("fk:", "").replace("assoc:", ""))
            if r.target in ents or any(x in ents for x in r.union):
                wanted.append((k, "r", r.key, r.hint or camel("has " + ((ents[r.target] if r.target in ents else next(ents[x] for x in r.union if x in ents)).name))))
    count: dict[str, int] = {}
    for _, _, _, w in wanted:
        count[w.lower()] = count.get(w.lower(), 0) + 1
    pname: dict[tuple[str, str, str], str] = {}
    taken: set[str] = set()
    for k, kind, ik, w in wanted:
        n = w if count[w.lower()] == 1 else camel(cname[k]) + w[:1].upper() + w[1:]
        cand, i = n, 2
        while cand.lower() in taken:
            cand = f"{n}{i}"
            i += 1
        taken.add(cand.lower())
        pname[(k, kind, ik)] = cand

    meta = OntologyMeta(iri=base.rstrip("#/"), prefixes={"ex": base, "owl": "http://www.w3.org/2002/07/owl#", "rdfs": "http://www.w3.org/2000/01/rdf-schema#", "xsd": XSD})
    onto = OntoModel(meta=meta)
    listing: list[dict[str, Any]] = []
    for k, e in ents.items():
        civi = civ[k]
        cmt = e.comment.strip()
        comments = {"fr": cmt or _prov(e.source, "fr"), "en": cmt or _prov(e.source, "en")} if (cmt or e.source) else {}
        if e.kind == "stub":
            comments = {"fr": "Classe créée automatiquement : « " + e.source + " ». À compléter.", "en": "Class created automatically: “" + e.source + "”. To be completed."}
        onto.classes[civi] = OntClass(iri=civi, labels={"fr": _human(cname[k], True), "en": _human(cname[k], True)}, comments=comments)
    for k, e in ents.items():
        civi = civ[k]
        oc = onto.classes[civi]
        for pk in e.parents:
            if pk in ents and civ[pk] != civi and civ[pk] not in oc.sub_class_of:
                oc.sub_class_of.append(civ[pk])
        item = {"iri": civi, "key": k, "name": cname[k], "source": e.source, "kind": e.kind, "parents": [cname[x] for x in e.parents if x in ents], "props": [], "rels": [], "keys": [], "assumed_key": e.assumed_key}
        iri_of: dict[str, str] = {}
        for p in e.props:
            piri = base + pname[(k, "p", p.key)]
            iri_of[p.key] = piri
            dt = XSD + p.xsd
            dp = DatatypeProperty(iri=piri, labels={"fr": _human(p.key, False), "en": _human(p.key, False)}, domain=[civi], range=[dt], functional=not p.many)
            if p.comment.strip():
                dp.comments = {"fr": p.comment.strip(), "en": p.comment.strip()}
            if p.enum:
                dp.range_expr = DataRange(base=dt, one_of=[LiteralValue(value=v, datatype=None if p.xsd == "string" else dt) for v in p.enum])   # xsd:string = littéral simple en RDF 1.1
            onto.datatype_properties[piri] = dp
            _cardinality(oc, piri, p.required, p.min_count, p.max_count, p.many)
            item["props"].append({"name": pname[(k, "p", p.key)], "source": p.key, "type": "xsd:" + p.xsd, "required": p.required, "many": p.many,
                                  "enum": p.enum[:12] if p.enum else None, "facets": p.facets or None, "degraded": p.degraded})
        for r in e.rels:
            if r.target not in ents and not any(x in ents for x in r.union):
                continue
            piri = base + pname[(k, "r", r.key)]
            iri_of[r.key] = piri
            rng = [civ[r.target]] if r.target in ents else []
            op = ObjectProperty(iri=piri, labels={"fr": _human(pname[(k, "r", r.key)], False), "en": _human(pname[(k, "r", r.key)], False)}, domain=[civi],
                                characteristics=[] if r.many else ["functional"])
            members = list(dict.fromkeys(civ[x] for x in r.union if x in ents)) if r.union else []
            if len(members) >= 2:
                op.range_union = members
            elif len(members) == 1:
                op.range = members      # owl:unionOf exige au moins deux membres (OWL 2 SS §8.1.1) : un seul se réduit à la classe
                draft.notice("union_reduced", "info", e.name, entity=e.name, relation=pname[(k, "r", r.key)])
            elif r.union:
                draft.notice("union_empty", "warning", e.name, entity=e.name, relation=pname[(k, "r", r.key)])
            else:
                op.range = rng
            cm = r.comment.strip()
            op.comments = {"fr": cm or _prov(r.source, "fr"), "en": cm or _prov(r.source, "en")} if (cm or r.source) else {}
            onto.object_properties[piri] = op
            _cardinality(oc, piri, r.required, r.min_count, r.max_count, r.many)
            item["rels"].append({"name": pname[(k, "r", r.key)], "source": r.source, "target": cname[r.target if r.target in ents else next(x for x in r.union if x in ents)], "required": r.required, "many": r.many,
                                 "union": [cname[x] for x in r.union if x in ents] or None})
        for key in e.keys:
            iris = [iri_of[x] for x in key if x in iri_of]
            if iris and len(iris) == len(key):
                if iris not in oc.has_keys:
                    oc.has_keys.append(iris)
                item["keys"].append([x.rsplit("#", 1)[-1].rsplit("/", 1)[-1] for x in iris])
            else:
                draft.notice("key_dropped", "warning", e.name, entity=e.name)
        listing.append(item)
    # --- shapes
    from ..shacl.owl_to_shacl import generate_shapes
    shapes, notes = generate_shapes(onto)
    _facets(draft, ents, civ, pname, base, shapes)
    shapes.prefixes = dict(meta.prefixes)
    nc = [n for n in notes if n.startswith("[NON-CORE]")]
    if nc:
        draft.ignore("key_uniqueness", f"{len(nc)}")
        draft.ignored["key_uniqueness"]["count"] = len(nc)
    stats = {"classes": len(onto.classes), "object_properties": len(onto.object_properties), "datatype_properties": len(onto.datatype_properties),
             "keys": sum(len(c.has_keys) for c in onto.classes.values()), "enumerations": sum(1 for p in onto.datatype_properties.values() if p.range_expr is not None),
             "shapes": len(shapes.shapes), "property_shapes": sum(len(s.properties) for s in shapes.shapes.values())}
    digest = hashlib.sha256(json.dumps([onto.model_dump(mode="json"), shapes.model_dump(mode="json", by_alias=True)], sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:16]
    return Built(onto=onto, shapes=shapes, classes=listing, stats=stats, notes=notes, digest=digest)


def _cardinality(oc: OntClass, piri: str, required: bool, min_count: Optional[int], max_count: Optional[int], many: bool) -> None:
    mn = min_count if min_count else (1 if required else 0)
    if mn >= 1:
        oc.restrictions.append(Restriction(property=piri, kind="min", n=mn))
    if many and max_count is not None and max_count >= max(mn, 1):
        oc.restrictions.append(Restriction(property=piri, kind="max", n=max_count))


def _facets(draft: Draft, ents: dict[str, Entity], civ: dict[str, str], pname: dict[tuple[str, str, str], str], base: str, shapes: ShapesModel) -> None:
    """Reporte les facettes de valeur (longueurs, bornes, motif) sur les property shapes correspondantes."""
    by_class: dict[str, Any] = {}
    for sh in shapes.shapes.values():
        for c in sh.targets.target_class:
            by_class[c] = sh
    for k, e in ents.items():
        sh = by_class.get(civ[k])
        if sh is None:
            continue
        for p in e.props:
            if not p.facets:
                continue
            piri = base + pname[(k, "p", p.key)]
            ps = next((x for x in sh.properties if x.path.kind == "predicate" and x.path.iri == piri), None)
            if ps is None:
                continue
            for f in _FACET_FIELDS:
                v = p.facets.get(f)
                if v is None:
                    continue
                if f in ("min_length", "max_length"):
                    if p.xsd in ("string", "anyURI"):
                        setattr(ps, f, int(v))
                elif f == "pattern":
                    if p.xsd == "string":
                        ps.pattern = v   # motif JSON Schema (ECMA 262) repris tel quel : sh:pattern cherche une sous-chaîne, comme JSON Schema
                else:
                    tzaware = bool(re.search(r"tz|time zone|offset", p.src_type or "", re.I)) and not re.search(r"without", p.src_type or "", re.I)
                    typed = _typed_bound(p.xsd, v, tzaware)
                    if typed and tzaware and str(v).strip() != typed.split('"')[1] and typed.endswith('Z"^^<' + XSD + 'dateTime>'):
                        draft.notice("bound_tz_assumed", "info", e.name, entity=e.name, prop=pname[(k, "p", p.key)])
                    if typed is None:
                        draft.notice("bound_dropped", "warning", e.name, entity=e.name, prop=pname[(k, "p", p.key)], value=str(v)[:40])
                    else:
                        setattr(ps, f, typed)
