"""Assistant global (L16) : conversation consciente de l'écran, qui propose des ACTIONS validées (jamais appliquées ici).

``run(project, messages, context, provider_id, attachments)`` -> ``{reply, actions, warnings, proposal?}``
Actions : ``ops`` (liste d'opérations d'édition validées par essai à blanc), ``proposal`` (ontologie partielle),
``shapes`` (correctifs de shapes), ``guided_query`` (requête guidée issue de /query/nl), ``navigate``.
Rien n'est inventé : les IRIs existantes sont retrouvées par nom local / libellé, les nouvelles entités prennent l'IRI de base du projet,
toute opération qui échoue à l'essai est retirée avec un avertissement. Sans LLM (mock / non configuré) : repli déterministe en français.
"""
from __future__ import annotations

import json
import re
import unicodedata
from functools import lru_cache
from pathlib import Path as FsPath
from typing import Any, Optional

from ..core.onto_model import XSD, OntoModel, local_name
from ..core.shapes_model import NodeShape, Path, PropertyShape, ShapesModel
from ..editing import ops as ops_mod

CTX_MAX = 24000
XSD_NAMES = {"string": "string", "texte": "string", "chaine": "string", "integer": "integer", "entier": "integer", "int": "integer",
             "decimal": "decimal", "nombre": "decimal", "reel": "decimal", "float": "double", "double": "double", "number": "decimal",
             "date": "date", "datetime": "dateTime", "dateheure": "dateTime", "boolean": "boolean", "booleen": "boolean",
             "bool": "boolean", "uri": "anyURI", "url": "anyURI"}
REF_KEYS = ("iri", "parent", "property", "filler", "inverse", "inverse_of")


# ----------------------------------------------------------------------------- normalisation / résolution
def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "", s)


def _sing(s: str) -> str:
    return s[:-1] if len(s) > 3 and s.endswith("s") else s


def pascal(text: str) -> str:
    words = re.findall(r"[A-Za-z0-9]+", unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode())
    return "".join(w[:1].upper() + w[1:] for w in words)


def camel(text: str) -> str:
    p = pascal(text)
    return p[:1].lower() + p[1:]


def base_of(onto: OntoModel) -> str:
    b = onto.meta.iri or "https://example.org/onto"
    return b if b.endswith(("#", "/")) else b + "#"


class Resolver:
    """Retrouve une entité existante par IRI, nom local ou libellé (insensible à la casse, aux accents et au pluriel)."""

    def __init__(self, onto: OntoModel):
        self.onto = onto
        self.idx: dict[str, list[tuple[str, str]]] = {}
        for kind, coll in (("class", onto.classes), ("object", onto.object_properties), ("data", onto.datatype_properties),
                           ("individual", onto.individuals)):
            for iri, e in coll.items():
                keys = {local_name(iri), *e.labels.values()}
                for k in keys:
                    for n in {norm(k), _sing(norm(k))}:
                        if n:
                            self.idx.setdefault(n, []).append((kind, iri))

    def find(self, text: Any, kinds: tuple[str, ...] = ("class", "object", "data")) -> Optional[str]:
        if not isinstance(text, str) or not text.strip():
            return None
        t = text.strip()
        for kind, coll in (("class", self.onto.classes), ("object", self.onto.object_properties), ("data", self.onto.datatype_properties)):
            if t in coll and kind in kinds:
                return t
        n = norm(t)
        for key in (n, _sing(n)):
            hits = [iri for k, iri in self.idx.get(key, []) if k in kinds]
            if hits:
                return hits[0]
        return None

    def kind(self, iri: str) -> Optional[str]:
        return ops_mod.kind_of(self.onto, iri)


def xsd_iri(text: Any) -> Optional[str]:
    if not isinstance(text, str):
        return None
    t = text.strip()
    if t.startswith(XSD):
        return t
    if t.lower().startswith("xsd:"):
        t = t[4:]
    n = norm(t)
    name = XSD_NAMES.get(n) or next((v for v in set(XSD_NAMES.values()) if norm(v) == n), None)
    return XSD + name if name else None


# ----------------------------------------------------------------------------- aperçu lisible des opérations
def _nm(onto: OntoModel, iri: Any, en: bool = False) -> str:
    if not isinstance(iri, str) or not iri:
        return "?"
    return f"“{onto.label(iri, 'en')}”" if en else f"« {onto.label(iri)} »"


def describe(op: dict, before: OntoModel, after: OntoModel, lang: str = "fr") -> str:
    en = lang == "en"
    k = op.get("op")
    n = lambda i: _nm(after if i in after.classes or i in after.object_properties or i in after.datatype_properties else before, i, en)  # noqa: E731
    iri = op.get("iri")
    if k == "add_class":
        s = (f"Add the class {n(iri)}" if en else f"Ajouter la classe {n(iri)}")
        return s + ((f" under {n(op['parent'])}" if en else f" sous {n(op['parent'])}") if op.get("parent") else "")
    if k == "add_subclass":
        return f"Place {n(iri)} under {n(op.get('parent'))}" if en else f"Placer {n(iri)} sous {n(op.get('parent'))}"
    if k == "remove_subclass":
        return f"Remove {n(iri)} from {n(op.get('parent'))}" if en else f"Retirer {n(iri)} de {n(op.get('parent'))}"
    if k == "add_datatype_property":
        t0 = local_name(op["range"]) if isinstance(op.get("range"), str) else "string"
        names = ({"string": "text", "integer": "integer", "decimal": "decimal", "date": "date", "dateTime": "date and time", "boolean": "boolean",
                  "double": "number", "anyURI": "link"} if en else
                 {"string": "texte", "integer": "entier", "decimal": "décimal", "date": "date", "dateTime": "date et heure", "boolean": "booléen",
                  "double": "nombre", "anyURI": "lien"})
        t = names.get(t0, t0)
        dom = ", ".join(n(d) for d in ([op["domain"]] if isinstance(op.get("domain"), str) else op.get("domain") or []))
        return f"Add the property {n(iri)} ({t}) to {dom or '?'}" if en else f"Ajouter la propriété {n(iri)} ({t}) à {dom or '?'}"
    if k == "add_object_property":
        d = ", ".join(n(x) for x in (op.get("domain") or [])) or "?"
        r = ", ".join(n(x) for x in (op.get("range") or [])) or "?"
        return f"Add the relationship {n(iri)} from {d} to {r}" if en else f"Ajouter la relation {n(iri)} de {d} vers {r}"
    if k == "set_domain_range":
        return f"Change the domain / range of {n(iri)}" if en else f"Modifier le domaine / la portée de {n(iri)}"
    if k == "set_restriction":
        kind, nn = op.get("kind"), op.get("n")
        txt = ({"min": f"at least {nn} value(s)", "max": f"at most {nn} value(s)", "exactly": f"exactly {nn} value(s)",
                "some": "at least one value", "only": "only values of the given type", "value": "a fixed value", "self": "itself"} if en else
               {"min": f"au moins {nn} valeur(s)", "max": f"au plus {nn} valeur(s)", "exactly": f"exactement {nn} valeur(s)",
                "some": "au moins une valeur", "only": "uniquement des valeurs du type indiqué", "value": "une valeur fixe", "self": "lui-même"}).get(kind, str(kind))
        if kind == "min" and nn == 1:
            return f"Make {n(op.get('property'))} required for {n(iri)}" if en else f"Rendre {n(op.get('property'))} obligatoire pour {n(iri)}"
        return f"On {n(iri)}: {n(op.get('property'))} with {txt}" if en else f"Sur {n(iri)} : {n(op.get('property'))} avec {txt}"
    if k == "remove_restriction":
        return f"Remove the restriction on {n(op.get('property'))} from {n(iri)}" if en else f"Retirer la restriction sur {n(op.get('property'))} de {n(iri)}"
    if k == "delete_entity":
        return f"Delete {_nm(before, iri, en)} (and everything attached to it)" if en else f"Supprimer {_nm(before, iri)} (et ce qui s'y rattache)"
    if k == "rename_entity":
        return f"Rename {_nm(before, iri, en)}" if en else f"Renommer {_nm(before, iri)}"
    if k == "set_label":
        return f"Label ({op.get('lang', 'fr')}) of {n(iri)}: “{op.get('text')}”" if en else f"Libellé ({op.get('lang', 'fr')}) de {n(iri)} : « {op.get('text')} »"
    if k == "set_comment":
        return f"Comment of {n(iri)}: “{str(op.get('text'))[:80]}”" if en else f"Commentaire de {n(iri)} : « {str(op.get('text'))[:80]} »"
    if k == "set_key":
        return f"Define the key of {n(iri)}" if en else f"Définir la clé de {n(iri)}"
    if k == "add_disjoint":
        return f"Declare {n(iri)} disjoint from another class" if en else f"Déclarer {n(iri)} disjointe d'une autre classe"
    if k == "set_characteristic":
        return f"Characteristic of {n(iri)}" if en else f"Caractéristique de {n(iri)}"
    return f"{k} on {n(iri)}" if en else f"{k} sur {n(iri)}"


