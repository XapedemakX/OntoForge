# 02. Front ↔ back communication {#communication-front-back}

How the browser and the server talk to each other: who adds which header, what the server refuses and why, and what the interface does with each refusal. The server part (FastAPI routes, pydantic models, dependencies) is in the "Server side" section further down. Back to the [index](README.en.md).

State verified on 23 November 2026 on branch `lot/L51`. Anything not executed is marked `À CONFIRMER` (to be confirmed).

## 1. Role {#role}

- Everything goes through JSON over HTTP under the `/api` prefix. No WebSocket, no SSE: "collaboration" is polling (presence every 20 s) plus optimistic concurrency (`If-Match`).
- The front end has no single client: a global `fetch` is **patched at start-up** (`frontend/src/auth/AuthGate.tsx`) to add the CSRF token, the project version, a write queue, and to react to 401 / 403 / 409 / 428. On top of it, seven clients, `api.ts` included (one per area), format calls, but all of them send the request and read the error through `frontend/src/lib/http.ts::request` (L52).
- The server returns JSON, except exports (text) and the zip (bytes).

## 2. Files and responsibilities {#fichiers}

| File | Responsibility |
|---|---|
| `frontend/src/api.ts::api` | main typed client (projects, analysis, generation, accounts, versions…); types mirror `backend/ontoforge/core/*.py` |
| `frontend/src/lib/http.ts::request` | the clients' **only send point**: calls `fetch` (the global one, looked up at each call), translates the network error (`ui.unreachable`, `status` 0) and reads `detail` (string or list of `{loc, msg}`), `code` and the JSON body; never throws, returns `{ok, res}` or `{ok: false, status, message, code, body}` |
| `frontend/src/lib/httpDetail.ts::detailMessage` | pure reading of `detail` (tested by `frontend/tests/http_detail.test.mjs`); `withLoc` prefixes the faulty field (Settings) |
| `frontend/src/api.ts::req` | the base call: URL, JSON body or `FormData`, then `request`; throws `ApiError` |
| `frontend/src/api.ts::ApiError` | error carrying `status` and `code` (stable server code) |
| `frontend/src/auth/AuthGate.tsx` | **replaces `window.fetch`**: CSRF, `If-Match`, `ETag`, per-project queue, 401 / 403 / 409 / 428 events; holds the session (`GET /api/auth/session`) |
| `frontend/src/collab/rev.ts` | known version per project (`getRev`, `noteRev`, `forceRev`), `queued` (write queue), `conflictFrom` (replayability) |
| `frontend/src/collab/useCollab.ts::useCollab` | presence heartbeat, "someone else saved" detection |
| `frontend/src/collab/Banners.tsx::ConflictDialog` | conflict dialog, "reload and reapply" |
| `frontend/src/screens/editor/types.ts::eapi` | graph editor client (`/graph`, `/ops`, perimeters, icons) |
| `frontend/src/screens/files/fapi.ts::fapi` | file editor client; returns `{status, ok, data}` instead of throwing |
| `frontend/src/screens/queries/qapi.ts::qapi` | guided queries client |
| `frontend/src/screens/assistant/aapi.ts::aapi` | full-screen assistant client |
| `frontend/src/assistant-global/gapi.ts::gapi` | Krakie panel client |
| `frontend/src/screens/settings/settingsApi.ts::settingsApi` | Settings client (`/api/settings`) |
| `frontend/src/lib/proposal.ts::acceptItem` | direct `POST /ops` call to accept an assistant proposal |
| `frontend/vite.config.ts` | development `/api` proxy |
| `frontend/nginx.conf` | proxy of the local Docker setup |
| `backend/ontoforge/security.py::SpaStatic` | serves the compiled front end in production (Cloud Run) |

## 3. Flow of a write call {#flux-ecriture}

Example: the graph editor adds a class (`POST /api/projects/{id}/ops`) on an instance with authentication.

