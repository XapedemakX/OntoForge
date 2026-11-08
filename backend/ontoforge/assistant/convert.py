"""JSON intermédiaire (simple, produit par le LLM ou les pré-analyseurs) → OntoModel validé."""
from __future__ import annotations

import json
import re
from typing import Any, Optional

from ontoforge.core.onto_model import (XSD, Annotation, DatatypeProperty, ObjectProperty, OntClass, OntoModel,
                                       OntologyMeta, Restriction)

from .naming import camel, pascal

SKOS = "http://www.w3.org/2004/02/skos/core#"
DEFAULT_BASE = "https://w3id.org/ontoforge/draft#"
# xsd:date / gYear... ne figurent pas dans la table de datatypes OWL 2 → remplacés par dateTime / integer
DATATYPES = {"string": "string", "integer": "integer", "int": "integer", "long": "long", "decimal": "decimal", "float": "float",
             "double": "double", "boolean": "boolean", "bool": "boolean", "datetime": "dateTime", "anyuri": "anyURI",
             "nonnegativeinteger": "nonNegativeInteger", "positiveinteger": "positiveInteger", "literal": "string"}
DEGRADED = {"date": "dateTime", "gyear": "integer", "time": "string", "gyearmonth": "string", "gmonthday": "string", "duration": "string"}
CHARS = {"functional", "inverseFunctional", "transitive", "symmetric", "asymmetric", "reflexive", "irreflexive"}


def extract_json(raw: str) -> dict[str, Any]:
    """Extrait un objet JSON d'une réponse LLM (balises ``` tolérées). Lève ValueError si impossible."""
    s = raw.strip()
    s = re.sub(r"^```(?:json)?\s*|\s*```$", "", s, flags=re.I)
    a, b = s.find("{"), s.rfind("}")
    if a < 0 or b <= a:
        raise ValueError("aucun objet JSON trouvé dans la réponse")
    try:
        obj = json.loads(s[a:b + 1])
    except json.JSONDecodeError as exc:
        raise ValueError(f"JSON invalide : {exc.msg} (ligne {exc.lineno}, colonne {exc.colno})") from None
    if not isinstance(obj, dict):
        raise ValueError("la racine JSON doit être un objet")
    return obj


def is_absolute_iri(n: str) -> bool:
    """Vrai pour une IRI absolue (``http://``, ``https://``, ``urn:``) : un nom local comme « httpUrl » n'en est pas une."""
    return n.startswith(("http://", "https://", "urn:"))


def normalize_base(base: Optional[str]) -> str:
    b = (base or DEFAULT_BASE).strip()
    return b if b.endswith(("#", "/")) else b + "#"


def _labels(d: dict[str, Any], fallback: str) -> dict[str, str]:
    out = {}
    for lang in ("fr", "en"):
        v = d.get(f"label_{lang}")
        if isinstance(v, str) and v.strip():
            out[lang] = v.strip()
    if isinstance(d.get("labels"), dict):
        out.update({k: str(v) for k, v in d["labels"].items() if v})
    if not out and fallback:
        out["en"] = fallback
    return out


def _comments(d: dict[str, Any]) -> dict[str, str]:
    out = {}
    for lang in ("fr", "en"):
        v = d.get(f"comment_{lang}")
        if isinstance(v, str) and v.strip():
            out[lang] = v.strip()
    v = d.get("comment")
    if isinstance(v, str) and v.strip() and not out:
        out["fr"] = v.strip()
    return out


def _annots(d: dict[str, Any]) -> list[Annotation]:
    out = []
    for key, prop in (("exact_match", "exactMatch"), ("close_match", "closeMatch"), ("see_also", None)):
        v = d.get(key)
        if isinstance(v, str) and is_absolute_iri(v):
            out.append(Annotation(property=(SKOS + prop) if prop else "http://www.w3.org/2000/01/rdf-schema#seeAlso", value=v, is_iri=True))
    return out