# ----------------------------------------------------------------------------- validation d'une liste d'opérations
def validate_ops(project: Any, raw_ops: Any, lang: str = "fr") -> tuple[list[dict], list[dict], list[str]]:
    """-> (opérations retenues et normalisées, aperçu [{op, text}], avertissements). Essai à blanc sur une copie du projet."""
    warns: list[str] = []
    work = project.model_copy(deep=True)
    kept: list[dict] = []
    preview: list[dict] = []
    if not isinstance(raw_ops, list):
        return [], [], ["Operation list missing or invalid." if lang == "en" else "Liste d'opérations absente ou invalide."]
    for i, op0 in enumerate(raw_ops[:60]):
        if not isinstance(op0, dict) or op0.get("op") not in ops_mod.HANDLERS:
            kind0 = op0.get("op") if isinstance(op0, dict) else op0
            warns.append(f"Operation {i + 1} dropped: unknown type ({kind0!r})." if lang == "en" else f"Opération {i + 1} retirée : type inconnu ({kind0!r}).")
            continue
        op = dict(op0)
        before = work.onto.model_copy(deep=True)
        res = Resolver(work.onto)
        try:
            _normalize(op, res, work.onto)
        except ValueError as exc:
            warns.append(f"Operation {i + 1} ({op0['op']}) dropped: {_en(exc)}" if lang == "en" else f"Opération {i + 1} ({op0['op']}) retirée : {exc}")
            continue
        trial = work.model_copy(deep=True)
        r = ops_mod.apply_ops(trial, [op])
        if r.errors:
            warns.append(f"Operation {i + 1} ({op['op']}) dropped: {_en(r.errors[0]['message'])}" if lang == "en"
                         else f"Opération {i + 1} ({op['op']}) retirée : {r.errors[0]['message']}")
            continue
        warns += [w for w in ([_en(x) for x in r.warnings] if lang == "en" else r.warnings) if w not in warns]
        work = trial
        kept.append(op)
        preview.append({"op": op["op"], "text": describe(op, before, work.onto, lang)})
    return kept, preview, warns


def _en(msg: Any) -> str:
    """Message d'erreur de validation (français, venant du moteur d'édition ou de `_normalize`) -> anglais."""
    from ..localize import tr
    return tr(str(msg), "en") or str(msg)


def _ref(res: Resolver, v: Any, kinds: tuple[str, ...], what: str, lang: str = "fr") -> str:
    iri = res.find(v, kinds)
    if not iri:
        if lang == "en":
            what_en = {"La classe parente": "The parent class", "La classe": "The class", "La propriété": "The property", "L'entité": "The entity"}.get(what, what)
            raise ValueError(f"{what_en} “{v}” not found in the ontology (nothing is invented)")
        raise ValueError(f"{what} « {v} » introuvable dans l'ontologie (rien n'est inventé)")
    return iri


def _normalize(op: dict, res: Resolver, onto: OntoModel) -> None:
    """Remplace les noms par des IRIs existantes ; fixe l'IRI des nouvelles entités sur l'IRI de base ; borne les champs."""
    k = op["op"]
    base = base_of(onto)
    if k in ("add_class", "add_object_property", "add_datatype_property"):
        raw = op.get("name") or (local_name(op["iri"]) if isinstance(op.get("iri"), str) else None) or op.get("label")
        name = pascal(str(raw)) if k == "add_class" else camel(str(raw or ""))
        if not name:
            raise ValueError("nom de la nouvelle entité manquant")
        op.pop("name", None)
        op["iri"] = base + name
        if res.find(op["iri"], ("class", "object", "data", "individual")) or ops_mod.kind_of(onto, op["iri"]):
            raise ValueError(f"« {name} » existe déjà")
    elif "iri" in op:
        op["iri"] = _ref(res, op["iri"], ("class", "object", "data"), "L'entité")
    if k == "add_class" and op.get("parent"):
        op["parent"] = _ref(res, op["parent"], ("class",), "La classe parente")
    if k == "add_subclass":
        op["parent"] = _ref(res, op.get("parent"), ("class",), "La classe parente")
    if k == "remove_subclass":
        op["parent"] = _ref(res, op.get("parent"), ("class",), "La classe parente")
    if k in ("add_object_property", "add_datatype_property", "set_domain_range"):
        for f in ("domain", "range"):
            if f not in op:
                continue
            vals = op[f] if isinstance(op[f], list) else [op[f]]
            is_data_range = f == "range" and (k == "add_datatype_property" or (k == "set_domain_range" and op["iri"] in onto.datatype_properties))
            out: list[str] = []
            for v in vals:
                if v in (None, ""):
                    continue
                out.append((xsd_iri(v) or "") if is_data_range else _ref(res, v, ("class",), "La classe"))
                if is_data_range and not out[-1]:
                    raise ValueError(f"type de données « {v} » inconnu")
            op[f] = out[0] if (k == "add_datatype_property" and f == "range" and out) else out
        if k == "add_datatype_property":
            op.setdefault("range", XSD + "string")
            if not op.get("domain"):
                raise ValueError("domaine manquant")
    if k in ("set_restriction", "remove_restriction"):
        op["property"] = _ref(res, op.get("property"), ("object", "data"), "La propriété")
        if op.get("filler"):
            fi = res.find(op["filler"], ("class",)) or xsd_iri(op["filler"])
            if not fi:
                raise ValueError(f"filler « {op['filler']} » introuvable")
            op["filler"] = fi
    if k in ("set_label", "set_comment"):
        op["text"] = str(op.get("text", ""))[:500]
        op.setdefault("lang", "fr")
    if k in ("move_node", "set_icon", "set_collapsed"):
        raise ValueError("opération de présentation non proposée par l'assistant")
    if k == "set_key" and isinstance(op.get("properties"), list):
        op["properties"] = [_ref(res, x, ("data",), "La propriété") for x in op["properties"]]


# ----------------------------------------------------------------------------- contexte -> texte pour le prompt
def _class_card(onto: OntoModel, iri: str) -> dict:
    c = onto.classes[iri]
    own = [{"name": local_name(i), "label": onto.label(i), "type": local_name(p.range[0]) if p.range else "string"}
           for i, p in onto.datatype_properties.items() if iri in p.domain]
    rel = [{"name": local_name(i), "label": onto.label(i), "to": ",".join(local_name(r) for r in p.range)}
           for i, p in onto.object_properties.items() if iri in p.domain]
    return {"class": local_name(iri), "label": onto.label(iri), "parents": [local_name(x) for x in c.sub_class_of],
            "dataProperties": own, "relations": rel,
            "restrictions": [f"{r.kind} {r.n if r.n is not None else ''} {local_name(r.property)}".replace("  ", " ") for r in c.restrictions]}


