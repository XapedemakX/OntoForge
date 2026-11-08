"""Amorcer une ontologie depuis un document (L25) : questions de compétence, brouillon traçable, contrôles déterministes.

Chaîne : document -> morceaux -> (1 appel « questions » + 1 appel « brouillon » par morceau) -> fusion des doublons
-> contrôles (schéma strict, noms valides, IRI nouvelles, hiérarchie sans cycle, extrait retrouvé dans le document)
-> lint W3C du brouillon -> couverture des questions. La proposition n'est JAMAIS appliquée ici : le front la soumet
à revue humaine, élément par élément (statut « à confirmer »).

Sans LLM (fournisseur non configuré, ``mock`` ou erreur du fournisseur) : repli déterministe (``docheur``), signalé approximatif.
Rien n'est envoyé hors de la machine avec ``mock`` ou ``ollama`` ; avec un fournisseur hébergé, ``confirm_hosted`` est exigé.
"""
from __future__ import annotations

import logging
import re
from typing import Any, Optional

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from ..core.onto_model import OntoModel, local_name
from . import docheur
from .convert import is_absolute_iri, normalize_base, to_onto
from .document import EXCERPT_MAX, Chunk, Document, chunk, digest, limits, locate
from .naming import _words as _name_words
from .naming import camel, humanize, pascal
from .providers import LLMError

log = logging.getLogger("ontoforge.assistant.document")

HOSTED = ("anthropic", "openai_compat")
RESERVED = {"thing", "nothing"}
NAME_RX = re.compile(r"^[A-Za-z][A-Za-z0-9]{0,63}$")

QUESTIONS_SYSTEM = """[TASK:docquestions]
Tu es un ontologue. On te donne un document (paragraphes préfixés par leur page, « [[p N]] »). Rédige entre 5 et 10 questions de compétence :
les questions concrètes auxquelles l'ontologie devra permettre de répondre, tirées du contenu du document (pas de questions génériques).
Écris-les dans la langue du document. Réponds par un unique objet JSON : {"questions":["...","..."]}. Aucun texte hors du JSON."""

DRAFT_SYSTEM = """[TASK:docdraft]
Tu es un ontologue expert (OWL 2 DL). Extrait du TEXTE fourni un brouillon d'ontologie qui permet de répondre aux QUESTIONS DE COMPÉTENCE.
Règles impérieuses :
1. Ne propose QUE ce que le texte justifie. Chaque élément porte "source": {"page": <numéro de la balise [[p N]]>, "excerpt": <citation EXACTE du texte, 300 caractères au plus>}.
2. Classes en PascalCase singulier, propriétés en camelCase ; propriétés d'objet = relations entre classes, propriétés de données = attributs.
3. Types de données parmi string, integer, decimal, double, boolean, dateTime, anyURI. "parent" seulement pour une vraie relation « est un » (pas partie-tout).
4. N'invente pas de classe absente du texte ; ne redéfinis pas les NOMS DÉJÀ CONNUS ; réutilise-les comme domaine, portée ou parent.
5. Libellés label_fr et label_en si tu peux les donner fidèlement.
Réponds par un unique objet JSON :
{"classes":[{"name","label_fr","label_en","comment","parent","disjoint_with":[],"key":[],"source":{"page","excerpt"}}],
 "object_properties":[{"name","label_fr","label_en","domain","range","functional","required","inverse","source":{"page","excerpt"}}],
 "datatype_properties":[{"name","label_fr","label_en","domain","range","functional","required","source":{"page","excerpt"}}],
 "explanation":"choix de modélisation","warnings":["points à arbitrer"]}
Aucun texte hors du JSON."""


# ----------------------------------------------------------------------------- schéma strict de la sortie
class _Src(BaseModel):
    model_config = ConfigDict(extra="forbid")
    page: int = Field(ge=1)
    excerpt: str = Field(min_length=3)


