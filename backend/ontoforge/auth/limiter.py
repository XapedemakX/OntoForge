"""Limitation des tentatives de connexion par adresse IP, avec délai progressif.

Les 2 premiers échecs n'imposent rien. À partir du 3e, l'IP est bloquée 2 s, puis 4 s, 8 s… jusqu'à 15 minutes ; pendant le blocage
le mot de passe n'est même pas vérifié (pas de coût de calcul, pas d'indice). Un échec compte pendant 15 minutes ; un succès remet
le compteur à zéro. L'état est en mémoire : avec une seule instance (max-instances=1) il est exact, il repart à zéro au redémarrage.
"""
from __future__ import annotations

import ipaddress
import threading
import time
from typing import Mapping, Optional

FREE_FAILURES = 2
BASE_DELAY = 2.0
MAX_DELAY = 900.0
WINDOW = 900.0
MAX_ENTRIES = 5000

_state: dict[str, list[float]] = {}   # ip -> [échecs, dernier échec, bloqué jusqu'à]
_lock = threading.Lock()


def _now() -> float:
    return time.monotonic()


def reset() -> None:
    with _lock:
        _state.clear()


def retry_after(ip: str) -> float:
    """Secondes à attendre avant d'accepter une tentative de cette IP (0 = libre)."""
    with _lock:
        st = _state.get(ip)
        return max(0.0, st[2] - _now()) if st else 0.0


def failure(ip: str) -> float:
    """Enregistre un échec ; renvoie le délai imposé avant la prochaine tentative."""
    t = _now()
    with _lock:
        if len(_state) >= MAX_ENTRIES:
            for k in [k for k, v in _state.items() if t - v[1] > WINDOW]:
                del _state[k]
            if len(_state) >= MAX_ENTRIES:
                _state.pop(next(iter(_state)))
        st = _state.get(ip)
        if st is None or t - st[1] > WINDOW:
            st = [0.0, t, 0.0]
        st[0] += 1
        st[1] = t
        n = int(st[0])
        delay = 0.0 if n <= FREE_FAILURES else min(MAX_DELAY, BASE_DELAY * 2 ** (n - FREE_FAILURES - 1))
        st[2] = t + delay
        _state[ip] = st
        return delay


def success(ip: str) -> None:
    with _lock:
        _state.pop(ip, None)


def client_ip(headers: Mapping[str, str], peer: Optional[str], hops: int) -> str:
    """IP du client. Derrière ``hops`` proxys de confiance, c'est l'entrée ``-hops`` de X-Forwarded-For (les entrées de gauche
    sont fournies par le client et se falsifient ; Cloud Run ajoute la vraie adresse à droite)."""
    if hops > 0:
        parts = [p.strip() for p in headers.get("x-forwarded-for", "").split(",") if p.strip()]
        if len(parts) >= hops:
            try:
                return str(ipaddress.ip_address(parts[-hops]))
            except ValueError:
                pass
    return peer or "unknown"
