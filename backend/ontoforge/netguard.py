"""Protection SSRF des appels sortants (L27) : endpoints SPARQL (enregistrés ou temporaires) et fournisseurs LLM.

Active quand ``ONTOFORGE_PUBLIC=1`` (instance exposée sur Internet). Sinon, les appels passent tels quels par httpx (usage local,
Ollama sur la machine, endpoint sur le réseau de l'entreprise).

Règles quand elle est active :
- schéma http ou https seulement, pas d'identifiants dans l'URL ;
- noms refusés : ``localhost``, ``*.localhost``, ``*.internal`` (dont ``metadata.google.internal``), ``*.local``, ``metadata`` ;
- adresses refusées : tout ce qui n'est pas globalement routable (privé RFC 1918, bouclage, link-local dont 169.254.169.254,
  100.64/10, réservé, multicast, non spécifié, ULA et link-local IPv6 dont fd00:ec2::254), ainsi que les IPv4 encapsulées dans
  une IPv6 (::ffff:a.b.c.d, 6to4, Teredo, NAT64) qui sont jugées sur l'IPv4 qu'elles contiennent ;
- anti-rebinding : le nom est résolu UNE fois, TOUTES les adresses obtenues sont contrôlées, et la connexion TCP se fait sur
  l'adresse contrôlée (jamais une seconde résolution). Le TLS reste vérifié sur le nom d'origine (SNI et certificat) ;
- redirections : au plus ``MAX_REDIRECTS`` (3), chacune re-contrôlée, l'en-tête Authorization retiré quand l'hôte change ;
- liste blanche optionnelle ``ONTOFORGE_EGRESS_ALLOW`` (noms d'hôtes séparés par des virgules ; ``*.exemple.org`` accepté) :
  si elle est renseignée, seuls ces hôtes sont joignables (le contrôle d'adresse s'applique quand même).
"""
from __future__ import annotations

import ipaddress
import os
import re
import socket
from typing import Any, Iterable, Optional
from urllib.parse import urljoin, urlsplit

import httpcore
import httpx

MAX_REDIRECTS = 3
_BLOCKED_NAMES = {"localhost", "metadata", "metadata.google.internal", "instance-data"}
_BLOCKED_SUFFIXES = (".localhost", ".internal", ".local", ".localdomain", ".home.arpa")
_NAT64 = ipaddress.ip_network("64:ff9b::/96")
_NAT64_LOCAL = ipaddress.ip_network("64:ff9b:1::/48")
_TEREDO = ipaddress.ip_network("2001::/32")
_EXTRA_BLOCKED = [ipaddress.ip_network(n) for n in ("169.254.0.0/16", "fe80::/10", "fd00:ec2::/32", "100.64.0.0/10", "192.0.0.0/24", "198.18.0.0/15")]


class NetGuardError(Exception):
    """Appel sortant refusé (message français, sans secret)."""


def enabled() -> bool:
    return os.environ.get("ONTOFORGE_PUBLIC", "").strip().lower() in ("1", "true", "yes", "on")


def allowlist() -> list[str]:
    return [h.strip().lower().rstrip(".") for h in os.environ.get("ONTOFORGE_EGRESS_ALLOW", "").split(",") if h.strip()]


# --------------------------------------------------------------------------------------- contrôles

def _embedded_v4(ip: ipaddress.IPv6Address) -> Optional[ipaddress.IPv4Address]:
    if ip.ipv4_mapped is not None:
        return ip.ipv4_mapped
    if ip.sixtofour is not None:
        return ip.sixtofour
    if ip in _TEREDO and ip.teredo is not None:
        return ip.teredo[1]
    if ip in _NAT64 or ip in _NAT64_LOCAL:
        return ipaddress.IPv4Address(int(ip) & 0xFFFFFFFF)
    return None