def selection_detail(project: Any, ctx: dict) -> Optional[dict]:
    sel = ctx.get("selection")
    if not isinstance(sel, dict) or not sel.get("id"):
        return None
    onto: OntoModel = project.onto
    res = Resolver(onto)
    iri = res.find(sel["id"])
    if iri and iri in onto.classes:
        return _class_card(onto, iri)
    if iri:
        p = onto.object_properties.get(iri) or onto.datatype_properties.get(iri)
        return {"property": local_name(iri), "label": onto.label(iri), "domain": [local_name(d) for d in p.domain],
                "range": [local_name(r) for r in p.range]}
    sh = project.shapes.shapes.get(sel["id"])
    if sh:
        return {"shape": sh.id, "targets": [local_name(t) for t in sh.targets.target_class],
                "properties": [{"path": local_name(ps.path.iri or ""), "min": ps.min_count, "max": ps.max_count, "datatype": local_name(ps.datatype or "")}
                               for ps in sh.properties][:30]}
    return {"kind": sel.get("kind"), "id": sel.get("id"), "label": sel.get("label")}


def schema_compact(onto: OntoModel) -> str:
    lines = [f"IRI de base : {base_of(onto)}"]
    for iri, c in list(onto.classes.items())[:80]:
        props = [f"{local_name(i)}:{local_name(p.range[0]) if p.range else 'string'}" for i, p in onto.datatype_properties.items() if iri in p.domain][:10]
        rels = [f"{local_name(i)}->{','.join(local_name(r) for r in p.range)}" for i, p in onto.object_properties.items() if iri in p.domain][:8]
        par = ",".join(local_name(x) for x in c.sub_class_of)
        lines.append(f"- {local_name(iri)} (« {onto.label(iri)} »){' < ' + par if par else ''} [{'; '.join(props + rels)}]")
    return "\n".join(lines)


# ----------------------------------------------------------------------------- shapes
SHAPE_FIELDS = {"min_count": int, "max_count": int, "min_length": int, "max_length": int, "min_inclusive": str, "max_inclusive": str,
                "min_exclusive": str, "max_exclusive": str, "pattern": str}
SHAPE_TXT = {"min_count": "au moins {v} valeur(s)", "max_count": "au plus {v} valeur(s)", "min_length": "longueur minimale {v}",
             "max_length": "longueur maximale {v}", "min_inclusive": "valeur minimale {v}", "max_inclusive": "valeur maximale {v}",
             "min_exclusive": "strictement supérieure à {v}", "max_exclusive": "strictement inférieure à {v}", "pattern": "format {v}"}


SHAPE_TXT_EN = {"min_count": "at least {v} value(s)", "max_count": "at most {v} value(s)", "min_length": "minimum length {v}",
                "max_length": "maximum length {v}", "min_inclusive": "minimum value {v}", "max_inclusive": "maximum value {v}",
                "min_exclusive": "strictly greater than {v}", "max_exclusive": "strictly less than {v}", "pattern": "format {v}"}


def validate_shape_patches(project: Any, raw: Any, lang: str = "fr") -> tuple[list[dict], list[dict], list[str]]:
    onto: OntoModel = project.onto
    res = Resolver(onto)
    out, prev, warns = [], [], []
    for i, p in enumerate(raw if isinstance(raw, list) else []):
        try:
            if not isinstance(p, dict):
                raise ValueError("invalid patch" if lang == "en" else "correctif invalide")
            cls = _ref(res, p.get("class"), ("class",), "La classe", lang)
            prop = _ref(res, p.get("property"), ("object", "data"), "La propriété", lang)
            cons: dict[str, Any] = {}
            for k, v in (p.get("constraints") or {}).items():
                if k not in SHAPE_FIELDS:
                    raise ValueError(f"constraint “{k}” not supported" if lang == "en" else f"contrainte « {k} » non gérée")
                if SHAPE_FIELDS[k] is int:
                    if isinstance(v, bool) or not isinstance(v, (int, float)) or int(v) != v or v < 0:
                        raise ValueError(f"“{k}” must be an integer ≥ 0" if lang == "en" else f"« {k} » doit être un entier ≥ 0")
                    v = int(v)
                else:
                    v = str(v)
                    if k == "pattern":
                        re.compile(v)
                    else:
                        float(v) if re.match(r"^-?\d", v) else None
                cons[k] = v
            if not cons:
                raise ValueError("no constraint" if lang == "en" else "aucune contrainte")
            msg = str(p.get("message") or "")[:200]
            out.append({"class": cls, "property": prop, "constraints": cons, **({"message": msg} if msg else {})})
            txt = ", ".join((SHAPE_TXT_EN if lang == "en" else SHAPE_TXT)[k].format(v=v) for k, v in cons.items())
            prev.append({"text": (f"Shape of {_nm(onto, cls, True)}: {_nm(onto, prop, True)} — {txt}" if lang == "en"
                                  else f"Shape de {_nm(onto, cls)} : {_nm(onto, prop)} — {txt}")})
        except (ValueError, re.error) as exc:
            warns.append(f"Constraint {i + 1} dropped: {exc}" if lang == "en" else f"Contrainte {i + 1} retirée : {exc}")
    return out, prev, warns


def apply_shape_patches(shapes: ShapesModel, onto: OntoModel, patches: list[dict]) -> int:
    """Applique les correctifs validés à ``shapes`` (en place) ; renvoie le nombre appliqué."""
    n = 0
    base = base_of(onto)
    for p in patches:
        node = next((s for s in shapes.shapes.values() if p["class"] in s.targets.target_class), None)
        if node is None:
            sid = base + local_name(p["class"]) + "Shape"
            node = NodeShape(id=sid)
            node.targets.target_class.append(p["class"])
            shapes.shapes[sid] = node
        ps = next((x for x in node.properties if x.path.kind == "predicate" and x.path.iri == p["property"]), None)
        if ps is None:
            ps = PropertyShape(id=f"{node.id}-{local_name(p['property'])}", path=Path(kind="predicate", iri=p["property"]))
            node.properties.append(ps)
        for k, v in p["constraints"].items():
            setattr(ps, k, v)
        if p.get("message"):
            ps.messages["fr"] = p["message"]
        n += 1
    return n


# ----------------------------------------------------------------------------- repli déterministe (français)
_NAME = r"([\w'’\-éèêëàâîïôöùûüç ]+?)"
_TYPES = r"(?:\s*\(?\s*(?:de\s+type|type|en|:)\s+([a-zéèû]+)\s*\)?)?"
_TYPES_EN = r"(?:\s*\(?\s*(?:of\s+type|type|as|:)\s+([a-z]+)\s*\)?)?"


def _split_sentence(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().strip(".!?")).strip()


def _dtype_of(word: Optional[str], unit: Optional[str]) -> str:
    if word and xsd_iri(word):
        return local_name(xsd_iri(word))  # type: ignore[arg-type]
    return "decimal" if unit else "string"


def _prop_ops(name: str, domain: str, word: Optional[str], unit: Optional[str], ll: str = "fr") -> list[dict]:
    dt = _dtype_of(word, unit)
    label = f"{name} ({unit})" if unit else name
    ops: list[dict] = [{"op": "add_datatype_property", "name": camel(name), "domain": [domain], "range": dt, "label": label, "lang": ll}]
    if unit:
        ops.append({"op": "set_comment", "iri": "@last", "text": f"Unit: {unit}" if ll == "en" else f"Unité : {unit}", "lang": ll})
    return ops


def _fix_last(ops: list[dict], onto: OntoModel) -> list[dict]:
    """Remplace le marqueur « @last » par le nom de la dernière entité ajoutée (résolu via son nom)."""
    last = None
    for o in ops:
        if o["op"].startswith("add_") and o["op"] != "add_subclass":
            last = o.get("name") or o.get("iri")
        elif o.get("iri") == "@last":
            o["iri"] = base_of(onto) + str(last)
    return ops


# ---- aide en contexte (L28) ----------------------------------------------------------------------------------------
HELP_MAP_PATH = FsPath(__file__).with_name("help_map.json")


