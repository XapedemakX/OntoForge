"""Versions publiées d'un projet (L49) : diff sémantique entre deux états de l'ontologie, niveau SemVer proposé, note de version.

Fichier annexe ``releases.json`` du dossier du projet (comme ``generations.json``) : une entrée par version enregistrée, avec un
instantané de l'ontologie pour calculer le diff suivant. ``project.json`` n'est modifié que par l'opération d'édition qui pose
``owl:versionInfo``, ``owl:versionIRI``, ``owl:priorVersion`` et ``dcterms:modified`` (journalisée, annulable).

Règles du contrat L49 (D-L49-02) :
- **majeure** : classe, relation (propriété objet), attribut (propriété de données) ou datatype ajouté ou retiré ; tout
  changement d'axiome qui les définit (hiérarchie, domaine, portée, caractéristiques, restrictions, clés, disjonctions,
  équivalences, inverses, chaînes) ; imports ; axiomes conservés hors modèle (``unmapped``) ;
- **mineure** : libellés, définitions et commentaires ; dépréciation (Semantic Versioning 2.0.0 §7) ; individus (données de
  référence) ;
- **correctif** : autres annotations (auteur, source, statut, notes) et en-tête de l'ontologie.
Le niveau proposé est le plus fort des changements ; aucun changement → correctif (republication).
"""
from __future__ import annotations

import datetime as _dt
import json
import threading
from typing import Any, Optional

from .. import fsutil
from ..conformance.practices import (DCT, PRIOR_VERSION, SEMVER_RE, SKOS_DEFINITION, SKOS_PREFLABEL, VERSION_INFO)
from ..core.onto_model import OntoModel, local_name
from . import store

FILE = "releases.json"
UNDONE_FILE = "releases-undone.json"  # versions annulées (journal d'opérations), rétablissables
MAX_RELEASES = 30
MAX_CHANGES = 500
LEVELS = ("patch", "minor", "major")
_lock = threading.RLock()

# Champs structurels (changement = majeur) par collection ; les autres champs sont du texte ou des annotations.
_STRUCT = {
    "classes": ("sub_class_of", "restrictions", "super_expressions", "equivalent_to", "disjoint_with", "disjoint_union_of",
                "has_keys", "one_of"),
    "object_properties": ("domain", "range", "domain_union", "range_union", "domain_expr", "range_expr", "inverse_of",
                          "sub_property_of", "equivalent_to", "disjoint_with", "chains", "characteristics"),
    "datatype_properties": ("domain", "domain_union", "domain_expr", "range", "range_expr", "functional", "sub_property_of",
                            "equivalent_to", "disjoint_with"),
    "datatypes": ("definition",),
    "individuals": ("types", "facts", "same_as", "different_from"),
    "annotation_properties": ("sub_property_of", "domain", "range"),
}
# Niveau d'un ajout ou d'un retrait par collection.
_PRESENCE = {"classes": "major", "object_properties": "major", "datatype_properties": "major", "datatypes": "major",
             "individuals": "minor", "annotation_properties": "patch"}
_TEXT_PROPS = {SKOS_DEFINITION, SKOS_PREFLABEL}
# Posées par l'enregistrement d'une version : jamais comptées comme des changements.
_RELEASE_PROPS = {VERSION_INFO, PRIOR_VERSION, DCT + "modified"}

KIND = {
    "fr": {"classes": "Classe", "object_properties": "Relation", "datatype_properties": "Attribut", "datatypes": "Datatype",
           "individuals": "Individu", "annotation_properties": "Propriété d'annotation", "meta": "En-tête"},
    "en": {"classes": "Class", "object_properties": "Relationship", "datatype_properties": "Attribute", "datatypes": "Datatype",
           "individuals": "Individual", "annotation_properties": "Annotation property", "meta": "Header"},
}
TXT = {
    "fr": {"added": "ajouté(e)", "removed": "retiré(e)", "changed": "modifié(e)", "deprecated": "dépréciée", "undeprecated": "n'est plus dépréciée",
           "labels": "libellés", "text": "définition ou commentaire", "annotations": "annotations", "imports": "imports (owl:imports)",
           "unmapped": "axiomes hors modèle", "all_different": "owl:AllDifferent",
           "major": "majeure", "minor": "mineure", "patch": "correctif",
           "h_major": "Changements majeurs (incompatibles)", "h_minor": "Changements mineurs", "h_patch": "Correctifs",
           "title": "Version {v}", "level": "Niveau : **{lvl}** (proposé : {prop}), depuis {prev}.", "first": "Première version enregistrée.",
           "none": "Aucun changement de l'ontologie depuis la version précédente.", "more": "… et {n} autre(s).",
           "replaced": "remplacée par {r}",
           "downgraded": "> Attention : la version {v} est plus faible que le niveau des changements ({lvl})."},
    "en": {"added": "added", "removed": "removed", "changed": "changed", "deprecated": "deprecated", "undeprecated": "no longer deprecated",
           "labels": "labels", "text": "definition or comment", "annotations": "annotations", "imports": "imports (owl:imports)",
           "unmapped": "axioms outside the model", "all_different": "owl:AllDifferent",
           "major": "major", "minor": "minor", "patch": "patch",
           "h_major": "Major changes (breaking)", "h_minor": "Minor changes", "h_patch": "Patches",
           "title": "Version {v}", "level": "Level: **{lvl}** (proposed: {prop}), since {prev}.", "first": "First recorded version.",
           "none": "No ontology change since the previous version.", "more": "… and {n} more.",
           "replaced": "replaced by {r}",
           "downgraded": "> Warning: version {v} is lower than the level of the changes ({lvl})."},
}


