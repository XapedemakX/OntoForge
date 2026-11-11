"""Opérations d'édition unitaires sur l'OntoModel (éditeur graphique, L9).

Chaque geste de l'éditeur = une opération ``{"op": ..., ...}``. ``apply_ops`` applique une liste d'opérations
**atomiquement** sur une copie de travail du projet : au moindre échec rien n'est modifié. Les erreurs sont
rapportées par index d'opération ; les avertissements (non bloquants) sont rassemblés à part.
"""
from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from ..core.onto_model import (
    OWL, RDF, RDFS, XSD, DatatypeProperty, LiteralValue, ObjectProperty, OntClass, OntoModel, Restriction, ClassExpr,
)
from ..core.project import Perimeter, Position, Project, ProjectView
from ..core.shapes_model import ShapesModel
from . import cycles, icons as icon_catalog

MAX_OPS = 500
IRI_RE = re.compile(r"^[A-Za-z][A-Za-z0-9+.\-]*:[^\s<>\"{}|\\^`]+$")
LANG_RE = re.compile(r"^([A-Za-z]{1,8}(-[A-Za-z0-9]{1,8})*)?$")

CHARACTERISTICS = ("functional", "inverseFunctional", "transitive", "symmetric", "asymmetric", "reflexive", "irreflexive")
SIMPLE_ONLY_CHARS = ("functional", "inverseFunctional", "asymmetric", "irreflexive")
RESTRICTION_KINDS = ("some", "only", "min", "max", "exactly", "value", "self")

# Carte de datatypes OWL 2 (OWL 2 Syntax §4.1) ; les autres xsd:* connus sont acceptés avec avertissement.
OWL2_DATATYPES = {
    OWL + "real", OWL + "rational", RDF + "PlainLiteral", RDF + "XMLLiteral", RDFS + "Literal",
    *(XSD + n for n in (
        "decimal", "integer", "nonNegativeInteger", "nonPositiveInteger", "positiveInteger", "negativeInteger",
        "long", "int", "short", "byte", "unsignedLong", "unsignedInt", "unsignedShort", "unsignedByte",
        "double", "float", "string", "normalizedString", "token", "language", "Name", "NCName", "NMTOKEN",
        "boolean", "hexBinary", "base64Binary", "anyURI", "dateTime", "dateTimeStamp")),
}
OUTSIDE_MAP_XSD = {XSD + n for n in ("date", "time", "gYear", "gYearMonth", "gMonth", "gMonthDay", "gDay", "duration",
                                     "dayTimeDuration", "yearMonthDuration")}
LANGSTRING = RDF + "langString"

COLLECTIONS = ("classes", "object_properties", "datatype_properties", "annotation_properties", "datatypes", "individuals")


class OpError(Exception):
    pass


@dataclass
class Work:
    """Copie de travail d'un projet : tout est appliqué ici puis validé avant d'être reporté."""
    onto: OntoModel
    view: ProjectView
    perimeters: list[Perimeter]
    shapes: ShapesModel
    decisions: dict[str, dict[str, str]]
    warnings: list[str] = field(default_factory=list)

    def warn(self, msg: str) -> None:
        if msg not in self.warnings:
            self.warnings.append(msg)


@dataclass
class OpsResult:
    applied: int
    errors: list[dict]
    warnings: list[str]
    changed_keys: list[str]
    before: dict[str, Any]  # valeurs d'origine (JSON) des champs modifiés, pour annuler


# ---- validation de base --------------------------------------------------------------------------------------

def _need(op: dict, key: str) -> Any:
    if key not in op or op[key] is None or op[key] == "":
        raise OpError(f"Champ « {key} » obligatoire")
    return op[key]


def _iri(v: Any, what: str = "IRI") -> str:
    if not isinstance(v, str) or not IRI_RE.match(v):
        raise OpError(f"{what} invalide : {v!r} (IRI absolue attendue, ex. https://exemple.org/onto#Nom)")
    return v


def _iri_list(v: Any, what: str) -> list[str]:
    if v is None:
        return []
    if isinstance(v, str):
        v = [v]
    if not isinstance(v, list):
        raise OpError(f"« {what} » doit être une IRI ou une liste d'IRIs")
    out: list[str] = []
    for x in v:
        x = _iri(x, what)
        if x not in out:
            out.append(x)
    return out


def _lang(op: dict) -> str:
    lang = op.get("lang", "fr")
    if not isinstance(lang, str) or not LANG_RE.match(lang):
        raise OpError(f"Code de langue invalide : {lang!r}")
    return lang


def _num(v: Any, name: str) -> float:
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
        raise OpError(f"« {name} » doit être un nombre fini")
    return float(v)


def kind_of(onto: OntoModel, iri: str) -> Optional[str]:
    for c in COLLECTIONS:
        if iri in getattr(onto, c):
            return c
    return None


def entity(onto: OntoModel, iri: str):
    k = kind_of(onto, iri)
    return getattr(onto, k)[iri] if k else None


def _exists_any(onto: OntoModel, iri: str) -> bool:
    return kind_of(onto, iri) is not None


RESERVED_NS = (RDF, RDFS, OWL, XSD)


def _not_reserved(iri: str) -> str:
    if iri.startswith(RESERVED_NS):
        raise OpError(f"{iri} appartient au vocabulaire réservé (rdf:, rdfs:, owl:, xsd:) : OWL 2 interdit de le redéfinir (Syntax §2.4, §5.8.1)")
    return iri


