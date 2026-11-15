# Changelog {#journal-des-versions}

Format: by version, what changes for the user, then the detail per work package. Sources: reports `journal/L*/rapport*.md`, reviews, `journal/decisions.md`. Work packages are described in `lots/`.

## L43: password change for every account (15 Nov 2026) {#l43-mot-de-passe-tous-comptes-15-nov-2026}

Jerem's request of 15/11 (D-L43-01, replaces point 2 of D-L42-02).

- **Change your own password, for everyone.** Account menu › "Change my password": current password, new one (at least 10 characters), confirmation, show/hide, success message. The account's other sessions are closed, the current one stays open. Krakie help and guide ("Change my password").
- **Configuration accounts.** The new password is saved (argon2, `accounts.json`, 600) and masks the `ONTOFORGE_AUTH_USERS` one, which no longer works. An administrator can reset that password (provisional) or "revert to the configuration password". The Administration panel shows "Password redefined in the interface". The mask keeps priority if you later edit the hash in `.env`: a warning says so.
- **L42 review fixes.** L42-01: hashing no longer blocks the directory, 5 changes per minute per account. L42-03: the administration log is archived (`admin-audit.1.jsonl`…, adjustable) and an action whose trace fails is refused. L42-05: the password typed at creation is masked (with a show button).
- Detail: `docs/CONTRACTS.md` §17, D-L43-01. No version bump (D-L21-02).

## L42: accounts, per-account language, administrator on every project (15 Nov 2026) {#l42-comptes-langue-administration-15-nov-2026}

Jerem's answers to question Q-L40-1 (D-L42-01).

- **Per-account language.** Each account picks its language (French or English) in the account menu; it is stored on the server and applies to the interface, to Krakie's answers and to texts generated at display time, for that account only. The global setting becomes the default language for new accounts. Without authentication: unchanged.
- **No generation by the reader.** Generating (Exports screen, dashboard, zip archive) writes the project's history: it is now a write, reserved for editors and the owner (lock, `If-Match` version on a shared project, CSRF token, a line in the activity log). A reader sees a greyed-out "read-only" button, views the history and exports the ontology and the shapes.
- **Account administration.** New "Administration › Accounts" panel for administrators only: list (role, source, active, last sign-in), creation (provisional password generated and shown once, or typed), reset, disable, delete with project transfer, promote, administration log. The provisional password is changed at first sign-in; any account created in the interface can change its own. Accounts from `ONTOFORGE_AUTH_USERS` stay managed by the configuration. An active administrator always remains; a disabled or deleted account loses its sessions at once.
- **The administrator sees every project.** Owner column, "My projects / Shared with me / All" filter, the owner's rights on each project; their actions on someone else's project are traced "as administrator". Other accounts: unchanged.
- Details: `docs/CONTRACTS.md` §17, D-L42-01. No version bump (D-L21-02).

## L41: fixes from the security review (15 Nov 2026) {#l41-corrections-relecture-securite-15-nov-2026}

- **Outbound calls checked as soon as there are accounts.** With `ONTOFORGE_AUTH=password`, the server refuses to call an internal address (private network, loopback, cloud metadata), as in public mode. Without authentication (local use), nothing changes. For an internal endpoint or provider (Fuseki, Ollama), name it in `ONTOFORGE_EGRESS_ALLOW_INTERNAL`. Default choice D-L41-01, which you can change.
- **Addresses hidden from non-administrator accounts.** The Settings assistant and query error messages no longer give the host or port of a registered endpoint or provider, and no longer show the start of a refused host's response.
- **A read no longer writes to the project.** Generation history is in a side file; the initial business map is no longer saved by a plain read. An editor no longer loses changes while a generation runs.
- **Neutral sharing.** "Unknown account" and "already the owner" give the same answer.
- **Unreadable sharing file.** The project is locked read-only (administrator only), with a message and a log line, instead of being silently reassigned.
- **SHACL validation.** At most 2 validations at once (`ONTOFORGE_SHACL_SLOTS`), otherwise `503` with `Retry-After`; the child process sets its own ceilings and receives no key.
- **Other.** Wider "heavy" ceiling (conformance, graph, operations, exports, files); master key file tightened to 600; credentials also dropped when the port or scheme changes on a redirect; nginx keeps the port in the `Host` header (browser writes on port 8088 work with authentication).

