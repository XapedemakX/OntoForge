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

import json
import os
import subprocess
import sys
import threading
from pathlib import Path
from typing import Literal as TLiteral, Optional

import rdflib
from pydantic import BaseModel, Field
from rdflib import BNode, Literal, URIRef
from rdflib.namespace import OWL, RDF, RDFS

from .. import childproc
from ..core.onto_model import OntoModel
from ..core.shapes_model import ShapesModel
from ..io.safe_parse import parse_into
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
    parse_into(g, data, guess_format(data, fmt))
    return g


# ---- exécution isolée (SEC-05) ----------------------------------------------------------------------------------------
WORKER = Path(__file__).with_name("_worker.py")


class ShaclLimitError(Exception):
    """Validation interrompue (délai, mémoire ou temps CPU) : message destiné à l'utilisateur."""


def _env_num(name: str, default: float) -> float:
    try:
        return max(1.0, float(os.environ.get(name, default)))
    except ValueError:
        return default


class _SameLabels(dict):
    """Contexte de nœuds blancs du lecteur N-Triples : conserve les étiquettes (identifiants de shapes, nœuds des rapports)."""

    def get(self, key, default=None):
        return key


def _parse_nt(g: rdflib.Graph, text: str) -> None:
    from rdflib.plugins.parsers.ntriples import NTGraphSink, W3CNTriplesParser
    W3CNTriplesParser(NTGraphSink(g)).parsestring(text, bnode_context=_SameLabels())


def _nt(g: Optional[rdflib.Graph]) -> Optional[str]:
    return None if g is None else g.serialize(format="nt")


class ShaclBusyError(Exception):
    """Trop de validations simultanées (plafond ``ONTOFORGE_SHACL_SLOTS``) : l'API répond 503 avec ``Retry-After`` (L39-01)."""

    retry_after = 5


def _slot_count() -> int:
    try:
        return max(1, min(32, int(os.environ.get("ONTOFORGE_SHACL_SLOTS", "2"))))
    except ValueError:
        return 2


_SLOTS = threading.BoundedSemaphore(_slot_count())  # comme conformance/hermit.py : un fils peut prendre 2 Go, donc peu de fils à la fois


def _run_isolated(dg: rdflib.Graph, sg: rdflib.Graph, og: Optional[rdflib.Graph], inf: str):
    """pySHACL dans un processus fils : délai, mémoire et CPU plafonnés (ONTOFORGE_SHACL_TIMEOUT_S = 30, ONTOFORGE_SHACL_MEMORY_MB = 2048),
    au plus ONTOFORGE_SHACL_SLOTS (2) validations en même temps ; ``ShaclBusyError`` si tous les créneaux sont pris (L41)."""
    if not _SLOTS.acquire(blocking=False):
        raise ShaclBusyError("Trop de validations SHACL en cours : réessayez dans quelques secondes.")
    try:
        return _run_isolated_locked(dg, sg, og, inf)
    finally:
        _SLOTS.release()


def _run_isolated_locked(dg: rdflib.Graph, sg: rdflib.Graph, og: Optional[rdflib.Graph], inf: str):
    timeout = _env_num("ONTOFORGE_SHACL_TIMEOUT_S", 30)
    mem = int(_env_num("ONTOFORGE_SHACL_MEMORY_MB", 2048))
    payload = json.dumps({"data": _nt(dg), "shapes": _nt(sg), "ont": _nt(og), "inference": inf}).encode("utf-8")
    try:
        proc = childproc.run_limited(WORKER, payload, timeout=timeout, mem_mb=mem, cpu_s=int(timeout) + 2, fsize=0)
    except subprocess.TimeoutExpired:
        raise ShaclLimitError(f"Validation interrompue : délai de {timeout:.0f} s dépassé. Une contrainte (par exemple un sh:pattern trop coûteux) "
                              "ou le volume de données est trop lourd ; simplifiez l'expression régulière ou réduisez les données.") from None
    if proc.returncode != 0 or not proc.stdout:
        if proc.returncode < 0 or b"MemoryError" in proc.stderr:
            raise ShaclLimitError("Validation interrompue : mémoire ou temps de calcul plafonnés. Une contrainte (par exemple un sh:pattern trop coûteux) "
                                  "ou le volume de données est trop lourd.")
        tail = (proc.stderr.decode("utf-8", "replace").strip().splitlines() or ["erreur inconnue"])[-1][:300]
        raise RuntimeError(tail)
    out = json.loads(proc.stdout)
    rg = rdflib.Graph()
    _parse_nt(rg, out["results"])
    return out["conforms"], rg, out["text"]


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
        conforms, results_graph, text = _run_isolated(dg, sg, og, inf)
    except ShaclBusyError:
        raise  # remonte jusqu'à l'API (503 + Retry-After) : ce n'est pas un échec de la validation
    except ShaclLimitError as exc:
        return ShaclReport(conforms=False, inference=inf, warnings=warnings + [str(exc)])
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