def _new_iri(w: Work, op: dict) -> str:
    """IRI de la nouvelle entité : ``iri`` explicite, ou ``name`` ajouté à l'IRI de l'ontologie."""
    if op.get("iri"):
        iri = _iri(op["iri"])
    elif op.get("name"):
        name = str(op["name"]).strip()
        if not re.match(r"^[A-Za-z_][\w.\-]*$", name):
            raise OpError(f"Nom local invalide : {name!r} (lettres, chiffres, _ . - ; commence par une lettre)")
        base = w.onto.meta.iri
        iri = base + name if base.endswith(("#", "/")) else base + "#" + name
    else:
        raise OpError("Champ « iri » (ou « name ») obligatoire")
    _not_reserved(iri)
    if _exists_any(w.onto, iri):
        raise OpError(f"L'IRI {iri} existe déjà ({kind_of(w.onto, iri)}) ; OWL 2 DL interdit de réutiliser une IRI pour deux sortes d'entités")
    return iri


def _class_ref(w: Work, iri: str, what: str) -> str:
    _iri(iri, what)
    if iri != OWL + "Thing" and iri not in w.onto.classes:
        raise OpError(f"Classe inconnue pour « {what} » : {iri}")
    return iri


_INT_RANGES = {"byte": (-2**7, 2**7 - 1), "short": (-2**15, 2**15 - 1), "int": (-2**31, 2**31 - 1), "long": (-2**63, 2**63 - 1),
               "unsignedByte": (0, 255), "unsignedShort": (0, 65535), "unsignedInt": (0, 2**32 - 1),
               "unsignedLong": (0, 2**64 - 1), "nonNegativeInteger": (0, None), "positiveInteger": (1, None),
               "nonPositiveInteger": (None, 0), "negativeInteger": (None, -1), "integer": (None, None)}


def check_literal(value: str, datatype: Optional[str], lang: Optional[str]) -> None:
    """Forme lexicale d'un littéral pour les datatypes de la carte OWL 2 (Direct Semantics §2.3) ; lève OpError."""
    import datetime as _dt
    if lang and datatype and datatype not in (RDF + "langString", RDF + "PlainLiteral"):
        raise OpError(f"Un littéral avec langue (@{lang}) ne peut pas avoir le datatype {datatype} (rdf:langString attendu)")
    if not datatype or not datatype.startswith(XSD):
        return
    name = datatype[len(XSD):]
    v = value
    bad = lambda why: OpError(f"« {value} » n'est pas une forme lexicale valide pour xsd:{name} ({why})")
    if name in _INT_RANGES:
        import re as _re
        if not _re.fullmatch(r"[+-]?\d+", v.strip()):
            raise bad("entier attendu")
        n = int(v)
        lo, hi = _INT_RANGES[name]
        if (lo is not None and n < lo) or (hi is not None and n > hi):
            raise bad("hors de l'intervalle du type")
    elif name == "decimal":
        import re as _re
        if not _re.fullmatch(r"[+-]?(\d+(\.\d*)?|\.\d+)", v.strip()):
            raise bad("décimal attendu")
    elif name in ("double", "float"):
        try:
            float(v.strip().replace("INF", "inf").replace("NaN", "nan")) if v.strip() not in ("INF", "-INF", "+INF", "NaN") else None
        except ValueError:
            raise bad("nombre flottant attendu") from None
    elif name == "boolean":
        if v.strip() not in ("true", "false", "1", "0"):
            raise bad("true, false, 1 ou 0 attendus")
    elif name in ("dateTime", "dateTimeStamp"):
        try:
            _dt.datetime.fromisoformat(v.strip().replace("Z", "+00:00"))
        except ValueError:
            raise bad("AAAA-MM-JJThh:mm:ss[Z|±hh:mm] attendu") from None
        if name == "dateTimeStamp" and not re.search(r"(Z|[+-]\d\d:\d\d)$", v.strip()):
            raise bad("fuseau horaire obligatoire")
    elif name == "date":
        try:
            _dt.date.fromisoformat(v.strip()[:10])
        except ValueError:
            raise bad("AAAA-MM-JJ attendu") from None
    elif name == "hexBinary":
        if not re.fullmatch(r"([0-9A-Fa-f]{2})*", v.strip()):
            raise bad("hexadécimal en nombre pair de chiffres attendu")


def _check_datatype(w: Work, iri: str, what: str = "datatype") -> str:
    _iri(iri, what)
    if iri in OWL2_DATATYPES or iri == LANGSTRING or iri in w.onto.datatypes:
        return iri
    if iri in OUTSIDE_MAP_XSD:
        w.warn(f"{iri.replace(XSD, 'xsd:')} n'appartient pas à la carte de datatypes d'OWL 2 : le profil OWL 2 DL n'est pas garanti")
        return iri
    if iri.startswith(XSD):
        raise OpError(f"Datatype XSD inconnu : {iri}")
    raise OpError(f"Datatype inconnu : {iri} (ni dans la carte OWL 2, ni déclaré dans l'ontologie)")


def _view_touch_check(w: Work, iri: str) -> None:
    if not _exists_any(w.onto, iri):
        raise OpError(f"Entité inconnue : {iri}")


# ---- propriétés simples / intégrité ------------------------------------------------------------------------

