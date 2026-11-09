"""Raisonnement OWL 2 DL avec HermiT (lot L32).

HermiT 1.3.8 est embarqué par owlready2 (``owlready2/hermit/HermiT.jar``). On ne passe PAS par l'API Python d'owlready2
(``sync_reasoner_hermit`` charge tout dans un monde en mémoire et ne rend ni durée ni diagnostic) : on lance directement
la ligne de commande de HermiT dans un sous-processus Java, avec le même classpath qu'owlready2 (le dossier ``hermit/`` contient
des classes corrigées qui doivent passer avant le jar) :

    java -Xmx<N>m -cp hermit:hermit/HermiT.jar org.semanticweb.HermiT.cli.CommandLine -c -O -D -I <ontologie.nt>

Sortie (une ligne par axiome, hiérarchie DIRECTE seulement) : ``SubClassOf( enfant parent )``,
``EquivalentClasses( a b … )`` (avec owl:Nothing = classes insatisfiables) et ``Type( individu classe )``.

Ce que HermiT ne fournit pas : aucune justification d'incohérence (l'option existe dans l'API Java d'OWL API, pas dans la
ligne de commande). Quand l'ontologie est incohérente, OntoForge cherche donc des CANDIDATS (individus dans deux classes
disjointes, sameAs/differentFrom) avec une heuristique syntaxique ; la réponse l'indique (``explanation.justification = false``).
"""
from __future__ import annotations

import os
import re
import shutil
import signal
import subprocess
import tempfile
import threading
import time
import zipfile
from dataclasses import dataclass
from typing import Any, Optional

import rdflib
from rdflib import BNode, URIRef
from rdflib.namespace import OWL, RDF, RDFS

DEFAULT_TIMEOUT = 30.0
MAX_TIMEOUT = 300.0
DEFAULT_MAX_MB = 1024
_LINE = re.compile(r"^([A-Za-z]+)\( ((?:<[^>]+>\s*)+) \)$", re.M)
_SLOTS = threading.BoundedSemaphore(int(os.environ.get("ONTOFORGE_HERMIT_SLOTS", "2")))


class HermitUnavailable(Exception):
    """Java ou owlready2 manquant. ``reason`` ∈ {java, owlready2}."""

    def __init__(self, reason: str, detail: str = ""):
        super().__init__(detail or reason)
        self.reason = reason


class HermitBusy(Exception):
    """Trop de raisonnements en parallèle (plafond mémoire du serveur)."""


@dataclass
class Setup:
    java: str
    classpath: str
    jar: str
    version: str


def configured_timeout(requested: Optional[float] = None) -> float:
    """Délai en secondes : demande > ONTOFORGE_HERMIT_TIMEOUT > 30 ; plafonné par ONTOFORGE_HERMIT_MAX_TIMEOUT (300)."""
    cap = float(os.environ.get("ONTOFORGE_HERMIT_MAX_TIMEOUT", MAX_TIMEOUT))
    base = float(os.environ.get("ONTOFORGE_HERMIT_TIMEOUT", DEFAULT_TIMEOUT))
    t = float(requested) if requested else base
    return max(1.0, min(t, cap))


def configured_memory() -> int:
    """Plafond du tas Java (Mo) : ONTOFORGE_HERMIT_MAX_MB, 1024 par défaut."""
    try:
        return max(128, int(os.environ.get("ONTOFORGE_HERMIT_MAX_MB", DEFAULT_MAX_MB)))
    except ValueError:
        return DEFAULT_MAX_MB


def locate() -> Setup:
    """Retrouve Java et le jar HermiT d'owlready2 ; lève HermitUnavailable sinon."""
    try:
        import owlready2
    except Exception as e:  # noqa: BLE001
        raise HermitUnavailable("owlready2", f"owlready2 introuvable : {type(e).__name__}") from None
    here = os.path.dirname(os.path.abspath(owlready2.__file__))
    folder, jar = os.path.join(here, "hermit"), os.path.join(here, "hermit", "HermiT.jar")
    if not os.path.isfile(jar):
        raise HermitUnavailable("owlready2", "HermiT.jar absent de owlready2")
    java = os.environ.get("ONTOFORGE_JAVA") or getattr(owlready2, "JAVA_EXE", None) or "java"
    java = shutil.which(java) or ""
    if not java:
        raise HermitUnavailable("java", "exécutable java introuvable dans le PATH")
    try:
        from importlib.metadata import version as _v
        ow = _v("owlready2")
    except Exception:  # noqa: BLE001
        ow = "?"
    try:
        with zipfile.ZipFile(jar) as z:
            mf = z.read("META-INF/MANIFEST.MF").decode("utf-8", "replace")
        hv = re.search(r"Implementation-Version:\s*(\S+)", mf)
        hv_s = hv.group(1) if hv else "1.3.8"
    except Exception:  # noqa: BLE001
        hv_s = "1.3.8"
    return Setup(java=java, classpath=os.pathsep.join([folder, jar]), jar=jar, version=f"HermiT {hv_s} (owlready2 {ow})")


