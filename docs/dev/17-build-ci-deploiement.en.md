# 17. Build, CI, Docker, Cloud Run, GitHub publication {#build-ci-deploiement}

How the code becomes an image, how continuous integration checks it, how the demo is deployed on Google Cloud Run and how the working repository is published to GitHub. The operator's step-by-step deployment commands are in `deploy/cloudrun/README.md` (not to be copied here): this chapter only explains the mechanics. Back to the [index](README.en.md).

State verified on 23 November 2026. No Docker build was run for this chapter (decision D-012: Docker is not available on the agents' machine); what concerns images was read from the files.

## 1. Role {#role}

Three paths produce OntoForge: (1) `docker compose` for local use (two containers), (2) the single image of `deploy/cloudrun/Dockerfile` for Cloud Run, (3) the front-end build in development (`npm run build`). GitHub CI checks the backend, the front end and the dependencies; Playwright recipes run on demand. No secret is in the repository.

## 2. Files and responsibilities {#fichiers}

| File | Responsibility |
|---|---|
| `frontend/package.json`, `frontend/package-lock.json` | front-end dependencies (exact versions), scripts `dev`, `build`, `preview`, `test` |
| `frontend/vite.config.ts` | React plugin, `/api` proxy in dev, `server.fs.allow: ['..']` to read `docs/guide` |
| `frontend/tsconfig.json` | strict TypeScript, `noEmit` (only Vite emits) |
| `frontend/Dockerfile` | front-end build (Node 22) then unprivileged nginx |
| `frontend/nginx.conf`, `frontend/security-headers.conf` | local server, `/api` proxy, security headers |
| `backend/Dockerfile` | backend image for `docker compose` (Python 3.12-slim + Java) |
| `backend/pyproject.toml`, `backend/constraints.txt` | dependencies and exact constraints |
| `docker-compose.yml` | three services (`init-perms`, `backend`, `frontend`), two volumes |
| `deploy/cloudrun/Dockerfile` | single production image (API + compiled front end) |
| `deploy/cloudrun/cloudbuild.yaml` | manual build by Cloud Build |
| `deploy/cloudrun/cloudbuild-trigger.yaml`, `trigger-main.yaml` | automatic deployment on a push to `main` (trigger) |
| `deploy/cloudrun/env.yaml` | non-secret service variables |
| `deploy/cloudrun/deploy-demo.ps1`, `deploy-demo.bat` | one-command update from Windows |
| `.github/workflows/ci.yml` | continuous integration |
| `.github/dependabot.yml` | dependency watch |
| `.dockerignore`, `.gcloudignore` | what stays out of the build context |
| `tools/git/publish.sh` | publication of the working repository to the GitHub clone |

## 3. Front-end build {#build-front}

- `npm run build` = `tsc -b && vite build`: type checking **blocks** the build (there is no linter otherwise). Measured on 23/11: about 23 s, entry module 642 kB (198 kB gzip), one chunk per screen and per guide page.
- `npm ci` (never `npm install`) in the images: the `package-lock.json` lock is authoritative, and the build fails if it diverges from `package.json` (SEC-14).
- Embedded documentation: `frontend/src/lib/docs.ts` imports `docs/guide/*.md` and `backend/ontoforge/assistant/help_map.json` by relative path **outside `frontend/`** (`import.meta.glob`). Hence the Docker build context is the repository root, and the Dockerfiles do `COPY docs/guide /docs/guide` and `COPY backend/ontoforge/assistant/help_map.json …` before `npm run build`. `.dockerignore` only lets `docs/guide` through: the `docs/dev` manual enters neither the image nor the app.
- CSP: `script-src 'self'`, no third-party resource (self-hosted fonts and icons, compiled guide, no CDN). A component that added an external script or font would be blocked (chapter 16).

## 4. Docker images {#docker}

```mermaid
flowchart LR
  subgraph LOCAL[docker compose]
    I[init-perms\nroot, chown of volumes] --> B[backend\npython:3.12-slim + Java\nuvicorn :8000]
    B --> F[frontend\nnginx-unprivileged 1.27-alpine :8080]
  end
  subgraph PROD[deploy/cloudrun/Dockerfile]
    S1[front stage\nnode:22-alpine\nnpm ci, npm run build] --> S2[runtime stage\npython:3.12-slim\nuvicorn :$PORT + /app/static]
  end
```

- Local: `docker-compose.yml` builds two images from the root (`backend/Dockerfile`, `frontend/Dockerfile`). The backend never runs as root; `init-perms` fixes the rights of volumes created by an earlier version. The port is published on `127.0.0.1` only by default (`ONTOFORGE_BIND`).
- Production: a single container. Why not nginx + uvicorn in one container: Cloud Run runs only one main process, a supervisor would make the image heavier and mix the logs. The front end is an SPA served to few visitors, uvicorn with GZip is enough, and authentication, security headers and SPA fallback live in the same place as the API (`backend/ontoforge/security.py::SpaStatic`).
- Reasoner: build argument `WITH_REASONER` (1 by default): installs `default-jre-headless` and the `reasoner` extra; at 0, the image is lighter and `POST /reason` answers 501.
- Reproducibility: `pip install -c constraints.txt` (exact versions, transitive ones included; consistency tested by `backend/tests/test_sec_network.py`), `npm ci`, base images by tag. The `sha256` digests of the base images are `À VÉRIFIER` (never determined for lack of network access, see the Dockerfile comment).
- User: unprivileged uid 10001; the `/data` volume (a mounted bucket in production) must belong to it.
- Both images start as the `ontoforge` user and read their configuration from the environment: `ONTOFORGE_DATA`, `ONTOFORGE_SAMPLES`, `ONTOFORGE_STATIC_DIR` (production), `ONTOFORGE_PUBLIC`, `ONTOFORGE_AUTH`, `ONTOFORGE_SECRET_FILE`, `ONTOFORGE_LLM_PROVIDER`… The production CMD **refuses to start** without `ONTOFORGE_EGRESS_ALLOW` (hosts reachable by outbound calls).

## 5. Continuous integration {#ci}

`.github/workflows/ci.yml` (decision D-L21-03: limited scope; no Neo4j and no C# compilation in CI). Triggers: push to `main`, pull request, manual dispatch (option `recettes`). Permissions `contents: read`. Actions are **pinned by commit SHA** (version in a comment); Dependabot proposes the new SHAs.

| Job | Content | Blocking |
|---|---|---|
| `backend` | Python 3.12, `pip install -c backend/constraints.txt -e "backend[dev]"`, `pytest -q` with `ONTOFORGE_LLM_PROVIDER=mock` | yes |
| `audit-dependances` | `pip-audit` on `backend/constraints.txt` (production: blocking); on the dev extra: informative | production: yes |
| `frontend` | Node 22, `npm ci`, `npm run build` | yes |
| `recettes` | manual: build, Playwright and Chromium installation, `tools/recette/e2e_ui.mjs`, `tools/recette/e2e_api.py`; screenshots as an artifact | manual |

Good to know: the `recettes` job creates a link `/home/claude/venv/bin/python` to the CI interpreter because the scripts hard-code it (chapter 18); Playwright is installed there **with no pinned version** (`npm install --no-save playwright`, DF-F07). CI does not run `npm test` (the 4 Node tests of the Markdown renderer also run through `backend/tests/test_sec_front.py`). The documentation tests (`backend/tests/test_dev_docs.py`, `test_docs_bilingual.py`) run with `pytest`.

Dependabot (`.github/dependabot.yml`): reports every Monday 6:00 (pip, npm), monthly (docker, actions); groups `semantique` (rdflib, pyshacl, owlrl, pyoxigraph, owlready2), `web`, `tests`, `codemirror`, `graphes`; **no major bump**, no merge without Jerem's approval (D-L21-02).

## 6. Deployment on Cloud Run {#cloud-run}

```mermaid
flowchart LR
  DEV[Jerem's machine] -->|git pull + deploy-demo.ps1| CB[Cloud Build\ncloudbuild.yaml]
  GH[GitHub main] -->|trigger, manual approval| CB2[Cloud Build\ncloudbuild-trigger.yaml]
  CB --> AR[(Artifact Registry\nontoforge:demo-YYYYMMDD-HHMM)]
  CB2 --> AR
  AR -->|gcloud run services update --image| CR[Cloud Run: ontoforge\n1 instance max, 2 Gi]
  SM[(Secret Manager\nmaster key, accounts)] --> CR
  BK[(Cloud Storage bucket\nmounted on /data)] --- CR
  CR --> DOM[domain ontoforge.ajlx.fr]
```

- First install: steps 0 to 6 of `deploy/cloudrun/README.md` (services, image repository, bucket, service account, secrets, `gcloud run deploy`, domain). Service settings: one instance maximum, 1 CPU, 2 Gi, port 8080, 300 s timeout; secrets (`ONTOFORGE_SECRET_KEY`, `ONTOFORGE_AUTH_USERS`) mounted from Secret Manager; non-secret variables from `deploy/cloudrun/env.yaml` (administrator, outbound hosts, SHACL and HermiT caps); Cloud Storage volume on `/data` with `uid=10001,gid=10001`.
- Update: `services update --image` changes **only the image**; a change to `env.yaml`, secrets or the volume needs the full `gcloud run deploy`.
- Automatic deployment (README §8): a Cloud Build trigger on a push to `main` runs build / push / update (`cloudbuild-trigger.yaml`) with a minimal-role service account and **manual approval required**. `SHORT_SHA` only exists with a trigger: this file is not for `gcloud builds submit`.
- State: the instance keeps nothing on its disk; projects and settings are in the bucket; the local triplestore lives in `/tmp/ontoforge-triplestore` (variable `ONTOFORGE_LOCAL_STORE_DIR`, set in `deploy/cloudrun/Dockerfile`, read by `backend/ontoforge/localstore/store.py::local_dir`; lost when the instance stops).
- Costs and shutdown: section "Coûts et arrêt" of the deployment README.
- The commands of README section 8 were not executed by the agent team (the README says so); the rest of the deployment is operated by Jerem from Windows (`À CONFIRMER`: no execution log in the repository). The cloud project identifiers are in the operator's scripts, not in this manual.

## 7. GitHub publication {#publication}

The working repository (`/home/claude/OntoForge`, with its lots, journals and screenshots) is **not** the GitHub one. `tools/git/publish.sh "message" [--push]`:

1. exports the **committed** state of `HEAD` (`git archive`), never the working tree;
2. removes `ref/`, `journal/securite/`, `journal/L18/video/` and `*.whl`;
3. searches for secrets (families of API keys, PEM blocks, password hashes, `.env` files, API keys in `settings.json`); the exact patterns and exceptions stay in the script; a hit **cancels** the publication;
4. synchronises into the publication clone (`/home/claude/ontoforge-pub` by default, variables `ONTOFORGE_SRC`, `ONTOFORGE_PUB`, `PUBLISH_BRANCH`) then commits with the attribution lines;
5. pushes only if `--push` is given.

The team protocol wants only the `git` agent to push, after green tests, review verdicts and documentation (`docs/TEAM.md`, sheet `.claude/agents/git-release.md`). The `docs/dev/` manual is therefore published with the rest: it must never contain a secret or audit detail (`test_dev_docs.py` checks this).

## 8. Decisions {#decisions}

- D-003: Docker; **D-012**: no Docker in the agents' build environment.
- D-L21-02: stable base (React 18, Vite 5, no bump). **D-L21-03**: CI limited to backend tests, front-end build and manual recipes.
- L39-secu (SEC-11, SEC-12, SEC-14, SEC-16): unprivileged execution, identical security headers in nginx and in the server (compared by `backend/tests/test_sec_network.py`), strict `npm ci` and exact Python constraints, mandatory egress list in public mode.
- L46 (D-L46-01): fastapi and starlette bump recorded in `backend/constraints.txt`.

## 9. Pitfalls {#pieges}

- Changing `docs/guide/` **without rebuilding** the front end: the app embeds the old version.
- Adding a file outside `frontend/` imported by the front end: also add it to the Docker context (`COPY`) in **both** Dockerfiles; otherwise the Docker build breaks while the local build passes.
- `nginx.conf` sets no compression (`À CONFIRMER`: image default) whereas production compresses (Starlette GZip): the weight of the entry (642 kB) is mostly felt in local Docker.
- Security headers exist in **two copies** (`frontend/security-headers.conf` and `backend/ontoforge/security.py::CSP`): change them together; the test compares them.
- nginx `include`: `add_header` is not inherited by a `location` that declares one, hence `include …/ontoforge-security-headers.conf` in **every** block.
- `services update --image` does not pick up `env.yaml`.
- CI uses Python 3.12, the agents' venv 3.13: any behaviour difference is `À CONFIRMER`.
- `/api`: nginx hides the backend's security headers (`proxy_hide_header`) so as not to double them, then sets its own.

## 10. How to add… {#comment-ajouter}

### … a front-end dependency {#ajouter-dependance-front}

Add the **exact** version to `frontend/package.json` (no `^`), regenerate `frontend/package-lock.json` with `npm install --package-lock-only`, check `npm ci && npm run build`, and note the reason in chapter 15. If it loads external resources, check the CSP.

### … a backend dependency {#ajouter-dependance-back}

Exact version in `backend/pyproject.toml` **and** in `backend/constraints.txt` (with its transitive ones); `pip-audit` must report nothing; mention the decision if it is a bump (D-L21-02).

### … a CI job {#ajouter-job-ci}

In `.github/workflows/ci.yml`, with actions pinned by SHA (copy the existing style); if a secret is needed, **do not** add it without approval (none is used today).

### … a production environment variable {#ajouter-variable-prod}

Non-secret: `deploy/cloudrun/env.yaml` then a full deployment. Secret: Secret Manager then `--set-secrets` (README §3 and §5). Document it in `.env.example` for local use.

### … a deployment configuration file {#ajouter-fichier-deploiement}

No secret, no project identifier: resource names and Cloud Build substitutions (`_REGION`, `_REPO`, `_SERVICE`), like `cloudbuild-trigger.yaml`.