def non_simple_properties(onto: OntoModel) -> dict[str, str]:
    """Propriétés d'objet non simples (OWL 2 Structural Spec §11.2) → raison."""
    ns: dict[str, str] = {}
    for iri, p in onto.object_properties.items():
        if "transitive" in p.characteristics:
            ns[iri] = "transitive"
        elif p.chains:
            ns[iri] = "cible d'une chaîne de propriétés"
    changed = True
    while changed:
        changed = False
        for iri, p in onto.object_properties.items():
            if iri in ns:
                continue
            reason = None
            # R ⊑ S avec R non simple ⇒ S non simple (on regarde les sous-propriétés de p)
            for q in onto.object_properties.values():
                if q.iri in ns and (iri in q.sub_property_of or iri in q.equivalent_to):
                    reason = f"super-propriété de {q.iri} (non simple)"
                    break
            if reason is None and p.inverse_of and p.inverse_of in ns:
                reason = f"inverse de {p.inverse_of} (non simple)"
            if reason is None:
                for q in onto.object_properties.values():
                    if q.inverse_of == iri and q.iri in ns:
                        reason = f"inverse de {q.iri} (non simple)"
                        break
            if reason is None and any(e in ns for e in p.equivalent_to):
                reason = "équivalente à une propriété non simple"
            if reason:
                ns[iri] = reason
                changed = True
    return ns


def _walk(e: ClassExpr):
    yield e
    for a in ([e.filler] if e.filler else []) + list(e.args):
        yield from _walk(a)


def _all_exprs(onto: OntoModel):
    """(propriétaire, ClassExpr) pour toutes les expressions, y compris imbriquées et celles des restrictions aplaties."""
    for c in onto.classes.values():
        for e in [*c.equivalent_to, *c.super_expressions, *(r.filler_expr for r in c.restrictions if r.filler_expr)]:
            for x in _walk(e):
                yield c.iri, x
    for p in [*onto.object_properties.values(), *onto.datatype_properties.values()]:
        for e in (p.domain_expr, getattr(p, "range_expr", None)):
            if isinstance(e, ClassExpr):
                for x in _walk(e):
                    yield p.iri, x


def equivalence_class(onto: OntoModel, iri: str) -> set[str]:
    """Classes nommées équivalentes à ``iri`` (directes ou par chaîne d'équivalences, dans les deux sens)."""
    edges: dict[str, set[str]] = {}
    for c in onto.classes.values():
        for e in c.equivalent_to:
            if e.op == "named" and e.iri and e.iri != c.iri:
                edges.setdefault(c.iri, set()).add(e.iri)
                edges.setdefault(e.iri, set()).add(c.iri)
    seen, stack = {iri}, [iri]
    while stack:
        for n in edges.get(stack.pop(), ()):
            if n not in seen:
                seen.add(n)
                stack.append(n)
    return seen


def related_by_subclass_or_equiv(onto: OntoModel, a: str, b: str) -> bool:
    """a et b sont-elles confondues ou en relation de sous-classe, en tenant compte des équivalences nommées ?"""
    ea, eb = equivalence_class(onto, a), equivalence_class(onto, b)
    if ea & eb:
        return True
    anc_a = {x for c in ea for x in onto.ancestors(c)}
    anc_b = {x for c in eb for x in onto.ancestors(c)}
    return bool(eb & anc_a) or bool(ea & anc_b) or bool(anc_a & eb) or any(equivalence_class(onto, x) & eb for x in anc_a) \
        or any(equivalence_class(onto, x) & ea for x in anc_b)


def integrity_errors(onto: OntoModel) -> list[str]:
    """Contraintes structurelles OWL 2 vérifiées après chaque lot d'opérations (seules les nouvelles sont bloquantes)."""
    out: list[str] = []
    # cycles de sous-classes (graphe orienté enfant → parent)
    color: dict[str, int] = {}

    def dfs(c: str, path: list[str]) -> None:
        color[c] = 1
        for par in onto.classes[c].sub_class_of:
            if par not in onto.classes:
                continue
            if color.get(par) == 1:
                cyc = path[path.index(par):] + [par] if par in path else [c, par]
                out.append("Cycle de sous-classes : " + " → ".join(cyc))
            elif par not in color:
                dfs(par, path + [par])
        color[c] = 2

    for c in sorted(onto.classes):
        if c not in color:
            dfs(c, [c])
    ns = non_simple_properties(onto)
    for iri, p in onto.object_properties.items():
        chars = set(p.characteristics)
        if "symmetric" in chars and "asymmetric" in chars:
            out.append(f"{iri} ne peut pas être à la fois symétrique et asymétrique")
        if "reflexive" in chars and "irreflexive" in chars:
            out.append(f"{iri} ne peut pas être à la fois réflexive et irréflexive")
        if "reflexive" in chars and "asymmetric" in chars:
            out.append(f"{iri} ne peut pas être à la fois réflexive et asymétrique")
        if iri in ns:
            for c in chars & set(SIMPLE_ONLY_CHARS):
                out.append(f"{iri} est non simple ({ns[iri]}) : la caractéristique « {c} » exige une propriété simple (OWL 2 §11.2)")
            if p.disjoint_with:
                out.append(f"{iri} est non simple ({ns[iri]}) : elle ne peut pas être déclarée disjointe (OWL 2 §11.2)")
        for o in p.disjoint_with:
            if o in ns and iri not in ns:
                out.append(f"{iri} est déclarée disjointe de {o}, non simple ({ns[o]}) : DisjointObjectProperties exige des propriétés simples (OWL 2 §11.2)")
    for owner, e in _all_exprs(onto):
        if e.op in ("min", "max", "exactly", "self") and e.property in ns:
            out.append(f"Restriction « {e.op} » dans {owner} : la propriété {e.property} est non simple ({ns[e.property]}) — "
                       "les cardinalités et owl:hasSelf exigent une propriété simple (OWL 2 §11.2)")
    for cls in onto.classes.values():
        for r in cls.restrictions:
            if r.property in ns and r.kind in ("min", "max", "exactly", "self"):
                out.append(f"Restriction « {r.kind} » sur {cls.iri} : la propriété {r.property} est non simple ({ns[r.property]}) — "
                           "les cardinalités et owl:hasSelf exigent une propriété simple (OWL 2 §11.2)")
        for d in cls.disjoint_with:
            if d == cls.iri or related_by_subclass_or_equiv(onto, cls.iri, d):
                out.append(f"{cls.iri} est déclarée disjointe de {d}, avec lequel elle est en relation de sous-classe : classe insatisfiable")
    return out