```mermaid
sequenceDiagram
  participant E as Screen (Editor.tsx)
  participant C as eapi.call
  participant F as patched window.fetch (AuthGate.tsx)
  participant Q as per-project queue (rev.ts::queued)
  participant RL as RateLimit
  participant A as AuthMiddleware
  participant K as CollabMiddleware
  participant R as FastAPI route (editing.py)
  E->>C: eapi.ops(pid, ops, label)
  C->>F: fetch('/api/projects/p1/ops', POST, JSON)
  F->>F: adds X-CSRF-Token (session token)
  F->>Q: queues the write for p1
  Q->>F: send(): adds If-Match "7"
  F->>RL: request + session cookie
  RL->>A: 60 s quota per IP and per session OK
  A->>A: valid session? Origin = Host? CSRF = token?
  A->>K: identity set (scope.state.auth_user)
  K->>K: enough role? If-Match = version 7?
  K->>R: project lock, the route runs
  R-->>K: 200 {ok, project…}
  K-->>F: ETag "8" added; version +1 if project.json changed
  F->>F: noteRev(p1, 8)
  F-->>C: Response
  C-->>E: OpResult
  Note over F,K: if the version changed: 409 {code: conflict} then ontoforge:conflict event
```

In the diagram:

1. Base URL: always relative (`/api/...`, constant `BASE` in `frontend/src/api.ts`). The browser therefore talks to the origin that served it, which makes CORS unnecessary in normal use.
2. Body: JSON (`Content-Type: application/json` set by the client) or `FormData` for file uploads (the browser sets the `Content-Type` with the boundary).
3. Session cookie: set by `POST /api/auth/login`; the browser sends it back on its own (same origin, no `credentials` setting needed). Name `__Host-ontoforge_session` when the cookie is `Secure`, `ontoforge_session` otherwise (`ONTOFORGE_COOKIE_SECURE=0`, plain-http testing); attributes `HttpOnly`, `SameSite=Lax`, path `/`. See `backend/ontoforge/auth/config.py` and `backend/ontoforge/api/auth.py::login`.
4. CSRF token: returned by `GET /api/auth/session` and by login (field `csrf`), kept in a module variable of `AuthGate.tsx`, never in browser storage. Added as `X-CSRF-Token` to every `/api` request that is not `GET` / `HEAD` / `OPTIONS`.
5. Origin check: server side only. For a write, if `Origin` is present its host must equal `Host` (or `X-Forwarded-Host`); otherwise 403 `bad_origin`. A client without `Origin` (a script) passes this check but must still supply the CSRF token.

## 4. Protocol details {#protocole}

### 4.1 Authentication and CSRF {#auth-csrf}

- Without authentication (`ONTOFORGE_AUTH` unset, local use), `GET /api/auth/session` answers `enabled: false` and the app opens directly; no token, no origin check.
- With authentication (`backend/ontoforge/auth/middleware.py::AuthMiddleware`): every `/api/*` route except `/api/health` and `/api/auth/*` requires a valid session (401 `auth_required`). Writes also require a consistent `Origin` and an `X-CSRF-Token` equal to the session token (403 `csrf`).
- A `GET` that writes: generation (`GET /api/projects/{id}/generate/{target}` and `/zip`) writes the history. It is treated as a write on both sides: the `WRITE_GET` regex in `AuthGate.tsx`, `csrf_required` / `_WRITE_GET` in `auth/middleware.py` (decision D-L42-01). If you add a `GET` that writes, change **both** lists (and `collab/routes.py` on the server): otherwise you get a CSRF 403 or no version sent.
- A 401 outside `/api/auth/*` raises the `ontoforge:auth-required` event: `AuthGate` forgets the token and shows the login page. A 403 `password_change_required` raises `ontoforge:must-change` (screen to change the temporary password).
- Login (`frontend/src/auth/Login.tsx`) calls `fetch` directly: a 429, or a 401 with `retry_after`, makes the button wait (countdown), with no automatic retry.

### 4.2 Project version: `ETag`, `If-Match`, 409, 428 {#if-match}

