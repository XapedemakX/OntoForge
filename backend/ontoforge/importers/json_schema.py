"""Import JSON Schema déterministe (L48) : objets → classes, propriétés → propriétés de données ou d'objet, ``required`` → minimum 1,
``$ref`` locaux → relations, ``enum`` / ``const`` → énumérations, ``allOf`` de références → sous-classes.

Aucun ``$ref`` n'est suivi sur le réseau ni sur le disque : une référence externe devient une classe « à compléter » (ou, si le fichier fait
partie du lot déposé, pointe sur sa classe). Bornes : taille (appelant), profondeur d'imbrication, nombre de nœuds, temps.
Mots-clés non traduits (``additionalProperties``, ``patternProperties``, ``if/then/else``, ``dependencies``…) : rapportés dans ``ignored``.
"""
from __future__ import annotations

import json
import os
import re
from typing import Any, Optional

from ..assistant.naming import pascal
from .ir import Draft, Entity, Prop, Rel
from .limits import MAX_DEPTH, MAX_ENUM, MAX_JSON_NODES, MAX_TABLES, Budget, ImportRefused

_STR_FORMATS = {"date-time": ("dateTime", None), "date": ("dateTime", "date"), "time": ("string", "time"), "duration": ("string", "duration"),
                "uri": ("anyURI", None), "uri-reference": ("anyURI", None), "iri": ("anyURI", None), "iri-reference": ("anyURI", None),
                "byte": ("base64Binary", None), "binary": ("base64Binary", None)}
_IGNORED_KW = ("additionalProperties", "patternProperties", "unevaluatedProperties", "propertyNames", "if", "then", "else", "dependencies",
               "dependentRequired", "dependentSchemas", "not", "minProperties", "maxProperties", "prefixItems", "contains", "unevaluatedItems")
_KEY_NAMES = re.compile(r"(?i)^(?:id|uuid|guid|identifier|(?:.*[_\s-])?id|.*Id)$")


def check_depth(text: str, limit: int) -> None:
    """Refuse un JSON trop imbriqué AVANT de l'analyser (l'analyseur standard est récursif)."""
    depth, i, n, instr, esc = 0, 0, len(text), False, False
    for ch in text:
        if instr:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                instr = False
            continue
        if ch == '"':
            instr = True
        elif ch in "[{":
            depth += 1
            if depth > limit:
                raise ImportRefused("too_deep", 422, max=limit)
        elif ch in "]}":
            depth -= 1


def load_json(text: str, budget: Budget) -> Any:
    check_depth(text, MAX_DEPTH)
    try:
        doc = json.loads(text, parse_constant=lambda c: (_ for _ in ()).throw(ValueError(c)))
    except RecursionError:
        raise ImportRefused("too_deep", 422, max=MAX_DEPTH) from None
    except ValueError as exc:
        raise ImportRefused("json_invalid", 422, detail=str(exc)[:120]) from None
    # nombre de nœuds (itératif)
    count, stack = 0, [doc]
    while stack:
        x = stack.pop()
        count += 1
        budget.tick()
        if count > MAX_JSON_NODES:
            raise ImportRefused("too_many_nodes", 413, max=MAX_JSON_NODES)
        if isinstance(x, dict):
            stack.extend(x.values())
        elif isinstance(x, list):
            stack.extend(x)
    return doc


def looks_like_json_schema(doc: Any) -> bool:
    if not isinstance(doc, dict) or "@context" in doc or "@graph" in doc:
        return False
    if "$schema" in doc and "json-schema" in str(doc["$schema"]):
        return True
    return any(k in doc for k in ("properties", "$defs", "definitions")) and (doc.get("type") in (None, "object") or "$defs" in doc or "definitions" in doc)


def _is_object(s: Any) -> bool:
    if not isinstance(s, dict):
        return False
    t = s.get("type")
    if t == "object" or (isinstance(t, list) and "object" in t):
        return True
    if "properties" in s:
        return True
    ao = s.get("allOf")
    return isinstance(ao, list) and any(_is_object(x) or (isinstance(x, dict) and "$ref" in x) for x in ao) and "type" not in s and bool(s.get("properties") or any(_is_object(x) for x in ao))


