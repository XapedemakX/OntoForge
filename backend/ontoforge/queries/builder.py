"""Constructeur de requêtes guidées façon Sparnatural — propriétaire : query (L15).

- `GuidedQuery` : modèle pydantic d'une « phrase » (racine, étapes, filtres, sélection, tri).
- `validate_guided` / `to_sparql` : génération SPARQL 1.1 (IRIs compactées avec les préfixes de l'ontologie).
- `Suggester` : assistance à la construction pilotée par l'ontologie (+ shapes) : propriétés sortantes et entrantes
  valides (domaine / portée, sous-classes, sous-propriétés, unions), propriétés de données filtrables, classes cibles.
- `build_all` : SPARQL + Cypher / Curiosity / GraphQL en réutilisant `translate.translate` (pas de duplication).
- `guided_from_sparql` : retrouve une requête guidée depuis un SPARQL simple (questions de compétence).
"""
from __future__ import annotations

import math
import re
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, field_validator

from ..core.onto_model import OWL, RDF, RDFS, XSD, OntoModel, local_name
from ..core.pg_model import PGModel
from ..core.shapes_model import ShapesModel

SKOS_PREF = "http://www.w3.org/2004/02/skos/core#prefLabel"
RDF_TYPE = RDF + "type"
VAR_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,30}$")
FilterKind = Literal["text_contains", "equals", "regex", "lang", "number_range", "date_range", "in_values"]
MAX_LIMIT = 10000
DEFAULT_PREFIXES = {"rdf": RDF, "rdfs": RDFS, "xsd": XSD, "owl": OWL}


# --------------------------------------------------------------------------------------------- modèle

class Root(BaseModel):
    var: str
    class_iri: Optional[str] = None  # None = n'importe quel sujet


class Step(BaseModel):
    from_var: str
    property_iri: str
    inverse: bool = False  # True : ?to property ?from
    to_var: str
    to_class_iri: Optional[str] = None
    optional: bool = False
    negated: bool = False  # « n'a pas de … » (FILTER NOT EXISTS)


class QFilter(BaseModel):
    var: str
    kind: FilterKind
    property_iri: Optional[str] = None  # propriété de données de `var` visée ; None = `var` est la valeur
    value: Any = None  # texte, motif, minimum, valeur d'égalité
    value2: Any = None  # maximum (number_range / date_range)
    values: list[Any] = Field(default_factory=list)  # in_values
    lang: Optional[str] = None  # kind=lang, ou étiquette de langue d'un littéral `equals`
    datatype: Optional[str] = None
    is_iri: bool = False  # les valeurs sont des IRIs
    case_insensitive: bool = True
    negate: bool = False


class SelectItem(BaseModel):
    var: str
    property_iri: Optional[str] = None
    label: bool = False  # ajoute le libellé (rdfs:label) de `var`


class OrderItem(BaseModel):
    var: str
    property_iri: Optional[str] = None
    desc: bool = False