def availability() -> dict[str, Any]:
    try:
        s = locate()
        return {"available": True, "version": s.version, "reason": None}
    except HermitUnavailable as e:
        return {"available": False, "version": None, "reason": e.reason}


# ---- messages bilingues ------------------------------------------------------------------------------------------
MSG: dict[str, dict[str, str]] = {
    "fr": {
        "unavail_java": "HermiT indisponible : Java est introuvable sur ce serveur. Installez un JRE (par exemple « apt-get install default-jre-headless ») "
                        "ou utilisez l'image Docker construite avec WITH_REASONER=1, puis relancez.",
        "unavail_owlready2": "HermiT indisponible : le paquet owlready2 (qui embarque HermiT) n'est pas installé. "
                             "Installez-le avec « pip install 'ontoforge[reasoner]' » (owlready2==0.47) ou utilisez l'image Docker construite avec WITH_REASONER=1.",
        "busy": "Trop de raisonnements HermiT en cours sur ce serveur. Réessayez dans quelques secondes.",
        "not_dl": "L'ontologie sort d'OWL 2 DL ({n} point(s) bloquant(s)) : HermiT n'offre ses garanties (correction et complétude) que pour OWL 2 DL. "
                  "Le résultat ci-dessous n'est qu'indicatif ; HermiT a pu ignorer des axiomes qu'il ne comprend pas.",
        "timeout": "HermiT n'a pas terminé dans le délai de {t:g} s : le calcul a été interrompu et aucun résultat n'est retenu. Augmentez le délai ou simplifiez l'ontologie.",
        "memory": "HermiT a dépassé le plafond mémoire de {m} Mo. Augmentez ONTOFORGE_HERMIT_MAX_MB ou simplifiez l'ontologie.",
        "error": "HermiT a échoué : {e}",
        "no_just": "HermiT (ligne de commande) ne fournit pas de justification de l'incohérence. Les éléments ci-dessous sont des candidats trouvés par OntoForge "
                   "(individus dans deux classes disjointes, sameAs et differentFrom) ; la cause réelle peut être ailleurs. Pour une justification minimale, "
                   "ouvrez l'ontologie dans Protégé (Explain inconsistent ontology).",
        "no_cand": "Aucun candidat évident (individu dans deux classes disjointes, sameAs contre differentFrom) : la cause passe par d'autres axiomes "
                   "(restrictions, cardinalités, propriétés fonctionnelles, clés owl:hasKey, valeurs de données…).",
        "via": " (type déduit du domaine ou de la portée de {p})",
        "imports": "{n} import(s) owl:imports non chargé(s) ({l}) : HermiT raisonne sur le seul contenu du projet, sans aller chercher les ontologies importées.",
        "thing_equiv": "{c} est inférée équivalente à owl:Thing : tout individu en fait partie. C'est souvent le signe d'un axiome trop large (domaine, portée ou définition).",
        "error_dl": " L'ontologie sort d'OWL 2 DL : l'échec vient probablement des points signalés dans le profil.",
        "disjoint": "{i} est de type {a} et {b}, qui sont disjointes",
        "sameas": "{a} et {b} sont à la fois owl:sameAs et owl:differentFrom",
        "unsat_member": "{i} est de type {c}, classe insatisfiable d'après ses ancêtres disjoints",
        "open_world": "HermiT raisonne en monde ouvert : l'absence d'une information n'est pas une erreur, et deux noms différents ne désignent pas forcément deux individus différents.",
    },
    "en": {
        "unavail_java": "HermiT is unavailable: Java was not found on this server. Install a JRE (for example “apt-get install default-jre-headless”) "
                        "or use the Docker image built with WITH_REASONER=1, then try again.",
        "unavail_owlready2": "HermiT is unavailable: the owlready2 package (which bundles HermiT) is not installed. "
                             "Install it with “pip install 'ontoforge[reasoner]'” (owlready2==0.47) or use the Docker image built with WITH_REASONER=1.",
        "busy": "Too many HermiT runs are in progress on this server. Try again in a few seconds.",
        "not_dl": "The ontology goes beyond OWL 2 DL ({n} blocking point(s)): HermiT only guarantees soundness and completeness for OWL 2 DL. "
                  "The result below is indicative only; HermiT may have ignored axioms it does not understand.",
        "timeout": "HermiT did not finish within {t:g} s: the run was stopped and no result is kept. Raise the time limit or simplify the ontology.",
        "memory": "HermiT exceeded the {m} MB memory cap. Raise ONTOFORGE_HERMIT_MAX_MB or simplify the ontology.",
        "error": "HermiT failed: {e}",
        "no_just": "HermiT (command line) does not provide a justification for the inconsistency. The items below are candidates found by OntoForge "
                   "(individuals in two disjoint classes, sameAs against differentFrom); the real cause may lie elsewhere. For a minimal justification, "
                   "open the ontology in Protégé (Explain inconsistent ontology).",
        "no_cand": "No obvious candidate (individual in two disjoint classes, sameAs against differentFrom): the cause lies in other axioms "
                   "(restrictions, cardinalities, functional properties, owl:hasKey keys, data values…).",
        "via": " (type derived from the domain or range of {p})",
        "imports": "{n} owl:imports not loaded ({l}): HermiT reasons over the project content only and does not fetch imported ontologies.",
        "thing_equiv": "{c} is inferred equivalent to owl:Thing: every individual belongs to it. This often reveals an axiom that is too broad (domain, range or definition).",
        "error_dl": " The ontology goes beyond OWL 2 DL: the failure most likely comes from the points reported by the profile check.",
        "disjoint": "{i} is typed {a} and {b}, which are disjoint",
        "sameas": "{a} and {b} are both owl:sameAs and owl:differentFrom",
        "unsat_member": "{i} is typed {c}, a class that is unsatisfiable given its disjoint ancestors",
        "open_world": "HermiT reasons under the open-world assumption: a missing fact is not an error, and two different names do not necessarily denote two different individuals.",
    },
}


