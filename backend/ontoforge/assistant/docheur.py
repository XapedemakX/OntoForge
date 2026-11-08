"""Repli déterministe de l'amorçage depuis un document (L25) : aucun LLM, aucun réseau.

Approximatif par construction, assez pour une démonstration : termes capitalisés fréquents, définitions « Terme : ... »,
motifs « un X est un Y » et « un X a un Y » en français et en anglais. Chaque élément porte l'extrait de la phrase d'origine.
Le fournisseur ``mock`` s'appuie sur ce même moteur.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Any, Optional

from .document import snap_excerpt
from .naming import camel, pascal

Segments = list[tuple[int, str]]  # (page, texte)

FR_WORDS = {"le", "la", "les", "des", "du", "une", "un", "et", "est", "sont", "pour", "avec", "dans", "sur", "par", "chaque", "doit", "qui", "que", "au", "aux", "ou"}
EN_WORDS = {"the", "an", "is", "are", "and", "for", "with", "in", "on", "by", "each", "must", "which", "that", "of", "to", "has", "have"}

STOP_CAP = {"le", "la", "les", "un", "une", "des", "ce", "cette", "ces", "il", "elle", "ils", "elles", "on", "nous", "vous", "chaque", "tout", "toute", "tous", "toutes",
            "lorsque", "quand", "si", "dans", "pour", "par", "sur", "avec", "sans", "selon", "afin", "ainsi", "cela", "ceci", "mais", "donc", "or", "ni", "car", "et", "ou",
            "the", "a", "an", "this", "that", "these", "those", "each", "every", "when", "if", "in", "for", "by", "on", "with", "without", "according", "and", "or", "but",
            "chapitre", "article", "section", "annexe", "page", "objet", "contexte", "objectifs", "objectif", "questions", "question", "glossaire", "definitions", "définitions",
            "exigences", "exigence", "perimetre", "périmètre", "introduction", "conclusion", "cahier", "charges", "version", "date", "auteur", "client", "titre"}
LOWER_JOIN = {"de", "du", "des", "d", "la", "le", "les", "et", "ou", "of", "the", "and"}

DET = r"(?:un|une|le|la|l'|l’|les|des|chaque|tout|toute|son|sa|ses|plusieurs|a|an|the|each|every|its|his|her|their|one|any|some)"
HAS_FR = r"(?:a|possède|possede|dispose de|comporte|est caractérisé par|est caracterise par|est identifié par|est identifie par|est décrit par|est decrit par|contient|comprend|est composé de|est compose de|est équipé de|est equipe de|porte)"
HAS_EN = r"(?:has|have|contains|comprises|includes|is identified by|is described by|is composed of|is equipped with|carries)"
REL_FR = r"(?:concerne|appartient à|appartient a|effectue|réalise|realise|gère|gere|utilise|remplace|inspecte|vérifie|verifie|entretient|répare|repare|emploie|accueille)"
REL_EN = r"(?:concerns|belongs to|performs|carries out|manages|uses|replaces|inspects|checks|maintains|repairs|employs|hosts)"

DATE_W = {"date", "jour", "heure", "day", "time", "datetime"}
INT_W = {"kilometrage", "km", "nombre", "quantite", "annee", "age", "mileage", "count", "year", "quantity", "number", "profondeur", "duree"}
DEC_W = {"prix", "cout", "montant", "tarif", "pression", "taux", "poids", "price", "cost", "amount", "rate", "weight", "pressure", "tension"}  # « dimension » d'un pneu = « 205/55 R16 » : une chaîne
BOOL_W = {"actif", "active", "valide", "valid", "obligatoire", "mandatory"}


def unaccent(s: str) -> str:
    return unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()


def nkey(s: str) -> str:
    """Clé de comparaison : sans accent, minuscules, alphanumérique, singulier simple."""
    w = re.sub(r"[^a-z0-9]+", "", unaccent(s).lower())
    if w.endswith("aux") and len(w) > 5:
        return w[:-3] + "al"
    if w.endswith("s") and not w.endswith("ss") and len(w) > 3:
        return w[:-1]
    return w


def detect_lang(text: str) -> str:
    toks = re.findall(r"[a-zà-ÿ]+", text.lower())
    fr = sum(1 for t in toks if t in FR_WORDS)
    en = sum(1 for t in toks if t in EN_WORDS)
    return "en" if en > fr else "fr"


def unwrap(text: str) -> str:
    """Recolle les lignes coupées par la mise en page (PDF) : une ligne pleine, sans ponctuation finale, suivie d'une ligne qui n'ouvre pas un titre ni une puce."""
    lines = text.split("\n")
    out: list[str] = []
    for ln in lines:
        prev = out[-1] if out else ""
        if prev and len(prev) >= 55 and not re.search(r"[.!?:;]\s*$", prev) and ln.strip() and not re.match(r"^\s*(\d+(\.\d+)*[.)]\s|[-•*]\s)", ln):
            out[-1] = prev.rstrip() + " " + ln.strip()
        else:
            out.append(ln)
    return "\n".join(out)


def _sentences(page: int, text: str) -> list[tuple[int, str, int]]:
    """(page, phrase, 0) : une phrase par ligne logique, coupée aux ponctuations fortes."""
    out = []
    for line in unwrap(text).split("\n"):
        for s in re.finditer(r"[^.!?;]+[.!?;]?", line):
            seg = s.group(0).strip()
            if len(seg) > 2:
                out.append((page, seg, 0))
    return out


def _datatype(word: str) -> str:
    ws = set(re.findall(r"[a-z]+", unaccent(word).lower()))
    if ws & DATE_W:
        return "dateTime"
    if ws & INT_W:
        return "integer"
    if ws & DEC_W:
        return "decimal"
    if ws & BOOL_W:
        return "boolean"
    return "string"


def _display(term: str) -> str:
    t = term.replace("_", " ").strip()
    return t[:1].upper() + t[1:]


class _Finder:
    def __init__(self, segs: Segments) -> None:
        self.segs = segs
        self.sents = [s for p, t in segs for s in _sentences(p, t)]
        self.text = "\n".join(t for _, t in segs)
        self.lang = detect_lang(self.text)
        self.classes: dict[str, dict[str, Any]] = {}  # nkey -> {display, source, parent}
        self.multi: set[str] = set()

    # --- sources
    def source(self, page: int, sentence: str) -> dict[str, Any]:
        ex = sentence.strip()
        if len(ex) > 300:
            ex = snap_excerpt(ex, 0, min(len(ex), 60))
        return {"page": page, "excerpt": ex}

    # --- termes
    def _tokens(self, s: str) -> list[str]:
        return re.findall(r"[\wÀ-ÿ'’-]+", s)

    def find_multiwords(self) -> None:
        """« Contrôle technique » : mot capitalisé suivi d'un mot en minuscules, répété et jamais en début de phrase seulement."""
        cnt: dict[str, int] = {}
        for _, s, _ in self.sents:
            for m in re.finditer(r"\b([A-ZÀ-Ý][a-zà-ÿ]{2,})\s+([a-zà-ÿ]{4,})\b", s):
                a, b = m.group(1), m.group(2)
                if a.lower() in STOP_CAP or b.lower() in STOP_CAP | FR_WORDS | EN_WORDS | LOWER_JOIN:
                    continue
                cnt[f"{a} {b}"] = cnt.get(f"{a} {b}", 0) + 1
        self.multi = {k for k, v in cnt.items() if v >= 2 and self._is_term(k.split()[0], v)}

    def _is_term(self, head: str, n: int) -> bool:
        # le mot seul doit aussi apparaître capitalisé ailleurs (sinon c'est une simple tournure de phrase)
        return len(re.findall(r"\b" + re.escape(head) + r"\b", self.text)) >= 2

    def protect(self, s: str) -> str:
        for k in sorted(self.multi, key=len, reverse=True):
            s = re.sub(re.escape(k), k.replace(" ", "_"), s, flags=re.I)
        return s

    def add_class(self, term: str, page: int, sentence: str, parent: Optional[str] = None) -> str:
        term = term.strip().replace("_", " ")
        k = nkey(term)
        if not k or len(k) < 3:
            return k
        cur = self.classes.get(k)
        if cur is None:
            self.classes[k] = {"display": _display(term), "source": self.source(page, sentence), "parent": parent}
        else:
            if len(term) < len(cur["display"]):  # on préfère la forme au singulier (la plus courte)
                cur["display"] = _display(term)
            if parent and not cur.get("parent"):
                cur["parent"] = parent
        return k

    def capitalised_terms(self) -> None:
        cnt: dict[str, int] = {}
        first: dict[str, tuple[int, str]] = {}
        strong: set[str] = set()
        for page, s, _ in self.sents:
            toks = self._tokens(self.protect(s))
            caps = [bool(t[:1].isupper()) and not t.isupper() for t in toks]
            solid = [c and t.lower() not in STOP_CAP for c, t in zip(caps, toks)]
            for i, t in enumerate(toks):
                base = t.replace("_", " ")
                if not caps[i] or t.lower() in STOP_CAP or len(t) < 3:
                    continue
                prev_cap = i > 0 and solid[i - 1]
                next_cap = i + 1 < len(toks) and solid[i + 1]
                if prev_cap or next_cap:  # nom propre composé (« Garage Martin ») : ignoré
                    continue
                definition = i == 0 and re.match(r"^\s*[\wÀ-ÿ' -]{3,40}\s*[:—–-]\s+\S", s) is not None
                if i == 0 and not definition and "_" not in t:
                    continue  # majuscule de début de phrase : pas un indice
                key = nkey(base)
                cnt[key] = cnt.get(key, 0) + (2 if definition else 1)
                if definition:
                    strong.add(key)
                first.setdefault(key, (page, s))
                self._disp = getattr(self, "_disp", {})
                if key not in self._disp or len(base) < len(self._disp[key]):
                    self._disp[key] = base
        for key, n in cnt.items():
            if n >= 2:
                page, s = first[key]
                self.add_class(self._disp[key], page, s)
        # une définition « Terme : ... » donne la source la plus utile : on la préfère
        for page, s, _ in self.sents:
            m = re.match(r"^\s*([\wÀ-ÿ' -]{3,40}?)\s*[:—–]\s+\S", self.protect(s))
            if m:
                k = nkey(m.group(1))
                if k in self.classes:
                    self.classes[k]["source"] = self.source(page, s)

    def resolve(self, term: str) -> Optional[str]:
        """Terme du texte → clé de classe connue (singulier, multi-mots) ou None."""
        k = nkey(term.replace("_", " "))
        if k in self.classes:
            return k
        # dernier mot d'un groupe nominal (« pneu avant » -> pneu) ou premier
        ws = re.findall(r"[\wÀ-ÿ]+", term.replace("_", " "))
        for w in (ws[0:1] + ws[-1:]) if ws else []:
            if nkey(w) in self.classes:
                return nkey(w)
        return None

    # --- motifs
    def patterns(self) -> tuple[list[dict], list[dict]]:
        objs: list[dict] = []
        datas: list[dict] = []
        is_re = re.compile(rf"\b{DET}?\s*(?P<x>[\wÀ-ÿ'’-]+)\s+(?:est|is)\s+(?:un|une|a|an)\s+(?:(?:type|sorte|forme|kind|sort)\s+(?:de|d'|d’|of)\s+)?(?P<y>[\wÀ-ÿ'’-]+)", re.I)
        has_re = re.compile(rf"(?:\b|^){DET}?\s*(?P<x>[\wÀ-ÿ'’-]+)\s+(?:{HAS_FR}|{HAS_EN})\s+(?P<rest>[^.;:!?]+)", re.I)
        rel_re = re.compile(rf"(?:\b|^){DET}?\s*(?P<x>[\wÀ-ÿ'’-]+)\s+(?P<v>{REL_FR}|{REL_EN})\s+{DET}?\s*(?P<y>[\wÀ-ÿ'’-]+)", re.I)
        for page, s, _ in self.sents:
            p = self.protect(s)
            for m in is_re.finditer(p):
                x, y = m.group("x"), m.group("y")
                if y.lower() in {"un", "une", "the", "an", "a"}:
                    continue
                xk, yk = self.resolve(x), self.resolve(y)
                if xk and xk != "":
                    if not yk:
                        if not y[:1].isupper():
                            continue
                        yk = self.add_class(y, page, s)
                    if xk != yk and yk in self.classes:
                        self.classes[xk]["parent"] = self.classes[yk]["display"]
            for m in has_re.finditer(p):
                xk = self.resolve(m.group("x"))
                if not xk:
                    continue
                for raw in re.split(r",|;|\bet\b|\band\b|\bou\b|\bor\b", m.group("rest")):
                    item = re.sub(rf"^\s*{DET}\s+", "", raw.strip(), flags=re.I).strip()
                    item = re.sub(r"^(?:une?|des|de|d'|d’)\s+", "", item, flags=re.I)
                    words = re.findall(r"[\wÀ-ÿ'’-]+", item)
                    if not words or len(words) > 4 or len(item) < 3:
                        continue
                    yk = self.resolve(item) if len(words) <= 2 else None
                    if yk and yk != xk and (item.replace("_", " ")[:1].isupper() or len(words) == 1 and nkey(words[0]) in self.classes):
                        name = ("has" if self.lang == "en" else "possede") + pascal(self.classes[yk]["display"])
                        objs.append({"name": name, "domain": self.classes[xk]["display"], "range": self.classes[yk]["display"],
                                     "label": self._rel_label(self.classes[yk]["display"]), "source": self.source(page, s)})
                    else:
                        label = " ".join(words).replace("_", " ")
                        if nkey(label) in self.classes:
                            continue
                        datas.append({"name": camel(label), "domain": self.classes[xk]["display"], "range": _datatype(label),
                                      "label": label, "source": self.source(page, s)})
            for m in rel_re.finditer(p):
                xk, yk = self.resolve(m.group("x")), self.resolve(m.group("y"))
                if xk and yk and xk != yk:
                    v = m.group("v").lower()
                    objs.append({"name": camel(v) + pascal(self.classes[yk]["display"]), "domain": self.classes[xk]["display"], "range": self.classes[yk]["display"],
                                 "label": f"{v} {self.classes[yk]['display'].lower()}", "source": self.source(page, s)})
        return objs, datas

    def _rel_label(self, rng: str) -> str:
        return ("has " if self.lang == "en" else "possède ") + rng.lower()


