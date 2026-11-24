"""L52 DF-F08 (et F01, F02, F04, F05, F06) : la suite pytest lance aussi les garde-fous Node du front.

Parité des clés et des espaces réservés fr.json / en.json, lecture de `detail`, clients API (frontend/tests/*.test.mjs, node --test).
Ces tests ne lisent que des fichiers du dépôt, mais les fichiers `.ts` importés tels quels exigent Node 22.18 ou plus
(suppression des types native) : ignorés si Node est absent ou plus ancien (le job backend de la CI n'installe pas Node).
"""
import re
import shutil
import subprocess
from pathlib import Path

import pytest

FRONT = Path(__file__).resolve().parents[2] / "frontend"


def _node_ok() -> bool:
    if shutil.which("node") is None:
        return False
    try:
        out = subprocess.run(["node", "--version"], capture_output=True, text=True, timeout=20).stdout
        m = re.match(r"v(\d+)\.(\d+)", out.strip())
        return bool(m) and (int(m.group(1)), int(m.group(2))) >= (22, 18)
    except (OSError, subprocess.SubprocessError):
        return False


@pytest.mark.skipif(not _node_ok(), reason="Node 22.18 ou plus absent")
@pytest.mark.parametrize("name", ["i18n_parity", "http_detail", "api_clients"])
def test_front_guard(name):
    r = subprocess.run(["node", "--test", f"tests/{name}.test.mjs"], cwd=FRONT, capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stdout[-1500:] + r.stderr[-500:]
