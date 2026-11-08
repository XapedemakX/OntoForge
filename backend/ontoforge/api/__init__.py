"""Routers REST d'OntoForge (préfixe /api, CONTRACTS.md §2)."""
from . import analysis, auth, assistant, editing, files, local_store, projects, queries, settings, system

ROUTERS = [system.router, auth.router, projects.router, analysis.router, assistant.router, settings.router, editing.router, files.router, queries.router, local_store.router]
