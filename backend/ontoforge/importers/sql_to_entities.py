"""Schéma relationnel (``sql_ddl.Schema``) → entités du brouillon (L48).

Règles (déterministes ; les points ambigus deviennent des *décisions* présentées à l'humain avec un choix par défaut) :
- table → classe (nom au singulier PascalCase) ; colonne → propriété de données ; clé primaire → ``owl:hasKey`` ;
- clé étrangère → propriété objet fonctionnelle (domaine = la table, portée = la table référencée), minimum 1 si toutes les colonnes sont NOT NULL ;
- table d'association (exactement deux clés étrangères et rien d'autre que leurs colonnes, éventuellement une clé de substitution que personne ne
  référence) → propriété objet N-N, sauf choix contraire ; avec colonnes en plus → classe réifiée (deux propriétés objet) ;
- clé primaire = clé étrangère unique (table « par type ») → propriété objet par défaut, ``rdfs:subClassOf`` si l'humain le choisit ;
- ``UNIQUE`` sur colonnes NOT NULL → clé candidate (``owl:hasKey`` supplémentaire) ; ``CHECK … IN (…)`` → énumération.
"""
from __future__ import annotations

import re
from typing import Any, Optional

from ..assistant.naming import camel, pascal, singular
from .ir import Decision, Draft, Entity, Prop, Rel
from .sql_ddl import Column, ForeignKey, Schema, Table

_ID_SUFFIX = re.compile(r"(?i)(?:[_\s-]?(?:id|fk|key|code|uuid|ref))$")


def _tkey(t: Table) -> str:
    return t.qname.lower()


def _class_name(t: Table, singularize: bool) -> str:
    return pascal(singular(t.name) if singularize else t.name)


def _stem(fk: ForeignKey, target_name: str) -> str:
    if len(fk.cols) == 1:
        s = _ID_SUFFIX.sub("", fk.cols[0])
        if s and s.lower() not in ("id", ""):
            return pascal(s)
    return target_name


def _enum_values(col: Column) -> Optional[list[str]]:
    if not col.enum:
        return None
    return list(dict.fromkeys(v for v, _num in col.enum))


def to_draft(schema: Schema, draft: Draft, options: dict[str, Any]) -> Draft:
    singularize = bool(options.get("singularize", True))
    choices: dict[str, str] = dict(options.get("choices") or {})
    tables = list(schema.tables.values())
    referenced_by: dict[str, int] = {}
    resolved: dict[int, Optional[Table]] = {}
    for t in tables:
        for fk in t.fks:
            tgt = schema.find(fk.ref_schema, fk.ref_name)
            resolved[id(fk)] = tgt
            if tgt is not None:
                referenced_by[_tkey(tgt)] = referenced_by.get(_tkey(tgt), 0) + (1 if tgt is not t else 0)

    def pk_ref_cols(t: Table) -> set[str]:
        return {c.lower() for c in t.pk}

    # --- classement des tables
    kind: dict[str, str] = {}      # clé → class | association | subclass_candidate
    parent_of: dict[str, Table] = {}
    assoc_like: set[str] = set()   # tables à deux clés étrangères avec colonnes en plus : classes réifiées
    for t in tables:
        k = _tkey(t)
        kind[k] = "class"
        fkcols = {c.lower() for fk in t.fks for c in fk.cols}
        extra = set(t.columns) - fkcols
        if len(t.fks) == 2 and all(resolved.get(id(fk)) is not None for fk in t.fks):
            pkset = pk_ref_cols(t)
            surrogate = len(pkset) == 1 and pkset <= extra and referenced_by.get(k, 0) == 0
            if not pkset or pkset <= fkcols or surrogate:
                others = extra - (pkset if surrogate else set())
                if not others:
                    kind[k] = "association"
                    continue
                assoc_like.add(k)
        if len(t.fks) >= 1 and t.pk and len(t.pk) == 1:
            for fk in t.fks:
                tgt = resolved.get(id(fk))
                if tgt is not None and len(fk.cols) == 1 and fk.cols[0].lower() == t.pk[0].lower() and tgt is not t:
                    kind[k] = "subclass_candidate"
                    parent_of[k] = tgt
                    break

    # --- décisions
    for t in tables:
        k = _tkey(t)
        if kind[k] == "association":
            did = f"association:{t.qname}"
            chosen = choices.get(did, "property")
            if chosen not in ("property", "class"):
                chosen = "property"
            draft.decisions.append(Decision(did, "association", t.qname, ["property", "class"], "property", chosen, {"table": t.qname}))
            if chosen == "class":
                kind[k] = "class"
                assoc_like.add(k)
        elif kind[k] == "subclass_candidate":
            did = f"subclass:{t.qname}"
            chosen = choices.get(did, "property")
            if chosen not in ("property", "subclass"):
                chosen = "property"
            draft.decisions.append(Decision(did, "subclass", t.qname, ["property", "subclass"], "property", chosen,
                                            {"table": t.qname, "parent": parent_of[k].qname}))
            kind[k] = "subclass" if chosen == "subclass" else "class"

    ents: dict[str, Entity] = {}
    for t in tables:
        k = _tkey(t)
        if kind[k] == "association":
            continue
        ents[k] = Entity(key=k, name=_class_name(t, singularize), comment=t.comment, source=f"table {t.qname}", kind="reified" if k in assoc_like else "class")

    def ensure_stub(fk: ForeignKey) -> str:
        key = ("stub:" + (fk.ref_schema or "") + "." + fk.ref_name).lower()
        if key not in ents:
            ents[key] = Entity(key=key, name=pascal(singular(fk.ref_name) if singularize else fk.ref_name), source=f"table {fk.ref_name} (absent from the script)", kind="stub")
            draft.notice("fk_target_missing", "warning", fk.ref_name, table=fk.ref_name)
        return key

    for t in tables:
        k = _tkey(t)
        if kind[k] == "association":
            _association(t, schema, ents, resolved, draft, singularize, ensure_stub)
            continue
        e = ents[k]
        fkcols = {c.lower() for fk in t.fks for c in fk.cols}
        subclass_fk = next((fk for fk in t.fks if kind[k] == "subclass" and len(fk.cols) == 1 and fk.cols[0].lower() == (t.pk[0].lower() if t.pk else "")), None)
        for col in t.columns.values():
            if col.name.lower() in fkcols:
                continue
            mp = col.mapped
            facets = dict(col.facets)
            if mp.max_length and "max_length" not in facets:
                facets["max_length"] = str(mp.max_length)
            e.props.append(Prop(key=col.name, xsd=mp.xsd, required=not col.nullable, many=col.type.array, enum=_enum_values(col), comment=col.comment,
                                src_type=col.type.raw, facets=facets, degraded=mp.degraded))
            _col_notices(draft, t, col)
        rel_keys: dict[str, str] = {}
        for fk in t.fks:
            if fk is subclass_fk:
                continue
            tgt = resolved.get(id(fk))
            tkey = _tkey(tgt) if tgt is not None else ensure_stub(fk)
            if tgt is not None and kind.get(tkey) == "association":
                draft.notice("fk_to_association", "warning", t.name, table=t.name, target=tgt.name)
            tname = ents[tkey].name if tkey in ents else pascal(singular(fk.ref_name))
            stem = _stem(fk, tname)
            required = all((t.col(c) is not None and not t.col(c).nullable) for c in fk.cols)
            r = Rel(key="fk:" + ",".join(c.lower() for c in fk.cols), target=tkey, required=required, many=False, hint="has" + stem,
                    source=f"column {t.name}.{', '.join(fk.cols)}", composite=len(fk.cols) > 1)
            if len(fk.cols) > 1:
                draft.notice("composite_fk", "review", t.name, table=t.name, target=tname, columns=", ".join(fk.cols))
            if any(x.hint == r.hint and x.target == r.target for x in e.rels):
                r.hint += "Ref"
            e.rels.append(r)
            for c in fk.cols:
                rel_keys[c.lower()] = r.key
        if kind[k] == "subclass" and subclass_fk is not None:
            tgt = resolved[id(subclass_fk)]
            e.parents.append(_tkey(tgt))
        _keys(t, e, rel_keys, kind[k] == "subclass", draft)
    # une classe réifiée : avis
    for e in ents.values():
        if e.kind == "reified":
            draft.notice("reified_class", "review", e.name, table=e.source.removeprefix("table "))
    draft.entities = ents
    return draft