@lru_cache(maxsize=1)
def help_map() -> dict[str, Any]:
    """Table écran -> section du guide (source unique, partagée avec le front)."""
    return json.loads(HELP_MAP_PATH.read_text(encoding="utf-8"))["screens"]


# écran déclaré par le contexte (vocabulaire des écrans) -> clé de la table
_HELP_ALIASES = {"ontology": "editor", "list": "ontology-list", "dashboard": "dashboard", "tableau": "dashboard", "ontologie": "editor"}


def help_section(screen: Any, lang: str = "fr") -> dict[str, Any]:
    """Page, ancre, titre et résumé du guide pour l'écran courant ; section générale si l'écran est inconnu."""
    tbl = help_map()
    key = str(screen or "")
    key = _HELP_ALIASES.get(key, key)
    e = tbl.get(key) or tbl["default"]
    ll = "en" if lang == "en" else "fr"
    return {"screen": key if key in tbl else "default", "page": e["page"], "anchor": e["anchor"], "title": e["title"][ll], "summary": e["summary"][ll]}


_HELP_FR = (r"(?:(?:j['’]ai\s+besoin\s+d['’])?l['’]\s*aide|aide(?:-moi)?|(?:à|a)\s+l['’]aide|documentation|doc|docs|manuel|mode\s+d['’]emploi|guide)"
            r"(?:\s+(?:sur|de|pour|à\s+propos\s+de)?\s*(?:cet|cette|ce|l['’])?\s*(?:écran|ecran|page|ici))?"
            r"|(?:ouvre|affiche|montre|donne(?:-moi)?)\s+(?:moi\s+)?(?:la\s+|l['’]\s*)?(?:doc|docs|documentation|aide|manuel|guide)(?:\s+(?:de\s+)?(?:cet|cette|ce)?\s*(?:écran|ecran|page|ici))?"
            r"|comment\s+(?:ça|ca|cela)\s+(?:marche|fonctionne)(?:\s+(?:ici|sur\s+(?:cet|cette)\s+(?:écran|ecran|page)))?"
            r"|comment\s+(?:on\s+)?(?:s['’]en\s+sert|l['’]utilise|utiliser\s+(?:cet\s+(?:écran|ecran)|ça|ca|ceci))"
            r"|(?:à|a)\s+quoi\s+(?:sert|ça\s+sert|ca\s+sert)\s+(?:cet\s+(?:écran|ecran)|cette\s+page|ceci|ça|ca)")
_HELP_EN = (r"(?:help(?:\s+me)?|docs?|documentation|manual|user\s+guide|guide)(?:\s+(?:on|about|for|with)\s+(?:this\s+)?(?:screen|page|here))?"
            r"|(?:open|show|display|give\s+me|get)\s+(?:me\s+)?(?:the\s+)?(?:docs?|documentation|help|manual|user\s+guide)(?:\s+(?:for|of|on)\s+(?:this\s+)?(?:screen|page|here))?"
            r"|how\s+(?:does|do)\s+(?:this|it|that)(?:\s+(?:screen|page))?\s+work(?:\s+here)?"
            r"|how\s+(?:do\s+i|can\s+i|to)\s+use\s+(?:this|it)(?:\s+(?:screen|page))?"
            r"|what(?:['’]s|\s+is)\s+(?:this|that)\s+(?:screen|page)(?:\s+for)?")


def is_help_request(text: str) -> bool:
    """Intention « aide » (fr / en) : aide, doc, comment ça marche ici, help, how does this work…"""
    t = _split_sentence(text)
    return bool(re.fullmatch(_HELP_FR, t, re.I) or re.fullmatch(_HELP_EN, t, re.I))


# ---- langue de la conversation ------------------------------------------------------------------------------------
_EN_WORDS = {"add", "create", "make", "set", "delete", "remove", "drop", "open", "show", "find", "list", "give", "which", "what", "how", "many", "the", "a",
             "an", "to", "of", "under", "with", "whose", "where", "in", "on", "for", "class", "property", "required", "mandatory", "constraint", "shape",
             "subclass", "go", "display", "me", "is", "are", "has", "have", "that", "from", "and", "help", "does", "this", "work", "here", "screen"}
_FR_WORDS = {"ajoute", "ajouter", "crée", "cree", "créer", "creer", "rends", "rendre", "supprime", "supprimer", "efface", "retire", "ouvre", "affiche", "cherche",
             "trouve", "liste", "donne", "quels", "quelles", "combien", "le", "la", "les", "une", "un", "des", "du", "de", "sous", "avec", "dont", "classe",
             "propriété", "propriete", "obligatoire", "contrainte", "pour", "sur", "dans", "et", "est", "sont", "à"}


def looks_english(text: str) -> bool:
    toks = re.findall(r"[a-zà-ÿ’']+", text.lower())
    en = sum(1 for t in toks if t in _EN_WORDS)
    fr = sum(1 for t in toks if t in _FR_WORDS)
    return en > fr


def reply_lang(message: str) -> str:
    """Langue de la réponse : anglais si le message est en anglais ou si l'assistant / l'interface sont réglés en anglais."""
    from ..localize import ui_lang
    from ..settings import store
    try:
        assistant = store.load(persist=False).language.assistant
    except Exception:  # noqa: BLE001
        assistant = "fr"
    return "en" if (looks_english(message) or assistant == "en" or ui_lang() == "en") else "fr"


def label_lang_for(message: str) -> str:
    """Langue du libellé créé : celle du message (un libellé @en pour une demande en anglais)."""
    return "en" if looks_english(message) else "fr"


def _bilingual(onto: OntoModel) -> bool:
    """Convention de l'ontologie : la majorité des entités portent à la fois un libellé fr et en."""
    ents = [e for coll in (onto.classes, onto.object_properties, onto.datatype_properties) for e in coll.values() if e.labels]
    return bool(ents) and sum(1 for e in ents if "fr" in e.labels and "en" in e.labels) * 2 > len(ents)


# Textes de réponse du repli déterministe, par langue.
MSG: dict[str, dict[str, str]] = {
    "fr": {
        "shape_missing_prop": "la propriété « {x} »", "shape_missing_shape": "la shape « {x} »",
        "shape_not_found": "Je ne retrouve pas {what} dans le projet.",
        "shape_ok": "Je propose cette contrainte ({txt}).",
        "parent_missing": "La classe parente « {p} » n'existe pas : « {n} » est ajoutée sans parent.",
        "class_reply": "Je propose d'ajouter la classe « {n} »", "class_under": " sous « {p} »",
        "class_prop": " avec la propriété « {p} »{u}.", "class_end": " Vérifiez l'aperçu puis appliquez.", "unit_in": " en {u}",
        "class_not_found": "Je ne trouve pas la classe « {c} ». Précisez son nom ou sélectionnez-la d'abord.",
        "prop_reply": "Je propose d'ajouter la propriété « {p} » à « {c} ».",
        "prop_not_found": "Je ne trouve pas la propriété « {p} ».", "which_class": "Sur quelle classe rendre cette propriété obligatoire ?",
        "req_reply": "Je propose de rendre « {p} » obligatoire pour « {c} » (au moins 1 valeur).",
        "del_not_found": "Je ne trouve pas « {t} » dans l'ontologie.",
        "del_reply": "Je propose de supprimer « {t} ». Les axiomes qui s'y rattachent sont retirés aussi : relisez l'aperçu.",
        "nav_reply": "Voici le raccourci.", "nav_summary": "Ouvrir : {s}",
        "doc_reply": "Voici la section du guide qui décrit l'écran « {t} ».",
        "query_reply": "Je transforme votre question en requête guidée, modifiable dans l'écran Requêtes.",
        "label_hint": "Aucun libellé français n'a été créé pour « {n} » : ajoutez-le si l'ontologie est bilingue.",
        "help": "Sans fournisseur LLM je comprends des demandes simples : « ajoute la classe Pneu sous Pièce », « ajoute la propriété pression à Pneu », "
                "« rends immatriculation obligatoire », « supprime Pneu », « ajoute une contrainte min 0 sur kilométrage dans la shape VehicleShape », "
                "« cherche les véhicules dont … ». Configurez un fournisseur dans Paramètres pour le reste.",
    },
    "en": {
        "shape_missing_prop": "the property “{x}”", "shape_missing_shape": "the shape “{x}”",
        "shape_not_found": "I can't find {what} in the project.",
        "shape_ok": "I suggest this constraint ({txt}).",
        "parent_missing": "The parent class “{p}” does not exist: “{n}” is added without a parent.",
        "class_reply": "I suggest adding the class “{n}”", "class_under": " under “{p}”",
        "class_prop": " with the property “{p}”{u}.", "class_end": " Check the preview, then apply.", "unit_in": " in {u}",
        "class_not_found": "I can't find the class “{c}”. Give its name or select it first.",
        "prop_reply": "I suggest adding the property “{p}” to “{c}”.",
        "prop_not_found": "I can't find the property “{p}”.", "which_class": "On which class should this property be required?",
        "req_reply": "I suggest making “{p}” required for “{c}” (at least 1 value).",
        "del_not_found": "I can't find “{t}” in the ontology.",
        "del_reply": "I suggest deleting “{t}”. The axioms attached to it are removed too: review the preview.",
        "nav_reply": "Here is the shortcut.", "nav_summary": "Open: {s}",
        "doc_reply": "Here is the guide section that describes the “{t}” screen.",
        "query_reply": "I'm turning your question into a guided query, which you can edit in the Queries screen.",
        "label_hint": "No French label was created for “{n}”: add one if the ontology is bilingual.",
        "help": "Without an LLM provider I understand simple requests: “add the class Tyre under Part with a property pressure in bar”, "
                "“add the property pressure to Tyre”, “make licensePlate required”, “delete Tyre”, "
                "“add a min constraint 0 on mileage in shape VehicleShape”, “find the vehicles whose …”, “open the shapes”. "
                "Configure a provider in Settings for anything else.",
    },
}

