"""Contenu et persistance du triplestore local d'un projet (L19).

Disposition sur disque : `$ONTOFORGE_DATA/projects/<id>/triplestore/{db/, meta.json}` (base RocksDB d'Oxigraph + métadonnées).
Graphes nommés (le graphe par défaut du magasin contient leur UNION DÉDUPLIQUÉE, reconstruite à chaque écriture, voir `rebuild_union`) :
- `urn:ontoforge:graph:ontology`    TBox de l'ontologie du projet (régénérée à chaque synchronisation) ;
- `urn:ontoforge:graph:individuals` individus du projet (ABox de l'éditeur) ;
- `urn:ontoforge:graph:data:<nom>`  un fichier de données importé (Turtle, N-Triples, JSON-LD, RDF/XML) ;
- `urn:ontoforge:graph:inferred`    triplets matérialisés par owlrl (RDFS ou OWL RL), jetables.

Isolement : aucun accès réseau (le JSON-LD distant est refusé par le parseur d'Oxigraph ; `SERVICE` est refusé avant exécution),
plafonds de taille de fichier et de triplets, une seule écriture à la fois (verrou lecteurs/écrivain par projet).
"""
from __future__ import annotations

import gc
import hashlib
import json
import os
import re
import shutil
import threading
import time
import unicodedata
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Optional

import pyoxigraph as ox

from .. import childproc
from ..projects import store as project_store

G_ONTOLOGY = "urn:ontoforge:graph:ontology"
G_INDIVIDUALS = "urn:ontoforge:graph:individuals"
G_INFERRED = "urn:ontoforge:graph:inferred"
G_DATA = "urn:ontoforge:graph:data:"
SEMANTICS = ("rdfs", "owlrl", "both")
FORMATS = {".ttl": ox.RdfFormat.TURTLE, ".turtle": ox.RdfFormat.TURTLE, ".nt": ox.RdfFormat.N_TRIPLES,
           ".jsonld": ox.RdfFormat.JSON_LD, ".json": ox.RdfFormat.JSON_LD,
           ".rdf": ox.RdfFormat.RDF_XML, ".owl": ox.RdfFormat.RDF_XML, ".xml": ox.RdfFormat.RDF_XML}
FORMAT_NAMES = {ox.RdfFormat.TURTLE: "turtle", ox.RdfFormat.N_TRIPLES: "n-triples", ox.RdfFormat.JSON_LD: "json-ld",
                ox.RdfFormat.RDF_XML: "rdf/xml"}


class StoreError(Exception):
    """Erreur lisible (français) avec le code HTTP proposé pour l'API."""

    def __init__(self, message: str, status: int = 422):
        super().__init__(message)
        self.status = status


# ------------------------------------------------------------------------------------------ plafonds

def _env_int(name: str, default: int) -> int:
    try:
        return max(1, int(os.environ.get(name, default)))
    except ValueError:
        return default


def _env_nonneg(name: str, default: int) -> int:
    try:
        return max(0, int(os.environ.get(name, default)))
    except ValueError:
        return default


def limits() -> dict[str, int]:
    """Plafonds (variables d'environnement `ONTOFORGE_LOCAL_STORE_*`)."""
    return {
        "max_triples": _env_int("ONTOFORGE_LOCAL_STORE_MAX_TRIPLES", 1_000_000),
        "max_upload_mb": _env_int("ONTOFORGE_LOCAL_STORE_MAX_UPLOAD_MB", 25),
        "max_inference_triples": _env_int("ONTOFORGE_LOCAL_STORE_MAX_INFERENCE_TRIPLES", 30_000),
        "max_validation_triples": _env_int("ONTOFORGE_LOCAL_STORE_MAX_VALIDATION_TRIPLES", 60_000),
        "query_timeout_s": _env_int("ONTOFORGE_LOCAL_STORE_TIMEOUT_S", 20),
        "inference_timeout_s": _env_int("ONTOFORGE_LOCAL_STORE_INFERENCE_TIMEOUT_S", 90),
        "query_memory_mb": _env_int("ONTOFORGE_LOCAL_STORE_MEMORY_MB", 3072),
        # L53 (D-L53-02) : disque éphémère (en mémoire sur Cloud Run), 0 = sans plafond ni purge (hors Cloud Run)
        "total_mb": _env_nonneg("ONTOFORGE_LOCAL_STORE_TOTAL_MB", 0),
        "idle_min": _env_nonneg("ONTOFORGE_LOCAL_STORE_IDLE_MIN", 0),
    }


# ------------------------------------------------------------------------------------ places des processus fils

