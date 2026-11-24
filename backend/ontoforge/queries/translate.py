"""Traduction SPARQL → Cypher / Curiosity Query API / GraphQL — propriétaire : query.

`translate(sparql, pg, onto=None) -> TranslationResult`

- Analyse : `rdflib.plugins.sparql.prepareQuery` → algèbre SPARQL.
- Mapping IRI → élément PG via les champs `source` du PGModel (NodeType.source, PGProperty.source, EdgeType.source),
  complété par l'ontologie si fournie (inverseOf, sous-propriétés, sous-classes, transitivité).
- Sous-ensemble traduit : BGP (rdf:type, propriétés objet / données), FILTER (comparaisons, booléens, regex,
  CONTAINS/STRSTARTS/STRENDS, IN, BOUND, EXISTS / NOT EXISTS, fonctions usuelles), OPTIONAL, MINUS, UNION (Cypher),
  BIND, ORDER BY / LIMIT / OFFSET / DISTINCT, COUNT/SUM/AVG/MIN/MAX/SAMPLE/GROUP_CONCAT + GROUP BY + HAVING,
  property paths `/`, `|`, `^`, `+`, `*`, `?`, ASK.
- Jamais d'exception : ce qui ne se traduit pas devient une note `[perte] …` (et `lossy=True`) ; les écarts de
  sémantique sans perte (inférence implicite, DISTINCT ajouté…) sont des notes `[info] …`.
La sortie Curiosity est du pseudo-code C# (Query API) marqué À VÉRIFIER.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Optional

from pydantic import BaseModel, Field
from rdflib import BNode, Literal, URIRef, Variable
from rdflib.namespace import OWL as _OWL, RDF as _RDF, RDFS as _RDFS, XSD as _XSD
from rdflib.paths import AlternativePath, InvPath, MulPath, NegatedPath, Path, SequencePath

from ..core.onto_model import OntoModel, local_name
from ..core.pg_model import EdgeType, NodeType, PGModel, PGProperty
from ..targets.graphql import camel, edge_cypher_type, list_field, lookup_field, pascal, relation_fields

RDF_TYPE = _RDF.type
SUBCLASS = _RDFS.subClassOf
CURIOSITY_DOC = "https://docs.curiosity.ai/workspace-build/apis-and-customization/custom-endpoints/graph-query-language"
VARLEN_DEPTH = 10  # profondeur par défaut de OutMany pour + / *


class TranslationResult(BaseModel):
    sparql: str
    query_form: Optional[str] = None  # select | ask | construct | describe
    cypher: Optional[str] = None
    curiosity: Optional[str] = None
    graphql: Optional[str] = None
    notes: list[str] = Field(default_factory=list)
    lossy: bool = False
    supported: bool = True  # False si la requête n'a pas pu être analysée / traduite du tout
    variables: list[str] = Field(default_factory=list)


# ==== index IRI → PG ================================================================================
@dataclass(frozen=True)
class ClassRef:
    node_type: str
    label: Optional[str]  # label Neo4j à poser (None si seulement le discriminant)
    disc_prop: Optional[str] = None
    disc_value: Optional[str] = None


@dataclass(frozen=True)
class EdgeRef:
    idx: int  # index dans pg.edge_types
    inverse: bool  # True : le prédicat SPARQL va de edge.to vers edge.from


class _Index:
    def __init__(self, pg: PGModel, onto: Optional[OntoModel]):
        self.pg, self.onto = pg, onto
        self.classes: dict[str, list[ClassRef]] = {}
        self.data: dict[str, list[tuple[str, PGProperty]]] = {}
        self.edge_data: dict[str, list[tuple[int, PGProperty]]] = {}
        self.edges: dict[str, list[EdgeRef]] = {}
        for nt in pg.node_types.values():
            label = nt.labels[0] if nt.labels else nt.name
            for i, src in enumerate(nt.source):
                if i == 0:
                    ref = ClassRef(nt.name, label)
                else:
                    ln = local_name(src)
                    if nt.discriminator and ln in nt.discriminator_values:
                        ref = ClassRef(nt.name, label, nt.discriminator, ln)
                    elif ln in nt.labels:
                        ref = ClassRef(nt.name, ln)
                    else:  # classe fusionnée (équivalence…) : même type
                        ref = ClassRef(nt.name, label)
                self.classes.setdefault(src, []).append(ref)
            # labels secondaires (multi-labels Neo4j) correspondant à une classe source d'un autre type
            for p in nt.properties:
                if p.source:
                    self.data.setdefault(p.source, []).append((nt.name, p))
        # multi-labels : la classe parente (labels[1:]) matche aussi les sous-types
        for nt in pg.node_types.values():
            for lab in nt.labels[1:]:
                for src, refs in list(self.classes.items()):
                    if any(r.label == lab and r.disc_prop is None for r in refs) and \
                            not any(r.node_type == nt.name for r in refs):
                        self.classes[src].append(ClassRef(nt.name, lab))
        for i, e in enumerate(pg.edge_types):
            if e.source:
                self.edges.setdefault(e.source, []).append(EdgeRef(i, False))
            for p in e.properties:
                if p.source:
                    self.edge_data.setdefault(p.source, []).append((i, p))
        if onto:
            for op in onto.object_properties.values():
                if op.inverse_of and op.inverse_of in self.edges and op.iri not in self.edges:
                    self.edges[op.iri] = [EdgeRef(r.idx, not r.inverse) for r in self.edges[op.inverse_of]]
                elif op.inverse_of and op.iri in self.edges and op.inverse_of not in self.edges:
                    self.edges[op.inverse_of] = [EdgeRef(r.idx, not r.inverse) for r in self.edges[op.iri]]

    def edge(self, r: EdgeRef) -> EdgeType:
        return self.pg.edge_types[r.idx]

    def id_prop(self, nt_name: Optional[str]) -> Optional[str]:
        nt = self.pg.node_types.get(nt_name or "")
        if not nt:
            return "uri"
        names = [p.name for p in nt.properties]
        if "uri" in names:
            return "uri"
        return nt.key[0] if nt.key else None

    def prop(self, nt_name: str, name: str) -> Optional[PGProperty]:
        nt = self.pg.node_types.get(nt_name)
        return next((p for p in nt.properties if p.name == name), None) if nt else None

    def sub_properties(self, iri: str) -> list[str]:
        if not self.onto:
            return []
        out, stack = [], [iri]
        while stack:
            cur = stack.pop()
            for op in self.onto.object_properties.values():
                if cur in op.sub_property_of and op.iri not in out:
                    out.append(op.iri)
                    stack.append(op.iri)
        return out

    def is_transitive(self, iri: str) -> bool:
        op = self.onto.object_properties.get(iri) if self.onto else None
        return bool(op and "transitive" in op.characteristics)


# ==== représentation intermédiaire ===================================================================
@dataclass
class NodeVar:
    name: str  # identifiant Cypher
    sparql: Optional[str] = None  # nom de variable SPARQL (None : constante / nœud anonyme)
    iri: Optional[str] = None  # IRI constante
    types: list[ClassRef] = field(default_factory=list)
    empty: bool = False  # contrainte de type insatisfiable / classe absente du PG : le motif ne doit rien renvoyer


@dataclass
class Rel:
    a: str
    b: str
    choices: list[EdgeRef]
    min: int = 1
    max: Optional[int] = 1  # None = non borné
    undirected: bool = False


@dataclass
class Block:
    optional: bool = False
    rels: list[Rel] = field(default_factory=list)
    nodes: list[str] = field(default_factory=list)  # nœuds introduits / utilisés dans le bloc
    conds: list[Any] = field(default_factory=list)  # expressions SPARQL (algèbre) ou str Cypher
    cy_conds: list[str] = field(default_factory=list)
    node_conds: dict[str, list[tuple[str, str, Any]]] = field(default_factory=dict)  # nœud → (prop, op, valeur)


class _Unsupported(Exception):
    pass


_CY_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_RESERVED = {"match", "where", "return", "with", "order", "by", "limit", "skip", "optional", "union", "and", "or",
             "not", "in", "is", "null", "true", "false", "count", "as", "case", "when", "end", "exists", "all"}


def _cy_ident(name: str) -> str:
    if _CY_IDENT.match(name) and name.lower() not in _RESERVED:
        return name
    return "`" + name.replace("`", "``") + "`"


def _cy_str(s: str) -> str:
    return "'" + s.replace("\\", "\\\\").replace("'", "\\'") + "'"


def _cs_str(s: str) -> str:
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


# ==== traducteur ====================================================================================
class _Translator:
    def __init__(self, pg: PGModel, onto: Optional[OntoModel]):
        self.pg, self.onto = pg, onto
        self.ix = _Index(pg, onto)
        self.notes: list[tuple[str, str]] = []
        self.nodes: dict[str, NodeVar] = {}
        self.prop_vars: dict[str, tuple[str, PGProperty]] = {}
        self.alias: dict[str, str] = {}  # var → expression Cypher (BIND, agrégats)
        self.blocks: list[Block] = []
        self.unbound: set[str] = set()
        self.has_varlen = False
        self._fresh = 0
        self.form = "select"
        self.curiosity_ok = True
        self.graphql_ok = True
        # sous-motif EXISTS / NOT EXISTS / MINUS en cours (L53, DF-B12) :
        # (nœuds extérieurs, typages capturés, "exists" | "minus", variables SPARQL liées à l'extérieur)
        self._sub_ctx: Optional[tuple[set, dict[str, list[list[ClassRef]]], str, set]] = None
        self._opt_keys: set = set()  # nœuds liés seulement par un OPTIONAL, pendant le rendu des FILTER tardifs (DF-B15)
        self._sub_vars: set = set()  # variables propres à un sous-motif (retirées après son rendu, DF-B18)
        self.select_star = False  # SELECT * : les variables propres à un sous-motif ne sont pas projetées (§18.2.1)
        self._sub_cs: dict[int, tuple[str, list[list[ClassRef]], bool]] = {}  # id(sous-motif) → filtre de type C#

    # ---- notes ----
    def note(self, level: str, text: str) -> None:
        if (level, text) not in self.notes:
            self.notes.append((level, text))

    def lost(self, text: str) -> None:
        self.note("perte", text)

    def info(self, text: str) -> None:
        self.note("info", text)

    def short(self, iri: str) -> str:
        return local_name(str(iri))

    # ---- nœuds ----
    def node_for(self, term, block: Block) -> str:
        if isinstance(term, Variable):
            key = str(term)
            if key in self.prop_vars:
                raise _Unsupported(f"?{key} est utilisée à la fois comme valeur de propriété et comme nœud")
            name = _cy_ident(key) if not key.startswith("_") else f"_v{len(self.nodes)}"
            if key not in self.nodes:
                self.nodes[key] = NodeVar(name=name, sparql=key)
        elif isinstance(term, URIRef):
            key = "<" + str(term) + ">"
            if key not in self.nodes:
                self.nodes[key] = NodeVar(name=f"n{len(self.nodes)}", iri=str(term))
        elif isinstance(term, BNode):
            key = "_:" + str(term)
            if key not in self.nodes:
                self.nodes[key] = NodeVar(name=f"b{len(self.nodes)}")
        else:
            raise _Unsupported(f"littéral en position de sujet : {term}")
        if key not in block.nodes:
            block.nodes.append(key)
        return key

    def fresh_var(self) -> Variable:
        self._fresh += 1
        return Variable(f"_p{self._fresh}")

    def node_types(self, key: str) -> set[str]:
        return {r.node_type for r in self.nodes[key].types}

    def type_family(self, types: set[str]) -> set[str]:
        """Types PG dont les propriétés s'appliquent : eux-mêmes + types portés par leurs labels secondaires
        (multi-labels : Technician:Person:Party hérite des propriétés de Party). Un type replié dans une racine
        (discriminant) est déjà la racine : rien à ajouter."""
        fam = set(types)
        for t in types:
            nt = self.pg.node_types.get(t)
            for lab in (nt.labels[1:] if nt else []):
                for o in self.pg.node_types.values():
                    if (o.labels[0] if o.labels else o.name) == lab:
                        fam.add(o.name)
        return fam

    # ---- classes ----
    def resolve_class(self, iri: str) -> list[ClassRef]:
        refs = self.ix.classes.get(iri)
        if refs:
            return refs
        if self.onto and iri in self.onto.classes:
            out: list[ClassRef] = []
            for d in self.onto.descendants(iri):
                out += self.ix.classes.get(d, [])
            if out:
                self.info(f"Classe {self.short(iri)} absente du PG : remplacée par ses sous-classes transposées "
                          f"({', '.join(sorted({r.disc_value or r.node_type for r in out}))}) — équivaut à une "
                          "requête SPARQL avec inférence RDFS.")
                return out
            for a in self.onto.ancestors(iri):
                if a in self.ix.classes:
                    self.lost(f"Sous-classe {self.short(iri)} non matérialisée dans le PG (ni label ni discriminant) : "
                              f"seule {self.short(a)} est interrogeable ; le filtre de type est perdu.")
                    return [ClassRef(r.node_type, r.label, r.disc_prop, r.disc_value) for r in self.ix.classes[a]]
        self.lost(f"Classe {self.short(iri)} absente du modèle PG : motif qui ne renvoie rien (jamais de motif non typé).")
        return []

    def add_type(self, key: str, refs: list[ClassRef]) -> None:
        nv = self.nodes[key]
        if not refs:
            # classe absente du PG : jamais de motif non typé (sur-ensemble) → motif qui ne renvoie rien
            nv.empty = True
            return
        if nv.types:
            inter = [r for r in nv.types if any(r.node_type == x.node_type for x in refs)]
            if not inter:
                self.lost(f"?{nv.sparql or nv.name} typée par deux classes sans type PG commun : intersection impossible "
                          "(motif qui ne renvoie rien).")
                nv.empty = True
                return
            new = [r for r in refs if any(r.node_type == t.node_type for t in nv.types)]
            old_d = {r.disc_value for r in nv.types if r.disc_value}
            new_d = {r.disc_value for r in new if r.disc_value}
            if old_d and new_d and all(r.disc_value for r in nv.types) and all(r.disc_value for r in new):
                common = old_d & new_d
                if not common:
                    self.lost(f"?{nv.sparql or nv.name} : types multiples non représentables par un discriminant "
                              f"mono-valué ({', '.join(sorted(old_d | new_d))}) — motif qui ne renvoie rien alors que "
                              "SPARQL admet une instance des deux classes.")
                    nv.empty = True
                    return
                nv.types = [r for r in new if r.disc_value in common]
                return
            # « parent puis sous-type » : le type le plus précis remplace l'autre
            disc = [r for r in refs if r.disc_value and any(r.node_type == t.node_type for t in nv.types)]
            nv.types = disc or inter or nv.types
            return
        nv.types = list(refs)

    # ---- motifs ----
    def bgp(self, triples, block: Block) -> None:
        triples = list(triples)
        triples.sort(key=lambda t: 0 if t[1] == RDF_TYPE else 1)
        for s, p, o in triples:
            self.triple(s, p, o, block)

    def triple(self, s, p, o, block: Block) -> None:
        if isinstance(p, Variable):
            self.lost(f"Prédicat variable ?{p} : pas d'équivalent direct en property graph (types de relation et "
                      "noms de propriétés sont du schéma, pas des données) — triplet ignoré.")
            self.unbound.add(str(p))
            return
        if p == RDF_TYPE:
            k = self.node_for(s, block)
            if isinstance(o, URIRef) and self._sub_ctx and k in self._sub_ctx[0]:
                # typage, dans un sous-motif, d'une variable liée à l'extérieur : condition sur ce nœud, pas un nouveau
                # type (L53, DF-B12 : avant, le type extérieur était modifié et la classe du sous-motif perdue)
                self._sub_ctx[1].setdefault(k, []).append(self.resolve_class(str(o)))
            elif isinstance(o, URIRef):
                self.add_type(k, self.resolve_class(str(o)))
            else:
                self.lost(f"Type variable (?{o}) : traduit par labels(n) en Cypher, sans correspondance IRI.")
                self.alias[str(o)] = f"labels({self.nodes[k].name})"
                self.curiosity_ok = False
            return
        if isinstance(p, Path):
            self.path_triple(s, p, o, block)
            return
        iri = str(p)
        if iri in (str(_RDFS.label), str(_RDFS.comment)) and iri not in self.ix.data:
            self.lost(f"{self.short(iri)} : annotation non transposée en propriété dans le PG.")
            if isinstance(o, Variable):
                self.unbound.add(str(o))
            return
        if iri in self.ix.data:
            self.data_triple(s, iri, o, block)
            return
        if iri in self.ix.edges:
            self.edge_triple(s, iri, o, block, 1, 1)
            return
        if iri in self.ix.edge_data:
            e = self.pg.edge_types[self.ix.edge_data[iri][0][0]]
            self.lost(f"{self.short(iri)} est portée par la relation {e.name} (dé-réification R01) : réécrire la requête "
                      "sur la propriété d'arête (-[r:…]-> r.prop) — non automatisé.")
            if isinstance(o, Variable):
                self.unbound.add(str(o))
            return
        subs = [sp for sp in self.ix.sub_properties(iri) if sp in self.ix.edges]
        if subs:
            self.info(f"{self.short(iri)} n'est pas transposée (O07) : traduite par l'alternative de ses "
                      f"sous-propriétés ({', '.join(self.short(x) for x in subs)}) — équivaut à l'inférence RDFS.")
            self.edge_triple(s, None, o, block, 1, 1, choices=[r for sp in subs for r in self.ix.edges[sp]])
            return
        if block.optional:
            self.lost(f"Propriété {self.short(iri)} absente du modèle PG (perdue ou non transposée) : triplet ignoré "
                      "dans l'OPTIONAL (variables non liées).")
        else:
            self.lost(f"Propriété {self.short(iri)} absente du modèle PG (perdue ou non transposée) : motif "
                      "obligatoire insatisfiable, le bloc ne renvoie rien.")
            block.cy_conds.append("false")
        if isinstance(o, Variable):
            self.unbound.add(str(o))

    def data_triple(self, s, iri: str, o, block: Block) -> None:
        k = self.node_for(s, block)
        cands = self.ix.data[iri]
        types = self.node_types(k)
        fam = self.type_family(types)
        fit = [c for c in cands if c[0] in fam] if types else cands
        if not fit:
            self.lost(f"{self.short(iri)} n'existe pas sur le type {', '.join(sorted(types))} dans le PG.")
            fit = cands
        if isinstance(o, Literal) and o.language:
            lf = [c for c in fit if c[1].lang == o.language]
            if lf:
                fit = lf
            else:
                self.lost(f"Littéral @{o.language} : la langue n'est pas conservée par la propriété "
                          f"{fit[0][1].name}.")
        elif len({c[1].lang for c in fit}) > 1:
            fr = [c for c in fit if c[1].lang == "fr"]
            fit = fr or fit
            self.info(f"{self.short(iri)} multilingue (D06) : propriété {fit[0][1].name} retenue ; "
                      "une propriété par langue dans le PG.")
        nts = {c[0] for c in fit}
        if not types and len(nts) == 1:
            nt = next(iter(nts))
            self.nodes[k].types = [ClassRef(nt, (self.pg.node_types[nt].labels or [nt])[0])]
        elif not types and len(nts) > 1:
            self.info(f"{self.short(iri)} existe sur plusieurs types ({', '.join(sorted(nts))}) : le type du sujet "
                      "n'est pas contraint.")
        nt, prop = fit[0]
        nv = self.nodes[k]
        if isinstance(o, Variable):
            ov = str(o)
            if ov in self.prop_vars or ov in self.nodes:
                other = self.prop_vars.get(ov)
                rhs = f"{self.nodes[other[0]].name}.{_cy_ident(other[1].name)}" if other else self.nodes[ov].name
                block.cy_conds.append(f"{nv.name}.{_cy_ident(prop.name)} = {rhs}")
                self.curiosity_ok = self.curiosity_ok and False
                self.note("curiosity", "Jointure sur valeur de propriété entre deux nœuds : à faire en C# après la "
                                       "traversée (pas d'équivalent Query API).")
            else:
                self.prop_vars[ov] = (k, prop)
                if self._sub_ctx and not block.optional:
                    # dans EXISTS / MINUS, le triplet exige la valeur (L53, DF-B12) : NOT EXISTS { ?v :p ?x } = « sans :p »
                    pn = f"{nv.name}.{_cy_ident(prop.name)}"
                    block.cy_conds.append(f"size({pn}) > 0" if prop.is_list else f"{pn} IS NOT NULL")
                if prop.is_list:
                    self.info(f"{prop.name} est une liste (D04) : chaque valeur SPARQL = un élément ; utiliser "
                              f"UNWIND {nv.name}.{prop.name} pour retrouver une ligne par valeur.")
        else:
            val = self.lit_cy(o)
            if prop.is_list:
                block.cy_conds.append(f"{val} IN {nv.name}.{_cy_ident(prop.name)}")
            else:
                block.cy_conds.append(f"{nv.name}.{_cy_ident(prop.name)} = {val}")
            block.node_conds.setdefault(k, []).append((prop.name, "=", o))

    def pick_edges(self, ka: str, kb: str, choices: list[EdgeRef]) -> list[EdgeRef]:
        ta, tb = self.node_types(ka), self.node_types(kb)

        def ends(r: EdgeRef) -> tuple[str, str]:
            e = self.ix.edge(r)
            return (e.to, e.from_) if r.inverse else (e.from_, e.to)
        fit = [r for r in choices if (not ta or ends(r)[0] in ta) and (not tb or ends(r)[1] in tb)]
        if not fit:
            self.lost("Relation incompatible avec les types des extrémités dans le PG "
                      f"({', '.join(sorted(ta)) or '?'} → {', '.join(sorted(tb)) or '?'}).")
            fit = choices
        froms = {ends(r)[0] for r in fit}
        tos = {ends(r)[1] for r in fit}
        if not ta and len(froms) == 1:
            nt = next(iter(froms))
            self.nodes[ka].types = [ClassRef(nt, (self.pg.node_types[nt].labels or [nt])[0])] if nt in self.pg.node_types else []
        if not tb and len(tos) == 1:
            nt = next(iter(tos))
            self.nodes[kb].types = [ClassRef(nt, (self.pg.node_types[nt].labels or [nt])[0])] if nt in self.pg.node_types else []
        return fit

    def edge_triple(self, s, iri: Optional[str], o, block: Block, mn: int, mx: Optional[int],
                    choices: Optional[list[EdgeRef]] = None) -> None:
        if isinstance(o, Literal):
            raise _Unsupported(f"littéral {o} comme objet d'une propriété objet")
        if isinstance(o, Variable) and str(o) in self.prop_vars:
            raise _Unsupported(f"?{o} utilisée comme nœud et comme valeur")
        ka, kb = self.node_for(s, block), self.node_for(o, block)
        ch = self.pick_edges(ka, kb, choices if choices is not None else self.ix.edges[iri])
        undirected = any(self.ix.edge(r).symmetric for r in ch) or len({r.inverse for r in ch}) > 1
        if len({r.inverse for r in ch}) > 1:
            self.info("Alternative mêlant un sens direct et un sens inverse : relation non orientée en Cypher.")
        if iri and mn == 1 and mx == 1 and self.ix.is_transitive(iri):
            self.info(f"{self.short(iri)} est transitive (O06) : traduction littérale (1 saut). Avec un raisonneur OWL, "
                      f"SPARQL renverrait la fermeture : écrire {self.short(iri)}+ (Cypher *1..) si c'est l'intention.")
        if iri and mn == 1 and mx == 1:
            subs = [sp for sp in self.ix.sub_properties(iri) if sp in self.ix.edges]
            if subs:
                self.info(f"{self.short(iri)} a des sous-propriétés transposées ({', '.join(self.short(x) for x in subs)}) "
                          "non incluses (pas d'inférence RDFS) ; les ajouter en alternative si nécessaire.")
        if any(self.ix.edge(r).symmetric for r in ch):
            self.info("Relation symétrique (O05) : un seul sens stocké, requête non orientée.")
        if mx != 1:
            self.has_varlen = True
        block.rels.append(Rel(ka, kb, ch, mn, mx, undirected))

    def path_steps(self, path) -> list:
        """Décompose un chemin en étapes : URIRef, ('inv', iri), ('alt', [steps]), ('mul', step, mod)."""
        if isinstance(path, URIRef):
            return [path]
        if isinstance(path, SequencePath):
            out = []
            for a in path.args:
                out += self.path_steps(a)
            return out
        if isinstance(path, InvPath):
            inner = self.path_steps(path.arg)
            return [("inv", st) for st in reversed(inner)]
        if isinstance(path, AlternativePath):
            return [("alt", [self.path_steps(a) for a in path.args])]
        if isinstance(path, MulPath):
            return [("mul", self.path_steps(path.path), path.mod)]
        if isinstance(path, NegatedPath):
            raise _Unsupported("chemin négatif (!p) : pas d'équivalent Cypher sans énumérer les types de relation")
        raise _Unsupported(f"chemin non reconnu : {path}")

    def step_choices(self, steps: list) -> list[EdgeRef]:
        """Étape réduite à un seul saut (pour |, + et *) → choix d'edges."""
        if len(steps) != 1:
            raise _Unsupported("séquence sous un opérateur de répétition ou d'alternative ((a/b)+) : nécessite les "
                               "quantified path patterns Neo4j 5.9+ — non automatisé")
        st = steps[0]
        if isinstance(st, URIRef):
            iri = str(st)
            if iri in self.ix.edges:
                return list(self.ix.edges[iri])
            subs = [sp for sp in self.ix.sub_properties(iri) if sp in self.ix.edges]
            if subs:
                self.info(f"{self.short(iri)} non transposée : remplacée par ses sous-propriétés dans le chemin.")
                return [r for sp in subs for r in self.ix.edges[sp]]
            raise _Unsupported(f"{self.short(iri)} dans un chemin n'est pas une relation du PG")
        if st[0] == "inv":
            return [EdgeRef(r.idx, not r.inverse) for r in self.step_choices([st[1]])]
        if st[0] == "alt":
            return [r for alt in st[1] for r in self.step_choices(alt)]
        raise _Unsupported("répétition imbriquée dans un chemin")

    def path_triple(self, s, path, o, block: Block) -> None:
        # rdf:type/rdfs:subClassOf* C  → type avec hiérarchie
        if isinstance(path, SequencePath) and len(path.args) == 2 and path.args[0] == RDF_TYPE and \
                isinstance(path.args[1], MulPath) and path.args[1].path == SUBCLASS and isinstance(o, URIRef):
            k = self.node_for(s, block)
            refs = self.resolve_class(str(o))
            if self.onto:
                for d in self.onto.descendants(str(o)):
                    refs = refs + [r for r in self.ix.classes.get(d, []) if r not in refs]
            self.info("rdf:type/rdfs:subClassOf* : la hiérarchie est matérialisée dans le PG (labels multiples ou "
                      "type aplati avec discriminant) : le simple filtre de type suffit.")
            if path.args[1].mod == "+":
                self.lost("rdf:type/rdfs:subClassOf+ (sous-classes strictes) : exclusion des instances directes non "
                          "traduite.")
            # type aplati : le parent couvre déjà les sous-types → pas de filtre discriminant
            parent = [r for r in refs if r.disc_prop is None]
            self.add_type(k, parent or refs)
            return
        try:
            steps = self.path_steps(path)
        except _Unsupported as e:
            self.lost(f"Chemin {path.n3() if hasattr(path, 'n3') else path} non traduit : {e}.")
            if isinstance(o, Variable):
                self.unbound.add(str(o))
            return
        # séquence : on chaîne avec des nœuds intermédiaires anonymes
        cur = s
        for i, st in enumerate(steps):
            nxt = o if i == len(steps) - 1 else self.fresh_var()
            self.step(cur, st, nxt, block)
            cur = nxt

    def step(self, s, st, o, block: Block) -> None:
        if isinstance(st, URIRef):
            self.triple(s, st, o, block)
            return
        try:
            if st[0] == "mul":
                ch = self.step_choices(st[1])
                mn, mx = {"+": (1, None), "*": (0, None), "?": (0, 1)}[st[2]]
                self.edge_triple(s, None, o, block, mn, mx, choices=ch)
            else:
                if st[0] == "inv" and isinstance(st[1], URIRef) and str(st[1]) in self.ix.data:
                    raise _Unsupported("inverse d'une propriété de données")
                self.edge_triple(s, None, o, block, 1, 1, choices=self.step_choices([st]))
        except _Unsupported as e:
            self.lost(f"Étape de chemin non traduite : {e}.")
            if isinstance(o, Variable):
                self.unbound.add(str(o))

    # ---- algèbre ----
    def pattern(self, node, block: Block) -> None:
        name = getattr(node, "name", None)
        if name == "BGP":
            self.bgp(node.triples, block)
        elif name == "Join":
            self.pattern(node.p1, block)
            self.pattern(node.p2, block)
        elif name == "LeftJoin" and self._sub_ctx:
            # DF-B18 (L53) : un OPTIONAL dans un sous-motif reste dans le sous-motif. Il ne change pas l'existence d'une
            # solution (EXISTS / NOT EXISTS) ; pour MINUS, il ne compte que s'il lie une variable de l'extérieur.
            self.pattern(node.p1, block)
            kind, outer_vars = self._sub_ctx[2], self._sub_ctx[3]
            # variables par parcours de l'algèbre (`_vars` manque sous EXISTS, traduit à part par translateGroupGraphPattern)
            q_vars = self.cond_vars(node.p2) - self.cond_vars(node.p1)
            if kind == "minus" and q_vars & outer_vars:
                self.lost("OPTIONAL dans un MINUS qui lie une variable du motif principal "
                          f"({', '.join('?' + v for v in sorted(q_vars & outer_vars))}) : non traduit, ignoré "
                          "(l'exclusion peut être plus large).")
            else:
                self.info("OPTIONAL dans un sous-motif EXISTS / NOT EXISTS / MINUS : sans effet sur le résultat, ignoré.")
            self._sub_vars |= q_vars - outer_vars  # variables de la partie ignorée : propres au sous-motif
        elif name == "LeftJoin":
            self.pattern(node.p1, block)
            opt = Block(optional=True)
            self.blocks.append(opt)
            self.pattern(node.p2, opt)
            expr = node.get("expr")
            if expr is not None and getattr(expr, "name", "") != "TrueFilter":
                opt.conds.append(expr)
        elif name == "Filter":
            self.pattern(node.p, block)
            block.conds.append(node.expr)
        elif name == "Extend" and self._sub_ctx and str(node.var) in self._sub_ctx[3]:
            # DF-B18 (L53) : BIND d'un sous-motif sur une variable du motif principal : non traduit
            self.pattern(node.p, block)
            self.lost(f"BIND ?{node.var} dans un sous-motif EXISTS / NOT EXISTS / MINUS sur une variable du motif "
                      "principal : non traduit, ignoré.")
        elif name == "Extend":
            self.pattern(node.p, block)
            self.alias[str(node.var)] = self.expr(node.expr)  # dans un sous-motif : local (restauré par sub_condition)
            self.curiosity_ok = False
            self.note("curiosity", f"BIND ?{node.var} : calculer la valeur en C# sur les nœuds résultats.")
        elif name == "Minus":
            self.pattern(node.p1, block)
            shared = set(getattr(node.p1, "_vars", None) or ()) & set(getattr(node.p2, "_vars", None) or ())
            if not shared and getattr(node.p2, "_vars", None) is not None:
                # SPARQL 1.1 §8.3.3 : sans variable partagée, MINUS ne retire rien (L53, DF-B14)
                self.info("MINUS sans variable partagée avec le motif principal : n'exclut rien (SPARQL 1.1, §8.3.3), "
                          "condition retirée.")
            else:
                block.conds.append(("minus", node.p2))
        elif name == "Graph":
            self.lost("GRAPH (graphes nommés) : pas de notion de graphe nommé dans le PG — le motif est traduit sur "
                      "tout le graphe ; compenser par une propriété `graph`/`source` sur les nœuds si nécessaire.")
            if isinstance(node.term, Variable):
                self.unbound.add(str(node.term))
            self.pattern(node.p, block)
        elif name == "ToMultiSet":
            self.pattern(node.p, block)
        elif name == "values":
            self.values(node, block)
        elif name == "Union":
            raise _Unsupported("UNION imbriquée dans un motif (seule l'UNION de premier niveau est traduite)")
        elif name in ("ServiceGraphPattern",) or name == "Service":
            raise _Unsupported("SERVICE (requête fédérée)")
        elif name in ("Project", "SelectQuery", "Slice", "Distinct", "AggregateJoin"):
            raise _Unsupported("sous-requête SELECT imbriquée (utiliser CALL { … } en Cypher — non automatisé)")
        else:
            raise _Unsupported(f"opérateur d'algèbre {name}")

    def values(self, node, block: Block) -> None:
        rows = node.get("res") or []
        if not rows:
            return
        vars_ = list(rows[0].keys())
        if len(vars_) != 1:
            raise _Unsupported("VALUES à plusieurs variables (traduire par UNWIND d'une liste de maps — non automatisé)")
        v = vars_[0]
        vals = [r[v] for r in rows]
        if all(isinstance(x, URIRef) for x in vals):
            k = self.node_for(v, block)
            nv = self.nodes[k]
            block.cy_conds.append(f"{nv.name}.{self.ix.id_prop(next(iter(self.node_types(k)), None))} IN "
                                  f"[{', '.join(_cy_str(str(x)) for x in vals)}]")
            block.node_conds.setdefault(k, []).append(("__id__", "IN", vals))
        else:
            self.alias[str(v)] = "_val"
            block.cy_conds.append("__UNWIND__" + f"[{', '.join(self.lit_cy(x) for x in vals)}] AS {_cy_ident(str(v))}")
            self.alias[str(v)] = _cy_ident(str(v))

    # ---- expressions ----
    def lit_cy(self, o) -> str:
        if isinstance(o, URIRef):
            return _cy_str(str(o))
        if isinstance(o, Literal):
            dt = str(o.datatype) if o.datatype else None
            v = str(o)
            if dt in (str(_XSD.integer), str(_XSD.int), str(_XSD.long), str(_XSD.short), str(_XSD.nonNegativeInteger),
                      str(_XSD.positiveInteger)):
                return str(int(o.toPython())) if re.match(r"^[+-]?\d+$", v.strip()) else _cy_str(v)
            if dt in (str(_XSD.decimal), str(_XSD.double), str(_XSD.float)):
                return v
            if dt == str(_XSD.boolean):
                return "true" if v.lower() in ("true", "1") else "false"
            if dt == str(_XSD.date):
                return f"date({_cy_str(v)})"
            if dt == str(_XSD.dateTime):
                return f"datetime({_cy_str(v)})"
            if dt == str(_XSD.time):
                return f"time({_cy_str(v)})"
            if dt in (str(_XSD.duration), str(_XSD.dayTimeDuration), str(_XSD.yearMonthDuration)):
                return f"duration({_cy_str(v)})"
            if dt and dt not in (str(_XSD.string), str(_RDF.langString)):
                self.lost(f"Littéral de type {self.short(dt)} sans type natif PG : comparé comme chaîne.")
            return _cy_str(v)
        raise _Unsupported(f"terme {o}")

    def var_cy(self, v: str) -> str:
        if v in self.alias:
            return self.alias[v]
        if v in self.prop_vars:
            k, p = self.prop_vars[v]
            return f"{self.nodes[k].name}.{_cy_ident(p.name)}"
        if v in self.nodes:
            return self.nodes[v].name
        self.unbound.add(v)
        return "null"

    def node_id(self, v: str) -> Optional[str]:
        if v in self.nodes and v not in self.alias:
            nv = self.nodes[v]
            return f"{nv.name}.{self.ix.id_prop(next(iter(self.node_types(v)), None))}"
        return None

    def expr(self, e) -> str:
        if isinstance(e, Variable):
            return self.var_cy(str(e))
        if isinstance(e, (Literal, URIRef)):
            return self.lit_cy(e)
        name = getattr(e, "name", None)
        if name == "RelationalExpression":
            op = e.op
            a, b = e.expr, e.other
            # comparaison nœud ↔ IRI : sur la propriété d'identité
            if isinstance(a, Variable) and isinstance(b, URIRef) and self.node_id(str(a)):
                return f"{self.node_id(str(a))} {'<>' if op == '!=' else op} {_cy_str(str(b))}"
            if op in ("IN", "NOT IN"):
                lhs = self.node_id(str(a)) if isinstance(a, Variable) and self.node_id(str(a)) else self.expr(a)
                lst = "[" + ", ".join(self.expr(x) for x in b) + "]"
                return f"{lhs} IN {lst}" if op == "IN" else f"NOT {lhs} IN {lst}"
            cop = {"=": "=", "!=": "<>", "<": "<", ">": ">", "<=": "<=", ">=": ">="}[op]
            return f"{self.expr(a)} {cop} {self.expr(b)}"
        if name == "ConditionalAndExpression":
            return "(" + " AND ".join([self.expr(e.expr)] + [self.expr(x) for x in e.other]) + ")"
        if name == "ConditionalOrExpression":
            return "(" + " OR ".join([self.expr(e.expr)] + [self.expr(x) for x in e.other]) + ")"
        if name == "UnaryNot":
            return f"NOT ({self.expr(e.expr)})"
        if name == "UnaryMinus":
            return f"-({self.expr(e.expr)})"
        if name in ("AdditiveExpression", "MultiplicativeExpression"):
            out = self.expr(e.expr)
            for op, other in zip(e.op, e.other):
                out += f" {op} {self.expr(other)}"
            return f"({out})"
        if name == "Builtin_REGEX":
            flags = str(e.flags) if e.get("flags") is not None else ""
            pat = str(e.pattern)
            if not pat.startswith("^"):
                pat = ".*" + pat
            else:
                pat = pat[1:]
            if not pat.endswith("$"):
                pat = pat + ".*"
            else:
                pat = pat[:-1]
            pre = "(?i)" if "i" in flags else ""
            self.info("REGEX : SPARQL cherche une sous-chaîne, Cypher =~ teste la chaîne entière → motif encadré de .*")
            return f"{self.expr(e.text)} =~ {_cy_str(pre + pat)}"
        simple = {"Builtin_CONTAINS": "CONTAINS", "Builtin_STRSTARTS": "STARTS WITH", "Builtin_STRENDS": "ENDS WITH"}
        if name in simple:
            return f"{self.expr(e.arg1)} {simple[name]} {self.expr(e.arg2)}"
        fn1 = {"Builtin_LCASE": "toLower", "Builtin_UCASE": "toUpper", "Builtin_STRLEN": "size", "Builtin_ABS": "abs",
               "Builtin_ROUND": "round", "Builtin_CEIL": "ceil", "Builtin_FLOOR": "floor"}
        if name in fn1:
            return f"{fn1[name]}({self.expr(e.arg)})"
        if name == "Builtin_STR":
            a = e.arg
            if isinstance(a, Variable) and self.node_id(str(a)):
                return self.node_id(str(a))
            return f"toString({self.expr(a)})"
        if name in ("Builtin_YEAR", "Builtin_MONTH", "Builtin_DAY", "Builtin_HOURS", "Builtin_MINUTES"):
            part = {"Builtin_YEAR": "year", "Builtin_MONTH": "month", "Builtin_DAY": "day", "Builtin_HOURS": "hour",
                    "Builtin_MINUTES": "minute"}[name]
            return f"{self.expr(e.arg)}.{part}"
        if name == "Builtin_NOW":
            return "datetime()"
        if name == "Builtin_BOUND":
            return f"{self.expr(e.arg)} IS NOT NULL"
        if name == "Builtin_COALESCE":
            return "coalesce(" + ", ".join(self.expr(x) for x in e.arg) + ")"
        if name == "Builtin_IF":
            return f"CASE WHEN {self.expr(e.arg1)} THEN {self.expr(e.arg2)} ELSE {self.expr(e.arg3)} END"
        if name == "Builtin_CONCAT":
            return "(" + " + ".join(self.expr(x) for x in e.arg) + ")"
        if name in ("Builtin_EXISTS", "Builtin_NOTEXISTS"):
            return self.exists_pattern(e.graph, negated=name == "Builtin_NOTEXISTS")
        if name in ("Builtin_isIRI", "Builtin_isURI", "Builtin_isLITERAL", "Builtin_isBLANK", "Builtin_isNUMERIC"):
            self.lost(f"{name[8:]}() : distinction IRI/littéral sans objet en property graph — remplacé par true.")
            return "true"
        if name == "Builtin_LANG":
            self.lost("LANG() : les littéraux PG n'ont pas de langue (une propriété par langue, D06) — remplacé par ''.")
            return "''"
        if name == "Builtin_LANGMATCHES":
            self.lost("LANGMATCHES : sans objet en PG — remplacé par true (choisir la propriété label_<lang>).")
            return "true"
        if name == "Builtin_DATATYPE":
            self.lost("DATATYPE() : pas de datatype IRI en PG — remplacé par null.")
            return "null"
        if name == "Function":
            iri = str(e.iri)
            args = [self.expr(x) for x in e.expr]
            casts = {str(_XSD.date): "date", str(_XSD.dateTime): "datetime", str(_XSD.integer): "toInteger",
                     str(_XSD.int): "toInteger", str(_XSD.decimal): "toFloat", str(_XSD.double): "toFloat",
                     str(_XSD.float): "toFloat", str(_XSD.string): "toString", str(_XSD.boolean): "toBoolean"}
            if iri in casts and len(args) == 1:
                return f"{casts[iri]}({args[0]})"
            raise _Unsupported(f"fonction {self.short(iri)}")
        if name and name.startswith("Aggregate_"):
            return self.aggregate(e)
        raise _Unsupported(f"expression {name or e}")

    def aggregate(self, a) -> str:
        kind = a.name[len("Aggregate_"):]
        dist = "DISTINCT " if a.get("distinct") else ""
        if kind == "Count":
            if a.vars == "*":
                return "count(*)" if not dist else "count(DISTINCT *)"
            v = str(a.vars)
            arg = self.node_id(v) if v in self.nodes and dist else self.expr(a.vars)
            return f"count({dist}{arg})"
        fn = {"Sum": "sum", "Avg": "avg", "Min": "min", "Max": "max"}
        if kind in fn:
            return f"{fn[kind]}({dist}{self.expr(a.vars)})"
        if kind == "Sample":
            return self.expr(a.vars)
        if kind == "GroupConcat":
            sep = a.get("separator") or " "
            self.info("GROUP_CONCAT → reduce(…) sur collect() (sans APOC).")
            return (f"reduce(s = '', x IN collect({dist}toString({self.expr(a.vars)})) | "
                    f"s + CASE WHEN s = '' THEN '' ELSE {_cy_str(sep)} END + x)")
        raise _Unsupported(f"agrégat {kind}")

    def exists_pattern(self, graph, negated: bool = False) -> str:
        """FILTER [NOT] EXISTS { … } → condition Cypher complète (L53, DF-B12)."""
        from rdflib.plugins.sparql.algebra import translateGroupGraphPattern, traverse, translatePath
        alg = translateGroupGraphPattern(traverse(graph, translatePath))
        return self.sub_condition(alg, negated, id(graph))

    def sub_condition(self, alg, negated: bool, sid: int, kind: str = "exists") -> str:
        """Sous-motif d'EXISTS, NOT EXISTS (`kind="exists"`) ou MINUS (`kind="minus"`, toujours nié) → condition Cypher.

        Le sous-motif ne déborde pas (DF-B18) : nœuds, propriétés, BIND et blocs qu'il crée sont retirés après son rendu.
        Un nœud d'OPTIONAL non lié (null) suit SPARQL : MINUS garde la ligne (domaines disjoints, §18.5) ; EXISTS /
        NOT EXISTS évalue alors le sous-motif sur tout le graphe (§18.6) — forme exacte pour un typage seul, sinon
        note [perte]."""
        snap = (set(self.nodes), dict(self.prop_vars), dict(self.alias), len(self.blocks))
        try:
            cond, info = self._sub_core(alg, negated, sid, kind)
        finally:
            self._sub_vars |= {k for k in self.nodes if k not in snap[0]} | (set(self.prop_vars) - set(snap[1])) | \
                (set(self.alias) - set(snap[2]))
            for k in [k for k in self.nodes if k not in snap[0]]:
                del self.nodes[k]
            self.prop_vars, self.alias = snap[1], snap[2]
            del self.blocks[snap[3]:]
        touched = info.get("touched", set()) if info else set()
        opt = touched & self._opt_keys
        if not opt or cond == "false":
            return cond
        names = ", ".join("?" + (self.nodes[k].sparql or self.nodes[k].name) for k in sorted(opt))
        if kind == "minus":
            if touched == opt and len(opt) == 1:
                k = next(iter(opt))
                self.info(f"MINUS sur {names} liée par OPTIONAL : ligne gardée quand la variable n'est pas liée "
                          "(domaines disjoints, SPARQL 1.1 §18.5).")
                return f"({self.nodes[k].name} IS NULL OR {cond})"
            self.lost(f"MINUS sur {names} liée par OPTIONAL et sur d'autres variables : traduit pour la variable liée "
                      "seulement (SPARQL 1.1 §18.5, compatibilité sur les seules variables liées).")
            return cond
        cap = info.get("captured", {})
        if info.get("only_types") and len(cap) == 1 and next(iter(cap)) in opt:
            k = next(iter(cap))
            self._fresh += 1
            u = f"_any{self._fresh}"
            preds = [self.type_predicate(k, refs, name=u) for refs in cap[k]]
            if all(preds):
                anywhere = f"EXISTS {{ MATCH ({u}) WHERE {' AND '.join(preds)} }}"
                self.info(f"EXISTS sur {names} liée par OPTIONAL : quand la variable n'est pas liée, le sous-motif est "
                          "évalué sur tout le graphe (SPARQL 1.1 §18.6) → CASE WHEN … IS NULL.")
                return (f"CASE WHEN {self.nodes[k].name} IS NULL THEN {'NOT ' if negated else ''}{anywhere} "
                        f"ELSE {cond} END")
        self.lost(f"Sous-motif EXISTS / NOT EXISTS sur {names} liée par OPTIONAL : quand la variable n'est pas liée, "
                  "SPARQL évalue le sous-motif sur tout le graphe (§18.6) ; traduit pour la variable liée seulement.")
        return cond

    def _sub_core(self, alg, negated: bool, sid: int, kind: str) -> tuple[str, dict]:
        """Sous-motif d'EXISTS, NOT EXISTS ou MINUS → condition Cypher, jamais un `MATCH` vide (L53, DF-B12).

        - Typage d'un nœud déjà lié à l'extérieur : prédicat de label ou de discriminant (`v:ElectricVehicle`,
          `NOT v:ElectricVehicle`), qui respecte les labels posés au chargement ; le type extérieur n'est pas modifié.
        - Sous-motif avec un nouveau motif : `[NOT] EXISTS { MATCH … WHERE … }` (les prédicats de type y sont ajoutés).
        - Sous-motif sans nouveau motif mais avec des conditions : ancré sur un nœud extérieur, `EXISTS { MATCH (v) WHERE … }`.
        - Rien de traduisible : note [perte] et condition `false` (jamais un sur-ensemble)."""
        outer = set(self.nodes)
        sub = Block()
        captured: dict[str, list[list[ClassRef]]] = {}
        outer_vars = {k for k in outer if not k.startswith(("<", "_:"))} | set(self.prop_vars) | set(self.alias)
        prev, self._sub_ctx = self._sub_ctx, (outer, captured, kind, outer_vars)
        try:
            self.pattern(alg, sub)
        finally:
            self._sub_ctx = prev
        pats, where = self.render_block(sub, set(outer), force_labels=False)
        only_types = not pats and not where and bool(captured)
        info = {"touched": (set(sub.nodes) & outer) | set(captured), "captured": captured, "only_types": only_types}
        bare = [self.type_predicate(k, refs, null_safe=only_types) for k, lst in captured.items() for refs in lst]
        if any(b is None for b in bare):  # type sans label : aucun filtre sûr
            return "false", info
        for k, lst in captured.items():
            self._check_sub_types(k, lst)
        # Sous négation, une perte qui rend le sous-motif insatisfiable (classe absente, propriété absente, nœud du
        # sous-motif vide) ne doit pas devenir « vrai » : la condition entière vaut false (revue query L53 it1).
        unsat = any(not refs for lst in captured.values() for refs in lst) or \
            any(self.nodes[k].empty for k in sub.nodes if k not in outer) or "false" in sub.cy_conds
        if negated and unsat:
            self.lost("Sous-motif NOT EXISTS / MINUS insatisfiable à cause d'un élément absent du PG : condition "
                      "remplacée par false (aucun résultat plutôt qu'un résultat élargi).")
            return "false", info
        nots = "NOT " if negated else ""
        if only_types:
            if len(captured) == 1:
                k = next(iter(captured))
                self._sub_cs[sid] = (k, captured[k], negated)
                if len(self.node_types(k)) != 1:
                    self.curiosity_ok = False
            else:
                self.curiosity_ok = False
            if "false" in bare:
                return "false", info  # classe absente : EXISTS faux (sous négation : traité plus haut)
            pred = bare[0] if len(bare) == 1 else "(" + " AND ".join(bare) + ")"
            return nots + pred, info
        self.curiosity_ok = self.curiosity_ok and not captured and self._simple_exists(sub, set(outer))
        conds = bare + ([where] if where else [])
        if not pats:
            anchor = next((k for k in sub.nodes if k in outer), None) or next(iter(captured), None)
            if anchor is None:
                self.lost("Sous-motif EXISTS / NOT EXISTS / MINUS sans motif traduisible : condition remplacée par "
                          "false (aucun résultat plutôt qu'un motif vide invalide).")
                return "false", info
            pats = [f"({self.nodes[anchor].name})"]
        return nots + "EXISTS { MATCH " + ", ".join(pats) + (" WHERE " + " AND ".join(conds) if conds else "") + " }", info

    def _compatible(self, a: ClassRef, b: ClassRef) -> bool:
        """Deux références de classe peuvent-elles désigner le même nœud PG ? Même type de nœud (et même valeur de
        discriminant si les deux en ont une), ou un type qui porte le label de l'autre (multi-labels neo4j)."""
        if a.node_type == b.node_type:
            return not (a.disc_value and b.disc_value) or a.disc_value == b.disc_value
        def labels(nt: str) -> list[str]:
            n = self.pg.node_types.get(nt)
            return (n.labels if n and n.labels else [nt])
        return (a.label in labels(b.node_type)) or (b.label in labels(a.node_type))

    def _check_sub_types(self, key: str, lst: list[list[ClassRef]]) -> None:
        """Typage de sous-motif incompatible avec les types PG du nœud extérieur (ou entre eux) : intersection non
        représentable, même perte que add_type au niveau principal (revue query L53 it1)."""
        nv = self.nodes[key]
        cands = list(nv.types)
        if not cands or nv.empty:
            return
        for refs in lst:
            if not refs:
                return  # classe absente : perte déjà signalée
            new = [r for r in refs if any(self._compatible(r, c) for c in cands)]
            if not new:
                self.lost(f"?{nv.sparql or nv.name} : typage du sous-motif incompatible avec ses autres types dans le PG "
                          "(intersection non représentable) : SPARQL admet une instance des deux classes, le PG non ; "
                          "sous NOT EXISTS / MINUS le résultat peut être plus large.")
                return
            cands = new

    def type_predicate(self, key: str, refs: list[ClassRef], null_safe: bool = False,
                       name: Optional[str] = None) -> Optional[str]:
        """« ?key a C » sur un nœud déjà apparié → prédicat Cypher : union des types possibles de C, chacun « label »
        ou « label ET discriminant » (même règle que node_pat). `null_safe` : discriminant absent = faux, pour que
        `NOT …` garde les nœuds sans discriminant. None : un type sans label (pas de filtre sûr, note [perte]).
        `name` : autre identifiant (nœud quelconque du graphe, cas d'une variable d'OPTIONAL non liée)."""
        n = name or self.nodes[key].name
        if not refs:
            return "false"  # classe absente du PG : note [perte] déjà posée par resolve_class
        if any(not r.label for r in refs):
            self.lost(f"?{self.nodes[key].sparql or n} : un des types de nœuds possibles n'a pas de label, typage du "
                      "sous-motif non traduisible (condition remplacée par false).")
            return None
        plain = sorted({r.label for r in refs if not r.disc_value})
        terms = [f"{n}:{_cy_ident(lab)}" for lab in plain]
        for r in sorted({r for r in refs if r.disc_value and r.label not in plain},
                        key=lambda r: (r.label, r.disc_prop or "", r.disc_value or "")):
            d = f"{n}.{_cy_ident(r.disc_prop)} = {_cy_str(r.disc_value)}"
            terms.append(f"({n}:{_cy_ident(r.label)} AND {f'coalesce({d}, false)' if null_safe else d})")
        return terms[0] if len(terms) == 1 else "(" + " OR ".join(terms) + ")"

    def cs_type_check(self, key: str, lst: list[list[ClassRef]], negated: bool) -> str:
        """Même condition en C# (Query API) sur le nœud courant n : décidée par le type du nœud, ou test du discriminant."""
        tb = next(iter(self.node_types(key))) if len(self.node_types(key)) == 1 else None
        if tb is None:
            self.curiosity_ok = False
            raise _Unsupported("typage d'un nœud aux types multiples dans EXISTS / MINUS")
        parts = []
        for refs in lst:
            match = [r for r in refs if r.node_type == tb]
            if not match and any(self._compatible(r, t) for r in refs for t in self.nodes[key].types):
                # autre type de nœud qui porte le label du nœud (sous-type multi-labels, nœud atteint par une relation) :
                # le type seul ne tranche pas (revue curiosity L53 it2)
                self.curiosity_ok = False
                raise _Unsupported("typage par un sous-type d'un autre type de nœud dans EXISTS / MINUS")
            if not match:
                parts.append("false")
            elif any(not r.disc_value for r in match):
                parts.append("true")
            else:
                dp = match[0].disc_prop
                acc = self.cs_access(tb, self.ix.prop(tb, dp), dp)
                vals = sorted({r.disc_value for r in match})
                parts.append(f"{acc} == {_cs_str(vals[0])}" if len(vals) == 1 else
                             f"new[] {{ {', '.join(_cs_str(v) for v in vals)} }}.Contains({acc})")
        if "false" in parts:
            body = "false"
        else:
            parts = [x for x in parts if x != "true"]
            body = "true" if not parts else parts[0] if len(parts) == 1 else "(" + " && ".join(parts) + ")"
        if negated:
            body = {"true": "false", "false": "true"}.get(body) or f"!({body})"
        return body

    def _simple_exists(self, sub: Block, before: set) -> bool:
        return len(sub.rels) == 1 and not sub.conds

    # ---- rendu Cypher ----
    def node_pat(self, key: str, printed: set) -> tuple[str, list[str]]:
        nv = self.nodes[key]
        conds: list[str] = []
        if key in printed:
            return f"({nv.name})", conds
        printed.add(key)
        labels = sorted({r.label for r in nv.types if r.label})
        nts = {r.node_type for r in nv.types}
        lab = ""
        if len(nts) == 1 and len(labels) >= 1:
            lab = ":" + _cy_ident(labels[0]) if len(labels) == 1 else ""
            discs = sorted({r.disc_value for r in nv.types if r.disc_value})
            if len(labels) > 1:
                conds.append("(" + " OR ".join(f"{nv.name}:{_cy_ident(l)}" for l in labels) + ")")
            if discs and all(r.disc_value for r in nv.types):
                dp = next(r.disc_prop for r in nv.types if r.disc_prop)
                conds.append(f"{nv.name}.{_cy_ident(dp)} = {_cy_str(discs[0])}" if len(discs) == 1 else
                             f"{nv.name}.{_cy_ident(dp)} IN [{', '.join(_cy_str(d) for d in discs)}]")
        elif labels:
            # Plusieurs types de nœuds (L52, DF-B06). Le motif est l'union des types : chaque référence vaut « label » ou
            # « label ET discriminant ». Une référence sans discriminant absorbe celles de même label qui en ont un.
            # Cas multi-labels Neo4j : Vehicle, ElectricVehicle et CombustionVehicle portent tous le label Vehicle → (v:Vehicle).
            plain = sorted({r.label for r in nv.types if r.label and not r.disc_value})
            terms = [f"{nv.name}:{_cy_ident(l)}" for l in plain]
            for r in sorted({r for r in nv.types if r.label and r.disc_value and r.label not in plain},
                            key=lambda r: (r.label, r.disc_prop or "", r.disc_value or "")):
                terms.append(f"({nv.name}:{_cy_ident(r.label)} AND {nv.name}.{_cy_ident(r.disc_prop)} = {_cy_str(r.disc_value)})")
            if any(not r.label for r in nv.types):  # référence sans label (jamais produite aujourd'hui) : pas de filtre sûr
                self.lost(f"?{nv.sparql or nv.name} : un des types de nœuds possibles n'a pas de label, motif non filtré "
                          "(sur-ensemble possible).")
            elif len(terms) == 1 and len(plain) == 1:
                lab = ":" + _cy_ident(plain[0])
            elif terms:
                conds.append("(" + " OR ".join(terms) + ")")
        if nv.empty:
            conds.append("false")  # classe absente / types incompatibles : aucun résultat (jamais un sur-ensemble)
        props = ""
        if nv.iri:
            idp = self.ix.id_prop(next(iter(nts), None))
            props = f" {{{_cy_ident(idp or 'uri')}: {_cy_str(nv.iri)}}}"
            if idp != "uri":
                self.info(f"IRI {self.short(nv.iri)} : le PG n'a pas de propriété uri, recherche sur la clé {idp} "
                          "(valeur à adapter).")
        return f"({nv.name}{lab}{props})", conds

    def rel_pat(self, r: Rel) -> str:
        types = []
        for c in r.choices:
            t = edge_cypher_type(self.pg, self.ix.edge(c))
            if t not in types:
                types.append(t)
        rng = ""
        if not (r.min == 1 and r.max == 1):
            rng = f"*{r.min}.." + (str(r.max) if r.max is not None else "")
        body = f"[:{'|'.join(_cy_ident(t) for t in types)}{rng}]"
        if r.undirected:
            return f"-{body}-"
        inv = r.choices[0].inverse if r.choices else False
        return f"<-{body}-" if inv else f"-{body}->"

    def render_block(self, block: Block, printed: set, force_labels: bool = True,
                     skip: Optional[list] = None) -> tuple[list[str], str]:
        pats: list[str] = []
        conds: list[str] = []
        tail: Optional[str] = None
        for r in block.rels:
            pa, ca = self.node_pat(r.a, printed)
            pb, cb = self.node_pat(r.b, printed)
            conds += ca + cb
            if tail == r.a and pats:
                pats[-1] += self.rel_pat(r) + pb
            else:
                pats.append(pa + self.rel_pat(r) + pb)
            tail = r.b
        in_rels = {k for r in block.rels for k in (r.a, r.b)}
        for k in block.nodes:
            if k not in in_rels and k not in printed:
                p, c = self.node_pat(k, printed)
                pats.append(p)
                conds += c
        unwind = [c[len("__UNWIND__"):] for c in block.cy_conds if c.startswith("__UNWIND__")]
        if unwind:
            self._unwinds = getattr(self, "_unwinds", []) + unwind
        conds += [c for c in block.cy_conds if not c.startswith("__UNWIND__")]
        conds += self.render_conds([c for c in block.conds if not any(c is x for x in (skip or []))])
        return pats, " AND ".join(conds)

    def render_conds(self, items: list) -> list[str]:
        conds: list[str] = []
        for c in items:
            try:
                if isinstance(c, tuple) and c[0] == "minus":
                    conds.append(self.sub_condition(c[1], True, id(c[1]), kind="minus"))
                    self.info("MINUS → NOT EXISTS { … } (les deux motifs partagent au moins une variable).")
                else:
                    conds.append(self.expr(c))
            except _Unsupported as e:
                self.lost(f"FILTER non traduit ({e}) : condition ignorée.")
        return conds

    @staticmethod
    def cond_vars(c, depth: int = 0) -> set[str]:
        """Variables SPARQL citées par une condition (expression d'algèbre, EXISTS compris, ou MINUS)."""
        if isinstance(c, tuple) and len(c) == 2 and c[0] == "minus":
            return {str(v) for v in (getattr(c[1], "_vars", None) or ())}
        out: set[str] = set()
        if depth > 60:
            return out
        if isinstance(c, Variable):
            out.add(str(c))
        elif isinstance(c, str):
            pass
        elif isinstance(c, dict):
            for v in c.values():
                out |= _Translator.cond_vars(v, depth + 1)
        elif isinstance(c, (list, tuple, set)) or type(c).__name__ == "ParseResults":
            for v in c:
                out |= _Translator.cond_vars(v, depth + 1)
        return out

    def has_aggregate(self) -> bool:
        return getattr(self, "_aggs", None) is not None

    # ---- point d'entrée ----
    def run(self, algebra) -> tuple[str, dict]:
        q = algebra
        self.form = {"SelectQuery": "select", "AskQuery": "ask", "ConstructQuery": "construct",
                     "DescribeQuery": "describe"}.get(q.name, q.name)
        if self.form in ("construct", "describe"):
            self.lost(f"{self.form.upper()} : la construction de triplets n'a pas d'équivalent ; seule la clause WHERE "
                      "est traduite (RETURN des variables).")
        if q.get("datasetClause"):
            self.lost("FROM / FROM NAMED : pas de graphes nommés en PG — ignoré.")
        mods: dict[str, Any] = {"distinct": False, "slice": None, "order": None, "pv": None, "having": [],
                                "extend": [], "aggs": None, "group": None}
        node = q.p
        while True:
            n = getattr(node, "name", None)
            if n == "Slice":
                mods["slice"] = (node.start, node.length)
            elif n in ("Distinct", "Reduced"):
                mods["distinct"] = True
            elif n == "Project":
                mods["pv"] = [str(v) for v in node.PV]
            elif n == "OrderBy":
                mods["order"] = node.expr
            elif n == "Extend" and (mods["aggs"] is None and self._above_agg(node)):
                mods["extend"].append((str(node.var), node.expr))
            elif n == "Filter" and self._above_agg(node):
                mods["having"].append(node.expr)
            elif n == "AggregateJoin":
                mods["aggs"] = node.A
            elif n == "Group":
                mods["group"] = node.expr or []
                node = node.p
                break
            else:
                break
            node = node.p
        branches = [node]
        if getattr(node, "name", None) == "Union" and mods["aggs"] is None:
            branches = self._flatten_union(node)
        return self.render(branches, mods), mods

    def _above_agg(self, node) -> bool:
        cur = node.p
        while cur is not None and getattr(cur, "name", None) in ("Extend", "Filter", "OrderBy", "Project"):
            cur = cur.p
        return getattr(cur, "name", None) == "AggregateJoin"

    def _flatten_union(self, node) -> list:
        if getattr(node, "name", None) == "Union":
            return self._flatten_union(node.p1) + self._flatten_union(node.p2)
        return [node]

    def render(self, branches: list, mods: dict) -> str:
        parts = []
        if len(branches) > 1:
            self.info("UNION → UNION de requêtes Cypher (mêmes colonnes) ; la traduction Curiosity ne couvre que la "
                      "première branche.")
            self.curiosity_ok = False
            self.graphql_ok = False
        saved = None
        for i, br in enumerate(branches):
            if i > 0:
                saved = saved or (self.nodes, self.prop_vars, self.blocks)
                self.nodes, self.prop_vars, self.blocks = {}, {}, []
            main = Block()
            self.blocks = [main]
            self.pattern(br, main)
            if i == 0:
                self.first = (dict(self.nodes), dict(self.prop_vars), list(self.blocks))
            parts.append(self.render_one(mods))
        if saved:
            self.nodes, self.prop_vars, self.blocks = self.first
        return "\nUNION\n".join(parts)

    def render_one(self, mods: dict) -> str:
        printed: set = set()
        lines: list[str] = []
        self._unwinds = []
        main = self.blocks[0]
        # DF-B15 (L53) : un FILTER qui cite une variable liée seulement par un OPTIONAL se place après l'OPTIONAL MATCH
        opt_keys = {k for b in self.blocks[1:] for k in b.nodes} - set(main.nodes)
        post = [c for c in main.conds if any(v in opt_keys or (v in self.prop_vars and self.prop_vars[v][0] in opt_keys)
                                             for v in self.cond_vars(c))] if opt_keys else []
        pats, where = self.render_block(main, printed, skip=post)
        for u in self._unwinds:
            lines.append(f"UNWIND {u}")
        if pats:
            lines.append("MATCH " + ", ".join(pats))
        if where:
            lines.append("WHERE " + where)
        late: list[str] = []
        for b in self.blocks[1:]:
            only_props = not b.rels and all(k in printed for k in b.nodes) and not b.cy_conds and not b.conds
            if only_props:
                self.info("OPTIONAL sur des propriétés d'un nœud déjà apparié : pas d'OPTIONAL MATCH nécessaire "
                          "(une propriété absente vaut null).")
                continue
            if not b.rels and all(k in printed for k in b.nodes):
                # optionnel avec filtres sur propriétés : la condition s'applique à la valeur, pas à la ligne
                self.info("OPTIONAL { propriété + FILTER } → expression CASE (valeur null si la condition échoue).")
                bp, bw = self.render_block(b, printed)
                for v, (k, p) in list(self.prop_vars.items()):
                    if k in b.nodes and bw:
                        self.alias[v] = f"CASE WHEN {bw} THEN {self.nodes[k].name}.{_cy_ident(p.name)} END"
                continue
            bp, bw = self.render_block(b, printed)
            lines.append("OPTIONAL MATCH " + ", ".join(bp) + (f" WHERE {bw}" if bw else ""))
        if post:
            self._opt_keys = opt_keys
            try:
                pw = self.render_conds(post)
            finally:
                self._opt_keys = set()
            if pw:
                self.info("FILTER sur une variable liée par OPTIONAL → WITH * WHERE … après l'OPTIONAL MATCH (la "
                          "variable n'existe pas avant).")
                lines.append("WITH *")
                lines.append("WHERE " + " AND ".join(pw))
        # projection
        pv = mods["pv"]
        if pv is None:
            pv = [n.sparql for n in self.nodes.values() if n.sparql and not n.sparql.startswith("_")] + \
                 [v for v in self.prop_vars if not v.startswith("_")]
        agg_alias: dict[str, str] = {}
        if mods["aggs"] is not None:
            for a in mods["aggs"]:
                try:
                    agg_alias[str(a.res)] = self.aggregate(a)
                except _Unsupported as e:
                    self.lost(f"Agrégat non traduit : {e}.")
                    agg_alias[str(a.res)] = "null"
        ext = {}
        for var, ex in mods["extend"]:
            if isinstance(ex, Variable) and str(ex) in agg_alias:
                ext[var] = agg_alias[str(ex)]
            else:
                try:
                    saved = dict(self.alias)
                    self.alias.update(agg_alias)
                    ext[var] = self.expr(ex)
                    self.alias = saved
                except _Unsupported as e:
                    self.lost(f"Expression de projection non traduite : {e}.")
                    ext[var] = "null"
        group_keys = [str(g) for g in (mods["group"] or []) if isinstance(g, Variable)]
        if mods["group"] and len(group_keys) != len(mods["group"]):
            self.lost("GROUP BY sur une expression : non traduit (regrouper sur une variable).")
        items: list[tuple[str, str]] = []
        for v in pv:
            if v in ext:
                expr = ext[v]
                if v in self.nodes and expr == self.nodes[v].name:
                    expr = self.node_id(v) or expr
            elif v in self.nodes and v not in self.alias:
                expr = self.node_id(v) or self.nodes[v].name
            elif v in self.prop_vars or v in self.alias:
                expr = self.var_cy(v)
            elif v in self._sub_vars and self.select_star:
                # SPARQL 1.1 §18.2.1 : hors de portée, pas de colonne avec SELECT * (rdflib la projette)
                self.info(f"?{v} n'apparaît que dans un sous-motif EXISTS / NOT EXISTS / MINUS : hors de portée "
                          "(SPARQL 1.1 §18.2.1), pas de colonne pour SELECT *.")
                continue
            elif v in self._sub_vars:
                expr = "null"  # nommée dans le SELECT : non liée, comme en SPARQL
                self.info(f"?{v} n'apparaît que dans un sous-motif EXISTS / NOT EXISTS / MINUS : non liée (null), "
                          "comme en SPARQL.")
            else:
                expr = "null"
                self.lost(f"?{v} n'est liée par aucun élément traduit : renvoyée à null.")
            items.append((v, expr))
        for g in group_keys:
            if g not in pv:
                self.info(f"GROUP BY ?{g} non projetée : ajoutée au regroupement implicite Cypher.")
                items.append((g, self.node_id(g) or self.var_cy(g)))
        distinct = "DISTINCT " if mods["distinct"] else ""
        if self.has_varlen and not mods["distinct"] and mods["aggs"] is None:
            distinct = "DISTINCT "
            self.info("Chemin de longueur variable : RETURN DISTINCT ajouté (un chemin SPARQL +/* rend des couples "
                      "distincts, Cypher un résultat par chemin).")
        ret = ", ".join(e if e == _cy_ident(v) else f"{e} AS {_cy_ident(v)}" for v, e in items)
        if self.form == "ask":
            ret = "count(*) > 0 AS result"
            distinct = ""
        if mods["having"]:
            with_items = [f"{e} AS {_cy_ident(v)}" if e != _cy_ident(v) else e for v, e in items
                          if v not in ext and v not in agg_alias]
            with_items += [f"{e} AS {_cy_ident(k)}" for k, e in agg_alias.items() if e != "null"]
            # _agg vars : identifiants valides
            lines.append("WITH " + ", ".join(dict.fromkeys(with_items)))
            saved = dict(self.alias)
            for k in agg_alias:
                self.alias[k] = _cy_ident(k)
            for v, e in items:
                if v not in ext:
                    self.alias[v] = _cy_ident(v)
            try:
                lines.append("WHERE " + " AND ".join(self.expr(h) for h in mods["having"]))
            except _Unsupported as e:
                self.lost(f"HAVING non traduit : {e}.")
            ret_items = []
            for v, e in items:
                if v in ext:
                    src = mods_ext_src(mods, v)
                    ret_items.append(f"{_cy_ident(src) if src in agg_alias else self.expr(Variable(v))} AS {_cy_ident(v)}"
                                     if src else _cy_ident(v))
                else:
                    ret_items.append(_cy_ident(v))
            ret = ", ".join(ret_items)
            self.alias = saved
        lines.append(f"RETURN {distinct}{ret}")
        if mods["order"]:
            obs = []
            for oc in mods["order"]:
                ex = oc.expr
                if isinstance(ex, Variable) and str(ex) in pv:
                    s = _cy_ident(str(ex))
                else:
                    try:
                        saved = dict(self.alias)
                        self.alias.update(agg_alias)
                        s = self.expr(ex)
                        self.alias = saved
                    except _Unsupported as e:
                        self.lost(f"ORDER BY non traduit : {e}.")
                        continue
                obs.append(s + (" DESC" if oc.order == "DESC" else ""))
            if obs:
                lines.append("ORDER BY " + ", ".join(obs))
        if mods["slice"]:
            start, length = mods["slice"]
            if start:
                lines.append(f"SKIP {start}")
            if length is not None:
                lines.append(f"LIMIT {length}")
        for v in sorted(self.unbound):
            if v in pv:
                self.lost(f"?{v} dépend d'un élément non traduit : valeur absente du résultat.")
        return "\n".join(lines)

    # ---- Curiosity ----
    def curiosity(self, mods: dict) -> Optional[str]:
        main = self.blocks[0]
        if not main.nodes:
            return None
        pv = mods["pv"] or []
        nodes_in = [k for k in main.nodes]
        target = next((v for v in pv if v in self.nodes and v in nodes_in), None)
        if target is None:
            target = next((self.prop_vars[v][0] for v in pv if v in self.prop_vars), None)
        if target is None and mods["aggs"]:
            for a in mods["aggs"]:
                vv = str(a.vars) if a.vars != "*" else None
                if vv in self.nodes:
                    target = vv
                    break
                if vv in self.prop_vars:
                    target = self.prop_vars[vv][0]
                    break
        target = target or nodes_in[0]
        # graphe non orienté des relations du bloc principal
        adj: dict[str, list[tuple[str, Rel]]] = {k: [] for k in nodes_in}
        for r in main.rels:
            adj.setdefault(r.a, []).append((r.b, r))
            adj.setdefault(r.b, []).append((r.a, r))

        def score(k: str) -> int:
            nv = self.nodes[k]
            s = 0
            if nv.iri:
                s += 10
            s += 3 * len(main.node_conds.get(k, []))
            if k == target:
                s += 1
            return s
        start = max(nodes_in, key=score)
        # BFS start → target
        prev: dict[str, tuple[str, Rel]] = {}
        seen = {start}
        queue = [start]
        while queue:
            cur = queue.pop(0)
            for nb, r in adj.get(cur, []):
                if nb not in seen:
                    seen.add(nb)
                    prev[nb] = (cur, r)
                    queue.append(nb)
        if target not in seen:
            self.note("curiosity", "Motif non connexe : produit cartésien sans équivalent dans la Query API.")
            return None
        path: list[tuple[str, str, Rel]] = []
        cur = target
        while cur != start:
            p, r = prev[cur]
            path.append((p, cur, r))
            cur = p
        path.reverse()
        chain = [start] + [b for _, b, _ in path]
        used_rels = {id(r) for _, _, r in path}
        pre: list[str] = []
        counter = [0]
        written: set[str] = set()  # nœuds dont les filtres sont écrits (chaîne ou sous-ensemble)

        def tname(k: str) -> Optional[str]:
            t = self.node_types(k)
            return next(iter(sorted(t))) if len(t) == 1 else None

        def step_code(a: str, b: str, r: Rel) -> str:
            tb = tname(b)
            names = []
            for c in r.choices:
                e = self.ix.edge(c)
                going_forward = (r.a == a) != c.inverse  # sens stocké de l'edge
                if self.pg.target == "curiosity":
                    nm = e.name if going_forward else (e.reverse or e.name)
                else:
                    nm = pascal(e.name) if going_forward else (pascal(e.reverse) if e.reverse else None)
                    if nm is None:
                        self.note("curiosity", f"Edge {e.name} sans reverse : nom Curiosity du sens retour à définir.")
                        nm = pascal(e.name) + "Inverse"
                if r.undirected and e.symmetric:
                    nm = e.name if self.pg.target == "curiosity" else pascal(e.name)
                names.append(nm)
            names = list(dict.fromkeys(names))
            nt = f"N.{tb}.Type" if tb else None
            if r.max == 1 and r.min == 1:
                if len(names) == 1 and nt:
                    return f".Out({nt}, E.{names[0]})"
                return f".Out(new[] {{ {nt or ''} }}, new[] {{ {', '.join('E.' + n for n in names)} }})"
            self.note("curiosity", f"Chemin de longueur variable → OutMany({VARLEN_DEPTH}, …) : profondeur bornée "
                                   f"(fermeture complète non garantie au-delà de {VARLEN_DEPTH} sauts) — À VÉRIFIER.")
            if r.min == 0:
                self.note("curiosity", "Chemin * (zéro saut inclus) : ajouter le nœud de départ au résultat en C#.")
            return (f".OutMany({VARLEN_DEPTH}, new[] {{ {nt or ''} }}, new[] {{ {', '.join('E.' + n for n in names)} }}, "
                    "distinct: true)  // À VÉRIFIER : sémantique de levels")

        def filters(k: str, skip_iri: bool = False) -> list[str]:
            out = []
            nv = self.nodes[k]
            tb = tname(k)
            for r in nv.types:
                if r.disc_prop and all(x.disc_value for x in nv.types) and tb:
                    vals = sorted({x.disc_value for x in nv.types})
                    if len(vals) == 1:
                        out.append(f".WhereString(N.{tb}.Type, N.{tb}.{pascal(r.disc_prop)}, {_cs_str(vals[0])})  // À VÉRIFIER : WhereString")
                    else:
                        out.append(f".WhereString(N.{tb}.Type, N.{tb}.{pascal(r.disc_prop)}, new[] {{ "
                                   f"{', '.join(_cs_str(v) for v in vals)} }})  // À VÉRIFIER : WhereString")
                    break
            for prop, op, val in main.node_conds.get(k, []):
                if prop == "__id__":
                    out.append(f".Where(n => new[] {{ {', '.join(_cs_str(str(x)) for x in val)} }}.Contains("
                               f"n.GetString(N.{tb}.{pascal(self.ix.id_prop(tb) or 'uri')})))  // À VÉRIFIER")
                    continue
                p = self.ix.prop(tb, prop) if tb else None
                if p and p.type == "String" and isinstance(val, Literal) and not p.is_list:
                    out.append(f".WhereString(N.{tb}.Type, N.{tb}.{pascal(prop)}, {_cs_str(str(val))})  // À VÉRIFIER : WhereString")
                else:
                    out.append(f".Where(n => {self.cs_access(tb, p, prop)} == {self.cs_lit(val)})  // À VÉRIFIER")
            for c in main.conds if k in nodes_in else []:
                pass
            return out

        # conditions FILTER portant sur un seul nœud → .Where(lambda) ; sinon note
        node_filters: dict[str, list[str]] = {}
        for c in main.conds:
            try:
                if isinstance(c, tuple):
                    tc = self._sub_cs.get(id(c[1]))
                    if not tc:  # L53 : l'exclusion n'est pas faite, la sortie C# est donc partielle
                        self.curiosity_ok = False
                        self.note("curiosity", "MINUS : calculer l'ensemble à exclure puis filtrer (!set.Contains(n.UID)).")
                        continue
                    ks, cs = {tc[0]}, self.cs_type_check(*tc)
                else:
                    ks, cs = self.cs_expr(c)
            except _Unsupported as e:
                self.curiosity_ok = False  # finitions L53 : un FILTER non traduit rend la sortie partielle
                self.note("curiosity", f"FILTER non traduit en Query API ({e}) : filtrer en C# après la traversée.")
                continue
            if len(ks) == 1 and cs == "true":
                continue  # condition toujours vraie sur ce type de nœud
            if len(ks) == 1 and cs == "false":
                node_filters.setdefault(next(iter(ks)), []).append(".Where(n => false)  // aucun résultat (type du nœud)")
                continue
            if len(ks) == 1:
                node_filters.setdefault(next(iter(ks)), []).append(f".Where(n => {cs})  // À VÉRIFIER : accesseurs")
            elif ks:
                self.note("curiosity", "FILTER portant sur plusieurs nœuds : à évaluer en C# (pas de jointure dans "
                                       "la Query API).")
        for c in main.cy_conds:
            if "=" in c and "." in c.split("=")[1]:
                pass

        def subset(y: str, x: str, r: Rel, visited: set) -> str:
            """Ensemble des UID de x reliés à au moins un y satisfaisant son sous-arbre."""
            counter[0] += 1
            vname = f"set{counter[0]}"
            ty = tname(y)
            lines = [f"var {vname} = Q().StartAt(N.{ty}.Type)" if ty else f"var {vname} = Q().StartAt(/* type ? */)"]
            lines += ["    " + f for f in filters(y) + node_filters.get(y, [])]
            written.add(y)
            for nb, r2 in adj.get(y, []):
                if r2 is r or nb in visited:
                    continue
                s2 = subset(nb, y, r2, visited | {y})
                lines.append(f"    .Where(n => {s2}.Contains(n.UID))  // À VÉRIFIER : n.UID")
            lines.append("    " + step_code(y, x, r))
            lines.append("    .AsEnumerable().Select(n => n.UID).ToHashSet();  // À VÉRIFIER")
            pre.append("\n".join(lines))
            return vname

        body: list[str] = []
        sv = self.nodes[start]
        ts = tname(start)
        if sv.iri and ts:
            body.append(f"Q().StartAt(N.{ts}.Type, {_cs_str(sv.iri)})  // clé = {self.ix.id_prop(ts)} — À VÉRIFIER")
        elif ts:
            body.append(f"Q().StartAt(N.{ts}.Type)")
        else:
            self.note("curiosity", "Type du nœud de départ inconnu : StartAt impossible sans type.")
            return None
        chain_set = set(chain)
        for i, k in enumerate(chain):
            body += filters(k) + node_filters.get(k, [])
            written.add(k)
            for nb, r in adj.get(k, []):
                if id(r) in used_rels or nb in chain_set:
                    if nb in chain_set and id(r) not in used_rels:
                        self.note("curiosity", "Cycle dans le motif : relation de fermeture non vérifiée.")
                    continue
                s = subset(nb, k, r, chain_set)
                body.append(f".Where(n => {s}.Contains(n.UID))  // À VÉRIFIER : n.UID")
            if i < len(path):
                a, b, r = path[i]
                body.append(step_code(a, b, r))
        # revue curiosity L53 it2 : un filtre sur un nœud hors de la traversée (OPTIONAL…) n'est pas écrit
        for k in sorted(set(node_filters) - written):
            self.curiosity_ok = False
            self.note("curiosity", f"Filtre sur ?{self.nodes[k].sparql or self.nodes[k].name} (hors de la traversée, "
                                   "par exemple OPTIONAL) non écrit : à appliquer en C# sur les voisins.")
        # blocs optionnels, NOT EXISTS
        if len(self.blocks) > 1:
            self.note("curiosity", "OPTIONAL : pas de jointure externe dans la Query API — lire les voisins optionnels "
                                   "dans la boucle sur les résultats (n.Out… / graphe).")
        # projection
        tt = tname(target)
        tail: list[str] = []
        if self.form == "ask":
            tail.append(".Any();")
        elif mods["aggs"]:
            aggs = mods["aggs"]
            counts = [a for a in aggs if a.name == "Aggregate_Count"]
            if not mods["group"] and len(counts) == len([a for a in aggs if a.name != "Aggregate_Sample"]) == 1:
                tail.append(".Count();")
            elif mods["group"]:
                g = str(mods["group"][0])
                if g in self.prop_vars and self.prop_vars[g][0] == target:
                    p = self.prop_vars[g][1]
                    tail.append(f".AsEnumerable().GroupBy(n => {self.cs_access(tt, p, p.name)})"
                                ".Select(g => new { key = g.Key, count = g.Count() });  // À VÉRIFIER")
                elif g in self.nodes and g != target:
                    self.note("curiosity", f"GROUP BY ?{g} (nœud) : inverser la traversée (partir de ?{g}) et "
                                           "compter les voisins par nœud en C#.")
                    body.insert(0, f"// regroupement par ?{g} : itérer Q().StartAt(N.{tname(g)}.Type) et compter les "
                                   "voisins de chaque nœud")
                    tail.append(".Count();  // par nœud de regroupement")
                else:
                    tail.append(".AsEnumerable()  // regroupement à faire en C#")
            else:
                tail.append(".AsEnumerable()  // agrégats à calculer en C# (LINQ)")
        else:
            if mods["order"]:
                obs = []
                for oc in mods["order"]:
                    v = str(oc.expr) if isinstance(oc.expr, Variable) else None
                    if v in self.prop_vars and self.prop_vars[v][0] == target:
                        p = self.prop_vars[v][1]
                        fn = "OrderByDescending" if oc.order == "DESC" else "OrderBy"
                        obs.append(f"{fn if not obs else fn.replace('OrderBy', 'ThenBy')}(n => {self.cs_access(tt, p, p.name)})")
                    else:
                        self.note("curiosity", "ORDER BY hors du nœud final : trier en C#.")
                start_slice = mods["slice"]
                if obs:
                    tail.append(".AsEnumerable()." + ".".join(obs))
                    if start_slice and start_slice[0]:
                        tail.append(f".Skip({start_slice[0]})")
                    if start_slice and start_slice[1] is not None:
                        tail.append(f".Take({start_slice[1]})")
                    tail[-1] += ";  // LINQ — À VÉRIFIER"
            elif mods["slice"]:
                s0, ln = mods["slice"]
                if s0:
                    tail.append(f".Skip({s0})")
                if ln is not None:
                    tail.append(f".Take({ln})")
            if not tail or not tail[-1].endswith("VÉRIFIER"):
                emit_fields = [self.prop_vars[v][1].name for v in pv if v in self.prop_vars and
                               self.prop_vars[v][0] == target]
                if emit_fields and tt:
                    tail.append(f'.Emit("N", new[] {{ {", ".join(f"N.{tt}.{pascal(f)}" for f in emit_fields)} }});')
                else:
                    tail.append('.Emit("N");')
            others = [v for v in pv if (v in self.nodes and v != target) or
                      (v in self.prop_vars and self.prop_vars[v][0] != target)]
            if others:
                self.note("curiosity", "La Query API renvoie les nœuds de fin de traversée : les colonnes "
                                       f"{', '.join('?' + v for v in others)} se lisent sur les voisins en C# "
                                       "(pas de tuples).")
        head = [f"// Curiosity Query API — pseudo-code C# (À VÉRIFIER : {CURIOSITY_DOC})",
                "// N.<Type>.Type / N.<Type>.<Champ> / E.<Edge> : constantes du schéma généré (Schema/Nodes, Edges) — À VÉRIFIER"]
        code = "\n".join(pre + ([""] if pre else []))
        main_q = body[0] + "".join("\n    " + x for x in body[1:] + tail)
        if not main_q.rstrip().endswith(";") and ";" not in tail[-1] if tail else True:
            main_q += ";"
        return "\n".join(head) + "\n" + code + "return " + main_q

    def cs_access(self, tb: Optional[str], p: Optional[PGProperty], name: str) -> str:
        fld = f"N.{tb}.{pascal(name)}" if tb else _cs_str(name)
        t = p.type if p else "String"
        acc = {"String": "GetString", "Integer": "GetInt", "Float": "GetDouble", "Decimal": "GetDouble",  # À VÉRIFIER : lecture decimal native de Curiosity non confirmée (précision perdue en requête)
               "Boolean": "GetBool",
               "Date": "GetTime", "DateTime": "GetTime", "LocalDateTime": "GetTime"}.get(t, "GetString")
        return f"n.{acc}({fld})"

    def cs_lit(self, v) -> str:
        if isinstance(v, Literal):
            dt = str(v.datatype) if v.datatype else None
            if dt in (str(_XSD.date), str(_XSD.dateTime)):
                return f"DateTimeOffset.Parse({_cs_str(str(v))})"
            if dt in (str(_XSD.integer), str(_XSD.int), str(_XSD.decimal), str(_XSD.double), str(_XSD.float)):
                return str(v)
            if dt == str(_XSD.boolean):
                return str(v).lower()
            return _cs_str(str(v))
        if isinstance(v, URIRef):
            return _cs_str(str(v))
        raise _Unsupported(f"terme {v}")

    def cs_expr(self, e) -> tuple[set, str]:
        """Expression → (nœuds référencés, lambda C# sur n)."""
        if isinstance(e, Variable):
            v = str(e)
            if v in self.prop_vars:
                k, p = self.prop_vars[v]
                return {k}, self.cs_access(next(iter(sorted(self.node_types(k))), None), p, p.name)
            raise _Unsupported(f"?{v} n'est pas une propriété")
        if isinstance(e, (Literal, URIRef)):
            return set(), self.cs_lit(e)
        name = getattr(e, "name", None)
        if name == "RelationalExpression":
            if e.op in ("IN", "NOT IN"):
                ka, a = self.cs_expr(e.expr)
                vals = ", ".join(self.cs_expr(x)[1] for x in e.other)
                s = f"new[] {{ {vals} }}.Contains({a})"
                return ka, s if e.op == "IN" else f"!{s}"
            ka, a = self.cs_expr(e.expr)
            kb, b = self.cs_expr(e.other)
            op = {"=": "==", "!=": "!=", "<": "<", ">": ">", "<=": "<=", ">=": ">="}[e.op]
            if op not in ("==", "!=") and ("GetString" in a or b.startswith('"')):
                return ka | kb, f"string.Compare({a}, {b}) {op} 0"
            return ka | kb, f"{a} {op} {b}"
        if name in ("ConditionalAndExpression", "ConditionalOrExpression"):
            parts = [self.cs_expr(e.expr)] + [self.cs_expr(x) for x in e.other]
            j = " && " if name == "ConditionalAndExpression" else " || "
            return set().union(*[p[0] for p in parts]), "(" + j.join(p[1] for p in parts) + ")"
        if name == "UnaryNot":
            k, s = self.cs_expr(e.expr)
            return k, f"!({s})"
        if name == "Builtin_REGEX":
            k, s = self.cs_expr(e.text)
            opt = ", RegexOptions.IgnoreCase" if e.get("flags") is not None and "i" in str(e.flags) else ""
            return k, f"Regex.IsMatch({s}, {_cs_str(str(e.pattern))}{opt})"
        m = {"Builtin_CONTAINS": "Contains", "Builtin_STRSTARTS": "StartsWith", "Builtin_STRENDS": "EndsWith"}
        if name in m:
            k, s = self.cs_expr(e.arg1)
            _, t = self.cs_expr(e.arg2)
            return k, f"{s}.{m[name]}({t})"
        if name in ("Builtin_LCASE", "Builtin_UCASE"):
            k, s = self.cs_expr(e.arg)
            return k, f"{s}.{'ToLowerInvariant' if name == 'Builtin_LCASE' else 'ToUpperInvariant'}()"
        if name == "Builtin_YEAR":
            k, s = self.cs_expr(e.arg)
            return k, f"{s}.Year"
        if name == "Builtin_BOUND":
            k, s = self.cs_expr(e.arg)
            return k, f"{s} != null"
        if name == "Builtin_NOW":
            return set(), "DateTimeOffset.UtcNow"
        if name in ("Builtin_EXISTS", "Builtin_NOTEXISTS"):
            tc = self._sub_cs.get(id(e.graph))
            if tc:  # sous-motif réduit au typage d'un nœud (L53, DF-B12)
                return {tc[0]}, self.cs_type_check(*tc)
            self.curiosity_ok = False  # revue curiosity L53 it1 : un EXISTS non traduit rend la sortie partielle
            raise _Unsupported("EXISTS / NOT EXISTS → calculer l'ensemble puis set.Contains(n.UID)")
        if name == "Function":
            if len(e.expr) == 1:
                return self.cs_expr(e.expr[0])
        raise _Unsupported(f"expression {name}")

    # ---- GraphQL ----
    def graphql(self, mods: dict) -> Optional[str]:
        reasons = []
        main = self.blocks[0]
        if mods["aggs"] is not None:
            reasons.append("agrégats")
        if self.has_varlen:
            reasons.append("chemin de longueur variable")
        if self.form != "select":
            reasons.append(f"forme {self.form.upper()}")
        if any(isinstance(c, tuple) for c in main.conds) or main.conds:
            reasons.append("FILTER")
        if mods["order"]:
            reasons.append("ORDER BY")
        if any(b.rels or b.conds or b.cy_conds for b in self.blocks[1:]):
            pass
        if any(r.undirected for b in self.blocks for r in b.rels):
            reasons.append("relation non orientée")
        if not self.graphql_ok:
            reasons.append("UNION / construction non supportée")
        if self.alias:
            reasons.append("BIND / expressions")
        if reasons:
            self.note("graphql", "Pas de requête GraphQL : lecture non simple (" + ", ".join(reasons) + ") — le "
                                 "schéma généré n'expose ni filtres ni agrégats.")
            return None
        rel_names = relation_fields(self.pg)
        # arbre depuis la racine
        adj: dict[str, list[tuple[str, Rel]]] = {}
        all_rels = [r for b in self.blocks for r in b.rels]
        for r in all_rels:
            adj.setdefault(r.a, []).append((r.b, r))
            adj.setdefault(r.b, []).append((r.a, r))
        pv = mods["pv"] or []
        cond_nodes = [k for k, cs in main.node_conds.items() if cs]
        root = None
        args = ""
        for k in cond_nodes:
            t = next(iter(self.node_types(k)), None)
            nt = self.pg.node_types.get(t or "")
            cs = main.node_conds[k]
            if nt and len(cs) == 1 and nt.key and cs[0][0] == nt.key[0] and len(nt.key) == 1:
                root = k
                args = f"({cs[0][0]}: {_gql_val(cs[0][2])})"
            else:
                self.note("graphql", "Filtre autre qu'une égalité sur la clé : non exprimable avec le schéma généré.")
                return None
        if len(cond_nodes) > 1:
            self.note("graphql", "Plusieurs nœuds filtrés : non exprimable avec le schéma généré.")
            return None
        nodes_all = [k for b in self.blocks for k in b.nodes]
        for k in nodes_all:
            if self.nodes[k].iri:
                t = next(iter(self.node_types(k)), None)
                if root is None and t:
                    root = k
                    idp = self.ix.id_prop(t)
                    nt = self.pg.node_types[t]
                    if idp == "uri" and nt.key != ["uri"]:
                        self.note("graphql", "Lookup par IRI : le schéma expose la clé métier ; requête par liste filtrée côté client.")
                        return None
                    args = f'({idp}: "{self.nodes[k].iri}")'
        if root is None:
            root = next((v for v in pv if v in self.nodes), None) or next((self.prop_vars[v][0] for v in pv if v in self.prop_vars), None)
        if root is None:
            return None
        rt = next(iter(self.node_types(root)), None)
        if rt is None or len(self.node_types(root)) != 1:
            self.note("graphql", "Type de la racine ambigu : pas de requête GraphQL.")
            return None
        single = bool(args)
        if not single:
            s = mods["slice"]
            a = []
            if s and s[1] is not None:
                a.append(f"first: {s[1]}")
            if s and s[0]:
                a.append(f"offset: {s[0]}")
            args = f"({', '.join(a)})" if a else ""
        field_name = lookup_field(rt) if single else list_field(rt)
        seen = {root}

        def sel(k: str, depth: int) -> list[str]:
            ind = "  " * depth
            t = next(iter(self.node_types(k)), None)
            nt = self.pg.node_types.get(t or "")
            out = []
            fields = [p.name for v, (kk, p) in self.prop_vars.items() if kk == k and not v.startswith("_p")]
            fields += [p.name for v, (kk, p) in self.prop_vars.items() if kk == k and v.startswith("_p")]
            if nt:
                for d in self.nodes[k].types:
                    if d.disc_value:
                        out.append(f"{ind}__typename")
                        self.note("graphql", f"Sous-type {d.disc_value} : filtrer sur __typename côté client "
                                             f"(… on {pascal(d.disc_value)}).")
                        break
                key = nt.key[0] if nt.key else "uri"
                if key not in fields:
                    fields.insert(0, key)
            out += [f"{ind}{f}" for f in dict.fromkeys(fields)]
            for nb, r in adj.get(k, []):
                if nb in seen:
                    continue
                seen.add(nb)
                c = r.choices[0]
                fwd, rev = rel_names[c.idx]
                going_forward = (r.a == k) != c.inverse
                fname = fwd if going_forward or rev is None else rev
                out.append(f"{ind}{fname} {{")
                out += sel(nb, depth + 1)
                out.append(f"{ind}}}")
            return out
        body = sel(root, 2)
        if len(seen) != len(set(nodes_all)):
            self.note("graphql", "Motif non arborescent : pas de requête GraphQL.")
            return None
        if len(self.blocks) > 1:
            self.info("GraphQL : les relations OPTIONAL deviennent de simples champs imbriqués (liste vide / null).")
        return "query {\n  " + field_name + args + " {\n" + "\n".join(body) + "\n  }\n}"


