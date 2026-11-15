"""Processus fils de la validation SHACL (L39-secu, SEC-05) : pySHACL sur trois graphes N-Triples (JSON sur stdin).

Exécuté par `validate.py` via `childproc.run_limited` : délai, plafond mémoire (RLIMIT_AS) et plafond CPU (RLIMIT_CPU) posés par le
processus lui-même avant ce script, environnement minimal (aucune clé). Un `sh:pattern` pathologique ou des données piégées tuent ce
processus, jamais le service. Aucune écriture de fichier. Le réseau n'est PAS coupé par le système (pySHACL ni rdflib n'en ouvrent pour
ces entrées, vérifié en L40 : SERVICE, FROM, GRAPH sans appel sortant), mais le fils ne reçoit aucun secret. Sortie : un objet JSON sur stdout.
"""
import json
import sys

import pyshacl
import rdflib
from rdflib.plugins.parsers.ntriples import NTGraphSink, W3CNTriplesParser


class _SameLabels(dict):
    """Contexte de nœuds blancs du lecteur N-Triples : conserve les étiquettes (le parent s'en sert pour retrouver ses shapes)."""

    def get(self, key, default=None):
        return key


def parse_nt(g: rdflib.Graph, text: str) -> None:
    W3CNTriplesParser(NTGraphSink(g)).parsestring(text, bnode_context=_SameLabels())


def main() -> None:
    req = json.loads(sys.stdin.buffer.read())

    def load(key: str):
        txt = req.get(key)
        if txt is None:
            return None
        g = rdflib.Graph()
        parse_nt(g, txt)
        return g

    dg, sg, og = load("data"), load("shapes"), load("ont")
    inf = req.get("inference") or "none"
    conforms, results_graph, text = pyshacl.validate(
        dg, shacl_graph=sg, ont_graph=og, inference=None if inf == "none" else inf,
        abort_on_first=False, allow_warnings=False, allow_infos=False, advanced=False, inplace=False,
    )
    sys.stdout.write(json.dumps({"conforms": bool(conforms), "results": results_graph.serialize(format="nt"), "text": str(text)}))


try:
    main()
except MemoryError:
    sys.stderr.write("MemoryError\n")
    sys.exit(3)
