"""Table exhaustive des routes qui portent un identifiant de projet : (méthode, modèle de chemin) -> (niveau, action du journal).

Niveaux : ``read`` (propriétaire, éditeur, lecteur), ``write`` (propriétaire, éditeur), ``owner`` (propriétaire seul).
Une route avec ``{pid}`` absente de cette table est refusée (403) : le cloisonnement échoue fermé.
``tests/test_collab.py::test_every_route_is_classified`` parcourt toutes les routes de
l'application et échoue si l'une n'est ni classée ici, ni déclarée sans projet (ci-dessous).
"""
from __future__ import annotations

P = "/api/projects/{pid}"
R, W, O = "read", "write", "owner"

ROUTES: dict[tuple[str, str], tuple[str, str]] = {
    ("GET", P): (R, ""), ("PUT", P): (W, "project"), ("DELETE", P): (O, "delete"),
    ("POST", P + "/import"): (W, "import"), ("PUT", P + "/onto"): (W, "ontology"), ("PUT", P + "/shapes"): (W, "shapes"),
    ("POST", P + "/dsl"): (W, "ontology"),
    # L48 : import déterministe SQL / CSV / JSON Schema ; l'aperçu est réservé à qui peut écrire (même contrat que l'import)
    ("POST", P + "/import/schema/preview"): (W, ""), ("POST", P + "/import/schema/apply"): (W, "import"),
    ("GET", P + "/export/ontology"): (R, ""), ("GET", P + "/export/shapes"): (R, ""),
    ("GET", P + "/conformance"): (R, ""), ("POST", P + "/reason"): (R, ""),
    ("POST", P + "/shacl/generate"): (W, "shapes"), ("POST", P + "/shacl/validate"): (R, ""),
    ("POST", P + "/analyze"): (R, ""), ("PUT", P + "/decisions/{target}"): (W, "decisions"),
    ("POST", P + "/decisions/{target}/accept-recommended"): (W, "decisions"),
    ("POST", P + "/decisions/{target}/branch"): (W, "decisions"),   # L47 : arbitrage par racine de hiérarchie
    ("GET", P + "/justification/{target}"): (R, ""),   # L47 : dossier de justification (lecture seule, ouvert au lecteur)
    # L42 (D-L42-01) : générer écrit l'historique (generations.json) : éditeur et propriétaire seulement ; le lecteur consulte l'historique
    ("GET", P + "/generate/{target}"): (W, "generate"), ("GET", P + "/generations"): (R, ""), ("GET", P + "/generate/{target}/zip"): (W, "generate"),
    ("POST", P + "/queries/translate"): (R, ""), ("GET", P + "/queries/competency"): (R, ""),
    ("POST", P + "/ops"): (W, "ontology"), ("GET", P + "/ops/history"): (R, ""),
    ("POST", P + "/ops/undo"): (W, "ontology"), ("POST", P + "/ops/redo"): (W, "ontology"), ("GET", P + "/graph"): (R, ""),
    ("GET", P + "/perimeters"): (R, ""), ("POST", P + "/perimeters"): (W, "perimeters"), ("PUT", P + "/perimeters/active"): (W, "perimeters"),
    ("GET", P + "/perimeters/{perimeter_id}"): (R, ""), ("GET", P + "/perimeters/{perimeter_id}/preview"): (R, ""),
    ("PUT", P + "/perimeters/{perimeter_id}"): (W, "perimeters"), ("DELETE", P + "/perimeters/{perimeter_id}"): (W, "perimeters"),
    ("GET", P + "/business-map"): (R, ""), ("PUT", P + "/business-map"): (W, "business_map"),
    ("POST", P + "/business-map/suggest-zones"): (W, "business_map"), ("POST", P + "/business-map/suggest-frames"): (W, "business_map"),
    ("POST", P + "/business-map/layout"): (W, "business_map"),
    ("GET", P + "/files"): (R, ""), ("POST", P + "/files/validate"): (R, ""), ("POST", P + "/files/diff"): (R, ""),
    ("GET", P + "/files/{path:path}"): (R, ""), ("PUT", P + "/files/{path:path}"): (W, "files"),
    ("GET", P + "/query/suggest"): (R, ""), ("POST", P + "/query/build"): (R, ""), ("POST", P + "/query/run"): (R, ""),
    ("GET", P + "/query/values"): (R, ""), ("POST", P + "/query/values"): (R, ""), ("GET", P + "/query/options"): (R, ""),
    ("POST", P + "/query/endpoint-test"): (R, ""), ("POST", P + "/query/nl"): (R, ""),
    ("GET", P + "/queries/saved"): (R, ""), ("POST", P + "/queries/saved"): (W, "queries"),
    ("GET", P + "/queries/saved/{qid}"): (R, ""), ("PUT", P + "/queries/saved/{qid}"): (W, "queries"),
    ("DELETE", P + "/queries/saved/{qid}"): (W, "queries"), ("GET", P + "/queries/competency/guided"): (R, ""),
    ("GET", P + "/store/stats"): (R, ""), ("POST", P + "/store/load"): (W, "store"), ("DELETE", P + "/store"): (W, "store"),
    ("POST", P + "/store/validate"): (R, ""),
    ("GET", P + "/versions"): (R, ""), ("PUT", P + "/versions"): (W, "versions"), ("GET", P + "/versions/check"): (R, ""),
    # L49 : versions publiées de l'ontologie (diff SemVer, note de version) et en-tête
    ("GET", P + "/releases"): (R, ""), ("GET", P + "/releases/preview"): (R, ""), ("GET", P + "/releases/{version}"): (R, ""),
    ("POST", P + "/releases"): (W, "release"), ("GET", P + "/metadata"): (R, ""),
    # L40 : partage, présence, activité
    ("GET", P + "/access"): (R, ""), ("POST", P + "/access/members"): (O, ""), ("DELETE", P + "/access/members/{login}"): (R, ""),
    ("POST", P + "/access/transfer"): (O, ""), ("POST", P + "/presence"): (R, ""), ("GET", P + "/activity"): (R, ""),
}