class _File:
    def __init__(self, idx: int, name: str, doc: dict):
        self.idx, self.name, self.doc = idx, name, doc
        self.defs: dict[str, Any] = {}
        for kw in ("$defs", "definitions"):
            if isinstance(doc.get(kw), dict):
                for k, v in doc[kw].items():
                    self.defs.setdefault(f"#/{kw}/{_ptr(k)}", v)
        self.entities: dict[str, str] = {}      # pointeur → clé d'entité
        self.prims: dict[str, Any] = {}         # pointeur → schéma primitif

    def key(self, ptr: str) -> str:
        return f"{self.idx}:{ptr}"


def _ptr(s: str) -> str:
    return s.replace("~", "~0").replace("/", "~1")


def parse_json_schema(files: list[tuple[str, str]], draft: Draft, options: dict[str, Any], budget: Budget) -> None:
    fl: list[_File] = []
    for i, (name, text) in enumerate(files):
        doc = load_json(text, budget)
        if not isinstance(doc, dict):
            raise ImportRefused("json_not_schema", 422, file=name)
        fl.append(_File(i, name, doc))
    by_base = {os.path.basename(f.name).lower(): f for f in fl}
    # --- phase 1 : classes
    for f in fl:
        root = f.doc
        if _is_object(root):
            title = root.get("title") if isinstance(root.get("title"), str) else None
            idn = re.sub(r"\.(?:schema\.)?json$", "", os.path.basename(str(root.get("$id") or "").rstrip("/")), flags=re.I) if isinstance(root.get("$id"), str) else ""
            stem = re.sub(r"\.(?:schema\.)?json$", "", os.path.basename(f.name), flags=re.I)
            cname = pascal(title or idn or stem or "Root")
            e = Entity(key=f.key("#"), name=cname, comment=str(root.get("description") or "")[:2000], source=f"schema {f.name}")
            _add(draft, e)
            f.entities["#"] = e.key
        for ptr, d in f.defs.items():
            if _is_object(d):
                nm = ptr.rsplit("/", 1)[-1].replace("~1", "/").replace("~0", "~")
                title = d.get("title") if isinstance(d.get("title"), str) else None
                e = Entity(key=f.key(ptr), name=pascal(title or nm), comment=str(d.get("description") or "")[:2000], source=f"{f.name} {ptr}")
                _add(draft, e)
                f.entities[ptr] = e.key
            elif isinstance(d, dict) and ("oneOf" in d or "anyOf" in d) and not d.get("type"):
                alts = d.get("oneOf") or d.get("anyOf")
                if isinstance(alts, list) and alts and all(isinstance(a, dict) and "$ref" in a for a in alts):
                    draft.ignore("json_union_def", f"{f.name} {ptr}")
                else:
                    f.prims[ptr] = d
            elif isinstance(d, (dict, bool)):
                f.prims[ptr] = d
    # --- phase 2 : propriétés
    for f in fl:
        ctx = _Ctx(f, by_base, draft, options, budget)
        if "#" in f.entities:
            ctx.fill(draft.entities[f.entities["#"]], f.doc, "#", 0)
        for ptr, k in list(f.entities.items()):
            if ptr != "#":
                ctx.fill(draft.entities[k], f.defs[ptr], ptr, 0)
        for kw in ("oneOf", "anyOf"):
            if kw in f.doc and not _is_object(f.doc) and "#" not in f.entities and not f.entities:
                draft.ignore("json_union_def", f"{f.name} {kw}")
    if not draft.entities:
        draft.notice("json_no_classes", "warning", None)
    for e in draft.entities.values():
        if e.kind != "stub":
            _guess_key(e, draft)


def _add(draft: Draft, e: Entity) -> None:
    if len(draft.entities) >= MAX_TABLES:
        raise ImportRefused("too_many_tables", 413, max=MAX_TABLES)
    draft.entities[e.key] = e