def to_onto(data: dict[str, Any], base_iri: Optional[str] = None) -> tuple[OntoModel, list[str]]:
    """Convertit et valide ; retourne (OntoModel, warnings). Les éléments invalides sont écartés avec avertissement."""
    base = normalize_base(base_iri)
    warns: list[str] = [str(w) for w in data.get("warnings", []) if w] if isinstance(data.get("warnings"), list) else []
    ont = data.get("ontology") if isinstance(data.get("ontology"), dict) else {}
    meta = OntologyMeta(iri=base.rstrip("#/"), labels=_labels(ont, ""), comments=_comments(ont),
                        prefixes={"ex": base, "owl": "http://www.w3.org/2002/07/owl#", "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
                                  "xsd": XSD, "skos": SKOS})
    m = OntoModel(meta=meta)

    def ciri(n: str) -> str:
        return n if is_absolute_iri(n) else base + pascal(n)

    def piri(n: str) -> str:
        return n if is_absolute_iri(n) else base + camel(n)

    def ensure_class(name: str, why: str) -> str:
        i = ciri(name)
        if i not in m.classes:
            m.classes[i] = OntClass(iri=i, labels={"en": name})
            warns.append(f"Classe « {name} » {why} : créée automatiquement, à compléter.")
        return i

    items = [c for c in data.get("classes", []) if isinstance(c, dict) and c.get("name")]
    for c in items:
        i = ciri(str(c["name"]))
        m.classes[i] = OntClass(iri=i, labels=_labels(c, str(c["name"])), comments=_comments(c), annotations=_annots(c))
    for c in items:
        i = ciri(str(c["name"]))
        oc = m.classes[i]
        parents = c.get("parents") or ([c["parent"]] if c.get("parent") else [])
        for p in parents:
            pi = ensure_class(str(p), "référencée comme parent")
            if pi != i and pi not in oc.sub_class_of:
                oc.sub_class_of.append(pi)
        for d in c.get("disjoint_with", []) or []:
            di = ensure_class(str(d), "déclarée disjointe")
            if di != i and di not in oc.disjoint_with:
                oc.disjoint_with.append(di)
    cyc = [i for i in m.classes if i in m.ancestors(i)]
    for i in cyc:
        m.classes[i].sub_class_of = []
        warns.append(f"Cycle de hiérarchie détecté sur {i} : parents retirés.")

    for o in data.get("object_properties", []) or []:
        if not isinstance(o, dict) or not o.get("name"):
            continue
        i = piri(str(o["name"]))
        op = ObjectProperty(iri=i, labels=_labels(o, str(o["name"])), comments=_comments(o), annotations=_annots(o))
        if o.get("domain"):
            op.domain = [ensure_class(str(o["domain"]), "utilisée comme domaine")]
        if o.get("range"):
            op.range = [ensure_class(str(o["range"]), "utilisée comme portée")]
        ch = [x for x in (o.get("characteristics") or []) if x in CHARS]
        if o.get("functional") and "functional" not in ch:
            ch.append("functional")
        op.characteristics = ch
        if o.get("inverse"):
            inv = piri(str(o["inverse"]))
            op.inverse_of = inv
            if inv not in m.object_properties:
                m.object_properties[inv] = ObjectProperty(iri=inv, labels={"en": str(o["inverse"])}, domain=list(op.range),
                                                          range=list(op.domain), inverse_of=i)
        if i in m.object_properties and m.object_properties[i].inverse_of and not op.inverse_of:
            op.inverse_of = m.object_properties[i].inverse_of
        m.object_properties[i] = op
        _cardinality(m, o, op.domain, i, None)

    for d in data.get("datatype_properties", []) or []:
        if not isinstance(d, dict) or not d.get("name"):
            continue
        i = piri(str(d["name"]))
        rng = str(d.get("range") or "string")
        key = rng.split("#")[-1].split(":")[-1].lower()
        if is_absolute_iri(rng):
            dt = rng
        elif key in DEGRADED:
            dt = XSD + DEGRADED[key]
            warns.append(f"Propriété « {d['name']} » : xsd:{rng.split(':')[-1]} n'est pas dans la table de datatypes OWL 2 DL, xsd:{DEGRADED[key]} utilisé.")
        elif key in DATATYPES:
            dt = XSD + DATATYPES[key]
        else:
            dt = XSD + "string"
            warns.append(f"Propriété « {d['name']} » : type « {rng} » inconnu, xsd:string utilisé.")
        dom = [ensure_class(str(d["domain"]), "utilisée comme domaine")] if d.get("domain") else []
        dp = DatatypeProperty(iri=i, labels=_labels(d, str(d["name"])), comments=_comments(d), annotations=_annots(d),
                              domain=dom, range=[dt], functional=bool(d.get("functional")))
        m.datatype_properties[i] = dp
        _cardinality(m, d, dom, i, dt)

    for c in items:
        keys = []
        for k in c.get("key", []) or []:
            ki = piri(str(k))
            if ki in m.datatype_properties or ki in m.object_properties:
                keys.append(ki)
            else:
                warns.append(f"Clé « {k} » de {c['name']} : propriété inconnue, clé ignorée.")
        if keys:
            m.classes[ciri(str(c["name"]))].has_keys.append(keys)
    if not m.classes:
        warns.append("La proposition ne contient aucune classe.")
    return OntoModel.model_validate(m.model_dump()), warns


def _cardinality(m: OntoModel, d: dict[str, Any], domains: list[str], prop: str, filler: Optional[str]) -> None:
    mn = 1 if d.get("required") else d.get("min")
    mx = d.get("max")
    for dom in domains:
        for kind, n in (("min", mn), ("max", mx)):
            if isinstance(n, int) and not isinstance(n, bool) and n >= (1 if kind == "min" else 0):
                m.classes[dom].restrictions.append(Restriction(property=prop, kind=kind, n=n, filler=None))