# Routes dont l'identifiant de projet est dans le corps JSON (assistant) : le handler appelle ``access.enforce`` / ``load_project``.
BODY_PROJECT_ROUTES: dict[tuple[str, str], str] = {
    ("POST", "/api/assistant/shapes"): R, ("POST", "/api/assistant/explain"): R, ("POST", "/api/assistant/chat"): R,
    ("POST", "/api/assistant/shapes/apply"): W, ("POST", "/api/assistant/document/draft"): R,
}

# Routes sans projet : ouvertes à tout compte connecté (les réglages, eux, sont réservés aux administrateurs en écriture).
NO_PROJECT: set[tuple[str, str]] = {
    ("GET", "/api/health"), ("GET", "/api/samples"), ("GET", "/api/standards"), ("GET", "/api/icons"),
    ("GET", "/api/auth/session"), ("POST", "/api/auth/login"), ("POST", "/api/auth/logout"),
    ("POST", "/api/auth/password"), ("PUT", "/api/auth/preferences"),   # L42 : le garde d'authentification les laisse passer, ils contrôlent la session eux-mêmes
    ("GET", "/api/projects"), ("POST", "/api/projects"),
    ("POST", "/api/import/schema/preview"),   # L48 : calcul pur, aucun projet touché ; sert l'écran Projets avant la création
    ("POST", "/api/import/schema/preview"),   # L48 : calcul pur, aucun projet touché ; sert l'écran Projets avant la création
    ("GET", "/api/assistant/status"), ("POST", "/api/assistant/draft"), ("POST", "/api/assistant/upload"),
    ("GET", "/api/assistant/document/demo"), ("POST", "/api/assistant/document/upload"), ("POST", "/api/assistant/document/estimate"),
}

SETTINGS_PREFIX = "/api/settings"
ADMIN_PREFIX = "/api/admin"   # L42 : toutes les routes d'administration des comptes (administrateurs seulement, 403 admin_only)


def is_settings_write(method: str, path: str) -> bool:
    """Toute écriture sous /api/settings, et les routes de test (elles utilisent les secrets enregistrés), sont réservées aux administrateurs."""
    return (path == SETTINGS_PREFIX or path.startswith(SETTINGS_PREFIX + "/")) and (method not in ("GET", "HEAD", "OPTIONS") or False)


def classify(method: str, template: str) -> tuple[str, str] | None:
    return ROUTES.get(("GET" if method == "HEAD" else method, template))