class StoreBusy(StoreError):
    """Toutes les places des processus fils du triplestore local sont prises : 503 avec `Retry-After` (L53, DF-B13)."""

    retry_after = 5

    def __init__(self) -> None:
        super().__init__("Trop de requêtes ou d'inférences en cours sur le triplestore local : réessayez dans quelques secondes.", 503)


def _slot_count() -> int:
    try:
        return max(1, min(32, int(os.environ.get("ONTOFORGE_LOCAL_STORE_SLOTS", "2"))))
    except ValueError:
        return 2


# Une seule famille de places pour les requêtes ET l'inférence, tous projets confondus : chaque fils peut prendre `query_memory_mb`
# d'espace d'adressage, la somme est donc places × plafond. Même modèle que ONTOFORGE_SHACL_SLOTS (shacl/validate.py).
_SLOTS = threading.BoundedSemaphore(_slot_count())


@contextmanager
def child_slot() -> Iterator[None]:
    """Réserve une place pour un processus fils (requête ou inférence) ; lève `StoreBusy` sans attendre si elles sont toutes prises."""
    if not _SLOTS.acquire(blocking=False):
        raise StoreBusy()
    try:
        yield
    finally:
        _SLOTS.release()


def _load_slot_count() -> int:
    try:
        return max(1, min(8, int(os.environ.get("ONTOFORGE_LOCAL_STORE_LOAD_SLOTS", "4"))))
    except ValueError:
        return 4


# L53 (B2 de la relecture déploiement) : un chargement analyse et écrit DANS le processus du serveur (environ 1,7 Mo de mémoire pour
# 1 000 triplets, mesuré le 24/11) : places bornées, comme les fils. Prise par la route avant la lecture du fichier.
_LOAD_SLOTS = threading.BoundedSemaphore(_load_slot_count())


@contextmanager
def load_slot() -> Iterator[None]:
    """Réserve une place de chargement (lecture + analyse + écriture d'un fichier dans le serveur) ; `StoreBusy` (503) sans attendre si pleine."""
    if not _LOAD_SLOTS.acquire(blocking=False):
        raise StoreBusy()
    try:
        yield
    finally:
        _LOAD_SLOTS.release()


# ----------------------------------------------------------------------------- verrou lecteurs/écrivain

class _RWLock:
    def __init__(self) -> None:
        self._c = threading.Condition()
        self._readers = 0
        self._writer = False

    @contextmanager
    def read(self) -> Iterator[None]:
        with self._c:
            while self._writer:
                self._c.wait()
            self._readers += 1
        try:
            yield
        finally:
            with self._c:
                self._readers -= 1
                self._c.notify_all()

    @contextmanager
    def write(self) -> Iterator[None]:
        with self._c:
            while self._writer or self._readers:
                self._c.wait()
            self._writer = True
        try:
            yield
        finally:
            with self._c:
                self._writer = False
                self._c.notify_all()


    @contextmanager
    def try_write(self) -> Iterator[bool]:
        """Verrou d'écriture pris SANS attendre : rend False (et ne prend rien) si une lecture ou une écriture est en cours."""
        with self._c:
            ok = not self._writer and not self._readers
            if ok:
                self._writer = True
        try:
            yield ok
        finally:
            if ok:
                with self._c:
                    self._writer = False
                    self._c.notify_all()


_LOCKS: dict[str, _RWLock] = {}
_LOCKS_GUARD = threading.Lock()


def lock(pid: str) -> _RWLock:
    with _LOCKS_GUARD:
        return _LOCKS.setdefault(pid, _RWLock())


# -------------------------------------------------------------------------------------------- chemins

def local_dir() -> Optional[Path]:
    """``ONTOFORGE_LOCAL_STORE_DIR`` : dossier LOCAL (disque de l'instance, ex. /tmp) où vit le triplestore, à la place de
    ``<projet>/triplestore``. Sur Cloud Run, ``/data`` est un montage Cloud Storage FUSE sur lequel RocksDB (verrous, mmap, renommages)
    ne doit pas vivre ; ce dossier est éphémère : perdu à l'arrêt de l'instance, reconstruit à la demande (`ensure`)."""
    v = os.environ.get("ONTOFORGE_LOCAL_STORE_DIR", "").strip()
    return Path(v) if v else None


def ephemeral() -> bool:
    return local_dir() is not None


def root(pid: str) -> Path:
    d = local_dir()
    if d is not None:
        project_store.project_dir(pid)  # valide l'identifiant (ProjectNotFound sinon)
        return d / pid
    return project_store.project_dir(pid) / "triplestore"


def purge(pid: str) -> None:
    """Supprime le triplestore d'un projet supprimé quand il vit hors du dossier du projet."""
    if ephemeral():
        shutil.rmtree(root(pid), ignore_errors=True)
        with _USE_GUARD:
            _LAST_USE.pop(pid, None)
            _PURGED.pop(pid, None)


