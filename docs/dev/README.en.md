# OntoForge Developer Manual {#manuel-developpeur}

This manual describes how OntoForge is coded: where each function lives, which libraries (exact versions) and why, how the pieces talk to each other, which pitfalls await the next developer, and how to add a screen, a rule, a route or a recipe. It is written for someone taking over the project without the agents who wrote it. To *use* OntoForge, read the user guide (`docs/guide/utilisateur.en.md`); for the rule catalogue, `docs/guide/regles.en.md`. Version française : [README.md](README.md).

State verified on 23 November 2026 (lot L51, decision D-L51-01). The manual is published on GitHub with the rest of the repository and is **not embedded in the application**.

## 1. Index {#sommaire}

| # | Chapter | Content |
|---|---|---|
| 01 | [Overview and getting started](01-vue-ensemble-demarrage.en.md) | layout, libraries, running in dev (venv, Docker), tests, recipes |
| 02 | [Front ↔ back communication](02-communication-front-back.en.md) | `frontend/src/api.ts`, FastAPI routes, sessions and CSRF, `If-Match` / 409 / 428, limiter, errors, downloads, proxy |
| 03 | [Internal model](03-modele-interne.en.md) | `core/`: ontology, project, property graph model |
| 04 | [RDF import and export](04-import-export-rdf.en.md) | rdflib, formats, JSON-LD, input guards |
| 05 | [OWL 2 conformance, lint, HermiT](05-conformite-owl-hermit.en.md) | profiles, lint, reasoner in a subprocess |
| 06 | [SHACL](06-shacl.en.md) | shape generation, bounded pySHACL, meta-validation |
| 07 | [Analysis engine and rule catalogue](07-moteur-analyse.en.md) | auto / to-arbitrate / lost findings, reclassification, oracle |
| 08 | [Generators](08-generateurs.en.md) | Curiosity (C#), Neo4j (Cypher), GraphQL, report, justification file |
| 09 | [Queries](09-requetes.en.md) | SPARQL → Cypher / C# translation, endpoints |
| 10 | [Local triplestore](10-triplestore-local.en.md) | pyoxigraph |
| 11 | [Krakie assistant](11-assistant-krakie.en.md) | agent, proposed actions, LLM providers, guardrails |
| 12 | [Accounts, sharing, administration](12-comptes-partage-admin.en.md) | presence, activity log |
| 13 | [Projects and versions](13-projets-versions.en.md) | storage, undo / redo, SemVer versions |
| 14 | [SQL, CSV, JSON Schema imports](14-imports-schemas.en.md) | deterministic import |
| 15 | [Front end: shell, state, design system, i18n, editors, phone](15-front.en.md) | `frontend/src/` |
| 16 | [Cross-cutting security](16-securite.en.md) | netguard, CSP, hardening, subprocesses (no exploitable detail) |
| 17 | [Build, CI, Docker, Cloud Run, publication](17-build-ci-deploiement.en.md) | from source to production |
| 18 | [Tests](18-tests.en.md) | pytest, oracle, Playwright recipes, screenshots |

Each chapter also exists in French (`NN-subject.md`, same anchors).

## 2. Reading paths {#parcours}

| I want to… | Read, in order |
|---|---|
| understand the project in an hour | 01, then §2 of 02, then 07 |
| **understand a front-end call** down to the server code | 02 (sequence diagram), 15 §4, then the chapter of the subsystem called |
| **add a transposition rule** | 07 (catalogue, detection), 08 (effect on generated code), 18 §4 (oracle), `docs/RULES.md` |
| add or change a generator | 03 (`PGModel`), 08, 18 |
| **add an API route** | 02 §9, 12 (per-project classification and roles), 03 (models), 18 |
| **add a screen** | 15 §13, 02 §9, 18 §11 |
| add a language or a text | 15 §6, `skills/i18n-ecriture-sure/SKILL.md` |
| understand sessions, sharing, conflicts | 12, 02 §4, 13 |
| understand the assistant and its guardrails | 11, 16, 15 §5 |
| touch import / export | 04, 14, 03 |
| deploy or fix CI | 17, 16, `deploy/cloudrun/README.md` |
| harden or audit | 16, 02 §4.1 and 4.4, 17 §4 |
| write a recipe or a test | 18, 01 §5.3 |

## 3. Manual conventions {#conventions}

- Plan of every chapter: role; files and responsibilities; flow (Mermaid diagram); libraries with exact version and reason; key structures; decisions (D-xxx); pitfalls; "how to add…".
- Citing code: a path from the repository root in backquotes, for example `backend/ontoforge/ratelimit.py`. A symbol is cited `path::symbol` (function, class or module-level constant; `path::Class.method` for a member; `path::object.member` in TypeScript). No line numbers (they move).
- Automatic check: `backend/tests/test_dev_docs.py` checks that every cited path exists, that every `path::symbol` exists in the file, that headings and `{#id}` anchors are identical in fr and en, that internal links are valid, that the 18 chapters exist and that no reference to a file of the security-audit folder and no secret appears. Code blocks are not checked.
- Examples: a path or symbol that does not exist yet (file to create, hypothetical name) is prefixed with `exemple:` inside the backquotes (`exemple:frontend/src/screens/Nouveau.tsx`); patterns containing `<n>`, `*`, `…`, `{x}` or a space are not checked either.
- Anchors: every level-1 or level-2 heading carries a `{#id}` anchor; the anchor is not translated. Internal links point to these anchors (`02-communication-front-back.en.md#if-match`).
- What is not verified is marked `À CONFIRMER` (to be confirmed) and listed in §5 [Open points](#points-ouverts); an external API not confirmed in the code is marked `À VÉRIFIER`.
- References: `D-xxx` refers to `journal/decisions.md`; `DF-Fxx` / `DF-Bxx` to `journal/L51/defauts.md` (code defects noted while writing; their L52 fix is described in `journal/L52/`); `SEC-xx` to security findings summarised in chapter 16 (audit reports are not published).
- Versions: read from `backend/pyproject.toml`, `backend/constraints.txt`, `frontend/package.json`.
- Nothing sensitive: no secret, no cloud project identifier, no exploitable vulnerability detail.
- Language: the manual is in French and English; code, file names and identifiers stay as in the repository (interface keys are in French, function names in English).

## 4. Other documents {#autres-documents}

| Document | What for |
|---|---|
| `docs/guide/architecture.en.md` | module catalogue (user / architecture viewpoint) |
| `docs/CONTRACTS.md` | frozen interface contracts (API, models) |
| `docs/RULES.md` | normative catalogue of transposition rules |
| `docs/PLAN.md`, `journal/decisions.md` | plan and decisions |
| `docs/TEAM.md` | agent team protocol, lot cycle, reviews |
| `docs/guide/contribuer.en.md` | contribution guide |
| `skills/` | reusable methods (documentation, recipes, i18n, deployment…) |

## 5. Open points {#points-ouverts}

What the manual could not verify (marked `À CONFIRMER` in the chapter). Code defects are listed in `journal/L51/defauts.md`.

| Chapter | Point | Why it is not verified |
|---|---|---|
| [02 §4.7](02-communication-front-back.en.md#proxy) | `Host` header kept by Vite's proxy (default `changeOrigin`) when authentication is on | not run with accounts enabled |
| [05](05-conformite-owl-hermit.en.md#hermit-installation) | Java version in a built Docker image (the `default-jre-headless` of Debian 13) | Docker builds are not possible in the working environment (D-012); 21.0.12.1 is the test environment's version |
| [06](06-shacl.en.md#pieges) | Behaviour of `childproc.run_limited` on Windows (`resource` missing) | not tested, the application runs in a Linux container |
| [11](11-assistant-krakie.en.md#fournisseurs) | D-006 mentions Bedrock, which is absent from the code: meant to go through an OpenAI-compatible endpoint | open question for Jerem, no code shows it |
| [17](17-build-ci-deploiement.en.md#pieges) | Compression in `nginx.conf` (default of the nginx image) | image not built here |
| [17](17-build-ci-deploiement.en.md#cloud-run) | Actual execution of the deployment commands | the operation is done by Jerem, no log in the repository |
| [17](17-build-ci-deploiement.en.md#pieges), [18](18-tests.en.md#pieges) | Behaviour gap between Python 3.12 (CI, images) and 3.13 (agents' venv) | the working venv is on 3.13; the suite was not replayed on 3.12 |
