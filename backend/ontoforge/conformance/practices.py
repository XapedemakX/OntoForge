"""Bonnes pratiques d'ontologie (L49) : fiche complète, dépréciation, version sémantique, métadonnées d'en-tête.

Règles BP08 à BP16, toutes « info » ou « warning », jamais bloquantes (elles ne touchent ni au profil DL ni à la génération).
Vocabulaires retenus (justification : docs/CONTRACTS.md §19, D-L49-01) :
- définition : ``skos:definition`` (SKOS Reference §7) ou ``rdfs:comment`` (RDF Schema 1.1 §3.7, OWL 2 SS §5.5) ;
- libellés : ``rdfs:label`` (SS §5.5) ou ``skos:prefLabel`` (SKOS §5, sous-propriété de rdfs:label), en fr et en ;
- auteur, contributeur, source, remplaçant, en-tête : DCMI Metadata Terms (``dcterms:*``, ``dc:*`` accepté en lecture) ;
- statut de revue : ``vs:term_status`` (W3C Semantic Web Vocabulary Status), valeurs ``unstable | testing | stable | archaic`` ;
- justification d'une caractéristique de propriété : ``skos:note`` ou une de ses sous-propriétés (SKOS §7 : editorialNote,
  scopeNote, changeNote, historyNote) ; OntoForge écrit ``skos:editorialNote`` ;
- dépréciation : ``owl:deprecated true`` (SS §5.5) + ``dcterms:isReplacedBy`` ;
- version : ``owl:versionInfo`` au format SemVer 2.0.0, ``owl:versionIRI`` distincte de l'IRI d'ontologie (SS §3.1, §3.3),
  ``owl:priorVersion`` vers la version précédente (SS §5.5).
"""
from __future__ import annotations

import re
from urllib.parse import urlsplit
from typing import Any, Iterable, Optional

from ..core.onto_model import OWL, RDFS, Annotation, Entity, OntoModel, local_name
from .report import Issue

SKOS = "http://www.w3.org/2004/02/skos/core#"
DCT = "http://purl.org/dc/terms/"
DC = "http://purl.org/dc/elements/1.1/"
VS = "http://www.w3.org/2003/06/sw-vocab-status/ns#"

SKOS_DEFINITION = SKOS + "definition"
SKOS_PREFLABEL = SKOS + "prefLabel"
SKOS_NOTE = SKOS + "note"
SKOS_EDITORIAL = SKOS + "editorialNote"
NOTE_PROPS = {SKOS_NOTE, SKOS_EDITORIAL, SKOS + "scopeNote", SKOS + "changeNote", SKOS + "historyNote"}
VS_STATUS = VS + "term_status"
STATUS_VALUES = ("unstable", "testing", "stable", "archaic")
IS_REPLACED_BY = DCT + "isReplacedBy"
VERSION_INFO = OWL + "versionInfo"
PRIOR_VERSION = OWL + "priorVersion"

LANGS = ("fr", "en")

