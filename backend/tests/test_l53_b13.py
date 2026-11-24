"""L53 (DF-B13) : nombre de places des processus fils du triplestore local (requêtes et inférence).

Avant : aucun nombre de places, N appels sur N projets lançaient N fils à la fois (journal/L53/corrections-b13.md)."""
from __future__ import annotations

import subprocess
import threading
import time

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("ONTOFORGE_DATA", str(tmp_path))
    monkeypatch.setenv("ONTOFORGE_LLM_PROVIDER", "mock")
    from ontoforge.main import app
    return TestClient(app, raise_server_exceptions=False)


class _Gauge:
    """Faux `childproc.run_limited` : compte les fils simultanés (sans lancer de processus) et les retient jusqu'à `release`."""

    def __init__(self) -> None:
        self.now, self.peak, self.calls = 0, 0, 0
        self.release = threading.Event()
        self._l = threading.Lock()

    def __call__(self, worker, payload, **kw):
        with self._l:
            self.now += 1
            self.calls += 1
            self.peak = max(self.peak, self.now)
        self.release.wait(90)  # délai large : une machine chargée ne doit pas libérer les places d'elle-même
        with self._l:
            self.now -= 1
        return subprocess.CompletedProcess([], 0, b'{"form": "ASK", "boolean": true}', b"")


def _projects(client, n):
    ids = []
    for i in range(n):
        r = client.post("/api/projects", json={"name": f"p{i}", "sample": "automaint"})
        assert r.status_code in (200, 201), r.text
        ids.append(r.json()["id"])
    return ids


def _ask(client, pid):
    return client.post(f"/api/projects/{pid}/query/run", json={"sparql": "ASK {}", "endpoint": {"kind": "local"}})


def _start_all(client, ids):
    """Une requête par projet, toutes lancées en même temps (l'analyseur SPARQL est sous verrou depuis DF-B17)."""
    out = [None] * len(ids)
    barrier = threading.Barrier(len(ids))

    def go(i):
        barrier.wait()
        out[i] = _ask(client, ids[i])

    threads = [threading.Thread(target=go, args=(i,)) for i in range(len(ids))]
    [t.start() for t in threads]
    return out, threads


def test_b13_query_children_are_capped_and_overflow_gives_503(client, monkeypatch):
    from ontoforge import childproc
    g = _Gauge()
    monkeypatch.setattr(childproc, "run_limited", g)
    ids = _projects(client, 5)  # places par défaut (2), sans réglage de test : c'est la reproduction de DF-B13
    from ontoforge.queries import endpoint
    endpoint.query_form("ASK {}")  # chauffe : premier import et grammaire de l'analyseur SPARQL
    for pid in ids:  # chauffe : création à froid de chacun des cinq magasins (sans fils : resynchronisation seule)
        assert client.post(f"/api/projects/{pid}/store/load").status_code == 200
    out, threads = _start_all(client, ids)
    deadline = time.time() + 90
    while time.time() < deadline and sum(1 for o in out if o is not None) < 3:
        time.sleep(0.02)  # les trois refus arrivent, les deux fils sont retenus
    done = sum(1 for o in out if o is not None)
    peak_while_held = g.peak
    g.release.set()
    [t.join(90) for t in threads]
    assert done == 3, f"{done} réponses reçues avant la libération (attendu : les 3 refus), pic {peak_while_held}"
    assert not any(t.is_alive() for t in threads) and g.now == 0, "des requêtes ou des faux fils sont restés en vie"
    codes = sorted(r.status_code for r in out)
    assert peak_while_held <= 2, f"{peak_while_held} fils simultanés pour 5 projets"  # avant : 5
    assert codes == [200, 200, 503, 503, 503], codes
    busy = next(r for r in out if r.status_code == 503)
    assert busy.headers["retry-after"] == "5" and busy.json()["detail"]


def test_b13_slots_are_released_after_use_and_after_error(client, monkeypatch):
    from ontoforge import childproc
    from ontoforge.localstore import store as st

    def boom(*a, **k):
        raise subprocess.TimeoutExpired("x", 1)
    monkeypatch.setattr(st, "_SLOTS", threading.BoundedSemaphore(1))
    monkeypatch.setattr(childproc, "run_limited", boom)
    pid = _projects(client, 1)[0]
    for _ in range(3):  # trois délais d'affilée : la place revient à chaque fois
        r = client.post(f"/api/projects/{pid}/query/run", json={"sparql": "ASK {}", "endpoint": {"kind": "local"}})
        assert r.status_code == 504, r.text
    assert st._SLOTS.acquire(blocking=False)


