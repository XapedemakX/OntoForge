"""Sous-ensemble des expressions ``CHECK`` reconnues (L48) : énumérations, bornes numériques, longueurs.

Reconnu, par conjonction (``AND``) de premier niveau, sur UNE colonne :
``col IN ('a','b')``, ``col = 'a' OR col = 'b'``, ``col = ANY (ARRAY['a','b'])`` (PostgreSQL, avec ``::text``), ``col >= 0``, ``0 < col``,
``col BETWEEN 1 AND 5``, ``LENGTH(col) <= 10`` (``LEN``, ``CHAR_LENGTH``), ``col <> ''`` (longueur minimale 1), ``col IS NOT NULL``.
Le reste est rendu tel quel dans ``unhandled`` (rapporté à l'humain, jamais perdu en silence). Analyse itérative bornée : profondeur MAX_DEPTH.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .limits import MAX_DEPTH, MAX_ENUM, Budget, ImportRefused
from .sql_lexer import Tok

_LEN_FN = {"LENGTH", "LEN", "CHAR_LENGTH", "CHARACTER_LENGTH"}
_CMP = {"=", "<", ">", "<=", ">=", "<>", "!="}
_FLIP = {"<": ">", ">": "<", "<=": ">=", ">=": "<=", "=": "=", "<>": "<>", "!=": "!="}


@dataclass
class CheckResult:
    enums: dict[str, list[tuple[str, bool]]] = field(default_factory=dict)   # colonne → [(valeur, numérique ?)]
    facets: dict[str, dict[str, str]] = field(default_factory=dict)          # colonne → {min_inclusive: "0", max_length: "10"…}
    notnull: set[str] = field(default_factory=set)
    unhandled: list[str] = field(default_factory=list)
    intersected: set[str] = field(default_factory=set)      # colonnes dont plusieurs contraintes ont été cumulées (ET)
    contradictions: set[str] = field(default_factory=set)   # colonnes dont les listes de valeurs n'ont rien en commun
    budget: Optional[Budget] = None


def _dedup(vals: list[tuple[str, bool]]) -> list[tuple[str, bool]]:
    return list(dict.fromkeys(vals))   # linéaire, ordre conservé


def _num(s: str) -> Optional[float]:
    try:
        return float(s)
    except ValueError:
        return None


def merge_facets(dst: dict[str, str], src: dict[str, str]) -> None:
    """Facettes cumulées (ET) : on garde la borne la plus stricte quand les deux sont numériques, sinon la première."""
    for k, v in src.items():
        if k not in dst:
            dst[k] = v
            continue
        a, b = _num(dst[k]), _num(v)
        if a is None or b is None:
            continue
        low = k.startswith("min") or k == "length"
        if (low and b > a) or (not low and b < a):
            dst[k] = v


def merge_enum(res: "CheckResult", col: str, vals: list[tuple[str, bool]]) -> None:
    """Plusieurs contraintes sur une même colonne se cumulent (ET) : intersection des listes de valeurs, jamais union."""
    if col in res.contradictions:
        return
    vals = _dedup(vals)
    old = res.enums.get(col)
    if old is None:
        res.enums[col] = vals
        return
    keep = set(vals)
    inter = [v for v in old if v in keep]
    res.intersected.add(col)
    if inter:
        res.enums[col] = inter
    else:
        del res.enums[col]
        res.contradictions.add(col)


def _text(toks: list[Tok]) -> str:
    return " ".join(("'" + t.v + "'") if t.k == "s" else t.v for t in toks)[:200]


def _match(toks: list[Tok], i: int) -> int:
    """Indice de la parenthèse fermante qui correspond à ``toks[i]`` (ou -1)."""
    depth = 0
    for j in range(i, len(toks)):
        if toks[j].is_p("("):
            depth += 1
        elif toks[j].is_p(")"):
            depth -= 1
            if depth == 0:
                return j
    return -1


def _strip_casts(toks: list[Tok]) -> list[Tok]:
    out: list[Tok] = []
    i, n = 0, len(toks)
    while i < n:
        t = toks[i]
        if t.is_p("::"):
            i += 1
            while i < n and toks[i].k == "w" and toks[i].u not in ("AND", "OR", "IN", "NOT", "IS", "BETWEEN", "LIKE"):
                i += 1
                if i < n and toks[i].is_p("("):
                    j = _match(toks, i)
                    i = (j + 1) if j > 0 else n
            while i + 1 < n and toks[i].is_p("[") and toks[i + 1].is_p("]"):
                i += 2
            continue
        if t.k == "w" and t.u == "CAST" and i + 1 < n and toks[i + 1].is_p("("):
            j = _match(toks, i + 1)
            if j > 0:
                inner = toks[i + 2:j]
                k = next((x for x, tk in enumerate(inner) if tk.k == "w" and tk.u == "AS"), len(inner))
                out.extend(_strip_casts(inner[:k]))
                i = j + 1
                continue
        out.append(t)
        i += 1
    return out


def _unwrap(toks: list[Tok]) -> list[Tok]:
    while len(toks) >= 2 and toks[0].is_p("(") and _match(toks, 0) == len(toks) - 1:
        toks = toks[1:-1]
    return toks


def _split(toks: list[Tok], kw: str) -> list[list[Tok]]:
    """Découpe au mot-clé ``kw`` de premier niveau ; le ``AND`` d'un ``BETWEEN`` n'est pas un séparateur."""
    parts, cur, depth, between = [], [], 0, False
    for t in toks:
        if t.is_p("("):
            depth += 1
        elif t.is_p(")"):
            depth -= 1
        elif depth == 0 and t.k == "w":
            if t.u == "BETWEEN":
                between = True
            elif t.u == kw:
                if kw == "AND" and between:
                    between = False
                else:
                    parts.append(cur)
                    cur = []
                    continue
        cur.append(t)
    parts.append(cur)
    return parts


def _col(toks: list[Tok]) -> Optional[str]:
    toks = _unwrap(toks)
    if toks and toks[0].k in ("w", "q") and (toks[0].k == "q" or toks[0].u not in ("NOT", "NULL", "TRUE", "FALSE", "CASE", "EXISTS")):
        j = 1
        while j + 1 < len(toks) and toks[j].is_p(".") and toks[j + 1].k in ("w", "q"):
            j += 2
        if j == len(toks):
            return toks[j - 1].v
    return None


def _lit(toks: list[Tok]) -> Optional[tuple[str, bool]]:
    toks = _unwrap(toks)
    if len(toks) == 1 and toks[0].k == "s":
        return toks[0].v, False
    if len(toks) == 1 and toks[0].k == "n":
        return toks[0].v, True
    if len(toks) == 2 and toks[0].k == "p" and toks[0].v in "+-" and toks[1].k == "n":
        return ("-" if toks[0].v == "-" else "") + toks[1].v, True
    return None


def _values(toks: list[Tok]) -> Optional[list[tuple[str, bool]]]:
    out = []
    cur: list[Tok] = []
    parts, depth = [], 0
    for t in toks:
        if t.is_p("("):
            depth += 1
        elif t.is_p(")"):
            depth -= 1
        if t.is_p(",") and depth == 0:
            parts.append(cur)
            cur = []
        else:
            cur.append(t)
    parts.append(cur)
    for p in parts:
        v = _lit(p)
        if v is None:
            return None
        out.append(v)
    return out if 0 < len(out) <= MAX_ENUM else None


def _one(res: CheckResult, toks: list[Tok], depth: int) -> bool:
    if depth > MAX_DEPTH:
        raise ImportRefused("too_deep", 422, max=MAX_DEPTH)
    toks = _unwrap(toks)
    if not toks:
        return True
    # OR de premier niveau : énumération si toutes les branches sont « même colonne = littéral »
    ors = _split(toks, "OR")
    if len(ors) > 1:
        if len(ors) > MAX_ENUM:
            return False   # liste trop longue : rapportée comme non traitée, comme IN (…)
        col, vals = None, []
        for b in ors:
            if res.budget is not None:
                res.budget.tick()
            b = _unwrap(b)
            eq = next((i for i, t in enumerate(b) if t.is_p("=")), -1)
            if eq <= 0:
                return False
            c, v = _col(b[:eq]), _lit(b[eq + 1:])
            if c is None:
                c, v = _col(b[eq + 1:]), _lit(b[:eq])
            if c is None or v is None or (col is not None and c.lower() != col.lower()):
                return False
            col = c
            vals.append(v)
        merge_enum(res, col, vals)
        return True
    ands = _split(toks, "AND")
    if len(ands) > 1:
        return all([_one(res, a, depth + 1) for a in ands])   # liste : toutes les branches sont analysées (et consignées)
    # col IS NOT NULL
    if len(toks) >= 4 and toks[-1].is_kw("NULL") and toks[-2].is_kw("NOT") and toks[-3].is_kw("IS"):
        c = _col(toks[:-3])
        if c:
            res.notnull.add(c)
            return True
    # col [NOT] IN (...)
    for idx, t in enumerate(toks):
        if t.is_kw("IN") and idx + 1 < len(toks) and toks[idx + 1].is_p("(") and _match(toks, idx + 1) == len(toks) - 1:
            if idx and toks[idx - 1].is_kw("NOT"):
                return False
            c, vals = _col(toks[:idx]), _values(toks[idx + 2:-1])
            if c and vals:
                merge_enum(res, c, vals)
                return True
            return False
    # col = ANY (ARRAY[...])
    anyi = next((i for i, t in enumerate(toks) if t.is_kw("ANY", "SOME")), -1)
    if anyi > 1 and toks[anyi - 1].is_p("="):
        c = _col(toks[:anyi - 1])
        rest = _unwrap(toks[anyi + 1:])
        if c and len(rest) >= 3 and rest[0].is_kw("ARRAY") and rest[1].is_p("[") and rest[-1].is_p("]"):
            vals = _values(rest[2:-1])
            if vals:
                merge_enum(res, c, vals)
                return True
        return False
    # col BETWEEN a AND b
    for idx, t in enumerate(toks):
        if t.is_kw("BETWEEN"):
            if idx and toks[idx - 1].is_kw("NOT"):
                return False
            c = _col(toks[:idx])
            parts = _split(toks[idx + 1:], "AND")
            if c and len(parts) == 2 and _lit(parts[0]) and _lit(parts[1]):
                f = res.facets.setdefault(c, {})
                f["min_inclusive"], f["max_inclusive"] = _lit(parts[0])[0], _lit(parts[1])[0]
                return True
            return False
    # comparaison
    cmp_i = next((i for i, t in enumerate(toks) if t.k == "p" and t.v in _CMP), -1)
    if cmp_i > 0 and cmp_i < len(toks) - 1:
        op, left, right = toks[cmp_i].v, toks[:cmp_i], toks[cmp_i + 1:]
        # LENGTH(col) op n
        for a, b, o in ((left, right, op), (right, left, _FLIP[op])):
            if len(a) >= 4 and a[0].k == "w" and a[0].u in _LEN_FN and a[1].is_p("(") and _match(a, 1) == len(a) - 1:
                c, v = _col(a[2:-1]), _lit(b)
                if c and v and v[1] and "." not in v[0]:
                    f = res.facets.setdefault(c, {})
                    key = {">=": "min_length", ">": "min_length", "<=": "max_length", "<": "max_length", "=": "length"}.get(o)
                    if key is None:
                        return False
                    n = int(v[0]) + (1 if o == ">" else -1 if o == "<" else 0)
                    if key == "length":
                        f["min_length"] = f["max_length"] = str(n)
                    else:
                        f[key] = str(max(n, 0))
                    return True
                return False
        c, v, o = _col(left), _lit(right), op
        if c is None:
            c, v, o = _col(right), _lit(left), _FLIP[op]
        if c is not None and v is not None:
            if v[1]:
                key = {">=": "min_inclusive", ">": "min_exclusive", "<=": "max_inclusive", "<": "max_exclusive"}.get(o)
                if o == "=":
                    res.enums.setdefault(c, []).append(v)
                    return True
                if key:
                    res.facets.setdefault(c, {})[key] = v[0]
                    return True
            elif o == "=":
                res.enums.setdefault(c, []).append(v)
                return True
            elif o in ("<>", "!=") and v[0] == "":
                res.facets.setdefault(c, {})["min_length"] = "1"
                return True
    return False


def analyze_check(toks: list[Tok], budget: Optional[Budget] = None) -> CheckResult:
    """Analyse l'expression d'un CHECK (jetons entre les parenthèses). ``unhandled`` liste ce qui n'a pas été compris."""
    res = CheckResult(budget=budget)
    toks = _unwrap(_strip_casts(toks))
    pieces = _split(toks, "AND") if toks else []
    for piece in pieces:
        sub = CheckResult(budget=budget)
        ok = False
        try:
            ok = _one(sub, piece, 0)
        except RecursionError:
            ok = False
        if ok:
            for c, v in sub.enums.items():
                merge_enum(res, c, v)
            res.contradictions |= sub.contradictions
            res.intersected |= sub.intersected
            for c in sub.contradictions:
                res.enums.pop(c, None)
            for c, f in sub.facets.items():
                merge_facets(res.facets.setdefault(c, {}), f)
            res.notnull |= sub.notnull
        else:
            res.unhandled.append(_text(piece))
    return res
