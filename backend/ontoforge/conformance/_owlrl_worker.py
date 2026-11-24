"""Processus fils du raisonnement OWL RL du contrôle de conformité (L52, DF-B03) : owlrl sur un graphe N-Triples lu sur stdin.

Lancé par `reasoner.py::reason` via `childproc.run_limited` : délai tenu par la mort du fils, plafonds mémoire (RLIMIT_AS) et CPU
(RLIMIT_CPU), environnement réduit (aucune clé). N'importe aucun module OntoForge : `_owlrl_core.py` est chargé depuis le dossier
de ce script. Sortie : un objet JSON sur stdout (`_owlrl_core.closure`).
"""
import importlib.util
import json
import os
import sys

import rdflib

# chargé par son chemin (et non en ajoutant ce dossier à sys.path, où d'autres modules masqueraient des noms)
_spec = importlib.util.spec_from_file_location("_owlrl_core", os.path.join(os.path.dirname(os.path.abspath(__file__)), "_owlrl_core.py"))
_owlrl_core = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_owlrl_core)


def main() -> None:
    g = rdflib.Graph()
    g.parse(data=sys.stdin.buffer.read(), format="nt")
    sys.stdout.write(json.dumps(_owlrl_core.closure(g)))


try:
    main()
except MemoryError:
    sys.stderr.write("MemoryError\n")
    sys.exit(3)
