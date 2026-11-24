"""Raisonnement : OWL RL (owlrl) dans un processus fils tuable, avec contournement du bug prp-key ; HermiT est dans conformance/hermit.py.
Jamais bloquant.

L52 (DF-B03) : avant, owlrl tournait dans un fil ``daemon`` abandonné au délai, mais un fil Python ne se tue pas : le calcul
continuait en arrière-plan. Désormais le calcul (``_owlrl_core.closure``) tourne dans ``_owlrl_worker.py``, lancé par
``childproc.run_limited`` : délai tenu par la mort du fils, mémoire (``ONTOFORGE_OWLRL_MEMORY_MB``, 2048) et CPU (délai + 2 s)
plafonnés, environnement réduit ; au plus ``ONTOFORGE_OWLRL_SLOTS`` (2) calculs simultanés, au-delà le raisonnement est sauté
avec une note. Le bug owlrl 7.1.2 (prp-key) est décrit dans ``_owlrl_core.py``.
"""
from __future__ import annotations

import json
import os
import threading
from pathlib import Path

import rdflib

from .. import childproc
from ._owlrl_core import apply_prp_key, rdf_list, unsat as _unsat  # noqa: F401 (API historique du module)
from .report import ReasonerInfo

WORKER = Path(__file__).with_name("_owlrl_worker.py")


def _env_int(name: str, default: int, lo: int, hi: int) -> int:
    try:
        return max(lo, min(hi, int(os.environ.get(name, default))))
    except ValueError:
        return default


_SLOTS = threading.BoundedSemaphore(_env_int("ONTOFORGE_OWLRL_SLOTS", 2, 1, 32))


def _memory_mb() -> int:
    return _env_int("ONTOFORGE_OWLRL_MEMORY_MB", 2048, 256, 1 << 20)


def _owlrl(g: rdflib.Graph, info: ReasonerInfo, timeout: float) -> None:
    """Fermeture OWL RL de ``g`` dans un processus fils plafonné ; remplit ``info`` (lève ``childproc.TimeoutExpired`` au délai)."""
    payload = g.serialize(format="nt").encode("utf-8")
    proc = childproc.run_limited(WORKER, payload, timeout=timeout, mem_mb=_memory_mb(), cpu_s=int(timeout) + 2, fsize=0)
    if proc.returncode != 0 or not proc.stdout:
        if proc.returncode < 0 or b"MemoryError" in proc.stderr:
            info.notes.append("OWL RL : mémoire ou temps de calcul plafonnés, raisonnement abandonné.")
            info.used, info.consistent = "none", None
            return
        tail = (proc.stderr.decode("utf-8", "replace").strip().splitlines() or ["erreur inconnue"])[-1][:300]
        raise RuntimeError(tail)
    out = json.loads(proc.stdout)
    info.notes.extend(out["notes"])
    info.consistent = bool(out["consistent"])
    info.notes.extend(f"Incohérence OWL RL : {e}" for e in out["errors"])
    info.unsatisfiable = list(out["unsatisfiable"])
    info.used = "owlrl"


def reason(g: rdflib.Graph, *, hermit: bool = False, timeout: float = 30.0) -> ReasonerInfo:
    """OWL RL en processus fils (délai `timeout`, tenu : le fils est tué) puis HermiT optionnel. Retourne toujours un ReasonerInfo."""
    info = ReasonerInfo()
    timeout = max(1.0, float(timeout))
    if not _SLOTS.acquire(blocking=False):
        info.notes.append("OWL RL : trop de raisonnements en cours, raisonnement non lancé ; relancez le contrôle dans quelques secondes.")
        return info
    try:
        _owlrl(g, info, timeout)
    except childproc.TimeoutExpired:
        info.notes.append(f"OWL RL : délai de {timeout:.0f} s dépassé, raisonnement abandonné.")
        info.used, info.consistent = "none", None
        return info
    except Exception as e:  # noqa: BLE001
        info.notes.append(f"OWL RL indisponible : {type(e).__name__}: {e}")
        return info
    finally:
        _SLOTS.release()
    if hermit:
        # SEC-21 : l ancien chargement par fichier local via owlready2 (sans retrait des owl:imports) est supprimé ; HermiT passe par conformance.hermit.
        info.notes.append("HermiT : utilisez le raisonneur dédié (conformance.hermit), qui retire les owl:imports avant l'exécution.")
    return info