def extract(segs: Segments) -> dict[str, Any]:
    """Segments (page, texte) → brouillon au format de l'assistant, chaque élément avec ``source`` {page, excerpt}."""
    f = _Finder(segs)
    f.find_multiwords()
    f.capitalised_terms()
    # les classes citées comme parent via « est un » doivent exister avant les motifs
    objs, datas = f.patterns()
    lab = "label_en" if f.lang == "en" else "label_fr"
    classes = []
    for k, c in f.classes.items():
        item = {"name": pascal(c["display"]), lab: c["display"], "source": c["source"]}
        if c.get("parent"):
            item["parent"] = pascal(c["parent"])
        classes.append(item)
    seen: set[tuple[str, str]] = set()
    names = {pascal(c["display"]) for c in f.classes.values()}
    objects, datatypes = [], []
    used: set[str] = set()
    for o in objs:
        if (o["name"], o["domain"]) in seen:
            continue
        seen.add((o["name"], o["domain"]))
        objects.append({"name": o["name"], lab: o["label"], "domain": pascal(o["domain"]), "range": pascal(o["range"]), "source": o["source"]})
    for d in datas:
        nm = d["name"]
        if not nm or (nm, d["domain"]) in seen:
            continue
        seen.add((nm, d["domain"]))
        if nm in used:  # nom déjà pris par une autre classe : préfixé par la classe pour rester unique
            nm = camel(d["domain"] + " " + d["label"])
            if nm in used:
                continue
        used.add(nm)
        datatypes.append({"name": nm, lab: d["label"], "domain": pascal(d["domain"]), "range": d["range"], "source": d["source"]})
    # un parent cité mais jamais déclaré comme classe : déclaré avec la phrase de l'enfant
    for c in list(classes):
        par = c.get("parent")
        if par and par not in names:
            names.add(par)
            classes.append({"name": par, lab: re.sub(r"(?<!^)([A-Z])", r" \1", par).strip(), "source": c["source"]})
    return {"classes": classes, "object_properties": objects, "datatype_properties": datatypes, "lang": f.lang,
            "explanation": "", "warnings": []}


