"""Lexeur SQL maison (L48) : PostgreSQL, MySQL / MariaDB, SQL Server, borné en nombre de jetons, en profondeur et en temps.

Une seule passe, sans retour arrière : chaque caractère est consommé au plus une fois (``str.find`` pour les chaînes et commentaires).
Types de jetons : ``w`` mot (identifiant nu ou mot-clé), ``q`` identifiant entre guillemets (``"x"``, `` `x` ``, ``[x]``),
``s`` littéral chaîne (y compris ``$$…$$``), ``n`` nombre, ``p`` ponctuation. ``u`` est la forme majuscule d'un mot.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from .limits import MAX_IDENT, MAX_STRING, MAX_TOKENS, Budget, ImportRefused

_WORD_START = re.compile(r"[^\W\d]|[#@]", re.U)
_WORD = re.compile(r"[\w$#@]+", re.U)
_NUM = re.compile(r"\d+(?:\.\d+)?(?:[eE][+-]?\d+)?|\.\d+(?:[eE][+-]?\d+)?")
_WS = re.compile(r"\s+")
_DOLLAR_TAG = re.compile(r"\$([A-Za-z_]\w*)?\$")
_TWO = {"::", "<>", "<=", ">=", "!=", "||", "->", ">>", "<<", ":="}


@dataclass(slots=True)
class Tok:
    k: str
    v: str
    line: int
    u: str = ""        # majuscule, pour les mots

    def is_kw(self, *names: str) -> bool:
        return self.k == "w" and self.u in names

    def is_p(self, ch: str) -> bool:
        return self.k == "p" and self.v == ch


def detect_dialect(text: str) -> str:
    """Devine le dialecte d'après des marques lexicales courantes. Ne sert qu'aux types ambigus et aux guillemets ; l'utilisateur peut l'imposer."""
    t = text[:400_000]
    score = {"postgresql": 0, "mysql": 0, "sqlserver": 0}
    if re.search(r"\[(?:dbo|sys)\]|\bIDENTITY\s*\(\s*\d+\s*,\s*\d+\s*\)|^\s*GO\s*$|\bNVARCHAR\s*\(\s*MAX\s*\)|\bSET\s+ANSI_NULLS|\bCLUSTERED\b|\buniqueidentifier\b|\bdatetime2\b", t, re.I | re.M):
        score["sqlserver"] += 3
    if re.search(r"`\w+`|\bENGINE\s*=|\bAUTO_INCREMENT\b|\bUNSIGNED\b|\bCHARSET\s*=|\bCOLLATE\s*=|/\*!\d{5}", t, re.I):
        score["mysql"] += 3
    if re.search(r"::\w|\bSERIAL\b|\bBIGSERIAL\b|\bBYTEA\b|\bTIMESTAMPTZ\b|\$\$|\bGENERATED\s+(?:ALWAYS|BY\s+DEFAULT)\s+AS\s+IDENTITY|\bCREATE\s+EXTENSION\b|\bSET\s+search_path\b|\bjsonb\b", t, re.I):
        score["postgresql"] += 3
    best = max(score, key=lambda k: score[k])
    return best if score[best] else "generic"


def tokenize(text: str, dialect: str, budget: Budget) -> tuple[list[Tok], list[str]]:
    """Retourne (jetons, avertissements). Lève ImportRefused si le script dépasse les bornes."""
    toks: list[Tok] = []
    warns: list[str] = []
    n, i, line = len(text), 0, 1
    backslash = dialect == "mysql"
    brackets = dialect == "sqlserver"
    depth = 0
    append = toks.append
    while i < n:
        budget.tick()
        if len(toks) > MAX_TOKENS:
            raise ImportRefused("too_many_tokens", 413, max=MAX_TOKENS)
        c = text[i]
        if c == "\n":
            line += 1
            i += 1
            continue
        if c in " \t\r\f\v ﻿":
            i += 1
            continue
        if c.isspace():
            m = _WS.match(text, i)
            line += text.count("\n", i, m.end())
            i = m.end()
            continue
        if c == "-" and text.startswith("--", i):
            j = text.find("\n", i)
            i = n if j < 0 else j
            continue
        if c == "#" and (i + 1 >= n or text[i + 1] in " \t\n\r") and dialect in ("mysql", "generic"):
            j = text.find("\n", i)
            i = n if j < 0 else j
            continue
        if c == "/" and text.startswith("/*", i):
            lvl, j = 1, i + 2
            while lvl and j < n:
                a, b = text.find("/*", j), text.find("*/", j)
                if b < 0:
                    j = n
                    lvl = -1
                    break
                if 0 <= a < b and dialect == "postgresql":
                    lvl += 1
                    j = a + 2
                else:
                    lvl -= 1
                    j = b + 2
                budget.tick()
            if lvl:
                warns.append("lex_unterminated_comment")
            line += text.count("\n", i, j)
            i = j
            continue
        if c == "'" or (c in "NnEeXxBbUu" and i + 1 < n and text[i + 1] == "'" and (i == 0 or not (text[i - 1].isalnum() or text[i - 1] == "_"))):
            esc = backslash or c in "Ee"
            start = i + (0 if c == "'" else 1)
            j = start + 1
            buf_end = -1
            while j < n:
                q = text.find("'", j)
                if q < 0:
                    break
                if esc:   # un antislash devant l'apostrophe : on saute
                    k, bs = q - 1, 0
                    while k > start and text[k] == "\\":
                        bs += 1
                        k -= 1
                    if bs % 2:
                        j = q + 1
                        continue
                if q + 1 < n and text[q + 1] == "'":
                    j = q + 2
                    continue
                buf_end = q
                break
            if buf_end < 0:
                warns.append("lex_unterminated_string")
                val, j = text[start + 1:], n
            else:
                val, j = text[start + 1:buf_end], buf_end + 1
            if len(val) > MAX_STRING:
                val = val[:MAX_STRING]
            val = val.replace("''", "'")
            if esc:
                val = re.sub(r"\\(.)", lambda m: {"n": "\n", "t": "\t", "r": "\r", "0": "\0"}.get(m.group(1), m.group(1)), val)
            append(Tok("s", val, line))
            line += text.count("\n", i, j)
            i = j
            continue
        if c == '"' or c == "`" or (c == "[" and brackets):
            close = {'"': '"', "`": "`", "[": "]"}[c]
            j = i + 1
            while True:
                q = text.find(close, j)
                if q < 0:
                    warns.append("lex_unterminated_ident")
                    q = n
                    break
                if q + 1 < n and text[q + 1] == close:   # "" `` ]] : guillemet doublé
                    j = q + 2
                    budget.tick()
                    continue
                break
            val = text[i + 1:q].replace(close * 2, close)
            if len(val) > MAX_IDENT:
                raise ImportRefused("ident_too_long", 422, max=MAX_IDENT, line=line)
            append(Tok("q", val, line))
            line += text.count("\n", i, q)
            i = min(n, q + 1)
            continue
        if c == "$":
            m = _DOLLAR_TAG.match(text, i)
            if m and (i == 0 or not (text[i - 1].isalnum() or text[i - 1] == "_")):
                end = text.find(m.group(0), m.end())
                body = text[m.end():] if end < 0 else text[m.end():end]
                if end < 0:
                    warns.append("lex_unterminated_string")
                j = n if end < 0 else end + len(m.group(0))
                append(Tok("s", body[:MAX_STRING], line))
                line += text.count("\n", i, j)
                i = j
                continue
        if c.isdigit() or (c == "." and i + 1 < n and text[i + 1].isdigit()):
            m = _NUM.match(text, i)
            append(Tok("n", m.group(0), line))
            i = m.end()
            continue
        if _WORD_START.match(c):
            m = _WORD.match(text, i)
            w = m.group(0)
            if len(w) > MAX_IDENT:
                raise ImportRefused("ident_too_long", 422, max=MAX_IDENT, line=line)
            append(Tok("w", w, line, w.upper()))
            i = m.end()
            continue
        two = text[i:i + 2]
        if two in _TWO:
            append(Tok("p", two, line))
            i += 2
            continue
        if c == "(" or c == "[":
            depth += 1
            if depth > MAX_DEPTH_SQL:
                raise ImportRefused("too_deep", 422, max=MAX_DEPTH_SQL, line=line)
        elif c == ")" or c == "]":
            depth = max(0, depth - 1)
        append(Tok("p", c, line))
        i += 1
    return toks, warns


MAX_DEPTH_SQL = 48