# ---- primitives de scrub / renommage ---------------------------------------------------------------------

_REF_KEYS = ("property", "filler", "iri", "data_range", "value")


def _dict_refs(d: dict, iri: str) -> bool:
    return any(isinstance(d.get(k), str) and d[k] == iri for k in _REF_KEYS)


_REMOVE = object()


def _scrub(obj: Any, iri: str) -> Any:
    if isinstance(obj, str):
        return _REMOVE if obj == iri else obj
    if isinstance(obj, list):
        out = []
        for el in obj:
            if isinstance(el, dict):
                if _dict_refs(el, iri):
                    continue
                r = _scrub(el, iri)
                if r is _REMOVE:
                    continue
                out.append(r)
            elif isinstance(el, list):
                if _contains(el, iri):
                    continue  # chaîne / clé composite devenue invalide : on retire tout l'axiome
                out.append(el)
            else:
                r = _scrub(el, iri)
                if r is not _REMOVE:
                    out.append(r)
        return out
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if k == iri:
                continue
            if isinstance(v, str):
                out[k] = None if v == iri and v is not None and k not in ("iri",) else v
            elif isinstance(v, dict):
                out[k] = None if _dict_refs(v, iri) else _scrub(v, iri)
            else:
                out[k] = _scrub(v, iri)
        return out
    return obj


def _contains(obj: Any, iri: str) -> bool:
    return json.dumps(iri) in json.dumps(obj, ensure_ascii=False) if isinstance(obj, (list, dict)) else obj == iri


def _mentions(model: Any, iri: str) -> bool:
    return _contains(model.model_dump(mode="json"), iri)


def _drop_axioms(onto: OntoModel, iri: str) -> list[str]:
    """Retire les axiomes **entiers** qui mentionnent ``iri`` dans une expression (jamais un seul opérande :
    A⊔B ne devient pas B, and(B) et not() n'existent pas). Renvoie la liste des axiomes retirés."""
    gone: list[str] = []
    for c in onto.classes.values():
        for fld in ("equivalent_to", "super_expressions"):
            keep = []
            for e in getattr(c, fld):
                (gone.append(f"{c.iri} — {fld}") if _mentions(e, iri) else keep.append(e))
            setattr(c, fld, keep)
        keep_r = []
        for r in c.restrictions:
            if r.filler_expr is not None and _mentions(r.filler_expr, iri):
                gone.append(f"{c.iri} — restriction sur {r.property}")
            else:
                keep_r.append(r)
        c.restrictions = keep_r
        if c.one_of and iri in c.one_of:
            gone.append(f"{c.iri} — owl:oneOf")
            c.one_of = None
    for p in [*onto.object_properties.values(), *onto.datatype_properties.values()]:
        for fld in ("domain_union", "range_union"):
            if iri in getattr(p, fld, []):
                gone.append(f"{p.iri} — {fld}")
                setattr(p, fld, [])
        for fld in ("domain_expr", "range_expr"):
            v = getattr(p, fld, None)
            if v is not None and _mentions(v, iri):
                gone.append(f"{p.iri} — {fld}")
                setattr(p, fld, None)
    for dt in onto.datatypes.values():
        if dt.definition is not None and _mentions(dt.definition, iri):
            gone.append(f"{dt.iri} — définition")
            dt.definition = None
    return gone


def _replace(obj: Any, old: str, new: str) -> Any:
    if isinstance(obj, str):
        return new if obj == old else obj
    if isinstance(obj, list):
        return [_replace(x, old, new) for x in obj]
    if isinstance(obj, dict):
        return {(new if k == old else k): _replace(v, old, new) for k, v in obj.items()}
    return obj


# ---- gestionnaires ------------------------------------------------------------------------------------------

def _op_add_class(w: Work, op: dict) -> None:
    iri = _new_iri(w, op)
    cls = OntClass(iri=iri)
    if op.get("label"):
        cls.labels[_lang(op)] = str(op["label"])
    if op.get("comment"):
        cls.comments[_lang(op)] = str(op["comment"])
    w.onto.classes[iri] = cls
    if op.get("parent"):
        parent = _class_ref(w, op["parent"], "parent")
        if parent != OWL + "Thing":
            cls.sub_class_of.append(parent)
    _apply_view(w, iri, op)