Decision D-L40-01 (optimistic concurrency, no real time).

| Step | Who | Detail |
|---|---|---|
| Load | `api.loadProject` / `api.getProject` | `GET` with the **internal** header `X-OntoForge-Load: 1`; the patched `fetch` removes it before sending and, on the response, sets the known version (`forceRev`) from `ETag`. |
| Plain read | `api.peekProject` | no load header: the known version does not change (display only). |
| Write | patched `window.fetch` | if a version is known for this project, adds `If-Match: "<n>"` (unless the caller already set it). The `/presence`, `/access`, `/activity` routes are excluded (`rev.ts::tracksRev`). |
| Write response | same | `ETag` read and stored (`noteRev`, only if greater). |
| Local concurrency | `rev.ts::queued` | two writes to the same project leave one after the other in this tab, never in parallel. The server does the same (per-project lock). |

Server answers (`backend/ontoforge/collab/access.py::check_precondition`):

- 409 `{code: "conflict", current_rev, last_actor, last_at}`: the version sent is not the current one. Nothing was saved.
- 428 `{code: "precondition_required", current_rev}`: no `If-Match` while the project is shared and the instance has accounts. On a non-shared project, or without authentication, a missing `If-Match` is accepted (scripts, recipes); so is `If-Match: *`.
- The front end reacts: the patched `fetch` raises the `ontoforge:conflict` event; `ConflictDialog` (mounted in `Shell.tsx`) reloads the project, then **replays** the write if it is in the safe list `REPLAYABLE` of `rev.ts` (operations, decisions, perimeters, saved queries, versions). For the others (whole-project PUT, import…), the dialog asks the user to redo the gesture by hand.
- A 403 `read_only` on a write raises `ontoforge:readonly` (a "read only" toast); the interface already disables the buttons (`collab/readonly.ts::useReadOnlyGuard`), but the server stays the authority.

### 4.3 Presence and polling {#presence}

`useCollab` calls `POST /api/projects/{id}/presence` (`api.presence`) on opening, every 20 s (`BEAT_MS`) while the tab is visible, and when it becomes visible again. The server forgets an account after 60 s without a heartbeat. The response carries `rev`, `last_actor`, `role`: if `rev` exceeds the known version and the author is not the current user, `StaleBanner` offers "reload" (event `ontoforge:reload-project`, handled by `Shell.tsx`). The role (`reader`) also switches the interface to read-only.

### 4.4 Rate limiter and 429 {#limiteur}

`backend/ontoforge/ratelimit.py::RateLimit`: 60 s sliding window, per IP address and per session-cookie fingerprint. Three per-minute caps: global 900, assistant 20, "heavy" 120 (the reasoner: at most 10). Tunable with `ONTOFORGE_RATE_*`, switched off by `ONTOFORGE_RATE_LIMIT=0` (the tests turn it off in `backend/tests/conftest.py`). Answer: 429 `{detail, code: "rate_limited", retry_after}` with `Retry-After`. The front end has **no retry logic**: the server message is shown as is (toast or `ErrorView`). Only login counts down the wait. Behind nginx or Cloud Run, the IP comes from `X-Forwarded-For` at rank `ONTOFORGE_PROXY_HOPS` (1 in `docker-compose.yml`, 1 by default in public mode).

### 4.5 Error format and translation {#erreurs}

Every refusal is JSON `{"detail": "...", "code": "..."}` (`code` is stable, `detail` is human text). Exceptions to the shape:

- 422 (pydantic validation): `{"detail": "Invalid input — field: message; ...", "errors": [...]}`; built in `backend/ontoforge/main.py::_handlers`, without the submitted values (an over-long password does not come back).
- 503 `{code: "busy", retry_after}`: too many parallel SHACL validations.
- 413: body too large (`security.BodyLimit`, 32 MB by default; nginx accepts 50 MB).
- 501: missing module or function (`backend/ontoforge/api/_common.py::service`); the screen shows "coming soon" (`ui.tsx::ErrorView`). Trap: `POST /reason` also answers 501 when the image was built without HermiT (`WITH_REASONER=0`); the Conformance screen then shows the server message as is, not "coming soon".