def message(key: str, lang: str = "fr", **kw: Any) -> str:
    return MSG["en" if lang == "en" else "fr"][key].format(**kw)


def unavailable_message(exc: HermitUnavailable, lang: str = "fr") -> str:
    return message("unavail_java" if exc.reason == "java" else "unavail_owlready2", lang)


# ---- hiérarchie déclarée ---------------------------------------------------------------------------------------
def _named(x: Any) -> bool:
    return isinstance(x, URIRef) and x not in (OWL.Thing, OWL.Nothing)


def _rdf_list(g: rdflib.Graph, head: Any) -> list:
    out, seen = [], set()
    while head is not None and head != RDF.nil and head not in seen:
        seen.add(head)
        f = g.value(head, RDF.first)
        if f is not None:
            out.append(f)
        head = g.value(head, RDF.rest)
    return out


def _declared_edges(g: rdflib.Graph) -> tuple[dict[Any, set], set[frozenset]]:
    """(sup[c] = parents nommés déclarés ; paires équivalentes déclarées). Les conjoints nommés d'une définition
    ``A ≡ B ⊓ R`` ou ``A ⊑ B ⊓ R`` comptent comme des parents déclarés de A."""
    sup: dict[Any, set] = {}
    eq: set[frozenset] = set()

    def add(c: Any, d: Any) -> None:
        if _named(c) and _named(d) and c != d:
            sup.setdefault(c, set()).add(d)

    def conjuncts(x: Any) -> list:
        if isinstance(x, BNode):
            h = g.value(x, OWL.intersectionOf)
            if h is not None:
                return [y for y in _rdf_list(g, h)]
        return []

    for c, d in g.subject_objects(RDFS.subClassOf):
        add(c, d)
        for k in conjuncts(d):
            add(c, k)
    for c, d in g.subject_objects(OWL.equivalentClass):
        if _named(c) and _named(d):
            add(c, d); add(d, c)
            eq.add(frozenset((c, d)))
        for a, b in ((c, d), (d, c)):
            for k in conjuncts(b):
                add(a, k)
    return sup, eq


