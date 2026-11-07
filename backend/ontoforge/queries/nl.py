"""Question en langage naturel -> requête guidée modifiable (L15) — propriétaire : query.

1. Pré-analyse déterministe : mots de la question associés aux libellés (toutes langues), altLabel SKOS et noms locaux
   des classes / propriétés (racinisation simple, petit lexique FR->EN de repli).
2. Fournisseur LLM (si configuré et autre que `mock`) : schéma compact + indices -> JSON GuidedQuery.
3. Validation stricte du JSON contre l'ontologie (correction ou retrait d'étape, termes écartés dans `unmatched`).
4. Repli 100 % déterministe : meilleure correspondance de classes + plus courts chemins entre classes citées.
"""
from __future__ import annotations

import re
import unicodedata
from datetime import date
from typing import Any, Optional

from pydantic import ValidationError

from ..core.onto_model import RDFS, OntoModel, local_name
from ..core.shapes_model import ShapesModel
from .builder import LANGTAG, OWL2_DATATYPES, GuidedQuery, QFilter, Root, SelectItem, Step, Suggester, VAR_RE

SKOS_ALT = "http://www.w3.org/2004/02/skos/core#altLabel"
STOP = set("""le la les l un une des du de d et ou a au aux en dans sur par pour avec sans que qui quel quels quelle quelles ont est sont
eu ete avoir etre il elle ils ce cette ces ceux liste lister donne donner affiche afficher trouve trouver tous toutes tout plus moins
the of and or in on by for with without which what who whose are is were was has have had all list show give find me any each to at
from after before since between pas ne n y se s qu apres avant depuis entre jusqu cherche chercher voir quelles ayant ayant""".split())
MONTHS = {m: i + 1 for i, ms in enumerate([
    "janvier january", "fevrier february", "mars march", "avril april", "mai may", "juin june", "juillet july",
    "aout august", "septembre september", "octobre october", "novembre november", "decembre december"]) for m in ms.split()}
FR_EN = {"vehicule": "vehicle", "voiture": "vehicle", "technicien": "technician", "mecanicien": "technician", "reparation": "repair",
         "ordre": "order", "client": "customer", "moteur": "engine", "piece": "part", "marque": "brand", "modele": "model",
         "ouvert": "open", "ferme": "close", "immatriculation": "registration", "kilometrage": "mileage", "rappel": "recall",
         "garantie": "warranty", "entretien": "maintenance", "carburant": "fuel", "proprietaire": "owner", "atelier": "garage",
         "annee": "year", "prix": "price", "puissance": "power", "nom": "name", "releve": "reading", "personne": "person",
         "organisation": "organization", "duree": "duration", "intervention": "service", "defaut": "trouble"}
NAMEISH = re.compile(r"(display|name|label|title|designation|nom|libelle)", re.I)


def _norm(s: str) -> str:
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()


def _en_stem(w: str) -> str:
    if len(w) > 4 and w.endswith("ies"):
        return w[:-3] + "y"
    for suf in ("ing", "ed", "es"):
        if len(w) > len(suf) + 3 and w.endswith(suf):
            return w[: -len(suf)]
    return w


def stem(word: str) -> str:
    w = _norm(word)
    if len(w) > 3 and w[-1] in "sx":
        w = w[:-1]
    w = FR_EN.get(w, w)
    return _en_stem(w)


def _words(text: str) -> list[str]:
    parts = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", text)
    return [w for w in re.findall(r"[A-Za-zÀ-ÿ0-9]+", parts)]


def _term_stems(term: str) -> frozenset[str]:
    return frozenset(s for s in (stem(w) for w in _words(term)) if s and _norm(s) not in STOP and len(s) > 1)


class Hit:
    def __init__(self, iri: str, kind: str, score: float, pos: list[int], term: str):
        self.iri, self.kind, self.score, self.pos, self.term = iri, kind, score, pos, term

    @property
    def first(self) -> int:
        return min(self.pos)