class ReleaseError(ValueError):
    pass


# ---- SemVer -------------------------------------------------------------------------------------------------------------

def parse(v: Optional[str]) -> Optional[tuple[int, int, int]]:
    m = SEMVER_RE.match((v or "").strip())
    return (int(m[1]), int(m[2]), int(m[3])) if m else None


def bump(v: Optional[str], level: str) -> str:
    cur = parse(v)
    if cur is None:
        return "1.0.0"
    a, b, c = cur
    return f"{a + 1}.0.0" if level == "major" else f"{a}.{b + 1}.0" if level == "minor" else f"{a}.{b}.{c + 1}"


# ---- diff ---------------------------------------------------------------------------------------------------------------

def _j(x: Any) -> str:
    return json.dumps(x, sort_keys=True, ensure_ascii=False, default=str)


def _ann(e: dict, text: bool, skip: frozenset = frozenset()) -> list:
    return sorted(_j(a) for a in e.get("annotations", [])
                  if (a["property"] in _TEXT_PROPS) == text and a["property"] not in _RELEASE_PROPS and a["property"] not in skip)


# Annotations posées avec une dépréciation : rattachées à la ligne « dépréciée », pas comptées une seconde fois.
_DEPRECATION_PROPS = frozenset({DCT + "isReplacedBy", "http://www.w3.org/2003/06/sw-vocab-status/ns#term_status"})


def _set_key(field: str, v: Any) -> Any:
    """Listes comparées selon leur sémantique : ensembles, sauf l'ordre intérieur d'une chaîne de propriétés (SS §9.2.4).
    Les axiomes hasKey forment un ensemble d'ensembles de propriétés (SS §9.5)."""
    if not isinstance(v, list):
        return _j(v)
    if field == "has_keys":
        return sorted(_j(sorted(x)) for x in v)
    return sorted(_j(x) for x in v)


def diff(old: OntoModel, new: OntoModel) -> list[dict[str, Any]]:
    """Changements de ``old`` vers ``new`` : ``{level, change, collection, iri, field?, replaced_by?}``, triés."""
    o, n = old.model_dump(mode="json"), new.model_dump(mode="json")
    out: list[dict[str, Any]] = []
    for coll, struct in _STRUCT.items():
        a, b = o.get(coll, {}), n.get(coll, {})
        for iri in sorted(set(a) | set(b)):
            if coll == "annotation_properties" and iri in _RELEASE_PROPS | _DEPRECATION_PROPS:
                continue  # déclarations posées par l'enregistrement d'une version ou par une dépréciation
            if iri not in a:
                out.append({"level": _PRESENCE[coll], "change": "added", "collection": coll, "iri": iri})
                continue
            if iri not in b:
                out.append({"level": _PRESENCE[coll], "change": "removed", "collection": coll, "iri": iri})
                continue
            x, y = a[iri], b[iri]
            for f in struct:
                if _set_key(f, x.get(f)) != _set_key(f, y.get(f)):
                    out.append({"level": "minor" if coll == "individuals" else "patch" if coll == "annotation_properties" else "major",
                                "change": "changed", "collection": coll, "iri": iri, "field": f})
            if x.get("deprecated") != y.get("deprecated"):
                reps = [z["value"] for z in y.get("annotations", []) if z["property"] == DCT + "isReplacedBy"]
                out.append({"level": "minor", "change": "deprecated" if y.get("deprecated") else "undeprecated", "collection": coll,
                            "iri": iri, **({"replaced_by": reps} if reps else {})})
            if _j(x.get("labels")) != _j(y.get("labels")):
                out.append({"level": "minor", "change": "changed", "collection": coll, "iri": iri, "field": "labels"})
            if _j(x.get("comments")) != _j(y.get("comments")) or _ann(x, True) != _ann(y, True):
                out.append({"level": "minor", "change": "changed", "collection": coll, "iri": iri, "field": "text"})
            skip = _DEPRECATION_PROPS if x.get("deprecated") != y.get("deprecated") else frozenset()
            if _ann(x, False, skip) != _ann(y, False, skip):
                out.append({"level": "patch", "change": "changed", "collection": coll, "iri": iri, "field": "annotations"})
    mo, mn = o["meta"], n["meta"]
    if sorted(mo.get("imports", [])) != sorted(mn.get("imports", [])):
        out.append({"level": "major", "change": "changed", "collection": "meta", "iri": mn.get("iri"), "field": "imports"})
    if _j(sorted(_j(u) for u in o.get("unmapped", []))) != _j(sorted(_j(u) for u in n.get("unmapped", []))):
        out.append({"level": "major", "change": "changed", "collection": "meta", "iri": mn.get("iri"), "field": "unmapped"})
    if _j(sorted(map(sorted, o.get("all_different", [])))) != _j(sorted(map(sorted, n.get("all_different", [])))):
        out.append({"level": "minor", "change": "changed", "collection": "meta", "iri": mn.get("iri"), "field": "all_different"})
    if (_ann(mo, False) + _ann(mo, True)) != (_ann(mn, False) + _ann(mn, True)) or _j(mo.get("labels")) != _j(mn.get("labels")) \
            or _j(mo.get("comments")) != _j(mn.get("comments")):
        out.append({"level": "patch", "change": "changed", "collection": "meta", "iri": mn.get("iri"), "field": "annotations"})
    return out


