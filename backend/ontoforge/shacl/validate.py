"""Validation SHACL (pySHACL) → ShaclReport.

`validate(data, shapes, onto=None, data_format=None, inference="none")` :
- `data` : données RDF (str / bytes, ou rdflib.Graph déjà chargé) ;
- `shapes` : ShapesModel (exporté en graphe via export_shapes) ;
- `onto` : OntoModel (ou rdflib.Graph) **fusionné comme `ont_graph`** pySHACL : ses triplets (TBox :
  subClassOf, domain/range, subPropertyOf…) sont mélangés aux données avant l'inférence et la validation ;
- `inference` : "none" | "rdfs" | "owlrl" (| "both" = rdfs + owlrl, accepté par pySHACL).

Attention (piège documenté dans skills/shacl-modeling) : avec inférence, les triplets **entaillés**
sont validés aussi — p. ex. `sh:closed` échoue sur une super-propriété déduite par rdfs:subPropertyOf,
et `sh:class` / `sh:targetClass` voient les types déduits par rdfs:domain/range.
"""
from __future__ import annotations

from typing import Literal as TLiteral, Optional

import rdflib
from pydantic import BaseModel, Field
from rdflib import BNode, Literal, URIRef
from rdflib.namespace import OWL, RDF, RDFS

from ..core.onto_model import OntoModel
from ..core.shapes_model import ShapesModel
from .export_shapes import path_to_sparql, shapes_to_graph_with_ids
from .import_shapes import SH, encode_term, guess_format, iter_all_property_shapes

Inference = TLiteral["none", "rdfs", "owlrl", "both"]
SEVERITY_NAMES = {SH.Violation: "Violation", SH.Warning: "Warning", SH.Info: "Info"}


class ShaclResult(BaseModel):
    """Un résultat de validation (sh:ValidationResult). IRIs absolues ; littéraux encodés comme
    `import_shapes.encode_term` (forme lexicale ou N-Triples)."""
    focus: str
    path: Optional[str] = None  # IRI du prédicat, ou chemin SPARQL 1.1 (`^<…>`, `<a>/<b>`) si complexe
    severity: str = "Violation"  # Violation | Warning | Info
    constraint: str  # IRI du composant (http://www.w3.org/ns/shacl#MinCountConstraintComponent)
    message: Optional[str] = None
    value: Optional[str] = None
    shape: Optional[str] = None  # id de la shape source dans le ShapesModel (IRI ou `_:…`)


class ShaclReport(BaseModel):
    conforms: bool
    results: list[ShaclResult] = Field(default_factory=list)
    inference: str = "none"
    warnings: list[str] = Field(default_factory=list)  # problèmes d'entrée, shapes ignorées…
    text: str = ""  # rapport texte pySHACL (diagnostic)

    def counts(self) -> dict[str, int]:
        out = {"Violation": 0, "Warning": 0, "Info": 0}
        for r in self.results:
            out[r.severity] = out.get(r.severity, 0) + 1
        return out


def _load(data, fmt: Optional[str]) -> rdflib.Graph:
    if isinstance(data, rdflib.Graph):
        return data
    g = rdflib.Graph()
    g.parse(data=data, format=guess_format(data, fmt))
    return g


def onto_to_graph(onto: OntoModel) -> rdflib.Graph:
    """OntoModel → graphe pour ont_graph. Utilise io.rdf_export (w3c) s'il est disponible, sinon un
    export TBox minimal (types, subClassOf, domain/range, subPropertyOf, inverseOf, equivalentClass nommée,
    caractéristiques, individus et leurs faits) suffisant pour l'inférence RDFS / OWL-RL de base."""
    try:  # module du lot L1/L2 (w3c) — import paresseux pour ne pas dépendre de son état d'avancement
        from ..io.rdf_export import model_to_graph  # type: ignore
        return model_to_graph(onto)
    except Exception:  # noqa: BLE001
        pass
    g = rdflib.Graph()
    char = {"functional": OWL.FunctionalProperty, "inverseFunctional": OWL.InverseFunctionalProperty,
            "transitive": OWL.TransitiveProperty, "symmetric": OWL.SymmetricProperty,
            "asymmetric": OWL.AsymmetricProperty, "reflexive": OWL.ReflexiveProperty,
            "irreflexive": OWL.IrreflexiveProperty}
    for c in onto.classes.values():
        s = URIRef(c.iri)
        g.add((s, RDF.type, OWL.Class))
        for p in c.sub_class_of:
            g.add((s, RDFS.subClassOf, URIRef(p)))
        for e in c.equivalent_to:
            if e.op == "named" and e.iri:
                g.add((s, OWL.equivalentClass, URIRef(e.iri)))
        for d in c.disjoint_with:
            g.add((s, OWL.disjointWith, URIRef(d)))
    for coll, typ in ((onto.object_properties, OWL.ObjectProperty), (onto.datatype_properties, OWL.DatatypeProperty)):
        for p in coll.values():
            s = URIRef(p.iri)
            g.add((s, RDF.type, typ))
            for d in p.domain:
                g.add((s, RDFS.domain, URIRef(d)))
            for r in p.range:
                g.add((s, RDFS.range, URIRef(r)))
            for sp in p.sub_property_of:
                g.add((s, RDFS.subPropertyOf, URIRef(sp)))
            for eq in p.equivalent_to:
                g.add((s, OWL.equivalentProperty, URIRef(eq)))
    for p in onto.object_properties.values():
        s = URIRef(p.iri)
        if p.inverse_of:
            g.add((s, OWL.inverseOf, URIRef(p.inverse_of)))
        for ch in p.characteristics:
            g.add((s, RDF.type, char[ch]))
    for p in onto.datatype_properties.values():
        if p.functional:
            g.add((URIRef(p.iri), RDF.type, OWL.FunctionalProperty))
    for i in onto.individuals.values():
        s = URIRef(i.iri)
        for t in i.types:
            g.add((s, RDF.type, URIRef(t)))
        for f in i.facts:
            if f.negative:
                continue
            o = URIRef(f.value) if f.is_iri else Literal(f.value, lang=f.lang,
                                                           datatype=URIRef(f.datatype) if f.datatype else None)
            g.add((s, URIRef(f.property), o))
    return g


