"""Interface de profil cible (lead) — adaptateur unique entre le moteur et `mapping/profiles/<cible>.py`.

Les profils sont écrits par les experts cibles (curiosity, neo4j) avec des signatures légèrement différentes.
Ce module les normalise derrière `Profile` et fournit un repli interne si un module manque ou casse
(le moteur ne doit jamais dépendre de l'état d'avancement d'un autre agent).

Ce que le moteur lit d'un profil :
- `cap(name)`            capacités de la plateforme (multi_label, edge_properties, native_reverse_edges, …) ;
- `node(local)`, `edge(local)`, `prop(local, lang=None)`, `reverse(edge_local, inverse_local, symmetric)` : nommage N01 ;
- `datatype(iri)`        -> (PGType, lossy, note) ;
- `rationale(rule_id)`   texte de justification fourni par l'expert cible (facultatif).

Les identifiants d'options ne viennent PAS des profils : le vocabulaire normatif est celui de
`samples/trap/expected-findings.yaml` (D-031), porté par `mapping/rules/`.
"""
from __future__ import annotations

import importlib
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

XSD = "http://www.w3.org/2001/XMLSchema#"
RDF = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
RDFS = "http://www.w3.org/2000/01/rdf-schema#"
OWL = "http://www.w3.org/2002/07/owl#"

# ------------------------------------------------------------------------------------------------
# Replis internes (utilisés seulement si le profil de l'expert manque ou lève une exception)
# ------------------------------------------------------------------------------------------------
_FALLBACK_TYPES: dict[str, tuple[str, bool, str]] = {
    XSD + "string": ("String", False, ""), XSD + "normalizedString": ("String", False, ""),
    XSD + "token": ("String", False, ""), XSD + "language": ("String", False, ""),
    XSD + "Name": ("String", False, ""), XSD + "NCName": ("String", False, ""), XSD + "NMTOKEN": ("String", False, ""),
    XSD + "anyURI": ("String", False, ""), XSD + "boolean": ("Boolean", False, ""),
    XSD + "decimal": ("Float", True, "décimal exact → flottant"), OWL + "real": ("Float", True, ""),
    OWL + "rational": ("Float", True, ""), XSD + "double": ("Float", False, ""), XSD + "float": ("Float", False, ""),
    XSD + "integer": ("Integer", True, "entier non borné → 64 bits"), XSD + "long": ("Integer", False, ""),
    XSD + "int": ("Integer", False, ""), XSD + "short": ("Integer", False, ""), XSD + "byte": ("Integer", False, ""),
    XSD + "nonNegativeInteger": ("Integer", True, ""), XSD + "positiveInteger": ("Integer", True, ""),
    XSD + "nonPositiveInteger": ("Integer", True, ""), XSD + "negativeInteger": ("Integer", True, ""),
    XSD + "unsignedLong": ("Integer", True, ""), XSD + "unsignedInt": ("Integer", False, ""),
    XSD + "unsignedShort": ("Integer", False, ""), XSD + "unsignedByte": ("Integer", False, ""),
    XSD + "hexBinary": ("String", True, "binaire en texte"), XSD + "base64Binary": ("String", True, "binaire en texte"),
    XSD + "dateTime": ("DateTime", False, ""), XSD + "dateTimeStamp": ("DateTime", False, ""),
    XSD + "date": ("Date", True, ""), XSD + "time": ("Time", True, ""), XSD + "duration": ("Duration", True, ""),
    XSD + "gYear": ("Integer", True, ""), XSD + "gYearMonth": ("String", True, ""),
    RDF + "PlainLiteral": ("String", True, "langue perdue"), RDF + "langString": ("String", True, "langue perdue"),
    RDF + "XMLLiteral": ("String", True, ""), RDFS + "Literal": ("String", True, "type inconnu"),
}


def _words(local: str) -> list[str]:
    s = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", local or "")
    s = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1 \2", s)
    return [w for w in re.split(r"[^A-Za-z0-9]+", s) if w]


def _pascal(local: str) -> str:
    chunks = [c for c in re.split(r"[^0-9A-Za-z]+", local or "") if c]
    out = "".join(c[0].upper() + c[1:] for c in chunks) or "Unnamed"
    return "N" + out if out[0].isdigit() else out


def _camel(local: str, lang: Optional[str] = None) -> str:
    ws = _words(local) or ["value"]
    out = ws[0][:1].lower() + ws[0][1:] + "".join(w[:1].upper() + w[1:] for w in ws[1:])
    if out[0].isdigit():
        out = "p" + out
    return out + (f"_{lang.lower().replace('-', '_')}" if lang else "")


def _upper_snake(local: str) -> str:
    out = "_".join(w.upper() for w in _words(local)) or "RELATED_TO"
    return "R_" + out if out[0].isdigit() else out


def _fallback_reverse(edge_local: str, inverse_local: Optional[str], symmetric: bool) -> str:
    e = _pascal(edge_local)
    if symmetric:
        return e
    if inverse_local:
        return _pascal(inverse_local)
    m = re.fullmatch(r"Has([A-Z0-9].*)", e)
    if m:
        return f"{m.group(1)}Of"
    m = re.fullmatch(r"Is([A-Z0-9].*)Of", e)
    if m:
        return f"Has{m.group(1)}"
    return f"{e}Inverse"