## L39-secu: security fixes (15 Nov 2026) {#l39-secu-15-nov-2026}

- **Local instance closed by default.** `docker compose` now publishes the interface on `127.0.0.1` only (address set with `ONTOFORGE_BIND`, port with `ONTOFORGE_PORT`). CORS is closed (explicit list in `ONTOFORGE_CORS_ORIGINS`), and nginx sends a CSP and the usual security headers. An instance opened to the network without authentication is flagged in the logs at startup. The guide explains how to open it on purpose.
- **Hardened imports.** An RDF/XML file that declares a `DOCTYPE` or entities is refused. A JSON-LD file whose context is a remote address is refused. Very long RDF lists are capped (beyond 1,500 unrecognised triples, blank nodes are not renumbered; beyond 10,000, the file is refused). SHACL validation runs in a separate process, with bounded time and memory and a clear message.
- **Keys bound to their address.** Changing the address of an LLM provider or a SPARQL endpoint erases the stored key or token (to be entered again). Connection tests never send a stored secret to another address.
- **Rate limited.** The API limits requests per address and per session, more strictly for the assistant and costly routes. The answer is `429` with `Retry-After`.
- **Unprivileged containers, separate master key, reproducible builds.** Backend and front end run without root. The master key lives in a separate volume (`ontoforge-keys`). `npm ci` is strict and Python dependencies are installed at the exact versions of `backend/constraints.txt` (no version changed).
- **Assistant and explanations.** Imported content (documents, labels, attachments) is marked as untrusted data in the prompts. The assistant's explanation now shows only `http(s)` and `mailto` links, and no images. Cloud Run draft: outbound host list required, trust in `Forwarded` headers limited, container without root. Dead reasoner code removed.

## L40: named projects and collaborative sharing (15 Nov 2026) {#l40-partage-collaboratif-15-nov-2026}

- With authentication on, every project has an owner. You only see your projects and those shared with you; an inaccessible project answers "not found".
- "Share" button in the header: enter another account's identifier and a role (editor or reader). The owner changes a role, removes an access or transfers ownership; an editor can neither share nor delete. A reader views and exports, nothing more ("read-only").
- Working together without real time: presence dots, a "bob changed the project" banner, a clearly explained conflict (never a silent overwrite) with "Reload and reapply", an activity log on the dashboard.
- Global settings (LLM providers, keys, endpoints) are reserved for administrators (first account, or `ONTOFORGE_AUTH_ADMINS`).
- Without authentication nothing changes. On first start with authentication, existing projects go to the first administrator.
- Details: `docs/CONTRACTS.md` §16, D-L40-01.

## L38: Krakie in Settings (15 Nov 2026) {#l38-krakie-parametres-15-nov-2026}

- Krakie is now on the Settings screen, with no project open: the same aquarium and panel, a context of its own (the tab on display) and suggestions per tab. She explains, diagnoses and recommends; she changes no setting, you do the saving.
- With no LLM (the first-launch case: demo provider), she still answers, tab by tab: steps to connect Anthropic, an OpenAI-compatible server or Ollama, add a SPARQL endpoint, choose versions, set languages and defaults, with a diagnosis of the current state. With a real provider the model answers; if it fails, the built-in answer takes over.
- Three action cards: "Go to this section" (opens the tab, scrolls, highlights the block), "Test connection" (the existing provider or endpoint test) and "Open help" (the guide section for the tab).
- Privacy: Krakie never receives an API key, a password or a token (only "a key is stored: yes or no"), cannot send one back, and masks any you paste in the conversation. Addresses are reduced to host and port (no credentials, path or parameters); the base IRI keeps its path, with opaque segments masked.
- The "?" button is also on the Settings screen and opens the guide at the section of the tab on display; the guide opens with no project (`#/aide/…`). The guide now describes each tab in its own section.

## L37c: Krakie rests on the Files status bar (15 Nov 2026) {#l37c-fichiers-15-nov-2026}

