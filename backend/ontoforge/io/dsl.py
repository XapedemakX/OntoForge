"""DSL texte compact → OntoModel (une ligne = un axiome).

`parse_dsl(text, base=None)` ne lève jamais d'exception : les erreurs sont renvoyées par ligne
(`{"line": n, "message": "…"}`) et les lignes valides sont appliquées quand même.
"""
from __future__ import annotations

import re
from typing import Optional

from ..core.onto_model import (
    ClassExpr, DatatypeProperty, Fact, Individual, ObjectProperty, OntClass, OntoModel, OntologyMeta,
    Restriction, OWL, RDF, RDFS, XSD,
)

__all__ = ["parse_dsl", "DSL_HELP", "DSL_EXAMPLE"]

DEFAULT_BASE = "https://example.org/onto#"
STD_PREFIXES = {
    "owl": OWL, "rdf": RDF, "rdfs": RDFS, "xsd": XSD,
    "skos": "http://www.w3.org/2004/02/skos/core#", "dcterms": "http://purl.org/dc/terms/",
}
XSD_SHORT = {"string", "integer", "int", "long", "decimal", "boolean", "dateTime", "dateTimeStamp", "float",
             "double", "anyURI", "nonNegativeInteger", "positiveInteger", "base64Binary", "hexBinary"}
CHARS = ["functional", "inverseFunctional", "transitive", "symmetric", "asymmetric", "reflexive", "irreflexive"]
CARD = {"1": ("exactly", 1), "0..1": ("max", 1), "1..*": ("min", 1), "*": None, "0..*": None}

_STR = r'"((?:[^"\\]|\\.)*)"(?:@([A-Za-z]{1,8}(?:-[A-Za-z0-9]+)*))?'
_STR_RE = re.compile(_STR)


class _Err(Exception):
    pass


def _strip_comment(line: str) -> str:
    out, in_str, in_iri = [], False, False
    for i, ch in enumerate(line):
        if in_str:
            if ch == '"' and line[i - 1] != "\\":
                in_str = False
        elif in_iri:
            if ch == ">":
                in_iri = False
        elif ch == '"':
            in_str = True
        elif ch == "<" and re.match(r"<[^\s<>]*>", line[i:]):
            in_iri = True
        elif ch == "#" and (i == 0 or line[i - 1].isspace()):
            break
        out.append(ch)
    return "".join(out).strip()


class _Ctx:
    def __init__(self, base: Optional[OntoModel]):
        self.m = base.model_copy(deep=True) if base else OntoModel(meta=OntologyMeta(iri=""))
        self.prefixes = dict(STD_PREFIXES)
        self.prefixes.update(self.m.meta.prefixes)
        ns = self.prefixes.get("")
        if not ns:
            ns = (self.m.meta.iri.rstrip("#/") + "#") if self.m.meta.iri else DEFAULT_BASE
        self.base = ns

    # ---- résolution des noms ----
    def iri(self, tok: str, datatype: bool = False) -> str:
        tok = tok.strip()
        if tok.startswith("<") and tok.endswith(">"):
            return tok[1:-1]
        if tok == "a":
            return RDF + "type"
        if datatype and tok in XSD_SHORT:
            return XSD + tok
        if re.match(r"^[A-Za-z_][\w.-]*:[^\s/]", tok) and not tok.startswith("http"):
            p, _, loc = tok.partition(":")
            if p in self.prefixes:
                return self.prefixes[p] + loc
            raise _Err(f"préfixe inconnu « {p}: » (déclarez-le avec @prefix {p}: <…>)")
        if tok.startswith(":"):
            return self.base + tok[1:]
        if re.match(r"^https?://", tok) or tok.startswith("urn:"):
            return tok
        if not re.match(r"^[\w\-.]+$", tok):
            raise _Err(f"nom invalide « {tok} »")
        return self.base + tok

    def cls(self, tok: str) -> str:
        iri = self.iri(tok)
        m = self.m
        if iri in m.object_properties or iri in m.datatype_properties:
            raise _Err(f"« {tok} » est déjà une propriété, pas une classe")
        if iri not in m.classes and iri != OWL + "Thing":
            m.classes[iri] = OntClass(iri=iri)
        return iri

    def labels_into(self, ent, rest: str, key: str = "labels") -> str:
        """Extrait les chaînes (labels) de `rest`, renvoie le reste sans elles."""
        def rep(mt):
            raw = mt.group(1).replace('\\"', '"')
            getattr(ent, key)[mt.group(2) or ""] = raw
            return " "
        return _STR_RE.sub(rep, rest)


def _add(lst: list, x) -> None:
    if x not in lst:
        lst.append(x)