# Semantic Versioning 2.0.0, expression régulière officielle (semver.org, FAQ).
SEMVER_RE = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-((?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?"
    r"(?:\+([0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?$")
# Segment de version dans un espace de noms : /1.2/, /v2/, /2.0.1#, /v1.0/ …
VERSION_SEGMENT_RE = re.compile(r"/(?:v\d+(?:\.\d+){0,2}|\d+\.\d+(?:\.\d+)?)(?=[/#]|$)", re.I)

# Champs de l'en-tête d'ontologie (métadonnées éditables, exportées) : clé → (propriété, valeur IRI ?, multivalué ?, par langue ?)
HEADER_FIELDS: dict[str, tuple[str, bool, bool, bool]] = {
    "title": (DCT + "title", False, False, True),
    "description": (DCT + "description", False, False, True),
    "version_info": (VERSION_INFO, False, False, False),
    "created": (DCT + "created", False, False, False),
    "modified": (DCT + "modified", False, False, False),
    "creators": (DCT + "creator", False, True, False),
    "contributors": (DCT + "contributor", False, True, False),
    "references": (DCT + "references", True, True, False),
    "subjects": (DCT + "subject", False, True, True),
    "sources": (DCT + "source", False, True, False),
    "license": (DCT + "license", True, False, False),
    "prior_version": (PRIOR_VERSION, True, False, False),
}
# Champs dont l'absence est signalée par BP16 (le reste est facultatif).
HEADER_EXPECTED = ("title", "description", "creators", "license", "created", "modified")

# Annotations qu'un éditeur peut écrire par l'opération set_annotations (liste fermée : pas d'écriture de vocabulaire réservé).
WRITABLE = {SKOS_DEFINITION, SKOS_PREFLABEL, SKOS_NOTE, SKOS_EDITORIAL, SKOS + "scopeNote", SKOS + "changeNote",
            SKOS + "historyNote", SKOS + "example", VS_STATUS, IS_REPLACED_BY, DCT + "replaces"} | {
    v[0] for v in HEADER_FIELDS.values()}
# Propriétés à valeur IRI parmi les écrivables (les autres : littéraux, avec langue pour les textes).
IRI_VALUED = {IS_REPLACED_BY, DCT + "replaces", DCT + "references", DCT + "license", PRIOR_VERSION}

_EXTERNAL = ("http://www.w3.org/1999/02/22-rdf-syntax-ns#", "http://www.w3.org/2000/01/rdf-schema#", OWL,
             "http://www.w3.org/2001/XMLSchema#", SKOS, DCT, DC, VS, "http://xmlns.com/foaf/0.1/", "http://www.w3.org/ns/prov#",
             "http://www.w3.org/ns/shacl#", "https://schema.org/", "http://schema.org/", "http://purl.org/vocab/vann/")

KIND_FR = {"class": "Classe", "objectProperty": "Propriété objet", "datatypeProperty": "Propriété de données"}
CRITERIA = ("label_fr", "label_en", "definition", "creator", "source", "status", "justification")


def is_external(iri: str) -> bool:
    return iri.startswith(_EXTERNAL)


def values(e: Entity, *props: str) -> list[Annotation]:
    return [a for a in e.annotations if a.property in props]


def has_label(e: Entity, lang: str) -> bool:
    return bool(e.labels.get(lang, "").strip()) or any(a.lang == lang and a.value.strip() for a in values(e, SKOS_PREFLABEL))


def has_definition(e: Entity) -> bool:
    return any(v.strip() for v in e.comments.values()) or any(a.value.strip() for a in values(e, SKOS_DEFINITION))


def status_of(e: Entity) -> Optional[str]:
    v = values(e, VS_STATUS)
    return v[0].value.strip() if v else None


def replaced_by(e: Entity) -> list[str]:
    return [a.value for a in values(e, IS_REPLACED_BY)]


def entities(onto: OntoModel) -> Iterable[tuple[str, Entity]]:
    """Classes et propriétés de l'ontologie (vocabulaires réutilisés exclus) : les entités qui ont une fiche."""
    for kind, coll in (("class", onto.classes), ("objectProperty", onto.object_properties),
                       ("datatypeProperty", onto.datatype_properties)):
        for iri in sorted(coll):
            if not is_external(iri):
                yield kind, coll[iri]


def _has_characteristics(kind: str, e: Any) -> bool:
    if kind == "objectProperty":
        return bool(e.characteristics)
    if kind == "datatypeProperty":
        return bool(e.functional)
    return False


def entity_card(kind: str, e: Any) -> dict[str, Any]:
    """Fiche d'une entité : critères remplis, manquants, score 0–100 (critères applicables seulement)."""
    crit: dict[str, bool] = {
        "label_fr": has_label(e, "fr"), "label_en": has_label(e, "en"), "definition": has_definition(e),
        "creator": bool(values(e, DCT + "creator", DC + "creator")), "source": bool(values(e, DCT + "source", DC + "source")),
        "status": status_of(e) is not None,
    }
    if _has_characteristics(kind, e):
        crit["justification"] = bool(values(e, *NOTE_PROPS))
    ok = sum(crit.values())
    return {"iri": e.iri, "kind": kind, "criteria": crit, "missing": [k for k, v in crit.items() if not v],
            "score": round(100 * ok / len(crit)), "deprecated": e.deprecated, "replaced_by": replaced_by(e),
            "status": status_of(e)}


def header(onto: OntoModel) -> dict[str, Any]:
    """En-tête de l'ontologie, champ par champ (lecture structurée de ``meta.annotations``)."""
    m = onto.meta
    out: dict[str, Any] = {"iri": m.iri, "version_iri": m.version_iri, "imports": list(m.imports)}
    for key, (prop, _iri, multi, by_lang) in HEADER_FIELDS.items():
        anns = values(m, prop) + (values(m, DC + prop[len(DCT):]) if prop.startswith(DCT) else [])
        if by_lang and not multi:
            out[key] = {a.lang or "": a.value for a in anns}
        elif by_lang:
            out[key] = [{"value": a.value, "lang": a.lang or ""} for a in anns]
        elif multi:
            out[key] = [a.value for a in anns]
        else:
            out[key] = anns[0].value if anns else None
    if not out["title"] and m.labels:
        out["title_from_label"] = dict(m.labels)
    return out


def header_card(onto: OntoModel) -> dict[str, Any]:
    h = header(onto)
    crit = {k: bool(h.get(k)) for k in HEADER_EXPECTED}
    crit["version_info"] = bool(h.get("version_info")) and bool(SEMVER_RE.match(h["version_info"] or ""))
    crit["version_iri"] = bool(onto.meta.version_iri) and onto.meta.version_iri != onto.meta.iri
    ok = sum(crit.values())
    return {"criteria": crit, "missing": [k for k, v in crit.items() if not v], "score": round(100 * ok / len(crit))}


def completeness(onto: OntoModel) -> dict[str, Any]:
    """Score de complétude par entité et pour l'ontologie (moyenne des fiches), plus celui de l'en-tête."""
    cards = [entity_card(k, e) for k, e in entities(onto)]
    score = round(sum(c["score"] for c in cards) / len(cards)) if cards else 100
    by_crit = {k: sum(1 for c in cards if c["criteria"].get(k)) for k in CRITERIA}
    applicable = {k: sum(1 for c in cards if k in c["criteria"]) for k in CRITERIA}
    return {"score": score, "entities": {c["iri"]: c for c in cards}, "header": header_card(onto),
            "criteria": {k: {"ok": by_crit[k], "of": applicable[k]} for k in CRITERIA if applicable[k]},
            "deprecated": sorted(c["iri"] for c in cards if c["deprecated"])}


def _label(kind: str, e: Entity) -> str:
    return f"{KIND_FR[kind]} {local_name(e.iri)}"


def lint(onto: OntoModel) -> list[Issue]:
    """Constats BP08 à BP16 (bonnes pratiques, jamais des erreurs)."""
    out: list[Issue] = []
    ents = list(entities(onto))
    known = {e.iri: e for _, e in ents}
    for coll in (onto.individuals, onto.annotation_properties, onto.datatypes):
        known.update({k: v for k, v in coll.items() if k not in known})

    # BP08 définition
    for kind, e in ents:
        if not has_definition(e):
            out.append(Issue(level="info", code="BP08", subject=e.iri, spec_ref="SKOS Reference §7 (skos:definition) ; OWL 2 SS §5.5 (rdfs:comment)",
                             message=f"{_label(kind, e)} : définition manquante (skos:definition ou rdfs:comment)."))
    # BP09 auteur, source, statut (regroupé quand aucune entité ne les porte : une ligne au lieu de N)
    missing = []
    for kind, e in ents:
        card = entity_card(kind, e)
        miss = [m for m in ("creator", "source", "status") if m in card["missing"]]
        if miss:
            missing.append((kind, e, miss))
    names = {"creator": "auteur (dcterms:creator)", "source": "source (dcterms:source)", "status": "statut (vs:term_status)"}
    ref9 = "DCMI Metadata Terms (dcterms:creator, dcterms:source) ; W3C Vocabulary Status (vs:term_status)"
    if ents and len(missing) == len(ents) and all(len(m[2]) == 3 for m in missing):
        out.append(Issue(level="info", code="BP09", subject=onto.meta.iri or None, spec_ref=ref9,
                         message=f"Aucune des {len(ents)} entités n'a d'auteur, de source ni de statut de revue : fiches à compléter."))
    else:
        for kind, e, miss in missing:
            out.append(Issue(level="info", code="BP09", subject=e.iri, spec_ref=ref9,
                             message=f"{_label(kind, e)} : fiche incomplète, manque " + ", ".join(names[m] for m in miss) + "."))
    # BP10 statut hors vocabulaire
    for kind, e in ents:
        for a in values(e, VS_STATUS):
            if a.value.strip() not in STATUS_VALUES:
                out.append(Issue(level="warning", code="BP10", subject=e.iri, spec_ref="W3C Vocabulary Status (vs:term_status)",
                                 message=f"{_label(kind, e)} : statut « {a.value} » inconnu ; valeurs attendues : {', '.join(STATUS_VALUES)}."))
        if e.deprecated and status_of(e) in ("stable", "testing"):
            out.append(Issue(level="warning", code="BP10", subject=e.iri, spec_ref="OWL 2 SS §5.5 (owl:deprecated) ; W3C Vocabulary Status",
                             message=f"{_label(kind, e)} : dépréciée mais de statut « {status_of(e)} » ; statut attendu : archaic."))
    # BP11 caractéristiques non justifiées
    for kind, e in ents:
        if _has_characteristics(kind, e) and not values(e, *NOTE_PROPS):
            chars = ", ".join(e.characteristics) if kind == "objectProperty" else "functional"
            out.append(Issue(level="info", code="BP11", subject=e.iri, spec_ref="SKOS Reference §7 (skos:note, skos:editorialNote)",
                             message=f"{_label(kind, e)} : caractéristiques ({chars}) sans justification (skos:editorialNote)."))
    # BP12 dépréciation : remplaçant absent, inconnu ou lui-même déprécié
    for kind, e in ents:
        reps = replaced_by(e)
        if e.deprecated and not reps:
            out.append(Issue(level="info", code="BP12", subject=e.iri, spec_ref="OWL 2 SS §5.5 (owl:deprecated) ; DCMI Metadata Terms (dcterms:isReplacedBy)",
                             message=f"{_label(kind, e)} : dépréciée sans remplaçant (dcterms:isReplacedBy)."))
        for r in reps:
            if r == e.iri:
                out.append(Issue(level="warning", code="BP12", subject=e.iri, spec_ref="DCMI Metadata Terms (dcterms:isReplacedBy)",
                                 message=f"{_label(kind, e)} : se désigne elle-même comme remplaçante."))
            elif r in known and known[r].deprecated:
                out.append(Issue(level="warning", code="BP12", subject=e.iri, spec_ref="DCMI Metadata Terms (dcterms:isReplacedBy)",
                                 message=f"{_label(kind, e)} : remplacée par {local_name(r)}, elle aussi dépréciée."))
            elif r not in known and not is_external(r) and r.startswith(_ns(e.iri)):
                out.append(Issue(level="warning", code="BP12", subject=e.iri, spec_ref="DCMI Metadata Terms (dcterms:isReplacedBy)",
                                 message=f"{_label(kind, e)} : remplaçant {local_name(r)} introuvable dans l'ontologie."))
        if reps and not e.deprecated:
            out.append(Issue(level="info", code="BP12", subject=e.iri, spec_ref="OWL 2 SS §5.5 (owl:deprecated)",
                             message=f"{_label(kind, e)} : a un remplaçant mais n'est pas marquée owl:deprecated."))
    # BP13 entité dépréciée encore utilisée (domaine, portée, restriction) ; le parent déprécié reste BP06
    dep = {iri for iri, e in known.items() if e.deprecated}
    if dep:
        for kind, e in ents:
            if e.deprecated or kind == "class":
                continue
            used = [x for x in list(e.domain) + list(getattr(e, "range", [])) if x in dep]
            for x in dict.fromkeys(used):
                out.append(Issue(level="warning", code="BP13", subject=e.iri, spec_ref="OWL 2 SS §5.5 (owl:deprecated)",
                                 message=f"{_label(kind, e)} : domaine ou portée {local_name(x)}, qui est dépréciée."))
        for c in onto.classes.values():
            if c.deprecated:
                continue
            for r in c.restrictions:
                for x in (r.property, r.filler):
                    if x and x in dep:
                        out.append(Issue(level="warning", code="BP13", subject=c.iri, spec_ref="OWL 2 SS §5.5 (owl:deprecated)",
                                         message=f"Classe {local_name(c.iri)} : restriction sur {local_name(x)}, qui est dépréciée."))
    # BP14 owl:versionInfo au format SemVer
    m = onto.meta
    vi = [a.value for a in values(m, VERSION_INFO)]
    if not vi:
        out.append(Issue(level="warning", code="BP14", subject=m.iri or None, spec_ref="OWL 2 SS §5.5 (owl:versionInfo) ; Semantic Versioning 2.0.0",
                         message="L'ontologie n'a pas d'owl:versionInfo : indiquez une version au format MAJEUR.MINEUR.CORRECTIF (ex. 1.0.0)."))
    for v in vi:
        if not SEMVER_RE.match(v.strip()):
            out.append(Issue(level="warning", code="BP14", subject=m.iri or None, spec_ref="Semantic Versioning 2.0.0",
                             message=f"owl:versionInfo « {v} » n'est pas au format SemVer MAJEUR.MINEUR.CORRECTIF (ex. 1.2.0)."))
    # BP15 versionIRI distincte, espace de noms sans version
    if m.version_iri and m.version_iri == m.iri:
        out.append(Issue(level="warning", code="BP15", subject=m.iri, spec_ref="OWL 2 SS §3.1, §3.3 (owl:versionIRI)",
                         message="owl:versionIRI est égale à l'IRI de l'ontologie : elle doit désigner la version (ex. …/onto/1.2.0)."))
    spaces = sorted({_ns(e.iri) for _, e in ents} | ({_ns(m.iri)} if m.iri else set()))
    for ns in spaces:
        if ns and VERSION_SEGMENT_RE.search(urlsplit(ns).path):
            out.append(Issue(level="warning", code="BP15", subject=ns, spec_ref="OWL 2 SS §3.3 (versionnement)",
                             message=f"L'espace de noms {ns} contient un numéro de version : les IRI des termes changeraient à chaque version. "
                                     "Gardez la version dans owl:versionIRI et owl:versionInfo."))
    # BP16 en-tête incomplet
    hc = header_card(onto)
    miss = [k for k in HEADER_EXPECTED if k in hc["missing"]]
    if miss:
        fr = {"title": "titre (dcterms:title)", "description": "objectif (dcterms:description)", "creators": "auteurs (dcterms:creator)",
              "license": "licence (dcterms:license)", "created": "date de création (dcterms:created)", "modified": "date de modification (dcterms:modified)"}
        out.append(Issue(level="info", code="BP16", subject=m.iri or None, spec_ref="DCMI Metadata Terms ; OWL 2 SS §3.5 (annotations d'ontologie)",
                         message="En-tête de l'ontologie incomplet, manque : " + ", ".join(fr[k] for k in miss) + "."))
    return out


def _ns(iri: Optional[str]) -> str:
    if not iri:
        return ""
    for sep in ("#", "/"):
        if sep in iri:
            return iri.rsplit(sep, 1)[0] + sep
    return iri