_KIND_RX = r"(min|max|minimum|maximum|motif|pattern)"
# écrans reconnus par « ouvre … » / « open … » (clé = nom normalisé sans accents ni espaces)
SCREENS = {"shapes": "shapes", "shape": "shapes", "requetes": "requetes", "queries": "requetes", "query": "requetes", "editeur": "ontologie",
           "editor": "ontologie", "graphe": "ontologie", "graph": "ontologie", "ontologie": "ontologie", "ontology": "ontologie", "diagram": "ontologie",
           "tableaudebord": "tableau", "tableau": "tableau", "dashboard": "tableau", "exports": "exports", "export": "exports", "analyse": "analyse",
           "analysis": "analyse", "conformite": "conformite", "conformance": "conformite", "compliance": "conformite", "parametres": "parametres",
           "settings": "parametres", "preferences": "parametres", "modele": "modele", "model": "modele", "targetmodel": "modele", "assistant": "assistant",
           "shacl": "shacl", "versions": "versions", "version": "versions", "list": "ontologie-liste", "ontologylist": "ontologie-liste", "listview": "ontologie-liste", "vueliste": "ontologie-liste"}


_VER_SHOW = re.compile(r"^(?:quelles?(?: sont)?(?: les)? versions?(?: [\w' ]+)?|quelle version(?: [\w' ]+)?|versions?|(?:donne|affiche|montre)(?:-moi| moi)? (?:les|mes) versions?(?: [\w' ]+)?|"
                       r"which versions?(?: [\w' ]+)?|what versions?(?: [\w' ]+)?|what(?:'s| is| are) (?:the |my )?(?:target )?versions?(?: [\w' ]+)?|show (?:me )?(?:the |my )?versions?(?: [\w' ]+)?)$")
_VER_UPDATE = re.compile(r"^(?:mets?|mettre) a jour (?:les |mes )?versions?(?: cibl\w+| du projet| recommandees?)?$|^applique[rz]? (?:les )?versions? recommandees?$|"
                         r"^(?:update|upgrade|bump) (?:the |my )?(?:target )?versions?(?: to (?:the )?recommended(?: ones)?)?$|^apply (?:the )?recommended versions?$")


def _ascii_low(text: str) -> str:
    t = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    return re.sub(r"\s+", " ", re.sub(r"[?!.;]+$", "", t.strip())).strip()


def _versions_intent(project: Any, message: str, lang: str) -> dict[str, Any]:
    """« quelles versions ? » / « which versions » (réponse + action d'ouverture) et « mets à jour les versions » (action confirmée par l'utilisateur)."""
    from .. import standards
    low = _ascii_low(message)
    en = lang == "en"
    upd = bool(_VER_UPDATE.match(low))
    if not upd and not _VER_SHOW.match(low):
        return {}
    explicit = dict(getattr(project, "target_versions", None) or {})
    rows = standards.describe(explicit, lang)
    chk = standards.check(explicit, lang)
    open_act = {"kind": "navigate", "screen": "versions", "summary": "Open the versions" if en else "Ouvrir les versions"}
    if upd:
        patch = chk["recommended"]
        if not patch:
            return {"reply": "The project versions already match the recommended ones. Nothing to change." if en else
                    "Les versions du projet sont déjà les recommandées. Rien à changer.", "actions": [open_act], "warnings": []}
        eff = chk["versions"]
        fam = {r["key"]: r["family"] for r in rows}
        changes = [{"key": k, "family": fam[k], "from": eff[k], "to": v} for k, v in patch.items()]
        txt = ("I suggest applying the recommended versions: " if en else "Je propose d'appliquer les versions recommandées : ") + \
              ", ".join(f"{c['family']} {c['from']} → {c['to']}" for c in changes) + (". Check, then apply." if en else ". Vérifiez, puis appliquez.")
        return {"reply": txt, "actions": [{"kind": "versions", "changes": changes}], "warnings": []}
    parts = [f"{r['family']} {r['value']} ({r['status']}" + (", " + ("project" if en else "projet") if r["pinned"] else (", default" if en else ", défaut")) + ")" for r in rows]
    txt = ("Versions targeted by this project: " if en else "Versions ciblées par ce projet : ") + " · ".join(parts) + "."
    gaps = [g for g in chk["gaps"] if g["severity"] in ("warning", "error")]
    if gaps:
        txt += ("\n\nPoints to watch: " if en else "\n\nPoints d'attention : ") + " ".join(
            g["message"] + (" " + g["recommendation"]["message"] if g.get("recommendation") else "") for g in gaps)
    return {"reply": txt, "actions": [open_act], "warnings": []}


