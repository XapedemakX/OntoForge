"""Routers REST d'OntoForge (préfixe /api, CONTRACTS.md §2)."""
from . import analysis, assistant, editing, projects, queries, settings, system

ROUTERS = [system.router, projects.router, analysis.router, assistant.router, settings.router, editing.router, queries.router]