def test_b13_inference_shares_the_same_slots(client, monkeypatch):
    from ontoforge import childproc
    from ontoforge.localstore import store as st
    monkeypatch.setattr(st, "_SLOTS", threading.BoundedSemaphore(1))
    st._SLOTS.acquire()  # une requête tient la seule place
    called = []
    monkeypatch.setattr(childproc, "run_limited", lambda *a, **k: called.append(1))
    pid = _projects(client, 1)[0]
    ttl = b"<http://example.org/t1> a <https://w3id.org/ontoforge/automaint#Technician> .\n"
    r = client.post(f"/api/projects/{pid}/store/load", files={"file": ("t.ttl", ttl)}, data={"inference": "rdfs"})
    assert r.status_code == 503 and r.headers["retry-after"] == "5", r.text
    assert not called  # aucun fils lancé
    # tout ou rien : le fichier refusé n'est pas resté dans le magasin
    s = client.get(f"/api/projects/{pid}/store/stats").json()
    assert not any(g["name"] == "t.ttl" for g in s["graphs"])


def test_b13_slot_count_is_configurable(monkeypatch):
    from ontoforge.localstore import store as st
    assert st._slot_count() == 2  # défaut
    monkeypatch.setenv("ONTOFORGE_LOCAL_STORE_SLOTS", "5")
    assert st._slot_count() == 5
    monkeypatch.setenv("ONTOFORGE_LOCAL_STORE_SLOTS", "zéro")
    assert st._slot_count() == 2
    monkeypatch.setenv("ONTOFORGE_LOCAL_STORE_SLOTS", "0")
    assert st._slot_count() == 1
    monkeypatch.setenv("ONTOFORGE_LOCAL_STORE_SLOTS", "999")
    assert st._slot_count() == 32


def _cloudrun_env():
    from pathlib import Path
    import yaml
    return yaml.safe_load((Path(__file__).resolve().parents[2] / "deploy" / "cloudrun" / "env.yaml").read_text(encoding="utf-8"))