def ip_allowed(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    if isinstance(ip, ipaddress.IPv6Address):
        v4 = _embedded_v4(ip)
        if v4 is not None:
            return ip_allowed(v4)
    if any(ip in n for n in _EXTRA_BLOCKED if n.version == ip.version):
        return False
    return bool(ip.is_global) and not (ip.is_multicast or ip.is_unspecified or ip.is_loopback or ip.is_link_local or ip.is_private or ip.is_reserved)


def _host_allowed_by_list(host: str, allow: Iterable[str]) -> bool:
    for a in allow:
        if a.startswith("*."):
            if host.endswith(a[1:]) and host != a[2:]:
                return True
        elif host == a:
            return True
    return False


def check_host(host: str) -> None:
    """Contrôle de forme du nom (avant résolution). Lève NetGuardError."""
    h = (host or "").strip().lower().rstrip(".")
    if not h:
        raise NetGuardError("Adresse refusée : nom d'hôte manquant.")
    try:
        literal = ipaddress.ip_address(h.strip("[]"))
    except ValueError:
        literal = None
    if literal is None:
        if re.fullmatch(r"(0x[0-9a-f]+|\d+)(\.(0x[0-9a-f]+|\d+))*", h):  # 2130706433, 0x7f.1, 0251.0376… : écritures détournées d'une IPv4
            raise NetGuardError("Adresse refusée : écriture numérique non standard d'une adresse IP.")
        if h in _BLOCKED_NAMES or h.endswith(_BLOCKED_SUFFIXES) or "." not in h:
            raise NetGuardError(f"Adresse refusée : « {h} » désigne une machine interne (serveur de métadonnées, boucle locale ou réseau privé).")
    elif not ip_allowed(literal):
        raise NetGuardError(f"Adresse refusée : {literal} est une adresse privée, locale ou réservée.")
    allow = allowlist()
    if allow and not _host_allowed_by_list(h, allow):
        raise NetGuardError(f"Adresse refusée : « {h} » ne figure pas dans la liste blanche des destinations (ONTOFORGE_EGRESS_ALLOW).")


def check_url(url: str) -> tuple[str, int]:
    """Valide l'URL (schéma, identifiants, nom d'hôte, liste blanche) ; renvoie (hôte, port). Ne résout rien."""
    try:
        u = urlsplit(url)
        port = u.port
    except ValueError:
        raise NetGuardError("Adresse refusée : URL illisible.") from None
    if u.scheme not in ("http", "https"):
        raise NetGuardError("Adresse refusée : seuls les schémas http et https sont autorisés.")
    if u.username or u.password:
        raise NetGuardError("Adresse refusée : les identifiants dans l'URL ne sont pas acceptés (utilisez les champs d'authentification).")
    if not u.hostname:
        raise NetGuardError("Adresse refusée : nom d'hôte manquant.")
    check_host(u.hostname)
    return u.hostname, port or (443 if u.scheme == "https" else 80)


def resolve_checked(host: str, port: int) -> list[str]:
    """Résout ``host`` une fois et vérifie TOUTES les adresses obtenues. Renvoie les adresses (chaînes) autorisées."""
    h = host.strip("[]")
    try:
        infos = socket.getaddrinfo(h, port, type=socket.SOCK_STREAM)
    except socket.gaierror:
        raise NetGuardError(f"Adresse injoignable : le nom « {host} » ne se résout pas.") from None
    ips: list[str] = []
    for fam, _t, _p, _c, sa in infos:
        raw = sa[0].split("%", 1)[0]
        ip = ipaddress.ip_address(raw)
        if not ip_allowed(ip):
            raise NetGuardError(f"Adresse refusée : « {host} » se résout vers une adresse privée, locale ou réservée ({ip}).")
        if raw not in ips:
            ips.append(raw)
    if not ips:
        raise NetGuardError(f"Adresse injoignable : le nom « {host} » ne se résout pas.")
    return ips


# ----------------------------------------------------------------------------------- transport épinglé

class _GuardedBackend(httpcore.SyncBackend):
    """Connecte sur l'adresse contrôlée. httpcore garde le nom d'origine pour le TLS (SNI + certificat) et l'en-tête Host."""

    def connect_tcp(self, host: str, port: int, timeout: Optional[float] = None, local_address: Optional[str] = None,
                    socket_options: Any = None) -> Any:
        last: Optional[Exception] = None
        for ip in resolve_checked(host, port):
            try:
                return super().connect_tcp(ip, port, timeout=timeout, local_address=local_address, socket_options=socket_options)
            except httpcore.ConnectError as exc:  # essaie l'adresse suivante
                last = exc
        raise last or httpcore.ConnectError("aucune adresse")


def guarded_client(timeout: float) -> httpx.Client:
    """Client httpx dont toute connexion passe par le contrôle d'adresse. Pas de proxy d'environnement, pas de redirection auto."""
    transport = httpx.HTTPTransport(trust_env=False)
    transport._pool._network_backend = _GuardedBackend()  # noqa: SLF001 — httpx n'expose pas le backend réseau
    return httpx.Client(transport=transport, timeout=timeout, follow_redirects=False, trust_env=False)


def request(method: str, url: str, *, timeout: float = 30.0, **kw: Any) -> httpx.Response:
    """Requête sortante contrôlée : redirections suivies à la main (3 au plus), chaque saut re-contrôlé.

    Lève NetGuardError (refus) ou httpx.HTTPError (échec réseau)."""
    headers = dict(kw.pop("headers", None) or {})
    auth = kw.pop("auth", None)
    cur, first_host = url, urlsplit(url).hostname
    with guarded_client(timeout) as c:
        for hop in range(MAX_REDIRECTS + 1):
            check_url(cur)
            h = urlsplit(cur).hostname
            if h != first_host:  # jamais d'identifiants vers un autre hôte
                headers = {k: v for k, v in headers.items() if k.lower() not in ("authorization", "x-api-key", "api-key", "x-goog-api-key")}
                auth = None
            r = c.request(method, cur, headers=headers, auth=auth, **kw)
            if r.status_code in (301, 302, 303, 307, 308) and r.headers.get("location"):
                if hop == MAX_REDIRECTS:
                    raise NetGuardError(f"Trop de redirections (plus de {MAX_REDIRECTS}).")
                cur = urljoin(cur, r.headers["location"])
                if r.status_code == 303 or (r.status_code in (301, 302) and method.upper() == "POST"):
                    method, kw = "GET", {}
                continue
            return r
    raise NetGuardError("Trop de redirections.")  # pragma: no cover


def post(url: str, **kw: Any) -> httpx.Response:
    """``httpx.post`` quand la protection est inactive (comportement historique), requête contrôlée sinon."""
    if not enabled():
        return httpx.post(url, **kw)
    return request("POST", url, **kw)


def client(timeout: float) -> httpx.Client:
    """Client pour ``queries.endpoint.make_client`` : httpx simple si inactif ; sinon client contrôlé qui re-vérifie l'URL."""
    if not enabled():
        return httpx.Client(timeout=timeout)
    return _CheckedClient(timeout)


class _CheckedClient:
    """Interface minimale (``post``, context manager) au-dessus de ``request``, utilisée par queries/endpoint.py."""

    def __init__(self, timeout: float) -> None:
        self.timeout = timeout

    def __enter__(self) -> "_CheckedClient":
        return self

    def __exit__(self, *a: Any) -> None:
        return None

    def post(self, url: str, **kw: Any) -> httpx.Response:
        return request("POST", url, timeout=self.timeout, **kw)