def _up(sup: dict[Any, set], c: Any) -> set:
    out, todo = {c}, [c]
    while todo:
        for p in sup.get(todo.pop(), ()):
            if p not in out:
                out.add(p); todo.append(p)
    return out


def _disjoint_pairs(g: rdflib.Graph) -> set[frozenset]:
    out: set[frozenset] = set()
    for a, b in g.subject_objects(OWL.disjointWith):
        out.add(frozenset((a, b)))
    for s in g.subjects(RDF.type, OWL.AllDisjointClasses):
        m = _rdf_list(g, g.value(s, OWL.members))
        for i, a in enumerate(m):
            for b in m[i + 1:]:
                out.add(frozenset((a, b)))
    for a, b in g.subject_objects(OWL.complementOf):
        if _named(a) and _named(b):
            out.add(frozenset((a, b)))
    return out


def _local(iri: Any) -> str:
    return re.split(r"[#/]", str(iri).rstrip("/#"))[-1] or str(iri)


def explain_inconsistency(g: rdflib.Graph, lang: str = "fr") -> dict[str, Any]:
    """Candidats syntaxiques d'une incohérence (PAS une justification HermiT). Fermeture des types par la hiérarchie déclarée."""
    sup, _ = _declared_edges(g)
    disj = [p for p in _disjoint_pairs(g) if len(p) == 2]
    ds = {frozenset(p) for p in disj}
    # classes insatisfiables « évidentes » : deux ancêtres (soi compris) disjoints
    unsat: set = set()
    for c in set(sup) | {x for v in sup.values() for x in v}:
        anc = _up(sup, c)
        if any(frozenset((a, b)) in ds for a in anc for b in anc if a != b):
            unsat.add(c)
    items: list[dict[str, Any]] = []
    classes: set = set()
    # types déduits du domaine (sujet) et de la portée (objet IRI) des propriétés utilisées dans les assertions
    via: dict[Any, dict[Any, set]] = {}
    for prop, dom in g.subject_objects(RDFS.domain):
        if _named(dom):
            for s_, _o in g.subject_objects(prop):
                if isinstance(s_, URIRef):
                    via.setdefault(s_, {}).setdefault(dom, set()).add(prop)
    for prop, rng in g.subject_objects(RDFS.range):
        if _named(rng) and (rng, RDF.type, OWL.Class) in g:
            for _s, o_ in g.subject_objects(prop):
                if isinstance(o_, URIRef):
                    via.setdefault(o_, {}).setdefault(rng, set()).add(prop)
    subjects = {s for s in g.subjects(RDF.type, None) if isinstance(s, URIRef)} | set(via)
    for i in sorted(subjects, key=str):
        direct = {t for t in g.objects(i, RDF.type) if _named(t)}
        derived = {t for t in via.get(i, {}) if t not in direct}
        if not direct and not derived:
            continue
        allt: set = set()
        origin: dict[Any, set] = {}
        for t in direct:
            allt |= _up(sup, t)
        for t in derived:
            for u in _up(sup, t):
                if u not in allt:
                    origin.setdefault(u, set()).update(via[i][t])
            allt |= _up(sup, t)
        hit = False
        for p in disj:
            a, b = sorted(p, key=str)
            if a in allt and b in allt:
                props = sorted({_local(x) for c in (a, b) for x in origin.get(c, ())})
                items.append({"individual": str(i), "classes": [str(a), str(b)], "kind": "disjoint",
                              "message": message("disjoint", lang, i=_local(i), a=_local(a), b=_local(b))
                              + (message("via", lang, p=", ".join(props)) if props else "")})
                classes |= {a, b}; hit = True
        if not hit:
            for t in sorted(direct & unsat, key=str):
                items.append({"individual": str(i), "classes": [str(t)], "kind": "unsatisfiable_class",
                              "message": message("unsat_member", lang, i=_local(i), c=_local(t))})
                classes.add(t)
    for a, b in g.subject_objects(OWL.sameAs):
        if isinstance(a, URIRef) and isinstance(b, URIRef) and ((a, OWL.differentFrom, b) in g or (b, OWL.differentFrom, a) in g):
            items.append({"individual": str(a), "classes": [], "kind": "same_and_different", "with": str(b),
                          "message": message("sameas", lang, a=_local(a), b=_local(b))})
    return {"justification": False, "source": "heuristic", "note": message("no_just", lang) + (" " + message("no_cand", lang) if not items else ""),
            "items": items, "individuals": sorted({it["individual"] for it in items}), "classes": sorted(str(c) for c in classes)}


