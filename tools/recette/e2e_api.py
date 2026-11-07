#!/home/claude/venv/bin/python
"""Recette it2 (L14) : parcours complet par l'API. Usage : /home/claude/venv/bin/python tools/recette/e2e_api.py [--keep]
Démarre le backend (mock, ONTOFORGE_DATA temporaire) sur un port libre + un petit serveur SPARQL rdflib (demo-data)."""
from __future__ import annotations
import io, json, os, socket, subprocess, sys, tempfile, threading, time, traceback, zipfile
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse
import httpx, rdflib

ROOT = Path(__file__).resolve().parents[2]
S = ROOT / "samples" / "automaint"
AM = "https://w3id.org/ontoforge/automaint#"
OUT = ROOT / "journal" / "L14" / "recette-api.json"
RESULTS: list[dict] = []


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0)); return s.getsockname()[1]


def start_sparql(port: int):
    g = rdflib.Graph(); g.parse(S / "automaint-demo-data.ttl", format="turtle")
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a): pass
        def _q(self, q):
            try:
                if "ASK" in q.upper()[:200] and "SELECT" not in q.upper():
                    body = {"head": {}, "boolean": bool(g.query(q).askAnswer)}
                else:
                    body = json.loads(g.query(q).serialize(format="json"))
                data, code = json.dumps(body).encode(), 200
            except Exception as e:
                data, code = str(e).encode(), 400
            self.send_response(code); self.send_header("Content-Type", "application/sparql-results+json")
            self.send_header("Content-Length", str(len(data))); self.end_headers(); self.wfile.write(data)
        def do_GET(self): self._q(parse_qs(urlparse(self.path).query).get("query", [""])[0])
        def do_POST(self):
            raw = self.rfile.read(int(self.headers.get("Content-Length", 0))).decode()
            ct = self.headers.get("Content-Type", "")
            self._q(parse_qs(raw).get("query", [""])[0] if "form" in ct else raw)
    srv = HTTPServer(("127.0.0.1", port), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, len(g)


def step(name: str):
    def deco(fn):
        t0 = time.time()
        try:
            r = fn()
            ok, detail = (r if isinstance(r, tuple) else (True, r))
            ok = bool(ok)
        except Exception as e:
            ok, detail = False, f"EXCEPTION {type(e).__name__}: {e} | {traceback.format_exc().splitlines()[-3].strip()}"
        RESULTS.append({"step": name, "ok": ok, "detail": str(detail)[:600], "s": round(time.time() - t0, 2)})
        print(("OK  " if ok else "KO  ") + name + " :: " + str(detail)[:300], flush=True)
        return fn
    return deco


def main() -> int:
    keep = "--keep" in sys.argv
    port, sport = free_port(), free_port()
    data = tempfile.mkdtemp(prefix="ontoforge-recette-")
    env = {**os.environ, "ONTOFORGE_DATA": data, "ONTOFORGE_LLM_PROVIDER": "mock", "ONTOFORGE_SECRET_KEY": "recette-secret-key-0123456789"}
    proc = subprocess.Popen([sys.executable, "-m", "uvicorn", "ontoforge.main:app", "--port", str(port), "--log-level", "warning"],
                            cwd=ROOT / "backend", env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    srv, ntriples = start_sparql(sport)
    B = f"http://127.0.0.1:{port}/api"
    c = httpx.Client(timeout=120)
    for _ in range(60):
        try:
            if c.get(B + "/health").status_code == 200: break
        except Exception: time.sleep(0.5)
    st: dict = {}
    def J(r, code=None):
        if code and r.status_code != code: raise AssertionError(f"HTTP {r.status_code}: {r.text[:200]}")
        if r.status_code >= 500: raise AssertionError(f"HTTP {r.status_code}: {r.text[:200]}")
        return r.json()

    @step("00 santé + exemples")
    def _():
        h = J(c.get(B + "/health"), 200); sm = [s["name"] for s in J(c.get(B + "/samples"), 200)]
        return ("automaint" in sm and "trap" in sm), f"{h} samples={sm}"

    @step("01 créer projet depuis automaint")
    def _():
        p = J(c.post(B + "/projects", json={"name": "recette", "sample": "automaint"}), 201); st["id"] = p["id"]
        n = len(p["onto"]["classes"]); return n >= 15 and AM + "Vehicle" in p["onto"]["classes"], f"id={p['id']} classes={n} shapes={len(p.get('shapes',{}).get('node_shapes',[]) ) if isinstance(p.get('shapes'),dict) else '?'}"
    pid = st.get("id")
    if not pid:
        print("projet non créé, arrêt"); proc.terminate(); return 2
    P = f"{B}/projects/{pid}"

    def shacl(f):
        with open(S / f, "rb") as fh:
            return J(c.post(P + "/shacl/validate", files={"file": (f, fh)}), 200)
    @step("02 SHACL automaint-demo-data.ttl (0 violation)")
    def _():
        r = shacl("automaint-demo-data.ttl"); return r["conforms"] and len(r["results"]) == 0, f"conforms={r['conforms']} results={len(r['results'])}"
    @step("03 SHACL automaint-data.ttl (4 violations)")
    def _():
        r = shacl("automaint-data.ttl"); return (not r["conforms"]) and len(r["results"]) == 4, f"conforms={r['conforms']} results={len(r['results'])}"
    @step("04 conformité OWL (DL vrai)")
    def _():
        r = J(c.get(P + "/conformance"), 200); return r["profiles"]["DL"] is True, f"profiles={r['profiles']} issues={len(r['issues'])} errors={sum(1 for i in r['issues'] if i.get('level')=='error')}"

    def ops(lst, label=None):
        return J(c.post(P + "/ops", json={"ops": lst, "label": label} if label else {"ops": lst}), 200)
    @step("05 édition : ajout classe Pneu")
    def _():
        r = ops([{"op": "add_class", "name": "Pneu", "label": "Pneu"}]); return r["ok"] and AM + "Pneu" in r["project"]["onto"]["classes"], f"ok={r['ok']} errors={r['errors']} can_undo={r['can_undo']}"
    @step("06 édition : Pneu sous-classe de Part")
    def _():
        r = ops([{"op": "add_subclass", "iri": AM + "Pneu", "parent": AM + "Part"}]); return r["ok"] and AM + "Part" in r["project"]["onto"]["classes"][AM + "Pneu"]["sub_class_of"], f"ok={r['ok']} errors={r['errors']}"
    @step("07 édition : propriété objet monteSur (Pneu → Vehicle)")
    def _():
        r = ops([{"op": "add_object_property", "name": "monteSur", "label": "monte sur", "domain": [AM + "Pneu"], "range": [AM + "Vehicle"]}])
        return r["ok"] and AM + "monteSur" in r["project"]["onto"]["object_properties"], f"ok={r['ok']} errors={r['errors']}"
    @step("08 undo puis redo")
    def _():
        h0 = J(c.get(P + "/ops/history"), 200)
        u = J(c.post(P + "/ops/undo"), 200); gone = AM + "monteSur" not in u["project"]["onto"]["object_properties"]
        rd = J(c.post(P + "/ops/redo"), 200); back = AM + "monteSur" in rd["project"]["onto"]["object_properties"]
        return gone and back and u["can_redo"], f"history_keys={list(h0)} undo_removed={gone} redo_restored={back}"
    @step("09 erreur de validation attendue sur un cycle (Part ⊑ Pneu)")
    def _():
        r = ops([{"op": "add_subclass", "iri": AM + "Part", "parent": AM + "Pneu"}])
        return (r["ok"] is False and r["errors"] and "ycle" in json.dumps(r["errors"], ensure_ascii=False)), f"ok={r['ok']} errors={json.dumps(r['errors'], ensure_ascii=False)[:200]}"
    @step("10 graphe (GET /graph)")
    def _():
        g = J(c.get(P + "/graph"), 200); return bool(g.get("nodes")), f"keys={list(g)} nodes={len(g.get('nodes',[]))} edges={len(g.get('edges',[]))}"

    @step("11 périmètre « Maintenance » + aperçu")
    def _():
        cls = [AM + x for x in ("Vehicle", "RepairOrder", "Technician", "ServiceOperation", "Part", "Garage")]
        r = J(c.post(P + "/perimeters", json={"name": "Maintenance", "classes": cls, "include_descendants": True}), 201); st["per"] = r["id"]
        pv = J(c.get(f"{P}/perimeters/{r['id']}/preview"), 200)
        c.put(P + "/perimeters/active", json={"id": r["id"]})
        return True, f"id={r['id']} counts={pv['counts']} excluded={len(pv['excluded'])}"
    @step("12 analyse restreinte au périmètre (constats info)")
    def _():
        full = J(c.post(P + "/analyze?target=curiosity"), 200)
        r = J(c.post(f"{P}/analyze?target=curiosity&perimeter={st['per']}"), 200)
        inf = [f for f in r["findings"] if f["severity"] == "info"]
        return len(inf) >= 1 and len(r["findings"]) <= len(full["findings"]) + len(inf), f"restreint={len(r['findings'])} dont info={len(inf)} ; complet={len(full['findings'])} ; node_types={len(r['node_types'])} vs {len(full['node_types'])} (complet)"
    for T in ("curiosity", "neo4j"):
        @step(f"13 analyse {T} (projet entier)")
        def _(T=T):
            c.put(P + "/perimeters/active", json={"id": None})
            r = J(c.post(f"{P}/analyze?target={T}"), 200); f = r["findings"]
            cnt = {s: sum(1 for x in f if x["severity"] == s) for s in ("auto", "review", "lost", "info")}
            return cnt["auto"] > 0 and cnt["review"] > 0, f"{cnt} X00={sum(1 for x in f if x['rule']=='X00')} node_types={len(r['node_types'])} edge_types={len(r['edge_types'])}"
        @step(f"14 accepter les recommandations {T} (sauf perdus)")
        def _(T=T):
            r = J(c.post(f"{P}/decisions/{T}/accept-recommended"), 200)
            lost_chosen = [x["id"] for x in r["findings"] if x["severity"] == "lost" and x.get("chosen")]
            rev_pending = [x["id"] for x in r["findings"] if x["severity"] == "review" and not x.get("chosen")]
            lost_pending = [x for x in r["findings"] if x["severity"] == "lost" and not x.get("chosen")]
            return (not rev_pending) and bool(lost_pending or not lost_chosen) and not lost_chosen, f"review en attente={len(rev_pending)} ; perdus acceptés par recommandation={len(lost_chosen)} ; perdus restants={len(lost_pending)} (l'API n'accepte plus les perdus par défaut : D-L14-02)"
        @step(f"15 générer {T} + zip")
        def _(T=T):
            g = J(c.get(f"{P}/generate/{T}"), 200); files = sorted(g["files"])
            z = c.get(f"{P}/generate/{T}/zip"); zf = zipfile.ZipFile(io.BytesIO(z.content)); names = zf.namelist()
            ok = z.status_code == 200 and len(files) >= (6 if T == "curiosity" else 3) and any("rapport-transposition" in n for n in names)
            return ok, f"fichiers={files} zip={len(names)} entrées {len(z.content)} o missing={g.get('missing')}"
    @step("16 historique des générations")
    def _():
        g = J(c.get(P + "/generations"), 200); return len(g) >= 2, f"{len(g)} entrées ; cibles={[x['target'] for x in g]} ; premier={json.dumps(g[0])[:160] if g else None}"
    @step("17 traduction de requête + questions de compétence")
    def _():
        t = J(c.post(f"{P}/queries/translate?target=neo4j", json={"sparql": f"PREFIX am: <{AM}> SELECT ?v WHERE {{ ?v a am:Vehicle }} LIMIT 5"}), 200)
        cq = J(c.get(f"{P}/queries/competency?target=neo4j"), 200)
        return "MATCH" in json.dumps(t) and len(cq) >= 5, f"cypher={str(t.get('cypher'))[:60]!r} competency={len(cq)}"

    @step("20 paramètres : fournisseur mock + secret jamais renvoyé")
    def _():
        r = c.post(B + "/settings/providers", json={"id": "mock-recette", "name": "Mock recette", "kind": "mock", "api_key": "sk-test-SECRET-1234567890"})
        pr = J(r, 201); c.put(B + "/settings", json={"default_provider_id": "mock-recette", "language": {"ui": "fr", "labels": "fr", "assistant": "fr"}})
        txt = c.get(B + "/settings").text; t = J(c.post(B + "/settings/providers/mock-recette/test"), 200)
        return ("SECRET-1234567890" not in txt and "SECRET-1234567890" not in json.dumps(pr)) and t.get("ok") is True, f"has_key={pr.get('has_key')} test={t.get('ok')} {t.get('message')} fuite_clé={'SECRET-1234567890' in txt}"
    @step("21 paramètres : secret chiffré sur disque")
    def _():
        f = Path(data) / "settings.json"; txt = f.read_text() if f.exists() else ""
        return f.exists() and "SECRET-1234567890" not in txt, f"settings.json existe={f.exists()} clé en clair={'SECRET-1234567890' in txt}"
    @step("22 paramètres : endpoint SPARQL local + test + activation")
    def _():
        url = f"http://127.0.0.1:{sport}/sparql"
        e = J(c.post(B + "/settings/endpoints", json={"name": "Local demo", "url": url}), 201)
        t = J(c.post(f"{B}/settings/endpoints/{e['id']}/test"), 200); c.put(B + "/settings/endpoints/active", json={"id": e["id"]})
        lst = J(c.get(B + "/settings/endpoints"), 200); st["ep"] = e["id"]
        return t.get("ok") is True and lst["active_endpoint_id"] == e["id"], f"id={e['id']} triples serveur={ntriples} test={t}"
    @step("23 requête guidée Véhicule → ordre → technicien (≥ 1 ligne)")
    def _():
        gq = {"root": {"var": "v", "class_iri": AM + "Vehicle"},
              "steps": [{"from_var": "v", "property_iri": AM + "hasRepairOrder", "to_var": "o", "to_class_iri": AM + "RepairOrder"},
                        {"from_var": "o", "property_iri": AM + "assignedTo", "to_var": "t", "to_class_iri": AM + "Technician"}],
              "limit": 20}
        b = J(c.post(P + "/query/build", json={"guided": gq, "target": "neo4j"}), 200)
        r = J(c.post(P + "/query/run", json={"guided": gq, "limit": 20}), 200)
        n = len(r.get("rows", [])); st["gq"] = gq
        return n >= 1, f"lignes={n} vars={r.get('vars') or r.get('variables')} graphe nodes={len((r.get('graph') or {}).get('nodes',[]))} cypher={str(b.get('cypher'))[:70]!r}"
    @step("24 requête sauvegardée (CRUD)")
    def _():
        q = J(c.post(P + "/queries/saved", json={"name": "V-O-T", "guided": st["gq"]}), 201)
        ls = J(c.get(P + "/queries/saved"), 200); d = J(c.delete(f"{P}/queries/saved/{q['id']}"), 200)
        return len(ls) >= 1, f"créée={q['id']} liste={len(ls)} suppr={d}"
    @step("25 autocomplétion de valeurs (/query/values)")
    def _():
        v = J(c.get(P + "/query/values", params={"class": AM + "Technician", "q": "a"}), 200); return len(v["values"]) >= 1, f"{len(v['values'])} valeurs ex={v['values'][:2]}"
    for q in ("quels véhicules ont eu une réparation par le technicien Martin ?", "liste des garages à Toulouse", "ordres de réparation ouverts après le 1er octobre"):
        @step(f"26 langage naturel : {q[:48]}")
        def _(q=q):
            d = J(c.post(P + "/query/nl", json={"question": q, "provider_id": "mock"}), 200)
            r = J(c.post(P + "/query/run", json={"guided": d["guided"], "limit": 50}), 200)
            return (d["mode"] and not d["unmatched"] and len(r["rows"]) >= 0), f"mode={d['mode']} conf={d.get('confidence')} unmatched={d['unmatched']} lignes={len(r['rows'])} sparql_ok={bool(d.get('sparql'))}"
    @step("27 questions de compétence guidées")
    def _():
        cg = J(c.get(P + "/queries/competency/guided"), 200); n = sum(1 for x in cg if x["guided"]); return len(cg) >= 5, f"{len(cg)} questions dont {n} convertibles"
    @step("30 assistant : statut")
    def _():
        s = J(c.get(B + "/assistant/status"), 200); return True, str(s)
    @step("31 assistant : chat (mock)")
    def _():
        r = J(c.post(B + "/assistant/chat", json={"project_id": pid, "provider_id": "mock-recette", "messages": [{"role": "user", "content": "Ajoute une classe Pneu liée aux véhicules"}]}), 200)
        return bool(r), json.dumps(r, ensure_ascii=False)[:260]
    @step("32 assistant : upload CSV + chat avec pièce jointe + draft")
    def _():
        csv = "id;immatriculation;marque;modele\n1;AB-123-CD;Renault;Clio\n2;EF-456-GH;Peugeot;208\n"
        up = J(c.post(B + "/assistant/upload", files={"file": ("vehicules.csv", csv.encode(), "text/csv")}), 200)
        ch = J(c.post(B + "/assistant/chat", json={"project_id": pid, "messages": [{"role": "user", "content": "Propose des classes depuis ce CSV"}],
                                                  "attachments": [{"name": up["name"], "kind": up["kind"], "content": up["content"]}]}), 200)
        dr = J(c.post(B + "/assistant/draft", json={"text": up["content"], "kind": "csv", "filename": up["name"], "base_iri": "https://example.org/recette#"}), 200)
        before = len(J(c.get(P), 200)["onto"]["classes"])
        return up["kind"] == "csv" and up["preview"].get("columns") and dr.get("proposal"), f"upload kind={up['kind']} cols={up['preview'].get('columns')} ; chat clés={list(ch)} ; draft classes={len(dr['proposal'].get('classes',{}))} warnings={dr.get('warnings')} ; projet inchangé={before}"
    @step("33 assistant : explain d'un constat")
    def _():
        pg = J(c.post(f"{P}/analyze?target=curiosity"), 200); f = next(x for x in pg["findings"] if x["severity"] in ("review", "lost"))
        r = J(c.post(B + "/assistant/explain", json={"project_id": pid, "target": "curiosity", "finding_id": f["id"]}), 200); return bool(r), json.dumps(r, ensure_ascii=False)[:200]
    @step("34 exports ontologie (xml) et shapes")
    def _():
        a = c.get(P + "/export/ontology?format=xml"); b = c.get(P + "/export/shapes"); return a.status_code == 200 and b.status_code == 200 and "<" in a.text[:200], f"onto {a.status_code} {len(a.text)} o ; shapes {b.status_code} {len(b.text)} o"
    @step("35 projet rechargé : décisions + périmètre persistés")
    def _():
        p = J(c.get(P), 200); return bool(p["decisions"].get("curiosity")) and any(x["name"] == "Maintenance" for x in p["perimeters"]), f"décisions={ {k: len(v) for k, v in p['decisions'].items()} } périmètres={[x['name'] for x in p['perimeters']]}"
    @step("36 projet piège : conformité + SHACL 8 violations")
    def _():
        t = J(c.post(B + "/projects", json={"name": "piege", "sample": "trap"}), 201)
        with open(ROOT / "samples/trap/trap-data.ttl", "rb") as fh:
            r = J(c.post(f"{B}/projects/{t['id']}/shacl/validate", files={"file": ("trap-data.ttl", fh)}), 200)
        cf = J(c.get(f"{B}/projects/{t['id']}/conformance"), 200); return len(r["results"]) == 8 and cf["profiles"]["DL"], f"violations={len(r['results'])} (attendu 8 = tests unitaires ; inférence {r['inference']} ; extra={[x['focus'].split('#')[-1] for x in r['results'] if x['focus'].endswith('ro_2026_0001')]}) DL={cf['profiles']['DL']}"

    proc.terminate(); srv.shutdown()
    ok = sum(r["ok"] for r in RESULTS); ko = len(RESULTS) - ok
    OUT.write_text(json.dumps({"ok": ok, "ko": ko, "steps": RESULTS}, ensure_ascii=False, indent=1))
    print(f"\n=== {ok} OK / {ko} KO sur {len(RESULTS)} étapes -> {OUT}")
    return 0 if ko == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