def level_of(changes: list[dict[str, Any]]) -> str:
    return max((c["level"] for c in changes), key=LEVELS.index, default="patch")


def level_rank(version: str, previous: str) -> int:
    """Niveau de l'incrément de ``previous`` à ``version`` : 2 majeur, 1 mineur, 0 correctif."""
    a, b = parse(version), parse(previous)
    if a is None or b is None:
        return 0
    return 2 if a[0] != b[0] else 1 if a[1] != b[1] else 0


# ---- note de version ----------------------------------------------------------------------------------------------------

def _line(c: dict[str, Any], lang: str, onto: OntoModel) -> str:
    t, k = TXT[lang], KIND[lang]
    name = onto.label(c["iri"], lang) if c.get("iri") and c["collection"] != "meta" else ""
    who = f"{k[c['collection']]} {name or local_name(c.get('iri') or '')}".strip() if c["collection"] != "meta" else k["meta"]
    iri = f" (`{c['iri']}`)" if c.get("iri") and c["collection"] != "meta" else ""
    if c["change"] in ("added", "removed"):
        return f"- {who}{iri} : {t[c['change']]}" if lang == "fr" else f"- {who}{iri}: {t[c['change']]}"
    if c["change"] in ("deprecated", "undeprecated"):
        rep = (", " + t["replaced"].format(r=", ".join(f"`{r}`" for r in c["replaced_by"]))) if c.get("replaced_by") else ""
        return (f"- {who}{iri} : {t[c['change']]}{rep}" if lang == "fr" else f"- {who}{iri}: {t[c['change']]}{rep}")
    f = c.get("field", "")
    what = t.get(f, f)
    return f"- {who}{iri} : {what} {t['changed']}" if lang == "fr" else f"- {who}{iri}: {what} {t['changed']}"


def release_note(version: str, changes: list[dict[str, Any]], *, previous: Optional[str], proposed: str, level: str,
                 onto: OntoModel, lang: str = "fr", date: Optional[str] = None) -> str:
    lang = lang if lang in TXT else "fr"
    t = TXT[lang]
    date = date or _dt.date.today().isoformat()
    L = [f"# {t['title'].format(v=version)} ({date})", ""]
    if previous is None:
        L += [t["first"], ""]
    else:
        L += [t["level"].format(lvl=t[level], prop=proposed, prev=previous), ""]
    if previous is not None and not changes:
        L += [t["none"], ""]
    if previous is not None and changes and level_rank(version, previous) < LEVELS.index(level):
        L += [t["downgraded"].format(v=version, lvl=t[level]), ""]
    for lvl in ("major", "minor", "patch"):
        rows = [c for c in changes if c["level"] == lvl]
        if not rows:
            continue
        L += [f"## {t['h_' + lvl]} ({len(rows)})", ""]
        L += [_line(c, lang, onto) for c in rows[:200]]
        if len(rows) > 200:
            L.append(t["more"].format(n=len(rows) - 200))
        L.append("")
    return "\n".join(L).rstrip() + "\n"


# ---- stockage -----------------------------------------------------------------------------------------------------------

