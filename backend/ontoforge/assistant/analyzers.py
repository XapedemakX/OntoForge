"""Pré-analyseurs déterministes CSV et SQL → squelette JSON intermédiaire (voir convert.py)."""
from __future__ import annotations

import csv
import io
import re
from typing import Any

from .naming import camel, humanize, pascal, singular

Skeleton = dict[str, Any]

SQL_TYPES = [
    (r"^(tiny|small|big|medium)?int|^serial|^bigserial|^smallserial|^integer", "integer"),
    (r"^(decimal|numeric|number|money)", "decimal"),
    (r"^(float|double|real)", "double"),
    (r"^(bool|bit)", "boolean"),
    (r"^(timestamp|datetime)", "dateTime"),
    (r"^date$", "dateTime"),
    (r"^(char|varchar|nvarchar|nchar|text|string|uuid|clob|citext)", "string"),
]


def sql_type(t: str) -> str:
    t = t.strip().lower()
    for rx, x in SQL_TYPES:
        if re.search(rx, t):
            return x
    return "string"


def _new(kind: str) -> Skeleton:
    return {"classes": [], "object_properties": [], "datatype_properties": [], "warnings": [], "source": kind}


# ----------------------------------------------------------------------------- CSV
def infer_type(values: list[str]) -> str:
    vals = [v.strip() for v in values if v is not None and v.strip() != ""]
    if not vals:
        return "string"
    if all(re.fullmatch(r"[+-]?\d+", v) for v in vals):
        return "integer"
    if all(re.fullmatch(r"[+-]?\d+([.,]\d+)?", v) for v in vals):
        return "decimal"
    if all(v.lower() in ("true", "false", "oui", "non", "yes", "no") for v in vals):
        return "boolean"
    if all(re.fullmatch(r"\d{4}-\d{2}-\d{2}([T ]\d{2}:\d{2}(:\d{2})?.*)?", v) for v in vals):
        return "dateTime"
    return "string"


