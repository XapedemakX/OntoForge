# OntoForge

Outil de conception d'ontologies OWL 2 / SHACL et de transposition vers des property graphs (Curiosity en priorité, Neo4j).

- Plan et décisions : docs/PLAN.md — Architecture et catalogue de règles : docs/ARCHITECTURE.md — Protocole d'équipe : docs/TEAM.md
- Agents : .claude/agents/ — Skills réutilisables (à maintenir à chaque lot) : skills/
- Contrats de lot : lots/ — Journal (revues, corrections, décisions, questions à Jerem) : journal/
- Lancer : `docker compose up --build` puis http://localhost:8088 — Tests backend : `cd backend && pytest -q`
- Doc et messages en français, code en anglais. Toute API externe non confirmée est marquée `À VÉRIFIER`.
