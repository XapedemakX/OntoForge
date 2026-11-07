# Plan de recette — itération 1 (mar. 3 nov., 16 h → 19 h)

Pilote : chef (Haiku pour l'exécution mécanique, rapports dans `journal/L7/`). Prérequis : L3 clos (11 h), L4 13 h, L5/L6 16 h. Rien de ce qui suit ne nécessite le réseau (assistant en `mock`). `PY=/home/claude/venv/bin/python`, dépôt `/home/claude/OntoForge`.

## 0. Pré-vol (5 min)
```bash
cd /home/claude/OntoForge/backend
$PY -m pip install -e ".[dev]" -q
$PY -m pytest -q                       # attendu : 0 échec, 0 erreur ; skip/xfail seulement HermiT
$PY -m pytest -q --durations=5 | tail -8   # analyze(trap) < 2 s (L3 A9)
cd ../frontend && npm ci --silent && npm run build   # attendu : exit 0, dist/index.html
node scripts/check-api.mjs ../docs/CONTRACTS.md      # exit 0
du -sk dist                                          # < 2000
cd .. && grep -rnoE "https?://[a-z0-9.-]+[^ \"'>]*" samples backend/tests | grep -vE "example\.(org|com)|w3\.org|w3id\.org/ontoforge|xmlns\.com|purl\.org|schema\.org|creativecommons\.org|localhost"   # aucune sortie
grep -rnE "sk-ant-[A-Za-z0-9]" backend frontend/src .env.example   # aucune sortie
grep -rn "À VÉRIFIER" backend/ontoforge | wc -l     # recopier la liste dans journal/L7/cloture.md
```

## 1. Scénario bout en bout par l'API (20 min)
```bash
cd /home/claude/OntoForge/backend
export ONTOFORGE_DATA=$(mktemp -d) ONTOFORGE_LLM_PROVIDER=mock
$PY -m uvicorn ontoforge.main:app --port 8000 &  sleep 3
B=http://localhost:8000/api; S=../samples
curl -s $B/health                                  # {"status":"ok","version":"0.1.0"}
curl -s $B/samples | $PY -c "import sys,json;print([s['name'] for s in json.load(sys.stdin)])"   # automaint, trap

# 1. projet depuis automaint
ID=$(curl -s -XPOST $B/projects -H 'content-type: application/json' -d '{"name":"recette","sample":"automaint"}' | $PY -c "import sys,json;print(json.load(sys.stdin)['id'])")
curl -s $B/projects/$ID | $PY -c "import sys,json;p=json.load(sys.stdin);print('am Vehicle' , 'https://w3id.org/ontoforge/automaint#Vehicle' in p['onto']['classes'], len(p['onto']['classes']))"   # True, >= 15

# 2. import (ontologie piège, puis shapes automaint)
curl -s -F file=@$S/trap/trap.ttl -F kind=ontology $B/projects/$ID/import | head -c 300; echo   # {project, warnings}
curl -s -F file=@$S/automaint/automaint-shapes.ttl -F kind=shapes $B/projects/$ID/import | head -c 200; echo
curl -s -XPOST $B/projects -H 'content-type: application/json' -d '{"name":"piege","sample":"trap"}' >/tmp/trap.json   # D-037 : une seule ontologie
TID=$($PY -c "import json;print(json.load(open('/tmp/trap.json'))['id'])")

# 3. conformité (piège) : DL vrai, avec issues de bonnes pratiques
curl -s $B/projects/$TID/conformance | $PY -c "import sys,json;r=json.load(sys.stdin);print(r['profiles']['DL'], sorted({i['code'] for i in r['issues']}))"   # True [...] ; aucun level=error
# 4. SHACL : 8 violations V1-V8 (confirmé aussi via l'API/projet depuis D-L14-01)
curl -s -F file=@$S/trap/trap-data.ttl $B/projects/$TID/shacl/validate | $PY -c "import sys,json;r=json.load(sys.stdin);print(r['conforms'], len(r['results']))"   # False 8
# 5. analyse Curiosity puis Neo4j
for T in curiosity neo4j; do
  curl -s -XPOST "$B/projects/$TID/analyze?target=$T" | $PY -c "import sys,json;p=json.load(sys.stdin);f=p['findings'];print('$T',len(f),{s:sum(1 for x in f if x['severity']==s) for s in ('auto','review','lost')},'X00:',sum(1 for x in f if x['rule']=='X00'))"
done                                               # review>0 et lost>0 ; X00 = règles hors It1 seulement
# 6. arbitrer une option, accepter les recommandations (la décision manuelle survit)
curl -s -XPUT $B/projects/$TID/decisions/curiosity -H 'content-type: application/json' -d '{"C02:https://w3id.org/ontoforge/automaint#Vehicle":"flatten_into_leaves"}' | head -c 100; echo
curl -s -XPOST $B/projects/$TID/decisions/curiosity/accept-recommended | $PY -c "import sys,json;p=json.load(sys.stdin);print(p['summary'] if 'summary' in p else 'ok')"   # pending == 0
curl -s $B/projects/$TID | $PY -c "import sys,json;print(json.load(sys.stdin)['decisions']['curiosity']['C02:https://w3id.org/ontoforge/automaint#Vehicle'])"   # flatten_into_leaves
# 7. génération + zip (Curiosity, puis Neo4j)
curl -s $B/projects/$TID/generate/curiosity | $PY -c "import sys,json;f=json.load(sys.stdin)['files'];print(sorted(f))"   # >= 6 .cs + rapport-transposition.md
curl -s -o /tmp/c.zip $B/projects/$TID/generate/curiosity/zip && unzip -l /tmp/c.zip | tail -3
curl -s -XPOST "$B/projects/$TID/analyze?target=neo4j" >/dev/null
curl -s $B/projects/$TID/generate/neo4j | $PY -c "import sys,json;f=json.load(sys.stdin)['files'];print(sorted(f));print([l for l in f['schema.cypher'].splitlines() if l.startswith('CREATE')][:3])"
# 8. traduction de requête et questions de compétence (projet automaint)
curl -s -XPOST "$B/projects/$ID/queries/translate?target=neo4j" -H 'content-type: application/json' \
  -d '{"sparql":"PREFIX am: <https://w3id.org/ontoforge/automaint#> SELECT ?v WHERE { ?v a am:Vehicle } LIMIT 5"}' | $PY -m json.tool | head -12   # cypher MATCH (v:Vehicle)... ; lossy false
curl -s "$B/projects/$ID/queries/competency?target=neo4j" | $PY -c "import sys,json;print(len(json.load(sys.stdin)))"   # >= 5
# 9. assistant (mock)
curl -s $B/assistant/status                        # configured selon mock
curl -s -XPOST $B/assistant/draft -H 'content-type: application/json' -d "$($PY -c "import json;print(json.dumps({'text':open('$S/automaint/assistant/garage-notes.txt').read(),'kind':'text','base_iri':'https://w3id.org/ontoforge/automaint#'}))")" | $PY -c "import sys,json;r=json.load(sys.stdin);print(len(r['proposal']['classes']), r['warnings'])"
curl -s $B/projects/$ID | $PY -c "import sys,json;print(len(json.load(sys.stdin)['onto']['classes']))"   # inchangé (jamais appliqué sans sélection)
# 10. exports
curl -s "$B/projects/$ID/export/ontology?format=xml" | head -3 ; curl -s $B/projects/$ID/export/shapes | head -3
kill %1
```
Critère de réussite : toutes les sorties « attendu » ci-dessus, zéro 500, tout 501 restant = fonctionnalité Should listée dans BACKLOG (jamais sur un parcours Must).

## 2. Tests ciblés rejoués (10 min)
`pytest -q tests/test_e2e.py` (scénario ci-dessus automatisé, lead) ; trap : `tests/test_engine_trap.py` (expected, must_not, no_silent_loss, deux cibles) ; `tests/test_shacl_validate.py` (V1–V8 en `none`, 1 `sh:closed` en `rdfs`) ; `tests/test_conformance_profiles.py -k nondl` (W01–W05).

## 3. Front (15 min)
```bash
cd /home/claude/OntoForge/frontend && npm run preview -- --port 4173 &   # backend déjà lancé en :8000
node scripts/smoke.mjs http://localhost:4173       # exit 0
```
Puis revue chef en lisant `src/screens/*` : 6 écrans It1 présents, textes en français, constat `lost` avec option retenue, décision relue après rechargement.

## 4. Revues croisées (qui relit quoi) — verdicts `journal/Lx/review-<id>-it<N>.md`
| Relecteur | Relit | Angle | Modèle |
|---|---|---|---|
| w3c | `engine.py` + `rules/*` (L3), `shacl/*` | `lost` / `review` justifiés, `must_not`, OWA vs CWA, pas de sur-promesse | Opus |
| shacl | `conformance/*` (L2), `core/shapes_model.py` | W01–W07, `spec_ref`, profils | Sonnet |
| curiosity | `profiles/neo4j.py`, `engine.py`, `targets/graphql.py` | cohérence des options, nommage | Sonnet |
| neo4j | `profiles/curiosity.py`, `targets/curiosity.py`, `engine.py` | NODE KEY Enterprise, `reverse`, clés | Sonnet |
| query | `targets/neo4j.py`, `api/analysis.py` | requêtes, formes Cypher 5 | Sonnet |
| w3c | `targets/curiosity.py`, `targets/neo4j.py`, `assistant/*` | fidélité aux constats `lost`, validité OWL des propositions | Opus |
| lead | `io/*`, `projects/store.py` croisé avec `core/*` | round-trip, `unmapped` | (lead) |
| chef | critères de chaque lot, API vs CONTRACTS, Dockerfile/compose/nginx | relance seul les commandes | Sonnet |
| agent neuf (aveugle) | `README.md` + `docs/RECETTE.md` | suit les étapes sans historique ; étape ambiguë = bloquant | Haiku/Sonnet |
Chaque lot : 1 itération de revue visée avant sa clôture ; 3 itérations KO → arbitrage chef (`decisions.md`).

## 5. Critère « docker compose up » — chez Jerem, 15 min (D-012)
Préconditions repoussées au chef avant 18 h 45 : `! grep -q openjdk-17 backend/Dockerfile` ; `grep -q "COPY backend/tests" backend/Dockerfile` ; `grep -q "proxy_pass http://backend:8000" frontend/nginx.conf` ; port `${ONTOFORGE_PORT:-8088}:80` et `8000` ; `.env.example` présent.
```bash
cp .env.example .env            # clé Anthropic facultative
docker compose up --build       # J1 : deux conteneurs, backend healthy (curl localhost:8000/api/health ou docker compose ps)
```
- J2 : http://localhost:8088 → « Démarrer depuis un exemple » → *Maintenance automobile* ou *Ontologie piège* : ontologie chargée, résumé affiché.
- J3 : Conformité → Constats Curiosity → choisir une option → « Accepter toutes les recommandations » → Exporter → zip (`.cs` nodes/edges/enregistrement/connecteur + `rapport-transposition.md`) ; même parcours en Neo4j (DDL).
- J4 (facultatif, avec clé) : Assistant → coller `samples/automaint/assistant/garage-notes.txt` → cocher 2 éléments → appliquer.
- Succès = J1–J3 sans intervention. Échec = Jerem colle la sortie de `docker compose up` / `logs backend` dans la Salle ou `journal/questions-jerem.md` ; correctif lead < 1 h.