def _terms(onto: OntoModel) -> list[tuple[str, str, str]]:
    out: list[tuple[str, str, str]] = []
    for kind, coll in (("class", onto.classes), ("object", onto.object_properties), ("data", onto.datatype_properties)):
        for iri, e in coll.items():
            ts = {local_name(iri), *e.labels.values()}
            ts |= {a.value for a in e.annotations if a.property == SKOS_ALT}
            out += [(iri, kind, t) for t in ts if t]
    return out


def preanalyse(question: str, onto: OntoModel) -> tuple[list[Hit], list[str], list[str]]:
    """Renvoie (correspondances, tokens, étapes de racinisation par token)."""
    toks = re.findall(r"[A-Za-zÀ-ÿ0-9][A-Za-zÀ-ÿ0-9'’\-]*", question)
    toks = [t for tok in toks for t in re.split(r"['’]", tok) if t]
    st = [stem(t) for t in toks]
    cands: list[Hit] = []
    for iri, kind, term in _terms(onto):
        ts = _term_stems(term)
        if not ts:
            continue
        pos = [i for i, s in enumerate(st) if s in ts and _norm(toks[i]) not in STOP]
        covered = {st[i] for i in pos}
        score = len(covered) / len(ts)
        if score >= 0.5 and pos and max(pos) - min(pos) <= 4:
            cands.append(Hit(iri, "data" if kind == "data" else ("object" if kind == "object" else "class"),
                             score + (0.01 if term == local_name(iri) else 0), pos, term))
    cands.sort(key=lambda h: (-round(h.score, 2), len(_term_stems(h.term)), h.iri))
    used = {"class": set(), "prop": set()}
    hits: list[Hit] = []
    for h in cands:
        g = "class" if h.kind == "class" else "prop"
        if any(p in used[g] for p in h.pos) or any(x.iri == h.iri for x in hits):
            continue
        used[g].update(h.pos)
        hits.append(h)
    hits.sort(key=lambda h: h.first)
    return hits, toks, st


# ------------------------------------------------------------------------------------ valeurs, dates

def _dates(q: str) -> tuple[list[dict[str, Any]], list[tuple[int, int]]]:
    """Intervalles de dates cités : [{lo, hi}] + spans de texte consommés."""
    out, spans = [], []
    n = _norm(q)
    yr = date.today().year
    mon = "|".join(MONTHS)
    pat = rf"(?:(apres|depuis|after|since|avant|before|jusqu'au|jusqu'a|until)\s+)?(?:le\s+|the\s+)?(\d{{1,2}})(?:er|e|st|nd|rd|th)?\s+({mon})(?:\s+(\d{{4}}))?"
    for m in re.finditer(pat, n):
        op = m.group(1) or ""
        d = f"{int(m.group(4) or yr):04d}-{MONTHS[m.group(3)]:02d}-{int(m.group(2)):02d}"
        item = {"hi": d} if op in ("avant", "before", "jusqu'au", "jusqu'a", "until") else {"lo": d}
        if not op:
            item = {"lo": d, "hi": d}
        item["assumed_year"] = not m.group(4)
        out.append(item)
        spans.append(m.span())
    for m in re.finditer(r"(apres|after|since|depuis|avant|before)?\s*(\d{4})-(\d{2})-(\d{2})", n):
        d = "-".join(m.group(2, 3, 4))
        out.append({"hi": d} if m.group(1) in ("avant", "before") else {"lo": d})
        spans.append(m.span())
    for m in re.finditer(r"\b(?:en|in|durant|during)\s+((?:19|20)\d{2})\b", n):
        out.append({"lo": f"{m.group(1)}-01-01", "hi": f"{m.group(1)}-12-31"})
        spans.append(m.span())
    return out, spans


def _values(question: str, hits: list[Hit], toks: list[str], date_words: set[str]) -> list[tuple[str, int]]:
    """Valeurs littérales : texte entre guillemets, ou mots capitalisés non reconnus (hors début de phrase)."""
    vals: list[tuple[str, int]] = [(m.group(1) or m.group(2), m.start()) for m in re.finditer(r"\"([^\"]+)\"|«\s*([^»]+?)\s*»", question)]
    taken = {p for h in hits for p in h.pos}
    cur: list[int] = []
    for i, t in enumerate(toks + [""]):
        ok = bool(t) and i > 0 and t[0].isupper() and i not in taken and _norm(t) not in STOP and _norm(t) not in date_words \
            and not t.isdigit()
        if ok:
            cur.append(i)
        elif cur:
            vals.append((" ".join(toks[j] for j in cur), cur[0]))
            cur = []
    return vals