def _apply_view(w: Work, iri: str, op: dict) -> None:
    if op.get("icon"):
        _op_set_icon(w, {"iri": iri, "icon": op["icon"]})
    if "x" in op or "y" in op:
        _op_move_node(w, {"iri": iri, "x": op.get("x", 0), "y": op.get("y", 0)})


def _op_rename_entity(w: Work, op: dict) -> None:
    old, new = _iri(_need(op, "iri")), _iri(_need(op, "new_iri"), "new_iri")
    if not _exists_any(w.onto, old):
        raise OpError(f"Entité inconnue : {old}")
    if old == new:
        raise OpError("L'ancienne et la nouvelle IRI sont identiques")
    _not_reserved(new)
    if _exists_any(w.onto, new):
        raise OpError(f"L'IRI {new} existe déjà")
    d = w.onto.model_dump(mode="json")
    prefixes = d["meta"].pop("prefixes")
    d = _replace(d, old, new)
    d["meta"]["prefixes"] = prefixes
    w.onto = OntoModel.model_validate(d)
    w.view = ProjectView.model_validate(_replace(w.view.model_dump(mode="json"), old, new))
    w.perimeters = [Perimeter.model_validate(_replace(p.model_dump(mode="json"), old, new)) for p in w.perimeters]
    sd = _replace(w.shapes.model_dump(mode="json", by_alias=True), old, new)
    w.shapes = ShapesModel.model_validate(sd)
    pat = re.compile(r"(?<=:)" + re.escape(old) + r"(?=$|:)")
    w.decisions = {t: {pat.sub(lambda _m: new, k): v for k, v in dec.items()} for t, dec in w.decisions.items()}


def _op_delete_entity(w: Work, op: dict) -> None:
    iri = _iri(_need(op, "iri"))
    k = kind_of(w.onto, iri)
    if not k:
        raise OpError(f"Entité inconnue : {iri}")
    gone = _drop_axioms(w.onto, iri)
    d = w.onto.model_dump(mode="json")
    refs_before = json.dumps(d, ensure_ascii=False).count(json.dumps(iri)) - 1
    for c in COLLECTIONS:
        d[c].pop(iri, None)
    prefixes = d["meta"].pop("prefixes")
    for key in list(d):
        if key in ("meta",) or key in COLLECTIONS:
            continue
        d[key] = _scrub(d[key], iri)
    for c in COLLECTIONS:
        d[c] = {kk: _scrub(vv, iri) if not isinstance(vv, str) else vv for kk, vv in d[c].items()}
    d["meta"]["prefixes"] = prefixes
    w.onto = OntoModel.model_validate(d)
    removed = refs_before - json.dumps(d, ensure_ascii=False).count(json.dumps(iri))
    if gone:
        w.warn(f"{len(gone)} axiome(s) entier(s) retiré(s) car ils mentionnaient {iri} (jamais tronqués) : " + " ; ".join(gone[:10]) + (" …" if len(gone) > 10 else ""))
    if removed > 0:
        w.warn(f"{removed} référence(s) à {iri} retirée(s) des autres entités (axiomes, restrictions, domaines…)")
    w.view.icons.pop(iri, None)
    w.view.positions.pop(iri, None)
    w.view.collapsed = [c for c in w.view.collapsed if c != iri]
    for p in w.perimeters:
        p.classes = [c for c in p.classes if c != iri]
        p.properties = [c for c in p.properties if c != iri]
    if iri in w.shapes.model_dump_json():
        w.warn(f"Des shapes SHACL mentionnent encore {iri} : à revoir dans l'onglet Shapes")


def _op_add_subclass(w: Work, op: dict) -> None:
    child, parent = _iri(_need(op, "iri")), _iri(_need(op, "parent"), "parent")
    if child not in w.onto.classes:
        raise OpError(f"Classe inconnue : {child}")
    if parent == OWL + "Thing":
        raise OpError("Toute classe est déjà une sous-classe de owl:Thing")
    if parent not in w.onto.classes:
        raise OpError(f"Classe parente inconnue : {parent}")
    if child == parent:
        raise OpError(cycles.cycle_message(child, parent, [child]))
    path = cycles.closing_path(w.onto, child, parent)
    if path:
        raise OpError(cycles.cycle_message(child, parent, path))
    c = w.onto.classes[child]
    if parent in c.sub_class_of:
        w.warn(f"{child} est déjà sous-classe de {parent} (aucun changement)")
        return
    c.sub_class_of.append(parent)


def _op_remove_subclass(w: Work, op: dict) -> None:
    child, parent = _iri(_need(op, "iri")), _iri(_need(op, "parent"), "parent")
    c = w.onto.classes.get(child)
    if c is None:
        raise OpError(f"Classe inconnue : {child}")
    if parent not in c.sub_class_of:
        raise OpError(f"{child} n'est pas une sous-classe directe de {parent}")
    c.sub_class_of.remove(parent)


def _classes_list(w: Work, v: Any, what: str) -> list[str]:
    out = _iri_list(v, what)
    for c in out:
        _class_ref(w, c, what)
    return out