**Who translates what.** The server writes in French and translates to English at the HTTP boundary when the user's language is `en` (`backend/ontoforge/localize/__init__.py::ui_lang`: the account language, otherwise `settings.language.ui`). The front end **adds nothing**: it shows `detail` as is. It only translates its own messages: `ui.http` ("Error {s}", non-JSON body) and `ui.unreachable` (the server does not answer, `status` 0) in `frontend/src/i18n/fr.json` and `en.json`.

Client-side normalisation: `req` reads `detail` (text or a list of `{msg}`) and copies `code` into `ApiError.code`. The six other clients repeat this block with slight variations (see Pitfalls).

### 4.6 Downloads (blob) {#telechargements}

- Text (Turtle ontology, shapes, justification, generated files): the API returns text (`req(..., text = true)`), the screen calls `frontend/src/ui.tsx::download(name, content, mime)`, which builds a `Blob`, an object URL and an `<a download>` link clicked programmatically.
- Zip: `api.zip` makes an **ordinary** `fetch` (hence it carries the CSRF token and the version: it is a write, D-L42-01) and reads `r.blob()`; `api.downloadZip` creates the link and revokes the URL after 4 s. No more direct `<a href="/api/…/zip">` link: it would carry neither token nor version.
- SVG / PNG export of the graph: entirely local (`frontend/src/screens/editor/exporter.ts`), no server call.

### 4.7 Development proxy and production {#proxy}