def _set_domain_range(prop, field: str, cls_iri: str) -> None:
    """Plusieurs classes pour une même propriété = union (intention usuelle), pas intersection."""
    cur, un = getattr(prop, field), getattr(prop, field + "_union")
    if not cur and not un:
        cur.append(cls_iri)
    elif cls_iri in cur or cls_iri in un:
        return
    else:
        if cur:
            un.extend(cur)
            cur.clear()
        un.append(cls_iri)


def _parse_tail(c: _Ctx, rest: str, ent, allow_chars: bool) -> dict:
    """Analyse « [card] key inverse X transitive … "label"@fr »."""
    info = {"card": "unset", "key": False, "inverse": None, "chars": []}
    # chaînes : `doc "…"` → commentaire, sinon label
    def doc(mt):
        ent.comments[mt.group(2) or ""] = mt.group(1).replace('\\"', '"')
        return " "
    rest = re.sub(r"\bdoc\s+" + _STR, doc, rest)
    rest = c.labels_into(ent, rest)
    mt = re.search(r"\[\s*([^\]]*?)\s*\]", rest)
    if mt:
        key = mt.group(1).replace(" ", "")
        if key not in CARD:
            m2 = re.fullmatch(r"(\d+)(?:\.\.(\d+|\*))?", key)
            if not m2:
                raise _Err(f"cardinalité invalide « [{mt.group(1)}] » (attendu [1], [0..1], [*], [1..*], [n], [n..m])")
            lo = int(m2.group(1))
            hi = lo if m2.group(2) is None else (None if m2.group(2) == "*" else int(m2.group(2)))
            info["card"] = ("range", lo, hi)
        else:
            info["card"] = CARD[key]
        rest = rest[:mt.start()] + " " + rest[mt.end():]
    words = rest.split()
    i = 0
    while i < len(words):
        w = words[i]
        if w == "key":
            info["key"] = True
        elif w == "inverse":
            if i + 1 >= len(words):
                raise _Err("« inverse » attend le nom de la propriété inverse")
            info["inverse"] = words[i + 1]
            i += 1
        elif w in CHARS:
            if not allow_chars and w != "functional":
                raise _Err(f"caractéristique « {w} » illégale sur une propriété de données (OWL 2 : seule functional)")
            info["chars"].append(w)
        else:
            raise _Err(f"mot inattendu « {w} »")
        i += 1
    return info


def _apply_card(cls: OntClass, prop_iri: str, card, filler: Optional[str] = None) -> None:
    if card in ("unset", None):
        return
    specs = []
    if card[0] == "range":
        _, lo, hi = card
        if hi is not None and hi == lo:
            specs = [("exactly", lo)]
        else:
            if lo:
                specs.append(("min", lo))
            if hi is not None:
                specs.append(("max", hi))
    else:
        specs.append(card)
    for kind, n in specs:
        r = Restriction(property=prop_iri, kind=kind, n=n, filler=filler)
        if r not in cls.restrictions:
            cls.restrictions.append(r)