def analyze_csv(text: str, filename: str | None = None) -> Skeleton:
    sk = _new("csv")
    lines = text.strip().splitlines()
    name = None
    while lines and lines[0].lstrip().startswith("#"):
        m = re.match(r"#\s*(?:table|name|classe?|entity)\s*[:=]\s*(\S+)", lines[0].strip(), re.I)
        if m:
            name = m.group(1)
        lines = lines[1:]
    if not lines:
        sk["warnings"].append("CSV vide : aucun en-tête détecté.")
        return sk
    body = "\n".join(lines)
    try:
        dialect = csv.Sniffer().sniff(lines[0], delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel
    rows = list(csv.reader(io.StringIO(body), dialect))
    header, data = rows[0], rows[1:51]
    cols = [c.strip() for c in header]
    if name is None:
        pk = next((c for c in cols if re.fullmatch(r"(?i)(id[_ ]?\w+|\w+[_ ]id)", c)), None)
        base = re.sub(r"(?i)(^id[_ ]|[_ ]id$)", "", pk) if pk else ""
        stem = re.sub(r"\.[A-Za-z0-9]+$", "", (filename or "").replace("\\", "/").rsplit("/", 1)[-1]).strip()
        name = base or stem or "Record"
        if not base and stem:
            sk["warnings"].append(f"Nom de classe déduit du nom du fichier « {filename} » (ou ajoutez une première ligne « # table: nom »).")
        elif not base:
            sk["warnings"].append("Nom de classe non déterminé : « Record » par défaut (ajoutez une première ligne « # table: nom »).")
    cname = pascal(singular(name))
    key: list[str] = []
    dps = []
    ops = []
    for i, col in enumerate(cols):
        if not col:
            continue
        values = [r[i] for r in data if i < len(r)]
        low = col.lower()
        is_id = bool(re.fullmatch(r"(id|uuid|(\w+[_ ])?id)", low))
        if is_id and not key and (low == "id" or pascal(singular(re.sub(r"[_ ]?id$", "", low))) == cname):
            dps.append({"name": camel(col), "label_en": humanize(col), "domain": cname, "range": "string" if infer_type(values) == "string" else infer_type(values),
                        "functional": True, "required": True})
            key.append(camel(col))
            continue
        if is_id and low != "id":
            target = pascal(singular(re.sub(r"[_ ]?id$", "", low)))
            ops.append({"name": "has" + target, "label_en": "has " + humanize(target), "domain": cname, "range": target, "functional": True})
            sk["classes"].append({"name": target, "label_en": humanize(target), "comment": "Classe référencée par la colonne " + col + " (à détailler)."})
            sk["warnings"].append(f"Colonne « {col} » interprétée comme référence vers la classe {target} (clé étrangère supposée).")
            continue
        t = infer_type(values)
        if t == "dateTime" and any(re.fullmatch(r"\d{4}-\d{2}-\d{2}", v.strip()) for v in values):
            sk["warnings"].append(f"Colonne « {col} » : date sans heure ; xsd:date n'est pas dans la table de datatypes OWL 2 DL, xsd:dateTime est utilisé.")
        dps.append({"name": camel(col), "label_en": humanize(col), "domain": cname, "range": t, "functional": True,
                    "required": bool(values) and all((v or "").strip() for v in values)})
    sk["classes"].insert(0, {"name": cname, "label_en": humanize(cname), "key": key})
    sk["datatype_properties"], sk["object_properties"] = dps, ops
    if not key:
        sk["warnings"].append("Aucune clé candidate détectée : choisissez un identifiant (owl:hasKey).")
    sk["classes"] = _dedupe(sk["classes"])
    return sk


def _dedupe(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: dict[str, dict[str, Any]] = {}
    for it in items:
        seen.setdefault(it["name"], it)
    return list(seen.values())


# ----------------------------------------------------------------------------- SQL
def _split_top(s: str) -> list[str]:
    out, depth, cur = [], 0, ""
    for ch in s:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == "," and depth == 0:
            out.append(cur.strip())
            cur = ""
        else:
            cur += ch
    if cur.strip():
        out.append(cur.strip())
    return out


def _idents(s: str) -> list[str]:
    return [x.strip().strip('`"[]') for x in s.split(",") if x.strip()]


def analyze_sql(text: str) -> Skeleton:
    sk = _new("sql")
    text = re.sub(r"--[^\n]*", "", text)
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    tables: dict[str, dict[str, Any]] = {}
    for m in re.finditer(r"create\s+table\s+(?:if\s+not\s+exists\s+)?([`\"\[\]\w.]+)\s*\((.*?)\)\s*(?:engine[^;]*)?;", text, re.I | re.S):
        tname = m.group(1).strip('`"[]').split(".")[-1].strip('`"[]')
        t = {"cols": {}, "pk": [], "fks": [], "unique": []}
        for part in _split_top(m.group(2)):
            low = part.lower()
            mpk = re.match(r"(?:constraint\s+\S+\s+)?primary\s+key\s*\((.*?)\)", low, re.S)
            mfk = re.match(r"(?:constraint\s+\S+\s+)?foreign\s+key\s*\((.*?)\)\s*references\s+([`\"\[\]\w.]+)\s*(?:\((.*?)\))?", part, re.I | re.S)
            muq = re.match(r"(?:constraint\s+\S+\s+)?unique\s*\((.*?)\)", low, re.S)
            if mpk:
                t["pk"] += _idents(mpk.group(1))
            elif mfk:
                t["fks"].append((_idents(mfk.group(1)), mfk.group(2).strip('`"[]').split(".")[-1], _idents(mfk.group(3) or "")))
            elif muq:
                t["unique"].append(_idents(muq.group(1)))
            elif re.match(r"(constraint|index|key|check)\b", low):
                continue
            else:
                mc = re.match(r"[`\"\[]?(\w+)[`\"\]]?\s+([A-Za-z_]+(?:\s*\([^)]*\))?)(.*)", part, re.S)
                if not mc:
                    continue
                cname, ctype, rest = mc.group(1), mc.group(2), mc.group(3).lower()
                t["cols"][cname] = {"type": ctype, "notnull": "not null" in rest or "primary key" in rest}
                if "primary key" in rest:
                    t["pk"].append(cname)
                if re.search(r"\bunique\b", rest):
                    t["unique"].append([cname])
                mr = re.search(r"references\s+([`\"\[\]\w.]+)", rest)
                if mr:
                    t["fks"].append(([cname], mr.group(1).strip('`"[]').split(".")[-1], []))
        tables[tname] = t
    # ALTER TABLE ... ADD FOREIGN KEY
    for m in re.finditer(r"alter\s+table\s+([`\"\w.]+)\s+add\s+(?:constraint\s+\S+\s+)?foreign\s+key\s*\((.*?)\)\s*references\s+([`\"\w.]+)", text, re.I | re.S):
        tn = m.group(1).strip('`"').split(".")[-1]
        if tn in tables:
            tables[tn]["fks"].append((_idents(m.group(2)), m.group(3).strip('`"').split(".")[-1], []))
    if not tables:
        sk["warnings"].append("Aucune instruction CREATE TABLE reconnue.")
        return sk
    cls = {tn: pascal(singular(tn)) for tn in tables}
    for tn, t in tables.items():
        c = cls[tn]
        fkcols = {col for cols, _, _ in t["fks"] for col in cols}
        key = [camel(x) for x in t["pk"] if x not in fkcols]
        cd = {"name": c, "label_en": humanize(c), "comment": f"Issu de la table SQL « {tn} »."}
        if key:
            cd["key"] = key
        elif t["pk"]:
            sk["warnings"].append(f"Table « {tn} » : clé primaire composée uniquement de clés étrangères ; table de jointure ? "
                                  "Une relation N-N directe ou une classe d'association est à arbitrer.")
        else:
            sk["warnings"].append(f"Table « {tn} » : pas de clé primaire ; identifiant à choisir.")
        sk["classes"].append(cd)
        for col, info in t["cols"].items():
            if col in fkcols:
                continue
            sk["datatype_properties"].append({"name": camel(col), "label_en": humanize(col), "domain": c, "range": sql_type(info["type"]),
                                              "functional": True, "required": info["notnull"]})
        for cols, target, _ in t["fks"]:
            tc = cls.get(target, pascal(singular(target)))
            if target not in tables:
                sk["warnings"].append(f"Table « {target} » référencée mais absente du script : classe {tc} créée vide.")
                sk["classes"].append({"name": tc, "label_en": humanize(tc)})
            col = cols[0]
            stem = re.sub(r"(?i)[_ ]?id$", "", col) if re.search(r"(?i)[_ ]?id$", col) else ""
            pname = "has" + pascal(stem) if stem else "has" + tc
            if any(o["name"] == pname and o["domain"] == c for o in sk["object_properties"]):
                pname += "Ref"
            nullable = not t["cols"].get(col, {}).get("notnull", False)
            sk["object_properties"].append({"name": pname, "label_en": "has " + humanize(stem or tc), "domain": c, "range": tc,
                                            "functional": True, "required": not nullable})
    sk["classes"] = _dedupe(sk["classes"])
    return sk