class GuidedQuery(BaseModel):
    root: Root
    steps: list[Step] = Field(default_factory=list)
    filters: list[QFilter] = Field(default_factory=list)
    select: list[SelectItem] = Field(default_factory=list)  # vide = toutes les variables non niées
    order_by: list[OrderItem] = Field(default_factory=list)
    limit: Optional[int] = 100
    offset: Optional[int] = None
    distinct: bool = True
    subclasses: bool = False  # `a/rdfs:subClassOf*` au lieu de `a` (inférence de sous-classes côté requête)
    label_lang: Optional[str] = None  # langue des libellés demandés (None = toutes)

    @field_validator("limit")
    @classmethod
    def _limit(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and not 1 <= v <= MAX_LIMIT:
            raise ValueError(f"limit doit être compris entre 1 et {MAX_LIMIT}")
        return v


class GuidedError(ValueError):
    """Requête guidée structurellement invalide (variable inconnue, doublon…)."""


def all_vars(q: GuidedQuery) -> list[str]:
    return [q.root.var] + [s.to_var for s in q.steps]


def validate_guided(q: GuidedQuery, onto: Optional[OntoModel] = None) -> list[str]:
    """Lève GuidedError si la structure est invalide ; renvoie des avertissements sémantiques (ontologie)."""
    seen: list[str] = []
    for v in all_vars(q):
        if not VAR_RE.match(v):
            raise GuidedError(f"Nom de variable invalide « {v} » (lettres, chiffres, _ ; 31 caractères maximum).")
        if v in seen:
            raise GuidedError(f"Variable « {v} » déclarée deux fois.")
        seen.append(v)
    known = {q.root.var}
    negated: set[str] = set()
    for i, s in enumerate(q.steps, 1):
        if s.from_var not in known:
            raise GuidedError(f"Étape {i} : la variable de départ « {s.from_var} » n'est pas encore définie.")
        if s.from_var in negated:
            raise GuidedError(f"Étape {i} : « {s.from_var} » est une variable niée, elle ne peut pas servir de départ.")
        known.add(s.to_var)
        if s.negated:
            negated.add(s.to_var)
    for f in q.filters:
        if f.var not in known:
            raise GuidedError(f"Filtre sur une variable inconnue « {f.var} ».")
        if f.var in negated:
            raise GuidedError(f"Filtre sur la variable niée « {f.var} ».")
    for it in [*q.select, *q.order_by]:
        if it.var not in known:
            raise GuidedError(f"Variable inconnue « {it.var} » dans la sélection ou le tri.")
        if it.var in negated:
            raise GuidedError(f"La variable niée « {it.var} » ne peut pas être sélectionnée.")
    warns: list[str] = []
    if onto is not None:
        sg = Suggester(onto)
        cls = {q.root.var: q.root.class_iri}
        for i, s in enumerate(q.steps, 1):
            cls[s.to_var] = s.to_class_iri
            if s.property_iri not in onto.object_properties:
                warns.append(f"Étape {i} : propriété objet inconnue de l'ontologie « {local_name(s.property_iri)} ».")
                continue
            src = cls.get(s.from_var)
            if src and src in onto.classes:
                ok = sg.applies(s.property_iri, src, "in" if s.inverse else "out")
                if ok is False:
                    warns.append(f"Étape {i} : « {local_name(s.property_iri)} » n'est pas définie pour « {local_name(src)} »"
                                 f"{' (sens inverse)' if s.inverse else ''} selon l'ontologie.")
            if s.to_class_iri and s.to_class_iri in onto.classes:
                ends = sg.target_classes(s.property_iri, src, inverse=s.inverse) if src else None
                if ends is not None and ends["restricted"] and s.to_class_iri not in {t["iri"] for t in ends["targets"]}:
                    warns.append(f"Étape {i} : « {local_name(s.to_class_iri)} » n'est pas une cible valide de "
                                 f"« {local_name(s.property_iri)} » (résultat probablement vide).")
        for f in q.filters:
            if f.property_iri and f.property_iri not in onto.datatype_properties and f.property_iri != RDFS + "label":
                warns.append(f"Filtre : propriété de données inconnue « {local_name(f.property_iri)} ».")
    return warns


# ------------------------------------------------------------------------------------ rendu SPARQL

IRIREF = re.compile(r"^[^\x00-\x20<>\"{}|^`\\]*$")
LANGTAG = re.compile(r"^[A-Za-z]{1,8}(-[A-Za-z0-9]{1,8})*$")
PREFIX_NAME = re.compile(r"^([A-Za-z][\w\-]*)?$")
OWL2_DATATYPES = {XSD + n for n in (
    "string", "normalizedString", "token", "language", "Name", "NCName", "NMTOKEN", "boolean", "decimal", "integer", "nonNegativeInteger",
    "nonPositiveInteger", "positiveInteger", "negativeInteger", "long", "int", "short", "byte", "unsignedLong", "unsignedInt",
    "unsignedShort", "unsignedByte", "double", "float", "date", "dateTime", "dateTimeStamp", "time", "gYear", "gYearMonth", "gMonth",
    "gMonthDay", "gDay", "duration", "dayTimeDuration", "yearMonthDuration", "anyURI", "hexBinary", "base64Binary")} | {
    RDF + "langString", RDF + "PlainLiteral", RDF + "XMLLiteral", RDFS + "Literal", OWL + "real", OWL + "rational"}


def valid_iri(i: str) -> bool:
    return isinstance(i, str) and bool(i) and bool(IRIREF.match(i))


class _Terms:
    """Compactage des IRIs en noms préfixés + échappement strict des littéraux (IRIREF, langtag validés)."""

    def __init__(self, prefixes: dict[str, str]):
        self.prefixes = {k: v for k, v in prefixes.items() if v and PREFIX_NAME.match(k) and valid_iri(v)}
        self.used: set[str] = set()

    def iri(self, i: str) -> str:
        if not valid_iri(i):
            raise GuidedError(f"IRI invalide ou dangereuse : {str(i)[:60]!r}.")
        best: Optional[tuple[str, str]] = None
        for p, ns in self.prefixes.items():
            if i.startswith(ns) and re.fullmatch(r"[A-Za-z_][\w\-]*", i[len(ns):] or "") \
                    and (best is None or len(ns) > len(self.prefixes[best[0]])):
                best = (p, i[len(ns):])
        if best is None:
            return f"<{i}>"
        self.used.add(best[0])
        return f"{best[0]}:{best[1]}"

    @staticmethod
    def string(s: str) -> str:
        out = s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\r", "\\r").replace("\t", "\\t")
        out = "".join(c if ord(c) >= 0x20 else f"\\u{ord(c):04x}" for c in out)
        return '"' + out + '"'

    def literal(self, v: Any, lang: Optional[str] = None, datatype: Optional[str] = None) -> str:
        if isinstance(v, bool):
            return "true" if v else "false"
        if isinstance(v, (int, float)) and not datatype:
            if isinstance(v, float) and not math.isfinite(v):
                raise GuidedError("Valeur numérique non finie.")
            return repr(v)
        s = str(v)
        if datatype:
            return f"{self.string(s)}^^{self.iri(datatype)}"
        if lang:
            if not LANGTAG.match(lang):
                raise GuidedError(f"Étiquette de langue invalide « {lang[:20]} ».")
            return f"{self.string(s)}@{lang}"
        return self.string(s)

    def header(self) -> str:
        return "".join(f"PREFIX {p}: <{self.prefixes[p]}>\n" for p in sorted(self.used))


def _num(v: Any) -> str:
    if isinstance(v, bool):
        raise GuidedError("Une valeur numérique est attendue.")
    if isinstance(v, (int, float)):
        if isinstance(v, float) and not math.isfinite(v):
            raise GuidedError("Valeur numérique non finie.")
        return repr(v)
    s = str(v).strip().replace(",", ".")
    try:
        return str(int(s))
    except ValueError:
        try:
            f = float(s)
            if not math.isfinite(f):
                raise ValueError
            return repr(f)
        except ValueError:
            raise GuidedError(f"Valeur numérique invalide « {v} ».") from None


def _safe(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_]", "_", name)[:24] or "p"


class _Names:
    """Attribue des noms de variables SPARQL sans collision avec ceux de l'utilisateur."""

    def __init__(self, taken: list[str]):
        self.taken = set(taken)
        self.props: dict[tuple[str, str], str] = {}

    def prop(self, var: str, prop: str, suffix: Optional[str] = None) -> str:
        key = (var, prop)
        if key not in self.props:
            base = f"{var}_{_safe(suffix or local_name(prop))}"
            cand, i = base, 2
            while cand in self.taken:
                cand, i = f"{base}{i}", i + 1
            self.taken.add(cand)
            self.props[key] = cand
        return self.props[key]


def default_prefixes(onto: Optional[OntoModel], extra: Optional[dict[str, str]] = None) -> dict[str, str]:
    px = dict(DEFAULT_PREFIXES)
    if onto is not None:
        px.update(onto.meta.prefixes)
        px.setdefault("skos", "http://www.w3.org/2004/02/skos/core#")
    px.update(extra or {})
    return px


class _Group:
    """Groupe SPARQL ({ … }) : triplets obligatoires, filtres, puis sous-groupes OPTIONAL imbriqués."""

    def __init__(self) -> None:
        self.req: list[str] = []
        self.flt: list[str] = []
        self.kids: list[str] = []
        self.opt: list["_Group"] = []

    def render(self, ind: str = "  ") -> list[str]:
        out = [ind + x for x in [*self.req, *self.flt]]
        for k in self.kids:
            out.append(ind + k)
        for g in self.opt:
            out.append(ind + "OPTIONAL {")
            out += g.render(ind + "  ")
            out.append(ind + "}")
        return out


def to_sparql(q: GuidedQuery, onto: Optional[OntoModel] = None, prefixes: Optional[dict[str, str]] = None) -> str:
    """SPARQL 1.1 (SELECT) de la requête guidée. Tout ce qui dépend d'une variable optionnelle est émis DANS son OPTIONAL.
    Tous les termes préfixés (rdf, rdfs…) sont déclarés. Lève GuidedError si la structure ou une IRI est invalide."""
    validate_guided(q)
    t = _Terms(default_prefixes(onto, prefixes))
    names = _Names(all_vars(q))
    negated = {s.to_var for s in q.steps if s.negated}
    root = _Group()
    home: dict[str, _Group] = {q.root.var: root}
    rdf_type, sub_of, rdfs_label = t.iri(RDF_TYPE), t.iri(RDFS + "subClassOf"), t.iri(RDFS + "label")

    def typing(var: str, cls: Optional[str]) -> list[str]:
        if not cls:
            return []
        return [f"?{var} {rdf_type}/{sub_of}* {t.iri(cls)} ." if q.subclasses else f"?{var} a {t.iri(cls)} ."]

    root.req += typing(q.root.var, q.root.class_iri)
    for s in q.steps:
        a, b = ("?" + s.to_var, "?" + s.from_var) if s.inverse else ("?" + s.from_var, "?" + s.to_var)
        tr = [f"{a} {t.iri(s.property_iri)} {b} ."] + typing(s.to_var, s.to_class_iri)
        g = home[s.from_var]
        if s.negated:
            g.flt.append("FILTER NOT EXISTS { " + " ".join(tr) + " }")
            home[s.to_var] = g
        elif s.optional:
            sub = _Group()
            sub.req += tr
            g.opt.append(sub)
            home[s.to_var] = sub
        else:
            g.req += tr
            home[s.to_var] = g
    # filtres : triplet de donnée dans le groupe de la variable ; négation = NOT EXISTS (pas de triplet obligatoire)
    pos_props = {(f.var, f.property_iri) for f in q.filters if f.property_iri and not f.negate}
    for i, f in enumerate(q.filters):
        g = home[f.var]
        if f.property_iri and f.negate:
            x = "?" + names.prop(f.var, f.property_iri + f"#neg{i}", local_name(f.property_iri) + "_n")
            inner = _filter(f.model_copy(update={"negate": False}), x, t, onto)
            g.flt.append(f"FILTER NOT EXISTS {{ ?{f.var} {t.iri(f.property_iri)} {x} . {inner} }}")
        elif f.property_iri:
            v = names.prop(f.var, f.property_iri)
            line = f"?{f.var} {t.iri(f.property_iri)} ?{v} ."
            if line not in g.req:
                g.req.append(line)
            g.flt.append(_filter(f, "?" + v, t, onto))
        else:
            g.flt.append(_filter(f, "?" + f.var, t, onto))
    # sélection
    cols: list[str] = []
    label_var: dict[str, str] = {}
    items = q.select or [SelectItem(var=v) for v in all_vars(q) if v not in negated]
    for it in items:
        g = home[it.var]
        if it.property_iri:
            v = names.prop(it.var, it.property_iri)
            if (it.var, it.property_iri) not in pos_props:
                line = f"?{it.var} {t.iri(it.property_iri)} ?{v}"
                if not any(line in o.req for o in g.opt):
                    sub = _Group()
                    sub.req.append(line + " .")
                    g.opt.append(sub)
            cols.append(v)
        else:
            cols.append(it.var)
        if it.label:
            lv = label_var.get(it.var)
            if lv is None:
                lv = label_var[it.var] = names.prop(it.var, "label", "label")
                sub = _Group()
                sub.req.append(f"?{it.var} {rdfs_label} ?{lv} .")
                if q.label_lang:
                    sub.flt.append(f"FILTER(LANG(?{lv}) = \"\" || LANGMATCHES(LANG(?{lv}), {t.string(q.label_lang)}))")
                g.opt.append(sub)
            cols.append(lv)
    cols = list(dict.fromkeys(cols))
    order = []
    for o in q.order_by:
        v = names.prop(o.var, o.property_iri) if o.property_iri else o.var
        if o.property_iri and (o.var, o.property_iri) not in pos_props and v not in cols:
            sub = _Group()
            sub.req.append(f"?{o.var} {t.iri(o.property_iri)} ?{v} .")
            home[o.var].opt.append(sub)
        order.append(f"DESC(?{v})" if o.desc else f"?{v}")
    lines = [f"SELECT {'DISTINCT ' if q.distinct else ''}{' '.join('?' + c for c in cols)}", "WHERE {"]
    lines += root.render()
    lines.append("}")
    if order:
        lines.append("ORDER BY " + " ".join(order))
    if q.limit:
        lines.append(f"LIMIT {q.limit}")
    if q.offset:
        lines.append(f"OFFSET {q.offset}")
    return t.header() + ("\n" if t.used else "") + "\n".join(lines) + "\n"


def _filter(f: QFilter, v: str, t: _Terms, onto: Optional[OntoModel]) -> str:
    def wrap(expr: str) -> str:
        return f"FILTER({'!' if f.negate else ''}({expr}))"

    if f.kind == "text_contains":
        if f.value in (None, ""):
            raise GuidedError("Filtre « contient » : valeur manquante.")
        s = str(f.value)
        return wrap(f"CONTAINS(LCASE(STR({v})), {t.string(s.lower())})" if f.case_insensitive
                    else f"CONTAINS(STR({v}), {t.string(s)})")
    if f.kind == "regex":
        if not f.value:
            raise GuidedError("Filtre « regex » : motif manquant.")
        return wrap(f"REGEX(STR({v}), {t.string(str(f.value))}{', \"i\"' if f.case_insensitive else ''})")
    if f.kind == "lang":
        if not f.lang and not f.value:
            raise GuidedError("Filtre « langue » : code de langue manquant.")
        rng = str(f.lang or f.value)
        if rng != "*" and not LANGTAG.match(rng):
            raise GuidedError(f"Étiquette de langue invalide « {rng[:20]} ».")
        return wrap(f"LANGMATCHES(LANG({v}), {t.string(rng)})")
    if f.kind == "equals":
        if f.value is None:
            raise GuidedError("Filtre « égal à » : valeur manquante.")
        if _textish(f, [f.value], onto):  # "Clio" = "Clio"@fr est faux (RDFterm-equal) : comparer les chaînes
            return wrap(f"STR({v}) = {t.string(str(f.value))}")
        return wrap(f"{v} = {_value(f, f.value, t, onto)}")
    if f.kind == "in_values":
        if not f.values:
            raise GuidedError("Filtre « parmi » : liste de valeurs vide.")
        if _textish(f, f.values, onto):
            return wrap(f"STR({v}) IN ({', '.join(t.string(str(x)) for x in f.values)})")
        return wrap(f"{v} IN ({', '.join(_value(f, x, t, onto) for x in f.values)})")
    if f.kind == "number_range":
        parts = []
        if f.value not in (None, ""):
            parts.append(f"{v} >= {_num(f.value)}")
        if f.value2 not in (None, ""):
            parts.append(f"{v} <= {_num(f.value2)}")
        if not parts:
            raise GuidedError("Filtre « intervalle numérique » : borne manquante.")
        return wrap(" && ".join(parts))
    if f.kind == "date_range":
        parts = []
        dt = f.datatype or _date_datatype(f, onto)
        if dt not in OWL2_DATATYPES and not (onto and dt in onto.datatypes):
            raise GuidedError(f"Datatype inconnu « {dt[:60]} ».")
        for val, op, end in ((f.value, ">=", False), (f.value2, "<=", True)):
            if val not in (None, ""):
                parts.append(f"{v} {op} {t.literal(_date_value(str(val), dt, end), datatype=dt)}")
        if not parts:
            raise GuidedError("Filtre « intervalle de dates » : borne manquante.")
        return wrap(" && ".join(parts))
    raise GuidedError(f"Type de filtre inconnu « {f.kind} ».")


def _textish(f: QFilter, vals: list[Any], onto: Optional[OntoModel]) -> bool:
    """Valeurs de type texte sans langue ni datatype explicites, sur une propriété textuelle ou une valeur brute."""
    if f.is_iri or f.datatype or f.lang or not all(isinstance(x, str) for x in vals):
        return False
    if onto is not None and f.property_iri in onto.datatype_properties:
        r = onto.datatype_properties[f.property_iri].range
        return not r or r[0] in _TEXT
    return f.property_iri is None or f.property_iri == RDFS + "label"


def _date_datatype(f: QFilter, onto: Optional[OntoModel]) -> str:
    """xsd:dateTime par défaut (seul type comparable en SPARQL 1.1 §17.3) ; dateTimeStamp -> dateTime ; date / gYear* / time conservés."""
    if onto is not None and f.property_iri in onto.datatype_properties:
        for r in onto.datatype_properties[f.property_iri].range:
            if r == XSD + "dateTimeStamp":
                return XSD + "dateTime"
            if r in (XSD + "date", XSD + "dateTime", XSD + "gYear", XSD + "gYearMonth", XSD + "time"):
                return r
    return XSD + "dateTime"


def _date_value(s: str, dt: str, end: bool) -> str:
    """Adapte la valeur ISO au type visé (gYear : YYYY, gYearMonth : YYYY-MM, date : AAAA-MM-JJ, dateTime : complétée)."""
    s = s.strip()
    if dt == XSD + "gYear":
        return s[:4]
    if dt == XSD + "gYearMonth":
        return s[:7]
    if dt == XSD + "date":
        return s[:10]
    if dt == XSD + "time":
        return s.split("T", 1)[1] if "T" in s else ("23:59:59" if end else "00:00:00")
    if dt == XSD + "dateTime" and "T" not in s:
        s += "T23:59:59" if end else "T00:00:00"
    return s


def _value(f: QFilter, x: Any, t: _Terms, onto: Optional[OntoModel]) -> str:
    if f.is_iri:
        return t.iri(str(x))
    dt = f.datatype
    if dt is None and onto is not None and f.property_iri in (onto.datatype_properties if onto else {}):
        r = onto.datatype_properties[f.property_iri].range
        if r and r[0] in _NUMERIC | {XSD + "boolean"}:
            return _num(x) if r[0] in _NUMERIC else ("true" if str(x).lower() in ("true", "1") else "false")
    if isinstance(x, (int, float, bool)) and not dt:
        return t.literal(x)
    return t.literal(x, lang=f.lang, datatype=dt)


# --------------------------------------------------------------------------- aide à la construction

_NUMERIC = {XSD + n for n in ("integer", "int", "long", "short", "byte", "decimal", "float", "double", "nonNegativeInteger",
                              "positiveInteger", "negativeInteger", "nonPositiveInteger", "unsignedInt", "unsignedLong")}
_TEXT = {XSD + n for n in ("string", "normalizedString", "token", "anyURI", "language")} | {RDF + "langString", RDFS + "Literal"}
_DATE = {XSD + n for n in ("date", "dateTime", "dateTimeStamp", "gYear", "gYearMonth", "time")}
KINDS = {
    "text": ["text_contains", "equals", "regex", "lang", "in_values"],
    "number": ["equals", "number_range", "in_values"],
    "date": ["date_range", "equals"],
    "boolean": ["equals"],
    "other": ["equals", "in_values"],
}


class Suggester:
    """Lecture de l'ontologie (et des shapes) pour proposer les prochaines étapes d'une phrase."""

    def __init__(self, onto: OntoModel, shapes: Optional[ShapesModel] = None, lang: str = "fr"):
        self.o, self.shapes, self.lang = onto, shapes, lang
        self._desc: dict[str, set[str]] = {}

    # --- hiérarchies
    def up(self, c: str) -> set[str]:
        return {c, *self.o.ancestors(c)} if c in self.o.classes else {c}

    def down(self, c: str) -> set[str]:
        if c not in self._desc:
            self._desc[c] = {c, *self.o.descendants(c)}
        return self._desc[c]

    def super_props(self, p: str, coll: Optional[dict] = None) -> list[str]:
        coll = coll if coll is not None else (self.o.object_properties if p in self.o.object_properties else self.o.datatype_properties)
        out, stack = [], list(getattr(coll.get(p), "sub_property_of", []))
        while stack:
            s = stack.pop()
            if s not in out and s != p:
                out.append(s)
                stack.extend(getattr(coll.get(s), "sub_property_of", []))
        return out

    # --- domaine / portée effectifs : (conjonction de classes, union de classes, approximatif?, déclaré?)
    def eff(self, p: str, side: Literal["domain", "range"]) -> tuple[list[str], list[list[str]], bool, bool]:
        """Domaine / portée effectifs = INTERSECTION des déclarations de p et de toutes ses super-propriétés
        (dom(p) ⊑ dom(q) pour q ⊒ p), l'inverse déclaré fournissant le côté opposé. -> (conjonction, unions, approximatif, déclaré)."""
        coll = self.o.object_properties if p in self.o.object_properties else self.o.datatype_properties
        opp = {"domain": "range", "range": "domain"}[side]
        conj: list[str] = []
        unions: list[list[str]] = []
        approx = declared = False
        for q in [p, *self.super_props(p, coll)]:
            e = coll.get(q)
            if e is None:
                continue
            own = False
            if getattr(e, side) or getattr(e, f"{side}_union", []) or getattr(e, f"{side}_expr", None) is not None:
                own = True
                conj += [c for c in getattr(e, side) if c not in conj]
                if getattr(e, f"{side}_union", []):
                    unions.append(list(getattr(e, f"{side}_union")))
                approx = approx or getattr(e, f"{side}_expr", None) is not None
            inv = self._inverse_of_declared(q) if q in self.o.object_properties else None
            if not own and inv and inv in self.o.object_properties:
                ie = self.o.object_properties[inv]
                if getattr(ie, opp) or getattr(ie, f"{opp}_union", []):
                    own = True
                    conj += [c for c in getattr(ie, opp) if c not in conj]
                    if getattr(ie, f"{opp}_union", []):
                        unions.append(list(getattr(ie, f"{opp}_union")))
            declared = declared or own
        return conj, unions, approx, declared

    def _inverse_of_declared(self, p: str) -> Optional[str]:
        e = self.o.object_properties.get(p)
        if e and e.inverse_of:
            return e.inverse_of
        return next((q.iri for q in self.o.object_properties.values() if q.inverse_of == p), None)

    def applies(self, p: str, c: str, direction: str = "out") -> Optional[bool]:
        """True/False si le domaine (out) ou la portée (in) est déterminé ; None si indéterminé (non déclaré)."""
        conj, uni, approx, declared = self.eff(p, "domain" if direction == "out" else "range")
        if not declared:
            return None
        up = self.up(c)
        if approx:
            return True
        return all(x in up for x in conj) and all(any(x in up for x in u) for u in uni)

    def _ends(self, p: str, side: str) -> tuple[list[str], bool]:
        """Classes (avec descendants) admissibles de l'autre extrémité ; restricted=False si non déclarées."""
        conj, unions, approx, declared = self.eff(p, side)  # type: ignore[arg-type]
        if not declared or approx:
            return [], False
        sets = [self.down(x) for x in conj] + [set().union(*[self.down(u) for u in us]) for us in unions]
        return sorted(set.intersection(*sets)) if sets else [], True

    def label(self, iri: str) -> str:
        return self.o.label(iri, self.lang)

    def _shape_props(self, c: str, p: str) -> list:
        if not self.shapes:
            return []
        up = self.up(c)
        out = []
        for ns in self.shapes.shapes.values():
            if up & set(ns.targets.target_class) or (ns.id in up):
                for ps in ns.properties:
                    if ps.path.kind == "predicate" and ps.path.iri == p and not ps.deactivated:
                        out.append(ps)
        return out

    def target_classes(self, p: str, from_class: Optional[str], inverse: bool = False) -> dict[str, Any]:
        cands, restricted = self._ends(p, "domain" if inverse else "range")
        note = None
        if from_class and not inverse:
            for ps in self._shape_props(from_class, p):
                if ps.class_:
                    allowed = set().union(*[self.down(x) for x in ps.class_])
                    cands = sorted(set(cands) & allowed) if restricted else sorted(allowed)
                    restricted, note = True, "restreint par une shape (sh:class)"
        if not restricted:
            cands = sorted(self.o.classes)
        return {"property": p, "label": self.label(p), "inverse": inverse, "restricted": restricted, "note": note,
                "targets": [{"iri": c, "label": self.label(c), "direct": self._is_direct(p, c, inverse)} for c in cands]}

    def _is_direct(self, p: str, c: str, inverse: bool) -> bool:
        conj, uni, _, _ = self.eff(p, "domain" if inverse else "range")
        return c in conj or any(c in u for u in uni)

    # --- suggestions pour une classe
    def for_class(self, c: str) -> dict[str, Any]:
        if c not in self.o.classes:
            raise KeyError(c)
        objs: list[dict[str, Any]] = []
        for p, e in self.o.object_properties.items():
            for direction in ("out", "in"):
                ok = self.applies(p, c, direction)
                if ok is False:
                    continue
                inv = direction == "in"
                tg = self.target_classes(p, c, inverse=inv)
                entry = {"iri": p, "label": self.label(p), "direction": direction, "inverse": inv,
                         "comment": (e.comments.get(self.lang) or e.comments.get("en") or next(iter(e.comments.values()), "")),
                         "inverse_of": self._inverse_of_declared(p), "untyped": ok is None,
                         "inherited_from": self._inherited(p, c, direction),
                         "targets": tg["targets"], "targets_restricted": tg["restricted"], "note": tg["note"],
                         "required": False, "max_count": None}
                if not inv:
                    for ps in self._shape_props(c, p):
                        entry["required"] = entry["required"] or bool(ps.min_count and ps.min_count >= 1)
                        if ps.max_count is not None:
                            entry["max_count"] = ps.max_count
                if ok is None and direction == "in":
                    continue  # propriété sans portée déclarée : proposée seulement dans le sens sortant
                objs.append(entry)
        datas: list[dict[str, Any]] = []
        for p, d in self.o.datatype_properties.items():
            ok = self.applies(p, c, "out")
            if ok is False:
                continue
            rng = (self.eff(p, "range")[0] or d.range or [XSD + "string"])[0]
            kind = self.value_kind(rng, d)
            entry = {"iri": p, "label": self.label(p), "datatype": rng, "datatype_label": local_name(rng), "value_kind": kind,
                     "filter_kinds": KINDS[kind], "untyped": ok is None, "functional": d.functional,
                     "required": False, "max_count": 1 if d.functional else None,
                     "inherited_from": self._inherited(p, c, "out")}
            for ps in self._shape_props(c, p):
                entry["required"] = entry["required"] or bool(ps.min_count and ps.min_count >= 1)
                if ps.max_count is not None:
                    entry["max_count"] = ps.max_count
                if ps.datatype:
                    entry["datatype"], entry["datatype_label"] = ps.datatype, local_name(ps.datatype)
                    entry["value_kind"] = self.value_kind(ps.datatype, d)
                    entry["filter_kinds"] = KINDS[entry["value_kind"]]
            datas.append(entry)
        datas.append({"iri": RDFS + "label", "label": {"fr": "libellé", "en": "label"}.get(self.lang, "label"),
                      "datatype": RDF + "langString", "datatype_label": "langString", "value_kind": "text",
                      "filter_kinds": KINDS["text"], "untyped": False, "functional": False, "required": False,
                      "max_count": None, "inherited_from": None, "synthetic": True})
        key = lambda e: (e["label"].lower(), e["iri"])  # noqa: E731
        return {"class": c, "label": self.label(c), "lang": self.lang,
                "ancestors": [{"iri": a, "label": self.label(a)} for a in self.o.ancestors(c)],
                "subclasses": [{"iri": s, "label": self.label(s)} for s in sorted(self.down(c) - {c})],
                "outgoing": sorted([e for e in objs if e["direction"] == "out"], key=key),
                "incoming": sorted([e for e in objs if e["direction"] == "in"], key=key),
                "data_properties": sorted(datas, key=key)}

    def value_kind(self, dt: str, d: Any = None) -> str:
        seen = set()
        while dt not in seen:
            seen.add(dt)
            if dt in _TEXT:
                return "text"
            if dt in _NUMERIC:
                return "number"
            if dt in _DATE:
                return "date"
            if dt == XSD + "boolean":
                return "boolean"
            dd = self.o.datatypes.get(dt)
            base = dd.definition.base if dd and dd.definition else None
            if not base:
                break
            dt = base
        return "other"

    def _inherited(self, p: str, c: str, direction: str) -> Optional[str]:
        """Classe ancêtre qui porte le domaine / la portée (None si la classe elle-même ou indéterminé)."""
        conj, uni, _, _ = self.eff(p, "domain" if direction == "out" else "range")
        for x in [*conj, *[y for u in uni for y in u]]:
            if x != c and x in self.up(c):
                return x
        return None


# ---------------------------------------------------------------------------------------- génération

class BuildResult(BaseModel):
    sparql: str
    cypher: Optional[str] = None
    curiosity: Optional[str] = None
    graphql: Optional[str] = None
    notes: list[str] = Field(default_factory=list)
    lossy: bool = False
    supported: bool = True
    warnings: list[str] = Field(default_factory=list)


def build_all(q: GuidedQuery, onto: OntoModel, pg: Optional[PGModel], prefixes: Optional[dict[str, str]] = None) -> BuildResult:
    warns = validate_guided(q, onto)
    sparql = to_sparql(q, onto, prefixes)
    res = BuildResult(sparql=sparql, warnings=warns)
    if pg is None:
        return res
    from .translate import translate  # réutilisation de la traduction existante
    tr = translate(sparql, pg, onto)
    res.cypher, res.curiosity, res.graphql = tr.cypher, tr.curiosity, tr.graphql
    res.notes, res.lossy, res.supported = list(tr.notes), tr.lossy, tr.supported
    if q.subclasses:
        res.notes.append("[info] « Inclure les sous-classes » : chemin rdf:type/rdfs:subClassOf* côté SPARQL ; "
                         "côté property graph, les sous-types sont portés par les labels ou le discriminant.")
    return res


# ------------------------------------------------------------------- SPARQL → requête guidée (simple)

def guided_from_sparql(sparql: str, onto: OntoModel) -> tuple[Optional[GuidedQuery], str]:
    """Convertit un SELECT simple (BGP, OPTIONAL, chemins en séquence, ORDER BY, LIMIT) en requête guidée.
    Renvoie (None, raison) si la requête dépasse ce que le constructeur sait exprimer."""
    from rdflib import Literal, URIRef, Variable
    from rdflib.paths import SequencePath
    from rdflib.plugins.sparql import prepareQuery
    try:
        alg = prepareQuery(sparql).algebra
    except Exception as e:  # noqa: BLE001
        return None, f"SPARQL illisible : {type(e).__name__}"
    limit = offset = None
    distinct = False
    order: list[tuple[str, bool]] = []
    node = alg
    triples: list[tuple[Any, Any, Any, bool]] = []
    proj: list[str] = []
    n = 0

    def bgp(nd, opt):
        for s, p, o in nd.triples:
            triples.append((s, p, o, opt))

    try:
        while True:
            n += 1
            if n > 12:
                return None, "structure trop complexe"
            name = node.name
            if name == "SelectQuery":
                node = node.p
            elif name == "Slice":
                limit, offset = node.length, node.start or None
                node = node.p
            elif name == "Distinct":
                distinct = True
                node = node.p
            elif name == "Project":
                proj = [str(v) for v in node.PV]
                node = node.p
            elif name == "OrderBy":
                for c in node.expr:
                    if not isinstance(c.expr, Variable):
                        return None, "tri sur une expression"
                    order.append((str(c.expr), c.order == "DESC"))
                node = node.p
            elif name == "BGP":
                bgp(node, False)
                break
            elif name == "LeftJoin":
                if node.expr is not None and getattr(node.expr, "name", "") != "TrueFilter":
                    return None, "OPTIONAL avec filtre"
                left, right = node.p1, node.p2
                if left.name != "BGP" or right.name != "BGP":
                    return None, "OPTIONAL imbriqué"
                bgp(left, False)
                bgp(right, True)
                break
            else:
                return None, f"opérateur « {name} » non exprimable (agrégat, filtre, union…)"
    except AttributeError:
        return None, "structure non reconnue"
    cls: dict[str, str] = {}
    objs: list[tuple[str, str, str, bool]] = []
    datas: list[tuple[str, str, str]] = []
    for s, p, o, opt in triples:
        if isinstance(p, SequencePath):
            if not (isinstance(s, Variable) and isinstance(o, Variable)) or not all(isinstance(x, URIRef) for x in p.args):
                return None, "chemin non exprimable"
            prev = str(s)
            for i, x in enumerate(p.args):
                nxt = str(o) if i == len(p.args) - 1 else f"{prev}_{i + 1}"
                objs.append((prev, str(x), nxt, opt))
                prev = nxt
            continue
        if not isinstance(p, URIRef) or not isinstance(s, Variable):
            return None, "triplet non exprimable"
        pi = str(p)
        if pi == RDF_TYPE:
            if not isinstance(o, URIRef):
                return None, "type non constant"
            cls[str(s)] = str(o)
        elif pi in onto.object_properties and isinstance(o, Variable):
            objs.append((str(s), pi, str(o), opt))
        elif pi in onto.datatype_properties and isinstance(o, Variable):
            datas.append((str(s), pi, str(o)))
        else:
            return None, f"prédicat « {local_name(pi)} » absent de l'ontologie ou non exprimable"
    if not objs and not cls:
        return None, "aucune classe ni relation"
    root = next((v for v in cls), None) or objs[0][0]
    steps: list[Step] = []
    placed = {root}
    pending = list(objs)
    while pending:
        for t in list(pending):
            s, p, o, opt = t
            if s in placed and o not in placed:
                steps.append(Step(from_var=s, property_iri=p, to_var=o, to_class_iri=cls.get(o), optional=opt))
                placed.add(o)
            elif o in placed and s not in placed:
                steps.append(Step(from_var=o, property_iri=p, inverse=True, to_var=s, to_class_iri=cls.get(s), optional=opt))
                placed.add(s)
            elif s in placed and o in placed:
                return None, "cycle dans le motif"
            else:
                continue
            pending.remove(t)
            break
        else:
            return None, "motif non connexe"
    dvar = {v: (s, p) for s, p, v in datas}
    select: list[SelectItem] = []
    for v in proj:
        if v in dvar:
            select.append(SelectItem(var=dvar[v][0], property_iri=dvar[v][1]))
        elif v in placed:
            select.append(SelectItem(var=v))
        else:
            return None, f"variable « {v} » non reconnue"
    ob = []
    for v, d in order:
        if v in dvar:
            ob.append(OrderItem(var=dvar[v][0], property_iri=dvar[v][1], desc=d))
        elif v in placed:
            ob.append(OrderItem(var=v, desc=d))
        else:
            return None, "tri sur une variable inconnue"
    try:
        lim = int(limit) if limit is not None else None
        off = int(offset) if offset else None
    except (TypeError, ValueError):
        return None, "LIMIT illisible"
    for s, vv in {(a, b) for a, b in [dvar[v] for v in dvar]}:
        pass
    return GuidedQuery(root=Root(var=root, class_iri=cls.get(root)), steps=steps, select=select, order_by=ob,
                       limit=lim, offset=off, distinct=distinct), \
        "propriétés de données lues en OPTIONAL" if datas else ""
