"""Lancement des processus fils isolés (L41 : L39-02, L39-03) : validation SHACL et requêtes du triplestore local.

- Plafonds (mémoire, CPU, taille de fichier) posés par le fils LUI-MÊME avant d'exécuter son script : un lanceur ``python -I -c``
  appelle ``resource.setrlimit`` puis ``runpy.run_path``. Pas de ``preexec_fn`` (dangereux dans un processus à plusieurs fils :
  blocage possible entre ``fork`` et ``exec``). ``start_new_session`` isole le fils dans sa propre session.
- Environnement minimal : ``PATH``, ``LANG`` (et ``LC_ALL``) et ``PYTHONPATH`` s'ils existent, rien d'autre. Ni clé maître, ni clé d'API,
  ni mot de passe de compte n'arrive au fils.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

_LAUNCHER = (
    "import resource, runpy, sys\n"
    "mem, cpu, fsize, script = int(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3]), sys.argv[4]\n"
    "resource.setrlimit(resource.RLIMIT_AS, (mem << 20, mem << 20))\n"
    "resource.setrlimit(resource.RLIMIT_CPU, (cpu, cpu + 1))\n"
    "resource.setrlimit(resource.RLIMIT_FSIZE, (fsize, fsize))\n"
    "sys.argv = [script] + sys.argv[5:]\n"
    "runpy.run_path(script, run_name='__main__')\n"
)
_ENV_KEEP = ("PATH", "LANG", "LC_ALL", "PYTHONPATH")


def minimal_env() -> dict[str, str]:
    env = {k: os.environ[k] for k in _ENV_KEEP if k in os.environ}
    env.setdefault("PATH", os.defpath)
    return env


def run_limited(worker: Path | str, payload: bytes, *, timeout: float, mem_mb: int, cpu_s: int, fsize: int = 0,
                args: Optional[list[str]] = None) -> subprocess.CompletedProcess:
    """Exécute ``worker`` (script Python) dans un fils plafonné ; lève ``subprocess.TimeoutExpired`` au-delà de ``timeout``."""
    cmd = [sys.executable, "-I", "-c", _LAUNCHER, str(int(mem_mb)), str(int(cpu_s)), str(int(fsize)), str(worker), *(args or [])]
    return subprocess.run(cmd, input=payload, capture_output=True, timeout=timeout, cwd="/", env=minimal_env(), start_new_session=True)
