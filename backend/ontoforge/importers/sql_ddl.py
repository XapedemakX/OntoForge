"""Analyseur DDL maison (L48) : ``CREATE TABLE``, ``ALTER TABLE … ADD``, ``CREATE [UNIQUE] INDEX``, ``COMMENT ON``, ``CREATE TYPE … AS ENUM``.

Dialectes : PostgreSQL, MySQL / MariaDB, SQL Server (et un SQL générique). Tout ce qui n'est pas du DDL de structure (données, vues, routines,
déclencheurs, droits, paramètres de session…) est compté dans ``Draft.ignored`` : jamais perdu en silence, jamais interprété.
Aucune exécution, aucun accès réseau, aucun module de base de données.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from . import sql_check
from .ir import Draft
from .limits import MAX_COLUMNS_TABLE, MAX_COLUMNS_TOTAL, MAX_ENUM, MAX_TABLES, Budget, ImportRefused
from .sql_lexer import Tok, detect_dialect, tokenize
from .sql_types import Mapped, SqlType, map_type, parse_type


@dataclass
class Column:
    name: str
    type: SqlType
    mapped: Mapped
    nullable: bool = True
    unique: bool = False
    auto: bool = False
    computed: bool = False
    comment: str = ""
    enum: Optional[list[tuple[str, bool]]] = None
    enum_dead: bool = False   # CHECK contradictoires : plus d'énumération
    facets: dict[str, str] = field(default_factory=dict)


@dataclass
class ForeignKey:
    cols: list[str]
    ref_name: str
    ref_schema: Optional[str]
    ref_cols: list[str]
    name: Optional[str] = None
    line: int = 0


@dataclass
class Table:
    name: str
    schema: Optional[str]
    columns: dict[str, Column] = field(default_factory=dict)       # clé : nom en minuscules
    pk: list[str] = field(default_factory=list)
    fks: list[ForeignKey] = field(default_factory=list)
    uniques: list[list[str]] = field(default_factory=list)
    comment: str = ""
    line: int = 0

    def col(self, name: str) -> Optional[Column]:
        return self.columns.get(name.lower())

    @property
    def qname(self) -> str:
        return f"{self.schema}.{self.name}" if self.schema else self.name


@dataclass
class Schema:
    tables: dict[tuple[str, str], Table] = field(default_factory=dict)
    dialect: str = "generic"
    enum_types: dict[str, list[str]] = field(default_factory=dict)
    domains: dict[str, tuple[SqlType, Optional[list[tuple[str, bool]]]]] = field(default_factory=dict)

    def find(self, schema: Optional[str], name: str) -> Optional[Table]:
        t = self.tables.get(((schema or "").lower(), name.lower()))
        if t:
            return t
        same = [x for (s, n), x in self.tables.items() if n == name.lower()]
        return same[0] if len(same) == 1 or (same and not schema) else None


_STARTS_NARROW = {"CREATE", "INSERT", "GRANT", "REVOKE", "TRUNCATE", "USE", "EXEC", "EXECUTE", "DECLARE", "COPY"}
_STARTS_AFTER_TABLE = _STARTS_NARROW | {"ALTER", "DROP", "SELECT", "SET", "UPDATE", "DELETE", "BEGIN", "COMMIT", "ROLLBACK", "VACUUM", "ANALYZE", "PRINT", "LOCK",
                                        "UNLOCK", "COMMENT", "SAVEPOINT", "RENAME", "CALL"}
_TEMP = {"TEMP", "TEMPORARY", "GLOBAL", "LOCAL", "UNLOGGED", "VOLATILE"}
_MODS_STOP = {"NOT", "NULL", "PRIMARY", "UNIQUE", "REFERENCES", "CHECK", "CONSTRAINT", "COMMENT", "COLLATE", "AUTO_INCREMENT", "AUTOINCREMENT", "IDENTITY",
              "GENERATED", "ON", "DEFAULT", "CHARACTER", "CHARSET", "AS", "KEY"}


def _split_statements(toks: list[Tok], budget: Budget) -> list[list[Tok]]:
    """Découpe en instructions : ``;``, ligne ``GO`` (SQL Server), et début d'une nouvelle instruction reconnaissable quand le ``;`` manque
    (après le corps d'un CREATE TABLE : ``ALTER``, ``COMMENT ON``, ``SET``… ; sinon seulement ``CREATE``, ``INSERT``, ``EXEC``…)."""
    out: list[list[Tok]] = []
    cur: list[Tok] = []
    depth = 0
    is_ct = body_closed = False
    n = len(toks)
    for i, t in enumerate(toks):
        budget.tick()
        if t.is_p("(") or t.is_p("["):
            depth += 1
        elif t.is_p(")") or t.is_p("]"):
            depth = max(0, depth - 1)
            if depth == 0 and is_ct and t.is_p(")"):
                body_closed = True
        elif depth == 0:
            if t.is_p(";"):
                if cur:
                    out.append(cur)
                cur, is_ct, body_closed = [], False, False
                continue
            if t.k == "w" and cur:
                u = t.u
                if u == "GO" and (i + 1 >= n or toks[i + 1].line != t.line or toks[i + 1].k == "n") and (i == 0 or toks[i - 1].line != t.line):
                    out.append(cur)
                    cur, is_ct, body_closed = [], False, False
                    continue
                brk = u in _STARTS_NARROW
                if body_closed and u in _STARTS_AFTER_TABLE:
                    brk = True
                if cur[0].is_kw("ALTER") and u == "ALTER":
                    brk = i + 1 < n and toks[i + 1].is_kw("TABLE")
                if u == "COMMENT":
                    brk = brk and i + 1 < n and toks[i + 1].is_kw("ON")
                if u == "COPY" and cur[0].is_kw("CREATE", "ALTER"):
                    brk = False
                if brk:
                    out.append(cur)
                    cur, is_ct, body_closed = [], False, False
            if t.k == "w" and t.u == "TABLE" and cur and cur[0].is_kw("CREATE") and len(cur) <= 7:
                is_ct = not any(x.is_kw("VIEW", "INDEX", "TYPE", "TRIGGER", "FUNCTION", "PROCEDURE") for x in cur)
        cur.append(t)
    if cur:
        out.append(cur)
    return out


class _P:
    """Analyse d'un script : porte le schéma en construction, le brouillon (avis, éléments ignorés) et le budget."""

    def __init__(self, draft: Draft, schema: Schema, budget: Budget):
        self.d, self.s, self.b = draft, schema, budget
        self.pending_comments: list[tuple[str, Optional[str], str, Optional[str], str]] = []   # (table, schema, column?, texte)
        self.total_cols = 0

    # ---- utilitaires de jetons ---------------------------------------------------------------
    @staticmethod
    def ident(t: Tok) -> str:
        return t.v

    def qname(self, st: list[Tok], i: int) -> tuple[Optional[str], str, int]:
        """Nom éventuellement qualifié (a.b.c) à partir de st[i] : retourne (schéma, nom, indice suivant)."""
        parts: list[str] = []
        n = len(st)
        while i < n and st[i].k in ("w", "q"):
            parts.append(st[i].v)
            i += 1
            if i + 1 < n and st[i].is_p(".") and (st[i + 1].k in ("w", "q") or st[i + 1].is_p(".")):
                i += 1
                if st[i].is_p("."):   # a..b (SQL Server) : schéma omis
                    i += 1
                continue
            break
        if not parts:
            raise ImportRefused("syntax", 422, line=st[min(i, n - 1)].line)
        return (parts[-2] if len(parts) >= 2 else None), parts[-1], i

    @staticmethod
    def match(st: list[Tok], i: int) -> int:
        depth = 0
        for j in range(i, len(st)):
            if st[j].is_p("("):
                depth += 1
            elif st[j].is_p(")"):
                depth -= 1
                if depth == 0:
                    return j
        return -1

    def paren_idents(self, st: list[Tok], i: int) -> tuple[list[str], int, bool]:
        """« ( a, b DESC, c(10) ) » → ([a, b, c], indice après la parenthèse, simple ?) ; ``simple`` faux si un élément est une expression."""
        if i >= len(st) or not st[i].is_p("("):
            return [], i, False
        j = self.match(st, i)
        if j < 0:
            return [], len(st), False
        names, simple, k, expect = [], True, i + 1, True
        depth = 0
        while k < j:
            t = st[k]
            if t.is_p("("):
                depth += 1
            elif t.is_p(")"):
                depth -= 1
            elif depth == 0 and t.is_p(","):
                expect = True
            elif depth == 0 and expect:
                if t.k in ("w", "q"):
                    names.append(t.v)
                else:
                    simple = False
                expect = False
            elif depth == 0 and t.k == "w" and t.u not in ("ASC", "DESC", "NULLS", "FIRST", "LAST", "COLLATE") and not st[k - 1].is_kw("COLLATE", "NULLS"):
                pass
            k += 1
        return names, j + 1, simple

    def skip_group(self, st: list[Tok], i: int) -> int:
        if i < len(st) and st[i].is_p("("):
            j = self.match(st, i)
            return (j + 1) if j > 0 else len(st)
        return i

    # ---- instructions ------------------------------------------------------------------------
    def statement(self, st: list[Tok]) -> None:
        self.b.tick(8)
        w = [t.u for t in st[:8] if t.k == "w"]
        first = w[0] if w else ""
        if first == "CREATE":
            self.create(st)
        elif first == "ALTER" and len(w) > 1 and w[1] == "TABLE":
            self.alter(st)
        elif first == "COMMENT" and len(w) > 1 and w[1] == "ON":
            self.comment_on(st)
        elif first in ("EXEC", "EXECUTE") and any(t.k in ("w", "q") and t.v.lower() == "sp_addextendedproperty" for t in st[:6]):
            self.ext_property(st)
        else:
            self.d.ignore(self.other_category(first, w), " ".join(t.v for t in st[:8]))

    @staticmethod
    def other_category(first: str, w: list[str]) -> str:
        if first in ("INSERT", "COPY", "UPDATE", "DELETE", "TRUNCATE", "MERGE"):
            return "data"
        if first in ("SET", "USE", "DECLARE", "BEGIN", "COMMIT", "ROLLBACK", "START", "LOCK", "UNLOCK", "PRINT", "GO", "SAVEPOINT", "VACUUM", "ANALYZE"):
            return "session"
        if first in ("GRANT", "REVOKE", "DENY"):
            return "grant"
        if first == "DROP":
            return "drop"
        if first == "ALTER":
            return "alter_other"
        if first == "COMMENT":
            return "comment_other"
        if first == "SELECT":
            return "data"
        return "other_statement"

    def create(self, st: list[Tok]) -> None:
        n, i, temp = len(st), 1, False
        while i < n and st[i].k == "w" and st[i].u in ({"OR", "REPLACE", "UNIQUE", "CLUSTERED", "NONCLUSTERED", "COLUMNSTORE", "FULLTEXT", "SPATIAL", "MATERIALIZED", "RECURSIVE", "DEFINER", "ALGORITHM", "SQL"} | _TEMP | {"EXTERNAL", "TRANSIENT"}):
            if st[i].u in _TEMP and st[i].u not in ("GLOBAL", "LOCAL"):
                temp = True
            if st[i].u in ("DEFINER", "ALGORITHM", "SQL"):
                # CREATE DEFINER=`x`@`y` VIEW … : on saute jusqu'à l'objet
                while i < n and not (st[i].k == "w" and st[i].u in ("VIEW", "TRIGGER", "PROCEDURE", "FUNCTION", "EVENT")):
                    i += 1
                break
            i += 1
        if i >= n:
            self.d.ignore("other_statement", " ".join(t.v for t in st[:6]))
            return
        kind = st[i].u if st[i].k == "w" else ""
        unique = any(t.is_kw("UNIQUE") for t in st[:i])
        if kind == "TABLE":
            self.create_table(st, i + 1, temp)
        elif kind == "INDEX":
            self.create_index(st, i + 1, unique)
        elif kind == "TYPE":
            self.create_type(st, i + 1)
        elif kind == "DOMAIN":
            self.create_domain(st, i + 1)
        elif kind in ("VIEW",):
            self.d.ignore("view", " ".join(t.v for t in st[i:i + 3]))
        elif kind in ("FUNCTION", "PROCEDURE", "PROC", "AGGREGATE", "OPERATOR"):
            self.d.ignore("routine", " ".join(t.v for t in st[i:i + 3]))
        elif kind in ("TRIGGER", "EVENT", "RULE", "POLICY"):
            self.d.ignore("trigger", " ".join(t.v for t in st[i:i + 3]))
        elif kind == "SEQUENCE":
            self.d.ignore("sequence", " ".join(t.v for t in st[i:i + 3]))
        else:
            self.d.ignore("other_statement", " ".join(t.v for t in st[:6]))

    # ---- CREATE TABLE ------------------------------------------------------------------------
    def create_table(self, st: list[Tok], i: int, temp: bool) -> None:
        n = len(st)
        while i < n and st[i].k == "w" and st[i].u in ("IF", "NOT", "EXISTS", "ONLY"):
            i += 1
        schema, name, i = self.qname(st, i)
        line = st[min(i, n - 1)].line
        if temp or name.startswith("#") or name.startswith("@"):
            self.d.ignore("temp_table", name)
            return
        if i >= n or not st[i].is_p("("):
            self.d.ignore("table_other", name)
            self.d.notice("table_not_parsed", "warning", name, table=name)
            return
        end = self.match(st, i)
        if end < 0:
            raise ImportRefused("syntax", 422, line=line)
        if len(self.s.tables) >= MAX_TABLES:
            raise ImportRefused("too_many_tables", 413, max=MAX_TABLES)
        key = ((schema or "").lower(), name.lower())
        if key in self.s.tables:
            self.d.notice("duplicate_table", "warning", name, table=name)
            return
        tbl = Table(name=name, schema=schema, line=line)
        self.s.tables[key] = tbl
        for item in self.split_commas(st[i + 1:end]):
            self.b.tick()
            if item:
                self.table_item(tbl, item)
        self.table_tail(tbl, st[end + 1:])

    @staticmethod
    def split_commas(toks: list[Tok]) -> list[list[Tok]]:
        parts, cur, depth = [], [], 0
        for t in toks:
            if t.is_p("(") or t.is_p("["):
                depth += 1
            elif t.is_p(")") or t.is_p("]"):
                depth -= 1
            if t.is_p(",") and depth == 0:
                parts.append(cur)
                cur = []
            else:
                cur.append(t)
        parts.append(cur)
        return parts

    def table_tail(self, tbl: Table, tail: list[Tok]) -> None:
        if not tail:
            return
        storage = False
        i = 0
        while i < len(tail):
            t = tail[i]
            if t.is_kw("COMMENT"):
                j = i + 1
                if j < len(tail) and tail[j].is_p("="):
                    j += 1
                if j < len(tail) and tail[j].k == "s":
                    tbl.comment = tail[j].v
                    i = j + 1
                    continue
            if t.is_kw("INHERITS"):
                self.d.notice("inherits", "review", tbl.name, table=tbl.name)
            if t.k == "w" and t.u in ("ENGINE", "CHARSET", "CHARACTER", "COLLATE", "AUTO_INCREMENT", "ROW_FORMAT", "PARTITION", "TABLESPACE", "WITH", "ON", "DEFAULT", "STORAGE", "DISTRIBUTED", "USING", "INHERITS", "TEXTIMAGE_ON", "FILESTREAM_ON", "UNLOGGED", "PCTFREE", "COMPRESS", "OPTIONS"):
                storage = True
            i += 1
        if storage:
            self.d.ignore("storage", tbl.name)

    def table_item(self, tbl: Table, toks: list[Tok]) -> None:
        i, cname = 0, None
        if toks[0].is_kw("CONSTRAINT") and len(toks) > 2:
            cname, i = toks[1].v, 2
        h = toks[i] if i < len(toks) else None
        if h is None:
            return
        nxt = toks[i + 1] if i + 1 < len(toks) else None
        nxt2 = toks[i + 2] if i + 2 < len(toks) else None
        if h.is_kw("PRIMARY") and nxt is not None and nxt.is_kw("KEY"):
            k = i + 2
            while k < len(toks) and toks[k].k == "w" and toks[k].u in ("CLUSTERED", "NONCLUSTERED", "HASH", "BTREE", "USING"):
                k += 1
            cols, _, _ = self.paren_idents(toks, k)
            self.set_pk(tbl, cols)
        elif h.is_kw("UNIQUE"):
            k = i + 1
            while k < len(toks) and toks[k].k in ("w", "q") and not toks[k].is_p("("):
                k += 1
            cols, _, _ = self.paren_idents(toks, k)
            if cols:
                tbl.uniques.append(cols)
        elif h.is_kw("FOREIGN") and nxt is not None and nxt.is_kw("KEY"):
            self.foreign_key(tbl, toks, i + 2, cname)
        elif h.is_kw("CHECK") and nxt is not None and nxt.is_p("("):
            e = self.match(toks, i + 1)
            self.apply_check(tbl, None, toks[i + 2:e] if e > 0 else toks[i + 2:])
        elif (h.is_kw("KEY", "INDEX") and nxt is not None and (nxt.is_p("(") or (nxt.k in ("w", "q") and nxt2 is not None and (nxt2.is_p("(") or nxt2.is_kw("USING"))))) \
                or h.is_kw("FULLTEXT", "SPATIAL", "EXCLUDE", "PERIOD", "LIKE", "SORTKEY", "DISTKEY"):
            self.d.ignore("index" if h.u in ("KEY", "INDEX", "FULLTEXT", "SPATIAL") else "table_other", f"{tbl.name}: {h.v}")
        elif h.is_kw("CONSTRAINT") or cname:
            self.d.ignore("table_other", f"{tbl.name}: {h.v}")
        else:
            self.column(tbl, toks)

    def set_pk(self, tbl: Table, cols: list[str]) -> None:
        if tbl.pk:
            self.d.notice("pk_twice", "warning", tbl.name, table=tbl.name)
            return
        tbl.pk = cols
        for c in cols:
            col = tbl.col(c)
            if col:
                col.nullable = False

    def apply_check(self, tbl: Table, only: Optional[str], toks: list[Tok]) -> None:
        r = sql_check.analyze_check(toks, self.b)
        for c in sorted(r.contradictions):
            self.d.notice("check_contradiction", "review", tbl.name, table=tbl.name, column=c)
        for c, vals in r.enums.items():
            col = tbl.col(c)
            if col is None or (only and c.lower() != only.lower()):
                r.unhandled.append(f"{c} IN (…)")
                continue
            if c in r.intersected:
                self.d.notice("check_intersected", "info", tbl.name, table=tbl.name, column=c)
            if col.enum_dead:
                continue
            if col.enum:   # CHECK successifs sur la colonne : ET, donc intersection
                keep = set(vals)
                inter = [v for v in col.enum if v in keep]
                self.d.notice("check_intersected" if inter else "check_contradiction", "info" if inter else "review", tbl.name, table=tbl.name, column=c)
                if not inter:
                    col.enum, col.enum_dead = None, True
                    continue
                col.enum = inter
            else:
                col.enum = list(vals)
        for c, f in r.facets.items():
            col = tbl.col(c)
            if col is None or (only and c.lower() != only.lower()):
                r.unhandled.append(f"{c} {','.join(f)}")
                continue
            sql_check.merge_facets(col.facets, f)
        for c in r.notnull:
            col = tbl.col(c)
            if col:
                col.nullable = False
        for u in r.unhandled:
            self.d.ignore("check_complex", f"{tbl.name}: {u}")

    def foreign_key(self, tbl: Table, toks: list[Tok], i: int, cname: Optional[str]) -> None:
        name = cname
        if i < len(toks) and toks[i].k in ("w", "q") and not toks[i].is_p("("):
            name = name or toks[i].v
            i += 1
        cols, i, _ = self.paren_idents(toks, i)
        if i < len(toks) and toks[i].is_kw("REFERENCES"):
            self.references(tbl, cols, toks, i + 1, name)
        else:
            self.d.ignore("table_other", f"{tbl.name}: FOREIGN KEY")

    def references(self, tbl: Table, cols: list[str], toks: list[Tok], i: int, name: Optional[str]) -> int:
        schema, ref, i = self.qname(toks, i)
        ref_cols, i, _ = self.paren_idents(toks, i)
        n = len(toks)
        acted = False
        while i < n and toks[i].k == "w" and toks[i].u in ("MATCH", "ON", "NOT", "DEFERRABLE", "INITIALLY", "ENFORCED", "NOCHECK", "DEFERRED", "IMMEDIATE", "FULL", "SIMPLE", "PARTIAL"):
            if toks[i].is_kw("ON") and i + 1 < n and toks[i + 1].is_kw("DELETE", "UPDATE"):
                acted = True
                i += 2
                while i < n and toks[i].k == "w" and toks[i].u in ("CASCADE", "RESTRICT", "NO", "ACTION", "SET", "NULL", "DEFAULT"):
                    i += 1
                    if i < n and toks[i].is_p("("):   # SET NULL (col)
                        i = self.skip_group(toks, i)
                continue
            if toks[i].is_kw("ON"):
                break
            i += 1
        if acted:
            self.d.ignore("fk_action", f"{tbl.name} → {ref}")
        tbl.fks.append(ForeignKey(cols=cols, ref_name=ref, ref_schema=schema, ref_cols=ref_cols, name=name, line=toks[0].line))
        return i

    # ---- colonnes ----------------------------------------------------------------------------
    def column(self, tbl: Table, toks: list[Tok]) -> None:
        if toks[0].k not in ("w", "q") or len(toks) < 2:
            self.d.ignore("table_other", f"{tbl.name}: {toks[0].v}")
            return
        name = toks[0].v
        if tbl.col(name):
            self.d.notice("duplicate_column", "warning", f"{tbl.name}.{name}", table=tbl.name, column=name)
            return
        self.total_cols += 1
        if len(tbl.columns) >= MAX_COLUMNS_TABLE or self.total_cols > MAX_COLUMNS_TOTAL:
            raise ImportRefused("too_many_columns", 413, max=MAX_COLUMNS_TABLE, total=MAX_COLUMNS_TOTAL)
        typ, i = parse_type(toks, 1)
        enum_from_type: Optional[list[tuple[str, bool]]] = None
        dom = self.s.domains.get(typ.base)
        if dom:
            typ, enum_from_type = dom[0], dom[1]
        mapped = map_type(typ, self.s.dialect)
        if typ.base in self.s.enum_types:
            enum_from_type = [(v, False) for v in self.s.enum_types[typ.base]]
            mapped = Mapped("string", note="enum_type")
        elif mapped.note == "unknown_type" and not dom:
            self.d.notice("unknown_type", "warning", f"{tbl.name}.{name}", table=tbl.name, column=name, type=typ.raw or "?")
        col = Column(name=name, type=typ, mapped=mapped)
        if mapped.enum is not None:
            col.enum = [(v, False) for v in mapped.enum][:MAX_ENUM]
        elif enum_from_type:
            col.enum = list(enum_from_type)
        if typ.base in ("serial", "smallserial", "bigserial", "serial2", "serial4", "serial8"):
            col.auto, col.nullable = True, False
        tbl.columns[name.lower()] = col
        n = len(toks)
        pending_fk: Optional[str] = None
        while i < n:
            self.b.tick()
            t = toks[i]
            if t.k != "w":
                if t.is_p("("):
                    i = self.skip_group(toks, i)
                else:
                    i += 1
                continue
            u = t.u
            if u == "CONSTRAINT":
                pending_fk = toks[i + 1].v if i + 1 < n else None
                i += 2
            elif u == "NOT" and i + 1 < n and toks[i + 1].is_kw("NULL"):
                col.nullable = False
                i += 2
            elif u == "NOT":   # NOT FOR REPLICATION, NOT DEFERRABLE…
                i += 2
            elif u == "NULL":
                i += 1
            elif u == "PRIMARY":
                i += 2
                if not tbl.pk:
                    tbl.pk = [name]
                col.nullable = False
            elif u == "UNIQUE":
                col.unique = True
                i += 1
                if i < n and toks[i].is_kw("KEY"):
                    i += 1
            elif u == "REFERENCES":
                i = self.references(tbl, [name], toks, i + 1, pending_fk)
                pending_fk = None
            elif u == "CHECK" and i + 1 < n and toks[i + 1].is_p("("):
                e = self.match(toks, i + 1)
                self.apply_check(tbl, name, toks[i + 2:e] if e > 0 else toks[i + 2:])
                i = (e + 1) if e > 0 else n
            elif u == "DEFAULT":
                self.d.ignore("default", f"{tbl.name}.{name}")
                i = self.skip_default(toks, i + 1)
            elif u in ("AUTO_INCREMENT", "AUTOINCREMENT"):
                col.auto = True
                i += 1
            elif u == "IDENTITY":
                col.auto, col.nullable = True, False
                i = self.skip_group(toks, i + 1)
            elif u == "GENERATED":
                k = i + 1
                while k < n and toks[k].k == "w" and toks[k].u in ("ALWAYS", "BY", "DEFAULT"):
                    k += 1
                if k < n and toks[k].is_kw("AS"):
                    if k + 1 < n and toks[k + 1].is_kw("IDENTITY"):
                        col.auto, col.nullable = True, False
                        k = self.skip_group(toks, k + 2)
                    else:
                        col.computed = True
                        self.d.ignore("computed", f"{tbl.name}.{name}")
                        k = self.skip_group(toks, k + 1)
                        if k < n and toks[k].is_kw("STORED", "VIRTUAL", "PERSISTED"):
                            k += 1
                i = max(k, i + 1)
            elif u == "AS" and i + 1 < n and toks[i + 1].is_p("("):
                col.computed = True
                self.d.ignore("computed", f"{tbl.name}.{name}")
                i = self.skip_group(toks, i + 1)
                if i < n and toks[i].is_kw("PERSISTED", "STORED", "VIRTUAL"):
                    i += 1
            elif u == "COMMENT" and i + 1 < n and toks[i + 1].k == "s":
                col.comment = toks[i + 1].v
                i += 2
            elif u in ("COLLATE", "CHARSET") or (u == "CHARACTER" and i + 1 < n and toks[i + 1].is_kw("SET")):
                self.d.ignore("collation", f"{tbl.name}.{name}")
                i += 3 if u == "CHARACTER" else 2
            elif u == "ON" and i + 1 < n and toks[i + 1].is_kw("UPDATE"):
                i = self.skip_default(toks, i + 2)
            else:
                i += 1

    def skip_default(self, toks: list[Tok], i: int) -> int:
        """Saute l'expression d'un DEFAULT : un littéral, un appel ``f(...)``, un groupe ``(…)``, ``NEXT VALUE FOR s``, avec ses ``::type``."""
        n = len(toks)
        if i >= n:
            return i
        t = toks[i]
        if t.is_p("("):
            i = self.skip_group(toks, i)
        elif t.k == "p" and t.v in "+-":
            i = self.skip_default(toks, i + 1)
        elif t.k == "w" and t.u == "NEXT" and i + 3 < n and toks[i + 1].is_kw("VALUE"):
            i += 4
        elif t.k in ("w", "q"):
            i += 1
            while i + 1 < n and toks[i].is_p(".") and toks[i + 1].k in ("w", "q"):
                i += 2
            if i < n and toks[i].is_p("("):
                i = self.skip_group(toks, i)
        else:
            i += 1
        while i < n and toks[i].is_p("::"):
            i += 1
            while i < n and toks[i].k == "w" and toks[i].u not in _MODS_STOP:
                i += 1
                if i < n and toks[i].is_p("("):
                    i = self.skip_group(toks, i)
        while i + 1 < n and toks[i].is_p("[") and toks[i + 1].is_p("]"):
            i += 2
        return i

    # ---- ALTER TABLE -------------------------------------------------------------------------
    def alter(self, st: list[Tok]) -> None:
        n, i = len(st), 2
        while i < n and st[i].k == "w" and st[i].u in ("ONLY", "IF", "EXISTS"):
            i += 1
        schema, name, i = self.qname(st, i)
        tbl = self.s.find(schema, name)
        if tbl is None:
            self.d.ignore("alter_other", f"ALTER TABLE {name}")
            return
        for act in self.split_commas(st[i:]):
            self.b.tick()
            if not act:
                continue
            k = 0
            while k < len(act) and act[k].k == "w" and act[k].u in ("WITH", "CHECK", "NOCHECK", "NOT", "VALID", "ONLY"):
                if act[k].u in ("CHECK", "NOCHECK") and k + 1 < len(act) and act[k + 1].is_kw("CONSTRAINT"):
                    break
                k += 1
            act = act[k:]
            if not act:
                continue
            if act[0].is_kw("ADD"):
                rest = act[1:]
                if rest and rest[0].is_kw("COLUMN"):
                    rest = rest[1:]
                    while rest and rest[0].is_kw("IF", "NOT", "EXISTS"):
                        rest = rest[1:]
                    if rest:
                        self.column(tbl, rest)
                    continue
                if rest and rest[0].is_kw("DEFAULT"):
                    self.d.ignore("default", f"{tbl.name}")
                    continue
                if rest and rest[0].is_kw("CONSTRAINT") and len(rest) > 3 and rest[2].is_kw("DEFAULT"):
                    self.d.ignore("default", f"{tbl.name}")
                    continue
                if rest and (rest[0].is_kw("CONSTRAINT", "PRIMARY", "UNIQUE", "FOREIGN", "CHECK", "KEY", "INDEX", "FULLTEXT", "SPATIAL")):
                    self.table_item(tbl, rest)
                elif rest:
                    self.column(tbl, rest)
            elif act[0].is_kw("ALTER") and any(t.is_kw("SET") for t in act[:5]) and any(t.is_kw("NOT") for t in act[:6]) and any(t.is_kw("NULL") for t in act[:7]):
                ci = 2 if act[1].is_kw("COLUMN") else 1
                col = tbl.col(act[ci].v) if ci < len(act) else None
                if col:
                    col.nullable = False
            else:
                self.d.ignore("alter_other", f"{tbl.name}: {act[0].v}")

    # ---- index, types, commentaires ----------------------------------------------------------
    def create_index(self, st: list[Tok], i: int, unique: bool) -> None:
        n = len(st)
        while i < n and st[i].k == "w" and st[i].u in ("CONCURRENTLY", "IF", "NOT", "EXISTS"):
            i += 1
        if i < n and st[i].k in ("w", "q") and not st[i].is_kw("ON"):
            i += 1
        if i < n and st[i].is_kw("ON"):
            i += 1
            while i < n and st[i].is_kw("ONLY"):
                i += 1
            schema, name, i = self.qname(st, i)
            while i < n and not st[i].is_p("(") and not st[i].is_kw("WHERE"):
                i += 1
            cols, j, simple = self.paren_idents(st, i)
            tbl = self.s.find(schema, name)
            has_where = any(t.is_kw("WHERE") for t in st[j:])
            if unique and tbl and cols and simple and not has_where and all(tbl.col(c) for c in cols):
                tbl.uniques.append(cols)
                return
            self.d.ignore("index", f"{name}")
            return
        self.d.ignore("index", " ".join(t.v for t in st[:6]))

    def create_type(self, st: list[Tok], i: int) -> None:
        schema, name, i = self.qname(st, i)
        if i + 1 < len(st) and st[i].is_kw("AS") and st[i + 1].is_kw("ENUM") and i + 2 < len(st) and st[i + 2].is_p("("):
            e = self.match(st, i + 2)
            vals = [t.v for t in st[i + 3:e if e > 0 else len(st)] if t.k == "s"][:MAX_ENUM]
            self.s.enum_types[name.lower()] = vals
        else:
            self.d.ignore("other_statement", f"CREATE TYPE {name}")

    def create_domain(self, st: list[Tok], i: int) -> None:
        schema, name, i = self.qname(st, i)
        if i < len(st) and st[i].is_kw("AS"):
            i += 1
        typ, i = parse_type(st, i)
        enum = None
        for k in range(i, len(st)):
            if st[k].is_kw("CHECK") and k + 1 < len(st) and st[k + 1].is_p("("):
                e = self.match(st, k + 1)
                r = sql_check.analyze_check(st[k + 2:e if e > 0 else len(st)], self.b)
                for c, vals in r.enums.items():
                    if c.upper() == "VALUE":
                        enum = vals
        self.s.domains[name.lower()] = (typ, enum)

    def comment_on(self, st: list[Tok]) -> None:
        n = len(st)
        if n < 5 or not st[2].is_kw("TABLE", "COLUMN"):
            self.d.ignore("comment_other", " ".join(t.v for t in st[:5]))
            return
        kind = st[2].u
        parts: list[str] = []
        i = 3
        while i < n and st[i].k in ("w", "q") and not st[i].is_kw("IS"):
            parts.append(st[i].v)
            i += 1
            if i < n and st[i].is_p("."):
                i += 1
        if i + 1 < n and st[i].is_kw("IS") and st[i + 1].k == "s":
            text = st[i + 1].v
            if kind == "TABLE" and parts:
                self.pending_comments.append((parts[-1], parts[-2] if len(parts) > 1 else None, "", None, text))
            elif kind == "COLUMN" and len(parts) >= 2:
                self.pending_comments.append((parts[-2], parts[-3] if len(parts) > 2 else None, parts[-1], None, text))

    def ext_property(self, st: list[Tok]) -> None:
        vals = [t.v for t in st if t.k == "s"]
        if len(vals) >= 6 and vals[0].lower() == "ms_description":
            text = vals[1]
            d = {vals[i].upper(): vals[i + 1] for i in range(2, len(vals) - 1, 2)}
            tname, sch = d.get("TABLE"), d.get("SCHEMA")
            if tname:
                self.pending_comments.append((tname, sch, d.get("COLUMN", ""), None, text))
                return
        self.d.ignore("comment_other", "sp_addextendedproperty")

    def finish(self) -> None:
        for tname, sch, col, _, text in self.pending_comments:
            tbl = self.s.find(sch, tname)
            if not tbl:
                continue
            if col:
                c = tbl.col(col)
                if c and not c.comment:
                    c.comment = text[:2000]
            elif not tbl.comment:
                tbl.comment = text[:2000]


def parse_ddl(texts: list[tuple[str, str]], dialect: str, draft: Draft, budget: Budget) -> Schema:
    """Analyse un ou plusieurs scripts ``(nom de fichier, texte)``. ``dialect`` : auto, postgresql, mysql, sqlserver ou generic."""
    joined = "\n".join(t for _, t in texts)[:600_000]
    d = detect_dialect(joined) if dialect in ("", "auto", None) else dialect
    schema = Schema(dialect=d)
    draft.dialect = d
    p = _P(draft, schema, budget)
    for fname, text in texts:
        toks, warns = tokenize(text, d, budget)
        for w in warns:
            draft.notice(w, "warning", fname, file=fname)
        for st in _split_statements(toks, budget):
            try:
                p.statement(st)
            except ImportRefused as exc:
                if exc.code in ("syntax",):
                    draft.notice("syntax_skipped", "warning", fname, file=fname, line=exc.params.get("line", st[0].line))
                    continue
                raise
    p.finish()
    return schema