# ------------------------------------------------------------------------------------- déterministe

class _Graph:
    def __init__(self, sg: Suggester):
        self.sg, self._c = sg, {}

    def neighbours(self, c: str) -> list[tuple[str, str, bool]]:
        if c not in self._c:
            d = self.sg.for_class(c)
            out: list[tuple[str, str, bool]] = []
            for e in (*d["outgoing"], *d["incoming"]):
                if not e["targets_restricted"]:
                    continue
                for t in e["targets"]:
                    if t["direct"]:
                        out.append((e["iri"], t["iri"], e["inverse"]))
            self._c[c] = out
        return self._c[c]


def _var_for(name: str, taken: set[str]) -> str:
    base = re.sub(r"[^A-Za-z0-9_]", "", local_name(name))[:20] or "x"
    base = base[0].lower() + base[1:]
    if not VAR_RE.match(base):
        base = "x"
    cand, i = base, 2
    while cand in taken:
        cand, i = f"{base}{i}", i + 1
    taken.add(cand)
    return cand


def _name_prop(sg: Suggester, c: str, prefer: Optional[str] = None) -> Optional[str]:
    props = [d for d in sg.for_class(c)["data_properties"] if d["value_kind"] == "text"]
    if prefer and any(d["iri"] == prefer for d in props):
        return prefer
    for d in props:
        if not d.get("synthetic") and NAMEISH.search(local_name(d["iri"])):
            return d["iri"]
    return next((d["iri"] for d in props if not d.get("synthetic")), RDFS + "label")


MSG = {
    "fr": {"no_class": "Aucune classe de l'ontologie reconnue dans la question ; choisissez la classe de départ à la main.",
           "start": "Classe de départ : « {c} ».", "no_path": "Aucun chemin trouvé vers « {c} » : terme laissé de côté.",
           "step": "{neg}{c} via « {p} »{inv}.", "neg": "Sans ", "inv": " (sens inverse)", "col": "Colonne « {p} » ajoutée.",
           "dates": "Filtre de dates sur « {p} » ({lo} → {hi})", "year": ", année {y} supposée",
           "text": "« {t} » recherché dans « {p} » de {c} (aucune propriété plus précise reconnue).",
           "no_llm": "[sans LLM : analyse déterministe] ", "llm_down": "[LLM indisponible ({e}) : analyse déterministe] ",
           "llm_bad": "[réponse du LLM invalide : analyse déterministe] "},
    "en": {"no_class": "No ontology class was recognised in the question; pick the starting class by hand.",
           "start": "Starting class: “{c}”.", "no_path": "No path found to “{c}”: term set aside.",
           "step": "{neg}{c} via “{p}”{inv}.", "neg": "Without ", "inv": " (reverse direction)", "col": "Column “{p}” added.",
           "dates": "Date filter on “{p}” ({lo} → {hi})", "year": ", year {y} assumed",
           "text": "“{t}” searched in “{p}” of {c} (no more specific property recognised).",
           "no_llm": "[no LLM: deterministic analysis] ", "llm_down": "[LLM unavailable ({e}): deterministic analysis] ",
           "llm_bad": "[invalid LLM response: deterministic analysis] "},
}