def _op_add_object_property(w: Work, op: dict) -> None:
    iri = _new_iri(w, op)
    p = ObjectProperty(iri=iri, domain=_classes_list(w, op.get("domain"), "domain"),
                       range=_classes_list(w, op.get("range"), "range"))
    if op.get("label"):
        p.labels[_lang(op)] = str(op["label"])
    chars = op.get("characteristics") or []
    if not isinstance(chars, list) or any(c not in CHARACTERISTICS for c in chars):
        raise OpError(f"Caractéristiques valides : {', '.join(CHARACTERISTICS)}")
    p.characteristics = list(dict.fromkeys(chars))
    w.onto.object_properties[iri] = p
    if op.get("inverse_of"):
        _op_set_inverse(w, {"iri": iri, "inverse": op["inverse_of"]})


def _op_add_datatype_property(w: Work, op: dict) -> None:
    iri = _new_iri(w, op)
    rng = _iri_list(op.get("range", XSD + "string"), "range")
    for r in rng:
        _check_datatype(w, r, "range")
    p = DatatypeProperty(iri=iri, domain=_classes_list(w, op.get("domain"), "domain"), range=rng,
                         functional=bool(op.get("functional", False)))
    if op.get("label"):
        p.labels[_lang(op)] = str(op["label"])
    w.onto.datatype_properties[iri] = p


def _op_set_domain_range(w: Work, op: dict) -> None:
    iri = _iri(_need(op, "iri"))
    if "domain" not in op and "range" not in op:
        raise OpError("Au moins « domain » ou « range » est attendu (null ou [] pour vider)")
    p = w.onto.object_properties.get(iri) or w.onto.datatype_properties.get(iri)
    if p is None:
        raise OpError(f"Propriété inconnue : {iri} (propriété d'objet ou de données attendue)")
    is_obj = iri in w.onto.object_properties
    if "domain" in op:
        p.domain = _classes_list(w, op["domain"], "domain")
        if p.domain_union or p.domain_expr:
            w.warn(f"Le domaine complexe (union / expression) de {iri} a été remplacé")
            p.domain_union, p.domain_expr = [], None
    if "range" in op:
        rng = _iri_list(op["range"], "range")
        for r in rng:
            _class_ref(w, r, "range") if is_obj else _check_datatype(w, r, "range")
        p.range = rng
        if is_obj and (p.range_union or p.range_expr):
            w.warn(f"La portée complexe de {iri} a été remplacée")
            p.range_union, p.range_expr = [], None
        if not is_obj and p.range_expr:
            w.warn(f"La restriction de datatype de {iri} a été remplacée")
            p.range_expr = None


def _prop_kind(w: Work, iri: str) -> str:
    if iri in w.onto.object_properties:
        return "object"
    if iri in w.onto.datatype_properties:
        return "data"
    raise OpError(f"Propriété inconnue : {iri}")


def _op_set_restriction(w: Work, op: dict) -> None:
    cls_iri = _iri(_need(op, "iri"))
    cls = w.onto.classes.get(cls_iri)
    if cls is None:
        raise OpError(f"Classe inconnue : {cls_iri}")
    prop = _iri(_need(op, "property"), "property")
    pk = _prop_kind(w, prop)
    kind = op.get("kind")
    if kind not in RESTRICTION_KINDS:
        raise OpError(f"« kind » doit valoir : {', '.join(RESTRICTION_KINDS)}")
    inverse = bool(op.get("inverse", False))
    if inverse and pk == "data":
        raise OpError("Une propriété de données n'a pas d'inverse")
    n = op.get("n")
    filler = op.get("filler")
    value = None
    if kind in ("min", "max", "exactly"):
        if isinstance(n, bool) or not isinstance(n, int) or n < 0:
            raise OpError("« n » doit être un entier ≥ 0 pour min / max / exactly")
    else:
        n = None
    if kind == "self":
        if pk != "object":
            raise OpError("owl:hasSelf n'est défini que pour les propriétés d'objet")
        filler = None
    if filler:
        _iri(filler, "filler")
        if pk == "object":
            _class_ref(w, filler, "filler")
        else:
            _check_datatype(w, filler, "filler")
    elif filler == "":
        filler = None
    if kind == "value":
        raw = _need(op, "value")
        if pk == "object":
            value = _iri(raw, "value")
            if value not in w.onto.individuals:
                w.warn(f"L'individu {value} n'est pas déclaré dans l'ontologie")
        else:
            dt = op.get("datatype")
            if dt:
                _check_datatype(w, dt, "datatype")
            check_literal(str(raw), dt, op.get("value_lang"))
            value = LiteralValue(value=str(raw), datatype=dt, lang=op.get("value_lang"))
        filler = None
    elif kind in ("some", "only") and filler is None and pk == "data":
        raise OpError("Une restriction de données some / only exige un datatype (« filler »)")
    cls.restrictions = [r for r in cls.restrictions if not (r.property == prop and r.inverse == inverse and r.kind == kind)]
    cls.restrictions.append(Restriction(property=prop, inverse=inverse, kind=kind, n=n, filler=filler, value=value))


def _op_remove_restriction(w: Work, op: dict) -> None:
    cls = w.onto.classes.get(_iri(_need(op, "iri")))
    if cls is None:
        raise OpError(f"Classe inconnue : {op['iri']}")
    prop = _iri(_need(op, "property"), "property")
    kind = op.get("kind")
    keep = [r for r in cls.restrictions if not (r.property == prop and (kind is None or r.kind == kind))]
    if len(keep) == len(cls.restrictions):
        raise OpError(f"Aucune restriction sur {prop}" + (f" de type {kind}" if kind else "") + f" dans {cls.iri}")
    cls.restrictions = keep


