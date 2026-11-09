"""Versions des normes et des cibles (L31).

``standards.json`` est la référence : maintenue par la veille (``docs/veille/``), livrée avec l'application, lue sans réseau.
Ce module en tire :
- les versions effectives d'un projet (valeurs d'usine < défaut global des paramètres < valeurs propres au projet) ;
- le statut de chaque version (recommandée, supportée, obsolète, fin de support, inconnue) ;
- le contrôle local des écarts (``check``) et la mise à jour vers les versions recommandées (``recommended_patch``) ;
- les capacités de syntaxe Neo4j selon la version (``neo4j_caps``) et le préfixe ``CYPHER n`` (``cypher_prefix``).
Aucune fonction n'appelle le réseau. Un écart qu'on ne peut pas vérifier est marqué « À VÉRIFIER », jamais inventé.
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel

KEYS = ("neo4j", "cypher", "curiosity_library", "shacl", "sparql", "rdf")
SUPPORTS = ("recommended", "supported", "obsolete", "end_of_support")
_FILE = Path(__file__).with_name("standards.json")
_FORMAT = {  # forme acceptée par l'API (les valeurs inconnues mais bien formées sont admises, puis signalées par le contrôle)
    "neo4j": re.compile(r"^\d{1,4}\.\d{1,3}$"),
    "cypher": re.compile(r"^(5|25)$"),
    "curiosity_library": re.compile(r"^\d{1,3}\.\d{1,3}\.\d{1,6}$"),
    "shacl": re.compile(r"^1\.[0-2]$"),
    "sparql": re.compile(r"^1\.[12]$"),
    "rdf": re.compile(r"^1\.[12]$"),
}
_TXT = {  # messages du contrôle, par langue
    "fr": {
        "obsolete": "La cible {fam} {v} n'est plus recommandée : version obsolète.",
        "end_of_support": "La cible {fam} {v} est en fin de support.",
        "unknown": "{fam} {v} ne figure pas dans la référence des versions (À VÉRIFIER).",
        "newer": "{fam} {r} est disponible et recommandée ; le projet cible {v}.",
        "incompatible": "Cypher {c} n'existe pas sur Neo4j {n} : le préfixe CYPHER {c} serait refusé.",
        "wd": "{fam} {v} est un brouillon ou une candidate : à utiliser en connaissance de cause (À VÉRIFIER).",
        "rec_to": "Passer à {fam} {r}.",
        "rec_cypher": "Revenir à Cypher {r} (ou cibler Neo4j 2026.10).",
        "src_project": "projet", "src_default": "défaut",
        "st": {"recommended": "recommandée", "supported": "supportée", "obsolete": "obsolète", "end_of_support": "fin de support", "unknown": "inconnue"},
        "fam": {"neo4j": "Neo4j", "cypher": "Cypher", "curiosity_library": "Curiosity.Library", "shacl": "SHACL", "sparql": "SPARQL", "rdf": "RDF"},
    },
    "en": {
        "obsolete": "The {fam} {v} target is no longer recommended: obsolete version.",
        "end_of_support": "The {fam} {v} target is out of support.",
        "unknown": "{fam} {v} is not in the version reference (TO VERIFY).",
        "newer": "{fam} {r} is available and recommended; the project targets {v}.",
        "incompatible": "Cypher {c} does not exist on Neo4j {n}: the CYPHER {c} prefix would be refused.",
        "wd": "{fam} {v} is a draft or candidate: use it knowingly (TO VERIFY).",
        "rec_to": "Move to {fam} {r}.",
        "rec_cypher": "Go back to Cypher {r} (or target Neo4j 2026.10).",
        "src_project": "project", "src_default": "default",
        "st": {"recommended": "recommended", "supported": "supported", "obsolete": "obsolete", "end_of_support": "end of support", "unknown": "unknown"},
        "fam": {"neo4j": "Neo4j", "cypher": "Cypher", "curiosity_library": "Curiosity.Library", "shacl": "SHACL", "sparql": "SPARQL", "rdf": "RDF"},
    },
}


class TargetVersions(BaseModel):
    """Défaut global (``settings.versions``) : une valeur par famille, d'usine = ``standards.json › defaults``."""
    neo4j: str = ""
    cypher: str = ""
    curiosity_library: str = ""
    shacl: str = ""
    sparql: str = ""
    rdf: str = ""

    def model_post_init(self, _ctx: Any) -> None:
        d = defaults()
        for k in KEYS:
            if not getattr(self, k):
                setattr(self, k, d[k])
            else:
                setattr(self, k, normalize(k, getattr(self, k)))


