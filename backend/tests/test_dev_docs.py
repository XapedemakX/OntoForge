"""L51 : cohérence du manuel du développeur (docs/dev/*.md, fr + en) avec le code.

Contrôles :
- tout chemin de fichier ou de dossier cité entre backquotes existe dans le dépôt ;
- tout symbole cité sous la forme `chemin::symbole` (ou `chemin::Classe.membre`) existe dans le fichier ;
- parité fr / en : mêmes ancres `{#id}`, mêmes titres (niveau et ancre, dans le même ordre) ;
- liens Markdown internes valides (fichier et fragment) ; un chapitre anglais ne renvoie qu'à des pages anglaises ;
- les 18 chapitres et le sommaire existent en fr et en (sauf ceux listés dans EXPECTED_MISSING) ;
- rien de sensible : aucun renvoi à un fichier de journal/securite (le dossier peut être nommé), aucun motif de secret.

Convention d'exemple (documentée dans docs/dev/README.md) : un chemin ou symbole précédé de `exemple:` n'est pas vérifié
(fichier à créer, nom hypothétique). Les motifs (`<n>`, `*`, `…`, `{x}`, espaces) ne sont pas vérifiés non plus.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
DEV = ROOT / "docs" / "dev"

# Numéros de chapitres encore absents (rédaction en cours). Vider cette liste à la clôture du lot : le test devient alors bloquant.
EXPECTED_MISSING: set[str] = set()

ROOT_DIRS = {"backend", "frontend", "docs", "tools", "deploy", "samples", "journal", "skills", "lots", "design", "ref"}
ROOT_FILES = {"docker-compose.yml", "CLAUDE.md", "README.md", "README.en.md", ".env.example", ".gitignore"}
ROOT_DOT_DIRS = {".github", ".claude"}

TEXT_CODE = {".py": "py", ".ts": "ts", ".tsx": "ts", ".mjs": "ts", ".js": "ts"}

FENCE = re.compile(r"^\s*(```|~~~)")
SPAN = re.compile(r"(?<!`)`([^`\n]+)`(?!`)")
HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*$")
ANCHOR = re.compile(r"\s*\{#([A-Za-z0-9_\-]+)\}\s*$")
LINK = re.compile(r"(?<!!)\[[^\]\n]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
SECRET = re.compile(r"sk-ant-[A-Za-z0-9_-]{20,}|AIza[0-9A-Za-z_-]{30,}|ghp_[A-Za-z0-9]{30,}|-----BEGIN [A-Z ]*(PRIVATE KEY|CERTIFICATE)")


def md_files() -> list[Path]:
    return sorted(DEV.glob("*.md")) if DEV.is_dir() else []


def prose(md: str) -> list[tuple[int, str]]:
    """Lignes hors blocs de code (numéro de ligne, texte)."""
    out, fence = [], False
    for i, line in enumerate(md.splitlines(), 1):
        if FENCE.match(line):
            fence = not fence
            continue
        if not fence:
            out.append((i, line))
    return out


def headings(md: str) -> list[tuple[int, str, str | None]]:
    """(niveau, texte sans ancre, ancre ou None) pour chaque titre hors blocs de code."""
    res = []
    for _, line in prose(md):
        m = HEADING.match(line)
        if not m:
            continue
        text, anchor = m.group(2), None
        a = ANCHOR.search(text)
        if a:
            anchor, text = a.group(1), text[: a.start()].strip()
        res.append((len(m.group(1)), text, anchor))
    return res


def slug(text: str) -> str:
    s = re.sub(r"[`*_]", "", text.lower())
    s = re.sub(r"[^\w\- ]", "", s, flags=re.UNICODE)
    return s.strip().replace(" ", "-")


def anchors_of(path: Path) -> set[str]:
    out = set()
    for _, text, a in headings(path.read_text(encoding="utf-8")):
        if a:
            out.add(a)
        out.add(slug(text))
        out.add(slug(text + (" {#" + a + "}" if a else "")))
    return out


def spans(path: Path) -> list[tuple[int, str]]:
    res = []
    for n, line in prose(path.read_text(encoding="utf-8")):
        for m in SPAN.finditer(line):
            res.append((n, m.group(1).strip()))
    return res


def as_citation(raw: str) -> tuple[str, str | None] | None:
    """(chemin, symbole) si le texte est une citation à vérifier, sinon None."""
    if raw.startswith("exemple:") or any(c in raw for c in " <>*…{}|$\\"):
        return None
    path, _, sym = raw.partition("::")
    first = path.split("/")[0]
    if "/" not in path and path not in ROOT_FILES:
        return None
    if first not in ROOT_DIRS | ROOT_DOT_DIRS and path not in ROOT_FILES:
        return None
    return path, (sym or None)


def has_symbol(file: Path, sym: str) -> bool:
    text = file.read_text(encoding="utf-8", errors="replace")
    kind = TEXT_CODE.get(file.suffix)
    if kind is None:  # JSON, YAML, Dockerfile, shell, CSS… : présence du mot ou de la clé
        return re.search(r"(?<![\w.-])" + re.escape(sym) + r"(?![\w-])", text) is not None
    container, _, member = sym.partition(".")
    pos = 0
    if member:
        m = _decl(container, kind).search(text)
        if not m:
            return False
        pos = m.start()
        name = member.split(".")[-1]
        return re.search(r"(?<![\w$])" + re.escape(name) + r"(?![\w$])", text[pos:]) is not None
    return _decl(sym, kind).search(text) is not None


def _decl(name: str, kind: str) -> re.Pattern:
    n = re.escape(name)
    if kind == "py":
        return re.compile(rf"^\s*(?:async\s+def|def|class)\s+{n}\b|^{n}\s*(?::[^=\n]+)?=(?!=)", re.M)
    return re.compile(
        rf"^\s*(?:export\s+)?(?:default\s+)?(?:declare\s+)?(?:async\s+)?(?:function\*?|class|const|let|var|interface|type|enum|abstract\s+class)\s+{n}\b"
        rf"|^\s*export\s*\{{[^}}]*\b{n}\b", re.M)


# ---------------------------------------------------------------------------------------------------------------------------

FILES = md_files()
IDS = [p.name for p in FILES]


def test_dev_docs_exist():
    assert DEV.is_dir() and FILES, "docs/dev/ est vide : le manuel du développeur doit au moins contenir README.md"


@pytest.mark.parametrize("path", FILES, ids=IDS)
def test_cited_paths_and_symbols_exist(path: Path):
    bad = []
    for n, raw in spans(path):
        cit = as_citation(raw)
        if cit is None:
            continue
        rel, sym = cit
        target = ROOT / rel.rstrip("/")
        if not target.exists():
            bad.append(f"{path.name}:{n} chemin inexistant : {rel}")
            continue
        if sym:
            if not target.is_file():
                bad.append(f"{path.name}:{n} `::` sur autre chose qu'un fichier : {raw}")
            elif not has_symbol(target, sym):
                bad.append(f"{path.name}:{n} symbole introuvable : {rel}::{sym}")
    assert not bad, "\n".join(bad)


@pytest.mark.parametrize("path", FILES, ids=IDS)
def test_headings_have_anchors_and_unique(path: Path):
    hs = headings(path.read_text(encoding="utf-8"))
    missing = [t for lvl, t, a in hs if lvl <= 2 and a is None]
    assert not missing, f"{path.name} : titres de niveau 1-2 sans ancre {{#id}} : {missing}"
    ids = [a for _, _, a in hs if a]
    dup = sorted({a for a in ids if ids.count(a) > 1})
    assert not dup, f"{path.name} : ancres en double : {dup}"


def _pairs() -> list[tuple[Path, Path]]:
    fr = [p for p in FILES if not p.name.endswith(".en.md")]
    return [(p, p.with_name(p.name[:-3] + ".en.md")) for p in fr]


@pytest.mark.parametrize("fr,en", _pairs(), ids=[p.name for p, _ in _pairs()])
def test_bilingual_parity(fr: Path, en: Path):
    assert en.exists(), f"{fr.name} n'a pas de jumeau {en.name}"
    hf, he = headings(fr.read_text(encoding="utf-8")), headings(en.read_text(encoding="utf-8"))
    assert [(lvl, a) for lvl, _, a in hf] == [(lvl, a) for lvl, _, a in he], (
        f"{fr.name} / {en.name} : titres ou ancres différents (niveau, ancre) :\n"
        f"  fr seulement : {sorted(set((l, a) for l, _, a in hf) - set((l, a) for l, _, a in he))}\n"
        f"  en seulement : {sorted(set((l, a) for l, _, a in he) - set((l, a) for l, _, a in hf))}")


@pytest.mark.parametrize("en", [p for p in FILES if p.name.endswith(".en.md")], ids=lambda p: p.name)
def test_english_has_french_twin(en: Path):
    assert en.with_name(en.name[: -len(".en.md")] + ".md").exists(), f"{en.name} n'a pas de version française"


@pytest.mark.parametrize("path", FILES, ids=IDS)
def test_internal_links(path: Path):
    bad = []
    english = path.name.endswith(".en.md")
    for n, line in prose(path.read_text(encoding="utf-8")):
        for m in LINK.finditer(line):
            href = m.group(1)
            if re.match(r"^[a-z][a-z0-9+.-]*:", href, re.I):  # http:, https:, mailto:
                continue
            file_part, _, frag = href.partition("#")
            target = (path.parent / file_part).resolve() if file_part else path
            chap = re.match(r"^(\d\d)-", target.name)
            if chap and chap.group(1) in EXPECTED_MISSING:
                continue  # chapitre annoncé, pas encore rédigé
            if not target.exists():
                bad.append(f"{path.name}:{n} lien cassé : {href}")
                continue
            if english and target.parent == DEV and target.suffix == ".md" and not target.name.endswith(".en.md") and target.name != "README.md":
                bad.append(f"{path.name}:{n} lien vers la page française : {href}")
            if frag and target.suffix == ".md" and frag not in anchors_of(target):
                bad.append(f"{path.name}:{n} fragment inconnu : {href}")
    assert not bad, "\n".join(bad)


def _chapters() -> dict[str, set[str]]:
    found: dict[str, set[str]] = {f"{i:02d}": set() for i in range(1, 19)}
    for p in FILES:
        m = re.match(r"^(\d\d)-.+?(\.en)?\.md$", p.name)
        if m and m.group(1) in found:
            found[m.group(1)].add("en" if m.group(2) else "fr")
    return found


def test_all_chapters_and_readme_present():
    problems = []
    names = {p.name for p in FILES}
    for r in ("README.md", "README.en.md"):
        if r not in names:
            problems.append(f"{r} manquant")
    for num, langs in _chapters().items():
        if num in EXPECTED_MISSING:
            continue
        for lang in ("fr", "en"):
            if lang not in langs:
                problems.append(f"chapitre {num} ({lang}) manquant")
    assert not problems, "\n".join(problems)


@pytest.mark.parametrize("readme", ["README.md", "README.en.md"])
def test_readme_lists_every_chapter(readme: str):
    path = DEV / readme
    if not path.exists():
        pytest.skip(f"{readme} absent")
    body = path.read_text(encoding="utf-8")
    suffix = ".en.md" if readme.endswith(".en.md") else ".md"
    missing = []
    for p in FILES:
        m = re.match(r"^(\d\d)-.+?(\.en)?\.md$", p.name)
        if not m or m.group(1) in EXPECTED_MISSING:
            continue
        if (suffix == ".en.md") == bool(m.group(2)) and p.name not in body:
            missing.append(p.name)
    assert not missing, f"{readme} ne renvoie pas à : {missing}"


@pytest.mark.parametrize("path", FILES, ids=IDS)
def test_nothing_sensitive(path: Path):
    text = path.read_text(encoding="utf-8")
    assert not re.search(r"journal/securite/[\w.-]+", text), f"{path.name} cite un fichier de journal/securite (jamais publié)"
    assert not SECRET.search(text), f"{path.name} : motif de secret détecté"


# ---- auto-contrôle du contrôleur lui-même ----

def test_checker_selftest():
    assert as_citation("exemple:frontend/src/Nouveau.tsx") is None
    assert as_citation("frontend/src/<n>.tsx") is None
    assert as_citation("api.ts") is None
    assert as_citation("backend/tests/test_dev_docs.py::has_symbol") == ("backend/tests/test_dev_docs.py", "has_symbol")
    assert has_symbol(ROOT / "frontend/src/api.ts", "ApiError")
    assert has_symbol(ROOT / "frontend/src/api.ts", "api.health")
    assert not has_symbol(ROOT / "frontend/src/api.ts", "nExistePas")
    assert has_symbol(ROOT / "backend/ontoforge/ratelimit.py", "RateLimit")
    assert has_symbol(ROOT / "backend/ontoforge/ratelimit.py", "WINDOW")
    assert not has_symbol(ROOT / "backend/ontoforge/ratelimit.py", "nExistePas")
