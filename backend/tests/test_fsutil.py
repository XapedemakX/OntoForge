"""Écriture de fichiers compatible Cloud Storage FUSE (L27) : pas de verrou fichier ni de lien, repli si le renommage échoue."""
import errno
import os
import pathlib
import re

from ontoforge import fsutil

SRC = pathlib.Path(fsutil.__file__).parent


def test_no_file_locks_or_links_in_code():
    """gcsfuse ne gère ni flock/fcntl ni liens : le code d'OntoForge ne doit en utiliser aucun."""
    bad = re.compile(r"\b(fcntl|flock|lockf|os\.symlink|os\.link|\.symlink_to|\.hardlink_to|msvcrt\.locking)\b")
    hits = []
    for p in SRC.rglob("*.py"):
        if p.name == "fsutil.py":
            continue  # sa docstring explique pourquoi ces appels sont interdits
        for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            if bad.search(line) and not line.lstrip().startswith("#"):
                hits.append(f"{p.relative_to(SRC)}:{i}")
    assert not hits, hits


def test_atomic_write_replaces_and_leaves_no_temp(tmp_path):
    p = tmp_path / "a" / "f.json"
    fsutil.atomic_write(p, "un")
    fsutil.atomic_write(p, "deux é")
    assert p.read_text(encoding="utf-8") == "deux é"
    assert [x.name for x in p.parent.iterdir()] == ["f.json"]


def test_fuse_like_errors_are_tolerated(tmp_path, monkeypatch):
    """chmod et fsync refusés (ENOTSUP) : l'écriture réussit quand même."""
    def refuse(*a, **k):
        raise OSError(errno.ENOTSUP, "not supported")
    monkeypatch.setattr(os, "chmod", refuse)
    monkeypatch.setattr(os, "fsync", refuse)
    p = tmp_path / "s.json"
    fsutil.atomic_write(p, b"{}", mode=0o600)
    assert p.read_bytes() == b"{}"


def test_rename_refused_falls_back_to_direct_write(tmp_path, monkeypatch):
    def refuse(*a, **k):
        raise OSError(errno.EPERM, "rename not permitted")
    monkeypatch.setattr(os, "replace", refuse)
    p = tmp_path / "r.txt"
    p.write_text("ancien")
    fsutil.atomic_write(p, "nouveau")
    assert p.read_text() == "nouveau"
    assert [x.name for x in tmp_path.iterdir()] == ["r.txt"]


def test_project_and_settings_writes_use_fsutil(tmp_path, monkeypatch):
    monkeypatch.setenv("ONTOFORGE_DATA", str(tmp_path))
    monkeypatch.setattr(os, "chmod", lambda *a, **k: (_ for _ in ()).throw(OSError(errno.ENOTSUP, "x")))
    from ontoforge.projects import store
    p = store.save(store.create("fuse-test"))
    assert store.get(p.id).name == "fuse-test"
    from ontoforge.settings import store as sstore
    s = sstore.load()
    sstore.save(s)
    assert (tmp_path / "settings.json").is_file()


def test_local_store_dir_outside_project(tmp_path, monkeypatch):
    monkeypatch.setenv("ONTOFORGE_DATA", str(tmp_path / "data"))
    monkeypatch.setenv("ONTOFORGE_LOCAL_STORE_DIR", str(tmp_path / "tmp-ts"))
    from ontoforge.localstore import store as ls
    from ontoforge.projects import store
    p = store.save(store.create("ts-ephemere"))
    assert ls.root(p.id) == tmp_path / "tmp-ts" / p.id and ls.ephemeral()
    ls.ensure(p.id, p)
    assert ls.exists(p.id) and not (store.project_dir(p.id) / "triplestore").exists()
    assert ls.stats(p.id, p)["ephemeral"] is True
    store.delete(p.id)
    assert not (tmp_path / "tmp-ts" / p.id).exists()