@lru_cache(maxsize=1)
def _load() -> dict[str, Any]:
    return json.loads(_FILE.read_text(encoding="utf-8"))


def defaults() -> dict[str, str]:
    return dict(_load()["defaults"])


def updated() -> str:
    return str(_load().get("updated", ""))


def _lang(lang: Optional[str]) -> str:
    if lang in ("fr", "en"):
        return lang  # type: ignore[return-value]
    try:
        from ..localize import ui_lang
        return "en" if ui_lang() == "en" else "fr"
    except Exception:  # noqa: BLE001
        return "fr"


def _family(key: str) -> dict[str, Any]:
    d = _load()
    return {"neo4j": d["neo4j"], "cypher": d["neo4j"]["cypher"], "curiosity_library": d["curiosity"],
            "shacl": d["w3c"]["shacl"], "sparql": d["w3c"]["sparql"], "rdf": d["w3c"]["rdf"]}[key]


def _vkey(s: str) -> tuple[int, ...]:
    return tuple(int(x) for x in re.findall(r"\d+", s))


def normalize(key: str, value: Any) -> str:
    v = str(value).strip()
    return str(_family(key).get("aliases", {}).get(v, v))


def check_format(key: str, value: Any) -> Optional[str]:
    """Message d'erreur (français) si la valeur n'a pas la forme attendue pour cette famille, sinon ``None``."""
    if key not in KEYS:
        return f"Famille inconnue « {key} » : attendu {', '.join(KEYS)}"
    v = normalize(key, value)
    if not isinstance(value, str) or not _FORMAT[key].match(v):
        known = ", ".join(e["id"] for e in _family(key)["versions"])
        return f"Version « {value} » invalide pour {key} (exemples : {known})"
    return None


def entry(key: str, value: str) -> Optional[dict[str, Any]]:
    """Entrée de référence d'une version (exacte, ou déduite d'une règle pour Neo4j) ; ``None`` si inconnue."""
    v = normalize(key, value)
    fam = _family(key)
    for e in fam["versions"]:
        if e["id"] == v:
            return e
    if key == "neo4j":
        for r in fam.get("rules", []):
            m = re.match(r["match"], v)
            if m and ("below" not in r or int(m.group(1)) < r["below"]):
                return {**{k: x for k, x in r.items() if k not in ("match", "below")}, "id": v, "label": f"Neo4j {v}"}
    return None


def status(key: str, value: str) -> str:
    e = entry(key, value)
    return e["support"] if e else "unknown"


def recommended(key: str, versions: Optional[dict[str, str]] = None) -> str:
    """Version recommandée de la famille ; pour Cypher, elle dépend de la cible Neo4j (25 là où il existe)."""
    if key == "cypher" and versions:
        e = entry("neo4j", versions.get("neo4j", ""))
        if e and "25" in (e.get("cypher") or []) and e["id"] == "2026.10":
            return "25"
    return next((e["id"] for e in _family(key)["versions"] if e.get("support") == "recommended"), defaults()[key])


# ---- effectif d'un projet --------------------------------------------------------------------------

def global_defaults() -> dict[str, str]:
    """Défaut global : réglages de l'utilisateur, à défaut les valeurs d'usine de ``standards.json``."""
    try:
        from ..settings import store
        return store.load(persist=False).versions.model_dump()
    except Exception:  # noqa: BLE001 — paramètres illisibles : valeurs d'usine
        return defaults()


def effective(explicit: Optional[dict[str, str]], base: Optional[dict[str, str]] = None) -> dict[str, str]:
    """Versions utilisées par un projet : ses valeurs propres, complétées par le défaut global (anciens projets : tout le défaut)."""
    out = dict(base if base is not None else global_defaults())
    for k, v in (explicit or {}).items():
        if k in KEYS and v:
            out[k] = normalize(k, v)
    return {k: out.get(k) or defaults()[k] for k in KEYS}


def for_project(project: Any) -> dict[str, str]:
    return effective(getattr(project, "target_versions", None))


# ---- capacités de syntaxe Neo4j ----------------------------------------------------------------------

def _ge(v: str, thr: str) -> bool:
    return _vkey(v)[:2] >= _vkey(thr)[:2]