def mods_ext_src(mods: dict, v: str) -> Optional[str]:
    for var, ex in mods["extend"]:
        if var == v and isinstance(ex, Variable):
            return str(ex)
    return None


def _gql_val(v) -> str:
    if isinstance(v, Literal) and v.datatype and str(v.datatype) in (str(_XSD.integer), str(_XSD.decimal),
                                                                     str(_XSD.boolean), str(_XSD.double)):
        return str(v)
    return '"' + str(v).replace('"', '\\"') + '"'


def _init_ns(onto: Optional[OntoModel]) -> dict[str, str]:
    ns = {"rdf": str(_RDF), "rdfs": str(_RDFS), "owl": str(_OWL), "xsd": str(_XSD)}
    if onto:
        ns.update({k: v for k, v in onto.meta.prefixes.items() if k})
    return ns


_SPARQL_SKIP = re.compile(r'#[^\n]*|"(?:[^"\\]|\\.)*"|\'(?:[^\'\\]|\\.)*\'|<[^<>\s]*>')  # commentaires, chaînes, IRI
_SELECT_STAR = re.compile(r"\bSELECT\s+(?:DISTINCT\s+|REDUCED\s+)?\*", re.I)
_CY_STRINGS = re.compile(r"'(?:[^'\\]|\\.)*'|`(?:[^`]|``)*`")  # littéraux et identifiants entre accents graves
_EMPTY_MATCH = re.compile(r"\bMATCH\s*(?:WHERE\b|\}|,|$)", re.M)  # MATCH suivi de rien, de WHERE, de } ou d'une virgule


