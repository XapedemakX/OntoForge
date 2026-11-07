"""Fournisseur mock : réponses déterministes réalistes (domaine automobile), sans réseau."""
from __future__ import annotations

import json
import re
from typing import Any, Optional

from ..texts import fallback_explain

AUTOMOTIVE: dict[str, Any] = {
    "ontology": {"label_fr": "Maintenance automobile", "label_en": "Car maintenance",
                 "comment": "Ontologie de maintenance automobile : véhicules, propriétaires, ordres de réparation et pièces.",
                 "comment_en": "Car maintenance ontology: vehicles, owners, repair orders and parts."},
    "classes": [
        {"name": "Vehicle", "label_fr": "Véhicule", "label_en": "Vehicle", "comment": "Véhicule routier identifié par son VIN.",
         "comment_en": "Road vehicle identified by its VIN.", "key": ["vin"]},
        {"name": "Car", "label_fr": "Voiture", "label_en": "Car", "parent": "Vehicle", "disjoint_with": ["Truck"]},
        {"name": "Truck", "label_fr": "Camion", "label_en": "Truck", "parent": "Vehicle"},
        {"name": "Person", "label_fr": "Personne", "label_en": "Person", "close_match": "https://schema.org/Person"},
        {"name": "Owner", "label_fr": "Propriétaire", "label_en": "Owner", "parent": "Person"},
        {"name": "Technician", "label_fr": "Technicien", "label_en": "Technician", "parent": "Person"},
        {"name": "RepairOrder", "label_fr": "Ordre de réparation", "label_en": "Repair order",
         "comment": "Intervention sur un véhicule.",
         "comment_en": "Work carried out on a vehicle.", "key": ["orderNumber"]},
        {"name": "Part", "label_fr": "Pièce", "label_en": "Part", "key": ["partNumber"]},
    ],
    "object_properties": [
        {"name": "ownedBy", "label_fr": "appartient à", "label_en": "owned by", "domain": "Vehicle", "range": "Owner", "functional": True, "inverse": "owns"},
        {"name": "concernsVehicle", "label_fr": "concerne le véhicule", "label_en": "concerns vehicle", "domain": "RepairOrder", "range": "Vehicle", "functional": True, "required": True},
        {"name": "assignedTo", "label_fr": "affecté à", "label_en": "assigned to", "domain": "RepairOrder", "range": "Technician"},
        {"name": "usesPart", "label_fr": "utilise la pièce", "label_en": "uses part", "domain": "RepairOrder", "range": "Part"},
    ],
    "datatype_properties": [
        {"name": "vin", "label_fr": "numéro VIN", "label_en": "VIN", "domain": "Vehicle", "range": "string", "functional": True, "required": True},
        {"name": "mileage", "label_fr": "kilométrage", "label_en": "mileage", "domain": "Vehicle", "range": "integer", "functional": True},
        {"name": "registrationDate", "label_fr": "date d'immatriculation", "label_en": "registration date", "domain": "Vehicle", "range": "date", "functional": True},
        {"name": "name", "label_fr": "nom", "label_en": "name", "domain": "Person", "range": "string", "required": True},
        {"name": "orderNumber", "label_fr": "numéro d'ordre", "label_en": "order number", "domain": "RepairOrder", "range": "string", "functional": True, "required": True},
        {"name": "openedAt", "label_fr": "ouvert le", "label_en": "opened at", "domain": "RepairOrder", "range": "dateTime", "functional": True},
        {"name": "partNumber", "label_fr": "référence", "label_en": "part number", "domain": "Part", "range": "string", "functional": True, "required": True},
        {"name": "unitPrice", "label_fr": "prix unitaire", "label_en": "unit price", "domain": "Part", "range": "decimal", "functional": True},
    ],
    "explanation": "Modèle minimal pour répondre à : quels véhicules, quels propriétaires, quelles interventions et quelles pièces ? "
                   "Person est réutilisée comme close match de schema.org/Person ; Owner et Technician sont des rôles modélisés en sous-classes "
                   "(à remplacer par une classe de rôle si une même personne cumule les rôles).",
    "warnings": ["Le rôle Owner/Technician en sous-classes impose une classification statique : à arbitrer."],
}

AUTOMOTIVE_EN = {
    "explanation": "Minimal model to answer: which vehicles, which owners, which interventions and which parts? "
                   "Person is reused as a close match of schema.org/Person; Owner and Technician are roles modeled as subclasses "
                   "(to be replaced by a role class if the same person holds several roles).",
    "warnings": ["Modeling the Owner/Technician roles as subclasses forces a static classification: to be decided."],
}


