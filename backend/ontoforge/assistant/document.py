"""Lecture d'un document (L25) : .txt, .md et .pdf à texte natif → pages de texte, puis découpage en morceaux.

Aucun appel réseau ici. Les PDF sont lus par pypdf (licence BSD-3, version épinglée dans pyproject.toml) ; un PDF scanné
(sans couche texte) est signalé comme non pris en charge : il n'y a pas de reconnaissance de caractères dans ce lot.
Limites configurables par variables d'environnement :

- ``ONTOFORGE_DOC_MAX_MB``     taille maximale du fichier (défaut 10) ;
- ``ONTOFORGE_DOC_MAX_PAGES``  nombre maximal de pages d'un PDF (défaut 60) ;
- ``ONTOFORGE_DOC_MAX_CHARS``  nombre maximal de caractères de texte extrait (défaut 400 000) ;
- ``ONTOFORGE_DOC_CHUNK_CHARS`` taille cible d'un morceau envoyé au LLM (défaut 8 000).
"""
from __future__ import annotations

import io
import os
import re
from dataclasses import dataclass, field
from typing import Any, Optional

EXTENSIONS = (".txt", ".md", ".markdown", ".pdf")
EXCERPT_MAX = 300


class DocumentError(Exception):
    """Document inutilisable. ``status`` est le code HTTP à renvoyer ; ``fr`` et ``en`` sont les deux messages affichables."""

    def __init__(self, status: int, fr: str, en: str) -> None:
        super().__init__(fr)
        self.status, self.fr, self.en = status, fr, en

    def message(self, lang: str = "fr") -> str:
        return self.en if lang == "en" else self.fr


def _env_int(name: str, default: int) -> int:
    try:
        v = int(os.environ.get(name, ""))
        return v if v > 0 else default
    except ValueError:
        return default


def limits() -> dict[str, int]:
    return {"max_bytes": _env_int("ONTOFORGE_DOC_MAX_MB", 10) * 1024 * 1024, "max_pages": _env_int("ONTOFORGE_DOC_MAX_PAGES", 60),
            "max_chars": _env_int("ONTOFORGE_DOC_MAX_CHARS", 400_000), "chunk_chars": _env_int("ONTOFORGE_DOC_CHUNK_CHARS", 8_000)}


@dataclass
class Page:
    page: int
    text: str


@dataclass
class Document:
    name: str
    pages: list[Page] = field(default_factory=list)

    @property
    def chars(self) -> int:
        return sum(len(p.text) for p in self.pages)

    def to_json(self) -> dict[str, Any]:
        return {"name": self.name, "pages": [{"page": p.page, "text": p.text} for p in self.pages]}

    @staticmethod
    def from_json(d: dict[str, Any]) -> "Document":
        return Document(str(d.get("name") or "document"), [Page(int(p["page"]), str(p["text"])) for p in d.get("pages", [])])


def _decode(data: bytes) -> str:
    for enc in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def clean(text: str) -> str:
    """Espaces normalisés, césures de fin de ligne recollées (« maintenan-\\nce »), lignes vides multiples réduites."""
    t = text.replace("\r\n", "\n").replace("\r", "\n").replace("\x00", "")
    t = re.sub(r"(\w)-\n(\w)", r"\1\2", t)
    t = re.sub(r"[ \t ]+", " ", t)
    t = re.sub(r" ?\n ?", "\n", t)
    return re.sub(r"\n{3,}", "\n\n", t).strip()


def extract(name: str, data: bytes) -> Document:
    """Octets d'un fichier → Document (pages numérotées à partir de 1). Lève DocumentError."""
    lim = limits()
    ext = os.path.splitext(name.lower())[1]
    if ext not in EXTENSIONS:
        raise DocumentError(415, f"Format « {ext or name} » non pris en charge : .txt, .md ou .pdf attendus.",
                            f"Unsupported format “{ext or name}”: .txt, .md or .pdf expected.")
    if len(data) > lim["max_bytes"]:
        mb = lim["max_bytes"] // 1024 // 1024
        raise DocumentError(413, f"Fichier trop volumineux (maximum {mb} Mo).", f"File too large (maximum {mb} MB).")
    if not data.strip():
        raise DocumentError(422, "Le fichier est vide.", "The file is empty.")
    doc = Document(os.path.basename(name))
    if ext == ".pdf":
        doc.pages = _pdf_pages(data, lim["max_pages"])
    else:
        text = clean(_decode(data))
        # un texte long est découpé en « pages » virtuelles de ~3 000 caractères pour que la source reste localisable
        doc.pages = [Page(i + 1, t) for i, t in enumerate(_virtual_pages(text))]
    if not doc.pages or not any(p.text.strip() for p in doc.pages):
        raise DocumentError(422, "Aucun texte exploitable dans ce document.", "No usable text in this document.")
    if doc.chars > lim["max_chars"]:
        raise DocumentError(413, f"Texte trop long ({doc.chars} caractères ; maximum {lim['max_chars']}).",
                            f"Text too long ({doc.chars} characters; maximum {lim['max_chars']}).")
    return doc


