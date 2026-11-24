# 11. Krakie assistant {#assistant-krakie}

Krakie is OntoForge's design assistant. It converses with awareness of the current screen and **proposes** actions (ontology changes, partial ontology, shape constraints, guided query, navigation, version updates); it never applies anything itself (D-006). It works with a configured LLM or, without one, with deterministic answers.

Sources read: `backend/ontoforge/assistant/agent.py`, `backend/ontoforge/assistant/service.py`, `backend/ontoforge/assistant/untrusted.py`, `backend/ontoforge/assistant/reasoning.py`, `backend/ontoforge/assistant/settings_help.py`, `backend/ontoforge/assistant/docdraft.py`, `backend/ontoforge/assistant/document.py`, `backend/ontoforge/assistant/docheur.py`, `backend/ontoforge/assistant/convert.py`, `backend/ontoforge/assistant/providers/`, `backend/ontoforge/api/assistant.py`, `backend/ontoforge/ratelimit.py`, `backend/ontoforge/settings/models.py`.

## Files {#fichiers}

| File | Responsibility |
|---|---|
| `backend/ontoforge/assistant/agent.py` | screen-aware global assistant: `run`, `build_actions`, `validate_ops` (dry run), `validate_shape_patches`, `deterministic` (fallback without LLM), `Resolver` (find an entity by name or label), `schema_compact` |
| `backend/ontoforge/assistant/service.py` | historical functions: `draft` (draft from a text), `propose_shapes`, `explain` (explain a finding), `chat`, `status` |
| `backend/ontoforge/assistant/untrusted.py` | `fence` (wrap untrusted content), `guard` (add the safety rule to the system prompt), `RULE` |
| `backend/ontoforge/assistant/reasoning.py` | "reason" intent: HermiT before any LLM (chapter [05](05-conformite-owl-hermit.en.md#hermit-krakie)) |
| `backend/ontoforge/assistant/settings_help.py` | Krakie on the Settings screen, without a project (D-L38-01): non-sensitive configuration snapshot, `redact` |
| `backend/ontoforge/assistant/document.py`, `docdraft.py`, `docheur.py` | bootstrapping an ontology from a document (L25): reading and chunking, competency questions and draft per chunk, deterministic fallback |
| `backend/ontoforge/assistant/convert.py` | `extract_json` (JSON inside an LLM answer), `to_onto` (proposal → `OntoModel`), `normalize_base` |
| `backend/ontoforge/assistant/providers/` | providers: `anthropic.py`, `openai_compat.py`, `ollama.py`, `mock.py`; shared interface and HTTP in `base.py`; selection in `__init__.py` |
| `backend/ontoforge/api/assistant.py` | routes `/api/assistant/*` |

## Conversation flow {#flux}

```mermaid
flowchart TD
  F[POST /api/assistant/chat {project_id?, messages, context, provider_id?, attachments}] --> S{project_id?}
  S -- no, context.screen=settings --> SH[settings_help.run]
  S -- yes, context given --> R[agent.run]
  R --> L[reply language: reply_lang of the last message]
  L --> Z{"reason" intent?}
  Z -- yes --> HZ[reasoning.answer: HermiT] --> BA
  Z -- no --> P{real provider configured?}
  P -- yes --> U[fence: screen context, schema, attachments; guard: system rule]
  U --> C[provider.complete] --> J[extract_json → {reply, actions, warnings}]
  J --> BA[build_actions: validation of each action]
  P -- no --> D[deterministic: simple intents] --> BA
  D -- nothing --> CH[service.chat: mock or help]
  BA --> OUT[{reply, actions, proposal, warnings}]
```

In `backend/ontoforge/assistant/agent.py::run`:

- The conversation must end with a user message (otherwise 422); only the last `MSG_LIMIT` (40) messages are kept; an attachment is cut at `ATT_LIMIT` (12,000 characters).
- A provider is "real" if it is configured and is not `mock`. Without a usable provider, no error: deterministic fallback.
- An LLM error becomes a 502 with a message free of secrets. An answer that is not JSON is returned as is, as text, without actions.
- `build_actions` handles at most 6 actions and **re-validates** each on the server:

| Action kind | Validation |
|---|---|
| `ops` | `validate_ops`: each operation (60 at most) is normalized (existing IRIs found by `Resolver`, new entities under the project base IRI), then tried on a copy of the project (`editing/ops.py::apply_ops`); a failing operation is removed with a warning |
| `proposal` | partial ontology converted by `to_onto`; never merged here |
| `shapes` | `validate_shape_patches`; applied through `POST /api/assistant/shapes/apply` (write right, undoable history) |
| `guided_query` | recomputed by `/query/nl` (chapter [09](09-requetes.en.md#nl)) |
| `versions` | the server recomputes recommended versions (`standards.check`): the LLM's request is never applied as is |
| `navigate`, `help` | screen taken from a closed list |
| `settings_goto`, `settings_test` | Settings screen only, produced by `settings_help.run` (see below); the test is started by the front, on click of the "Test connection" button (`frontend/src/assistant-global/ActionCards.tsx::TestCard`), which calls `settingsApi.testProvider` or `testEndpoint`; the server does not run it inside the chat reply |

The front knows these nine kinds (`frontend/src/assistant-global/store.ts::ActionKind`).

`ops` actions are applied through the editing route (`POST /api/projects/{pid}/ops`, chapter [13](13-projets-versions.en.md)), on a user click.

## Untrusted content {#non-fiables}

Any text that does not come from the person typing (ontology labels and comments, documents, attachments, findings, endpoint answers) is wrapped by `backend/ontoforge/assistant/untrusted.py::fence` in a `<donnees source="…">…</donnees>` block. A `donnees` tag inside the content is neutralized, so it cannot close the block. `guard` adds to every system prompt a (priority) rule forbidding to follow any instruction found in those blocks. The safety net stays on the server: nothing is applied without a click, and every action is re-validated (SEC-17, OWASP LLM01).

## LLM providers {#fournisseurs}

`backend/ontoforge/assistant/providers/__init__.py::get_provider`: explicit `provider_id`, else the default provider from the settings (`$ONTOFORGE_DATA/settings.json`, chapter [12](12-comptes-partage-admin.en.md)); as long as that file does not exist, historical environment variables (`ONTOFORGE_LLM_PROVIDER`, default `anthropic`).

| Kind | Class | Endpoint | Default model | Configured if |
|---|---|---|---|---|
| `anthropic` | `AnthropicProvider` | `https://api.anthropic.com/v1/messages` (or `base_url` + `/v1/messages`), header `anthropic-version: 2023-06-01` | `claude-sonnet-5-5` (`ONTOFORGE_LLM_MODEL`) | API key |
| `openai_compat` | `OpenAICompatProvider` | `<base_url>/chat/completions`; `response_format: json_object` when a schema is requested; non-secret settings (`reasoning_effort`, `temperature`, `top_p`) passed through | `gpt-4o` | `base_url` |
| `ollama` | `OllamaProvider` | Ollama server | `llama3.1` | `base_url` |
| `mock` | `MockProvider` | no network; deterministic answers from the car domain | — | always |

Every request goes through `backend/ontoforge/assistant/providers/base.py::post_json`, which calls `netguard.post` (outgoing address control, chapter [16](16-securite.en.md)), applies the `ONTOFORGE_LLM_TIMEOUT` timeout (120 s), turns HTTP errors into French messages (`http_error`) and masks secrets in the returned detail (`_detail`). An address rejected by `netguard` gives a generic message citing neither host nor address (L41-R1). Structured output is requested through the prompt text (`schema_hint`): no provider uses native tool calling. D-006 also mentioned Bedrock: there is no Bedrock provider in the code (`À CONFIRMER`: through an OpenAI-compatible endpoint).

The `mock` provider is the test default; no test depends on a key (D-021).

## Bootstrapping from a document {#document}

`backend/ontoforge/assistant/docdraft.py::draft_document`: document (`.txt`, `.md`, `.pdf` with native text read by pypdf) split into chunks (`document.py`, limits `ONTOFORGE_DOC_MAX_MB` 10, `ONTOFORGE_DOC_MAX_PAGES` 60, `ONTOFORGE_DOC_MAX_CHARS` 400,000, `ONTOFORGE_DOC_CHUNK_CHARS` 8,000); one "questions" call then one "draft" call per chunk; duplicate merging; deterministic checks (strict schema, valid names, new IRIs, cycle-free hierarchy, **excerpt found in the document**); W3C lint of the draft (`lint(..., practices=False)`); question coverage. With a hosted provider, `confirm_hosted: true` is required (the document leaves the machine); with `mock` or `ollama`, nothing leaves. Without an LLM, `docheur.py` gives an approximate draft, flagged as such. The proposal is reviewed item by item in the front.

## Krakie on the Settings screen {#parametres}

`POST /api/assistant/chat` without `project_id` is accepted only for `context.screen = "settings"` (D-L38-01). `settings_help.run` only sends a **non-sensitive** configuration snapshot to the LLM: no key, password, token or user identifier, URLs without credentials or parameters. Messages and the answer go through `redact`. Specific actions: `settings_goto`, `settings_test`, `help`.

## Rate {#debit}

`backend/ontoforge/ratelimit.py` puts `/api/assistant/(chat|draft|shapes|explain|upload|shapes/apply|document/…)` and `/query/nl` in the `assistant` family: `ONTOFORGE_RATE_ASSISTANT_PER_MIN` (20 per minute, per IP address and per session), beyond that 429 with `Retry-After`.

## Libraries {#librairies}

| Library | Version | Why |
|---|---|---|
| httpx | 0.28.1 | HTTP calls to providers (through `netguard`) |
| pypdf | 7.0.0 | PDF text (bootstrapping from a document) |
| pydantic | 2.10.3 | provider configuration, proposal models |

No provider SDK: the APIs are called directly over HTTP JSON.

## Decisions {#decisions}

- D-006: configurable-provider assistant, every proposal subject to human review.
- D-021: `mock` by default in tests.
- D-L8-01: API keys encrypted in the settings, never returned.
- D-L38-01: Krakie on the Settings screen.
- L39-secu (SEC-17): imported content fenced as untrusted data.

## Pitfalls and limits {#pieges}

- No streaming: `complete` waits for the full answer (120 s timeout by default).
- JSON by instruction: a model that ignores the format gives a text answer without actions; `extract_json` tolerates text around the JSON.
- Language: the reply language follows the last message (`reply_lang`), not the UI setting.
- Cost: each document chunk makes two calls; `POST /api/assistant/document/estimate` estimates before running.

## How to add… {#comment-ajouter}

**…a provider.** Write a class inheriting from `Configured` in `backend/ontoforge/assistant/providers/` (properties `model`, `configured`, method `complete(system, messages, max_tokens, json_schema)`), call the service through `post_json` (never `httpx` directly: you would lose `netguard` and secret masking), register it in `PROVIDERS`, add the kind to `Kind` in `backend/ontoforge/settings/models.py` and to the front's Settings screen.

**…an action kind.** Add the branch in `build_actions` with full server-side validation, describe it in the `AGENT_SYSTEM` prompt, and its rendering and application in the front: `ActionKind` type (`frontend/src/assistant-global/store.ts`), card (`frontend/src/assistant-global/ActionCards.tsx`), application on click (`frontend/src/assistant-global/run.ts`), chapter [15](15-front.en.md). An action must never apply on the server without an explicit user call.

**…a deterministic intent.** Recognize it in `deterministic` (or a dedicated module called before the LLM, like `reasoning.answer`) and return raw actions: they will go through `build_actions` like the LLM's.