class _Item(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=120)
    label_fr: Optional[str] = None
    label_en: Optional[str] = None
    comment: Optional[str] = None
    comment_en: Optional[str] = None
    exact_match: Optional[str] = None
    close_match: Optional[str] = None
    source: _Src


class DClass(_Item):
    parent: Optional[str] = None
    disjoint_with: list[str] = []
    key: list[str] = []


class DObject(_Item):
    domain: Optional[str] = None
    range: Optional[str] = None
    functional: bool = False
    required: bool = False
    min: Optional[int] = None
    max: Optional[int] = None
    inverse: Optional[str] = None
    characteristics: list[str] = []


class DData(_Item):
    domain: Optional[str] = None
    range: str = "string"
    functional: bool = False
    required: bool = False


KINDS: dict[str, tuple[str, type[_Item]]] = {"classes": ("class", DClass), "object_properties": ("objectProperty", DObject),
                                            "datatype_properties": ("datatypeProperty", DData)}
TOP_KEYS = set(KINDS) | {"explanation", "warnings", "lang", "ontology"}


def _msg(lang: str, fr: str, en: str) -> str:
    return en if lang == "en" else fr


def _label_of(it: _Item) -> str:
    return it.label_fr or it.label_en or it.name


# ----------------------------------------------------------------------------- plan et estimation
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1", "host.docker.internal"}


def is_hosted(p: Any) -> bool:
    """Le texte quitterait-il la machine ? Oui pour anthropic / openai_compat, et pour un Ollama dont l'URL n'est pas locale
    (hôte en boucle locale, ``host.docker.internal`` ou nom de service sans point, comme ``ollama`` dans docker compose)."""
    name = getattr(p, "name", "")
    if name in HOSTED:
        return True
    if name == "ollama":
        from urllib.parse import urlsplit
        try:
            url = p._get("base_url", "OLLAMA_BASE_URL") or ""
            host = (urlsplit(url if "://" in url else "http://" + url).hostname or "").lower()
        except Exception:  # noqa: BLE001 — URL illisible : on reste prudent
            return True
        if not host or host in LOCAL_HOSTS or host.startswith("127."):
            return False
        return "." in host or ":" in host  # nom sans point (« ollama ») : service du même docker compose
    return False


def plan(doc: Document, p: Any) -> dict[str, Any]:
    """Nombre d'appels et taille envoyée, avant tout envoi. ``hosted`` : le texte quitterait la machine."""
    chunks = chunk(doc)
    dig = digest(doc)
    overhead = len(DRAFT_SYSTEM) + 600
    sent = len(dig) + len(QUESTIONS_SYSTEM) + sum(c.chars + overhead for c in chunks)
    engine = "llm" if (p.configured and p.name != "mock") else "heuristic"
    return {"chunks": len(chunks), "calls": (1 + len(chunks)) if engine == "llm" else 0, "chars_sent": sent if is_hosted(p) else 0,
            "chars_total": sent, "hosted": is_hosted(p), "engine": engine, "provider": p.name, "model": getattr(p, "model", ""),
            "pages": len(doc.pages), "chars": doc.chars, "limits": limits()}


# ----------------------------------------------------------------------------- appels LLM
def _ask(p: Any, system: str, user: str, max_tokens: int = 6000) -> dict[str, Any]:
    from .service import _ask_json
    return _ask_json(p, system, user, max_tokens)


def _llm_questions(p: Any, doc: Document, lang: str) -> list[str]:
    data = _ask(p, QUESTIONS_SYSTEM + f"\nLangue de la réponse : {'English' if lang == 'en' else 'français'}.", "DOCUMENT\n" + digest(doc), 2000)
    qs = data.get("questions")
    if not isinstance(qs, list):
        raise LLMError("réponse sans liste de questions")
    out = []
    for q in qs:
        s = q.get("question") if isinstance(q, dict) else q
        if isinstance(s, str) and 8 <= len(s.strip()) <= 300 and s.strip() not in out:
            out.append(s.strip())
    return out[:10]