def deterministic(project: Any, message: str, ctx: dict, lang: str = "fr") -> dict[str, Any]:
    """Intentions simples, en français ou en anglais. -> {reply, actions(brutes), warnings} ou {} si aucune intention reconnue.

    ``lang`` : langue des textes de réponse (« en » si le message est en anglais ou si l'assistant / l'interface sont en anglais) ;
    le libellé des entités créées suit la langue du message."""
    vi = _versions_intent(project, message, lang)
    if vi:
        return vi
    onto: OntoModel = project.onto
    res = Resolver(onto)
    m = _split_sentence(message)
    low = m.lower()
    M = MSG["en" if lang == "en" else "fr"]
    ll = label_lang_for(message)
    sel = ctx.get("selection") if isinstance(ctx.get("selection"), dict) else None
    sel_iri = res.find(sel["id"]) if sel and sel.get("id") else None
    warns: list[str] = []

    def cls_of(text: Optional[str]) -> Optional[str]:
        if text and re.fullmatch(r"(?i)(cette classe|elle|celle-ci|la classe sélectionnée|this class|it|this one|the selected class|the current class)", text.strip()):
            return sel_iri if sel_iri in onto.classes else None
        return res.find(text, ("class",)) if text else None

    def label_warn(name: str) -> None:
        # libellé créé en anglais alors que l'ontologie est bilingue et que les libellés affichés sont en français
        if ll == "en" and _bilingual(onto):
            try:
                from ..settings import store
                show = store.load(persist=False).language.labels
            except Exception:  # noqa: BLE001
                show = "fr"
            if show == "fr":
                warns.append(MSG["en" if lang == "en" else "fr"]["label_hint"].format(n=name))

    # « ajoute une contrainte min n sur p dans la shape S » / « add a min constraint 0 on p in shape S »
    mm = re.search(rf"contrainte\s+{_KIND_RX}\s+(\S+)\s+(?:sur|pour)\s+(?:la\s+propri[ée]t[ée]\s+)?{_NAME}\s+(?:dans|de|pour)\s+(?:la\s+)?(?:shape|forme)\s+{_NAME}$", m, re.I)
    mm_en = re.search(rf"^(?:add|create|set)\s+(?:an?\s+)?(?:{_KIND_RX}\s+(?:value\s+)?(\S+)\s+constraint|constraint\s+{_KIND_RX}\s+(?:of\s+)?(\S+)|{_KIND_RX}\s+constraint\s+(?:of\s+|=\s*)?(\S+))"
                      rf"\s+(?:on|for)\s+(?:the\s+property\s+)?{_NAME}\s+(?:in|of|for|on)\s+(?:the\s+)?shape\s+{_NAME}$", m, re.I)
    if mm or mm_en:
        if mm:
            kind, val, pname, sname = mm.group(1).lower(), mm.group(2), mm.group(3), mm.group(4)
        else:
            g = mm_en.groups()  # type: ignore[union-attr]
            kind, val = next((g[i].lower(), g[i + 1]) for i in (0, 2, 4) if g[i])
            pname, sname = g[6], g[7]
        prop = res.find(pname, ("object", "data"))
        cls = res.find(re.sub(r"(?i)shape$", "", sname).strip(), ("class",))
        if not cls:
            sh = next((s for s in project.shapes.shapes.values() if norm(local_name(s.id)) in (norm(sname), norm(sname) + "shape")), None)
            cls = sh.targets.target_class[0] if sh and sh.targets.target_class else None
        if not prop or not cls:
            what = M["shape_missing_prop"].format(x=pname) if not prop else M["shape_missing_shape"].format(x=sname)
            return {"reply": M["shape_not_found"].format(what=what), "actions": [], "warnings": []}
        dp = onto.datatype_properties.get(prop)
        numeric = bool(dp and dp.range and local_name(dp.range[0]) not in ("string", "boolean", "anyURI"))
        key = ("pattern" if kind in ("motif", "pattern") else ("min_inclusive" if numeric else "min_count") if kind.startswith("min")
               else ("max_inclusive" if numeric else "max_count"))
        txt = (SHAPE_TXT_EN if lang == "en" else SHAPE_TXT)[key].format(v=val)
        return {"reply": M["shape_ok"].format(txt=txt),
                "actions": [{"kind": "shapes", "patches": [{"class": cls, "property": prop, "constraints": {key: val if key in ("pattern",) or "inclusive" in key else int(val) if val.isdigit() else val}}]}], "warnings": []}

    # « ajoute la classe X [sous Y] [avec une propriété p [en unité] [de type T]] » / « add the class X under Y with a property p in bar »
    mm = re.match(rf"^(?:ajoute|cr[ée]e|ajouter|cr[ée]er)\s+(?:une\s+|la\s+|le\s+)?(?:nouvelle\s+)?(?:classe|concept)\s+{_NAME}(?:\s+(?:sous|enfant de|sous-classe de|sous la classe|héritant de)\s+(?:la\s+classe\s+)?{_NAME})?(?:\s+(?:avec|et)\s+(?:une|la)\s+propri[ée]t[ée]\s+{_NAME}(?:\s+en\s+(\w+))?{_TYPES})?$", m, re.I)
    if not mm:
        mm = re.match(rf"^(?:add|create)\s+(?:an?\s+|the\s+)?(?:new\s+)?(?:class|concept)\s+{_NAME}(?:\s+(?:under|below|beneath|as\s+(?:a\s+)?(?:sub-?class|child)\s+of|(?:sub-?class|child)\s+of|inheriting\s+from|extending)\s+(?:the\s+)?(?:class\s+)?{_NAME})?"
                      rf"(?:\s+(?:with|and)\s+(?:an?\s+|the\s+)?(?:new\s+)?(?:data\s+)?property\s+{_NAME}(?:\s+in\s+(\w+))?{_TYPES_EN})?$", m, re.I)
    if mm:
        name, parent_t, pname, unit, typ = mm.group(1).strip(), mm.group(2), mm.group(3), mm.group(4), mm.group(5)
        if pname and typ is None and unit is None:
            mt = re.match(rf"^{_NAME}\s+(?:de\s+type|type|of\s+type)\s+(\w+)$", pname)
            if mt:
                pname, typ = mt.group(1), mt.group(2)
        ops: list[dict] = [{"op": "add_class", "name": pascal(name), "label": name[:1].upper() + name[1:], "lang": ll}]
        if parent_t:
            parent = res.find(parent_t.strip(), ("class",))
            if parent:
                ops[0]["parent"] = parent
            else:
                warns.append(M["parent_missing"].format(p=parent_t.strip(), n=name))
        if pname:
            ops += _prop_ops(pname.strip(), base_of(onto) + pascal(name), typ, unit, ll)
            ops[-1 if not unit else -2]["domain"] = [base_of(onto) + pascal(name)]
        ops = _fix_last(ops, onto)
        txt = M["class_reply"].format(n=name)
        if ops[0].get("parent"):
            txt += M["class_under"].format(p=onto.label(ops[0]["parent"], "en" if lang == "en" else "fr"))
        txt += M["class_prop"].format(p=pname.strip(), u=M["unit_in"].format(u=unit) if unit else "") if pname else "."
        label_warn(name)
        return {"reply": txt + M["class_end"], "actions": [{"kind": "ops", "ops": ops}], "warnings": warns}

    # « ajoute la propriété p [(type)] [en unité] à X » / « add the property p to X »
    mm = re.match(rf"^(?:ajoute|cr[ée]e|ajouter|cr[ée]er)\s+(?:une\s+|la\s+)?(?:nouvelle\s+)?propri[ée]t[ée]\s+{_NAME}(?:\s+en\s+(\w+))?{_TYPES}\s+(?:à|a|sur|pour|dans)\s+(?:la\s+classe\s+|l[ae']\s*)?{_NAME}$", m, re.I)
    if not mm:
        mm = re.match(rf"^(?:add|create)\s+(?:an?\s+|the\s+)?(?:new\s+)?(?:data\s+)?property\s+{_NAME}(?:\s+in\s+(\w+))?{_TYPES_EN}\s+(?:to|on|for|in)\s+(?:the\s+class\s+|the\s+|a\s+|an\s+)?{_NAME}$", m, re.I)
    if mm:
        pname, unit, typ, ctext = mm.group(1).strip(), mm.group(2), mm.group(3), mm.group(4).strip()
        if typ is None:
            mt = re.match(rf"^{_NAME}\s+(?:de\s+type|type|of\s+type)\s+(\w+)$", pname)
            if mt:
                pname, typ = mt.group(1), mt.group(2)
        cls = cls_of(ctext)
        if not cls:
            return {"reply": M["class_not_found"].format(c=ctext), "actions": [], "warnings": []}
        ops = _fix_last(_prop_ops(pname, cls, typ, unit, ll), onto)
        label_warn(pname)
        return {"reply": M["prop_reply"].format(p=pname, c=onto.label(cls, "en" if lang == "en" else "fr")), "actions": [{"kind": "ops", "ops": ops}], "warnings": warns}

    # « rends p obligatoire [dans|pour|sur X] » / « make p required [in X] »
    mm = re.match(rf"^(?:rends|rend|rendre|met|mets)\s+(?:la\s+propri[ée]t[ée]\s+)?{_NAME}\s+obligatoire(?:\s+(?:dans|pour|sur|de)\s+(?:la\s+classe\s+|l[ae']\s*)?{_NAME})?$", m, re.I)
    if not mm:
        mm = re.match(rf"^(?:make|set|mark)\s+(?:the\s+property\s+)?{_NAME}\s+(?:as\s+)?(?:required|mandatory)(?:\s+(?:in|for|on|of)\s+(?:the\s+class\s+|the\s+)?{_NAME})?$", m, re.I)
    if mm:
        prop = res.find(mm.group(1), ("object", "data"))
        if not prop:
            return {"reply": M["prop_not_found"].format(p=mm.group(1)), "actions": [], "warnings": []}
        cls = cls_of(mm.group(2)) if mm.group(2) else (sel_iri if sel_iri in onto.classes else None)
        if not cls:
            p = onto.object_properties.get(prop) or onto.datatype_properties.get(prop)
            cls = p.domain[0] if p and p.domain else None
        if not cls:
            return {"reply": M["which_class"], "actions": [], "warnings": []}
        lb = "en" if lang == "en" else "fr"
        return {"reply": M["req_reply"].format(p=onto.label(prop, lb), c=onto.label(cls, lb)),
                "actions": [{"kind": "ops", "ops": [{"op": "set_restriction", "iri": cls, "property": prop, "kind": "min", "n": 1}]}], "warnings": []}

    # « supprime X » / « delete X »
    mm = re.match(rf"^(?:supprime|supprimer|efface|retire|enl[èe]ve)\s+(?:la\s+classe\s+|la\s+propri[ée]t[ée]\s+|la\s+relation\s+|l[ae']\s*)?{_NAME}$", m, re.I)
    if not mm:
        mm = re.match(rf"^(?:delete|remove|drop|erase)\s+(?:the\s+)?(?:class\s+|property\s+|relation(?:ship)?\s+)?{_NAME}$", m, re.I)
    if mm:
        t = mm.group(1).strip()
        iri = sel_iri if re.fullmatch(r"(?i)(cette classe|cet élément|ceci|celle-ci|this class|this element|this|it|this one)", t) else res.find(t)
        if not iri:
            return {"reply": M["del_not_found"].format(t=t), "actions": [], "warnings": []}
        return {"reply": M["del_reply"].format(t=onto.label(iri, "en" if lang == "en" else "fr")),
                "actions": [{"kind": "ops", "ops": [{"op": "delete_entity", "iri": iri}]}], "warnings": []}

    # aide en contexte : « aide », « comment ça marche ici », « doc » / « help », « how does this work »
    if is_help_request(m):
        sec = help_section(ctx.get("screen"), lang)
        return {"reply": M["doc_reply"].format(t=sec["title"]), "actions": [{"kind": "help", "screen": sec["screen"]}], "warnings": []}

    # navigation : « ouvre les shapes » / « open the shapes »
    mm = re.match(r"^(?:ouvre|va|aller|affiche)\s+(?:à|a|au|aux|sur)?\s*(?:les\s+|l[ae']\s*|le\s+|la\s+)?(.+)$", m, re.I)
    if not mm:
        mm = re.match(r"^(?:open|go\s+to|goto|show|display|navigate\s+to|take\s+me\s+to|switch\s+to)\s+(?:the\s+|my\s+)?(.+?)(?:\s+(?:screen|page|tab|view))?$", m, re.I)
    if mm:
        scr = SCREENS.get(norm(mm.group(1)))
        if scr:
            return {"reply": M["nav_reply"], "actions": [{"kind": "navigate", "screen": scr, "summary": M["nav_summary"].format(s=mm.group(1).strip())}], "warnings": []}

    # requête : « cherche les X dont … » / « find the X whose … »
    if (re.match(r"^(?:cherche|trouve|liste|donne|affiche|montre|quels?|quelles?|combien)\b", low) and not low.startswith("affiche le")) or \
            re.match(r"^(?:find|search(?:\s+for)?|list|give\s+me|show(?:\s+me)?|display|get|which|what\s+(?:are|were)|how\s+many|who)\b", low):
        return {"reply": M["query_reply"], "actions": [{"kind": "guided_query", "question": m}], "warnings": []}
    return {}