def cloudrun_worst_case(env) -> dict:
    """Somme au pire de `deploy/cloudrun/env.yaml` (Mo) : serveur + places × plafonds + chargement dans le serveur + disque en mémoire."""
    n = lambda k: int(env[k])  # noqa: E731 - toutes ces variables doivent être posées explicitement pour Cloud Run
    parts = {
        "serveur": 175,  # mesuré au repos : 121 à 146 Mo (application chargée, un projet), retenu 175
        "shacl": n("ONTOFORGE_SHACL_SLOTS") * n("ONTOFORGE_SHACL_MEMORY_MB"),
        "owlrl": n("ONTOFORGE_OWLRL_SLOTS") * n("ONTOFORGE_OWLRL_MEMORY_MB"),
        "hermit": n("ONTOFORGE_HERMIT_SLOTS") * (n("ONTOFORGE_HERMIT_MAX_MB") + 150),  # 150 Mo de JVM hors tas
        "triplestore_fils": n("ONTOFORGE_LOCAL_STORE_SLOTS") * n("ONTOFORGE_LOCAL_STORE_MEMORY_MB"),
        # chargement : (plafond de triplets + 20 000 d'un bloc d'analyse) × 1,7 Mo / 1 000 (mesuré), plus le fichier lu en mémoire
        "triplestore_chargement": n("ONTOFORGE_LOCAL_STORE_LOAD_SLOTS") * (
            -(-(n("ONTOFORGE_LOCAL_STORE_MAX_TRIPLES") + 20_000) * 17 // 10_000) + n("ONTOFORGE_LOCAL_STORE_MAX_UPLOAD_MB")),
        "triplestore_disque": n("ONTOFORGE_LOCAL_STORE_TOTAL_MB"),  # le disque de l'instance est en mémoire
        # un corps de requête reçu en entier avant la prise d'une place ; les envois simultanés au-delà du premier sont pris sur la marge
        "corps_de_requete": n("ONTOFORGE_MAX_BODY_MB"),
    }
    parts["total"] = sum(parts.values())
    return parts


def test_b13_cloudrun_env_sum_at_worst_fits_in_2_gib():
    """La somme au pire de `deploy/cloudrun/env.yaml` tient dans les 2 Gio du conteneur, disque en mémoire et chargements compris.
    Si un plafond ou un nombre de places change, ce test oblige à refaire le calcul (README Cloud Run, chapitres 16 et 17)."""
    env = _cloudrun_env()
    parts = cloudrun_worst_case(env)
    assert parts["total"] <= 2048, f"{parts['total']} Mo au pire pour 2048 Mo : {parts}"
    assert parts["total"] == 1933  # valeur du calcul documenté ; à mettre à jour avec la documentation
    assert int(env["ONTOFORGE_LOCAL_STORE_IDLE_MIN"]) > 0  # la purge des bases inactives est active sur Cloud Run


def test_b13_deploy_scripts_apply_env_yaml_and_the_2_gib_settings():
    """Les deux chemins de mise à jour (script PowerShell, déclencheur Cloud Build) appliquent env.yaml, 2 Gi, une instance et les mêmes secrets
    que l'étape 5 du README : sinon une modification d'env.yaml reste lettre morte (revue déploiement L53, B1)."""
    import re
    from pathlib import Path
    root = Path(__file__).resolve().parents[2] / "deploy" / "cloudrun"
    readme = (root / "README.md").read_text(encoding="utf-8")
    secrets = re.search(r'--set-secrets "([^"]+)"', readme).group(1)
    for name in ("deploy-demo.ps1", "cloudbuild-trigger.yaml"):
        text = (root / name).read_text(encoding="utf-8")
        code = "\n".join(ln for ln in text.splitlines() if not ln.lstrip().startswith("#"))
        for needed in ("--env-vars-file", "deploy/cloudrun/env.yaml", "--max-instances", "--memory", "2Gi", "--set-secrets", secrets):
            assert needed in code, (name, needed)
        assert re.search(r"--max-instances[ =]1\b", code), name


def test_b13_disk_cap_refuses_a_load_that_does_not_fit(client, monkeypatch, tmp_path):
    monkeypatch.setenv("ONTOFORGE_LOCAL_STORE_DIR", str(tmp_path / "ts"))
    monkeypatch.setenv("ONTOFORGE_LOCAL_STORE_TOTAL_MB", "8")
    pid = _projects(client, 1)[0]
    ttl = "".join(f"<http://e/s{i}> <http://e/p> \"valeur {i}\" .\n" for i in range(20_000)).encode()  # environ 10 Mo estimés
    r = client.post(f"/api/projects/{pid}/store/load", files={"file": ("big.nt", ttl)})
    assert r.status_code == 413 and "Espace du triplestore local plein" in r.json()["detail"], r.text
    small = client.post(f"/api/projects/{pid}/store/load", files={"file": ("s.nt", b'<http://e/a> <http://e/p> "x" .\n')})
    assert small.status_code == 200, small.text  # un petit fichier passe encore
    s = client.get(f"/api/projects/{pid}/store/stats").json()
    assert s["disk"]["total_mb"] == 8 and not any(g["name"] == "big.nt" for g in s["graphs"])


def test_b13_inferred_graph_counts_in_the_disk_cap_all_or_nothing(client, monkeypatch, tmp_path):
    """it2 (devback, non-bloquant 2) : le graphe inféré entre dans le plafond total. Une inférence qui ne tient pas est refusée en 413 AVANT le
    remplacement : l'ancien graphe inféré est gardé, et un chargement qui la demandait restaure son état (le fichier n'est pas ajouté)."""
    import subprocess
    from ontoforge import childproc
    monkeypatch.setenv("ONTOFORGE_LOCAL_STORE_DIR", str(tmp_path / "ts"))
    monkeypatch.setenv("ONTOFORGE_LOCAL_STORE_TOTAL_MB", "64")
    out = {"nt": b'<http://e/i> <http://e/q> "petit" .\n'}
    monkeypatch.setattr(childproc, "run_limited", lambda *a, **k: subprocess.CompletedProcess([], 0, out["nt"], b""))
    pid = _projects(client, 1)[0]
    ok = client.post(f"/api/projects/{pid}/store/load", files={"file": ("a.nt", b'<http://e/a> <http://e/p> "x" .\n')}, data={"inference": "owlrl"})
    assert ok.status_code == 200 and any(g["kind"] == "inferred" and g["triples"] == 1 for g in ok.json()["graphs"]), ok.text
    out["nt"] = "".join(f'<http://e/i{i}> <http://e/q> "v" .\n' for i in range(150_000)).encode()  # environ 70 Mo estimés
    r = client.post(f"/api/projects/{pid}/store/load", files={"file": ("b.nt", b'<http://e/b> <http://e/p> "y" .\n')}, data={"inference": "owlrl"})
    assert r.status_code == 413 and "Espace du triplestore local plein" in r.json()["detail"], r.text
    s = client.get(f"/api/projects/{pid}/store/stats").json()
    assert not any(g["name"] == "b.nt" for g in s["graphs"]), s["graphs"]  # tout ou rien : le fichier n'est pas resté
    assert [g["triples"] for g in s["graphs"] if g["kind"] == "inferred"] == [1]  # l'ancien graphe inféré est gardé
    r = client.post(f"/api/projects/{pid}/store/load", data={"inference": "owlrl"})  # refresh : même contrôle
    assert r.status_code == 413, r.text


def test_b13_purge_rereads_the_clock_under_the_lock(client, monkeypatch, tmp_path):
    """it2 (devback, non-bloquant 1) : un usage qui commence entre la lecture de l'horloge et la prise du verrou sauve la base."""
    from ontoforge.localstore import store as st
    monkeypatch.setenv("ONTOFORGE_LOCAL_STORE_DIR", str(tmp_path / "ts"))
    monkeypatch.setenv("ONTOFORGE_LOCAL_STORE_IDLE_MIN", "10")
    a, b = _projects(client, 2)
    ttl = b'<http://e/a> <http://e/p> "x" .\n'
    for pid in (a, b):
        assert client.post(f"/api/projects/{pid}/store/load", files={"file": ("f.nt", ttl)}).status_code == 200
    st._LAST_USE[a] -= 11 * 60
    real = st.lock

    def lock_then_use(pid):  # l'usage de `a` arrive juste avant que la purge prenne le verrou
        if pid == a:
            st.touch(a)
        return real(pid)
    monkeypatch.setattr(st, "lock", lock_then_use)
    assert st.purge_idle(skip=b) == [] and st.exists(a)


def test_b13_idle_databases_are_purged_with_a_clear_message(client, monkeypatch, tmp_path):
    from ontoforge.localstore import store as st
    monkeypatch.setenv("ONTOFORGE_LOCAL_STORE_DIR", str(tmp_path / "ts"))
    monkeypatch.setenv("ONTOFORGE_LOCAL_STORE_IDLE_MIN", "10")
    a, b = _projects(client, 2)
    ttl = b'<http://e/a> <http://e/p> "x" .\n'
    assert client.post(f"/api/projects/{a}/store/load", files={"file": ("a.nt", ttl)}).status_code == 200
    assert client.post(f"/api/projects/{b}/store/load", files={"file": ("b.nt", ttl)}).status_code == 200
    assert st.exists(a) and st.exists(b)
    st._LAST_USE[a] -= 11 * 60  # a est inactif depuis 11 minutes ; b vient d'être utilisé
    client.post(f"/api/projects/{b}/store/load", files={"file": ("b2.nt", ttl)})  # tout usage déclenche la purge des autres
    assert not st.exists(a) and st.exists(b)
    s = client.get(f"/api/projects/{a}/store/stats").json()
    assert s["exists"] is False and "supprimé(s) après 10 min" in s["purged"]["message"] and s["purged"]["files"] == ["a.nt"]
    client.put("/api/settings", json={"language": {"ui": "en", "labels": "en", "assistant": "en"}})
    assert "deleted after 10 min" in client.get(f"/api/projects/{a}/store/stats").json()["purged"]["message"]
    client.put("/api/settings", json={"language": {"ui": "fr", "labels": "fr", "assistant": "fr"}})
    # l'ontologie et les individus reviennent seuls ; l'avis disparaît dès qu'un fichier est rechargé
    assert client.post(f"/api/projects/{a}/store/load", files={"file": ("a.nt", ttl)}).status_code == 200
    assert "purged" not in client.get(f"/api/projects/{a}/store/stats").json()


def test_b13_purge_never_deletes_a_database_in_use(client, monkeypatch, tmp_path):
    """Sous un verrou de lecture (requête en cours), la purge laisse la base : le verrou d'écriture est pris sans attendre."""
    from ontoforge.localstore import store as st
    monkeypatch.setenv("ONTOFORGE_LOCAL_STORE_DIR", str(tmp_path / "ts"))
    monkeypatch.setenv("ONTOFORGE_LOCAL_STORE_IDLE_MIN", "1")
    a = _projects(client, 1)[0]
    client.post(f"/api/projects/{a}/store/load", files={"file": ("a.nt", b'<http://e/a> <http://e/p> "x" .\n')})
    st._LAST_USE[a] -= 3600
    with st.lock(a).read():
        assert st.purge_idle() == [] and st.exists(a)
    assert st.purge_idle() == [a] and not st.exists(a)


def test_b13_purge_and_loads_run_concurrently_without_error(client, monkeypatch, tmp_path):
    """Des chargements, des lectures et des purges en même temps sur plusieurs projets : aucune erreur 500, aucune base à moitié supprimée."""
    from ontoforge.localstore import store as st
    monkeypatch.setenv("ONTOFORGE_LOCAL_STORE_DIR", str(tmp_path / "ts"))
    monkeypatch.setenv("ONTOFORGE_LOCAL_STORE_IDLE_MIN", "1")
    monkeypatch.setattr(st, "_LOAD_SLOTS", threading.BoundedSemaphore(8))
    ids = _projects(client, 4)
    bad, stop = [], threading.Event()

    def worker(pid, k):
        for i in range(6):
            st._LAST_USE[pid] = 0.0  # chaque tour, la base paraît inactive : la purge des autres threads la vise
            r = client.post(f"/api/projects/{pid}/store/load", files={"file": (f"f{k}.nt", f'<http://e/s{i}> <http://e/p> "v{i}" .\n'.encode())})
            if r.status_code != 200:
                bad.append((pid, r.status_code, r.text[:100]))
            r = client.get(f"/api/projects/{pid}/store/stats")
            if r.status_code != 200:
                bad.append(("stats", r.status_code, r.text[:100]))

    ts = [threading.Thread(target=worker, args=(p, k)) for k, p in enumerate(ids)]
    [t.start() for t in ts]
    [t.join(120) for t in ts]
    assert not bad, bad[:3]
    assert not any(t.is_alive() for t in ts)
    # État final (it2) : chaque base est soit purgée en entier (avec son avis), soit intacte avec son DERNIER fichier (un seul triplet, à son nom) ;
    # jamais de dossier sans meta.json ni de base à moitié supprimée.
    for k, pid in enumerate(ids):
        s = client.get(f"/api/projects/{pid}/store/stats").json()
        if s["exists"]:
            files = [g for g in s["graphs"] if g["kind"] == "data"]
            assert [(g["name"], g["triples"]) for g in files] == [(f"f{k}.nt", 1)], (pid, s["graphs"])
        else:
            assert pid in st._PURGED, pid
    for d in (tmp_path / "ts").iterdir():
        assert (st.root(d.name) / "meta.json").is_file(), d


def test_b13_load_slots_give_503_when_busy(client, monkeypatch):
    from ontoforge.localstore import store as st
    monkeypatch.setattr(st, "_LOAD_SLOTS", threading.BoundedSemaphore(1))
    pid = _projects(client, 1)[0]
    with st.load_slot():
        r = client.post(f"/api/projects/{pid}/store/load", files={"file": ("a.nt", b'<http://e/a> <http://e/p> "x" .\n')})
    assert r.status_code == 503 and r.headers["retry-after"] == "5", r.text
    assert client.post(f"/api/projects/{pid}/store/load", files={"file": ("a.nt", b'<http://e/a> <http://e/p> "x" .\n')}).status_code == 200