# ---- analyse de la sortie HermiT ---------------------------------------------------------------------------------
def parse_output(text: str) -> dict[str, Any]:
    sub: list[tuple[str, str]] = []
    equiv: list[list[str]] = []
    types: dict[str, list[str]] = {}
    for rel, body in _LINE.findall(text):
        iris = [x for x in re.findall(r"<([^>]+)>", body)]
        if rel == "SubClassOf" and len(iris) == 2:
            sub.append((iris[0], iris[1]))
        elif rel == "EquivalentClasses":
            equiv.append(iris)
        elif rel == "Type" and len(iris) == 2:
            types.setdefault(iris[0], []).append(iris[1])
    return {"sub": sub, "equiv": equiv, "types": types}


def compare(g: rdflib.Graph, parsed: dict[str, Any]) -> dict[str, Any]:
    """Hiérarchie inférée − hiérarchie déclarée : sous-classes nouvelles, équivalences nouvelles, classes insatisfiables, individus reclassés."""
    sup, eq = _declared_edges(g)
    nothing, thing = str(OWL.Nothing), str(OWL.Thing)
    unsat: list[str] = []
    new_eq: list[list[str]] = []
    for grp in parsed["equiv"]:
        if nothing in grp:
            unsat += [x for x in grp if x != nothing and not x.startswith(str(OWL))]
            continue
        members = [x for x in grp if x != thing and not x.startswith(str(OWL))]
        if len(members) < 2:
            continue
        fresh = any(not (URIRef(b) in _up(sup, URIRef(a)) and URIRef(a) in _up(sup, URIRef(b)))
                    for i, a in enumerate(members) for b in members[i + 1:])
        if fresh:
            new_eq.append(sorted(members))
    # HermiT n'écrit qu'un représentant (arbitraire) par groupe de classes équivalentes : une arête est « déjà déclarée » si
    # un membre du groupe de l'enfant a, dans la hiérarchie déclarée, un membre du groupe du parent pour ancêtre.
    group: dict[str, set[str]] = {}
    thing_eq: list[str] = []
    for grp in parsed["equiv"]:
        if nothing in grp:
            continue
        if thing in grp:
            thing_eq += [x for x in grp if not x.startswith(str(OWL))]
        for x in grp:
            group[x] = set(grp)
    new_sub: list[dict[str, str]] = []
    for c, d in parsed["sub"]:
        if c.startswith(str(OWL)) or d.startswith(str(OWL)) or c in unsat or c == d:
            continue
        gd = {URIRef(x) for x in group.get(d, {d})}
        if not any(_up(sup, URIRef(c2)) & gd for c2 in group.get(c, {c})):
            new_sub.append({"sub": c, "sup": d})
    new_sub.sort(key=lambda x: (x["sub"], x["sup"]))
    re_ind: list[dict[str, Any]] = []
    for i, ts in sorted(parsed["types"].items()):
        inferred = {t for t in ts if not t.startswith(str(OWL))}
        if not inferred:
            continue
        declared = {t for t in g.objects(URIRef(i), RDF.type) if _named(t) and not str(t).startswith(str(OWL))}
        closure: set = set()
        for t in declared:
            closure |= _up(sup, t)
        fresh_t = sorted(t for t in inferred if URIRef(t) not in closure)
        if fresh_t:
            re_ind.append({"individual": i, "declared": sorted(str(t) for t in declared), "inferred": fresh_t})
    return {"unsatisfiable": sorted(set(unsat)), "new_subclass": new_sub, "new_equivalent": new_eq, "reclassified": re_ind,
            "thing_equivalent": sorted(set(thing_eq)),
            "counts": {"declared_subclass": sum(len(v) for v in sup.values()), "inferred_subclass": len(parsed["sub"]),
                       "inferred_types": sum(len(v) for v in parsed["types"].values())}}