def neo4j_caps(version: str) -> dict[str, bool]:
    """Ce que la version de Neo4j permet dans les scripts générés (seuils : ``standards.json › neo4j › features``)."""
    f = _load()["neo4j"]["features"]
    v = version if re.match(r"^\d+\.\d+$", version or "") else defaults()["neo4j"]
    major = _vkey(v)[0]
    return {"legacy_assert": major < 5, "rel_unique": _ge(v, f["rel_unique"]), "type_constraint": _ge(v, f["type_constraint"]),
            "type_list": _ge(v, f["type_constraint_list"]), "call_scoped": _ge(v, f["call_in_transactions_scoped"]),
            "cypher25": _ge(v, f["cypher25"]), "calendar": major >= 2025}


def cypher_prefix(neo4j: str, cypher: str) -> str:
    """Préfixe de version de Cypher, à placer devant CHAQUE requête (il ne vaut que pour la requête qui le suit)."""
    caps = neo4j_caps(neo4j)
    if cypher == "25":
        return "CYPHER 25 " if caps["cypher25"] else ""
    if cypher == "5" and caps["calendar"]:
        return "CYPHER 5 "  # sur une base calendaire, la version par défaut peut être 25 : on fixe 5 explicitement
    return ""  # 5.x : le préfixe n'est pas nécessaire (accepté par 5.26 ? À VÉRIFIER, donc omis)


def cypher_compatible(neo4j: str, cypher: str) -> bool:
    e = entry("neo4j", neo4j)
    allowed = (e or {}).get("cypher") or []
    return not allowed or cypher in allowed


def shacl_features(version: str, lang: Optional[str] = None) -> list[dict[str, Any]]:
    """Fonctions SHACL 1.2, marquées « 1.2 ». ``state`` : ``disabled`` (version ciblée 1.0) ou ``unavailable`` (1.2 ciblée mais ni OntoForge
    ni pyshacl ne l'implémentent : À VÉRIFIER). Aucune n'est écrite dans les exports."""
    lg = _lang(lang)
    v = normalize("shacl", version)
    out = []
    for f in _loc(_family("shacl")["features"], lg):
        on = _vkey(v)[:2] >= _vkey(f["since"])[:2]
        out.append({**f, "state": ("enabled" if f["implemented"] else "unavailable") if on else "disabled"})
    return out


def shacl_header(version: str) -> str:
    """Commentaire Turtle placé en tête de l'export des shapes (français, comme les autres fichiers générés).
    Vide pour SHACL 1.0 (la Recommandation) : l'export reste alors identique octet pour octet ; l'en-tête marque une cible différente."""
    v = normalize("shacl", version)
    if v == "1.0":
        return ""
    feats = ", ".join(f["id"] for f in shacl_features(v, "fr"))
    lines = [f"# Shapes SHACL — version ciblée : SHACL {v} (statut : {status_label('shacl', v, 'fr')} ; référence du {updated()}).",
             f"# SHACL {v} est un brouillon : ses fonctions ({feats}) ne sont pas implémentées par OntoForge ni par pyshacl, "
             "aucune n'est écrite. À VÉRIFIER."]
    return "\n".join(lines) + "\n"


def status_label(key: str, value: str, lang: Optional[str] = None) -> str:
    return _TXT[_lang(lang)]["st"][status(key, value)]


def line(versions: dict[str, str], keys: tuple[str, ...]) -> str:
    names = {"neo4j": "Neo4j", "cypher": "Cypher", "curiosity_library": "Curiosity.Library", "shacl": "SHACL", "sparql": "SPARQL", "rdf": "RDF"}
    return " · ".join(f"{names[k]} {versions[k]}" for k in keys if versions.get(k))


# ---- localisation de la référence ---------------------------------------------------------------------

def _loc(obj: Any, lang: str) -> Any:
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if k.endswith("_en"):
                continue
            en = obj.get(k + "_en")
            out[k] = _loc(en if lang == "en" and en else v, lang)
        return out
    if isinstance(obj, list):
        return [_loc(x, lang) for x in obj]
    return obj


def reference(lang: Optional[str] = None) -> dict[str, Any]:
    """La référence complète (``GET /api/standards``), textes dans la langue de l'interface."""
    lg = _lang(lang)
    ref = _loc(_load(), lg)
    ref["lang"] = lg
    ref["legend"] = _TXT[lg]["st"]
    return ref


# ---- vue d'un projet et contrôle ------------------------------------------------------------------------

def _choices(key: str, current: str, lg: str) -> list[dict[str, Any]]:
    out = [{"id": e["id"], "label": e.get("label") or e["id"], "support": e.get("support", "supported"), "maturity": e.get("maturity"), "note": e.get("note", "")}
           for e in _loc(_family(key)["versions"], lg)]
    if current and all(c["id"] != current for c in out):
        e = entry(key, current)
        le = _loc(e, lg) if e else {}
        out.append({"id": current, "label": le.get("label") or current, "support": (e or {}).get("support", "unknown"), "maturity": None,
                    "note": le.get("note", "")})
    return out


