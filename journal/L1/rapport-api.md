# L1 — Rapport API (lead)

Date : 2026-11-02 (soir). Référence : `docs/CONTRACTS.md` §1–§2.
Tests : `cd backend && /home/claude/venv/bin/python -m pytest -q tests/test_store.py tests/test_api_projects.py tests/test_api_contract.py` → **21 passed**. Suite complète verte au moment du rapport.

## Livré
| Fichier | Contenu |
|---|---|
| `backend/ontoforge/projects/store.py` | `list_projects()`, `get(id)`, `save(project)`, `delete(id)` + `create(name, description)`, `write_file/read_file` (fichiers annexes, ex. `data.ttl`). Dossier `$ONTOFORGE_DATA/projects/<id>/` (défaut `./data`) : `project.json` (source de vérité), `decisions.json`, `onto.ttl` / `shapes.ttl` réécrits à chaque save si `io.rdf_export.serialize` / `shacl.export_shapes.serialize_shapes` existent (import paresseux ; échec d'export journalisé, ne bloque pas le save). Id = `slug(nom)[:40]-<6 hex uuid>`, regex `^[a-z0-9][a-z0-9-]*$` (anti-traversée). Écriture atomique (tmp + fsync + `os.replace`). Horodatage ISO 8601 UTC. |
| `backend/ontoforge/samples.py` | `list_samples()`, `get_sample(name)`. Racine `$ONTOFORGE_SAMPLES`, défaut `<dépôt>/samples`. Classement : `*-shapes.*` → shapes, `*-data.*` → data, autres `.ttl/.owl/.rdf/.jsonld/…` → ontologie. Titre : `title.txt` ou 1re ligne de `README.md`, sinon nom du dossier. |
| `backend/ontoforge/api/` | `_common.py` (import paresseux → 501, 404 projet, 422 cible/parsing), `system.py`, `projects.py`, `analysis.py`, `assistant.py`. **Les 27 (méthode, chemin) de CONTRACTS §2** sont présents (vérifié par `test_api_contract.py::test_all_contract_routes_exist`). |
| `backend/ontoforge/main.py` | Montage des routers, CORS ouvert (`ONTOFORGE_CORS_ORIGINS`, défaut `*`), handler 422 en français (`detail` lisible + `errors` brut). |
| `backend/Dockerfile`, `docker-compose.yml` | Contexte de build = racine (voir ci-dessous). |
| `backend/tests/test_store.py`, `test_api_projects.py`, `test_api_contract.py` | Store sur `tmp_path` ; cycle projet complet avec services factices injectés via `sys.modules` ; 501 attendus pour chaque endpoint quand le module manque (et quand la fonction manque). |

## Comportements à connaître (front et autres agents)
- **501** : `{"detail": "module <pkg.mod> pas encore disponible"}` dès que `ontoforge.<pkg.mod>` ne s'importe pas ou n'expose pas la fonction attendue. CRUD, PUT onto/shapes, health, samples fonctionnent sans aucun module de service.
- **422 parsing** : `{"detail": "Impossible de lire l'ontologie « x.ttl » : <message du parseur>"}` (idem shapes, données SHACL). Fichier vide → 422.
- `POST /projects` → **201**. Avec `sample`, ontologie + shapes parsés (501 si `io.rdf_import` / `shacl.import_shapes` absent, rien n'est créé), `*-data.ttl` copié en `data.ttl` dans le dossier projet, warnings d'import dans `project.notes`.
- `GET /projects` → `[{id, name, description, updated_at, target, stats{classes, object_properties, datatype_properties, individuals, shapes}}]`, tri par `updated_at` décroissant.
- `PUT /projects/{id}` : `id` et `created_at` du chemin / de l'existant sont conservés. `DELETE` renvoie le projet supprimé.
- `POST /import` : `kind=auto` (défaut) → shapes si le texte contient l'espace de noms SHACL et `NodeShape`/`PropertyShape`, sinon ontologie ; réponse `{project, warnings, kind}` (`kind` = type retenu, champ en plus du contrat). L'import **remplace** l'ontologie (ou les shapes).
- `POST /dsl` : `merge=true` → `parse_dsl(text, base=project.onto)`, sinon base `None` ; le modèle renvoyé est sauvegardé.
- `GET /export/ontology?format=` : `turtle|xml|json-ld` (+ `nt|n3|trig`), en-tête `Content-Disposition`.
- `GET /conformance` : `check_conformance(onto, None)` (pas de graphe brut conservé en it1).
- `POST /shacl/generate {merge}` : merge = ajoute les shapes générées sans écraser les existantes.
- `POST /shacl/validate` : format des données déduit de l'extension (`.ttl`→turtle, `.owl/.rdf`→xml, `.jsonld`→json-ld…).
- `POST /analyze?target=` (défaut `project.target`) : `analyze(onto, shapes|None si vide, target, project.decisions[target])`.
- `PUT /decisions/{target}` : fusion `{finding_id: option_id}` ; `null` supprime la décision ; non persisté si le moteur est absent (501).
- `POST /decisions/{target}/accept-recommended` : pour chaque finding `review|lost` non arbitré ayant `recommended`, enregistre la recommandation puis réanalyse.
- `GET /generate/{target}` → `{files, missing}` : agrège `targets.<target>`, `targets.graphql`, `targets.report` (ceux qui existent ; `missing` = modules absents, champ en plus). 501 si aucun n'existe ou si `mapping.engine` manque. Accepte un `generate` qui renvoie `dict[nom, contenu]` (CONTRACTS) **ou** `list[GeneratedFile{path, content}]` (D-017). `/zip` : fichiers sous `<id>-<target>/`.
- `queries/*` : `?target=` (défaut `project.target`), le PGModel est recalculé avec les décisions du projet.

## Assistant (L6) — signatures attendues dans `assistant/service.py` (proposition, à confirmer par le pilote L6)
`status() -> {provider, model, configured}` ; `draft(text, kind, base_iri) -> {proposal, explanation, warnings}` ; `propose_shapes(onto, shapes) -> {proposal, explanation}` ; `explain(finding: Finding, target, onto) -> str | {text}`. Les routes `/api/assistant/*` renvoient 501 tant que ce module n'existe pas. Si L6 choisit d'autres noms, adapter `api/assistant.py` (une ligne par route).

## Docker — samples dans l'image (modifié)
Le contexte de build backend passe à la racine du dépôt :
```yaml
# docker-compose.yml
  backend:
    build:
      context: .
      dockerfile: backend/Dockerfile
```
`backend/Dockerfile` reproduit l'arborescence `/app/backend` + `/app/samples` (WORKDIR `/app/backend`), donc `samples.py` **et** `tests/conftest.py` trouvent `samples/` sans configuration ; les lignes ajoutées :
```dockerfile
COPY backend/pyproject.toml ./
COPY backend/ontoforge ./ontoforge
COPY backend/tests ./tests
COPY samples /app/samples
ENV ONTOFORGE_DATA=/data ONTOFORGE_SAMPLES=/app/samples
```
Le reste (Java, `.[reasoner]`, volume `/data`, port 8000, healthcheck, frontend `8080:80`) est inchangé.

**Recommandé (non créé, hors périmètre)** : un fichier `backend/Dockerfile.dockerignore` (BuildKit) contenant `frontend/node_modules`, `frontend/dist`, `**/__pycache__`, `.git`, `data/`, `.env` pour ne pas envoyer `node_modules` dans le contexte backend.

## Vérification serveur (uvicorn :8000, données dans un dossier temporaire)
- `GET /api/health` → `{"status":"ok","version":"0.1.0"}`
- `GET /api/projects` → `[]` puis la liste après `POST /api/projects`
- `GET /api/samples` → `trap` (ontology `trap.ttl`, shapes `trap-shapes.ttl`, data `trap-data.ttl`)
- `POST /analyze` → 501 `module mapping.engine pas encore disponible` (attendu)
- `POST /import` de `samples/trap/trap-shapes.ttl` en `kind=auto` → détecté `shapes`, parsé par le vrai `shacl.import_shapes`, `shapes.ttl` écrit par le vrai `shacl.export_shapes`.

## Écarts / points pour le chef (non bloquants pour moi)
1. **`lots/L1.md` ≠ `docs/CONTRACTS.md`** : L1.md décrit 36 endpoints aux chemins différents (`/export?kind=`, `/projects/from-sample`, `POST /conformance`, `/validate`, `PATCH`, `/rules`, `/targets`, `/report`, `POST /generate`, `/generate.zip`, `/assistant/proposals/{id}/apply`…) et des noms camelCase. J'ai suivi **CONTRACTS.md** (consigne). À trancher dans `journal/decisions.md` ; A3/A8/A9/A10 de L1.md sont à réécrire sur les chemins de CONTRACTS.
2. **Critère A11** (`grep -q "COPY tests" Dockerfile`) échoue désormais textuellement (la ligne est `COPY backend/tests ./tests`) : remplacer par `grep -q "COPY backend/tests" Dockerfile`.
3. **D-017** (`generate(pg, options) -> list[GeneratedFile]`) contredit CONTRACTS (`generate(pg, onto) -> dict[str, str]`) ; l'API accepte les deux formes de retour, mais appelle `generate(pg, onto)`.
4. `pg_model.py` n'a pas de `GeneratedFile` (critère A2 de L1.md).
