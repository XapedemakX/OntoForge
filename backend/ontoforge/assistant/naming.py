"""Conventions de nommage : classes PascalCase, propriétés camelCase."""
from __future__ import annotations

import re
import unicodedata


def _words(s: str) -> list[str]:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    s = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", s)
    return [w for w in re.split(r"[^A-Za-z0-9]+", s) if w]


def pascal(s: str) -> str:
    out = "".join(w[:1].upper() + w[1:].lower() for w in _words(s))
    return out if out and not out[0].isdigit() else "X" + out


def camel(s: str) -> str:
    p = pascal(s)
    return p[:1].lower() + p[1:]


def humanize(s: str) -> str:
    return " ".join(w.lower() for w in _words(s))


def singular(s: str) -> str:
    w = s
    low = w.lower()
    if low.endswith("ies") and len(w) > 4:
        return w[:-3] + "y"
    if low.endswith(("sses", "xes", "ches", "shes")):
        return w[:-2]
    if low.endswith("s") and not low.endswith(("ss", "us", "is")) and len(w) > 3:
        return w[:-1]
    return w