def _is_en(system: str, user: str = "") -> bool:
    """Langue demandée au fournisseur : « Langue de la réponse : English » (chat) ou « LANGUAGE: English » (explication)."""
    return bool(re.search(r"Langue de la réponse : English|LANGUAGE: English", system + "\n" + user))


def _automotive(en: bool) -> dict[str, Any]:
    return {**AUTOMOTIVE, **AUTOMOTIVE_EN} if en else AUTOMOTIVE


FR = {"vehicle": "Véhicule", "order": "Ordre", "part": "Pièce", "record": "Enregistrement"}


def _block(text: str, tag: str) -> Optional[dict[str, Any]]:
    m = re.search(tag + r"\s*```json\s*(.*?)```", text, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except ValueError:
        return None


class MockProvider:
    name = "mock"
    timeout_s = None

    def __init__(self, cfg=None) -> None:
        self.cfg = cfg

    @property
    def model(self) -> str:
        return "mock"

    @property
    def configured(self) -> bool:
        return True

    def complete(self, system: str, messages: list[dict[str, str]], max_tokens: int = 4096,
                 json_schema: Optional[dict[str, Any]] = None) -> str:
        user = messages[-1]["content"] if messages else ""
        if "[TASK:draft]" in system:
            sk = _block(user, "SQUELETTE")
            if sk:
                out = dict(sk)
                for c in out.get("classes", []):
                    c.setdefault("label_fr", FR.get(c["name"].lower(), c.get("label_en", c["name"])))
                out["explanation"] = "Squelette dérivé de la source : une classe par entité, une propriété par colonne, clés conservées."
                return json.dumps(out, ensure_ascii=False)
            if re.search(r"(?i)véhicul|vehicle|garage|auto|voiture|réparation|repair", user):
                return json.dumps(_automotive(_is_en(system, user)), ensure_ascii=False)
            return json.dumps({"ontology": {"label_en": "Draft"}, "classes": [{"name": "Thing1", "label_en": "Thing"}],
                               "explanation": "Le mock ne connaît que le domaine automobile.", "warnings": ["Réponse générique du mock."]})
        if "[TASK:chat]" in system:
            en = _is_en(system, user)
            sk = _block(user, "SQUELETTE")
            if sk:
                out = dict(sk)
                for c in out.get("classes", []):
                    c.setdefault("label_fr", FR.get(c["name"].lower(), c.get("label_en", c["name"])))
                return json.dumps({"reply": ("I derived a skeleton from the attachment: one class per entity, one property per column." if en else
                                             "J'ai dérivé un squelette de la pièce jointe : une classe par entité, une propriété par colonne."),
                                   "ontology": out, "warnings": out.get("warnings", [])}, ensure_ascii=False)
            if re.search(r"(?i)véhicul|vehicle|garage|auto|voiture|réparation|repair", user):
                a = _automotive(en)
                return json.dumps({"reply": ("Here is a proposed car-maintenance model; please review it element by element." if en else
                                             "Voici une proposition de modèle de maintenance automobile ; à relire élément par élément."),
                                   "ontology": a, "warnings": a["warnings"]}, ensure_ascii=False)
            return json.dumps({"reply": ("Could you specify the domain (actors, objects, events)? The mock only knows the automotive domain." if en else
                                         "Pouvez-vous préciser le domaine (acteurs, objets, événements) ? Le mock ne connaît que l'automobile."),
                               "ontology": None, "warnings": []}, ensure_ascii=False)
        if "[TASK:shapes]" in system:
            cands = (_block(user, "CANDIDATS") or {}).get("properties", [])
            enr = []
            for c in cands:
                n = c.get("name", "").lower()
                e = {"class": c["class"], "property": c["property"]}
                if "vin" in n:
                    e.update(pattern="^[A-HJ-NPR-Z0-9]{17}$", message_fr="Le VIN comporte 17 caractères (sans I, O, Q).")
                elif any(k in n for k in ("mileage", "kilom", "price", "prix", "quantity", "quantite")):
                    e.update(min_inclusive="0", message_fr="La valeur doit être positive ou nulle.")
                elif "year" in n or "annee" in n:
                    e.update(min_inclusive="1900", max_inclusive="2100")
                else:
                    continue
                enr.append(e)
            return json.dumps({"enrichments": enr, "explanation": f"{len(enr)} contrainte(s) de motif ou de plage ajoutée(s) sur {len(cands)} propriété(s) candidate(s)."},
                              ensure_ascii=False)
        if "[TASK:explain]" in system:
            f = _block(user, "CONSTAT") or {}
            tg = re.search(r"CIBLE\s*:\s*(\w+)", user)
            return fallback_explain(f, tg.group(1) if tg else "curiosity", "en" if _is_en(system, user) else "fr")
        return "{}"