# ------------------------------------------------------------------------------------------------
@dataclass
class Profile:
    target: str
    capabilities: dict[str, Any] = field(default_factory=dict)
    _node: Callable[[str], str] = _pascal
    _edge: Callable[[str], str] = _pascal
    _prop: Callable[[str, Optional[str]], str] = lambda l, lang=None: _camel(l, lang)
    _reverse: Callable[[str, Optional[str], bool], Optional[str]] = _fallback_reverse
    _datatype: Callable[[Optional[str]], tuple[str, bool, str]] = lambda i: _FALLBACK_TYPES.get(i or RDFS + "Literal", ("String", True, "type inconnu"))
    _rationales: dict[str, str] = field(default_factory=dict)
    source: str = "fallback"  # nom du module effectivement utilisé
    warnings: list[str] = field(default_factory=list)

    # -- capacités --------------------------------------------------------------------------------
    def cap(self, name: str, default: Any = None) -> Any:
        return self.capabilities.get(name, default)

    @property
    def multi_label(self) -> bool:
        return bool(self.cap("multi_label", self.target == "neo4j"))

    @property
    def edge_properties(self) -> bool:
        return bool(self.cap("edge_properties", self.target == "neo4j"))

    @property
    def native_reverse(self) -> bool:
        return bool(self.cap("native_reverse_edges", self.target == "curiosity"))

    # -- nommage ----------------------------------------------------------------------------------
    def _safe(self, fn: Callable, fallback: Callable, *args) -> Any:
        try:
            out = fn(*args)
            if out:
                return out
        except Exception as exc:  # profil d'un autre agent en cours d'écriture
            msg = f"profil {self.target} : {getattr(fn, '__name__', fn)} a levé {exc!r}, repli interne"
            if msg not in self.warnings:
                self.warnings.append(msg)
        return fallback(*args)

    def node(self, local: str) -> str:
        return self._safe(self._node, _pascal, local)

    def edge(self, local: str) -> str:
        return self._safe(self._edge, _pascal if self.target == "curiosity" else _upper_snake, local)

    def prop(self, local: str, lang: Optional[str] = None) -> str:
        fb = (lambda l, g=None: _pascal(l) + (_pascal(g) if g else "")) if self.target == "curiosity" else _camel
        return self._safe(self._prop, fb, local, lang)

    def reverse(self, edge_local: str, inverse_local: Optional[str] = None, symmetric: bool = False) -> Optional[str]:
        if self.target != "curiosity":
            return None
        return self._safe(self._reverse, _fallback_reverse, edge_local, inverse_local, symmetric)

    def datatype(self, iri: Optional[str]) -> tuple[str, bool, str]:
        try:
            t = self._datatype(iri)
            if t and t[0]:
                return t
        except Exception:
            pass
        return _FALLBACK_TYPES.get(iri or RDFS + "Literal", ("String", True, "type inconnu"))

    def rationale(self, rule: str) -> str:
        return self._rationales.get(rule, "")


# ------------------------------------------------------------------------------------------------
def _curiosity(mod) -> Profile:
    def prop(local, lang=None):
        if lang:
            return mod.lang_prop_name(local, lang)
        return mod.prop_name(local)

    def reverse(edge_local, inverse_local, symmetric):
        return mod.reverse_name(edge_local, inverse_local, symmetric=symmetric)

    return Profile(
        target="curiosity", capabilities=dict(getattr(mod, "CAPABILITIES", {})),
        _node=mod.node_name, _edge=mod.edge_name, _prop=prop, _reverse=reverse,
        _datatype=lambda i: tuple(mod.map_datatype(i)),
        _rationales={k: v.get("rationale", "") for k, v in getattr(mod, "RECOMMENDATIONS", {}).items()
                     if isinstance(v, dict)},
        source=mod.__name__,
    )


def _neo4j(mod) -> Profile:
    def dt(i):
        d = mod.map_xsd(i)
        return (d["type"], bool(d.get("lossy")), d.get("note", ""))

    return Profile(
        target="neo4j", capabilities=dict(getattr(mod, "CAPABILITIES", {})),
        _node=mod.node_name, _edge=mod.edge_name, _prop=lambda l, lang=None: mod.prop_name(l, lang),
        _reverse=lambda e, i, s: None, _datatype=dt,
        _rationales={k: v.get("rationale", "") for k, v in getattr(mod, "RECOMMENDATIONS", {}).items()
                     if isinstance(v, dict)},
        source=mod.__name__,
    )


_FALLBACK_CAPS = {
    "curiosity": {"multi_label": False, "edge_properties": False, "native_reverse_edges": True,
                  "single_string_key": True, "composite_key": False},
    "neo4j": {"multi_label": True, "edge_properties": True, "native_reverse_edges": False,
              "single_string_key": False, "composite_key": True},
}


def get_profile(target: str) -> Profile:
    """Profil normalisé pour `target` ; repli interne si `mapping/profiles/<target>.py` est absent ou cassé."""
    if target not in ("curiosity", "neo4j"):
        raise ValueError(f"cible inconnue : {target}")
    try:
        mod = importlib.import_module(f"ontoforge.mapping.profiles.{target}")
        return _curiosity(mod) if target == "curiosity" else _neo4j(mod)
    except Exception as exc:
        prof = Profile(target=target, capabilities=dict(_FALLBACK_CAPS[target]))
        if target == "neo4j":
            prof._edge = _upper_snake
        else:
            prof._prop = lambda l, lang=None: _pascal(l) + (_pascal(lang) if lang else "")
        prof.warnings.append(f"profil {target} indisponible ({exc!r}) : repli interne")
        return prof