def _virtual_pages(text: str, size: int = 3000) -> list[str]:
    if len(text) <= size:
        return [text]
    out: list[str] = []
    cur = ""
    for para in re.split(r"\n{2,}", text):
        if cur and len(cur) + len(para) + 2 > size:
            out.append(cur)
            cur = ""
        cur = (cur + "\n\n" + para) if cur else para
    if cur:
        out.append(cur)
    return out


def _pdf_pages(data: bytes, max_pages: int) -> list[Page]:
    try:
        from pypdf import PdfReader
        from pypdf.errors import PyPdfError
    except ImportError:  # pragma: no cover — dépendance déclarée dans pyproject.toml
        raise DocumentError(501, "La lecture des PDF nécessite la bibliothèque pypdf (non installée).",
                            "Reading PDFs requires the pypdf library (not installed).") from None
    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            try:
                ok = reader.decrypt("")
            except Exception:  # noqa: BLE001 — pypdf lève selon l'algorithme de chiffrement
                ok = 0
            if not ok:
                raise DocumentError(422, "PDF protégé par mot de passe : non pris en charge.", "Password-protected PDF: not supported.")
        n = len(reader.pages)
        if n > max_pages:
            raise DocumentError(413, f"PDF de {n} pages (maximum {max_pages}).", f"PDF with {n} pages (maximum {max_pages}).")
        pages = [Page(i + 1, clean(reader.pages[i].extract_text() or "")) for i in range(n)]
    except DocumentError:
        raise
    except (PyPdfError, ValueError, KeyError, TypeError, OSError, RecursionError) as exc:
        raise DocumentError(422, f"PDF illisible ({type(exc).__name__}).", f"Unreadable PDF ({type(exc).__name__}).") from None
    # PDF scanné : des pages sans (ou presque sans) couche texte. Pas d'OCR dans ce lot.
    chars = sum(len(p.text) for p in pages)
    if chars < 40 * max(1, len(pages)) and chars < 200:
        raise DocumentError(422, "Ce PDF semble scanné (aucune couche texte) : la reconnaissance de caractères n'est pas prise en charge. "
                            "Fournissez un PDF à texte natif, ou un fichier .txt / .md.",
                            "This PDF looks scanned (no text layer): OCR is not supported. Provide a native-text PDF, or a .txt / .md file.")
    return pages


# ----------------------------------------------------------------------------- découpage
@dataclass
class Chunk:
    index: int
    segments: list[tuple[int, str]]  # (page, texte)

    @property
    def text(self) -> str:
        """Texte envoyé au LLM : chaque paragraphe est précédé de son numéro de page, « [[p 2]] »."""
        return "\n\n".join(f"[[p {p}]] {t}" for p, t in self.segments)

    @property
    def chars(self) -> int:
        return len(self.text)

    @property
    def pages(self) -> list[int]:
        return sorted({p for p, _ in self.segments})


def split_paragraphs(text: str, limit: int) -> list[str]:
    """Paragraphes d'une page ; un paragraphe plus long que ``limit`` est coupé aux fins de phrases."""
    out: list[str] = []
    for para in re.split(r"\n{2,}", text):
        para = para.strip()
        if not para:
            continue
        while len(para) > limit:
            cut = max(para.rfind(". ", 0, limit), para.rfind("\n", 0, limit), para.rfind("; ", 0, limit))
            cut = cut + 1 if cut > limit // 3 else limit
            out.append(para[:cut].strip())
            para = para[cut:].strip()
        if para:
            out.append(para)
    return out