def deterministic(question: str, onto: OntoModel, shapes: Optional[ShapesModel], lang: str = "fr", msg_lang: Optional[str] = None) -> dict[str, Any]:
    M = MSG["en" if (msg_lang or lang) == "en" else "fr"]
    sg = Suggester(onto, shapes, lang)
    g = _Graph(sg)
    hits, toks, st = preanalyse(question, onto)
    classes = [h for h in hits if h.kind == "class"]
    dprops = [h for h in hits if h.kind == "data"]
    unmatched: list[str] = []
    notes: list[str] = []
    dates, dspans = _dates(question)
    date_words = {w for w in _norm(question).replace("-", " ").split() if w in MONTHS or re.fullmatch(r"\d+(er|e)?", w)}
    if not classes:
        words = [t for t in toks if _norm(t) not in STOP and not t.isdigit()]
        return {"guided": GuidedQuery(root=Root(var="x")).model_dump(mode="json"), "explanation":
                M["no_class"],
                "confidence": 0.0, "unmatched": words, "mode": "deterministic"}
    taken: set[str] = set()
    root_c = classes[0].iri
    root = Root(var=_var_for(root_c, taken), class_iri=root_c)
    placed: list[tuple[str, str]] = [(root.var, root_c)]  # (var, class)
    cls_var = {root_c: root.var}
    steps: list[Step] = []
    why = [M["start"].format(c=sg.label(root_c))]
    for h in classes[1:]:
        target = h.iri
        if any(target == c or target in sg.down(c) for _, c in placed):
            continue
        path = _shortest(g, sg, [c for _, c in placed], target)
        if path is None:
            unmatched.append(toks[h.first])
            why.append(M["no_path"].format(c=sg.label(target)))
            continue
        start_c, hops = path
        cur_var = next(v for v, c in placed if c == start_c)
        for prop, to_c, inv in hops:
            v = _var_for(to_c, taken)
            neg = h.first > 0 and _norm(toks[h.first - 1]) in ("sans", "without", "aucun", "aucune") and to_c == target
            steps.append(Step(from_var=cur_var, property_iri=prop, inverse=inv, to_var=v, to_class_iri=to_c, negated=neg))
            placed.append((v, to_c))
            cls_var.setdefault(to_c, v)
            cur_var = v
            why.append(M["step"].format(neg=M["neg"] if neg else "", c=sg.label(to_c), p=sg.label(prop), inv=M["inv"] if inv else ""))
    filters: list[QFilter] = []
    select: list[SelectItem] = []
    def var_of_class(c: str) -> Optional[str]:
        return next((v for v, cc in placed if cc == c or c in sg.down(cc)), None)
    for h in dprops:  # propriétés de données citées -> colonnes
        for v, c in placed:
            if sg.applies(h.iri, c, "out") is not False:
                select.append(SelectItem(var=v, property_iri=h.iri))
                why.append(M["col"].format(p=sg.label(h.iri)))
                break
        else:
            unmatched.append(toks[h.first])
    for d in dates:
        pick = None
        for h in dprops:
            if sg.value_kind(next(iter(onto.datatype_properties[h.iri].range), ""), None) == "date":
                pick = h.iri
                break
        var = None
        for v, c in placed:
            dl = [x for x in sg.for_class(c)["data_properties"] if x["value_kind"] == "date"]
            if pick and any(x["iri"] == pick for x in dl) or (not pick and dl):
                var, pick = v, pick or dl[0]["iri"]
                break
        if not var:
            unmatched.append("date")
            continue
        filters.append(QFilter(var=var, kind="date_range", property_iri=pick, value=d.get("lo"), value2=d.get("hi")))
        why.append(M["dates"].format(p=sg.label(pick), lo=d.get("lo", "…"), hi=d.get("hi", "…"))
                   + (M["year"].format(y=date.today().year) if d.get("assumed_year") else "") + ".")
    for text, pos in _values(question, hits, toks, date_words):
        near = [h for h in classes if h.first < pos] or classes
        c = (near[-1] if near else classes[0]).iri
        var = var_of_class(c) or root.var
        prop = _name_prop(sg, next((cc for v, cc in placed if v == var), root_c), dprops[0].iri if dprops else None)
        filters.append(QFilter(var=var, kind="text_contains", property_iri=prop, value=text))
        why.append(M["text"].format(t=text, p=sg.label(prop), c=sg.label(c)))
    consumed = {p for h in hits for p in h.pos}
    for i, t in enumerate(toks):
        if i in consumed or _norm(t) in STOP or t.isdigit() or _norm(t) in date_words or any(t == v for v, _ in _values(question, hits, toks, date_words) for t in v.split()):
            continue
        unmatched.append(t)
    unmatched = list(dict.fromkeys(unmatched))
    content = [t for t in toks if _norm(t) not in STOP and not t.isdigit() and _norm(t) not in date_words]
    conf = round(max(0.05, min(0.95, 1 - len(unmatched) / max(1, len(content)))) * (0.9 if len(classes) == 1 and not filters else 1.0), 2)
    if select:  # les colonnes demandées s'ajoutent aux entités, elles ne les remplacent pas
        select = [SelectItem(var=v) for v, _ in placed if v not in {s_.to_var for s_ in steps if s_.negated}] + select
    gq = GuidedQuery(root=root, steps=steps, filters=filters, select=select, label_lang=None)
    return {"guided": gq.model_dump(mode="json"), "explanation": " ".join(why), "confidence": conf,
            "unmatched": unmatched, "mode": "deterministic"}