def _known_names(onto: OntoModel, acc: list[dict[str, Any]]) -> str:
    names = [local_name(i) for i in onto.classes][:80] + [str(c.get("name")) for d in acc for c in d.get("classes", [])][:80]
    return ", ".join(dict.fromkeys(names)) or "(aucun)"


def _llm_chunk(p: Any, ch: Chunk, qs: list[str], onto: OntoModel, acc: list[dict[str, Any]], base: str) -> dict[str, Any]:
    user = (f"Base IRI : {base}\n\nQUESTIONS DE COMPÉTENCE\n" + "\n".join(f"- {q}" for q in qs)
            + f"\n\nNOMS DÉJÀ CONNUS : {_known_names(onto, acc)}\n\nTEXTE\n{ch.text}\n")
    return _ask(p, DRAFT_SYSTEM, user)


# ----------------------------------------------------------------------------- consolidation
class Cons:
    """Résultat de la consolidation : modèle + traçabilité + écarts."""

    def __init__(self) -> None:
        self.warnings: list[str] = []
        self.skipped: list[dict[str, str]] = []
        self.provenance: dict[str, dict[str, Any]] = {}
        self.merged = 0
        self.dropped = 0


def _parse(raw: dict[str, Any], doc: Document, lang: str, c: Cons) -> dict[str, list[tuple[str, _Item]]]:
    """Schéma strict + extrait retrouvé dans le document. Un élément invalide est écarté avec son motif, jamais corrigé en silence."""
    out: dict[str, list[tuple[str, _Item]]] = {k: [] for k in KINDS}
    extra = sorted(set(raw) - TOP_KEYS)
    if extra:
        c.warnings.append(_msg(lang, f"Clés inattendues ignorées dans la réponse du LLM : {', '.join(extra)}.",
                               f"Unexpected keys ignored in the LLM response: {', '.join(extra)}."))
    for key, (kind, model) in KINDS.items():
        items = raw.get(key)
        if items is None:
            continue
        if not isinstance(items, list):
            c.warnings.append(_msg(lang, f"« {key} » n'est pas une liste : ignoré.", f"“{key}” is not a list: ignored."))
            c.dropped += 1
            continue
        for obj in items:
            try:
                it = model.model_validate(obj)
            except ValidationError as exc:
                e = exc.errors()[0]
                nm = obj.get("name") if isinstance(obj, dict) else "?"
                where = ".".join(str(x) for x in e["loc"])
                c.warnings.append(_msg(lang, f"Élément « {nm} » écarté : schéma invalide ({where} : {e['msg']}).",
                                       f"Item “{nm}” rejected: invalid schema ({where}: {e['msg']})."))
                c.dropped += 1
                continue
            hit = locate(doc, it.source.excerpt, it.source.page)
            if hit is None:
                c.warnings.append(_msg(lang, f"« {it.name} » écarté : l'extrait cité est introuvable dans le document (possible invention).",
                                       f"“{it.name}” rejected: the quoted excerpt is not in the document (possible hallucination)."))
                c.dropped += 1
                continue
            it.source = _Src(page=hit[0], excerpt=hit[1][:EXCERPT_MAX])
            out[key].append((kind, it))
    return out


def _ckey(it: _Item) -> set[str]:
    ks = {docheur.nkey(it.name)}
    for lab in (it.label_fr, it.label_en):
        if lab:
            ks.add(docheur.nkey(lab))
    return {k for k in ks if k}


def _valid_name(name: str, kind: str) -> Optional[str]:
    if not _name_words(name):  # « !!! » ou un nom sans lettre latine donnerait « X » : plusieurs noms fusionneraient en une même IRI
        return None
    n = pascal(name) if kind == "class" else camel(name)
    if not n or not NAME_RX.match(n) or n.lower() in RESERVED:
        return None
    return n


