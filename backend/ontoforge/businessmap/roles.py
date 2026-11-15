"""Rôles de nœuds de la carte métier : déduction automatique, couleurs de légende.

Les rôles sont des étiquettes génériques, déduites de la structure du schéma d'abord, du nom du type ensuite ; l'humain a toujours
le dernier mot (``BusinessMapState.roles``). Heuristiques (la première qui s'applique gagne) :

1. ``lookup`` (liste de valeurs) : classe énumérée (owl:oneOf), ou ciblée par au moins 3 types différents, avec au plus une
   relation sortante, peu de propriétés à valeur littérale (au plus 3 si on les connaît) et, si les effectifs sont connus, un
   effectif inférieur ou égal à 10 % de l'effectif médian.
2. ``hub`` (pivot) : ciblé par au moins 4 types différents (ou 15 % des types si le schéma est grand).
3. ``component`` : source d'une relation « partie de » ; ``main`` (principal) : cible d'une telle relation, ou type qui porte
   au moins 2 relations sortantes pour au plus un type entrant.
4. ``document`` : nom évoquant un contenu documentaire (document, guide, rapport, notice…).
5. ``settings`` (paramétrage) : nom évoquant une configuration (paramètre, règle, profil, gabarit…).
6. ``reference`` (référentiel) : nom évoquant des données de référence (catalogue, code, norme…), ou type référencé par au
   moins 2 autres types sans presque rien en sortie.
7. ``context`` : tout le reste.

Un rôle posé par l'humain prime toujours ; un rôle libre (texte quelconque) est accepté. Les anciens ids (``issue``, ``key``…)
enregistrés par une version précédente sont lus comme leur équivalent actuel (``model.LEGACY_ROLES``).
"""
from __future__ import annotations

import re
import zlib
from statistics import median
from typing import Optional

from .graph import SchemaGraph

DOCUMENT = re.compile(r"document|manual|manuel|guide|report|rapport|procedure|procédure|article|publication|notice|contract|contrat", re.I)
SETTINGS = re.compile(r"config|setting|parametre|paramètre|parameter|plan\b|plan[A-Z]|schedule|calendrier|profile|profil|template|gabarit|rule|règle|regle|policy|politique", re.I)
REFERENCE = re.compile(r"catalog|catalogue|reference|référence|code|standard|norme|brand|marque|nomenclature|taxonomy|taxonomie", re.I)

ROLE_LABELS = {
    "main": {"fr": "principal : enregistrement central", "en": "main: central record"},
    "component": {"fr": "composant : partie d'un enregistrement", "en": "component: part of a record"},
    "hub": {"fr": "pivot : référencé par beaucoup de types", "en": "hub: referenced by many types"},
    "lookup": {"fr": "liste de valeurs : petit référentiel", "en": "lookup: a short list of values"},
    "context": {"fr": "contexte : environnement, acteurs, lieux", "en": "context: surroundings, actors, places"},
    "reference": {"fr": "référentiel : données de référence", "en": "reference: reference data"},
    "document": {"fr": "document : contenu documentaire", "en": "document: written content"},
    "settings": {"fr": "paramétrage : configuration, règles", "en": "settings: configuration, rules"},
}

# teintes propres à OntoForge, tirées des jetons de design/tokens.css (lagon, info, lanterne…) ; lisibles en clair comme en sombre
ROLE_COLORS = {
    "main": "#0b6e6e", "component": "#2c4f8f", "hub": "#c2570c", "lookup": "#9a7b0a",
    "context": "#4f7a8c", "reference": "#3f7d3a", "document": "#7b4b94", "settings": "#8c5a3c",
}
FREE_PALETTE = ["#b5651d", "#1f8a8a", "#a23b72", "#4a6fa5", "#6b8e23", "#c0504d", "#8064a2", "#3a7f5c"]

ZONE_COLORS = ["#eef3ff", "#eefaf2", "#fff6e6", "#f3eeff", "#fdeeee", "#eef9fb", "#f6fae9", "#fdf0f7"]


def role_color(role: str, overrides: Optional[dict[str, str]] = None) -> str:
    if overrides and role in overrides:
        return overrides[role]
    if role in ROLE_COLORS:
        return ROLE_COLORS[role]
    return FREE_PALETTE[zlib.crc32(role.encode("utf-8")) % len(FREE_PALETTE)]


def role_label(role: str, lang: str) -> str:
    return ROLE_LABELS.get(role, {}).get(lang if lang in ("fr", "en") else "en", role)


def _words(label: str, nid: str) -> str:
    local = re.split(r"[#/]", nid)[-1]
    return f"{label} {local}"


def infer_roles(g: SchemaGraph) -> dict[str, str]:
    n_nodes = len(g.nodes)
    in_types: dict[str, set[str]] = {k: set() for k in g.nodes}
    out_deg = {k: 0 for k in g.nodes}
    part_src: set[str] = set()
    part_tgt: set[str] = set()
    for r in g.rels:
        if r.kind != "relation" or r.source == r.target or r.source not in g.nodes or r.target not in g.nodes:
            continue
        in_types[r.target].add(r.source)
        out_deg[r.source] += 1
        if r.both:  # une relation fusionnée est aussi entrante dans l'autre sens
            in_types[r.source].add(r.target)
            out_deg[r.target] += 1
        if r.part == "part_of":
            part_src.add(r.source)
            part_tgt.add(r.target)
        elif r.part == "has_part":
            part_src.add(r.target)
            part_tgt.add(r.source)
    counts = [n.count for n in g.nodes.values() if n.count]
    med = median(counts) if len(counts) >= 3 else None  # moins de trois types peuplés : effectifs non significatifs
    key_min = max(4, int(0.15 * n_nodes + 0.5)) if n_nodes > 26 else 4
    roles: dict[str, str] = {}
    for k, n in g.nodes.items():
        fan_in, fan_out = len(in_types[k]), out_deg[k]
        small = n.count is None or med is None or n.count <= 0.1 * med
        few_literals = n.n_data is None or n.n_data <= 3
        if n.enumerated or (fan_in >= 3 and fan_out <= 1 and small and few_literals):
            roles[k] = "lookup"
        elif fan_in >= key_min:
            roles[k] = "hub"
        elif k in part_src and k not in part_tgt:
            roles[k] = "component"
        elif k in part_tgt or (fan_out >= 2 and fan_in <= 1):
            roles[k] = "main"
        else:
            text = _words(n.label, k)
            roles[k] = ("document" if DOCUMENT.search(text) else "settings" if SETTINGS.search(text)
                        else "reference" if REFERENCE.search(text) or (fan_in >= 2 and fan_out <= 1) else "context")
    return roles