- On the Files screen, the reef now sits above the status bar instead of covering it, and the problems list keeps a right margin so it never runs under Krakie.
- Any bar pinned to the bottom of a screen can say so (`data-ag-floor`), and the reef rests on it.

## L37b: Krakie's reef grows from the screen edge (15 Nov 2026) {#l37b-recif-krakie-15-nov-2026}

- The water halo from L37 is gone: no coloured blob over the cards any more. The reef grows from the bottom edge of the window, bottom right, in the app's own colours (theme teal, softened coral and starfish), in light and dark. Krakie swims just above it, with a few rare micro-bubbles. Only Krakie and the reef react to clicks; the rest of the area lets the mouse through. The keyboard focus is a discreet ring around Krakie, and the proposals badge stays. The editor minimap was raised accordingly.

## L37: Krakie in a small aquarium (15 Nov 2026) {#l37-krakie-aquarium-15-nov-2026}

- Krakie's floating button is no longer a disc: it is a small frameless aquarium (light water with soft edges, a pixel-art reef, a few micro-bubbles) in which Krakie swims slowly, pausing now and then. On hover she stops and turns towards the cursor; she still thinks, looks happy or worried as before. Click, Ctrl+K and label unchanged; smaller version on mobile; `prefers-reduced-motion` freezes Krakie and the bubbles. The editor minimap was moved up to make room.

## L36c: business map fixes (15 Nov 2026) {#l36c-corrections-carte-metier-15-nov-2026}

- An empty zone is no longer lost: the server keeps it, with its place on the map, and it survives a page reload.
- More accurate wording: “relationship declared in both directions” (inverse or symmetric, the symmetric one being drawn apart) and “a single direction kept for this scenario”; an `owl:disjointUnionOf` no longer makes a class “abstract”; the hierarchy link carries a translated “is a”; a banner flags properties that are not drawn (missing domain or range) and relationships declared on a union of classes.
- Counts: an individual of a subclass counts for the parent class, with no double counting.
- Generic default roles (main, component, hub, lookup, context, reference, document, settings) with new tints; previously saved roles are read as their equivalent. The inspector says whether a role is inferred or chosen.
- Mobile: the map opens at a readable zoom (at least 45%), “Fit all” gives the overview.
- API: `/business-map` routes added to the documentation (API, architecture, limits, glossary).

## L36b: business map (15 Nov 2026) {#l36b-carte-metier-15-nov-2026}

- New “Business map” screen (Design step, shortcut from the Target model): the schema of the ontology or of the target model in tinted business zones, types coloured by role with their count, curved arrows, frames, legend and scenario notes. Zoom, hover, pinning by drag, editable zones and scenarios, zone suggestions (five strategies) and frame suggestions, rearranging, undo, SVG and PNG ×2 or ×4 export. 21-step guided tour; Krakie knows the screen.

## L35: sidebar collapsible to icons (11 Nov 2026) {#l35-bandeau-lateral-repliable-en-icones-11-nov-2026}