def _read(pid: str) -> list[dict[str, Any]]:
    try:
        d = json.loads((store.project_dir(pid) / FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError, store.ProjectNotFound):
        return []
    return [x for x in d if isinstance(x, dict) and parse(x.get("version"))] if isinstance(d, list) else []


def history(pid: str) -> list[dict[str, Any]]:
    """Versions enregistrées, de la plus ancienne à la plus récente, sans les instantanés."""
    return [{k: v for k, v in r.items() if k != "snapshot"} for r in _read(pid)]


def get(pid: str, version: str) -> Optional[dict[str, Any]]:
    return next(({k: v for k, v in r.items() if k != "snapshot"} for r in _read(pid) if r.get("version") == version), None)


def last(pid: str) -> Optional[dict[str, Any]]:
    rs = _read(pid)
    return rs[-1] if rs else None


def version_iri_for(onto_iri: str, version: str) -> str:
    """IRI de version : IRI de l'ontologie sans « # » ni « / » final, suivie de ``/<version>`` (l'espace de noms des termes,
    lui, ne change pas : OWL 2 SS §3.3)."""
    return onto_iri.rstrip("#/") + "/" + version


def preview(pid: str, onto: OntoModel, lang: str = "fr") -> dict[str, Any]:
    """Diff de l'état courant avec la dernière version enregistrée, niveau et numéro proposés, note de version."""
    prev = last(pid)
    current = next((a.value for a in onto.meta.annotations if a.property == VERSION_INFO), None)
    if prev is None:
        changes: list[dict[str, Any]] = []
        level = "patch"
        proposed = current.strip() if parse(current) else "1.0.0"
        previous = None
    else:
        changes = diff(OntoModel.model_validate(prev["snapshot"]), onto)
        level = level_of(changes) if changes else None  # SemVer : pas de nouvelle version sans changement
        previous = prev["version"]
        proposed = bump(previous, level or "patch")
    counts = {lvl: sum(1 for c in changes if c["level"] == lvl) for lvl in ("major", "minor", "patch")}
    return {"previous": previous, "current": current, "proposed": proposed, "level": level, "unchanged": prev is not None and not changes,
            "counts": counts,
            "changes": changes[:MAX_CHANGES], "truncated": len(changes) > MAX_CHANGES,
            "version_iri": version_iri_for(onto.meta.iri, proposed) if onto.meta.iri else None,
            "note": release_note(proposed, changes, previous=previous, proposed=proposed, level=level or "patch", onto=onto, lang=lang)}


def check_version(version: str, previous: Optional[str]) -> str:
    v = (version or "").strip()
    if not SEMVER_RE.match(v):
        raise ReleaseError(f"« {version} » n'est pas une version SemVer (MAJEUR.MINEUR.CORRECTIF, ex. 1.2.0)")
    if previous is not None and parse(v) <= parse(previous):
        raise ReleaseError(f"La version publiée {v} doit être supérieure à la précédente ({previous})")
    return v


def _write(pid: str, name: str, rows: list[dict[str, Any]]) -> None:
    fsutil.atomic_write(store.project_dir(pid) / name, json.dumps(rows, ensure_ascii=False, indent=1))


def _read_undone(pid: str) -> list[dict[str, Any]]:
    try:
        d = json.loads((store.project_dir(pid) / UNDONE_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError, store.ProjectNotFound):
        return []
    return [x for x in d if isinstance(x, dict) and parse(x.get("version"))] if isinstance(d, list) else []


def append(pid: str, record: dict[str, Any], onto: OntoModel) -> None:
    with _lock:
        cur = _read(pid)
        cur.append({**record, "snapshot": onto.model_dump(mode="json")})
        _write(pid, FILE, cur[-MAX_RELEASES:])
        _write(pid, UNDONE_FILE, [])  # une nouvelle version efface ce qui pouvait être rétabli (comme la pile « rétablir »)


def drop_last(pid: str, version: str) -> None:
    """Retire la dernière entrée si c'est ``version`` (échec d'écriture du projet après l'ajout)."""
    with _lock:
        cur = _read(pid)
        if cur and cur[-1].get("version") == version:
            _write(pid, FILE, cur[:-1])


def history_label(version: str) -> str:
    """Libellé de l'entrée du journal d'opérations qui enregistre une version (clé du lien annuler ↔ releases.json)."""
    return f"version {version}"


def on_history(pid: str, label: Optional[str], redo: bool) -> Optional[str]:
    """Annuler l'entrée « version x » du journal retire x de ``releases.json`` (gardée dans ``releases-undone.json``) ;
    la rétablir la remet. Renvoie la version déplacée, ou None. Appelé sous ``history.lock()``."""
    if not label or not label.startswith("version "):
        return None
    v = label[len("version "):]
    with _lock:
        cur, undone = _read(pid), _read_undone(pid)
        if not redo and cur and cur[-1].get("version") == v:
            undone.append(cur.pop())
        elif redo and undone and undone[-1].get("version") == v:
            cur.append(undone.pop())
        else:
            return None
        _write(pid, FILE, cur[-MAX_RELEASES:])
        _write(pid, UNDONE_FILE, undone[-MAX_RELEASES:])
        return v
