# 16. Cross-cutting security {#securite}

The security mechanisms that span several subsystems: where they are coded, what they guarantee, how to avoid bypassing them when adding code. Only the defensive design is described here. Attack scenarios and audit results stay in the secu agent's reports, outside this manual.

Sources read: `backend/ontoforge/main.py`, `backend/ontoforge/security.py`, `backend/ontoforge/hardening.py`, `backend/ontoforge/netguard.py`, `backend/ontoforge/childproc.py`, `backend/ontoforge/ratelimit.py`, `backend/ontoforge/io/safe_parse.py`, `backend/ontoforge/auth/`, `backend/ontoforge/collab/`, `backend/ontoforge/settings/crypto.py`, `backend/ontoforge/assistant/untrusted.py`, `backend/ontoforge/targets/justification.py`, `backend/Dockerfile`, `docs/CONTRACTS.md` §15, tests `backend/tests/test_security.py`, `backend/tests/test_netguard.py`, `backend/tests/test_sec_rdf.py`, `backend/tests/test_sec_network.py`, `backend/tests/test_sec_ratelimit.py`, `backend/tests/test_sec_assistant.py`, `backend/tests/test_sec_settings.py`, `backend/tests/test_sec_front.py`.

## Overview {#vue}

```mermaid
flowchart TD
  IN[HTTP request] --> RL[Rate: ratelimit.RateLimit]
  RL --> BL[Size: security.BodyLimit]
  BL --> SH[Headers: security.SecurityHeaders]
  SH --> AU[Session, CSRF, Origin: auth.middleware]
  AU --> CB[Per-project rights: collab.middleware]
  CB --> H[Handler]
  H --> PARSE[Inputs: io/safe_parse, per-module caps]
  H --> OUT[Outgoing calls: netguard]
  H --> CHILD[Heavy computations: childproc.run_limited, HermiT as subprocess]
  H --> LLM[LLM: untrusted.fence + action re-validation]
  H --> SEC[Secrets: settings.crypto, never returned]
```

## Mechanisms {#mecanismes}

