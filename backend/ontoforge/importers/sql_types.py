"""Types SQL → datatypes XSD de la table de datatypes OWL 2 (L48).

Le résultat est un nom court XSD (``int``, ``dateTime``…). ``xsd:date``, ``xsd:time``, ``xsd:duration`` et ``xsd:gYear`` ne font pas partie
de la table de datatypes OWL 2 (OWL 2 Structural Specification §4) : ils sont remplacés (``dateTime`` ou ``string``) et le remplacement est
signalé (``degraded``). Un type inconnu devient ``string`` (avis ``unknown_type``).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class SqlType:
    base: str                      # nom normalisé en minuscules, sans paramètres (« character varying »)
    params: list[str] = field(default_factory=list)
    unsigned: bool = False
    array: bool = False
    raw: str = ""


@dataclass
class Mapped:
    xsd: str
    degraded: Optional[str] = None  # type d'origine si le datatype XSD naturel est hors OWL 2
    note: Optional[str] = None      # code d'avis : unknown_type, json_as_string, set_as_string, bit_as_string…
    max_length: Optional[int] = None
    enum: Optional[list[str]] = None


_INT = {"smallint": "short", "int2": "short", "smallserial": "short", "serial2": "short",
        "int": "int", "integer": "int", "int4": "int", "mediumint": "int", "serial": "int", "serial4": "int",
        "bigint": "long", "int8": "long", "bigserial": "long", "serial8": "long", "int64": "long"}
_UNSIGNED = {"short": "unsignedShort", "int": "unsignedInt", "long": "unsignedLong", "byte": "unsignedByte"}
_DEC = {"decimal", "numeric", "number", "dec", "fixed", "money", "smallmoney", "numeric()"}
_DBL = {"double", "double precision", "float8", "float64"}
_FLT = {"real", "float4", "float32"}
_STR = {"char", "varchar", "nchar", "nvarchar", "text", "tinytext", "mediumtext", "longtext", "ntext", "citext", "character",
        "character varying", "national character", "national character varying", "national char", "national varchar", "char varying",
        "varchar2", "nvarchar2", "clob", "nclob", "name", "bpchar", "sysname", "string", "long varchar", "long", "uniqueidentifier",
        "uuid", "inet", "cidr", "macaddr", "macaddr8", "tsvector", "tsquery", "ltree", "hstore", "money_text", "oid", "regclass",
        "enum_text", "rowid", "urowid", "graphic", "vargraphic", "longvarchar", "varchar_ignorecase"}
_JSONISH = {"json", "jsonb", "xml", "sql_variant", "variant", "object", "array"}
_GEO = {"geometry", "geography", "point", "line", "lseg", "box", "path", "polygon", "circle", "linestring", "multipoint", "multilinestring",
        "multipolygon", "geometrycollection", "hierarchyid"}
_BIN = {"bytea", "blob", "tinyblob", "mediumblob", "longblob", "binary", "varbinary", "image", "raw", "long raw", "bfile"}
_TS = {"timestamp", "datetime", "datetime2", "smalldatetime", "timestamptz", "timestamp with time zone", "timestamp without time zone",
       "datetimeoffset", "timestamp with local time zone", "timestamp_ntz", "timestamp_ltz", "timestamp_tz"}
_TIMEISH = {"time", "timetz", "time with time zone", "time without time zone"}
def _ident(t) -> str:
    return t.v.lower() if t.k == "w" else t.v


def _continues(words: list[str], u: str) -> bool:
    """Le mot ``u`` (majuscule) prolonge-t-il le nom de type déjà lu ? Évite d'avaler « CHARACTER SET », « WITH », « TO »… d'une colonne."""
    w0 = words[0]
    if u == "PRECISION":
        return words == ["double"]
    if u == "VARYING":
        return w0 in ("character", "char", "bit", "national character", "national char") or words in (["national", "character"], ["national", "char"])
    if u in ("CHARACTER", "CHAR", "VARCHAR"):
        return words in (["national"], ["long"])
    if u == "RAW":
        return words == ["long"]
    if u in ("WITH", "WITHOUT", "LOCAL", "TIME", "ZONE"):
        return w0 in ("timestamp", "time") and (u != "TIME" or words[-1] in ("with", "without", "local")) and (u != "ZONE" or words[-1] == "time")
    if u in ("YEAR", "MONTH", "DAY", "HOUR", "MINUTE", "SECOND", "TO"):
        return w0 == "interval"
    return False


def parse_type(toks, i: int) -> tuple[SqlType, int]:
    """Lit un type à partir de ``toks[i]`` ; retourne (type, indice suivant). ``toks`` : jetons du lexeur."""
    words: list[str] = []
    params: list[str] = []
    unsigned = False
    n = len(toks)
    if i < n and toks[i].k in ("w", "q"):
        words = [_ident(toks[i])]
        i += 1
        while i + 1 < n and toks[i].is_p(".") and toks[i + 1].k in ("w", "q"):   # schéma.type : on garde le nom du type
            words = [_ident(toks[i + 1])]
            i += 2
    while words and i < n:
        t = toks[i]
        if t.is_p("("):
            depth, j, cur = 1, i + 1, []
            while j < n:
                tj = toks[j]
                if tj.is_p("("):
                    depth += 1
                elif tj.is_p(")"):
                    depth -= 1
                    if not depth:
                        break
                elif tj.is_p(",") and depth == 1:
                    params.append(" ".join(cur))
                    cur = []
                    j += 1
                    continue
                cur.append(tj.v)
                j += 1
            if cur:
                params.append(" ".join(cur))
            i = j + 1
            continue
        if t.k == "w" and t.u in ("UNSIGNED", "SIGNED", "ZEROFILL"):
            unsigned = unsigned or t.u == "UNSIGNED"
            i += 1
            continue
        if t.k == "w" and _continues(words, t.u):
            words.append(t.v.lower())
            if len(words) == 2 and words[0] in ("national", "long"):
                words = [" ".join(words)]
            i += 1
            continue
        break
    array = False
    while i + 1 < n and toks[i].is_p("[") and toks[i + 1].is_p("]"):
        array = True
        i += 2
    while i + 2 < n and toks[i].is_p("[") and toks[i + 1].k == "n" and toks[i + 2].is_p("]"):
        array = True
        i += 3
    base = " ".join(words)
    if base.startswith("timestamp") and "with" in words and "without" not in words:
        base = "timestamp with time zone"
    elif base.startswith("timestamp") and "without" in words:
        base = "timestamp without time zone"
    elif base.startswith("timestamp with local"):
        base = "timestamp with local time zone"
    elif base.startswith("time") and "with" in words and "without" not in words:
        base = "time with time zone"
    elif base.startswith("time") and "without" in words:
        base = "time without time zone"
    return SqlType(base=base, params=params, unsigned=unsigned, array=array, raw=base + (f"({','.join(params)})" if params else "")), i


def map_type(t: SqlType, dialect: str) -> Mapped:
    b, p = t.base, t.params
    plen = int(p[0]) if p and re.fullmatch(r"\d+", p[0]) else None
    if b in _INT or b in ("tinyint", "byte"):
        if b == "tinyint":
            if dialect == "mysql" and plen == 1 and not t.unsigned:
                return Mapped("boolean", note="tinyint1_as_boolean")
            x = "unsignedByte" if dialect == "sqlserver" else "byte"
        else:
            x = _INT.get(b, "byte")
        if t.unsigned and x in _UNSIGNED:
            x = _UNSIGNED[x]
        return Mapped(x)
    if b in _DEC:
        return Mapped("decimal")
    if b in _DBL:
        return Mapped("double")
    if b in _FLT:
        return Mapped("float")
    if b == "float":
        if plen is not None:
            return Mapped("float" if plen <= 24 else "double")
        return Mapped("float" if dialect == "mysql" else "double", note="float_ambiguous" if dialect in ("mysql", "generic") else None)
    if b in ("bool", "boolean"):
        return Mapped("boolean")
    if b == "bit":
        if plen is None or plen == 1:
            return Mapped("boolean")
        return Mapped("string", note="bit_as_string")
    if b in ("bit varying", "varbit"):
        return Mapped("string", note="bit_as_string")
    if b == "timestamp" and dialect == "sqlserver":
        return Mapped("hexBinary", note="rowversion")
    if b == "rowversion":
        return Mapped("hexBinary", note="rowversion")
    if b in _TS:
        return Mapped("dateTime")
    if b == "date":
        return Mapped("dateTime", degraded="date")
    if b in _TIMEISH:
        return Mapped("string", degraded="time")
    if b == "year":
        return Mapped("integer", degraded="year")
    if b == "interval" or b.startswith("interval ") or b == "timespan":
        return Mapped("string", degraded="duration")
    if b in _STR:
        if b in ("char", "varchar", "nchar", "nvarchar", "character", "character varying", "varchar2", "nvarchar2", "national character", "national character varying", "bpchar", "char varying", "national char", "national varchar") and plen:
            return Mapped("string", max_length=plen)
        return Mapped("string")
    if b in _BIN:
        return Mapped("base64Binary")
    if b in _JSONISH:
        return Mapped("string", note="json_as_string")
    if b in _GEO:
        return Mapped("string", note="geo_as_string")
    if b in ("enum", "set"):
        vals = [x for x in p]
        return Mapped("string", enum=vals if b == "enum" else None, note="set_as_string" if b == "set" else None)
    return Mapped("string", note="unknown_type")