def chunk(doc: Document, size: Optional[int] = None) -> list[Chunk]:
    """Découpe en morceaux d'environ ``size`` caractères, sans jamais couper un paragraphe, avec recouvrement nul."""
    size = size or limits()["chunk_chars"]
    chunks: list[Chunk] = []
    cur: list[tuple[int, str]] = []
    used = 0
    for pg in doc.pages:
        for para in split_paragraphs(pg.text, size - 20):
            add = len(para) + 12
            if cur and used + add > size:
                chunks.append(Chunk(len(chunks), cur))
                cur, used = [], 0
            cur.append((pg.page, para))
            used += add
    if cur:
        chunks.append(Chunk(len(chunks), cur))
    return chunks


def digest(doc: Document, size: Optional[int] = None) -> str:
    """Début du document, plus les titres, pour la génération des questions de compétence (un seul appel)."""
    size = size or limits()["chunk_chars"]
    head = "\n\n".join(f"[[p {p.page}]] {p.text}" for p in doc.pages)
    if len(head) <= size:
        return head
    titles = [ln.strip() for p in doc.pages for ln in p.text.splitlines()
              if re.match(r"^(#{1,4}\s+|\d+(\.\d+)*[.)]\s+[A-ZÀ-Ý])", ln.strip()) and len(ln.strip()) < 100]
    top = head[: size * 2 // 3]
    return top + "\n\n[...]\n\nTITRES\n" + "\n".join(titles)[: size // 3]


# ----------------------------------------------------------------------------- extraits
def squash(s: str) -> str:
    """Forme comparable : minuscules, espaces et guillemets/tirets typographiques normalisés."""
    s = s.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"').replace("«", '"').replace("»", '"')
    s = s.replace("–", "-").replace("—", "-").replace("…", "...").replace("­", "")
    return re.sub(r"\s+", " ", s).strip().lower()


def snap_excerpt(text: str, start: int, end: int) -> str:
    """Extrait ≤ 300 caractères de ``text`` autour de [start, end[ : la phrase qui le contient, sinon une fenêtre centrée."""
    a = max(text.rfind(". ", 0, start), text.rfind("\n", 0, start), text.rfind("! ", 0, start), text.rfind("? ", 0, start))
    a = 0 if a < 0 else a + 1
    b_candidates = [i for i in (text.find(". ", end), text.find("\n", end), text.find("! ", end), text.find("? ", end)) if i >= 0]
    b = min(b_candidates) + 1 if b_candidates else len(text)
    s = text[a:b].strip()
    if len(s) <= EXCERPT_MAX:
        return s
    mid = (start + end) // 2
    lo = max(0, mid - (EXCERPT_MAX - 2) // 2)
    hi = min(len(text), lo + EXCERPT_MAX - 2)
    lo = max(0, hi - (EXCERPT_MAX - 2))
    piece = text[lo:hi].strip()
    return ("…" if lo > 0 else "") + piece + ("…" if hi < len(text) else "")


def locate(doc: Document, excerpt: str, page_hint: Optional[int] = None) -> Optional[tuple[int, str]]:
    """Retrouve ``excerpt`` dans le document → (page réelle, extrait recadré ≤ 300) ; None si introuvable.

    La comparaison ignore la casse, les espaces et la typographie. La page annoncée par le LLM n'est qu'un indice :
    la page retenue est celle où le texte se trouve vraiment.
    """
    want = squash(excerpt).strip(" .…")
    if len(want) < 4:
        return None
    pages = sorted(doc.pages, key=lambda p: (p.page != page_hint, p.page))
    for pg in pages:
        # on cherche dans une copie « squashée » dont on garde la correspondance d'indices avec le texte d'origine
        flat, idx = [], []
        for i, ch in enumerate(pg.text):
            sq = squash(ch) if not ch.isspace() else " "
            if ch.isspace() and flat and flat[-1] == " ":
                continue
            for c in (sq or ""):
                flat.append(c)
                idx.append(i)
        hay = "".join(flat)
        k = hay.find(want)
        if k >= 0:
            s, e = idx[k], idx[min(k + len(want) - 1, len(idx) - 1)] + 1
            return pg.page, snap_excerpt(pg.text, s, e)
    return None