| Area | Mechanism | Where | Chapter |
|---|---|---|---|
| Access | password authentication (argon2id), signed `HttpOnly` / `Secure` / `SameSite=Lax` cookie, revocation through `gen` | `backend/ontoforge/auth/` | [12](12-comptes-partage-admin.en.md#authentification) |
| Cross-site requests | `X-CSRF-Token` bound to the session and `Origin` check on every write (and on `GET`s that write) | `backend/ontoforge/auth/middleware.py::csrf_required` | [12](12-comptes-partage-admin.en.md#authentification), [02](02-communication-front-back.en.md) |
| Isolation | exhaustive table of project routes, fail closed (`unclassified`), 404 for an inaccessible project, sharing state outside the model | `backend/ontoforge/collab/routes.py::ROUTES`, `backend/ontoforge/collab/access.py::require` | [12](12-comptes-partage-admin.en.md#cloisonnement) |
| Rate | 60 s sliding windows per IP and per session: global 900, assistant 20, heavy 120, reasoner 10 per minute; 429 with `Retry-After`; login attempts with progressive delay | `backend/ontoforge/ratelimit.py`, `backend/ontoforge/auth/limiter.py` | [12](12-comptes-partage-admin.en.md#authentification) |
| Size | body limited to `ONTOFORGE_MAX_BODY_MB` (32 MB), through `Content-Length` then by counting received bytes | `backend/ontoforge/security.py::BodyLimit` | — |
| Headers | strict CSP (`default-src 'self'`, no external resource, `frame-ancestors 'none'`), `nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy`, `Permissions-Policy`, HSTS behind HTTPS, `Cache-Control: no-store` on `/api/*` | `backend/ontoforge/security.py::SecurityHeaders`, `CSP`; second copy served by nginx locally: `frontend/security-headers.conf` (both compared by `backend/tests/test_sec_network.py`, to be changed together: chapter [17](17-build-ci-deploiement.en.md#pieges)) | [15](15-front.en.md) |
| Produced documents | HTML justification file under CSP `default-src 'none'` (`STRICT_CSP`, the only own policy kept by `SecurityHeaders`, by exact equality), escaped texts | `backend/ontoforge/targets/justification.py` | [08](08-generateurs.en.md#justification) |
| RDF files | any `DOCTYPE` rejected in RDF/XML and TriX, remote JSON-LD contexts rejected, canonicalization and unrecognized triples capped | `backend/ontoforge/io/safe_parse.py::parse_into`; local triplestore: `check_xml`, `check_jsonld` in `backend/ontoforge/localstore/store.py::parse_to_store` | [04](04-import-export-rdf.en.md#garde-fous), [10](10-triplestore-local.en.md#chargement) |
| Other inputs | SQL / CSV / JSON Schema importers bounded (`Budget`), assistant document bounded, triplestore capped | `backend/ontoforge/importers/limits.py`, `backend/ontoforge/assistant/document.py`, `backend/ontoforge/localstore/store.py::limits` | [14](14-imports-schemas.en.md#bornes), [11](11-assistant-krakie.en.md#document), [10](10-triplestore-local.en.md#plafonds) |
| Outgoing calls | address control (http and https schemes, internal names and non-routable addresses rejected, single resolution and connection on the checked address, redirects re-checked, optional allowlist) | `backend/ontoforge/netguard.py` | below |
| Heavy computations | capped child processes (memory, CPU, no file writes, minimal environment, separate session); HermiT as a Java subprocess killed on timeout | `backend/ontoforge/childproc.py::run_limited`, `backend/ontoforge/conformance/hermit.py::_run_java` | [06](06-shacl.en.md#flux-validation), [10](10-triplestore-local.en.md#flux-requete), [05](05-conformite-owl-hermit.en.md#hermit-bornes) |
| SPARQL | read-only (updates rejected by the parser), forced `LIMIT`, timeout, `SERVICE` rejected locally | `backend/ontoforge/queries/endpoint.py`, `backend/ontoforge/localstore/runner.py::guard` | [09](09-requetes.en.md#endpoints) |
| LLM | imported content fenced as untrusted data, priority system rule, no action applied without a click, each action re-validated on the server | `backend/ontoforge/assistant/untrusted.py`, `backend/ontoforge/assistant/agent.py::build_actions` | [11](11-assistant-krakie.en.md#non-fiables) |
| Secrets | API keys and endpoint secrets encrypted (Fernet, key derived by HKDF), never returned by the API, masked in provider error messages; administration log without password or token | `backend/ontoforge/settings/crypto.py`, `backend/ontoforge/assistant/providers/base.py::_detail`, `backend/ontoforge/auth/accounts.py` | [12](12-comptes-partage-admin.en.md#parametres) |
| Start-up | dangerous authentication configuration = refusal to start; warnings if the instance listens beyond loopback without authentication, if `.env` is readable by others, if public mode has no outgoing allowlist; `/docs` and `/openapi.json` closed in public mode | `backend/ontoforge/auth/config.py::load_config`, `backend/ontoforge/hardening.py::startup_checks`, `backend/ontoforge/main.py::create_app` | — |
| Container | unprivileged user (uid 10001), `/data` and `/keys` owned by it, exact dependency versions (`constraints.txt`) | `backend/Dockerfile`, `backend/constraints.txt` | [17](17-build-ci-deploiement.en.md) |

## Outgoing calls: netguard {#netguard}

`backend/ontoforge/netguard.py` wraps httpx for SPARQL endpoints and LLM providers.

- When: on as soon as the instance is shared, `ONTOFORGE_PUBLIC=1` **or** `ONTOFORGE_AUTH=password` (`enabled`, D-L41-01). In local use without authentication, calls go through as is (Ollama on the machine, endpoint on the company network).
- How: `check_url` (scheme, credentials in the URL), `check_host` (internal names, non-standard numeric notations), `resolve_checked` (the name is resolved **once**, every address is checked by `ip_allowed`), then the TCP connection is made to the checked address (`_GuardedBackend`), TLS still being verified against the original name. `request` follows at most `MAX_REDIRECTS` (3) redirects, each re-checked.
- Intended exceptions: `ONTOFORGE_EGRESS_ALLOW_INTERNAL` exempts named internal hosts or addresses (with authentication); `ONTOFORGE_EGRESS_ALLOW` restricts destinations to a list. Some addresses stay rejected in every case (`_always_refused`).
- Messages: a refusal on an endpoint or provider saved by an administrator gives a generic message, without host or resolved address (L41); only a temporary endpoint typed by the caller gets the precise reason.

Entry point to use: `netguard.client(timeout)` (client with `post`) or `netguard.post(url, ...)`. A direct `httpx` call in a new module would bypass the whole control.

## Child processes {#processus-fils}

L41 rule: any computation whose cost depends on user input (shape regular expression, SPARQL query, reasoning) runs outside the server process, with a timeout enforced by killing the child. `backend/ontoforge/childproc.py::run_limited` starts `python -I` with a launcher that sets `RLIMIT_AS`, `RLIMIT_CPU`, `RLIMIT_FSIZE` then runs the script. Reduced environment (`minimal_env`), `cwd="/"`, separate session, no `preexec_fn`. The number of simultaneous children is bounded by non-blocking semaphores for SHACL, HermiT and OWL RL (saturation: a 503, or a note for OWL RL); local triplestore children (queries and inference, all projects) also have their places since L53 (`ONTOFORGE_LOCAL_STORE_SLOTS`, `localstore/store.py::child_slot`, 503 with `Retry-After`, DF-B13: before, N calls on N projects started N children); loading a file, which happens in the server and not in a child, also has its own places (`ONTOFORGE_LOCAL_STORE_LOAD_SLOTS`, `load_slot`) and a triple cap set for Cloud Run. HermiT follows the same rule through its own launcher (process group killed on timeout). OWL RL reasoning in the conformance check also goes through it since L52 (`backend/ontoforge/conformance/_owlrl_worker.py`, DF-B03: before, a thread abandoned on timeout kept computing). So does local triplestore inference (`backend/ontoforge/localstore/_infer_worker.py`, DF-B07: before, a direct `subprocess.run`, full environment and no memory or CPU cap). Each memory cap bounds one child, not their sum: on Cloud Run (2 GiB, one instance), `deploy/cloudrun/env.yaml` lowers the caps (chapter [17](17-build-ci-deploiement.en.md)), and the calculation is about the **worst-case sum**: server (175 MB) + for each family places × cap. `env.yaml` values (measurements and detail: chapter [17](17-build-ci-deploiement.en.md#plafonds-somme)): 175 (server at rest, 121 to 146 MB measured) + SHACL 1 × 320 + OWL RL 1 × 256 + HermiT 1 × (192 + 150 for the JVM) + triplestore children 1 × 640 + loading in the server 124 (50,000 triples per project) + in-memory disk 64 + one request body 12 (`ONTOFORGE_MAX_BODY_MB`, 32 by default) = **1933 MB, a 115 MB margin under 2048**. The test `test_b13_cloudrun_env_sum_at_worst_fits_in_2_gib` reads `env.yaml` back and fails if the sum exceeds 2048 MB: any change to a cap or a slot count goes through this calculation. The cap is an address-space cap, higher than the memory actually used (measured at about 0.7 GiB in total).

## Decisions {#decisions}

- D-L8-01: secrets encrypted, never returned.
- D-L21-02: no version upgrade without Jerem's decision, security updates included (proposed, then arbitrated).
- D-L40-01, D-L42-01: isolation, roles, CSRF on `GET`s that write.
- D-L41-01: outgoing address control as soon as authentication is on; messages without host details.
- L39-secu, L41: input safeguards, child processes, rate limiter, headers (CONTRACTS §15).

## Pitfalls and limits {#pieges}

- In-memory state (limiters, revocation, presence): valid for **one** instance; to be reviewed before any horizontal scaling.
- Local mode: without authentication, no access or egress protection; the start-up warning says so if listening is not local.
- New code: protections live in precise entry points (`parse_into`, `netguard`, `run_limited`, `ROUTES`, `fence`). A module that bypasses them inherits nothing: secu review is mandatory for any lot touching inputs, files, outgoing calls, secrets, authentication or the LLM (matrix in `docs/TEAM.md`).

## How to add… {#comment-ajouter}

**…a route.** Classify it in `ROUTES` (chapter [12](12-comptes-partage-admin.en.md#comment-ajouter)), add it to the limiter's `RULES` if costly, read RDF files through `parse_into`, bound every loop over an input.

**…an outgoing call.** Go through `netguard.client` or `netguard.post`, with a timeout; never return the body of a remote response in an error message when `netguard.enabled()` is true.

**…a costly computation.** A standalone script started by `childproc.run_limited`, JSON input and output, a slot semaphore and a "busy" error as 503 (model: `backend/ontoforge/shacl/validate.py`).

**…text sent to the LLM.** Any content that does not come from the person typing goes through `fence`; every system prompt through `guard`.
