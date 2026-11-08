"""Écriture de fichiers compatible avec un montage Cloud Storage FUSE (gcsfuse) comme avec un disque local (L27).

Ce que gcsfuse permet et ne permet pas (À VÉRIFIER dans la doc Google avant de changer quoi que ce soit) :
- créer, lire, écraser, renommer un fichier : oui. Le renommage est une copie suivie d'une suppression, il n'est pas atomique
  côté bucket ; en revanche un objet n'apparaît qu'à la fermeture du fichier, donc une écriture directe ne laisse jamais de
  fichier à moitié écrit visible ;
- chmod : accepté sans effet, ou refusé selon la version ; fsync : peut échouer ; verrous (flock, fcntl) : non pris en charge ;
  liens symboliques et liens durs : non.
OntoForge n'utilise donc ni verrou fichier ni lien : la sérialisation des écritures repose sur des verrous de threads, ce qui
suffit avec une seule instance (max-instances=1). Ce module sert d'unique point d'écriture : fichier temporaire voisin puis
``os.replace`` ; si le renommage échoue (système de fichiers qui le refuse), repli sur une écriture directe.
"""
from __future__ import annotations

import logging
import os
import tempfile
from pathlib import Path

log = logging.getLogger(__name__)


def try_chmod(path: str | os.PathLike, mode: int) -> None:
    """chmod best effort : un système de fichiers qui n'en veut pas (FUSE) ne doit pas faire échouer l'écriture."""
    try:
        os.chmod(path, mode)
    except OSError:
        pass


def atomic_write(path: Path | str, content: str | bytes, *, mode: int | None = None, prefix: str | None = None) -> None:
    """Écrit ``content`` dans ``path`` : fichier temporaire dans le même dossier, flush, fsync (best effort), puis ``os.replace``."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = content.encode("utf-8") if isinstance(content, str) else content
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=prefix or f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
            fh.flush()
            try:
                os.fsync(fh.fileno())
            except OSError:
                pass  # fsync refusé par certains montages FUSE : la fermeture du fichier suffit à publier l'objet
        if mode is not None:
            try_chmod(tmp, mode)
        try:
            os.replace(tmp, path)
        except OSError as exc:
            log.warning("renommage refusé (%s) : écriture directe de %s", exc.__class__.__name__, path.name)
            _write_direct(path, data, mode)
            _unlink_quiet(tmp)
    except BaseException:
        _unlink_quiet(tmp)
        raise


def _write_direct(path: Path, data: bytes, mode: int | None) -> None:
    with open(path, "wb") as fh:
        fh.write(data)
        fh.flush()
        try:
            os.fsync(fh.fileno())
        except OSError:
            pass
    if mode is not None:
        try_chmod(path, mode)


def _unlink_quiet(p: str | os.PathLike) -> None:
    try:
        os.unlink(p)
    except OSError:
        pass
