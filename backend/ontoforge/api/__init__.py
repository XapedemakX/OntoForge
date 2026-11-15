"""Routers REST d'OntoForge (préfixe /api, CONTRACTS.md §2)."""
from . import analysis, auth, assistant, business_map, editing, files, local_store, projects, queries, settings, sharing, system, versions

ROUTERS = [system.router, auth.router, projects.router, analysis.router, assistant.router, settings.router, editing.router, business_map.router, files.router, queries.router, local_store.router, versions.router, sharing.router]