def _shortest(g: _Graph, sg: Suggester, sources: list[str], target: str, max_len: int = 4):
    """BFS multi-sources : (classe de départ, [(propriété, classe atteinte, inverse)]) ou None."""
    goal = sg.down(target)
    frontier = [(s, s, []) for s in sources]
    seen = set(sources)
    for _ in range(max_len):
        nxt = []
        for start, c, hops in frontier:
            for prop, to_c, inv in sorted(g.neighbours(c), key=lambda e: (e[2], e[0], e[1])):
                if to_c in seen:
                    continue
                seen.add(to_c)
                h2 = [*hops, (prop, to_c, inv)]
                if to_c in goal:
                    return start, h2
                nxt.append((start, to_c, h2))
        frontier = nxt
    return None


# ------------------------------------------------------------------------------------------ LLM

SYSTEM = """[TASK:nl] Tu traduis une question en langage naturel en requête guidée JSON pour une ontologie OWL.
Réponds UNIQUEMENT par un objet JSON {"guided": {...}, "explanation": "..."} (sans texte autour, explication en français).
Format de "guided" : {"root":{"var","class_iri"},"steps":[{"from_var","property_iri","inverse":bool,"to_var","to_class_iri","optional":bool,"negated":bool}],
"filters":[{"var","kind":"text_contains|equals|regex|lang|number_range|date_range|in_values","property_iri","value","value2","values":[]}],
"select":[{"var","property_iri","label":bool}],"order_by":[{"var","property_iri","desc":bool}],"limit":100}.
Règles : n'utilise QUE les classes et propriétés du schéma, nommées exactement comme dans le schéma (nom local) ; "inverse":true si la
relation va de to_var vers from_var ; chaque from_var doit être défini avant ; les noms de variables sont [A-Za-z][A-Za-z0-9_]* ;
pour une date, utilise date_range avec value (min) et value2 (max) au format ISO ; ne devine pas : omets ce qui n'est pas dans le schéma."""


def schema_digest(onto: OntoModel, lang: str = "fr") -> tuple[str, dict[str, str]]:
    lookup: dict[str, str] = {}
    lines = ["CLASSES"]
    for iri, c in sorted(onto.classes.items()):
        lookup[local_name(iri)] = iri
        par = ",".join(local_name(p) for p in c.sub_class_of)
        lines.append(f"- {local_name(iri)} (« {onto.label(iri, lang)} »){' < ' + par if par else ''}")
    lines.append("RELATIONS (domaine -> portée)")
    for iri, p in sorted(onto.object_properties.items()):
        lookup[local_name(iri)] = iri
        d = ",".join(local_name(x) for x in [*p.domain, *p.domain_union]) or "?"
        r = ",".join(local_name(x) for x in [*p.range, *p.range_union]) or "?"
        lines.append(f"- {local_name(iri)} (« {onto.label(iri, lang)} ») : {d} -> {r}")
    lines.append("PROPRIÉTÉS DE DONNÉES (domaine : type)")
    for iri, p in sorted(onto.datatype_properties.items()):
        lookup[local_name(iri)] = iri
        d = ",".join(local_name(x) for x in [*p.domain, *p.domain_union]) or "?"
        lines.append(f"- {local_name(iri)} (« {onto.label(iri, lang)} ») : {d} : {local_name(p.range[0]) if p.range else 'string'}")
    return "\n".join(lines), lookup