| Context | Who serves what | Details |
|---|---|---|
| Dev (`npm run dev`) | Vite on 5173 serves the front end; `server.proxy['/api']` forwards to `ONTOFORGE_API` (default `http://localhost:8000`) | `frontend/vite.config.ts`. The browser stays on origin 5173: cookies and `Origin` are consistent without CORS. `À CONFIRMER`: the proxy keeps the `Host` header (Vite's default `changeOrigin` setting) with authentication on; not executed here. |
| `vite preview` (recipes) | same proxy | recipes also intercept `/api` in the browser towards the throwaway backend (`tools/recette/e2e_ui.mjs`). |
| Local Docker (`docker compose up`) | nginx (container port 8080, published on `ONTOFORGE_PORT`, 8088) serves the front end and forwards `/api/` to `backend:8000` | `frontend/nginx.conf`: `Host $http_host` (keeps the port: the origin check compares `Origin` and `Host`), `X-Forwarded-For $remote_addr`, 300 s timeout, 50 MB body, `Cache-Control: no-store` on the API, headers from `frontend/security-headers.conf`. |
| Cloud Run (production) | a single container: uvicorn serves the API **and** the compiled front end through `security.SpaStatic` | `deploy/cloudrun/Dockerfile`; `SpaStatic` returns the file, or `index.html` for front-end routes, a JSON 404 for an unknown `/api/` path, a real 404 for a missing static file. |

## 5. Server-side layer order {#ordre-middlewares}

Execution order of a request (outside in), as built by `backend/ontoforge/main.py::create_app`:
`RateLimit` → `BodyLimit` → `SecurityHeaders` (if public, authenticated or serving the front end) → CORS (if `ONTOFORGE_CORS_ORIGINS`) → `AuthMiddleware` (if authentication) → `CollabMiddleware` → routes. Static files are mounted on `/` in the router: they also go through these layers, but `AuthMiddleware` only handles `/api`.

## 6. Server side {#cote-serveur}

Sources read: `backend/ontoforge/main.py`, `backend/ontoforge/api/__init__.py`, `backend/ontoforge/api/_common.py`, `backend/ontoforge/api/*.py`, `backend/ontoforge/collab/routes.py`, `backend/ontoforge/collab/access.py`, `backend/tests/test_api_contract.py`.

### 6.1 Routers {#serveur-routeurs}

`backend/ontoforge/api/__init__.py::ROUTERS` lists the sixteen routers included by `create_app`: `system` (`/api/health`, `/api/samples`), `auth`, `projects`, `analysis`, `assistant`, `settings`, `editing`, `business_map`, `files`, `queries`, `local_store`, `versions`, `releases`, `sharing`, `admin`, `schema_import`. Each declares its prefix (`/api`, `/api/projects/{pid}`, `/api/projects/{pid}/store`, `/api/assistant`…). There is no FastAPI dependency (`Depends`) for identity or rights: they are set by the middlewares (section 5) and read through `backend/ontoforge/collab/access.py::current`.

The contract path list is checked by `backend/tests/test_api_contract.py`; project route classification by `backend/tests/test_collab.py::test_every_route_is_classified` (chapter [12](12-comptes-partage-admin.en.md#cloisonnement)).

### 6.2 Shape of a route {#serveur-forme}

The common pattern, for instance in `backend/ontoforge/api/projects.py` and `backend/ontoforge/api/analysis.py`:

1. Access and loading: `backend/ontoforge/api/_common.py::load_project(pid, level)` repeats the access check (`access.enforce`) then reads the project; 404 if the project is unknown or inaccessible, 403 if the role is not enough.
2. Lazy service: `service("io.rdf_import", "parse_ontology")` imports the module at call time; a missing module or function gives 501 `module … pas encore disponible` (legacy of lot L1, when the API existed before the modules). `optional_service` returns `None` instead of raising.
3. Reading errors: `parse_error(what, exc)` turns a reading exception into a readable 422 (message cut at 800 characters).
4. Output: either a declared model (`response_model=Project`, `PGModel`), or a dictionary passed through `dump`, which serializes pydantic models **with their aliases** (`from`, `in`, `class`). Texts produced by the engine go through `localize` before leaving (`localize_pg`, `tr_deep`).
5. Long computations: `async` routes that read a file hand the work to `run_in_threadpool` (SHACL validation, schema imports) so as not to block the event loop. `def` routes already run in FastAPI's thread pool.
6. Write: `store.save(p)` (chapter [13](13-projets-versions.en.md#ecritures)); version and activity log are handled afterwards by `CollabMiddleware`, not by the route.

### 6.3 Exchanged models {#serveur-modeles}

The main bodies and responses are the normative models of `backend/ontoforge/core/` (chapter [03](03-modele-interne.en.md)): `Project`, `OntoModel`, `ShapesModel`, `PGModel`. Route-specific bodies are small pydantic models declared in the route's file (`ProjectCreate`, `DslRequest`, `ReasonRequest`, `BranchRequest`, `RunRequest`…). Exceptions: `PUT /decisions/{target}` and `POST /ops` receive a free `dict`, validated by hand (two formats accepted for compatibility). The front keeps its mirror types by hand (`frontend/src/api.ts`): a field added on the server does not appear there by itself.

### 6.4 HTTP errors {#serveur-erreurs}

Handlers in `backend/ontoforge/main.py::_handlers`:

| Exception | Response |
|---|---|
| `HTTPException` (including `CollabError`, `AccountError`) | `{detail, …payload}`; `detail` translated into English if the request language is `en`; `CollabError.payload` adds `code` and the useful fields (`current_rev`, `last_actor`, `role`) |
| `ShaclBusyError` | 503 `{detail, code: "busy", retry_after}` and `Retry-After` |
| `RequestValidationError` | 422 `{detail: "Invalid input — field: message; …", errors}`; the keys `input`, `ctx` and `url` are removed from `errors` (an entered value, a password for instance, never comes back) |

Middleware refusals (401, 403 `csrf`, `bad_origin`, `admin_only`, `unclassified`, 413, 429) are written directly as JSON by the ASGI layer, without going through these handlers. Their `detail` is translated by the same mechanism (`localize.tr`) through `backend/ontoforge/auth/middleware.py::localized` (L52, DF-F03): the account language when the session has already been read (CSRF, origin, temporary password, `unclassified`), otherwise the global `language.ui` setting (401 without a session; 413, because `BodyLimit` runs before authentication). The 429 and `admin_only` were already bilingual (`access.msg`). The `code` never changes: the front relies on it, not on the text.

## 7. Decisions {#decisions}

- D-L40-01: optimistic concurrency (`ETag` / `If-Match`), explicit 409, presence without real time, `If-Match` optional on a non-shared project, 428 on a shared project.
- D-L42-01: generation (and its zip) is a write: CSRF, version, queue; the `GET` verb is kept so as not to break clients.
- D-L41-01: outbound address control as soon as authentication is on (details in chapter 16).
- D-L39 (SEC-02, SEC-10): CORS closed by default, rate limiter: see `backend/ontoforge/hardening.py::add_cors`.

## 8. Pitfalls {#pieges}

- `fetch` is modified globally, when `AuthGate.tsx` is imported (guard `window.__ofFetch`). A test or script that does not import this module calls the real `fetch`: no CSRF, no `If-Match`. Every new write must go through `window.fetch` (not `XMLHttpRequest`, not `navigator.sendBeacon`).
- Seven clients, one send: `api.ts::req`, `eapi`, `fapi`, `qapi`, `aapi`, `gapi`, `settingsApi` (and `lib/proposal.ts`) go through `lib/http.ts::request`; there is no `fetch` + `detail` block left to copy (DF-F01, DF-F02, fixed in L52). Each client keeps its own error type: `fapi` never throws (it returns `{status, ok, data}`); the others throw `ApiError`, `SettingsError` or a plain `Error`. `frontend/tests/api_clients.test.mjs` fails if a client calls `fetch` again or re-reads `detail`, or if a hard-coded French network message comes back.
- Since L52, a validation-list `detail` is read by every client (before, `eapi`, `api.zip`, `formCall` and `lib/proposal.ts` accepted only the string, `fapi` did not read `detail` and left it to its callers; `aapi` and `gapi` already read the list). It is a safeguard: the backend returns a string today, so nothing changes on screen. A network error in `lib/proposal.ts` shows `ui.unreachable` instead of the browser's own message. The message shown to the user no longer mentions port 8000 (a developer hint): troubleshooting is in chapter [01](01-vue-ensemble-demarrage.en.md#depannage).
- The `BodyLimit` 413 follows the global language setting, not the account's: this filter runs before authentication.
- Replay: only add a route to `REPLAYABLE` (`rev.ts`) if replaying the body after a reload cannot overwrite anything.
- 429 not handled: no automatic retry; a chain of heavy calls (analysis, generation) can show an error instead of waiting.
- Adding a `GET` that writes: three places (see 4.1).
- Presence ≠ version: the three routes `/presence`, `/access`, `/activity` do not update the known version; if you add similar ones, extend `tracksRev`.

## 9. How to add… {#comment-ajouter}

### … an API call (read or write) {#ajouter-appel}

1. Server side: route and model (see the "Server side" section below); if the route carries `{pid}`, classify it in `backend/ontoforge/collab/routes.py` (a project route that is not classified is refused with 403 `unclassified`).
2. Front side: add the method to the area's client, with its type (mirror of the pydantic model). For a general call: `frontend/src/api.ts::api`, using `p(id)` for the URL.
3. A write needs nothing special: CSRF and `If-Match` are added by the global `fetch`. Go through `lib/http.ts::request` (never `fetch` nor a `detail` reading in the client). For a binary download, follow `api.zip`.
4. New server-side error text: write it in French and add it to the translation tables (`backend/ontoforge/localize/`), otherwise it stays French in the English interface.
5. Test: an API test (`backend/tests/test_api_contract.py` is the model) and, if the screen changes, a recipe (chapter 18).

### … a header exchanged between front and back {#ajouter-entete}

Front side, in the patched `fetch` (`AuthGate.tsx`); server side, read the header in the relevant layer; add its name to `CORS_HEADERS` in `backend/ontoforge/hardening.py` if it must pass through CORS.