def _merge_into(a: _Item, b: _Item, c: Optional["Cons"] = None, lang: str = "fr") -> None:
    for f in ("label_fr", "label_en", "comment", "comment_en", "exact_match", "close_match"):
        if not getattr(a, f) and getattr(b, f):
            setattr(a, f, getattr(b, f))
    if isinstance(a, DClass) and isinstance(b, DClass):
        if not a.parent and b.parent:
            a.parent = b.parent
        a.disjoint_with = list(dict.fromkeys([*a.disjoint_with, *b.disjoint_with]))
        a.key = list(dict.fromkeys([*a.key, *b.key]))
    if isinstance(a, (DObject, DData)) and isinstance(b, (DObject, DData)):
        # rdfs:domain / rdfs:range sont globaux : deux domaines différents ne se fusionnent pas (leur conjonction serait fausse).
        # Le premier est gardé et l'écart est signalé, jamais perdu en silence.
        for f in ("domain", "range") if isinstance(a, DObject) and isinstance(b, DObject) else ("domain",):
            va, vb = getattr(a, f), getattr(b, f)
            if not va and vb:
                setattr(a, f, vb)
            elif va and vb and docheur.nkey(va) != docheur.nkey(vb) and c is not None:
                what = _msg(lang, "domaine" if f == "domain" else "portée", f)
                c.warnings.append(_msg(lang, f"« {a.name} » : {what} « {vb} » d'un autre passage ignoré (« {va} » gardé). "
                                             "Une même propriété ne peut pas avoir deux domaines distincts ; renommez l'une des deux (ex. dateControle).",
                                       f"“{a.name}”: {what} “{vb}” from another passage ignored (“{va}” kept). "
                                       "A property cannot have two distinct domains; rename one of them (e.g. inspectionDate)."))