def db_path(pid: str) -> Path:
    return root(pid) / "db"


# ------------------------------------------------------------------ disque éphémère : plafond total et purge (L53, D-L53-02)
# Sur Cloud Run le système de fichiers de l'instance est en mémoire : les bases de `ONTOFORGE_LOCAL_STORE_DIR` comptent dans les 2 Gio.
# Deux garde-fous réglables, actifs seulement quand le dossier est local et éphémère :
# - `ONTOFORGE_LOCAL_STORE_TOTAL_MB` : taille totale du dossier ; un chargement qui la ferait dépasser est refusé (413) ;
# - `ONTOFORGE_LOCAL_STORE_IDLE_MIN` : une base non utilisée depuis ce nombre de minutes est supprimée (les fichiers chargés sont perdus ;
#   l'ontologie et les individus sont recréés à la demande par `ensure`).
_ONTOLOGY_ESTIMATE = 10_000  # triplets (ontologie + individus d'un projet courant : 4 700 pour automaint)
BYTES_PER_TRIPLE = 500   # mesuré le 24/11 : 470 octets par triplet sur disque pour des littéraux de 25 caractères, union comprise
COMPACTION_MARGIN = 1.25  # la taille monte transitoirement pendant les compactions de RocksDB (1,06 à 1,24 fois la taille finale mesurée)
_LAST_USE: dict[str, float] = {}
_PURGED: dict[str, dict[str, Any]] = {}
_USE_GUARD = threading.Lock()


def touch(pid: str) -> None:
    """Note l'usage du triplestore d'un projet (horloge de la purge) et efface l'avis de purge dès qu'un fichier est rechargé ailleurs."""
    with _USE_GUARD:
        _LAST_USE[pid] = time.monotonic()


def dir_size_mb() -> float:
    """Taille totale (Mo) du dossier éphémère des triplestores ; 0 s'il n'est pas utilisé."""
    d = local_dir()
    if d is None or not d.is_dir():
        return 0.0
    total = 0
    for base, _, files in os.walk(d):
        for name in files:
            try:
                total += os.path.getsize(os.path.join(base, name))
            except OSError:
                pass
    return total / 1048576


def check_disk_budget(extra_triples: int) -> None:
    """413 si le chargement de `extra_triples` triplets ferait dépasser `ONTOFORGE_LOCAL_STORE_TOTAL_MB` (marge de compaction comprise)."""
    lim = limits()
    cap = lim["total_mb"]
    if not ephemeral() or not cap:
        return
    used = dir_size_mb()
    need = extra_triples * BYTES_PER_TRIPLE / 1048576
    if (used + need) * COMPACTION_MARGIN > cap:
        raise StoreError(f"Espace du triplestore local plein : {used:.0f} Mo utilisés sur {cap} Mo, ce chargement en demande environ {need:.0f} de plus. "
                         f"Videz le triplestore d'un autre projet, ou attendez la purge des bases inactives (au bout de {lim['idle_min'] or 'N'} min).", 413)


def purge_idle(skip: Optional[str] = None) -> list[str]:
    """Supprime les bases inactives depuis `ONTOFORGE_LOCAL_STORE_IDLE_MIN` minutes (sauf `skip`). Chaque suppression se fait sous le verrou
    d'écriture du projet, pris SANS attendre : une base en cours d'usage est laissée. Appelée avant chaque création, chargement ou lecture ;
    pas de tâche de fond. Rend les identifiants purgés."""
    idle = limits()["idle_min"]
    d = local_dir()
    if not idle or d is None or not d.is_dir():
        return []
    now, purged = time.monotonic(), []
    for entry in sorted(d.iterdir()):
        pid = entry.name
        if pid == skip or not entry.is_dir():
            continue
        with _USE_GUARD:
            last = _LAST_USE.setdefault(pid, now)  # base sans horloge (redémarrage, copie) : l'attente commence maintenant
        if now - last < idle * 60:
            continue
        with lock(pid).try_write() as ok:
            if not ok:
                continue
            with _USE_GUARD:  # horloge relue sous le verrou : un usage qui vient de commencer sauve la base (it2)
                if time.monotonic() - _LAST_USE.get(pid, now) < idle * 60:
                    continue
            meta = _meta_read(pid)
            gc.collect()
            shutil.rmtree(entry, ignore_errors=True)
            with _USE_GUARD:
                _LAST_USE.pop(pid, None)
                _PURGED[pid] = {"at": now_iso(), "files": [f.get("name", "") for f in meta.get("files", [])], "idle_min": idle}
            purged.append(pid)
    return purged