def _col_notices(draft: Draft, t: Table, col: Column) -> None:
    mp = col.mapped
    where = f"{t.name}.{col.name}"
    if mp.degraded:
        draft.notice("degraded_type", "warning", where, table=t.name, column=col.name, type=col.type.raw or col.type.base, xsd=mp.xsd)
    if mp.note and mp.note not in ("unknown_type", "enum_type"):
        draft.notice(mp.note, "review" if mp.note in ("float_ambiguous", "tinyint1_as_boolean") else "info", where, table=t.name, column=col.name, type=col.type.raw)
    if col.type.array:
        draft.notice("array_column", "review", where, table=t.name, column=col.name)
    if col.auto:
        draft.ignore("identity", where)


def _keys(t: Table, e: Entity, rel_keys: dict[str, str], inherited: bool, draft: Draft) -> None:
    def to_key(cols: list[str]) -> Optional[list[str]]:
        out: list[str] = []
        for c in cols:
            col = t.col(c)
            if col is None:
                return None
            k = rel_keys.get(c.lower()) or col.name
            if k not in out:
                out.append(k)
        return out
    if t.pk and not inherited:
        k = to_key(t.pk)
        if k:
            e.keys.append(k)
    elif not t.pk and not inherited:
        draft.notice("no_primary_key", "review", t.name, table=t.name)
    uniques = [list(u) for u in t.uniques] + [[c.name] for c in t.columns.values() if c.unique]
    for u in uniques:
        if all((t.col(c) is not None and not t.col(c).nullable) for c in u):
            k = to_key(u)
            if k and k not in e.keys:
                e.keys.append(k)
                if not t.pk and len(e.keys) == 1:
                    draft.notice("key_from_unique", "review", t.name, table=t.name, columns=", ".join(u))
        else:
            draft.notice("unique_nullable", "review", t.name, table=t.name, columns=", ".join(u))


def _association(t: Table, schema: Schema, ents: dict[str, Entity], resolved: dict[int, Optional[Table]], draft: Draft, singularize: bool, ensure_stub) -> None:
    a, b = t.fks
    ta, tb = resolved[id(a)], resolved[id(b)]
    ka, kb = _tkey(ta), _tkey(tb)
    src = ents.get(ka)
    if src is None:   # la table d'origine est elle-même une association : on retombe sur une classe
        draft.notice("fk_to_association", "warning", t.name, table=t.name, target=ta.name)
        return
    if kb not in ents:
        draft.notice("fk_to_association", "warning", t.name, table=t.name, target=tb.name)
        return
    required = False
    r = Rel(key="assoc:" + t.qname.lower(), target=kb, required=required, many=True, comment=t.comment, source=f"association table {t.qname}",
            hint=camel(t.name))
    if any(x.hint == r.hint for x in src.rels):
        r.hint += "Ref"
    src.rels.append(r)
    draft.notice("association_collapsed", "info", t.name, table=t.name, source=src.name, target=ents[kb].name)