# ----------------------------------------------------------------------------- LLM
AGENT_SYSTEM = """[TASK:agent]
Tu es Krakie, l'assistant d'OntoForge (conception d'ontologies OWL 2 destinées à un property graph Curiosity / Neo4j). Tu CONNAIS l'écran de l'utilisateur
et tu AGIS en proposant des actions que l'utilisateur validera : tu n'appliques jamais rien toi-même. Réponds en {LANG}, de façon brève.
Réponds par UN objet JSON : {"reply":"...","actions":[...],"warnings":[]}. Types d'actions :
- {"kind":"ops","summary":"...","ops":[...]} avec des opérations d'édition parmi :
  add_class{name,label,parent?}, add_subclass{iri,parent}, add_datatype_property{name,domain:[Classe],range:"string|integer|decimal|date|dateTime|boolean",label}, add_object_property{name,domain:[..],range:[..],label},
  set_restriction{iri,property,kind:"min|max|exactly|some|only",n}, set_domain_range{iri,domain?,range?}, set_label{iri,text,lang}, set_comment{iri,text,lang}, rename_entity{iri,name}, delete_entity{iri}.
  Désigne les entités EXISTANTES par leur nom local (celui du schéma ci-dessous) ; pour une NOUVELLE entité donne seulement « name » (l'IRI de base est ajoutée côté serveur). N'invente aucune entité existante.
- {"kind":"proposal","ontology":{format d'ontologie : classes[{name,label_fr,label_en,comment,parent}], object_properties[...], datatype_properties[...]}} pour un modèle plus large.
- {"kind":"shapes","patches":[{"class":"Classe","property":"propriété","constraints":{"min_count":1,"max_count":1,"min_inclusive":"0","pattern":"...","min_length":n}}]}
- {"kind":"guided_query","question":"question en français sur les données"}
- {"kind":"navigate","screen":"tableau|ontologie|shapes|requetes|analyse|exports|versions"}
Si la demande est une simple question, réponds sans action. Si elle est ambiguë, pose UNE question dans reply, sans action. Aucun texte hors du JSON.
"""


def _lang_name(lang: str) -> str:
    return "français" if lang == "fr" else "English"


def _ctx_text(project: Any, ctx: dict) -> str:
    extra = ctx.get("extra") if isinstance(ctx.get("extra"), dict) else {}
    parts = [f"ÉCRAN : {ctx.get('screen', 'inconnu')}", f"CIBLE : {ctx.get('target') or project.target}"]
    if ctx.get("perimeter"):
        parts.append(f"PÉRIMÈTRE : {ctx['perimeter']}")
    det = selection_detail(project, ctx)
    if det:
        parts.append("SÉLECTION :\n" + json.dumps(det, ensure_ascii=False))
    if extra:
        parts.append("DONNÉES DE L'ÉCRAN :\n" + json.dumps(extra, ensure_ascii=False, default=str)[:3000])
    return "\n".join(parts)


def _guided(project: Any, question: str, provider: Any, target: Optional[str], lang: str = "fr") -> dict[str, Any]:
    from ..queries import builder, nl
    from ..api.analysis import run_analysis
    from ..localize import tr_deep
    res = nl.interpret(question, project.onto, project.shapes, provider, lang, lang)
    try:
        gq = builder.GuidedQuery.model_validate(res["guided"])
        built = builder.build_all(gq, project.onto, run_analysis(project, target or project.target), project.onto.meta.prefixes)
        res.update(sparql=built.sparql, cypher=built.cypher, curiosity=built.curiosity, notes=built.notes, lossy=built.lossy)
    except Exception as exc:  # noqa: BLE001 — une requête non générable reste ouvrable dans l'écran Requêtes
        res.update(sparql=None, notes=[f"Génération impossible : {exc}"], lossy=True)
    for k in ("explanation", "notes", "warnings"):
        if k in res:
            res[k] = tr_deep(res[k], lang)
    return res


