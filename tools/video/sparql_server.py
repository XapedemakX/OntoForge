"""Petit endpoint SPARQL (rdflib, lecture seule) sur les données de démo automaint, pour filmer l'écran Requêtes.
Usage : /home/claude/venv/bin/python tools/video/sparql_server.py 8931"""
import json, sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse
import rdflib

S = Path(__file__).resolve().parents[2] / "samples" / "automaint"
g = rdflib.Graph(); g.parse(S / "automaint-demo-data.ttl", format="turtle")
for extra in ("automaint.ttl",):
    if (S / extra).exists(): g.parse(S / extra, format="turtle")

class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def _q(self, q):
        try:
            r = g.query(q)
            body = {"head": {}, "boolean": bool(r.askAnswer)} if r.type == "ASK" else json.loads(r.serialize(format="json"))
            data, code = json.dumps(body).encode(), 200
        except Exception as e:
            data, code = str(e).encode(), 400
        self.send_response(code); self.send_header("Content-Type", "application/sparql-results+json")
        self.send_header("Content-Length", str(len(data))); self.end_headers(); self.wfile.write(data)
    def do_GET(self): self._q(parse_qs(urlparse(self.path).query).get("query", [""])[0])
    def do_POST(self):
        raw = self.rfile.read(int(self.headers.get("Content-Length", 0))).decode()
        self._q(parse_qs(raw).get("query", [""])[0] if "form" in self.headers.get("Content-Type", "") else raw)

ThreadingHTTPServer(("127.0.0.1", int(sys.argv[1]) if len(sys.argv) > 1 else 8931), H).serve_forever()