def consolidate(drafts: list[dict[str, Any]], doc: Document, onto: OntoModel, base: str, lang: str) -> tuple[dict[str, Any], Cons]:
    """Brouillons bruts (un par morceau) -> données prêtes pour ``to_onto`` + traçabilité. Voir la docstring du module."""
    c = Cons()
    dlang = docheur.detect_lang("\n".join(p.text for p in doc.pages))  # langue des libellés : celle du document, pas celle de l'interface
    parsed: dict[str, list[tuple[str, _Item]]] = {k: [] for k in KINDS}
    for raw in drafts:
        for k, v in _parse(raw, doc, lang, c).items():
            parsed[k].extend(v)

    # --- noms valides, puis fusion des doublons (nom local ou libellé normalisés)
    merged: dict[str, list[_Item]] = {k: [] for k in KINDS}
    index: dict[str, dict[str, _Item]] = {k: {} for k in KINDS}
    for key, lst in parsed.items():
        for kind, it in lst:
            nm = _valid_name(it.name, kind)
            if nm is None:
                c.warnings.append(_msg(lang, f"« {it.name} » écarté : nom non valide pour une IRI.", f"“{it.name}” rejected: not a valid IRI name."))
                c.dropped += 1
                continue
            if not (it.label_fr or it.label_en):  # libellé dans la langue du document, avec ses accents (pas le nom local en @en)
                setattr(it, f"label_{dlang}", it.name.strip())
            if dlang == "en" and it.comment and not it.comment_en:  # un commentaire sans langue suit le document
                it.comment_en, it.comment = it.comment, None
            it.name = nm
            hit = next((index[key][k] for k in _ckey(it) if k in index[key]), None)
            if hit is not None:
                _merge_into(hit, it, c, lang)
                c.merged += 1
                continue
            merged[key].append(it)
            for k in _ckey(it):
                index[key][k] = it

    # --- doublons avec l'ontologie existante : écartés, mais leur IRI sert de référence
    existing: dict[str, dict[str, str]] = {"classes": {}, "object_properties": {}, "datatype_properties": {}}
    for coll, store in (("classes", onto.classes), ("object_properties", onto.object_properties), ("datatype_properties", onto.datatype_properties)):
        for iri, e in store.items():
            for k in {docheur.nkey(local_name(iri)), *(docheur.nkey(v) for v in e.labels.values())}:
                if k:
                    existing[coll].setdefault(k, iri)
    kinds_of: dict[str, str] = {}  # IRI -> collection, ontologie existante puis brouillon : une IRI = un seul type d'entité (OWL 2 DL, SS §5.9)
    for coll, store in (("classes", onto.classes), ("object_properties", onto.object_properties), ("datatype_properties", onto.datatype_properties)):
        for iri in store:
            kinds_of.setdefault(iri, coll)
    kept: dict[str, list[_Item]] = {k: [] for k in KINDS}
    ref: dict[str, str] = {}  # clé de classe -> nom ou IRI à utiliser dans les références
    for key, lst in merged.items():
        for it in lst:
            iri = next((existing[key][k] for k in _ckey(it) if k in existing[key]), None)
            if iri:
                c.skipped.append({"name": it.name, "iri": iri, "reason": "existing"})
                if key == "classes":
                    for k in _ckey(it):
                        ref[k] = iri
                continue
            my_iri = base + (pascal(it.name) if key == "classes" else camel(it.name))
            other = kinds_of.get(my_iri)
            if other and other != key:
                c.warnings.append(_msg(lang, f"« {it.name} » écarté : l'IRI {local_name(my_iri)} désigne déjà une autre sorte d'entité ({other}) ; "
                                             "ce punning est interdit en OWL 2 DL (SS §5.9). Renommez-le.",
                                       f"“{it.name}” rejected: IRI {local_name(my_iri)} already names another kind of entity ({other}); "
                                       "this punning is not allowed in OWL 2 DL (SS §5.9). Rename it."))
                c.dropped += 1
                continue
            kinds_of.setdefault(my_iri, key)
            kept[key].append(it)
    own = {k for it in kept["classes"] for k in _ckey(it)}
    for k, iri in existing["classes"].items():
        ref.setdefault(k, iri)

    def resolve(name: Optional[str], owner: _Item, role: str) -> Optional[str]:
        """Nom cité -> nom d'une classe du brouillon, IRI d'une classe existante, ou classe créée depuis la source de l'élément."""
        if not name:
            return None
        k = docheur.nkey(name)
        if k in own:
            hit = next(it for it in kept["classes"] if k in _ckey(it))
            return hit.name
        if k in ref:
            return ref[k]
        nm = _valid_name(name, "class")
        if nm is None:
            return None
        stub = DClass(name=nm, label_fr=name if dlang != "en" else None, label_en=name if dlang == "en" else None, source=owner.source)
        kept["classes"].append(stub)
        own.update(_ckey(stub))
        c.warnings.append(_msg(lang, f"La classe « {name} » (citée comme {role} de « {owner.name} ») n'était pas déclarée : créée depuis le même extrait, à vérifier.",
                               f"Class “{name}” (cited as {role} of “{owner.name}”) was not declared: created from the same excerpt, please check."))
        return nm

    for it in list(kept["classes"]):
        assert isinstance(it, DClass)
        it.parent = resolve(it.parent, it, "parent") if it.parent else None
        it.disjoint_with = [x for x in (resolve(d, it, "disjointe") for d in it.disjoint_with) if x]
    for it in list(kept["object_properties"]):
        assert isinstance(it, DObject)
        it.domain, it.range = resolve(it.domain, it, "domaine"), resolve(it.range, it, "portée")
        if it.inverse:
            it.inverse = camel(it.inverse)
    for it in list(kept["datatype_properties"]):
        assert isinstance(it, DData)
        it.domain = resolve(it.domain, it, "domaine")

    # --- hiérarchie sans cycle, y compris à travers l'ontologie existante
    parent_of: dict[str, str] = {}
    for iri, cl in onto.classes.items():
        if cl.sub_class_of:
            parent_of[iri] = cl.sub_class_of[0]

    def ident(n: str) -> str:
        return n if is_absolute_iri(n) else base + pascal(n)

    for it in kept["classes"]:
        assert isinstance(it, DClass)
        if not it.parent:
            continue
        me, up = ident(it.name), ident(it.parent)
        seen, cur = set(), up
        cyc = me == up
        while cur and cur not in seen and not cyc:
            seen.add(cur)
            cur = parent_of.get(cur, "")
            cyc = cur == me
        if cyc:
            c.warnings.append(_msg(lang, f"Cycle de hiérarchie évité : le parent « {local_name(up)} » de « {it.name} » est retiré.",
                                   f"Hierarchy cycle avoided: parent “{local_name(up)}” of “{it.name}” was removed."))
            it.parent = None
        else:
            parent_of[me] = up

    # --- données pour to_onto + traçabilité
    data: dict[str, Any] = {"classes": [], "object_properties": [], "datatype_properties": [], "warnings": []}
    for key in KINDS:
        for it in kept[key]:
            d = it.model_dump(exclude={"source"}, exclude_none=True)
            data[key].append(d)
            iri = it.name if is_absolute_iri(it.name) else base + (pascal(it.name) if key == "classes" else camel(it.name))
            src = {"document": doc.name, "page": it.source.page, "excerpt": it.source.excerpt}
            c.provenance[iri] = src
            if isinstance(it, DObject) and it.inverse:
                c.provenance.setdefault(base + camel(it.inverse), src)
    return data, c