def build_actions(project: Any, raw_actions: Any, provider: Any, ctx: dict) -> tuple[list[dict], list[str]]:
    """Valide chaque action brute (LLM ou repli) -> actions finales {kind, payload, summary}."""
    from .convert import normalize_base, to_onto
    out: list[dict] = []
    warns: list[str] = []
    lang = ctx.get("_lang", "fr")
    en = lang == "en"
    for a in (raw_actions if isinstance(raw_actions, list) else [])[:6]:
        if not isinstance(a, dict):
            continue
        kind = a.get("kind")
        if kind == "ops":
            ops, preview, w = validate_ops(project, a.get("ops"), lang)
            warns += w
            if ops:
                out.append({"kind": "ops", "payload": {"ops": ops, "preview": preview},
                            "summary": str(a.get("summary") or "") or (f"{len(ops)} change(s) to the ontology" if en else f"{len(ops)} modification(s) de l'ontologie")})
        elif kind == "proposal":
            ont = a.get("ontology")
            if isinstance(ont, dict) and (ont.get("classes") or ont.get("object_properties") or ont.get("datatype_properties")):
                prop, w = to_onto(ont, normalize_base(base_of(project.onto)))
                warns += [_en(x) for x in w] if en else w
                out.append({"kind": "proposal", "payload": {"proposal": prop.model_dump(mode="json", by_alias=True)},
                            "summary": str(a.get("summary") or "") or ("Ontology proposal" if en else "Proposition d'ontologie")})
        elif kind == "shapes":
            patches, preview, w = validate_shape_patches(project, a.get("patches"), lang)
            warns += w
            if patches:
                out.append({"kind": "shapes", "payload": {"patches": patches, "preview": preview},
                            "summary": str(a.get("summary") or "") or (f"{len(patches)} shape constraint(s)" if en else f"{len(patches)} contrainte(s) de shape")})
        elif kind == "guided_query":
            q = str(a.get("question") or "").strip()
            if q:
                res = _guided(project, q, provider, ctx.get("target"), lang)
                out.append({"kind": "guided_query", "payload": json.loads(json.dumps({**res, "question": q}, default=str)),
                            "summary": str(res.get("explanation") or "")[:200] or ("Guided query" if en else "Requête guidée")})
        elif kind == "help":
            sec = help_section(ctx.get("screen") if ctx.get("screen") not in (None, "", "unknown") else a.get("screen"), lang)
            out.append({"kind": "help", "payload": {k: sec[k] for k in ("screen", "page", "anchor", "title")}, "summary": sec["summary"]})
        elif kind == "versions":  # L31 : le serveur recalcule les versions recommandées, la demande brute n'est jamais appliquée telle quelle
            from .. import standards
            explicit = dict(getattr(project, "target_versions", None) or {})
            chk = standards.check(explicit, lang)
            fam = {r["key"]: r["family"] for r in standards.describe(explicit, lang)}
            changes = [{"key": k, "family": fam[k], "from": chk["versions"][k], "to": v} for k, v in chk["recommended"].items()]
            if changes:
                out.append({"kind": "versions", "payload": {"changes": changes, "patch": chk["recommended"], "before": explicit,
                                                            "preview": [{"text": f"{c['family']} {c['from']} → {c['to']}"} for c in changes]},
                            "summary": f"{len(changes)} version(s) to update" if en else f"{len(changes)} version(s) à mettre à jour"})
        elif kind == "navigate":
            scr = str(a.get("screen") or "")
            if scr in {"tableau", "ontologie", "ontologie-liste", "shapes", "requetes", "analyse", "exports", "conformite", "shacl", "modele", "assistant", "parametres", "versions"}:
                out.append({"kind": "navigate", "payload": {"screen": scr}, "summary": str(a.get("summary") or (f"Open {scr}" if en else f"Ouvrir {scr}"))})
    return out, warns


def run(project: Any, messages: list[dict[str, Any]], context: dict[str, Any], provider_id: Optional[str] = None,
        attachments: Optional[list[dict[str, Any]]] = None) -> dict[str, Any]:
    from fastapi import HTTPException
    from . import service
    from .convert import extract_json
    from .providers import LLMError
    ctx = dict(context or {})
    msgs = [{"role": "assistant" if m.get("role") == "assistant" else "user", "content": str(m.get("content", ""))}
            for m in (messages or []) if str(m.get("content", "")).strip()][-service.MSG_LIMIT:]
    if not msgs or msgs[-1]["role"] != "user":
        raise HTTPException(status_code=422, detail="La conversation doit se terminer par un message de l'utilisateur.")
    last = msgs[-1]["content"]
    rl = reply_lang(last)  # langue de la réponse, des résumés d'actions et des avertissements
    ctx["_lang"] = rl
    try:
        p = service._provider(provider_id)
    except HTTPException:
        p = None  # aucun fournisseur exploitable : repli déterministe
    real = p is not None and p.configured and getattr(p, "name", "mock") != "mock"
    warns: list[str] = []

    from . import reasoning  # L32 : « raisonne », « vérifie la cohérence », « run the reasoner » (HermiT), avec ou sans LLM
    rz = reasoning.answer(project, last, rl)
    if rz is not None:
        actions, w = build_actions(project, rz["actions"], p, ctx)
        return {"reply": rz["reply"], "actions": actions, "proposal": None, "warnings": [*rz["warnings"], *w]}

    if real:
        lang = _lang_name(rl)
        user = _ctx_text(project, ctx) + "\n\nSCHÉMA DE L'ONTOLOGIE\n" + schema_compact(project.onto)[:CTX_MAX] + "\n\nDEMANDE\n" + last
        for a in attachments or []:
            user += f"\n--- PIÈCE JOINTE {a.get('name')} ---\n{str(a.get('content', ''))[:service.ATT_LIMIT]}"
        try:
            raw = p.complete(AGENT_SYSTEM.replace("{LANG}", lang), [*msgs[:-1], {"role": "user", "content": user}], 6000)
        except LLMError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from None
        try:
            data = extract_json(raw)
        except ValueError:
            return {"reply": raw.strip(), "actions": [], "proposal": None, "warnings": warns}
        actions, w = build_actions(project, data.get("actions"), p, ctx)
        warns += w + [str(x) for x in (data.get("warnings") or []) if x]
        if not actions and not data.get("reply"):
            det = deterministic(project, last, ctx, rl)
            if det:
                actions, w = build_actions(project, det["actions"], p, ctx)
                return {"reply": det["reply"], "actions": actions, "proposal": _prop(actions), "warnings": warns + w + det["warnings"]}
        return {"reply": str(data.get("reply") or ""), "actions": actions, "proposal": _prop(actions), "warnings": warns}

    det = deterministic(project, last, ctx, rl)
    if det:
        actions, w = build_actions(project, det["actions"], p, ctx)
        return {"reply": det["reply"], "actions": actions, "proposal": _prop(actions), "warnings": [*det["warnings"], *w]}
    # pas d'intention simple : conversation de conception classique (mock / squelettes), sinon aide
    try:
        r = service.chat(project, msgs, provider_id, attachments, rl)
    except HTTPException:
        r = {"reply": "", "proposal": None, "warnings": []}
    actions = []
    if r.get("proposal") is not None:
        pr = r["proposal"]
        actions.append({"kind": "proposal", "payload": {"proposal": pr.model_dump(mode="json", by_alias=True) if hasattr(pr, "model_dump") else pr},
                        "summary": "Ontology proposal" if rl == "en" else "Proposition d'ontologie"})
    reply = r.get("reply") or MSG[rl]["help"]
    return {"reply": reply, "actions": actions, "proposal": r.get("proposal"),
            "warnings": [_en(x) for x in r.get("warnings", [])] if rl == "en" else r.get("warnings", [])}


def _prop(actions: list[dict]) -> Any:
    return next((a["payload"]["proposal"] for a in actions if a["kind"] == "proposal"), None)