def _line(c: _Ctx, line: str) -> None:
    m = c.m
    if line.startswith("@prefix"):
        mt = re.fullmatch(r"@prefix\s+([A-Za-z_][\w.-]*)?:\s*<([^>]*)>\s*\.?", line)
        if not mt:
            raise _Err("syntaxe attendue : @prefix ex: <https://…#>")
        c.prefixes[mt.group(1) or ""] = mt.group(2)
        m.meta.prefixes[mt.group(1) or ""] = mt.group(2)
        if not mt.group(1):
            c.base = mt.group(2)
        return
    if line.startswith("@base"):
        mt = re.fullmatch(r"@base\s+<([^>]*)>\s*\.?", line)
        if not mt:
            raise _Err("syntaxe attendue : @base <https://…#>")
        c.base = mt.group(1)
        if not m.meta.iri:
            m.meta.iri = mt.group(1).rstrip("#/")
        return
    # énumération : FuelType : {A, B}
    mt = re.fullmatch(r"(\S+)\s*:\s*\{(.*)\}\s*(.*)", line)
    if mt:
        ci = c.cls(mt.group(1))
        cl = m.classes[ci]
        members = [x.strip() for x in mt.group(2).split(",") if x.strip()]
        if not members:
            raise _Err("énumération vide")
        iris = [c.iri(x) for x in members]
        cl.one_of = list(iris)
        for ii in iris:
            ind = m.individuals.setdefault(ii, Individual(iri=ii))
            _add(ind.types, ci)
        c.labels_into(cl, mt.group(3))
        return
    # relation : A -p-> B [card] inverse q …
    mt = re.fullmatch(r"(\S+)\s+-\s*(\S+?)\s*->\s*(\S+)(.*)", line)
    if mt:
        a, p, b = c.cls(mt.group(1)), c.iri(mt.group(2)), c.cls(mt.group(3))
        if p in m.datatype_properties:
            raise _Err(f"« {mt.group(2)} » est une propriété de données")
        op = m.object_properties.setdefault(p, ObjectProperty(iri=p))
        info = _parse_tail(c, mt.group(4), op, True)
        _set_domain_range(op, "domain", a)
        _set_domain_range(op, "range", b)
        for ch in info["chars"]:
            _add(op.characteristics, ch)
        if info["inverse"]:
            q = c.iri(info["inverse"])
            if q in m.datatype_properties:
                raise _Err("l'inverse ne peut pas être une propriété de données")
            op.inverse_of = q
            inv = m.object_properties.setdefault(q, ObjectProperty(iri=q))
            _set_domain_range(inv, "domain", b)
            _set_domain_range(inv, "range", a)
        _apply_card(m.classes[a], p, info["card"])
        if info["key"]:
            raise _Err("« key » n'est admis que sur une propriété de données (Classe.prop : type key)")
        return
    # propriété de données : A.p : type [card] key
    mt = re.fullmatch(r"([^\s.<>]+(?:\.[^\s.<>]+)*?)\.([A-Za-z_][\w-]*)\s*:\s*(\S+)(.*)", line)
    if mt and not line.startswith("<"):
        a, p = c.cls(mt.group(1)), c.iri(mt.group(2))
        dt = c.iri(mt.group(3), datatype=True)
        if p in m.object_properties:
            raise _Err(f"« {mt.group(2)} » est déjà une propriété objet")
        dp = m.datatype_properties.setdefault(p, DatatypeProperty(iri=p))
        info = _parse_tail(c, mt.group(4), dp, False)
        _set_domain_range(dp, "domain", a)
        _add(dp.range, dt)
        if "functional" in info["chars"]:
            dp.functional = True
        _apply_card(m.classes[a], p, info["card"])
        if info["key"]:
            _add(m.classes[a].has_keys, [p]) if [p] not in m.classes[a].has_keys else None
        return
    # individu : x a C, D [labels]
    mt = re.fullmatch(r"(\S+)\s+a\s+([^\"]+?)\s*((?:" + _STR + r"\s*)*)", line)
    if mt:
        ii = c.iri(mt.group(1))
        if ii in m.classes:
            raise _Err(f"« {mt.group(1)} » est une classe, pas un individu")
        ind = m.individuals.setdefault(ii, Individual(iri=ii))
        for t in [x.strip() for x in mt.group(2).split(",") if x.strip()]:
            _add(ind.types, c.cls(t))
        c.labels_into(ind, mt.group(3) or "")
        return
    # A <> B (disjointes) ; A = B (équivalentes) ; A < B, C (sous-classe)
    mt = re.fullmatch(r"(\S+)\s+(<>|=|<)\s+(.+)", line)
    if mt:
        a = c.cls(mt.group(1))
        rest = mt.group(3)
        labelholder = m.classes[a]
        rest = c.labels_into(labelholder, rest)
        targets = [x.strip() for x in rest.split(",") if x.strip()]
        if not targets:
            raise _Err("opérande manquant")
        bs = []
        for t in targets:
            if " " in t:
                raise _Err(f"nom invalide « {t} » (séparez les parents par des virgules)")
            bs.append(c.cls(t))
        if mt.group(2) == "<":  # tout est vérifié avant d'écrire : une ligne refusée n'a aucun effet, même au-delà de 1 500 lignes
            from ..editing import cycles
            for b in bs:
                if b == a:
                    raise _Err("une classe ne peut pas être sa propre sous-classe directe")
                path = cycles.closing_path(m, a, b)
                if path:
                    raise _Err(cycles.cycle_message(a, b, path))
        for b in bs:
            if mt.group(2) == "<":
                _add(m.classes[a].sub_class_of, b)
            elif mt.group(2) == "=":
                e = ClassExpr(op="named", iri=b)
                if e not in m.classes[a].equivalent_to:
                    m.classes[a].equivalent_to.append(e)
            else:
                if a not in m.classes[b].disjoint_with:
                    _add(m.classes[a].disjoint_with, b)
        return
    # déclaration : Name "label"@fr "label"@en [doc "…"]
    mt = re.fullmatch(r"([^\s\"]+)((?:\s+(?:doc\s+)?" + _STR + r")*)", line)
    if mt:
        ci = c.iri(mt.group(1))
        if ci in m.object_properties or ci in m.datatype_properties:  # libeller une propriété déjà utilisée
            cl = (m.object_properties.get(ci) or m.datatype_properties[ci])
        else:
            c.cls(mt.group(1))
            cl = m.classes[ci]
        tail = mt.group(2) or ""
        def doc(x):
            cl.comments[x.group(2) or ""] = x.group(1).replace('\\"', '"')
            return " "
        tail = re.sub(r"\bdoc\s+" + _STR, doc, tail)
        c.labels_into(cl, tail)
        return
    raise _Err("ligne non reconnue (voir l'aide du DSL)")