# ----------------------------------------------------------------------------- lint et assemblage
def _merged_with(onto: OntoModel, prop: OntoModel) -> OntoModel:
    m = onto.model_copy(deep=True)
    m.classes.update({k: v for k, v in prop.classes.items() if k not in onto.classes})
    m.object_properties.update({k: v for k, v in prop.object_properties.items() if k not in onto.object_properties})
    m.datatype_properties.update({k: v for k, v in prop.datatype_properties.items() if k not in onto.datatype_properties})
    return m


def _lint(onto: OntoModel, prop: OntoModel, lang: str) -> list[dict[str, Any]]:
    from ..conformance.lint import lint
    from ..localize import tr
    # éléments ajoutés par le brouillon, sorte par sorte : une IRI existante redéclarée sous une autre sorte (punning) reste « à moi »
    mine = {i for i in prop.classes if i not in onto.classes} | {i for i in prop.object_properties if i not in onto.object_properties} \
        | {i for i in prop.datatype_properties if i not in onto.datatype_properties}
    try:
        issues = lint(_merged_with(onto, prop))
    except Exception as exc:  # noqa: BLE001 — le lint ne doit jamais empêcher d'afficher le brouillon
        log.warning("lint du brouillon impossible : %s", exc)
        return []
    out = []
    for i in issues:
        if i.subject in mine:
            out.append({"level": i.level, "code": i.code, "subject": i.subject, "message": (tr(i.message, lang) or i.message), "spec_ref": i.spec_ref})
    return out


def _fix_existing_refs(prop: OntoModel, onto: OntoModel) -> None:
    """to_onto crée des classes « fantômes » pour les IRI existantes citées : on les remplace par la classe existante (aucune modification parasite)."""
    for iri in list(prop.classes):
        if iri in onto.classes:
            prop.classes[iri] = onto.classes[iri].model_copy(deep=True)
    refs = {r for op in prop.object_properties.values() for r in (*op.domain, *op.range)} | {r for dp in prop.datatype_properties.values() for r in dp.domain}
    refs |= {p for cl in prop.classes.values() for p in cl.sub_class_of}
    for iri in refs:
        if iri in onto.classes and iri not in prop.classes:
            prop.classes[iri] = onto.classes[iri].model_copy(deep=True)