def _guess_key(e: Entity, draft: Draft) -> None:
    if e.keys or e.parents:
        return
    for p in e.props:
        if p.required and not p.many and p.xsd in ("string", "integer", "anyURI") and _KEY_NAMES.match(p.key) and not p.enum:
            e.keys.append([p.key])
            e.assumed_key = True
            draft.notice("assumed_key", "review", e.name, entity=e.name, column=p.key)
            return
    draft.notice("no_key_candidate", "review", e.name, entity=e.name)


class _Ctx:
    def __init__(self, f: _File, by_base: dict[str, _File], draft: Draft, options: dict[str, Any], budget: Budget):
        self.f, self.by_base, self.d, self.o, self.b = f, by_base, draft, options, budget
        self.pattern_noted = False

    # ---- références ----------------------------------------------------------------------------
    def resolve(self, ref: str, hops: int = 0) -> tuple[str, Any]:
        """('entity', clé) | ('prim', schéma) | ('external', nom) | ('unresolved', ref)."""
        if not isinstance(ref, str) or len(ref) > 512:
            return "unresolved", ref
        if ref.startswith("#"):
            if ref == "#":
                k = self.f.entities.get("#")
                return ("entity", k) if k else ("unresolved", ref)
            k = self.f.entities.get(ref)
            if k:
                return "entity", k
            if ref in self.f.prims:
                prim = self.f.prims[ref]
                if isinstance(prim, dict) and "$ref" in prim and hops < 8:
                    return self.resolve(prim["$ref"], hops + 1)
                return "prim", prim
            return "unresolved", ref
        base, _, frag = ref.partition("#")
        # référence vers un autre fichier, URL comprise : cherchée par son nom parmi les fichiers déposés, jamais téléchargée
        # (L52 : la condition « pas une URL … or True » était toujours vraie ; comportement conservé, voir docs/dev/14)
        other = self.by_base.get(os.path.basename(base).lower())
        if other is not None:
            ptr = "#" + frag if frag else "#"
            k = other.entities.get(ptr)
            if k:
                return "entity", k
            if ptr in other.prims:
                return "prim", other.prims[ptr]
        return "external", ref

    def external_stub(self, ref: str) -> str:
        last = re.sub(r"\.(?:schema\.)?json$", "", os.path.basename(ref.partition("#")[0].rstrip("/")), flags=re.I)
        frag = ref.partition("#")[2].rsplit("/", 1)[-1]
        nm = pascal(frag or last or "External")
        key = "ext:" + ref.lower()
        if key not in self.d.entities:
            self.d.entities[key] = Entity(key=key, name=nm, source=f"external reference {ref[:120]}", kind="stub")
            self.d.notice("external_ref", "warning", nm, ref=ref[:120])
        return key

    # ---- remplissage ---------------------------------------------------------------------------
    def fill(self, e: Entity, s: Any, ptr: str, depth: int) -> None:
        if depth > MAX_DEPTH:
            raise ImportRefused("too_deep", 422, max=MAX_DEPTH)
        if not isinstance(s, dict):
            return
        self.b.tick()
        required = set(x for x in (s.get("required") or []) if isinstance(x, str)) if isinstance(s.get("required"), list) else set()
        for part in (s.get("allOf") or []) if isinstance(s.get("allOf"), list) else []:
            if not isinstance(part, dict):
                continue
            if "$ref" in part:
                kind, val = self.resolve(part["$ref"])
                if kind == "entity" and val != e.key and val not in e.parents:
                    e.parents.append(val)
                else:
                    self.d.ignore("json_keyword", f"allOf → {str(part['$ref'])[:80]}")
            else:
                required |= set(x for x in (part.get("required") or []) if isinstance(x, str)) if isinstance(part.get("required"), list) else set()
                self.fill_props(e, part, required, ptr, depth)
        self.fill_props(e, s, required, ptr, depth)
        for kw in _IGNORED_KW:
            if kw in s and not (kw == "additionalProperties" and s[kw] in (False, None)):
                self.d.ignore("json_keyword", f"{e.name}: {kw}")
        for kw in ("oneOf", "anyOf"):
            if kw in s and _is_object(s) and isinstance(s[kw], list):
                self.d.ignore("json_keyword", f"{e.name}: {kw}")

    def fill_props(self, e: Entity, s: dict, required: set[str], ptr: str, depth: int) -> None:
        props = s.get("properties")
        if not isinstance(props, dict):
            return
        for name, ps in props.items():
            self.b.tick()
            if not isinstance(name, str) or not name:
                continue
            if e.prop(name) or e.rel(name):
                continue
            self.property(e, name, ps, name in required, ptr + "/properties/" + _ptr(name), depth)

    def nullable(self, ps: dict) -> tuple[dict, bool]:
        """Retire ``null`` des types et des unions : retourne (schéma sans null, nullable ?)."""
        nullable = bool(ps.get("nullable") is True)
        t = ps.get("type")
        if isinstance(t, list):
            rest = [x for x in t if x != "null"]
            nullable = nullable or len(rest) != len(t)
            ps = {**ps, "type": rest[0] if len(rest) == 1 else rest}
        for kw in ("anyOf", "oneOf"):
            alts = ps.get(kw)
            if isinstance(alts, list):
                rest = [a for a in alts if not (isinstance(a, dict) and a.get("type") == "null")]
                if len(rest) != len(alts):
                    nullable = True
                    if len(rest) == 1 and isinstance(rest[0], dict):
                        ps = {**{k: v for k, v in ps.items() if k != kw}, **rest[0]}
                    else:
                        ps = {**ps, kw: rest}
        return ps, nullable

    def property(self, e: Entity, name: str, ps: Any, required: bool, ptr: str, depth: int) -> None:
        if not isinstance(ps, dict):
            self.d.ignore("json_keyword", f"{e.name}.{name}: schéma booléen")
            return
        ps, nullable = self.nullable(ps)
        if nullable and required:
            self.d.notice("nullable_required", "info", f"{e.name}.{name}", entity=e.name, property=name)
            required = False
        comment = str(ps.get("description") or "")[:2000]
        # allOf d'une seule référence (enveloppe)
        if isinstance(ps.get("allOf"), list) and len(ps["allOf"]) == 1 and isinstance(ps["allOf"][0], dict) and "$ref" in ps["allOf"][0] and "$ref" not in ps:
            ps = {**{k: v for k, v in ps.items() if k != "allOf"}, "$ref": ps["allOf"][0]["$ref"]}
        if "$ref" in ps:
            kind, val = self.resolve(ps["$ref"])
            if kind == "entity":
                e.rels.append(Rel(key=name, target=val, required=required, many=False, comment=comment, source=f"{e.name}.{name} → {str(ps['$ref'])[:80]}", hint="has" + pascal(name)))
                return
            if kind == "external":
                tk = self.external_stub(val)
                e.rels.append(Rel(key=name, target=tk, required=required, many=False, comment=comment, source=f"{e.name}.{name} → {val[:80]}", hint="has" + pascal(name)))
                return
            if kind == "prim" and isinstance(val, dict) and "$ref" not in val:
                merged = {**val, **{k: v for k, v in ps.items() if k != "$ref"}}
                self.property(e, name, merged, required, ptr, depth)
                return
            self.d.ignore("json_ref_unresolved", f"{e.name}.{name}: {str(ps['$ref'])[:80]}")
            return
        for kw in ("oneOf", "anyOf"):
            alts = ps.get(kw)
            if isinstance(alts, list) and alts and "type" not in ps:
                keys = []
                for a in alts:
                    if isinstance(a, dict) and "$ref" in a:
                        kind, val = self.resolve(a["$ref"])
                        keys.append(val if kind == "entity" else self.external_stub(val) if kind == "external" else None)
                    elif isinstance(a, dict) and _is_object(a) and depth < MAX_DEPTH:
                        keys.append(self.inline_entity(e, f"{name}{len(keys) + 1}", a, ptr, depth))
                    else:
                        keys.append(None)
                if keys and all(keys):
                    uniq = list(dict.fromkeys(keys))
                    e.rels.append(Rel(key=name, target=uniq[0], union=uniq if len(uniq) > 1 else [], required=required, many=False, comment=comment,
                                      source=f"{e.name}.{name} ({kw})", hint="has" + pascal(name)))
                    return
                if all(isinstance(a, dict) and a.get("type") in ("string", "integer", "number", "boolean") for a in alts):
                    self.d.notice("union_as_string", "review", f"{e.name}.{name}", entity=e.name, property=name)
                    e.props.append(Prop(key=name, xsd="string", required=required, comment=comment, src_type=kw))
                    return
                self.d.ignore("json_keyword", f"{e.name}.{name}: {kw}")
                self.d.notice("union_as_string", "review", f"{e.name}.{name}", entity=e.name, property=name)
                e.props.append(Prop(key=name, xsd="string", required=required, comment=comment, src_type=kw))
                return
        t = ps.get("type")
        if isinstance(t, list):
            self.d.notice("mixed_type", "review", f"{e.name}.{name}", entity=e.name, property=name, types=", ".join(str(x) for x in t[:5]))
            t = "string"
        if t is None:
            t = "object" if "properties" in ps else "array" if "items" in ps else None
        if "enum" in ps or "const" in ps:
            vals = ps["enum"] if isinstance(ps.get("enum"), list) else [ps["const"]] if "const" in ps else []
            lex = _lexical(vals)
            if lex is not None and 0 < len(lex) <= MAX_ENUM:
                xsd = {"integer": "integer", "number": "double", "boolean": "boolean"}.get(t if isinstance(t, str) else "", "string")
                e.props.append(Prop(key=name, xsd=xsd, required=required, comment=comment, enum=lex, src_type=str(t or "enum")))
                return
            self.d.ignore("json_keyword", f"{e.name}.{name}: enum non scalaire")
        if t == "object":
            if isinstance(ps.get("properties"), dict) and ps["properties"] and depth < MAX_DEPTH:
                k = self.inline_entity(e, name, ps, ptr, depth)
                e.rels.append(Rel(key=name, target=k, required=required, many=False, comment=comment, source=f"{e.name}.{name} (nested object)", hint="has" + pascal(name)))
            else:
                self.d.ignore("json_free_object", f"{e.name}.{name}")
            return
        if t == "array":
            self.array(e, name, ps, required, comment, ptr, depth)
            return
        if t in ("string", "integer", "number", "boolean"):
            p = self.primitive(e, name, ps, t, required, comment)
            e.props.append(p)
            return
        if t == "null":
            self.d.ignore("json_keyword", f"{e.name}.{name}: type null")
            return
        self.d.ignore("json_keyword", f"{e.name}.{name}: type inconnu")

    def inline_entity(self, parent: Entity, name: str, schema: dict, ptr: str, depth: int) -> str:
        key = f"{parent.key}/{name}"
        ne = Entity(key=key, name=pascal(parent.name + pascal(name)), comment=str(schema.get("description") or "")[:2000], source=f"{parent.source} · {name}")
        while any(x.name == ne.name for x in self.d.entities.values()):
            ne.name += "2"
        _add(self.d, ne)
        self.fill(ne, schema, ptr, depth + 1)
        return key

    def array(self, e: Entity, name: str, ps: dict, required: bool, comment: str, ptr: str, depth: int) -> None:
        items = ps.get("items")
        mn, mx = ps.get("minItems"), ps.get("maxItems")
        mn = mn if isinstance(mn, int) and not isinstance(mn, bool) and mn >= 0 else None
        mx = mx if isinstance(mx, int) and not isinstance(mx, bool) and mx >= 0 else None
        if required and not mn:
            self.d.notice("required_array_empty", "info", f"{e.name}.{name}", entity=e.name, property=name)
        if not isinstance(items, dict):
            self.d.ignore("json_keyword", f"{e.name}.{name}: items absent ou en liste")
            return
        items, _ = self.nullable(items)
        if "$ref" in items:
            kind, val = self.resolve(items["$ref"])
            if kind in ("entity", "external"):
                tk = val if kind == "entity" else self.external_stub(val)
                e.rels.append(Rel(key=name, target=tk, required=bool(mn), many=True, comment=comment, min_count=mn, max_count=mx,
                                  source=f"{e.name}.{name} (list)", hint="has" + pascal(name)))
                return
            if kind == "prim" and isinstance(val, dict) and "$ref" not in val:
                items = {**val, **{k: v for k, v in items.items() if k != "$ref"}}
            else:
                self.d.ignore("json_ref_unresolved", f"{e.name}.{name}: {str(items['$ref'])[:80]}")
                return
        t = items.get("type")
        if t == "object" and isinstance(items.get("properties"), dict) and items["properties"] and depth < MAX_DEPTH:
            k = self.inline_entity(e, name, items, ptr + "/items", depth)
            e.rels.append(Rel(key=name, target=k, required=bool(mn), many=True, comment=comment, min_count=mn, max_count=mx,
                              source=f"{e.name}.{name} (list of objects)", hint="has" + pascal(name)))
            return
        if "enum" in items and isinstance(items["enum"], list):
            lex = _lexical(items["enum"])
            if lex is not None and 0 < len(lex) <= MAX_ENUM:
                xsd = {"integer": "integer", "number": "double", "boolean": "boolean"}.get(t if isinstance(t, str) else "", "string")
                e.props.append(Prop(key=name, xsd=xsd, required=bool(mn), many=True, enum=lex, comment=comment, min_count=mn, max_count=mx, src_type="array"))
                return
        if t in ("string", "integer", "number", "boolean"):
            p = self.primitive(e, name, items, t, bool(mn), comment)
            p.many, p.min_count, p.max_count, p.src_type = True, mn, mx, "array of " + t
            e.props.append(p)
            return
        self.d.ignore("json_keyword", f"{e.name}.{name}: éléments de liste non traduits")

    def primitive(self, e: Entity, name: str, ps: dict, t: str, required: bool, comment: str) -> Prop:
        xsd, degraded = {"string": "string", "integer": "integer", "number": "double", "boolean": "boolean"}[t], None
        facets: dict[str, str] = {}
        if t == "string":
            fmt = ps.get("format")
            if isinstance(fmt, str) and fmt in _STR_FORMATS:
                xsd, degraded = _STR_FORMATS[fmt]
            if ps.get("contentEncoding") == "base64":
                xsd = "base64Binary"
            for kw, fk in (("minLength", "min_length"), ("maxLength", "max_length")):
                v = ps.get(kw)
                if isinstance(v, int) and not isinstance(v, bool) and v >= 0:
                    facets[fk] = str(v)
            if isinstance(ps.get("pattern"), str) and len(ps["pattern"]) <= 500:
                facets["pattern"] = ps["pattern"]
                if not self.pattern_noted:
                    self.pattern_noted = True
                    self.d.notice("pattern_dialect", "info", None)
        elif t in ("integer", "number"):
            for kw, fk in (("minimum", "min_inclusive"), ("maximum", "max_inclusive")):
                v = ps.get(kw)
                if isinstance(v, (int, float)) and not isinstance(v, bool):
                    facets[fk] = _num(v)
            for kw, base, fk in (("exclusiveMinimum", "minimum", "min_exclusive"), ("exclusiveMaximum", "maximum", "max_exclusive")):
                v = ps.get(kw)
                if isinstance(v, (int, float)) and not isinstance(v, bool):
                    facets[fk] = _num(v)
                elif v is True and isinstance(ps.get(base), (int, float)):
                    facets.pop("min_inclusive" if kw == "exclusiveMinimum" else "max_inclusive", None)
                    facets[fk] = _num(ps[base])
        if degraded:
            self.d.notice("degraded_type", "warning", f"{e.name}.{name}", table=e.name, column=name, type=degraded, xsd=xsd)
        return Prop(key=name, xsd=xsd, required=required, comment=comment, facets=facets, degraded=degraded, src_type=t)


def _num(v: Any) -> str:
    return str(int(v)) if isinstance(v, int) or (isinstance(v, float) and v.is_integer() and abs(v) < 1e15) else repr(float(v))


def _lexical(vals: list) -> Optional[list[str]]:
    out: list[str] = []
    for v in vals:
        if isinstance(v, bool):
            out.append("true" if v else "false")
        elif isinstance(v, (int, float)):
            out.append(_num(v))
        elif isinstance(v, str):
            out.append(v[:500])
        else:
            return None
    return list(dict.fromkeys(out))