def validate(data: str | bytes | rdflib.Graph, shapes: ShapesModel, onto: OntoModel | rdflib.Graph | None = None,
             data_format: str | None = None, inference: str = "none") -> ShaclReport:
    """Valide `data` contre `shapes` avec pySHACL. Ne lève pas d'exception sur entrée invalide :
    renvoie `conforms=False` + warning."""
    import pyshacl  # import local : coût de chargement

    inf = (inference or "none").lower()
    if inf not in ("none", "rdfs", "owlrl", "both"):
        return ShaclReport(conforms=False, inference=inf,
                           warnings=[f"Inférence inconnue « {inference} » (attendu : none, rdfs, owlrl)."])
    warnings: list[str] = []
    try:
        dg = _load(data, data_format)
    except Exception as exc:  # noqa: BLE001
        return ShaclReport(conforms=False, inference=inf, warnings=[f"Données RDF illisibles : {exc}"])
    sg, node_ids = shapes_to_graph_with_ids(shapes)
    og = None
    if onto is not None:
        # TBox seulement : les individus de l'ontologie (ABox d'exemple) ne sont pas des données à valider
        # (ils produisaient un faux positif : op_oil_change typé PreventiveOperation sans inférence).
        og = onto if isinstance(onto, rdflib.Graph) else onto_to_graph(onto.model_copy(update={"individuals": {}}))
    if any(c.sparql for _, c in iter_all_property_shapes(shapes)) or any(s.sparql for s in shapes.shapes.values()):
        warnings.append("Des contraintes SHACL-SPARQL sont présentes : exécutées par pySHACL (advanced=False suffit "
                        "pour sh:sparql de SHACL-SPARQL).")
    try:
        conforms, results_graph, text = pyshacl.validate(
            dg, shacl_graph=sg, ont_graph=og, inference=None if inf == "none" else inf,
            abort_on_first=False, allow_warnings=False, allow_infos=False, advanced=False, inplace=False,
        )
    except Exception as exc:  # noqa: BLE001
        return ShaclReport(conforms=False, inference=inf, warnings=warnings + [f"Échec pySHACL : {exc}"])

    paths = {ps.id: ps.path for _, ps in iter_all_property_shapes(shapes)}
    results: list[ShaclResult] = []
    for r in results_graph.subjects(RDF.type, SH.ValidationResult):
        src = results_graph.value(r, SH.sourceShape)
        shape_id = node_ids.get(src) if src is not None else None
        if shape_id is None and src is not None:
            shape_id = str(src) if isinstance(src, URIRef) else None
        rp = results_graph.value(r, SH.resultPath)
        path: Optional[str] = None
        if shape_id in paths:
            p = paths[shape_id]
            path = p.iri if p.kind == "predicate" else path_to_sparql(p)
        elif isinstance(rp, URIRef):
            path = str(rp)
        msgs = {(m.language or ""): str(m) for m in results_graph.objects(r, SH.resultMessage)}
        try:
            from ..localize import ui_lang as _ui_lang
            _pref = _ui_lang()
        except Exception:  # réglages indisponibles
            _pref = "fr"
        message = msgs.get(_pref) or msgs.get("fr") or msgs.get("en") or msgs.get("") or (next(iter(msgs.values())) if msgs else None)
        val = results_graph.value(r, SH.value)
        sev = results_graph.value(r, SH.resultSeverity)
        focus = results_graph.value(r, SH.focusNode)
        results.append(ShaclResult(
            focus=encode_term(focus) if focus is not None else "",
            path=path,
            severity=SEVERITY_NAMES.get(sev, str(sev)),
            constraint=str(results_graph.value(r, SH.sourceConstraintComponent)),
            message=message,
            value=encode_term(val) if val is not None and not isinstance(val, BNode) else (
                "_:" if isinstance(val, BNode) else None),
            shape=shape_id,
        ))
    results.sort(key=lambda x: (x.focus, x.path or "", x.constraint, x.value or ""))
    return ShaclReport(conforms=bool(conforms), results=results, inference=inf, warnings=warnings, text=str(text))
