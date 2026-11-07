# L6 — Assistant IA de conception : rapport

## Livré (backend/ontoforge/assistant/)
- `providers/` : `base.py` (LLMError en français, timeouts `ONTOFORGE_LLM_TIMEOUT`, aucune clé journalisée), `anthropic.py`, `openai_compat.py`, `ollama.py`, `mock.py` ; sélection `get_provider()` via `ONTOFORGE_LLM_PROVIDER` (défaut anthropic). `configured` = clé/URL présente.
- `analyzers.py` : pré-analyse CSV (délimiteur, types inférés, clé, FK supposées) et SQL (CREATE TABLE, PK, FK inline/table/ALTER, NOT NULL, UNIQUE, tables de jointure signalées).
- `convert.py` : JSON intermédiaire → `OntoModel` validé (nommage Pascal/camel, labels fr/en, domaine/portée, inverse, cardinalités en restrictions, `has_keys`, skos:exactMatch/closeMatch, xsd:date/gYear dégradés avec avertissement, cycles retirés, références inconnues créées avec avertissement).
- `service.py` : `status`, `draft` (relance unique si JSON invalide, repli squelette si LLM absent/en erreur), `propose_shapes` (generate_shapes + enrichissement LLM : patterns, plages, in), `explain` (repli déterministe sans LLM).
- Tests : `test_assistant_service.py` (16), `test_assistant_api.py` (1, TestClient + mock). Suite complète : 206 verts.
- Skill `skills/ontology-rapid-design/SKILL.md`.

## Compatibilité API
Signatures de `api/assistant.py` respectées : `propose_shapes(onto, shapes)`, `explain(finding, target, onto)` (renvoie `{text}`), `draft(text, kind, base_iri)`. Les formes `propose_shapes(project)` et `explain(project, target, finding)` sont aussi acceptées. Aucun changement d'API demandé (pas de `journal/L6/demandes-api.md`).

## Points d'attention
- Erreurs : HTTPException 422 (texte vide/kind), 413 (trop long), 503 (non configuré, source texte), 502 (LLM/JSON invalide après relance).
- Format réels des fournisseurs (Anthropic, OpenAI-compat, Ollama) testés uniquement avec httpx simulé : `# À VÉRIFIER` en conditions réelles (surtout `response_format` OpenAI et `format: json` Ollama, modèle par défaut non-Anthropic).
- Mock : ne connaît que le domaine automobile (texte) et relaie le squelette CSV/SQL.
- Pas d'événement Salle des agents via ArtifactData (non chargé pour économie) : ligne ajoutée dans journal/events.jsonl.