# ----------------------------------------------------------------------------- couverture des questions
STOP_Q = set("""le la les un une des du de d l au aux et ou en a est sont ont etre avoir quel quelle quels quelles quoi qui que quand comment combien pourquoi ou dont
ce cet cette ces se sa son ses leur leurs il elle ils elles on nous vous je tu y ne pas plus moins tres tout tous toute toutes chaque plusieurs autre autres meme donne donnee donnees
par pour sur sous dans avec sans entre vers chez depuis jusqu selon cours ci mois an ans fois peut peuvent doit doivent faut
the a an of to in on at by for with from and or is are was were be been has have had do does did what which who whom whose when where how why many much each every all any some
this that these those it its their there then than as per about over under between into onto""".split())


def _words(s: str) -> list[str]:
    s = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", s)
    return [docheur.nkey(w) for w in re.findall(r"[A-Za-zÀ-ÿ]+", s) if len(w) >= 3]


def coverage(qs: list[str], onto: OntoModel, prop: OntoModel) -> list[dict[str, Any]]:
    """Une question est « couverte » si au moins un de ses mots significatifs correspond à un terme (nom ou libellé) du brouillon ou de l'ontologie."""
    terms: dict[str, tuple[str, str]] = {}  # mot -> (libellé, origine) ; les classes priment sur les propriétés
    for pick in (lambda m: [m.classes], lambda m: [m.object_properties, m.datatype_properties]):
        for origin, m in (("existing", onto), ("draft", prop)):
            for coll in pick(m):
                for iri, e in coll.items():
                    label = next(iter(e.labels.values()), local_name(iri))
                    known = iri in onto.classes or iri in onto.object_properties or iri in onto.datatype_properties
                    for w in [*_words(local_name(iri)), *(w for v in e.labels.values() for w in _words(v))]:
                        if w not in STOP_Q:
                            terms.setdefault(w, (label, "existing" if known else "draft"))
    out = []
    for i, q in enumerate(qs, 1):
        hits: list[str] = []
        for w in _words(q):
            if w in terms and w not in STOP_Q and terms[w][0] not in hits:
                hits.append(terms[w][0])
        out.append({"id": f"q{i}", "text": q, "covered": bool(hits), "terms": hits[:6]})
    return out