# ----------------------------------------------------------------------------- questions de compétence
def doc_questions(segs: Segments, limit: int = 10) -> list[str]:
    out: list[str] = []
    for _, text in segs:
        for line in text.splitlines():
            for s in re.findall(r"[^.?!\n]*\?", line):
                q = re.sub(r"^[\s\-–•*\d.)]+", "", s).strip()
                if 12 <= len(q) <= 220 and q.lower() not in {x.lower() for x in out}:
                    out.append(q)
    return out[:limit]


def template_questions(draft: dict[str, Any], lang: str) -> list[str]:
    en = lang == "en"
    qs: list[str] = []
    lbl = lambda it: it.get("label_fr") or it.get("label_en") or it["name"]  # noqa: E731
    cl = {c["name"]: lbl(c) for c in draft.get("classes", [])}
    for c in draft.get("classes", []):
        if c.get("parent") and c["parent"] in cl:
            qs.append(f"Which kinds of “{cl[c['parent']]}” are distinguished?" if en else f"Quels types de « {cl[c['parent']]} » distingue-t-on ?")
            break
    for d in draft.get("datatype_properties", []):
        if d.get("domain") in cl:
            qs.append(f"What is recorded about “{lbl(d)}” for “{cl[d['domain']]}”?" if en else f"Que sait-on de « {lbl(d)} » pour « {cl[d['domain']]} » ?")
    for o in draft.get("object_properties", []):
        if o.get("domain") in cl and o.get("range") in cl:
            qs.append(f"How is “{cl[o['domain']]}” linked to “{cl[o['range']]}”?" if en else f"Comment « {cl[o['domain']]} » est-il relié à « {cl[o['range']]} » ?")
    for c in draft.get("classes", []):
        qs.append(f"What must be known about “{lbl(c)}”?" if en else f"Que faut-il savoir sur « {lbl(c)} » ?")
    return qs


def questions(segs: Segments, lang: str) -> list[str]:
    """5 à 10 questions : celles du document d'abord, complétées par des modèles de questions tirés des termes extraits."""
    qs = doc_questions(segs)
    if len(qs) < 5:
        extra = template_questions(extract(segs), lang)
        # on alterne les formes (hiérarchie, attributs, relations) plutôt que d'enchaîner dix attributs
        for q in extra:
            if len(qs) >= 7:
                break
            if q not in qs:
                qs.append(q)
    return qs[:10]


def parse_marked(text: str) -> Segments:
    """Texte envoyé au LLM (paragraphes préfixés « [[p N]] ») → segments (page, texte)."""
    segs: Segments = []
    for m in re.finditer(r"\[\[p (\d+)\]\]\s*(.*?)(?=\n\n\[\[p \d+\]\]|\Z)", text, re.S):
        segs.append((int(m.group(1)), m.group(2).strip()))
    return segs