- The left menu collapses into a strip of about 56 px (icons only, logo reduced to Krakie's head, steps as badges 1 to 4, tooltips on hover and keyboard focus, number of findings to decide as a badge on the icon). Button at the bottom of the sidebar or Ctrl+B; the choice is remembered in the browser.
- Automatic collapse on full-canvas screens (graphical editor, list view, files, documentation), unless the sidebar was kept open. Settings, Display tab: Automatic, Open or Collapsed. The editor canvas is refitted when the transition ends; `prefers-reduced-motion` removes the animation. Mobile unchanged.

## L30: Krakie comes alive in the hidden game (8 Nov 2026) {#l30-krakie-vivante-dans-le-jeu-cache-8-nov-2026}

- Fix: Krakie no longer gets distorted when she moves (no more sprite shear: the body stays intact and only the tentacles trail by one pixel).
- In "Krakie's Triple Catch", Krakie swims (6 frames, waving tentacles, a slight bounce) and leans in the direction she moves.
- Short expressions: a wink for each item caught, a big smile and sparkles for a complete triple, surprise for a bonus, a grimace with a slight shake for a lost finding or a broken IRI, and constant worry on a single life. A glass halo during the SHACL shield, a purple effect during inference. At the end of a game: a trophy for a record or 400 points, worry otherwise.
- A word is no longer both a target and a distractor of another category, and the background graph stays under the score banner. With `prefers-reduced-motion`: fixed expressions, no shake, bounce or lean.
- Fix: in the hidden game, Krakie no longer shows up as a flat teal square when a pose image fails to load (stale cached manifest, missing file): all poses are preloaded before play, otherwise a pixel-art silhouette replaces them; the play area stays centered from 390 to 2560 px; "doneBy" now reads "DONE BY".

## L29: Krakie the blacksmith (8 Nov 2026) {#l29-krakie-forgeronne-8-nov-2026}

- Krakie forges (two hammers on an anvil) during exports, analysis, shape generation and the draft from a document, in place of Krakie at the wheel. She then raises a graph-shaped trophy for about 2 s at the end of a successful run. Still frames with `prefers-reduced-motion`.
- New poses `forge` (8 frames) and `trophee` (4 frames). The "racer" pose stays in the sources of `design/krakie/` but is no longer displayed.

## L31: standard and target versions (8 Nov 2026) {#l31-versions-des-normes-et-des-cibles-8-nov-2026}

- Bundled `standards.json` reference (W3C, Neo4j, Cypher, Curiosity.Library, internal libraries); `GET /api/standards`.
- Versions per project with a global default in Settings; local check `versions/check`; Versions screen.
- Neo4j: `CYPHER 25` / `CYPHER 5` prefix query by query, constraints depending on the version. Curiosity: Curiosity.Library version in the headers and the README. The transposition report lists the versions. SHACL 1.2 features are disabled.
- Krakie: `quelles versions ?`, `mets à jour les versions`, and a gap bubble once per session.
- SHACL: the only published version is 1.0 (Recommendation of 20 July 2017). "SHACL 1.1" does not officially exist and is read only as a synonym of 1.0. Neo4j 4.4: only `schema.cypher` has a variant (ASSERT syntax, `À VÉRIFIER`).
- Krakie fix: a bare "help" now gets an English answer.

## 0.1.0: Iteration 1 (delivery planned for Tuesday 3 November 2026, ~7 pm, Paris, D-022) {#iteration-1-livraison-prevue-le-mardi-3-novembre-2026-19-h-paris-d-022}

> Status at the first L12 pass: the acceptance test at Jerem's (`docker compose up --build`, work package L7) has not happened yet and no work package has a `cloture.md` file. This version reflects the state of the repository on the evening of 3 November 2026.

### What's new {#nouveautes}

- Design: projects (empty, from the `automaint` and `trap` examples, or by file drop); a Protégé-style ontology editor; Quick input (DSL, one line = one axiom); import of Turtle, RDF/XML, JSON-LD, N-Triples, N3, TriG; export to Turtle, RDF/XML, JSON-LD, N-Triples, N3.
- Check: OWL 2 DL / EL / QL / RL conformance with specification references (W01 to W07) and best practices (BP01 to BP07).
- SHACL: import, generation from the ontology, validation of a data file (no inference by default).
- Transpose: an engine of 66 rules (+ S01, S02, G02) with *auto / to decide / lost* findings, options per target, a recommendation per target, decisions remembered and replayed, decisions grouped by rule, "Accept all recommendations".
- Generate: Curiosity (`Schema.cs`, `Edges.cs`, `RegisterSchema.cs`, `Connector.cs`), Neo4j (`schema.cypher`, `ingest.cypher`, `validation.cypher`, `model.mmd`), `schema.graphql`, transposition report, zip.
- Queries: SPARQL → Cypher / Curiosity / GraphQL translation with loss notes; competency questions.
- AI assistant: ontology draft from text, CSV or SQL, accepted element by element; proposed shapes; explanation of a finding; providers `anthropic`, `openai_compat`, `ollama`, `mock`.
- Docker: `docker compose up --build` (FastAPI backend + nginx frontend), projects persisted in the `ontoforge-data` volume.

### By work package {#par-lot}

| Package | Content | Reviews (verdicts) |
|---|---|---|
| L0 | Scoping: catalogue extended to 66 rules (36 + 30 added), severities of K02 and C05 corrected to `review`, oracle `samples/trap/expected-findings.yaml`, normative option vocabulary (D-031) | w3c: KO then fixes |
| L1 | Foundation: `core/*` (pydantic contracts), REST API (27 iteration 1 routes), project storage, RDF imports/exports, DSL, Dockerfile / compose | w3c it1: OK |
| L2 | Conformance (DL/EL/QL/RL profiles, W01 to W07, BP01 to BP07, optional reasoner), SHACL (import/export/generation/validation/translation to PG constraints); `validate` without inference by default (D-034, D-L2-01) | w3c it1: KO → it2: OK |
| L3 | Mapping engine: 66 rules implemented from iteration 1 (no `X00`), oracle 6/6 `must_not`, 66 expected findings, transposition report, grouping by rule, grouped decisions | w3c it1: KO → it2: OK |
| L4 | Curiosity, Neo4j and GraphQL generators; SPARQL translator; competency questions; xsd type maps per target | curiosity/neo4j cross it1: KO → it2: OK; w3c it1: KO, it2: KO |
| L5 | React interface: 7 screens + assistant panel, light/dark theme, screenshots in `journal/L5/screens/` | - |
| L6 | AI assistant: service, CSV/SQL parsers, JSON → `OntoModel` conversion, 4 providers | - |
| L7 | Acceptance plan (`journal/L7/plan-recette.md`) | acceptance at Jerem's to come |
| L13 (leftovers, iteration 2 brought forward) | `Decimal` (Curiosity without loss), reverse names (`mapping/reverse_names.py`), I01/C08 (reference nodes), readable diagram, script `tools/dotnet/check-curiosity.ps1` | w3c it1: KO (reverse name collisions) |

### L16 and L17 (4 November 2026) {#l16-et-l17-4-novembre-2026}

- L16: global Krakie (floating button, Ctrl+K, screen context, Apply / Undo cards, intents without an LLM).
- L17: rebuilt List view, rebuilt Shapes screen (inline editing, generation diff, validation), Queries: temporary endpoint, possible values without an endpoint, new logo. API: `dry_run` on `/shacl/generate`, `GET /query/options`, `POST /query/endpoint-test`. See `journal/L16/cloture.md` and `journal/L17/cloture.md`.

### Notable fixes from the reviews {#corrections-notables-issues-des-revues}

- Catalogue: `owl:hasKey` is never `auto` (K02, SS §9.5); a named `owl:equivalentClass` = `review` (C05); two `rdfs:domain` / `rdfs:range` = intersection (D12/O21), never union; a relation with 3 or more roles = R02, never R01.
- Engine: `some` / `min n` cardinalities are never read as "exactly 1"; flattened inheritance without a false obligation; non-simple properties without cardinality; property chains kept in order; complex domain/range → explicit G01.
- Generators: hexBinary / base64Binary and `rdf:langString` classified outside the OWL 2 map (loss); fallback key = IRI property, never an empty match pattern; Neo4j: Enterprise constraints separated.
- Translator: a class or property missing from the model = empty pattern + loss (never an untyped pattern); multiple types on the same discriminator = loss.
- Conformance: W07 ignores reused vocabularies (dcterms, skos...); `DisjointUnion` classified outside EL/QL/RL (confirmed).

### Structuring decisions {#decisions-structurantes}

D-002 (FastAPI + React), D-003 (Docker only), D-004 (SHACL from v0.1), D-005 (Curiosity first), D-006 (assistant subject to human review), D-028 (normative `core/*` contracts), D-031 (66 rules), D-034 (validation without inference), D-035 (finding identifier format), D-038 (no golden files), D-L13-01 (`Decimal`). Full list: `journal/decisions.md`.

### Known limits at delivery {#limites-connues-a-la-livraison}

Curiosity C# not compiled, Cypher not executed, external APIs `À VÉRIFIER`, no authentication. Details in [`limites.en.md`](limites.en.md).

## 0.2.0: Iteration 2 (delivery planned for Friday 6 November 2026) {#iteration-2-livraison-prevue-le-vendredi-6-novembre-2026}

> Status as of 4 November 2026: work packages L8, L9, L10, L11, L13, L14 (demo data, generation history) and L15 are delivered on the code side. The acceptance test (L14) and Jerem's validation are still to do. Backend tests: 528 green according to the L15 review (not rerun by the documentation writer). `npm run build` green according to the reports.

### What's new {#nouveautes-2}

- Path and dashboard: the interface follows Design → Check → Transpose → Generate; a dashboard per project (Krakie's next action, steps, findings per target, generations, perimeters); the "Abysse" design system (light / dark), IBM Plex; fr / en interface.
- Interactive graphical editor: canvas + collapsible inspector + tree + quick input; gestures (double-click = class, drag = subclass / property / disjointness, F2, Delete); undo / redo (200 levels); OWL 2 validation of each gesture (all or nothing); icons per class; semantic zoom.
- Perimeters: subsets of the ontology to transpose (several per project), `?perimeter=` on analysis and generation, findings P00 to P03.
- Settings: multiple LLM providers (type, URL, model, key encrypted on the server, connection test, default), languages, defaults (base IRI, prefixes, target, naming), multiple SPARQL endpoints (one active).
- Full-screen assistant: a conversation per project, provider choice, file upload (CSV, SQL, text, Markdown, 2 MB) with preview, quick actions, a proposal accepted or rejected element by element, also shown in the editor.
- Interactive querying: a guided sentence driven by the ontology and the shapes, value autocompletion from the endpoint, filters, columns, read-only execution, results as a table and a graph, SPARQL / Cypher / Curiosity / GraphQL side by side, saved queries, natural-language question (`POST /query/nl`, deterministic fallback).
- Krakie, an animated pixel-art mascot (8 poses).
- Generation history on the server (`GET /generations`); demo data `samples/automaint/automaint-demo-data.ttl` and `tools/demo/generate_demo_data.py`.
- Documentation: this guide updated (user, architecture, API, limits, glossary).

### By work package {#par-lot-2}

| Package | Content | Reviews |
|---|---|---|
| L8 | `settings/` (Fernet + HKDF, `ONTOFORGE_SECRET_KEY`, rotation), `api/settings.py`, multiple providers, `/assistant/chat` and `/upload`, Settings screen (CONTRACTS §4, D-L8-01) | - |
| L9 | `editing/` (operations, history, perimeters, graph, icons), `api/editing.py`, graphical editor (CONTRACTS §5, D-L9-01, D-L9-02) | - |
| L10 | Full-screen assistant, `lib/proposal.ts` store | - |
| L11 | Shell, kit, i18n, "Abysse" tokens, Krakie, dashboard | - |
| L13 | Iteration 1 leftovers: Decimal, reverse names (+ collision fix after the W3C review), I01 / C08, model diagram, `tools/dotnet/check-curiosity.ps1` | w3c it1 KO → fixed (475 tests green) |
| L14 | Generation history (§7), demo data (524 tests green) | - |
| L15 | Guided querying, multiple endpoints, `/query/nl` (CONTRACTS §6); engine fix (D-L15-01) | curiosity: approved with reservations (1 blocker fixed) |

### Notable fixes {#corrections-notables}

- Reverse: a derived return name can no longer reuse an existing OWL property (fallback `<Edge>Of<Source>`).
- Inheritance under an abstract class (D-L15-01): properties copied into each concrete leaf. Before, `DisplayName` disappeared from the C# schema of Technician / Garage / Customer / Brand. Rerun the analysis of existing projects.
- Decimal: Curiosity without loss; Neo4j `Float` with a flagged loss.
- I01 / C08: no more I01 finding for the members of `owl:oneOf`.
- Queries: discriminator filter kept by the translator; read-only safeguards.

### Structuring decisions {#decisions-structurantes-2}

D-L2-01, D-L4-02, D-L8-01 (encrypted settings), D-L9-01 (editor: all-or-nothing `/ops`), D-L9-02 (`NodeType.icon`, `info` severity: accepted, not yet implemented), D-L13-01 (`Decimal`), D-L15-01 (copy into the leaves). Plan: `docs/PLAN-IT2.md` (decisions of 3 and 4 November: Krakie, one active endpoint, Sparnatural-style querying with our own builder, natural language).

### Known limits {#limites-connues}

Curiosity C# and Query API not verified, Cypher not executed, external APIs `À VÉRIFIER`, no authentication, no SSRF filtering, real LLM providers not tried, no automated front-end test. Details: [`limites.en.md`](limites.en.md).

## 0.3.0 (in progress) {#en-cours}

Work packages L19 to L26, one per line. Details are in `journal/L<n>/rapport.md`.

- L19: embedded local triplestore per project (pyoxigraph 0.5.13), queries, RDFS / OWL RL inference, SHACL validation. Default graph = deduplicated union (D-L19-01). w3c and query reviews OK at iteration 2, documentation verified.
- L20: easter egg with Krakie, a small hidden game in the application (a hint is in Settings); scout review it1 OK.
- L21: standards and library watch (`docs/veille/`), Dependabot in flag-only mode (D-L21-01 to D-L21-03: no scheduled watch, no version bumps, manual Neo4j and Curiosity validation). w3c, neo4j and curiosity reviews OK.
- L22: built-in file editor ("Files" screen, CodeMirror 6, validation, diff preview, `/files` API); w3c and scout reviews OK at iteration 2.
- L23: humanizing the documentation and skills, step 1 (`humanizer` skill).
- L24: publishing, continuous integration (pytest, front-end build, manual acceptance runs) and supervised Dependabot.
- L25: start an ontology from a document (.txt, .md, .pdf) with a source excerpt, a "To confirm" badge and W3C checks; w3c and scout reviews it1.
- L32: reasoning with HermiT. A "Reason with HermiT" button in Conformance (consistency, unsatisfiable classes that you can click and that turn red in the editor, inferences you can add to the model through `/ops`, reclassified individuals; during the computation, Krakie the blacksmith and "HermiT is reasoning… (up to 30 s)", then a trophy if consistent or a worried Krakie otherwise), `POST /api/projects/{id}/reason`, Krakie intent `raisonne / vérifie la cohérence / run the reasoner`, Cloud Run image with Java by default (`WITH_REASONER=1`). Reviews: see `journal/L32/rapport.md`.
- L26: reading the ontology graph. A floating legend that shows only the encodings present, a "VOWL notation" mode (VOWL 2: classes as circles, external, equivalent and anonymous classes, datatypes, property characteristics), a "Show" menu with a density slider and a counter, SVG and PNG export of the graph as displayed, a "legend" step in the guided tour (19 steps). `GET /graph` stays backward compatible and gains (`external`, `equivalent`, `include=external,anonymous,thing`). w3c, scout, doc and humanizer reviews: see `journal/L26/rapport.md`.
- L28: built-in documentation (Documentation entry in the side menu, contents, search, links between files, offline), a "?" button per screen, Krakie `help` action, a tour step (20 steps). See "Built-in documentation and help" in `utilisateur.en.md`.
- L33: documentation in English. The user guide, limits, contributing, API and changelog pages exist as `.en.md` and are shown when the interface is in English. The "French only" banner now appears only on untranslated files (architecture, rules, glossary). Each heading of these files carries an explicit `{#id}`, identical in French and English, so the "?" button and Krakie open the right section in both languages. The `test_help_map.py` test checks the anchors in both versions.
- L34: screenshots in the documentation. About sixty images per language (fr and en, same automaint data) illustrate the guide, the limits and the contributing pages; clicking an image opens a viewer (Esc to close). They are generated by `node tools/docs/captures.mjs` and loaded on demand, outside the application code.
- L34d: bilingual exports and subclass cycle. The generated files (comments and headers of `Connector.cs`, `Schema.cs`, `Edges.cs`, `RegisterSchema.cs`, `schema.cypher`, `ingest.cypher`, `validation.cypher`, `schema.graphql`, the READMEs and the transposition report) follow the interface language, or the export's `?lang=fr|en` parameter; code and ontology labels are never translated. The import demo document and the questions of the no-LLM fallback also follow the interface language (new `automaint-requirements.pdf`, generated by `make_cahier_des_charges.py --lang en`). Fix: quick entry and `/ops` refuse a subclass that would close a cycle (message in fr and en, with the path and the offending line), and `/analyze` no longer answers 500 on a cycle that is already there: it reports it as a BP03 information finding.