def _bad_filter(f: dict, onto: OntoModel) -> Optional[tuple[str, str]]:
    """(raison, terme) si le filtre du LLM n'est pas sûr : valeur non scalaire, IRI inconnue de l'ontologie, langue ou datatype invalides."""
    vals = [f.get("value"), f.get("value2"), *(f.get("values") or [])]
    if any(isinstance(x, (dict, list)) for x in vals) or not isinstance(f.get("values") or [], list):
        return "valeur non scalaire", "valeur"
    if f.get("is_iri"):
        known = {*onto.individuals, *onto.classes, *onto.object_properties}
        for x in vals:
            if x not in (None, "") and (not isinstance(x, str) or x not in known):
                return f"IRI « {str(x)[:50]} » inconnue de l'ontologie", str(x)[:50]
    lang = f.get("lang")
    if lang not in (None, "") and not (isinstance(lang, str) and (LANGTAG.match(lang) or (f.get("kind") == "lang" and lang == "*"))):
        return f"étiquette de langue invalide « {str(lang)[:20]} »", str(lang)[:20]
    dt = f.get("datatype")
    if dt not in (None, "") and not (isinstance(dt, str) and (dt in OWL2_DATATYPES or dt in onto.datatypes)):
        return f"datatype « {str(dt)[:50]} » hors de la carte OWL 2", str(dt)[:50]
    return None


def sanitize(data: Any, onto: OntoModel, shapes: Optional[ShapesModel], lookup: dict[str, str]) -> tuple[Optional[GuidedQuery], list[str], list[str]]:
    """Validation stricte : corrige (sens, classe cible) ou retire (étape + dépendances). -> (requête, unmatched, notes)."""
    unmatched: list[str] = []
    notes: list[str] = []
    if not isinstance(data, dict) or not isinstance(data.get("root"), dict):
        return None, [], ["JSON sans racine exploitable."]

    def iri(x: Any) -> Optional[str]:
        if not isinstance(x, str) or not x:
            return None
        return lookup.get(x, x)

    d = dict(data)
    for k in ("steps", "filters", "select", "order_by"):
        d[k] = [dict(i) for i in (d.get(k) or []) if isinstance(i, dict)]
    d["root"]["class_iri"] = iri(d["root"].get("class_iri"))
    root_c = d["root"]["class_iri"]
    if root_c and root_c not in onto.classes:
        unmatched.append(local_name(root_c))
        d["root"]["class_iri"] = root_c = None
    sg = Suggester(onto, shapes)
    cls = {d["root"].get("var"): root_c}
    good: list[dict] = []
    for s in d["steps"]:
        s["property_iri"] = iri(s.get("property_iri"))
        s["to_class_iri"] = iri(s.get("to_class_iri"))
        p, fv = s["property_iri"], s.get("from_var")
        if p not in onto.object_properties or fv not in cls:
            unmatched.append(local_name(p or "?"))
            notes.append(f"Étape retirée : relation « {local_name(p or '?')} » inconnue ou variable de départ absente.")
            continue
        src = cls[fv]
        if src:
            ok = sg.applies(p, src, "in" if s.get("inverse") else "out")
            if ok is False:
                flip = sg.applies(p, src, "out" if s.get("inverse") else "in")
                if flip is not False:
                    s["inverse"] = not s.get("inverse")
                    notes.append(f"Sens de « {local_name(p)} » corrigé.")
                else:
                    unmatched.append(local_name(p))
                    notes.append(f"Étape retirée : « {local_name(p)} » n'est pas applicable à « {local_name(src)} ».")
                    continue
            tc = s["to_class_iri"]
            if tc:
                t = sg.target_classes(p, src, inverse=bool(s.get("inverse")))
                if tc not in onto.classes or (t["restricted"] and tc not in {x["iri"] for x in t["targets"]}):
                    notes.append(f"Classe cible « {local_name(tc)} » invalide pour « {local_name(p)} » : retirée.")
                    unmatched.append(local_name(tc))
                    s["to_class_iri"] = None
        cls[s.get("to_var")] = s["to_class_iri"]
        good.append(s)
    d["steps"] = good
    known = set(cls)
    flt = []
    for f in d["filters"]:
        f["property_iri"] = iri(f.get("property_iri"))
        pr = f["property_iri"]
        if f.get("var") not in known or (pr and pr not in onto.datatype_properties and pr != RDFS + "label"):
            unmatched.append(local_name(pr or str(f.get("var"))))
            notes.append(f"Filtre retiré : propriété « {local_name(pr or '?')} » ou variable inconnue.")
            continue
        bad = _bad_filter(f, onto)
        if bad:
            unmatched.append(bad[1])
            notes.append(f"Filtre retiré : {bad[0]}.")
            continue
        flt.append(f)
    d["filters"] = flt
    for key in ("select", "order_by"):
        keep = []
        for it in d[key]:
            it["property_iri"] = iri(it.get("property_iri"))
            pr = it["property_iri"]
            if it.get("var") not in known or (pr and pr not in onto.datatype_properties):
                unmatched.append(local_name(pr or str(it.get("var"))))
                continue
            keep.append(it)
        d[key] = keep
    d["limit"] = d.get("limit") if isinstance(d.get("limit"), int) and 1 <= d["limit"] <= 10000 else 100
    try:
        return GuidedQuery.model_validate(d), list(dict.fromkeys(unmatched)), notes
    except ValidationError as exc:
        return None, unmatched, [f"JSON non conforme au modèle de requête guidée : {exc.errors()[0]['msg']}"]