def exists(pid: str) -> bool:
    return db_path(pid).is_dir()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _meta_read(pid: str) -> dict[str, Any]:
    try:
        return json.loads((root(pid) / "meta.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"version": 1, "files": [], "inference": None, "ontology_signature": None, "created_at": None}


def _meta_write(pid: str, meta: dict[str, Any]) -> None:
    project_store._atomic_write(root(pid) / "meta.json", json.dumps(meta, ensure_ascii=False, indent=2))


def _open_rw(pid: str) -> ox.Store:
    db_path(pid).parent.mkdir(parents=True, exist_ok=True)
    try:
        return ox.Store(str(db_path(pid)))
    except OSError as exc:
        raise StoreError(f"Le triplestore local est verrouillé ou illisible ({str(exc)[:120]}).", 503) from None


def _with_store(pid: str, fn: Any, readonly: bool = False) -> Any:
    """Ouvre la base, appelle `fn(store)`, la referme. Oxigraph ne referme RocksDB qu'à la destruction de l'objet : la seule
    référence est locale à cette fonction (un `store` conservé par l'appelant garderait la base ouverte et ses fichiers mouvants)."""
    try:
        store = ox.Store.read_only(str(db_path(pid))) if readonly else _open_rw(pid)
    except OSError as exc:
        raise StoreError(f"Le triplestore local est illisible ({str(exc)[:120]}).", 503) from None
    try:
        out = fn(store)
        if not readonly:
            rebuild_union(store)  # chaque écriture (chargement, vidage, inférence, synchronisation) refait l'union dédupliquée
            store.flush()
        return out
    except Exception as exc:
        if not readonly:
            try:  # écriture interrompue (inférence en échec, plafond...) : l'union ne doit jamais rester périmée (revue it2)
                rebuild_union(store)
            except Exception:  # noqa: BLE001 - la cause d'origine prime
                pass
        exc.__traceback__ = None  # le traceback garderait `store` vivant (via les cadres de `fn`) : la base resterait verrouillée
        raise
    finally:
        del store
        gc.collect()


def _count(store: ox.Store, graph: str) -> int:
    return sum(1 for _ in store.quads_for_pattern(None, None, None, ox.NamedNode(graph)))


def _total(store: ox.Store) -> int:
    """Quads des graphes NOMMÉS (le graphe par défaut n'est que l'union dérivée, il ne compte pas)."""
    return len(store) - sum(1 for _ in store.quads_for_pattern(None, None, None, ox.DefaultGraph()))


def rebuild_union(store: ox.Store) -> int:
    """Matérialise dans le graphe par défaut l'union DÉDUPLIQUÉE des graphes nommés (SPARQL 1.1 §13.1 : le graphe par défaut est
    un graphe RDF, donc un ensemble). Oxigraph 0.5.13 sert sinon `use_default_graph_as_union` en multi-ensemble (COUNT = 2 pour
    un triplet présent dans deux graphes) ; le magasin, lui, est un ensemble par graphe, d'où la déduplication à l'insertion.
    Lecture par blocs : jamais d'itérateur ouvert pendant l'écriture."""
    import itertools
    d = ox.DefaultGraph()
    store.clear_graph(d)
    for g in list(store.named_graphs()):
        it = iter(store.quads_for_pattern(None, None, None, g))
        while True:
            chunk = list(itertools.islice(it, 50_000))
            if not chunk:
                break
            store.bulk_extend(ox.Quad(q.subject, q.predicate, q.object, d) for q in chunk)
    return sum(1 for _ in store.quads_for_pattern(None, None, None, d))


def _replace_graph(store: ox.Store, graph: str, nt: bytes) -> int:
    g = ox.NamedNode(graph)
    store.clear_graph(g)
    if nt.strip():
        store.load(input=nt, format=ox.RdfFormat.N_TRIPLES, to_graph=g)
    return _count(store, graph)


# --------------------------------------------------------------------------- ontologie et individus

def _project_graphs(p: Any) -> tuple[bytes, bytes]:
    """(TBox, individus) du projet en N-Triples. Les individus = triplets dont le sujet est un individu de l'éditeur (+ nœuds anonymes liés)."""
    import rdflib
    from ..io.rdf_export import model_to_graph
    tbox = model_to_graph(p.onto.model_copy(update={"individuals": {}}))
    full = model_to_graph(p.onto)
    subjects = {rdflib.URIRef(i) for i in p.onto.individuals}
    ind = rdflib.Graph()
    todo, seen = list(subjects), set()
    while todo:
        s = todo.pop()
        if s in seen:
            continue
        seen.add(s)
        for t in full.triples((s, None, None)):
            ind.add(t)
            if isinstance(t[2], rdflib.BNode):
                todo.append(t[2])
    nt = lambda g: g.serialize(format="nt", encoding="utf-8")  # noqa: E731
    return nt(tbox), nt(ind)


def signature(p: Any) -> str:
    """Empreinte de l'ontologie du projet (l'horodatage `updated_at` n'a qu'une résolution d'une seconde)."""
    return hashlib.sha1(p.onto.model_dump_json().encode("utf-8")).hexdigest()


def _sync_ontology(pid: str, p: Any, store: ox.Store, meta: dict[str, Any]) -> None:
    tb, ind = _project_graphs(p)
    n_tb = _replace_graph(store, G_ONTOLOGY, tb)
    n_ind = _replace_graph(store, G_INDIVIDUALS, ind)
    meta["ontology_signature"] = signature(p)
    meta["ontology_triples"], meta["individuals_triples"] = n_tb, n_ind
    if meta.get("inference"):
        meta["inference"]["stale"] = True  # l'ontologie a changé depuis la matérialisation


def ensure(pid: str, p: Any) -> None:
    """Crée le triplestore s'il n'existe pas (ontologie + individus du projet) ; resynchronise l'ontologie si le projet a changé."""
    purge_idle(skip=pid)
    touch(pid)
    with lock(pid).write():
        meta = _meta_read(pid)
        if exists(pid) and meta.get("ontology_signature") == signature(p):
            return
        if not exists(pid):
            check_disk_budget(_ONTOLOGY_ESTIMATE)  # nouvelle base : de la place pour l'ontologie et les individus
        _with_store(pid, lambda store: _sync_ontology(pid, p, store, meta))
        meta["created_at"] = meta.get("created_at") or now_iso()
        _meta_write(pid, meta)


# ------------------------------------------------------------------------------------------ chargement

def slug(name: str) -> str:
    norm = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^A-Za-z0-9._-]+", "-", norm).strip("-")[:80] or "donnees"


def detect_format(filename: str, raw: bytes) -> ox.RdfFormat:
    ext = os.path.splitext(filename.lower())[1]
    if ext in FORMATS:
        return FORMATS[ext]
    head = raw[:2000].lstrip(b"\xef\xbb\xbf \t\r\n")
    if head[:1] in (b"{", b"["):
        return ox.RdfFormat.JSON_LD
    if head[:5] == b"<?xml" or head[:4] == b"<rdf":
        return ox.RdfFormat.RDF_XML
    return ox.RdfFormat.TURTLE


def _parse_error(exc: Exception, filename: str) -> StoreError:
    msg = str(exc).splitlines()[0][:240] if str(exc) else type(exc).__name__
    if "LoadDocumentCallback" in msg or "remote context" in msg.lower():
        return StoreError(f"« {filename} » : le contexte JSON-LD distant est refusé (aucun accès réseau depuis le triplestore local) ; "
                          "intégrez le contexte dans le fichier.", 422)
    return StoreError(f"« {filename} » : fichier RDF illisible — {msg}", 422)


def parse_to_store(raw: bytes, filename: str) -> tuple[ox.Store, ox.RdfFormat]:
    """Lit un fichier RDF EN FLUX dans un magasin mémoire temporaire (validation + comptage avant tout écrit sur disque) : l'analyse
    s'arrête dès que le plafond de triplets est dépassé, au lieu de matérialiser un Turtle compact qui en produirait des millions."""
    import itertools

    from ..io import safe_parse
    fmt = detect_format(filename, raw)
    # L52 (DF-B08) : mêmes gardes que l'import d'ontologie (io/safe_parse.py) : tout DOCTYPE refusé en RDF/XML (Oxigraph développe
    # les entités internes), contexte JSON-LD distant et imbrication excessive refusés. La taille est bornée par load_data.
    try:
        if fmt == ox.RdfFormat.RDF_XML:
            safe_parse.check_xml(raw, strict=True)  # échec fermé : Oxigraph est plus tolérant qu'expat (revue secu L52 it1)
        elif fmt == ox.RdfFormat.JSON_LD:
            safe_parse.check_jsonld(raw)
    except safe_parse.UnsafeRdfError as exc:
        if fmt == ox.RdfFormat.JSON_LD and "distant" in str(exc):  # message historique du triplestore pour un contexte distant
            raise _parse_error(ValueError("remote context"), filename) from None
        raise StoreError(f"« {filename} » : {exc}", 422) from None
    cap = limits()["max_triples"]
    tmp = ox.Store()
    n = 0
    try:
        it = ox.parse(input=raw, format=fmt)
        while True:
            chunk = list(itertools.islice(it, 20_000))
            if not chunk:
                break
            n += len(chunk)
            if n > cap:
                raise StoreError(f"Plafond de {cap:,} triplets dépassé par « {filename} » (analyse interrompue).".replace(",", " "), 413)
            tmp.bulk_extend(chunk)
    except (SyntaxError, ValueError, OSError) as exc:
        raise _parse_error(exc, filename) from None
    except MemoryError:  # L52 (revue secu) : le lecteur d'Oxigraph refuse un élément de plus de 16 Mio (taille maximale de son tampon)
        raise StoreError(f"« {filename} » : un élément du fichier (littéral ou IRI) est trop gros pour le lecteur RDF (16 Mio au plus).", 413) from None
    return tmp, fmt


def _dump_nt(store: ox.Store, graph: str) -> bytes:
    return store.dump(None, ox.RdfFormat.N_TRIPLES, from_graph=ox.NamedNode(graph)) or b""


def load_data(pid: str, p: Any, raw: bytes, filename: str, *, source: str = "upload", inference: Optional[str] = None) -> dict[str, Any]:
    """Ajoute (ou remplace, à nom égal) un fichier de données. `inference` : None = conserver le réglage, "none" = retirer, "rdfs" | "owlrl"."""
    lim = limits()
    if len(raw) > lim["max_upload_mb"] * 1024 * 1024:
        raise StoreError(f"Fichier trop volumineux (plafond {lim['max_upload_mb']} Mo).", 413)
    if not raw.strip():
        raise StoreError(f"« {filename} » est vide.", 422)
    check_semantics(inference)
    tmp, fmt = parse_to_store(raw, filename)
    n_new = len(tmp)  # majorant (quads de tous les graphes) ; le compte exact est relu après insertion
    graph = G_DATA + slug(filename)
    ensure(pid, p)
    with lock(pid).write():
        meta = _meta_read(pid)
        check_disk_budget(n_new)

        def work(store: ox.Store) -> None:
            others = _total(store) - _count(store, graph)
            if others + n_new > lim["max_triples"]:
                raise StoreError(f"Plafond de {lim['max_triples']:,} triplets dépassé ({others + n_new:,} après chargement).".replace(",", " "), 413)
            g = ox.NamedNode(graph)
            previous = _dump_nt(store, graph)  # restauré si l'inférence échoue : le chargement est tout ou rien
            store.clear_graph(g)
            # Tous les graphes du fichier (un JSON-LD peut porter des graphes nommés `@graph` + `@id`) sont aplatis dans le graphe du
            # fichier : avant la revue w3c L19 it1, seuls les triplets du graphe par défaut étaient copiés et les autres perdus en silence.
            store.bulk_extend(ox.Quad(q.subject, q.predicate, q.object, g) for q in tmp.quads_for_pattern(None, None, None, None))
            n_file = _count(store, graph)
            meta["files"] = [f for f in meta.get("files", []) if f["graph"] != graph] + [
                {"graph": graph, "name": filename, "format": FORMAT_NAMES.get(fmt, str(fmt)), "triples": n_file, "source": source, "loaded_at": now_iso()}]
            try:
                _apply_inference(pid, store, meta, inference)
            except Exception:
                _replace_graph(store, graph, previous)
                raise

        _with_store(pid, work)
        _meta_write(pid, meta)
    with _USE_GUARD:
        _PURGED.pop(pid, None)  # de nouvelles données : l'avis de purge n'a plus d'objet
    return stats(pid, p)


def refresh(pid: str, p: Any, inference: Optional[str] = None) -> dict[str, Any]:
    """Resynchronise l'ontologie et les individus du projet ; recalcule l'inférence si elle est active (ou demandée)."""
    check_semantics(inference)
    ensure(pid, p)
    with lock(pid).write():
        meta = _meta_read(pid)
        _with_store(pid, lambda store: _apply_inference(pid, store, meta, inference))
        _meta_write(pid, meta)
    return stats(pid, p)


def drop(pid: str) -> None:
    """Suppression du projet : vide le magasin sous le verrou d'écriture (attend les requêtes en cours) puis oublie le verrou."""
    clear(pid)
    with _LOCKS_GUARD:
        _LOCKS.pop(pid, None)


def clear(pid: str) -> None:
    """Vide complètement le triplestore (supprime la base et les métadonnées)."""
    with lock(pid).write():
        gc.collect()
        shutil.rmtree(root(pid), ignore_errors=True)
    with _USE_GUARD:
        _LAST_USE.pop(pid, None)
        _PURGED.pop(pid, None)


# ---------------------------------------------------------------------------------------------- inférence

def check_semantics(s: Optional[str]) -> None:
    if s not in (None, "none", *SEMANTICS):
        raise StoreError(f"Inférence inconnue « {s} » (attendu : none, rdfs, owlrl, both).", 422)


def _apply_inference(pid: str, store: ox.Store, meta: dict[str, Any], requested: Optional[str]) -> None:
    """None = conserver la sémantique en cours (et recalculer, les données ont changé) ; "none" = retirer ; "rdfs" | "owlrl"."""
    current = (meta.get("inference") or {}).get("semantics")
    want = current if requested is None else (None if requested == "none" else requested)
    if want is None:
        if _count(store, G_INFERRED):
            store.clear_graph(ox.NamedNode(G_INFERRED))
        meta["inference"] = None
        return
    meta["inference"] = materialize(store, want)


def materialize(store: ox.Store, semantics: str) -> dict[str, Any]:
    """Calcule la fermeture owlrl de (ontologie + individus + données) et stocke les seuls faits utiles dans le graphe inféré."""
    lim = limits()
    sources = [G_ONTOLOGY, G_INDIVIDUALS] + [g.value for g in store.named_graphs() if g.value.startswith(G_DATA)]
    n_src = sum(_count(store, g) for g in sources)
    if n_src > lim["max_inference_triples"]:
        raise StoreError(f"Inférence limitée à {lim['max_inference_triples']:,} triplets sources ({n_src:,} ici) : owlrl est un moteur Python "
                         "qui matérialise en mémoire. Réduisez les données ou utilisez un endpoint avec raisonnement.".replace(",", " "), 413)
    nt = b"".join(_dump_nt(store, g) for g in sources)
    worker = Path(__file__).with_name("_infer_worker.py")
    timeout = lim["inference_timeout_s"]
    # L52 (DF-B07) : même isolement que les requêtes (runner.py) et SHACL : environnement réduit, mémoire (RLIMIT_AS) et CPU plafonnés
    try:
        with child_slot():  # L53 (DF-B13) : places partagées avec les requêtes ; StoreBusy (503) remonte telle quelle
            proc = childproc.run_limited(worker, nt, timeout=timeout, mem_mb=lim["query_memory_mb"], cpu_s=int(timeout) + 2, fsize=0,
                                         args=[semantics])
    except childproc.TimeoutExpired:
        raise StoreError(f"Inférence {semantics} interrompue après {timeout} s (graphe trop gros ou trop riche pour owlrl).", 504) from None
    if proc.returncode != 0:
        if proc.returncode < 0 or b"MemoryError" in proc.stderr:
            raise StoreError(f"Inférence {semantics} interrompue : mémoire ou temps de calcul plafonnés (graphe trop gros ou trop riche "
                             "pour owlrl). Réduisez les données ou utilisez un endpoint avec raisonnement.", 413)
        tail = (proc.stderr.decode("utf-8", "replace").strip().splitlines() or ["erreur inconnue"])[-1][:200]
        raise StoreError("Échec de l'inférence : " + tail, 500)
    # it2 (budget disque) : le graphe inféré entre dans le plafond total. Contrôle AVANT le remplacement : refus 413 tout ou rien (l'ancien
    # graphe inféré est conservé ; un chargement qui l'a demandé restaure son fichier).
    check_disk_budget(max(0, proc.stdout.count(b"\n") - _count(store, G_INFERRED)))
    n_inf = _replace_graph(store, G_INFERRED, proc.stdout)
    notes = []
    m = re.search(rb"NOTE hasKey (\d+)", proc.stderr)
    if m:  # revue w3c L19 it1 : prp-key déduit owl:sameAs (pas d'unicité en OWL) ; SHACL Core ne vérifie pas l'unicité entre individus
        notes.append(f"owl:hasKey ignoré ({m.group(1).decode()} axiomes) : la règle prp-key d'OWL 2 RL (qui déduirait owl:sameAs entre "
                     "individus de mêmes valeurs de clé) est trop lente dans owlrl ; cherchez les doublons de clé par une requête "
                     "SPARQL (GROUP BY sur les propriétés clés, HAVING (COUNT(*) > 1)).")
    m = re.search(rb"NOTE sameAs (\d+)", proc.stderr)
    if m:
        notes.append(f"{m.group(1).decode()} triplets owl:sameAs déduits (pas d'hypothèse de noms uniques en OWL : propriété "
                     "fonctionnelle ou inverse fonctionnelle à plusieurs valeurs) : à vérifier, c'est souvent une erreur de données.")
    for e in re.findall(rb"^ERROR (.*)$", proc.stderr, re.M)[:5]:
        notes.append("Incohérence OWL RL détectée par owlrl : " + e.decode("utf-8", "replace"))
    return {"semantics": semantics, "triples": n_inf, "source_triples": n_src, "at": now_iso(), "stale": False, "notes": notes}


# ------------------------------------------------------------------------------------------------ stats

def demo_for(p: Any) -> Optional[dict[str, str]]:
    """Jeu de démonstration de l'exemple d'origine du projet (`*demo-data*` de samples/<nom>/), s'il y en a un."""
    from .. import samples
    root_dir = samples.samples_root()
    if not root_dir.is_dir():
        return None
    srcs = set(p.source_files)
    for d in sorted(x for x in root_dir.iterdir() if x.is_dir() and not x.name.startswith(".")):
        info = samples.describe(d)
        if not (srcs & set(info["ontology"])):
            continue
        demo = [f for f in info["data"] if "demo" in f.lower()]
        if demo:
            return {"sample": d.name, "file": demo[0]}
    return None


def stats(pid: str, p: Any) -> dict[str, Any]:
    lim = limits()
    base = {"limits": lim, "demo": demo_for(p), "engine": "pyoxigraph " + ox.__version__, "ephemeral": ephemeral()}
    if ephemeral():
        base["disk"] = {"used_mb": round(dir_size_mb(), 1), "total_mb": lim["total_mb"], "idle_min": lim["idle_min"]}
        gone = _PURGED.get(pid)
        if gone:
            n = len(gone["files"])
            base["purged"] = {"at": gone["at"], "files": gone["files"], "message": (
                f"{n} fichier(s) de données chargé(s) dans ce triplestore ont été supprimé(s) après {gone['idle_min']} min d'inactivité, pour libérer la "
                "mémoire de l'instance. L'ontologie et les individus du projet sont recréés à la demande ; rechargez vos fichiers de données."
                if n else
                f"Le triplestore de ce projet a été supprimé après {gone['idle_min']} min d'inactivité, pour libérer la mémoire de l'instance ; "
                "il est recréé à la demande.")}
    if not exists(pid):
        return {"exists": False, "triples": 0, "graphs": [], "inference": None, "ontology_stale": False, **base}
    with lock(pid).read():
        if not exists(pid):  # purgée entre le test et le verrou (it2)
            return {"exists": False, "triples": 0, "graphs": [], "inference": None, "ontology_stale": False, **base}
        meta = _meta_read(pid)
        total, inferred = _with_store(pid, lambda store: (_total(store), _count(store, G_INFERRED)), readonly=True)
    graphs = [{"graph": G_ONTOLOGY, "kind": "ontology", "name": "ontology", "triples": meta.get("ontology_triples", 0)},
              {"graph": G_INDIVIDUALS, "kind": "individuals", "name": "individuals", "triples": meta.get("individuals_triples", 0)}]
    graphs += [{"graph": f["graph"], "kind": "data", "name": f["name"], "triples": f["triples"], "format": f.get("format"),
                "source": f.get("source"), "loaded_at": f.get("loaded_at")} for f in meta.get("files", [])]
    if inferred:
        graphs.append({"graph": G_INFERRED, "kind": "inferred", "name": (meta.get("inference") or {}).get("semantics", ""), "triples": inferred})
    return {"exists": True, "triples": total, "graphs": graphs, "inference": meta.get("inference"),
            "ontology_stale": meta.get("ontology_signature") != signature(p), "size_kb": _disk_kb(pid), **base}


def data_graphs(pid: str) -> list[str]:
    """IRI des graphes de fichiers de données importés."""
    return [f["graph"] for f in _meta_read(pid).get("files", [])]


def _disk_kb(pid: str) -> int:
    return sum(f.stat().st_size for f in db_path(pid).rglob("*") if f.is_file()) // 1024


# ------------------------------------------------------------------------------ export (SHACL, valeurs)

def to_rdflib(pid: str, graphs: tuple[str, ...] | None = None, max_triples: int | None = None) -> Any:
    """Contenu du triplestore (par défaut individus + données, sans la TBox ni l'inféré) sous forme de graphe rdflib."""
    import rdflib
    out = rdflib.Graph()
    if not exists(pid):
        return out
    def read(store: ox.Store) -> None:
        names = list(graphs) if graphs else [G_INDIVIDUALS] + [g.value for g in store.named_graphs() if g.value.startswith(G_DATA)]
        n = sum(_count(store, g) for g in names)
        if max_triples is not None and n > max_triples:
            raise StoreError(f"Validation limitée à {max_triples:,} triplets ({n:,} ici).".replace(",", " "), 413)
        for g in names:
            out.parse(data=_dump_nt(store, g), format="nt")

    with lock(pid).read():
        _with_store(pid, read, readonly=True)
    return out