def describe(explicit: Optional[dict[str, str]] = None, lang: Optional[str] = None, base: Optional[dict[str, str]] = None) -> list[dict[str, Any]]:
    """Une ligne par famille : valeur effective, origine (projet / défaut), statut, remarque et choix du sélecteur."""
    lg = _lang(lang)
    eff = effective(explicit, base)
    t = _TXT[lg]
    rows = []
    for k in KEYS:
        v = eff[k]
        e = entry(k, v)
        le = _loc(e, lg) if e else {}
        sup = e["support"] if e else "unknown"
        rows.append({"key": k, "family": t["fam"][k], "value": v, "pinned": k in (explicit or {}),
                     "source": "project" if k in (explicit or {}) else "default", "support": sup, "status": t["st"][sup],
                     "maturity": (e or {}).get("maturity"), "note": le.get("note", ""), "choices": _choices(k, v, lg)})
    return rows


def check(explicit: Optional[dict[str, str]] = None, lang: Optional[str] = None, base: Optional[dict[str, str]] = None) -> dict[str, Any]:
    """Écarts entre les versions d'un projet et la référence. Purement local. ``needs_attention`` : au moins un écart de sévérité
    ``warning`` ou ``error`` (obsolète, fin de support, incohérence) ; les ``info`` (plus récente, inconnue) n'interrompent personne."""
    lg = _lang(lang)
    t = _TXT[lg]
    eff = effective(explicit, base)
    gaps: list[dict[str, Any]] = []
    patch: dict[str, str] = {}

    def add(key: str, kind: str, severity: str, msg: str, rec: Optional[str], rec_msg: str = "") -> None:
        gaps.append({"key": key, "family": t["fam"][key], "value": eff[key], "kind": kind, "severity": severity, "message": msg,
                     "recommendation": ({"key": key, "value": rec, "message": rec_msg or t["rec_to"].format(fam=t["fam"][key], r=rec)} if rec else None)})
        if rec and severity in ("warning", "error", "info") and kind in ("obsolete", "end_of_support", "incompatible", "newer"):
            patch[key] = rec

    # Neo4j d'abord : la recommandation de Cypher en dépend
    for k in ("neo4j", "cypher", "curiosity_library", "shacl", "sparql", "rdf"):
        v = eff[k]
        e = entry(k, v)
        fam = t["fam"][k]
        rec = recommended(k, {**eff, **patch})
        if e is None:
            add(k, "unknown", "info", t["unknown"].format(fam=fam, v=v), None)
            continue
        if e["support"] in ("obsolete", "end_of_support"):
            add(k, e["support"], "warning", t[e["support"]].format(fam=fam, v=v), rec if rec != v else None)
        elif e["support"] == "supported":
            if e.get("maturity") in ("WD", "CR"):
                add(k, "draft", "info", t["wd"].format(fam=fam, v=v), None)
            elif rec != v and _vkey(rec) > _vkey(v) and k == "curiosity_library":
                add(k, "newer", "info", t["newer"].format(fam=fam, r=rec, v=v), rec)
    eff2 = {**eff, **patch}
    if not cypher_compatible(eff2["neo4j"], eff2["cypher"]):
        # incohérence : on corrige Cypher (la cible Neo4j est le choix structurant)
        rec = recommended("cypher", {**eff2})
        if not cypher_compatible(eff2["neo4j"], rec):
            rec = "5"
        gaps.append({"key": "cypher", "family": t["fam"]["cypher"], "value": eff["cypher"], "kind": "incompatible", "severity": "error",
                     "message": t["incompatible"].format(c=eff2["cypher"], n=eff2["neo4j"]),
                     "recommendation": {"key": "cypher", "value": rec, "message": t["rec_cypher"].format(r=rec)}})
        patch["cypher"] = rec
    elif "neo4j" in patch and not cypher_compatible(patch["neo4j"], eff["cypher"]):
        patch["cypher"] = "5"
    attention = any(g["severity"] in ("warning", "error") for g in gaps)
    patch = {k: v for k, v in patch.items() if v != eff[k]}
    return {"updated": updated(), "versions": eff, "explicit": dict(explicit or {}), "gaps": gaps, "ok": not gaps,
            "needs_attention": attention, "recommended": patch, "lang": lg}
