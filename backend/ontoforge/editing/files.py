"""Éditeur de fichiers (L22) : texte canonique des fichiers du projet, validation en direct, diff, application.

Fichiers éditables : ``onto.ttl`` (ontologie), ``shapes.ttl`` (SHACL), ``decisions.json`` (arbitrages).
Fichiers générés (lecture seule) : ``generated/<nom>`` pour la cible courante du projet.

Le texte servi est **canonique** : le graphe est ré-étiqueté de façon déterministe (``to_canonical_graph``) avant
sérialisation, de sorte que deux lectures successives donnent le même texte (sinon l'ordre des nœuds blancs, tiré au
hasard par rdflib, ferait varier l'etag et le diff). Conséquence assumée : les commentaires et la mise en forme du
texte saisi sont normalisés à l'application.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from typing import Any, Optional

import rdflib
from rdflib.compare import graph_diff, to_canonical_graph, to_isomorphic
from rdflib.namespace import RDF, SH
from rdflib.plugins.parsers.notation3 import BadSyntax

from ..core.onto_model import OntoModel
from ..core.project import Project
from ..core.shapes_model import ShapesModel

ONTO = "onto.ttl"
SHAPES = "shapes.ttl"
DECISIONS = "decisions.json"
EDITABLE = (ONTO, SHAPES, DECISIONS)
GENERATED_PREFIX = "generated/"
MAX_BYTES = 2_000_000


class FileNotFound(KeyError):
    pass


class ReadOnlyFile(Exception):
    pass


def _t(fr: str, en: str, lang: str) -> str:
    return en if lang == "en" else fr


# ---- langages ------------------------------------------------------------------------------------------------

def language_of(path: str) -> str:
    ext = path.rsplit(".", 1)[-1].lower() if "." in path else ""
    return {"ttl": "turtle", "trig": "trig", "rq": "sparql", "sparql": "sparql", "json": "json", "cs": "csharp",
            "cypher": "cypher", "cql": "cypher", "graphql": "graphql", "gql": "graphql", "md": "markdown",
            "mmd": "text"}.get(ext, "text")


# ---- texte canonique -----------------------------------------------------------------------------------------

def _slug(seg: str) -> str:
    s = re.sub(r"[^A-Za-z0-9_]", "", seg)
    return s if s and s[0].isalpha() else ""


def _fallback_prefixes(g: rdflib.Graph, taken: set[str], bound: set[str]) -> dict[str, str]:
    """Préfixe pour l'espace de noms dominant des entités s'il n'en a aucun (fichier source sans déclaration, RDF/XML…).

    Dérivé de l'IRI d'ontologie (dernier segment), sinon ``onto``. N'écrase jamais un préfixe déclaré.
    """
    counts: dict[str, int] = {}
    for s in set(g.subjects()):
        if isinstance(s, rdflib.URIRef):
            m = re.match(r"^(.*[#/])[^#/]*$", str(s))
            if m and m.group(1) not in bound:
                counts[m.group(1)] = counts.get(m.group(1), 0) + 1
    out: dict[str, str] = {}
    onto_iri = next((str(s) for s in g.subjects(RDF.type, rdflib.OWL.Ontology) if isinstance(s, rdflib.URIRef)), "")
    for ns, n in sorted(counts.items(), key=lambda kv: -kv[1])[:3]:
        if n < 3 and out:
            break
        base = _slug((onto_iri.rstrip("#/").rsplit("/", 1)[-1] if onto_iri and ns.startswith(onto_iri) else ns.rstrip("#/").rsplit("/", 1)[-1])) or "onto"
        cand, i = base, 2
        while cand in taken or cand in out:
            cand, i = f"{base}{i}", i + 1
        out[cand] = ns
    return out


def canonical_turtle(g: rdflib.Graph) -> str:
    cg = to_canonical_graph(g)
    out = rdflib.Graph(bind_namespaces="none")
    taken: set[str] = set()
    bound: set[str] = set()
    for p, n in g.namespaces():
        out.bind(p, n)
        taken.add(p)
        bound.add(str(n))
    for p, n in _fallback_prefixes(g, taken, bound).items():
        out.bind(p, rdflib.URIRef(n))
    for tr in cg:
        out.add(tr)
    return out.serialize(format="turtle")


def onto_graph(o: OntoModel) -> rdflib.Graph:
    from ..io.rdf_export import model_to_graph
    return model_to_graph(o)


def shapes_graph(s: ShapesModel) -> rdflib.Graph:
    from ..shacl.export_shapes import shapes_to_graph
    return shapes_to_graph(s)


def decisions_text(d: dict) -> str:
    return json.dumps(d, indent=2, ensure_ascii=False) + "\n"


def etag_of(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:16]


def canonical_text(p: Project, path: str) -> str:
    if path == ONTO:
        return canonical_turtle(onto_graph(p.onto))
    if path == SHAPES:
        return canonical_turtle(shapes_graph(p.shapes))
    if path == DECISIONS:
        return decisions_text(p.decisions)
    raise FileNotFound(path)


# ---- texte source conservé (Turtle) --------------------------------------------------------------------------
# On garde le texte saisi par l'utilisateur (commentaires, ordre, mise en forme) dans ``editor-sources.json`` et on le
# sert tant que le texte canonique du projet est celui qu'il avait au moment de l'application (même etag canonique :
# le canonique est déterministe, donc graphes isomorphes). Toute modification venue d'ailleurs (autre écran, annulation
# vers un autre état) change le canonique : on sert alors le canonique, avec une note.
SOURCES = "editor-sources.json"
SOURCE_PATHS = (ONTO, SHAPES)


def _sources_file(p: Project):
    from ..projects import store
    return store.project_dir(p.id) / SOURCES


def load_sources(p: Project) -> dict:
    try:
        data = json.loads(_sources_file(p).read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save_source(p: Project, path: str, text: str, canon_etag: str) -> None:
    from ..projects import store
    data = load_sources(p)
    data[path] = {"text": text, "canon_etag": canon_etag}
    store._atomic_write(_sources_file(p), json.dumps(data, ensure_ascii=False))


_COMMENT_RE = re.compile(r'"(?:[^"\\]|\\.)*"|\'(?:[^\'\\]|\\.)*\'|<[^<>\s]*>|(#.*$)')


def comment_lines(text: str) -> int:
    """Nombre de lignes portant un commentaire Turtle (``#`` hors chaîne et hors IRI), pleine ligne ou en fin de ligne."""
    n = 0
    for line in text.splitlines():
        if any(m.group(1) for m in _COMMENT_RE.finditer(line)):
            n += 1
    return n


def served(p: Project, path: str) -> tuple[str, Optional[dict]]:
    """Texte servi à la lecture + note éventuelle (``{"state": "canonical", "comment_lines": N}``)."""
    canon = canonical_text(p, path)
    if path not in SOURCE_PATHS:
        return canon, None
    ent = load_sources(p).get(path)
    if not ent:
        return canon, None
    if ent.get("canon_etag") == etag_of(canon):
        return ent["text"], {"state": "source", "comment_lines": comment_lines(ent["text"])}
    lost = comment_lines(ent["text"])
    return canon, {"state": "canonical", "comment_lines": lost}


def editable_text(p: Project, path: str) -> str:
    return served(p, path)[0]


def generated_files(p: Project) -> dict[str, str]:
    from ..api.analysis import generate_files
    try:
        files, _ = generate_files(p, p.target)
    except Exception:  # noqa: BLE001 — l'arbre des fichiers ne doit pas dépendre d'un module d'export absent
        return {}
    return {GENERATED_PREFIX + name: text for name, text in sorted(files.items())}


def read(p: Project, path: str) -> dict:
    """Contenu d'un fichier du projet (éditable ou généré)."""
    if path in EDITABLE:
        text, note = served(p, path)
        return {"path": path, "content": text, "etag": etag_of(text), "editable": True, "generated": False,
                "language": language_of(path), "version": p.updated_at, "source": note}
    if path.startswith(GENERATED_PREFIX):
        gen = generated_files(p)
        if path not in gen:
            raise FileNotFound(path)
        return {"path": path, "content": gen[path], "etag": etag_of(gen[path]), "editable": False, "generated": True,
                "language": language_of(path), "version": p.updated_at}
    raise FileNotFound(path)


def tree(p: Project) -> dict:
    files: list[dict] = []
    for path in EDITABLE:
        text = editable_text(p, path)
        files.append({"path": path, "name": path, "editable": True, "generated": False, "language": language_of(path),
                      "etag": etag_of(text), "size": len(text.encode("utf-8"))})
    for path, text in generated_files(p).items():
        files.append({"path": path, "name": path[len(GENERATED_PREFIX):], "editable": False, "generated": True,
                      "language": language_of(path), "etag": etag_of(text), "size": len(text.encode("utf-8"))})
    return {"version": p.updated_at, "target": p.target, "files": files}


# ---- diagnostics ---------------------------------------------------------------------------------------------

def diag(line: int, col: int, severity: str, message: str, code: str, **extra: Any) -> dict:
    return {"line": max(1, line), "col": max(1, col), "severity": severity, "message": message, "code": code, **extra}


_WHY = {
    "expected '.' or '}' or ']' at end of statement": ("point « . » attendu en fin de déclaration (un « ; » ou un « . » a-t-il été oublié ?)",
                                                       "expected '.' at the end of the statement (a missing ';' or '.'?)"),
    "Prefix": None,
}


def _why(why: str, lang: str) -> str:
    if why in _WHY and _WHY[why]:
        fr, en = _WHY[why]  # type: ignore[misc]
        return _t(fr, en, lang)
    m = re.match(r'Prefix "([^"]*)" not bound', why)
    if m:
        return _t(f"préfixe « {m.group(1)} » non déclaré (ajouter @prefix {m.group(1)} <…> .)",
                  f"prefix \"{m.group(1)}\" is not declared (add @prefix {m.group(1)} <…> .)", lang)
    return why


def _mask(line: str) -> str:
    """Remplace commentaires, chaînes et IRIs d'une ligne Turtle par des espaces (pour chercher un jeton de préfixe)."""
    return re.sub(r'"(?:[^"\\]|\\.)*"|\'(?:[^\'\\]|\\.)*\'|<[^<>\s]*>|#.*$', lambda m: " " * len(m.group(0)), line)


def find_prefix_use(text: str, prefix: str) -> Optional[tuple[int, int]]:
    """Première utilisation du préfixe ``prefix:`` (rdflib rapporte une position peu fiable pour cette erreur)."""
    pat = re.compile(r"(?<![\w\-:.])" + re.escape(prefix) + r":")
    for i, line in enumerate(text.splitlines()):
        if _decl_line(line):
            continue
        m = pat.search(_mask(line))
        if m:
            return i + 1, m.start() + 1
    return None


def _line_col(raw: bytes, offset: int) -> tuple[int, int]:
    """Ligne et colonne (1-based) ; ``offset`` est un indice de caractère dans le texte décodé (pas un octet)."""
    head = raw.decode("utf-8", errors="replace")[:max(0, offset)]
    line = head.count("\n") + 1
    return line, len(head) - (head.rfind("\n") + 1) + 1


# Base fictive : sans @base, rdflib résout une IRI relative contre le répertoire courant du serveur (file:///…),
# ce qui ferait entrer un chemin serveur dans l'ontologie. On la détecte et on la refuse (Turtle §6.3, RFC 3986 §5.1).
_NO_BASE = "http://no-base.ontoforge.invalid/"
_IRI_FORBIDDEN = re.compile(r'[\x00-\x20<>"{}|^`\\]')  # caractères exclus de IRIREF (Turtle §6.4)


def _find_text(text: str, needle: str) -> Optional[tuple[int, int]]:
    for i, line in enumerate(text.splitlines()):
        j = line.find(needle)
        if j >= 0:
            return i + 1, j + 1
    return None


def _iri_errors(g: rdflib.Graph, text: str, lang: str) -> list[dict]:
    out: list[dict] = []
    seen: set[str] = set()
    for t in g:
        for x in t:
            if not isinstance(x, rdflib.URIRef) or str(x) in seen:
                continue
            iri = str(x)
            if iri.startswith(_NO_BASE):
                seen.add(iri)
                rel = iri[len(_NO_BASE):]
                pos = _find_text(text, f"<{rel}>") or (1, 1)
                out.append(diag(*pos, "error", _t(f"IRI relative <{rel}> sans @base : écrire l'IRI complète ou déclarer @base <…> .",
                                                  f"Relative IRI <{rel}> without @base: write the full IRI or declare @base <…> .", lang),
                                "turtle-relative-iri"))
            elif _IRI_FORBIDDEN.search(iri):
                seen.add(iri)
                pos = _find_text(text, iri) or (1, 1)
                out.append(diag(*pos, "error", _t(f"IRI invalide <{iri}> : espace ou caractère interdit (Turtle §6.4).",
                                                  f"Invalid IRI <{iri}>: space or forbidden character (Turtle §6.4).", lang),
                                "turtle-bad-iri"))
    return out


def literal_diagnostics(g: rdflib.Graph, text: str, lang: str) -> list[dict]:
    """Littéraux mal typés (forme lexicale hors de l'espace lexical du datatype) : avertissement.

    RDF 1.1 Concepts §3.3 les admet, mais en OWL 2 DL un littéral mal typé rend l'ontologie incohérente.
    """
    out: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for o in g.objects():
        if isinstance(o, rdflib.Literal) and o.datatype is not None and getattr(o, "ill_typed", False):
            key = (str(o), str(o.datatype))
            if key in seen:
                continue
            seen.add(key)
            dt = _short(g, o.datatype)
            pos = _find_text(text, f'"{o}"^^') or _find_text(text, f'"{o}"') or (1, 1)
            out.append(diag(*pos, "warning", _t(f"Littéral mal typé \"{o}\"^^{dt} : forme lexicale invalide (incohérent en OWL 2 DL).",
                                                f"Ill-typed literal \"{o}\"^^{dt}: invalid lexical form (inconsistent in OWL 2 DL).", lang),
                            "ill-typed-literal"))
    return out


def syntax_diagnostics(text: str, lang: str = "fr") -> tuple[Optional[rdflib.Graph], list[dict]]:
    """Analyse Turtle ; renvoie (graphe | None, diagnostics d'erreur de syntaxe avec ligne et colonne)."""
    g = rdflib.Graph(bind_namespaces="none")
    try:
        g.parse(data=text, format="turtle", publicID=_NO_BASE)
    except BadSyntax as exc:
        raw = getattr(exc, "_str", b"") or b""
        if isinstance(raw, str):
            raw = raw.encode("utf-8")
        line, col = _line_col(raw, getattr(exc, "_i", 0))
        raw_why = str(getattr(exc, "_why", "") or exc)
        mp = re.match(r'Prefix "([^"]*):?" not bound', raw_why)
        found = find_prefix_use(text, mp.group(1).rstrip(":")) if mp else None
        if found:
            line, col = found
        why = _why(raw_why, lang)
        return None, [diag(line, col, "error", _t(f"Syntaxe Turtle : {why}", f"Turtle syntax: {why}", lang), "turtle-syntax")]
    except Exception as exc:  # noqa: BLE001 — autres erreurs rdflib (IRI, littéraux…)
        msg = str(exc).strip().splitlines()[0] if str(exc).strip() else exc.__class__.__name__
        m = re.search(r"line (\d+)", str(exc))
        return None, [diag(int(m.group(1)) if m else 1, 1, "error", _t(f"Syntaxe Turtle : {msg}", f"Turtle syntax: {msg}", lang), "turtle-syntax")]
    iri_errs = _iri_errors(g, text, lang)
    if iri_errs:
        return None, iri_errs
    return g, []


_PREFIX_RE = re.compile(r"(?im)^\s*(?:@prefix|prefix)\s+([A-Za-z][\w.\-]*)?:\s*<([^>]*)>")


def prefixes_of(text: str) -> dict[str, str]:
    return {(m.group(1) or ""): m.group(2) for m in _PREFIX_RE.finditer(text)}


def _decl_line(s: str) -> bool:
    t = s.lstrip().lower()
    return t.startswith(("@prefix", "prefix ", "@base", "base "))


class Locator:
    """Retrouve la ligne d'un sujet (IRI) dans un texte Turtle : forme <IRI> ou préfixée, en position de sujet de préférence."""

    def __init__(self, text: str) -> None:
        self.lines = text.splitlines()
        self.pmap = prefixes_of(text)

    def candidates(self, iri: str) -> list[str]:
        out = [f"<{iri}>"]
        for p, ns in sorted(self.pmap.items(), key=lambda kv: -len(kv[1])):
            if ns and iri.startswith(ns):
                rest = iri[len(ns):]
                if re.fullmatch(r"[\w\-]+(?:\.[\w\-]+)*", rest or "x") or rest == "":
                    out.append(f"{p}:{rest}")
        return out

    def find(self, iri: str) -> Optional[tuple[int, int]]:
        return self.find_any(self.candidates(iri))

    def find_any(self, cands: list[str]) -> Optional[tuple[int, int]]:
        first: Optional[tuple[int, int]] = None
        pats = [re.compile(r"(?<![\w:<#/\-])" + re.escape(c) + r"(?![\w\-:])") for c in cands]
        for i, line in enumerate(self.lines):
            if _decl_line(line):
                continue
            for pat in pats:
                m = pat.search(line)
                if not m:
                    continue
                if not line[:m.start()].strip():
                    return i + 1, m.start() + 1
                if first is None:
                    first = (i + 1, m.start() + 1)
        return first


def _short(g: rdflib.Graph, term: Any) -> str:
    try:
        return g.namespace_manager.normalizeUri(term)
    except Exception:  # noqa: BLE001
        return str(term)


def onto_diagnostics(text: str, lang: str = "fr") -> list[dict]:
    g, errs = syntax_diagnostics(text, lang)
    if g is None:
        return errs
    from ..io.rdf_import import RdfImportError, parse_ontology, parse_warning
    out: list[dict] = []
    loc = Locator(text)
    out_lit = literal_diagnostics(g, text, lang)
    try:
        model, warns = parse_ontology(text, "turtle")
    except (RdfImportError, ValueError) as exc:
        return [diag(1, 1, "error", _t(f"Ontologie illisible : {exc}", f"Unreadable ontology: {exc}", lang), "onto-import")]
    out.extend(out_lit)
    seen: set[tuple] = set()

    def add(subject: Optional[str], severity: str, message: str, code: str, spec: Optional[str] = None) -> None:
        pos = loc.find(subject) if subject else None
        line, col = pos if pos else (1, 1)
        key = (line, code, message)
        if key in seen:
            return
        seen.add(key)
        out.append(diag(line, col, severity, message, code, **({"subject": subject} if subject else {}),
                        **({"spec": spec} if spec else {})))

    for w in warns:
        pw = parse_warning(w)
        if pw["code"] == "format":
            continue
        add(pw["subject"], "warning", pw["message"], str(pw["code"]))
    try:
        from .. import localize
        from ..conformance.profiles import check_conformance
        from ..core.onto_model import local_name  # noqa: F401
        rep = localize.localize_conformance(json.loads(check_conformance(model, None, run_reasoner=False).model_dump_json()), lang)
        for i in rep["issues"]:
            sev = "info" if i["level"] == "info" else "warning"  # la conformité n'empêche jamais l'application
            add(i.get("subject"), sev, i["message"], i["code"], i.get("spec_ref"))
    except Exception as exc:  # noqa: BLE001 — la conformité est un plus : jamais bloquante pour l'édition
        out.append(diag(1, 1, "info", _t(f"Contrôles de conformité indisponibles : {exc}", f"Conformance checks unavailable: {exc}", lang), "conformance-off"))
    out.sort(key=lambda d: (d["line"], d["col"]))
    return out


def shapes_diagnostics(text: str, lang: str = "fr") -> list[dict]:
    g, errs = syntax_diagnostics(text, lang)
    if g is None:
        return errs
    out: list[dict] = []
    loc = Locator(text)
    # méta-validation shacl-shacl (pySHACL), puis lecture dans le modèle de shapes
    meta = _shacl_shacl(g, text, loc, lang)
    out.extend(meta)
    out.extend(nodeshape_path_diagnostics(g, loc, lang))
    out.extend(literal_diagnostics(g, text, lang))
    try:
        from ..shacl.import_shapes import parse_shapes
        _, warns = parse_shapes(text, "turtle")
        for w in warns:
            m = re.match(r"\[([\w\-]+)\]\s*(?:<([^>]*)>)?\s*:?\s*(.*)$", w, re.S)
            code, subj, msg = (m.group(1), m.group(2), m.group(3)) if m else ("shapes", None, w)
            if code == "format":
                continue
            pos = loc.find(subj) if subj else None
            out.append(diag(*(pos or (1, 1)), "warning", msg, code, **({"subject": subj} if subj else {})))
    except Exception as exc:  # noqa: BLE001
        if meta and meta[0]["code"] == "shacl-shacl":
            # la méta-shape a déjà localisé la cause : ses constats deviennent les erreurs qui bloquent l'application
            for d in meta:
                d["severity"] = "error"
            out.append(diag(meta[0]["line"], meta[0]["col"], "error",
                            _t("Shapes non appliquables : corriger d'abord les erreurs signalées par la méta-shape SHACL.",
                               "Shapes cannot be applied: first fix the errors reported by the SHACL meta-shape.", lang),
                            "shapes-import", detail=str(exc)))
        else:
            out.append(diag(1, 1, "error", _t(f"Shapes illisibles (non appliquables) : {exc}", f"Unreadable shapes (cannot be applied): {exc}", lang), "shapes-import"))
    out.sort(key=lambda d: (d["line"], d["col"]))
    return out


def _shacl_shacl(g: rdflib.Graph, text: str, loc: Locator, lang: str) -> list[dict]:
    try:
        import os
        import pyshacl
        asset = os.path.join(os.path.dirname(pyshacl.__file__), "assets", "shacl-shacl.ttl")
        meta = rdflib.Graph().parse(asset, format="turtle")
        _, rg, _ = pyshacl.validate(g, shacl_graph=meta, inference=None, advanced=False, inplace=False)  # À VÉRIFIER : API pySHACL 0.29
    except Exception as exc:  # noqa: BLE001
        return [diag(1, 1, "info", _t(f"Méta-validation SHACL indisponible : {exc}", f"SHACL meta-validation unavailable: {exc}", lang), "shacl-shacl-off")]
    out: list[dict] = []
    seen: set[tuple] = set()
    results = list(rg.subjects(RDF.type, SH.ValidationResult))
    # les constats « liste mal formée » sont émis en cascade (ListShape, ListNodeShape, hasValue rdf:nil, or…) : on garde celui
    # qui porte le prédicat fautif (sh:in…), les autres sont des échos de la même cause
    def is_list(r) -> bool:
        m = str(rg.value(r, SH.resultMessage) or "")
        return any(k in m for k in ("ListShape", "ListNodeShape", "rdf:nil", "rdf:rest"))
    results.sort(key=lambda r: (not is_list(r), rg.value(r, SH.resultPath) is None))
    list_done = False
    for r in results:
        focus = rg.value(r, SH.focusNode)
        path = rg.value(r, SH.resultPath)
        value = rg.value(r, SH.value)
        msg = str(rg.value(r, SH.resultMessage) or "")
        comp = str(rg.value(r, SH.sourceConstraintComponent) or "")
        if is_list(r):
            if list_done:
                continue
            list_done = True
        pos: Optional[tuple[int, int]] = None
        if isinstance(focus, rdflib.URIRef):
            pos = loc.find(str(focus))
        if pos is None:  # nœud blanc : on cherche le prédicat fautif (et la valeur), sinon le sujet qui le porte
            cands: list[str] = []
            if isinstance(path, rdflib.URIRef):
                cands += Locator(text).candidates(str(path))
            if cands and value is not None:
                lex = str(value)
                for i, line in enumerate(loc.lines):
                    if any(c in line for c in cands) and lex in line:
                        pos = (i + 1, line.index(next(c for c in cands if c in line)) + 1)
                        break
            if pos is None and cands:
                pos = loc.find_any(cands)
            if pos is None:
                for s in g.subjects(None, focus):
                    if isinstance(s, rdflib.URIRef):
                        pos = loc.find(str(s))
                        break
        where = f" ({_short(g, path)})" if isinstance(path, rdflib.URIRef) else ""
        why = _shacl_why(msg, comp, lang, is_list(r))
        text_msg = _t(f"Méta-shape SHACL{where} : {why}", f"SHACL meta-shape{where}: {why}", lang)
        key = (pos or (1, 1), text_msg)
        if key in seen:
            continue
        seen.add(key)
        out.append(diag(*(pos or (1, 1)), "warning", text_msg, "shacl-shacl", detail=msg))
    return out


def _shacl_why(msg: str, comp: str, lang: str, is_list: bool) -> str:
    """Traduit les familles fréquentes de messages pySHACL (méta-shape) ; le message brut reste dans ``detail``."""
    if lang == "en":
        if is_list:
            return "a well-formed RDF list is expected, e.g. ( ex:a ex:b )"
        return msg
    if is_list:
        return "une liste RDF bien formée est attendue, par exemple ( ex:a ex:b )"
    m = re.match(r"Value is not Literal with datatype (\S+)", msg)
    if m:
        return f"la valeur doit être un littéral de type {m.group(1)}"
    m = re.match(r"Value is not of Node Kind (\S+)", msg)
    if m:
        kinds = {"sh:IRI": "un IRI", "sh:Literal": "un littéral", "sh:BlankNode": "un nœud blanc",
                 "sh:BlankNodeOrIRI": "un IRI ou un nœud blanc", "sh:BlankNodeOrLiteral": "un nœud blanc ou un littéral",
                 "sh:IRIOrLiteral": "un IRI ou un littéral"}
        return f"la valeur doit être {kinds.get(m.group(1), m.group(1))}"
    m = re.match(r"More than (\d+) values", msg)
    if m:
        return f"plus de {m.group(1)} valeur(s) : au plus {m.group(1)} attendue(s)"
    m = re.match(r"Less than (\d+) values", msg)
    if m:
        return f"moins de {m.group(1)} valeur(s) : au moins {m.group(1)} attendue(s)"
    if "XoneConstraintComponent" in comp or "exactly one shape" in msg:
        return "ce nœud doit être soit une NodeShape, soit une PropertyShape (exactement l'une des deux)"
    return msg


def nodeshape_path_diagnostics(g: rdflib.Graph, loc: Locator, lang: str) -> list[dict]:
    """Une instance de sh:NodeShape ne peut pas avoir de sh:path (SHACL §2.3) : shacl-shacl ne le contrôle pas."""
    out: list[dict] = []
    for s in sorted(set(g.subjects(RDF.type, SH.NodeShape)), key=str):
        if (s, SH.path, None) in g:
            pos = loc.find(str(s)) if isinstance(s, rdflib.URIRef) else loc.find_any(Locator("").candidates(str(g.value(s, SH.path))))
            out.append(diag(*(pos or (1, 1)), "warning",
                            _t("Une NodeShape ne peut pas avoir de sh:path (SHACL §2.3) : c'est une PropertyShape, ou retirer sh:path.",
                               "A NodeShape cannot have sh:path (SHACL §2.3): make it a PropertyShape, or remove sh:path.", lang),
                            "shacl-nodeshape-path", **({"subject": str(s)} if isinstance(s, rdflib.URIRef) else {})))
    return out


def json_diagnostics(text: str, lang: str = "fr") -> list[dict]:
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        return [diag(exc.lineno, exc.colno, "error", _t(f"JSON invalide : {exc.msg}", f"Invalid JSON: {exc.msg}", lang), "json-syntax")]
    return _decisions_shape_errors(data, text, lang)


def _decisions_shape_errors(data: Any, text: str, lang: str) -> list[dict]:
    if not isinstance(data, dict) or any(not isinstance(v, dict) for v in data.values()):
        return [diag(1, 1, "error", _t("decisions.json doit être un objet {cible: {identifiant: choix}}.",
                                       "decisions.json must be an object {target: {id: choice}}.", lang), "decisions-shape")]
    out: list[dict] = []
    for tgt, d in data.items():
        for k, v in d.items():
            if not isinstance(v, str):
                m = re.search(re.escape(json.dumps(k)), text)
                line = text[:m.start()].count("\n") + 1 if m else 1
                out.append(diag(line, 1, "error", _t(f"Le choix de « {k} » doit être une chaîne.", f"The choice for \"{k}\" must be a string.", lang), "decisions-shape"))
    return out


def validate(p: Project, path: str, content: str, lang: str = "fr") -> list[dict]:
    """Diagnostics d'un contenu pour un chemin du projet. Fichier généré ou inconnu : aucun diagnostic."""
    if len(content.encode("utf-8")) > MAX_BYTES:
        return [diag(1, 1, "error", _t("Fichier trop volumineux pour l'éditeur (> 2 Mo).", "File too large for the editor (> 2 MB).", lang), "too-large")]
    if path == ONTO:
        return onto_diagnostics(content, lang)
    if path == SHAPES:
        return shapes_diagnostics(content, lang)
    if path == DECISIONS:
        return json_diagnostics(content, lang)
    return []


# ---- diff et application -------------------------------------------------------------------------------------

@dataclass
class Prepared:
    path: str
    after_text: str
    changed: bool
    summary: dict
    diagnostics: list[dict] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    onto: Optional[OntoModel] = None
    shapes: Optional[ShapesModel] = None
    decisions: Optional[dict] = None
    source: Optional[str] = None  # texte saisi à conserver tel quel (None : on écrit le canonique)
    model_changed: bool = True


class Invalid(Exception):
    def __init__(self, diagnostics: list[dict]) -> None:
        super().__init__("invalid")
        self.diagnostics = diagnostics


def _sample(g: rdflib.Graph, n: int = 25) -> list[str]:
    nm = g.namespace_manager
    return [" ".join(x.n3(nm) for x in t) + " ." for t in sorted(g)[:n]]


def _triple_diff(old: rdflib.Graph, new: rdflib.Graph) -> dict:
    _, only_old, only_new = graph_diff(to_isomorphic(old), to_isomorphic(new))
    return {"unit": "triples", "added": len(only_new), "removed": len(only_old),
            "samples": {"added": _sample(only_new), "removed": _sample(only_old)}}


def _rewritten(typed: rdflib.Graph, result: rdflib.Graph) -> dict:
    """Écart entre le graphe du texte saisi et le graphe canonique résultant : ce que l'import a réécrit."""
    _, only_typed, only_result = graph_diff(to_isomorphic(typed), to_isomorphic(result))
    return {"count": len(only_typed), "added": len(only_result),
            "samples": {"from": _sample(only_typed, 40), "to": _sample(only_result, 40)}}


def _finish(path: str, content: str, typed: rdflib.Graph, new_g: rdflib.Graph, old_g: rdflib.Graph, current: str,
            warns: list[str], **models: Any) -> Prepared:
    summary = _triple_diff(old_g, new_g)
    rew = _rewritten(typed, new_g)
    nc = comment_lines(content)
    kept = rew["count"] == 0 and rew["added"] == 0
    canon = canonical_turtle(new_g)
    summary["rewritten"] = rew
    summary["comment_lines"] = nc
    summary["source_kept"] = kept
    summary["comments_lost"] = 0 if kept else nc
    after = content if kept else canon
    return Prepared(path, after, after != current, summary, warnings=[w for w in warns if not w.startswith("[format]")],
                    source=content if kept else None, model_changed=bool(summary["added"] or summary["removed"]), **models)


def prepare(p: Project, path: str, content: str, lang: str = "fr") -> Prepared:
    """Valide le contenu, calcule le texte canonique résultant et le résumé du changement. Lève ``Invalid`` si la syntaxe est invalide."""
    if path.startswith(GENERATED_PREFIX):
        raise ReadOnlyFile(path)
    if path not in EDITABLE:
        raise FileNotFound(path)
    if len(content.encode("utf-8")) > MAX_BYTES:
        raise Invalid(validate(p, path, content, lang))
    current = editable_text(p, path)
    if path == DECISIONS:
        errs = [d for d in json_diagnostics(content, lang) if d["severity"] == "error"]
        if errs:
            raise Invalid(errs)
        new = json.loads(content)
        old = p.decisions
        flat = lambda d: {(t, k): v for t, m in d.items() for k, v in m.items()}  # noqa: E731
        fo, fn = flat(old), flat(new)
        added = sum(1 for k in fn if k not in fo)
        removed = sum(1 for k in fo if k not in fn)
        changed_n = sum(1 for k in fn if k in fo and fo[k] != fn[k])
        after = decisions_text(new)
        return Prepared(path, after, after != current, {"unit": "decisions", "added": added, "removed": removed, "changed": changed_n,
                                                       "samples": {"added": [], "removed": []}}, decisions=new)
    g, errs = syntax_diagnostics(content, lang)
    if g is None:
        raise Invalid(errs)
    warns: list[str] = []
    if path == ONTO:
        from ..io.rdf_import import RdfImportError, parse_ontology
        try:
            model, warns = parse_ontology(content, "turtle")
        except (RdfImportError, ValueError) as exc:
            raise Invalid([diag(1, 1, "error", _t(f"Ontologie illisible : {exc}", f"Unreadable ontology: {exc}", lang), "onto-import")]) from None
        return _finish(path, content, g, onto_graph(model), onto_graph(p.onto), current, warns, onto=model)
    from ..shacl.import_shapes import parse_shapes
    try:
        smodel, warns = parse_shapes(content, "turtle")
    except Exception as exc:  # noqa: BLE001
        errs = [d for d in shapes_diagnostics(content, lang) if d["severity"] == "error"]
        raise Invalid(errs or [diag(1, 1, "error", _t(f"Shapes illisibles : {exc}", f"Unreadable shapes: {exc}", lang), "shapes-import")]) from None
    return _finish(path, content, g, shapes_graph(smodel), shapes_graph(p.shapes), current, warns, shapes=smodel)


def drop_source(p: Project, path: str) -> None:
    from ..projects import store
    data = load_sources(p)
    if data.pop(path, None) is not None:
        store._atomic_write(_sources_file(p), json.dumps(data, ensure_ascii=False))


def remember_source(p: Project, path: str, prep: "Prepared") -> None:
    """Après application : conserve le texte saisi s'il est isomorphe au graphe du projet, sinon repart du canonique."""
    if path not in SOURCE_PATHS:
        return
    if prep.source is not None:
        save_source(p, path, prep.source, etag_of(canonical_text(p, path)))
    else:
        drop_source(p, path)


SNAPSHOT_KEY = {ONTO: "onto", SHAPES: "shapes", DECISIONS: "decisions"}