# ----------------------------------------------------------------------------- point d'entrée
def draft_document(project: Any, doc: Document, p: Any, lang: str = "fr", confirm_hosted: bool = False,
                   base_iri: Optional[str] = None) -> dict[str, Any]:
    """Document -> {questions, proposal, provenance, lint, ...}. Rien n'est appliqué au projet."""
    onto = project.onto
    pl = plan(doc, p)
    if pl["hosted"] and not confirm_hosted:
        raise HTTPException(status_code=409, detail=_msg(lang, f"Le document serait envoyé au fournisseur hébergé « {p.name} » ({pl['calls']} appels, "
                            f"environ {pl['chars_sent']} caractères). Confirmez l'envoi pour continuer.",
                            f"The document would be sent to the hosted provider “{p.name}” ({pl['calls']} calls, about {pl['chars_sent']} characters). Confirm to continue."))
    from . import service
    base = normalize_base(base_iri or (onto.meta.iri if onto.meta.iri else None) or service._default_base())
    chunks = chunk(doc)
    segs_all = [(pg.page, pg.text) for pg in doc.pages]
    warnings: list[str] = []
    engine = pl["engine"]
    qs: list[str] = []
    drafts: list[dict[str, Any]] = []
    calls = 0
    if engine == "llm":
        try:
            qs = _llm_questions(p, doc, lang)
            calls += 1
            for ch in chunks:
                try:
                    drafts.append(_llm_chunk(p, ch, qs, onto, drafts, base))
                    calls += 1
                except (LLMError, HTTPException) as exc:
                    detail = getattr(exc, "detail", None) or str(exc)
                    warnings.append(_msg(lang, f"Morceau {ch.index + 1}/{len(chunks)} : fournisseur en erreur ({detail}) ; repli déterministe sur ce morceau.",
                                         f"Chunk {ch.index + 1}/{len(chunks)}: provider error ({detail}); deterministic fallback on this chunk."))
                    drafts.append(docheur.extract(ch.segments))
        except (LLMError, HTTPException) as exc:
            detail = getattr(exc, "detail", None) or str(exc)
            warnings.append(_msg(lang, f"Fournisseur en erreur ({detail}) ; repli déterministe sur tout le document.",
                                 f"Provider error ({detail}); deterministic fallback on the whole document."))
            engine, drafts, qs = "heuristic", [], []
    if engine == "heuristic":
        drafts = [docheur.extract(segs_all)]
        qs = docheur.questions(segs_all, lang)
    if not qs:
        qs = docheur.questions(segs_all, lang)
    qs = qs[:10]
    approximate = engine == "heuristic" or any(d.get("lang") for d in drafts)
    if approximate:
        warnings.insert(0, _msg(lang, "Brouillon approximatif, produit sans LLM (motifs et termes fréquents) : relisez chaque élément avec son extrait.",
                                "Approximate draft produced without an LLM (patterns and frequent terms): review each item against its excerpt."))
    data, cons = consolidate(drafts, doc, onto, base, lang)
    prop, w = to_onto(data, base)
    # les classes citées de l'ontologie existante ne sont pas à recréer
    w = [x for x in w if not any(i in x for i in onto.classes)]
    _fix_existing_refs(prop, onto)
    # to_onto étiquette en @en, avec le nom local, ce qu'il crée lui-même (inverses) : dans un document non anglais c'est une
    # langue fausse. Libellé humanisé dans la langue du document.
    dlang = docheur.detect_lang("\n".join(pg.text for pg in doc.pages))
    if dlang != "en":
        for coll in (prop.classes, prop.object_properties, prop.datatype_properties):
            for iri, e in coll.items():
                if iri not in onto.classes and list(e.labels) == ["en"] and e.labels["en"] in (local_name(iri), camel(local_name(iri))):
                    e.labels = {dlang: humanize(local_name(iri))}
    issues = _lint(onto, prop, lang)
    # une erreur de conformité OWL 2 DL sur un élément du brouillon : l'élément est retiré (il serait refusé à l'application)
    bad = {i["subject"] for i in issues if i["level"] == "error"}
    if bad:
        for coll in (prop.classes, prop.object_properties, prop.datatype_properties):
            for iri in [x for x in coll if x in bad]:
                del coll[iri]
        for iri in bad:
            cons.provenance.pop(iri, None)
        warnings.append(_msg(lang, f"{len(bad)} élément(s) retiré(s) : non conformes à OWL 2 DL.", f"{len(bad)} item(s) removed: not OWL 2 DL conformant."))
        issues = [i for i in issues if i["subject"] not in bad]
    prov = {k: v for k, v in cons.provenance.items() if k in prop.classes or k in prop.object_properties or k in prop.datatype_properties}
    explanation = " ".join(str(d.get("explanation") or "") for d in drafts).strip()
    n = len(prop.classes) + len(prop.object_properties) + len(prop.datatype_properties)
    return {"document": {"name": doc.name, "pages": len(doc.pages), "chars": doc.chars, "lang": dlang}, "engine": engine, "approximate": approximate,
            "provider": p.name, "stats": {"chunks": len(chunks), "calls": calls, "chars_sent": pl["chars_sent"], "merged": cons.merged, "dropped": cons.dropped, "items": n},
            "questions": coverage(qs, onto, prop), "proposal": prop, "provenance": prov, "lint": issues, "skipped": cons.skipped,
            "warnings": [*warnings, *cons.warnings, *w], "explanation": explanation}