# ---- exécution ---------------------------------------------------------------------------------------------------
def _run_java(cmd: list[str], timeout: float) -> tuple[Optional[int], str, str, bool]:
    """(code, stdout, stderr, timed_out). Le processus Java (et ses enfants) est tué à l'expiration."""
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, errors="replace", start_new_session=True)
    try:
        out, err = p.communicate(timeout=timeout)
        return p.returncode, out, err, False
    except subprocess.TimeoutExpired:
        try:
            os.killpg(p.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            p.kill()
        try:
            out, err = p.communicate(timeout=5)
        except Exception:  # noqa: BLE001
            out, err = "", ""
        return None, out or "", err or "", True


def run_hermit(g: rdflib.Graph, *, timeout: Optional[float] = None, lang: str = "fr", java_args: Optional[list[str]] = None) -> dict[str, Any]:
    """Lance HermiT sur le graphe RDF de l'ontologie. Lève HermitUnavailable (→ 501) ou HermitBusy (→ 503).

    Retour : dict JSON (voir docs/CONTRACTS.md §POST /reason). Les fichiers temporaires sont toujours supprimés."""
    setup = locate()
    limit = configured_timeout(timeout)
    mem = configured_memory()
    from .profiles import dl_issues
    dl_errors = sorted({f"{i.code} : {i.message}" for i in dl_issues(g) if i.level == "error"})
    out: dict[str, Any] = {
        "reasoner": "hermit", "version": setup.version, "status": "ok", "consistent": None, "duration_ms": 0,
        "timeout_s": limit, "max_memory_mb": mem, "dl": {"conformant": not dl_errors, "violations": dl_errors},
        "warnings": [], "explanation": None, "unsatisfiable": [],
        "hierarchy": {"new_subclass": [], "new_equivalent": [], "counts": {}}, "reclassified": [], "error": None,
    }
    if dl_errors:
        out["warnings"].insert(0, message("not_dl", lang, n=len(dl_errors)))
    # owl:imports : jamais suivis (HermiT irait chercher l'IRI sur le réseau depuis le serveur, ou échouerait). On raisonne sur
    # le contenu du projet, et on le dit.
    imports = sorted({str(o) for o in g.objects(None, OWL.imports)})
    if imports:
        g2 = rdflib.Graph()
        for t in g:
            if t[1] != OWL.imports:
                g2.add(t)
        g = g2
        out["warnings"].append(message("imports", lang, n=len(imports), l=", ".join(imports[:3]) + (" …" if len(imports) > 3 else "")))
    if not _SLOTS.acquire(blocking=False):
        raise HermitBusy(message("busy", lang))
    tmp = tempfile.mkdtemp(prefix="ontoforge-hermit-")
    t0 = time.monotonic()
    try:
        path = os.path.join(tmp, "onto.nt")
        g.serialize(destination=path, format="nt", encoding="utf-8")
        cmd = [setup.java, f"-Xmx{mem}m", "-Djava.io.tmpdir=" + tmp, *(java_args or []), "-cp", setup.classpath,
               "org.semanticweb.HermiT.cli.CommandLine", "-c", "-O", "-D", "-I", "--ignoreUnsupportedDatatypes", "file://" + path]
        code, so, se, timed_out = _run_java(cmd, limit)
        out["duration_ms"] = int((time.monotonic() - t0) * 1000)
        if timed_out:
            out["status"] = "timeout"
            out["warnings"].append(message("timeout", lang, t=limit))
            return out
        if "InconsistentOntologyException" in se or "Inconsistent ontology" in se or "Inconsistent ontology" in so:
            out["consistent"] = False
            out["explanation"] = explain_inconsistency(g, lang)
            out["unsatisfiable"] = []
            return out
        if "OutOfMemoryError" in se:
            out["status"] = "error"; out["error"] = message("memory", lang, m=mem)
            return out
        if code not in (0, None):
            last = [ln for ln in se.splitlines() if ln.strip() and "JAVA_TOOL_OPTIONS" not in ln]
            out["status"] = "error"; out["error"] = message("error", lang, e=(last[0] if last else f"code {code}")[:300]) + (message("error_dl", lang) if dl_errors else "")
            return out
        parsed = parse_output(so)
        cmp_ = compare(g, parsed)
        out["consistent"] = True
        out["unsatisfiable"] = cmp_["unsatisfiable"]
        out["hierarchy"] = {"new_subclass": cmp_["new_subclass"], "new_equivalent": cmp_["new_equivalent"], "counts": cmp_["counts"]}
        out["reclassified"] = cmp_["reclassified"]
        out["warnings"] += [message("thing_equiv", lang, c=_local(c)) for c in cmp_["thing_equivalent"]]
        return out
    finally:
        _SLOTS.release()
        shutil.rmtree(tmp, ignore_errors=True)