def _op_set_text(field_name: str) -> Callable[[Work, dict], None]:
    def run(w: Work, op: dict) -> None:
        iri = _iri(_need(op, "iri"))
        e = entity(w.onto, iri)
        if e is None:
            raise OpError(f"Entité inconnue : {iri}")
        if "text" not in op or not isinstance(op["text"], str):
            raise OpError("Champ « text » obligatoire (chaîne vide pour supprimer)")
        lang = _lang(op)
        d = getattr(e, field_name)
        if op["text"].strip():
            d[lang] = op["text"]
        else:
            d.pop(lang, None)
    return run


def _op_set_characteristic(w: Work, op: dict) -> None:
    iri = _iri(_need(op, "iri"))
    ch = op.get("characteristic")
    on = op.get("value", True)
    if not isinstance(on, bool):
        raise OpError("« value » doit être un booléen")
    if iri in w.onto.datatype_properties:
        if ch != "functional":
            raise OpError("Une propriété de données ne peut être que fonctionnelle")
        w.onto.datatype_properties[iri].functional = on
        return
    p = w.onto.object_properties.get(iri)
    if p is None:
        raise OpError(f"Propriété inconnue : {iri}")
    if ch not in CHARACTERISTICS:
        raise OpError(f"« characteristic » doit valoir : {', '.join(CHARACTERISTICS)}")
    if on and ch not in p.characteristics:
        p.characteristics.append(ch)
    elif not on and ch in p.characteristics:
        p.characteristics.remove(ch)


def _op_set_inverse(w: Work, op: dict) -> None:
    iri = _iri(_need(op, "iri"))
    p = w.onto.object_properties.get(iri)
    if p is None:
        raise OpError(f"Propriété d'objet inconnue : {iri}")
    inv = op.get("inverse")
    if not inv:
        p.inverse_of = None
        return
    inv = _iri(inv, "inverse")
    q = w.onto.object_properties.get(inv)
    if q is None:
        raise OpError(f"Propriété d'objet inconnue : {inv}")
    if inv == iri:
        raise OpError("Une propriété égale à son inverse est symétrique : utilisez set_characteristic « symmetric »")
    if q.inverse_of and q.inverse_of != iri:
        raise OpError(f"{inv} a déjà pour inverse {q.inverse_of}")
    p.inverse_of = inv


def _disjoint_target(w: Work, op: dict) -> tuple[Any, Any, str]:
    a, b = _iri(_need(op, "iri")), _iri(_need(op, "other"), "other")
    if a == b:
        raise OpError("Une entité ne peut pas être disjointe d'elle-même")
    ka, kb = kind_of(w.onto, a), kind_of(w.onto, b)
    if ka is None or kb is None:
        raise OpError(f"Entité inconnue : {a if ka is None else b}")
    if ka != kb or ka not in ("classes", "object_properties", "datatype_properties"):
        raise OpError("La disjonction relie deux classes, deux propriétés d'objet ou deux propriétés de données")
    return getattr(w.onto, ka)[a], getattr(w.onto, kb)[b], ka


def _op_add_disjoint(w: Work, op: dict) -> None:
    ea, eb, k = _disjoint_target(w, op)
    if k == "classes" and related_by_subclass_or_equiv(w.onto, ea.iri, eb.iri):
        raise OpError(f"{ea.iri} et {eb.iri} sont équivalentes ou en relation de sous-classe (directe ou par équivalences) : "
                      "les déclarer disjointes rend la classe insatisfiable")
    if eb.iri in ea.disjoint_with or ea.iri in eb.disjoint_with:
        w.warn(f"{ea.iri} et {eb.iri} sont déjà disjointes (aucun changement)")
        return
    ea.disjoint_with.append(eb.iri)


def _op_remove_disjoint(w: Work, op: dict) -> None:
    ea, eb, _ = _disjoint_target(w, op)
    if eb.iri in ea.disjoint_with:
        ea.disjoint_with.remove(eb.iri)
    elif ea.iri in eb.disjoint_with:
        eb.disjoint_with.remove(ea.iri)
    else:
        raise OpError(f"{ea.iri} et {eb.iri} ne sont pas déclarées disjointes")


def _op_set_key(w: Work, op: dict) -> None:
    cls = w.onto.classes.get(_iri(_need(op, "iri")))
    if cls is None:
        raise OpError(f"Classe inconnue : {op['iri']}")
    props = _iri_list(op.get("properties"), "properties")
    for p in props:
        _prop_kind(w, p)
    idx = op.get("index", 0)
    if isinstance(idx, bool) or not isinstance(idx, int) or idx < 0 or idx > len(cls.has_keys):
        raise OpError(f"« index » hors limites (0..{len(cls.has_keys)})")
    if not props:
        if idx >= len(cls.has_keys):
            raise OpError("Aucune clé à supprimer à cet index")
        cls.has_keys.pop(idx)
    elif idx == len(cls.has_keys):
        cls.has_keys.append(props)
    else:
        cls.has_keys[idx] = props