def interpret(question: str, onto: OntoModel, shapes: Optional[ShapesModel], provider: Any = None, lang: str = "fr",
              msg_lang: Optional[str] = None) -> dict[str, Any]:
    """Point d'entrée : LLM + validation si un fournisseur réel est configuré, sinon (ou en cas d'échec) repli déterministe.

    ``lang`` : langue des libellés ; ``msg_lang`` : langue de l'explication (par défaut ``lang``)."""
    M = MSG["en" if (msg_lang or lang) == "en" else "fr"]
    base = deterministic(question, onto, shapes, lang, msg_lang)
    base["provider"] = getattr(provider, "name", None)
    if provider is None or getattr(provider, "name", "mock") == "mock" or not getattr(provider, "configured", False):
        base["explanation"] = (M["no_llm"] if provider is not None else "") + base["explanation"]
        return base
    from ..assistant.service import _ask_json
    from ..assistant.providers import LLMError
    digest, lookup = schema_digest(onto, lang)
    hints = "; ".join(f"« {h.term} » -> {local_name(h.iri)}" for h in preanalyse(question, onto)[0])
    user = ("LANGUAGE: write the explanation in English.\n" if (msg_lang or lang) == "en" else "") + f"SCHÉMA\n{digest}\n\nINDICES (pré-analyse, non contraignants) : {hints or 'aucun'}\n\nQUESTION : {question}"
    try:
        out = _ask_json(provider, SYSTEM, user, 3000)
    except (LLMError, Exception) as exc:  # noqa: BLE001 — repli, jamais d'échec dur
        base["explanation"] = M["llm_down"].format(e=type(exc).__name__) + base["explanation"]
        return base
    gq, unmatched, notes = sanitize(out.get("guided") if isinstance(out, dict) else None, onto, shapes, lookup)
    if gq is None:
        base["explanation"] = M["llm_bad"] + " ".join(notes) + " " + base["explanation"]
        return base
    expl = str(out.get("explanation") or "") + (" " + " ".join(notes) if notes else "")
    n_terms = max(1, len(preanalyse(question, onto)[0]))
    conf = round(max(0.1, min(0.95, 0.9 - 0.15 * len(unmatched) - 0.05 * len(notes))), 2)
    return {"guided": gq.model_dump(mode="json"), "explanation": expl.strip(), "confidence": conf,
            "unmatched": unmatched, "mode": "llm", "provider": provider.name, "n_hints": n_terms}