def parse_dsl(text: str, base: Optional[OntoModel] = None) -> tuple[OntoModel, list[dict]]:
    errors: list[dict] = []
    try:
        c = _Ctx(base)
    except Exception as e:  # base invalide : ne jamais lever
        return OntoModel(meta=OntologyMeta(iri="")), [{"line": 0, "message": f"modèle de base invalide : {e}"}]
    lines = (text or "").splitlines()
    rollback = len(lines) <= 1500
    for n, raw in enumerate(lines, 1):
        line = _strip_comment(raw)
        if not line:
            continue
        snap = (c.m.model_copy(deep=True), dict(c.prefixes), c.base) if rollback else None
        try:
            _line(c, line)
        except Exception as e:  # _Err attendue ; le reste = filet de sécurité
            errors.append({"line": n, "message": str(e) if isinstance(e, _Err) else f"erreur interne : {e}"})
            if snap:  # une ligne en erreur n'a aucun effet partiel
                c.m, c.prefixes, c.base = snap
    if not c.m.meta.iri:
        c.m.meta.iri = c.base.rstrip("#/")
    return c.m, errors


DSL_EXAMPLE = '''# Mini-ontologie de maintenance (DSL OntoForge)
@prefix am: <https://w3id.org/ontoforge/automaint#>
@base <https://w3id.org/ontoforge/automaint#>

Vehicle "Véhicule"@fr "Vehicle"@en
ElectricVehicle < Vehicle, LowEmissionAsset
Car = Automobile
Vehicle <> Garage
Vehicle.vin : string [1] key "VIN"
Vehicle.mileageKm : decimal [0..1]
RepairOrder -concerns-> Vehicle [1] inverse hasRepairOrder
Part -partOf-> Part transitive
FuelType : {Diesel, Petrol, Electric}
am:garage42 a Garage "Garage 42"
'''

DSL_HELP = f"""Aide du DSL OntoForge
=====================

Une ligne = un axiome. Les lignes vides sont ignorées ; « # » (précédé d'un espace ou en début de ligne)
commence un commentaire. Une erreur sur une ligne n'empêche pas de lire les autres : elle est signalée
avec son numéro de ligne.

Noms : `Vehicle` (relatif à @base / @prefix « : »), `am:Vehicle` (CURIE), `<https://…#Vehicle>` (IRI complète).
Préfixes prédéfinis : owl, rdf, rdfs, xsd, skos, dcterms. Les classes citées mais non déclarées sont créées.

Syntaxe
-------
@prefix ex: <https://exemple.org/onto#>      déclare un préfixe (le préfixe vide « : » fixe l'espace de noms par défaut)
@base <https://exemple.org/onto#>             espace de noms des noms relatifs
Vehicle "Véhicule"@fr "Vehicle"@en            déclare une classe avec ses libellés (doc "texte"@fr = commentaire)
ElectricVehicle < Vehicle, LowEmissionAsset   sous-classe de (SubClassOf), plusieurs parents possibles
Car = Automobile                              classes équivalentes (EquivalentClasses)
Vehicle <> Garage                             classes disjointes (DisjointClasses)
Vehicle.vin : string [1] key "VIN"            propriété de données : domaine Vehicle, type xsd:string,
                                              cardinalité [1] [0..1] [*] [1..*] [n] [n..m], « key » → owl:hasKey
RepairOrder -concerns-> Vehicle [1] inverse hasRepairOrder transitive
                                              propriété objet : domaine, portée, cardinalité (restriction sur le
                                              domaine), inverse, caractéristiques : functional, inverseFunctional,
                                              transitive, symmetric, asymmetric, reflexive, irreflexive
FuelType : {{Diesel, Petrol, Electric}}         classe énumérée (owl:oneOf) ; les individus sont créés
am:garage42 a Garage "Garage 42"              individu typé

Types de données : string, integer, int, long, decimal, boolean, dateTime, float, double, anyURI… (xsd:),
ou toute IRI/CURIE. Préférez xsd:dateTime à xsd:date/gYear/duration, hors de la carte de datatypes OWL 2 DL.

Sémantique à connaître
----------------------
* Une même propriété utilisée avec plusieurs classes en domaine (ou portée) est lue comme une UNION de classes
  (rdfs:domain [owl:unionOf …]) ; en RDF pur, plusieurs rdfs:domain voudraient dire INTERSECTION.
* `[1]`, `[0..1]`, `[1..*]` produisent des restrictions de cardinalité sur la classe (monde ouvert : ce sont des
  axiomes, pas des contraintes de validation ; utilisez SHACL pour valider).
* `key` produit owl:hasKey : il n'impose ni l'existence ni l'unicité de la valeur.

Exemple complet (vérifié automatiquement par les tests)
--------------------------------------------------------
{DSL_EXAMPLE}"""