def _op_set_icon(w: Work, op: dict) -> None:
    iri = _iri(_need(op, "iri"))
    _view_touch_check(w, iri)
    icon = op.get("icon")
    if not icon:
        w.view.icons.pop(iri, None)
        return
    if not isinstance(icon, str) or not icon_catalog.ICON_RE.match(icon):
        raise OpError(f"Icône invalide : {icon!r} (format Font Awesome « fa-nom », ex. fa-user)")
    if icon not in icon_catalog.ICON_IDS:
        w.warn(f"L'icône {icon} n'est pas dans le catalogue d'OntoForge (elle sera acceptée si Font Awesome la fournit)")
    w.view.icons[iri] = icon


def _op_move_node(w: Work, op: dict) -> None:
    iri = _iri(_need(op, "iri"))
    _view_touch_check(w, iri)
    w.view.positions[iri] = Position(x=_num(op.get("x"), "x"), y=_num(op.get("y"), "y"))


def _op_set_collapsed(w: Work, op: dict) -> None:
    iri = _iri(_need(op, "iri"))
    _view_touch_check(w, iri)
    on = op.get("collapsed", True)
    if not isinstance(on, bool):
        raise OpError("« collapsed » doit être un booléen")
    if on and iri not in w.view.collapsed:
        w.view.collapsed.append(iri)
    elif not on:
        w.view.collapsed = [c for c in w.view.collapsed if c != iri]


HANDLERS: dict[str, Callable[[Work, dict], None]] = {
    "add_class": _op_add_class,
    "rename_entity": _op_rename_entity,
    "delete_entity": _op_delete_entity,
    "add_subclass": _op_add_subclass,
    "remove_subclass": _op_remove_subclass,
    "add_object_property": _op_add_object_property,
    "set_domain_range": _op_set_domain_range,
    "add_datatype_property": _op_add_datatype_property,
    "set_restriction": _op_set_restriction,
    "remove_restriction": _op_remove_restriction,
    "set_label": _op_set_text("labels"),
    "set_comment": _op_set_text("comments"),
    "set_characteristic": _op_set_characteristic,
    "set_inverse": _op_set_inverse,
    "add_disjoint": _op_add_disjoint,
    "remove_disjoint": _op_remove_disjoint,
    "set_key": _op_set_key,
    "set_icon": _op_set_icon,
    "move_node": _op_move_node,
    "set_collapsed": _op_set_collapsed,
}

TRACKED = ("onto", "view", "perimeters", "shapes", "decisions")


def snapshot(p: Project, keys: tuple[str, ...] = TRACKED) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k in keys:
        v = getattr(p, k)
        if k == "perimeters":
            out[k] = [x.model_dump(mode="json") for x in v]
        elif k == "decisions":
            out[k] = json.loads(json.dumps(v))
        else:
            out[k] = v.model_dump(mode="json", by_alias=True)
    return out


def restore(p: Project, snap: dict[str, Any]) -> None:
    for k, v in snap.items():
        if k == "onto":
            p.onto = OntoModel.model_validate(v)
        elif k == "view":
            p.view = ProjectView.model_validate(v)
        elif k == "perimeters":
            p.perimeters = [Perimeter.model_validate(x) for x in v]
        elif k == "shapes":
            p.shapes = ShapesModel.model_validate(v)
        elif k == "decisions":
            p.decisions = v


def apply_ops(p: Project, ops: list[Any]) -> OpsResult:
    """Applique ``ops`` à ``p`` en mémoire si et seulement si toutes réussissent (sinon ``p`` est intact)."""
    errors: list[dict] = []
    if not isinstance(ops, list) or not ops:
        return OpsResult(0, [{"index": 0, "message": "Liste d'opérations vide ou invalide"}], [], [], {})
    if len(ops) > MAX_OPS:
        return OpsResult(0, [{"index": MAX_OPS, "message": f"Trop d'opérations ({len(ops)} > {MAX_OPS})"}], [], [], {})
    before = snapshot(p)
    w = Work(onto=p.onto.model_copy(deep=True), view=p.view.model_copy(deep=True),
             perimeters=[x.model_copy(deep=True) for x in p.perimeters], shapes=p.shapes.model_copy(deep=True),
             decisions=json.loads(json.dumps(p.decisions)))
    before_integrity = set(integrity_errors(w.onto))
    applied = 0
    for i, op in enumerate(ops):
        try:
            if not isinstance(op, dict) or "op" not in op:
                raise OpError("Une opération est un objet avec un champ « op »")
            h = HANDLERS.get(op["op"])
            if h is None:
                raise OpError(f"Opération inconnue : {op['op']!r} (attendu : {', '.join(HANDLERS)})")
            h(w, op)
            applied += 1
        except OpError as e:
            errors.append({"index": i, "message": str(e)})
        except Exception as e:  # modèle invalide, etc. : jamais de 500 sur une opération mal formée
            errors.append({"index": i, "message": f"Opération « {op.get('op') if isinstance(op, dict) else op} » invalide : {e}"})
    if not errors:
        for msg in integrity_errors(w.onto):
            if msg not in before_integrity:
                errors.append({"index": len(ops) - 1, "message": msg})
    if errors:
        return OpsResult(0, errors, w.warnings, [], {})
    p.onto, p.view, p.perimeters, p.shapes, p.decisions = w.onto, w.view, w.perimeters, w.shapes, w.decisions
    after = snapshot(p)
    keys = [k for k in TRACKED if after[k] != before[k]]
    return OpsResult(applied, [], w.warnings, keys, {k: before[k] for k in keys})
