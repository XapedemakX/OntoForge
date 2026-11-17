"""Import CSV déterministe (L48) : une classe par fichier, types déduits d'un échantillon, clés et références proposées.

Lecteur RFC 4180 maison (guillemets doublés, retours à la ligne dans les champs), borné : au plus ``MAX_CSV_ROWS`` lignes lues,
``MAX_CSV_FIELD`` caractères par champ, ``MAX_COLUMNS_TABLE`` colonnes. Rien d'autre que l'en-tête et l'échantillon n'est lu.
"""
from __future__ import annotations

import os
import re
from typing import Any, Optional

from ..assistant.naming import camel, pascal, singular
from .ir import Decision, Draft, Entity, Prop, Rel
from .limits import MAX_COLUMNS_TABLE, MAX_CSV_FIELD, MAX_CSV_ROWS, Budget, ImportRefused

_INT = re.compile(r"[+-]?\d{1,18}")
_DEC = re.compile(r"[+-]?(?:\d+\.\d+|\.\d+|\d+\.)(?:[eE][+-]?\d+)?")
_DEC_COMMA = re.compile(r"[+-]?\d+,\d+")
_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
_DATETIME = re.compile(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?(?:Z|[+-]\d{2}:?\d{2})?")
_DATE_OTHER = re.compile(r"\d{1,2}[/.\-]\d{1,2}[/.\-]\d{2,4}")
_ID_COL = re.compile(r"(?i)^(?:id|uuid|guid|(?:.*[_\s-])?id|id[_\s-].*|.*Id)$")
_FK_COL = re.compile(r"(?i)^(?:(.+?)[_\s-]id|id[_\s-](.+)|(.+?)Id)$")
DELIMS = [",", ";", "\t", "|"]


def detect_delimiter(text: str) -> str:
    head = text[:8192]
    best, bestn = ",", 0
    for d in DELIMS:
        n, inq = 0, False
        for ch in head.split("\n", 1)[0] if "\n" in head else head:
            if ch == '"':
                inq = not inq
            elif ch == d and not inq:
                n += 1
        if n > bestn:
            best, bestn = d, n
    return best


def read_rows(text: str, delim: str, max_rows: int, budget: Budget) -> tuple[list[list[str]], bool]:
    """Lit au plus ``max_rows`` lignes. Retourne (lignes, tronqué ?)."""
    rows: list[list[str]] = []
    n, i = len(text), 0
    field_rx = re.compile(r"[^" + re.escape(delim) + r"\r\n\"]*")
    while i < n and len(rows) < max_rows:
        row: list[str] = []
        while True:
            budget.tick()
            if i < n and text[i] == '"':
                buf: list[str] = []
                j = i + 1
                while True:
                    q = text.find('"', j)
                    if q < 0:
                        buf.append(text[j:])
                        j = n
                        break
                    buf.append(text[j:q])
                    if q + 1 < n and text[q + 1] == '"':
                        buf.append('"')
                        j = q + 2
                        continue
                    j = q + 1
                    break
                tail = field_rx.match(text, j)   # texte parasite entre le guillemet fermant et le séparateur : conservé
                val = "".join(buf) + tail.group(0)
                i = tail.end()
            else:
                m = field_rx.match(text, i)
                val = m.group(0)
                i = m.end()
                if i < n and text[i] == '"':   # guillemet au milieu d'un champ non cité : littéral
                    q = text.find(delim, i)
                    e = min([x for x in (text.find("\n", i), q) if x >= 0] or [n])
                    val += text[i:e]
                    i = e
            row.append(val[:MAX_CSV_FIELD])
            if len(row) > MAX_COLUMNS_TABLE:
                raise ImportRefused("too_many_columns", 413, max=MAX_COLUMNS_TABLE, total=MAX_COLUMNS_TABLE)
            if i < n and text[i] == delim:
                i += 1
                continue
            break
        if i < n and text[i] == "\r":
            i += 1
        if i < n and text[i] == "\n":
            i += 1
        if len(row) == 1 and row[0] == "" and (i >= n or True):
            continue   # ligne vide
        rows.append(row)
    return rows, i < n


def infer(values: list[str]) -> tuple[str, Optional[str], Optional[str]]:
    """(type XSD court, ancien type si dégradé, code d'avis éventuel) d'après les valeurs non vides."""
    vs = [v.strip() for v in values if v.strip() != ""]
    if not vs:
        return "string", None, None
    if all(_INT.fullmatch(v) and not (len(v.lstrip("+-")) > 1 and v.lstrip("+-").startswith("0")) for v in vs):
        return "integer", None, None
    if all((_INT.fullmatch(v) or _DEC.fullmatch(v)) and not (len(v.lstrip("+-")) > 1 and v.lstrip("+-").startswith("0") and "." not in v) for v in vs):
        return "decimal", None, None
    if all(_DEC_COMMA.fullmatch(v) or _INT.fullmatch(v) for v in vs) and any(_DEC_COMMA.fullmatch(v) for v in vs):
        return "string", None, "decimal_comma"
    if all(v.lower() in ("true", "false") for v in vs):
        return "boolean", None, None
    if all(_DATETIME.fullmatch(v) for v in vs):
        return "dateTime", None, None
    if all(_DATE.fullmatch(v) or _DATETIME.fullmatch(v) for v in vs):
        return "dateTime", "date", None
    if all(_DATE_OTHER.fullmatch(v) for v in vs):
        return "string", None, "date_format"
    return "string", None, None


def _stem(filename: str) -> str:
    base = os.path.basename((filename or "").replace("\\", "/"))
    return re.sub(r"\.[A-Za-z0-9]{1,6}$", "", base).strip()


def parse_csv(files: list[tuple[str, str]], draft: Draft, options: dict[str, Any], budget: Budget) -> None:
    """Ajoute au brouillon une entité par fichier CSV. ``options`` : singularize, required_from_sample, choices."""
    singularize = bool(options.get("singularize", True))
    from_sample = bool(options.get("required_from_sample", False))
    choices: dict[str, str] = dict(options.get("choices") or {})
    delim_opt = options.get("delimiter")
    parsed: list[tuple[str, str, list[str], list[list[str]], list[Optional[str]]]] = []
    for fname, text in files:
        lines = text.lstrip("﻿")
        name_hint = None
        while True:   # lignes de tête « # table: nom »
            s = lines.lstrip(" \t")
            if not s.startswith("#"):
                break
            e = s.find("\n")
            first = s if e < 0 else s[:e]
            m = re.match(r"#\s*(?:table|name|class|classe|entity)\s*[:=]\s*(\S+)", first, re.I)
            if m:
                name_hint = m.group(1)
            lines = "" if e < 0 else s[e + 1:]
        delim = delim_opt if delim_opt in DELIMS else detect_delimiter(lines)
        rows, truncated = read_rows(lines, delim, MAX_CSV_ROWS + 1, budget)
        if not rows:
            draft.notice("csv_empty", "warning", fname, file=fname)
            continue
        header = rows[0]
        data = rows[1:]
        if truncated:
            draft.notice("csv_sampled", "info", fname, file=fname, rows=len(data))
        if delim != ",":
            draft.notice("csv_delimiter", "info", fname, file=fname, delimiter={"\t": "tabulation", ";": ";", "|": "|"}.get(delim, delim))
        cols: list[str] = []
        seen: dict[str, int] = {}
        for i, h in enumerate(header):
            h = h.strip() or f"column_{i + 1}"
            if not h.strip():
                h = f"column_{i + 1}"
            k = h.lower()
            if k in seen:
                seen[k] += 1
                draft.notice("csv_duplicate_header", "warning", fname, file=fname, column=h)
                h = f"{h}_{seen[k]}"
            else:
                seen[k] = 1
            cols.append(h)
        if all(re.fullmatch(r"[+-]?\d+(?:[.,]\d+)?", c.strip() or "x") for c in header):
            draft.notice("csv_header_numeric", "warning", fname, file=fname)
        cname = pascal(singular(name_hint or _stem(fname)) if singularize else (name_hint or _stem(fname)))
        if not (name_hint or _stem(fname)):
            cname = "Record"
            draft.notice("csv_no_name", "warning", fname, file=fname)
        parsed.append((fname, cname, cols, data, [name_hint]))
    names = {cname.lower(): cname for _, cname, *_ in parsed}
    for fname, cname, cols, data, _ in parsed:
        if len(draft.entities) >= 400:
            raise ImportRefused("too_many_tables", 413, max=400)
        key = cname.lower()
        if key in draft.entities:
            key = key + "_" + str(len(draft.entities))
            draft.notice("csv_name_clash", "warning", fname, file=fname, name=cname)
        e = Entity(key=key, name=cname, source=f"file {fname}")
        keycol: Optional[str] = None
        for idx, col in enumerate(cols):
            values = [r[idx] if idx < len(r) else "" for r in data]
            low = col.lower()
            stem_name = pascal(singular(re.sub(r"(?i)[_\s-]?id$|^id[_\s-]?", "", col)))
            m = _FK_COL.match(col)
            is_own = low in ("id", "uuid", "guid") or (_ID_COL.match(col) and stem_name.lower() == cname.lower())
            if is_own and keycol is None:
                filled = [v for v in values if v.strip()]
                if len(filled) == len(values) and len(set(filled)) == len(filled) and filled:
                    keycol = col
            elif m and not is_own and stem_name and stem_name.lower() != cname.lower():
                did = f"reference:{e.key}.{col}"
                target_known = stem_name.lower() in names
                default = "relation" if target_known else "property"
                chosen = choices.get(did, default)
                if chosen not in ("property", "relation"):
                    chosen = default
                draft.decisions.append(Decision(did, "reference", f"{cname}.{col}", ["property", "relation"], default, chosen,
                                                {"entity": cname, "column": col, "target": stem_name, "target_in_files": target_known}))
                if chosen == "relation":
                    tkey = stem_name.lower()
                    if tkey not in draft.entities and tkey not in {n.lower() for n in names}:
                        draft.entities[tkey] = Entity(key=tkey, name=stem_name, source=f"column {cname}.{col} (classe référencée)", kind="stub")
                    filled = [v for v in values if v.strip()]
                    e.rels.append(Rel(key=col, target=tkey, required=bool(from_sample and values and len(filled) == len(values)), many=False,
                                      hint="has" + stem_name, source=f"column {cname}.{col}"))
                    continue
            xsd, degraded, note = infer(values)
            if note:
                draft.notice(note, "review", f"{cname}.{col}", file=fname, column=col)
            if degraded:
                draft.notice("degraded_type", "warning", f"{cname}.{col}", table=cname, column=col, type=degraded, xsd=xsd)
            filled = [v for v in values if v.strip()]
            e.props.append(Prop(key=col, xsd=xsd, required=bool(from_sample and values and len(filled) == len(values)), degraded=degraded, src_type="csv"))
        if keycol:
            e.keys.append([keycol])
            e.assumed_key = True
            p = e.prop(keycol)
            if p:
                p.required = True
            draft.notice("assumed_key", "review", cname, entity=cname, column=keycol)
        else:
            draft.notice("no_key_candidate", "review", cname, entity=cname)
        draft.entities[e.key] = e
    # les classes référencées déjà décrites par un autre fichier : on fait pointer la relation sur la bonne clé
    for e in draft.entities.values():
        for r in e.rels:
            if r.target not in draft.entities:
                for k, other in draft.entities.items():
                    if other.name.lower() == r.target:
                        r.target = k
                        break
