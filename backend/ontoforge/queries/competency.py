"""Questions de compétence générées depuis un PGModel — propriétaire : query.

`competency_questions(pg, onto=None)` -> 5 à 10 `CompetencyQuestion` (question métier, SPARQL, Cypher, Curiosity).
Les requêtes cible sont obtenues en traduisant le SPARQL avec `translate` : si la traduction est lossy, la question
l'indique (`lossy`, `notes`) — c'est précisément ce que la question de compétence doit révéler.
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from ..core.onto_model import OntoModel
from ..core.pg_model import EdgeType, NodeType, PGModel, PGProperty
from .translate import translate

MAX_QUESTIONS = 10
TEMPLATES = {
    "fr": {"list": "Quels sont les {nt} et leur {lp} ?", "relation": "Quels {a} sont liés à quels {b} par {e} (avec leurs libellés) ?",
           "count": "Combien de {a} sont liés à chaque {b} (relation {e}) ?", "optional": "Quels {a} existent, avec leur {e} s'il y en a un ?",
           "transitive": "Quels {a} sont, directement ou indirectement, reliés par {e} ?", "filter": "Quels {nt} ont {num} supérieur à 0 ?",
           "subclass": "Quelles instances sont de la sous-classe {sub} (héritage aplati en {nt}) ?",
           "path": "Quels {a} atteignent un {c} via {e1} puis {e2} ?"},
    "en": {"list": "What are the {nt} and their {lp}?", "relation": "Which {a} are linked to which {b} through {e} (with their labels)?",
           "count": "How many {a} are linked to each {b} ({e} relationship)?", "optional": "Which {a} exist, with their {e} if there is one?",
           "transitive": "Which {a} are linked, directly or indirectly, through {e}?", "filter": "Which {nt} have {num} greater than 0?",
           "subclass": "Which instances belong to the subclass {sub} (flattened into {nt})?",
           "path": "Which {a} reach a {c} via {e1} then {e2}?"},
}
_NAMEISH = ("name", "label", "title", "designation", "description")
_NUMERIC = ("Integer", "Float", "Long", "Double", "Decimal")


class CompetencyQuestion(BaseModel):
    id: str
    question: str
    sparql: str
    cypher: Optional[str] = None
    curiosity: Optional[str] = None
    lossy: bool = False
    notes: list[str] = Field(default_factory=list)
    pattern: str = ""  # list | relation | count | optional | transitive | filter


def _nt_iri(nt: NodeType) -> Optional[str]:
    return nt.source[0] if nt.source else None


def _prop_iri(p: PGProperty) -> Optional[str]:
    return p.source if p.source and p.source.startswith(("http://", "https://", "urn:")) else None


def _label_prop(nt: NodeType) -> Optional[PGProperty]:
    cands = [p for p in nt.properties if _prop_iri(p) and not p.is_list]
    for p in cands:
        if any(w in p.name.lower() for w in _NAMEISH) and p.type == "String":
            return p
    for k in nt.key:
        for p in cands:
            if p.name == k:
                return p
    return cands[0] if cands else None


def _score(pg: PGModel, nt: NodeType) -> int:
    return sum(1 for e in pg.edge_types if nt.name in (e.from_, e.to))


def competency_questions(pg: PGModel, onto: Optional[OntoModel] = None, lang: str = "fr") -> list[CompetencyQuestion]:
    """5 à 10 questions pertinentes (selon la structure du modèle) avec sparql + cypher + curiosity."""
    specs: list[tuple[str, str, str]] = []  # (pattern, question, sparql)
    T = TEMPLATES["en" if lang == "en" else "fr"]
    nts = {n.name: n for n in pg.node_types.values()} if isinstance(pg.node_types, dict) else {n.name: n for n in pg.node_types}
    edges = [e for e in pg.edge_types if e.source and e.from_ in nts and e.to in nts and _nt_iri(nts[e.from_]) and _nt_iri(nts[e.to])]
    hubs = sorted((n for n in nts.values() if _nt_iri(n)), key=lambda n: -_score(pg, n))

    # 1. liste d'un type central avec son libellé
    for nt in hubs[:1]:
        lp = _label_prop(nt)
        if lp:
            specs.append(("list", T["list"].format(nt=nt.name, lp=lp.name),
                          f"SELECT ?x ?l WHERE {{ ?x a <{_nt_iri(nt)}> ; <{_prop_iri(lp)}> ?l . }} ORDER BY ?l LIMIT 50"))
    # 2. relations simples entre types distincts (ordre d'importance)
    used: set[str] = set()
    simple = [e for e in edges if e.from_ != e.to and not e.derived]
    simple.sort(key=lambda e: -(_score(pg, nts[e.from_]) + _score(pg, nts[e.to])))
    for e in simple:
        a, b = nts[e.from_], nts[e.to]
        la, lb = _label_prop(a), _label_prop(b)
        if not (la and lb) or e.name in used:
            continue
        used.add(e.name)
        specs.append(("relation", T["relation"].format(a=a.name, b=b.name, e=e.name),
                      f"SELECT ?a ?la ?b ?lb WHERE {{ ?a a <{_nt_iri(a)}> ; <{_prop_iri(la)}> ?la ; <{e.source}> ?b . "
                      f"?b <{_prop_iri(lb)}> ?lb . }} LIMIT 50"))
        if len([s for s in specs if s[0] == "relation"]) >= 3:
            break
    # 3. comptage par destination
    for e in simple[:6]:
        a, b = nts[e.from_], nts[e.to]
        if e.name in used and any(s[0] == "count" for s in specs):
            continue
        specs.append(("count", T["count"].format(a=a.name, b=b.name, e=e.name),
                      f"SELECT ?b (COUNT(?a) AS ?n) WHERE {{ ?a <{e.source}> ?b . ?b a <{_nt_iri(b)}> . }} "
                      f"GROUP BY ?b ORDER BY DESC(?n) LIMIT 10"))
        break
    # 4. OPTIONAL : un nœud avec relation optionnelle
    for e in simple:
        if e.cardinality.out and e.cardinality.out.startswith("0"):
            a = nts[e.from_]
            specs.append(("optional", T["optional"].format(a=a.name, e=e.name),
                          f"SELECT ?a ?b WHERE {{ ?a a <{_nt_iri(a)}> . OPTIONAL {{ ?a <{e.source}> ?b }} }} LIMIT 50"))
            break
    # 5. transitive / auto-relation
    for e in edges:
        if e.from_ == e.to and not e.symmetric:
            a = nts[e.from_]
            specs.append(("transitive", T["transitive"].format(a=a.name, e=e.name),
                          f"SELECT ?x ?y WHERE {{ ?x <{e.source}>+ ?y . }} LIMIT 50"))
            break
    # 6. FILTER numérique ou énumération
    for nt in hubs:
        num = next((p for p in nt.properties if _prop_iri(p) and p.type in _NUMERIC and not p.is_list), None)
        if num:
            specs.append(("filter", T["filter"].format(nt=nt.name, num=num.name),
                          f"SELECT ?x ?v WHERE {{ ?x a <{_nt_iri(nt)}> ; <{_prop_iri(num)}> ?v . FILTER(?v > 0) }} LIMIT 50"))
            break
    # 7. héritage aplati : question par sous-type (discriminant)
    for nt in hubs:
        if nt.discriminator and len(nt.source) > 1:
            sub = nt.source[1]
            specs.append(("subclass", T["subclass"].format(sub=sub.rsplit('#', 1)[-1].rsplit('/', 1)[-1], nt=nt.name),
                          f"SELECT ?x WHERE {{ ?x a <{sub}> . }} LIMIT 50"))
            break
    # 8. chemin à deux sauts
    for e1 in simple:
        for e2 in simple:
            if e1 is not e2 and e1.to == e2.from_ and e1.from_ != e2.to:
                a, c = nts[e1.from_], nts[e2.to]
                specs.append(("path", T["path"].format(a=a.name, c=c.name, e1=e1.name, e2=e2.name),
                              f"SELECT DISTINCT ?a ?c WHERE {{ ?a <{e1.source}>/<{e2.source}> ?c . }} LIMIT 50"))
                break
        else:
            continue
        break
    # complément si < 5 : une liste par autre type
    for nt in hubs[1:]:
        if len(specs) >= 5:
            break
        lp = _label_prop(nt)
        if lp:
            specs.append(("list", T["list"].format(nt=nt.name, lp=lp.name),
                          f"SELECT ?x ?l WHERE {{ ?x a <{_nt_iri(nt)}> ; <{_prop_iri(lp)}> ?l . }} LIMIT 50"))

    out: list[CompetencyQuestion] = []
    for i, (pat, q, sp) in enumerate(specs[:MAX_QUESTIONS], 1):
        r = translate(sp, pg, onto)
        out.append(CompetencyQuestion(id=f"CQ{i:02d}", question=q, sparql=sp, cypher=r.cypher, curiosity=r.curiosity,
                                      lossy=r.lossy, notes=r.notes, pattern=pat))
    return out