def translate(sparql: str, pg: PGModel, onto: Optional[OntoModel] = None) -> TranslationResult:
    res = TranslationResult(sparql=sparql)
    try:
        from . import sparql_lock  # analyseur rdflib non réentrant (L53, DF-B17)
        pq = sparql_lock.prepare_query(sparql, initNs=_init_ns(onto))
    except Exception as e:  # noqa: BLE001 — jamais d'exception vers l'appelant
        res.supported = False
        res.lossy = True
        res.notes = [f"[erreur] SPARQL invalide ou non supporté par le parseur (mise à jour, extension…) : "
                     f"{type(e).__name__}: {str(e)[:300]}"]
        return res
    t = _Translator(pg, onto)
    t.select_star = bool(_SELECT_STAR.search(_SPARQL_SKIP.sub(" ", sparql)))
    mods: dict = {}
    try:
        res.cypher, mods = t.run(pq.algebra)
    except _Unsupported as e:
        t.lost(f"Requête non traduite : {e}.")
        res.supported = False
    except Exception as e:  # noqa: BLE001
        t.lost(f"Erreur interne du traducteur ({type(e).__name__}: {e}) — requête non traduite.")
        res.supported = False
    res.query_form = t.form
    if res.cypher is not None and _EMPTY_MATCH.search(_CY_STRINGS.sub("''", res.cypher)):
        # garde générique (L53, DF-B12) : un MATCH sans motif est du Cypher invalide, il n'est jamais renvoyé
        t.lost("Traduction refusée : le Cypher produit contenait un MATCH sans motif (invalide) ; requête non traduite.")
        res.cypher = None
        res.supported = False
    if res.cypher is not None:
        # Query API Curiosity toujours tentée ; si une partie n'est pas exprimable (curiosity_ok faux), elle est marquée partielle
        try:
            res.curiosity = t.curiosity(mods)
            if not t.curiosity_ok and res.curiosity:
                res.curiosity += "\n// Traduction partielle : voir les notes [curiosity]."
        except _Unsupported as e:
            t.note("curiosity", f"Non traduit en Query API : {e}.")
        except Exception as e:  # noqa: BLE001
            t.note("curiosity", f"Erreur interne (Curiosity) : {type(e).__name__}: {e}.")
        try:
            res.graphql = t.graphql(mods)
        except Exception as e:  # noqa: BLE001
            t.note("graphql", f"Erreur interne (GraphQL) : {type(e).__name__}: {e}.")
        if pg.target == "curiosity":
            t.info("Cible Curiosity : noms de relations Cypher dérivés des edges par la convention N01 (UPPER_SNAKE).")
    res.notes = [f"[{lvl}] {txt}" for lvl, txt in t.notes]
    res.lossy = any(lvl == "perte" for lvl, _ in t.notes) or not res.supported
    res.variables = [str(v) for v in getattr(pq.algebra, "PV", []) or []]
    return res
