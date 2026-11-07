"""Générateur Neo4j 5 : PGModel → schema.cypher, ingest.cypher, validation.cypher, model.mmd, README-neo4j.md.

Propriétaire : agent neo4j. Contrat : docs/CONTRACTS.md §1 — `generate(pg, onto=None) -> dict[str, str]`.
Sortie déterministe (tri par nom / id). Syntaxe vérifiée sur le Cypher Manual 5 (voir skills/neo4j-schema-design).
"""
from __future__ import annotations

import re
from typing import Any, Iterable, Optional

from ontoforge.core.pg_model import EdgeType, Materialization, NodeType, PGModel, PGProperty, Validation
from ontoforge.mapping.profiles.neo4j import PG_TO_CYPHER_CAST, PG_TO_CYPHER_TYPE

__all__ = ["generate", "quote", "literal"]

IRI_MARKER = "urn:ontoforge:iri"

_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_RESERVED = {
    "ALL", "AND", "ANY", "AS", "ASC", "ASCENDING", "BY", "CALL", "CASE", "COLLECT", "CONSTRAINT", "CONTAINS",
    "COUNT", "CREATE", "DELETE", "DESC", "DESCENDING", "DETACH", "DISTINCT", "DROP", "ELSE", "END", "ENDS",
    "EXISTS", "FALSE", "FOR", "FOREACH", "FROM", "IN", "INDEX", "IS", "KEY", "LIMIT", "LOAD", "MATCH", "MERGE",
    "NODE", "NONE", "NOT", "NULL", "ON", "OPTIONAL", "OR", "ORDER", "REMOVE", "REQUIRE", "RETURN", "SET", "SKIP",
    "STARTS", "THEN", "TRUE", "UNION", "UNIQUE", "UNWIND", "USE", "WHEN", "WHERE", "WITH", "XOR", "YIELD",
}


# ---------------------------------------------------------------------------
# Utilitaires d'échappement
# ---------------------------------------------------------------------------
def quote(name: str) -> str:
    """Identifiant Cypher, échappé en backticks si nécessaire (`` pour un backtick littéral)."""
    if _IDENT.match(name) and name.upper() not in _RESERVED:
        return name
    return "`" + name.replace("`", "``") + "`"


def literal(v: Any) -> str:
    """Littéral Cypher (chaîne entre apostrophes, échappements \\ et ')."""
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return repr(v)
    if isinstance(v, (list, tuple)):
        return "[" + ", ".join(literal(x) for x in v) + "]"
    s = str(v).replace("\\", "\\\\").replace("'", "\\'")
    return "'" + s + "'"


def _snake(name: str) -> str:
    s = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", name)
    s = re.sub(r"[^A-Za-z0-9]+", "_", s).strip("_").lower()
    return s or "x"


def _comment(text: str, prefix: str = "// ") -> str:
    return "\n".join(prefix + line if line else prefix.rstrip() for line in text.splitlines())


def _commented(stmt: str) -> str:
    return "\n".join("// " + line for line in stmt.splitlines())


def _cypher_type(p: PGProperty) -> str:
    t = PG_TO_CYPHER_TYPE.get(p.type, "STRING")
    return f"LIST<{t} NOT NULL>" if p.is_list else t


def _cast(p: PGProperty, expr: str) -> str:
    fn = PG_TO_CYPHER_CAST.get(p.type)
    if p.is_list:
        return f"[x IN {expr} | {fn}(x)]" if fn else expr
    out = f"{fn}({expr})" if fn else expr
    if p.default is not None:
        out = f"coalesce({out}, {literal(p.default)})"
    return out


class _Names:
    """Noms de contraintes / index stables et uniques (espace de noms commun Neo4j)."""

    def __init__(self) -> None:
        self.used: set[str] = set()

    def get(self, base: str) -> str:
        name, i = base, 2
        while name in self.used:
            name, i = f"{base}_{i}", i + 1
        self.used.add(name)
        return name


# ---------------------------------------------------------------------------
# Analyse du modèle
# ---------------------------------------------------------------------------
class _Model:
    def __init__(self, pg: PGModel) -> None:
        self.pg = pg
        self.nodes: list[NodeType] = [pg.node_types[k] for k in sorted(pg.node_types)]
        self.edges: list[EdgeType] = sorted(pg.edge_types, key=lambda e: (e.name, e.from_, e.to))
        self.edge_by_name: dict[str, EdgeType] = {}
        for e in self.edges:
            self.edge_by_name.setdefault(e.name, e)

    def label(self, nt_name: Optional[str]) -> Optional[str]:
        if not nt_name:
            return None
        nt = self.pg.node_types.get(nt_name)
        return (nt.labels[0] if nt and nt.labels else nt_name)

    def ancestors(self, nt: NodeType) -> list[NodeType]:
        return [self.pg.node_types[l] for l in nt.labels[1:] if l in self.pg.node_types and l != nt.name]

    def inherited(self, nt: NodeType) -> dict[str, PGProperty]:
        out: dict[str, PGProperty] = {}
        for a in self.ancestors(nt):
            for p in a.properties:
                out.setdefault(p.name, p)
        return out

    def all_props(self, nt: NodeType) -> list[PGProperty]:
        own = {p.name for p in nt.properties}
        return list(nt.properties) + [p for n, p in sorted(self.inherited(nt).items()) if n not in own]

    def prop(self, nt_name: Optional[str], edge_name: Optional[str], prop: Optional[str]) -> Optional[PGProperty]:
        if not prop:
            return None
        if nt_name and nt_name in self.pg.node_types:
            for p in self.all_props(self.pg.node_types[nt_name]):
                if p.name == prop:
                    return p
        if edge_name and edge_name in self.edge_by_name:
            for p in self.edge_by_name[edge_name].properties:
                if p.name == prop:
                    return p
        return None

    def key(self, nt: NodeType) -> list[str]:
        if nt.key:
            return list(nt.key)
        for a in self.ancestors(nt):
            if a.key:
                return list(a.key)
        fb = self.iri_name(nt) or self._unique_required(nt)
        return [fb] if fb else []

    def iri_name(self, nt: Optional[NodeType]) -> Optional[str]:
        """Propriété portant l'IRI : marqueur source == IRI_MARKER (D-L4-02), repli insensible à la casse sur `uri`."""
        if nt is None:
            return None
        props = self.all_props(nt)
        for p in props:
            if p.source == IRI_MARKER:
                return p.name
        for p in props:
            if p.name.lower() == "uri":
                return p.name
        return None

    def _unique_required(self, nt: NodeType) -> Optional[str]:
        for p in self.all_props(nt):
            if p.unique and p.required and not p.is_list:
                return p.name
        return None

    def iri_expr(self, var: str, nt_name: Optional[str]) -> str:
        name = self.iri_name(self.pg.node_types.get(nt_name)) if nt_name else None
        return f"{var}.{quote(name)}" if name else "null"

    def key_inherited(self, nt: NodeType) -> bool:
        k = self.key(nt)
        return any(self.key(a) == k for a in self.ancestors(nt))

    def merge_label(self, nt: NodeType) -> str:
        """Label portant la contrainte de clé : le plus général des labels ayant la même clé."""
        k = self.key(nt)
        chosen = nt.labels[0] if nt.labels else nt.name
        for a in self.ancestors(nt):
            if self.key(a) == k:
                chosen = a.labels[0] if a.labels else a.name
        return chosen

    def node_pattern(self, var: str, nt_name: str, key_expr: str) -> Optional[str]:
        """Motif de correspondance par clé ; None si le type n'a aucune clé (jamais de motif vide)."""
        nt = self.pg.node_types.get(nt_name)
        if not nt or not self.key(nt):
            return None
        ml, primary = self.merge_label(nt), (nt.labels[0] if nt.labels else nt.name)
        labels = ":" + quote(ml) + ("" if ml == primary else ":" + quote(primary))
        k = self.key(nt)
        props = ", ".join(f"{quote(x)}: {self._key_cast(nt, x, f'{key_expr}.{quote(x)}')}" for x in k)
        return f"({var}{labels} {{{props}}})"

    def _key_cast(self, nt: NodeType, prop: str, expr: str) -> str:
        p = next((q for q in self.all_props(nt) if q.name == prop), None)
        return _cast(p.model_copy(update={"default": None}), expr) if p else expr


# ---------------------------------------------------------------------------
# schema.cypher
# ---------------------------------------------------------------------------
def _schema(m: _Model) -> str:
    names = _Names()
    community: list[str] = []
    enterprise: list[str] = []
    indexes: list[str] = []
    notes: list[str] = []

    for nt in m.nodes:
        lab = nt.labels[0] if nt.labels else nt.name
        s, ql = _snake(lab), quote(lab)
        pat = f"FOR (n:{ql})"
        inh = m.inherited(nt)
        key = nt.key if nt.key else []
        if key and m.key_inherited(nt):
            key = []  # clé déjà contrainte sur le label parent (multi-labels)
        uniq_done: set[str] = set()
        if key:
            req = ", ".join(f"n.{quote(k)}" for k in key)
            req = req if len(key) == 1 else f"({req})"
            uname = names.get(f"{s}_key_unique")
            community.append(f"// clé {lab}({', '.join(key)}) — Community : UNIQUE (Enterprise : NODE KEY ci-dessous)\n"
                             f"CREATE CONSTRAINT {uname} IF NOT EXISTS {pat} REQUIRE {req} IS UNIQUE;")
            kname = names.get(f"{s}_node_key")
            enterprise.append(f"DROP CONSTRAINT {uname} IF EXISTS;\n"
                              f"CREATE CONSTRAINT {kname} IF NOT EXISTS {pat} REQUIRE {req} IS NODE KEY;")
            if len(key) == 1:
                uniq_done.add(key[0])
        for p in nt.properties:
            qp = quote(p.name)
            parent = inh.get(p.name)
            if p.unique and p.name not in uniq_done and not (parent and parent.unique):
                community.append(f"CREATE CONSTRAINT {names.get(f'{s}_{_snake(p.name)}_unique')} IF NOT EXISTS "
                                 f"{pat} REQUIRE n.{qp} IS UNIQUE;")
            if p.required and p.name not in key and not (parent and parent.required):
                enterprise.append(f"CREATE CONSTRAINT {names.get(f'{s}_{_snake(p.name)}_not_null')} IF NOT EXISTS "
                                  f"{pat} REQUIRE n.{qp} IS NOT NULL;")
            if not parent:
                enterprise.append(f"CREATE CONSTRAINT {names.get(f'{s}_{_snake(p.name)}_type')} IF NOT EXISTS "
                                  f"{pat} REQUIRE n.{qp} IS :: {_cypher_type(p)};")
            if p.indexed and not p.unique and key != [p.name]:
                kind = "TEXT INDEX" if (p.type == "String" and not p.is_list and p.lang) else "INDEX"
                suffix = "text" if kind == "TEXT INDEX" else "range"
                indexes.append(f"// index {lab}.{p.name} : propriété marquée « indexed »"
                               + (f" (source : {p.source})" if p.source else "") + "\n"
                               f"CREATE {kind} {names.get(f'{s}_{_snake(p.name)}_{suffix}')} IF NOT EXISTS "
                               f"{pat} ON (n.{qp});")
            if p.enum:
                notes.append(f"// ENUM {lab}.{p.name} ∈ {{{', '.join(p.enum)}}} — pas de contrainte native → validation.cypher")
            if p.pattern:
                notes.append(f"// PATTERN {lab}.{p.name} =~ {p.pattern} — pas de contrainte native → validation.cypher")

    for e in m.edges:
        s, qt = "rel_" + _snake(e.name), quote(e.name)
        pat = f"FOR ()-[r:{qt}]-()"
        seen: set[str] = set()
        for p in e.properties:
            if p.name in seen:
                continue
            seen.add(p.name)
            qp = quote(p.name)
            if p.unique:
                community.append(f"CREATE CONSTRAINT {names.get(f'{s}_{_snake(p.name)}_unique')} IF NOT EXISTS "
                                 f"{pat} REQUIRE r.{qp} IS UNIQUE;")
            if p.required:
                enterprise.append(f"CREATE CONSTRAINT {names.get(f'{s}_{_snake(p.name)}_not_null')} IF NOT EXISTS "
                                  f"{pat} REQUIRE r.{qp} IS NOT NULL;")
            enterprise.append(f"CREATE CONSTRAINT {names.get(f'{s}_{_snake(p.name)}_type')} IF NOT EXISTS "
                              f"{pat} REQUIRE r.{qp} IS :: {_cypher_type(p)};")
            if p.indexed and not p.unique:
                indexes.append(f"// index [:{e.name}].{p.name} : propriété marquée « indexed »\n"
                               f"CREATE INDEX {names.get(f'{s}_{_snake(p.name)}_range')} IF NOT EXISTS "
                               f"{pat} ON (r.{qp});")
        c = e.cardinality
        if c.out != "0..*" or c.in_ != "0..*":
            notes.append(f"// CARDINALITY ({e.from_})-[:{e.name}]->({e.to}) out={c.out} in={c.in_} — "
                         f"pas de contrainte de cardinalité de relation → validation.cypher")
        if e.symmetric or not e.directed:
            notes.append(f"// SYMMETRIC {e.name} — un seul sens stocké, interroger avec -[:{e.name}]- (non orienté)")
        if e.derived:
            notes.append(f"// DERIVED {e.name} — relation matérialisée, recalculée par validation.cypher")

    # Plein texte (optionnel) : propriétés textuelles multilingues / de nommage
    ft_labels: list[str] = []
    ft_props: list[str] = []
    for nt in m.nodes:
        texty = [p.name for p in nt.properties if p.type == "String" and not p.is_list
                 and (p.lang or p.name in {"name", "fullName", "label", "title", "description"})]
        if texty:
            ft_labels.append(nt.labels[0] if nt.labels else nt.name)
            ft_props.extend(x for x in texty if x not in ft_props)
    fulltext = ""
    if ft_labels:
        fname = names.get(_snake(m.pg.meta.name or "model") + "_fulltext")
        fulltext = (f"CREATE FULLTEXT INDEX {fname} IF NOT EXISTS FOR (n:{'|'.join(quote(l) for l in ft_labels)}) "
                    f"ON EACH [{', '.join('n.' + quote(p) for p in ft_props)}];")

    lost = [f for f in sorted(m.pg.findings, key=lambda f: f.id) if f.severity == "lost"]
    lost_lines = []
    for f in lost:
        opt = f.chosen or f.recommended
        label = next((o.label for o in f.options if o.id == opt), opt) if opt else "non arbitré"
        short = re.split(r"[#/]", f.subject.rstrip("/#"))[-1] or f.subject
        lost_lines.append(f"// LOST {f.id} — {f.title} — sujet : {short} <{f.subject}> — compensation : {label}")

    out = [_header(m.pg, "schema.cypher", "Contraintes et index Neo4j 5 (idempotents, IF NOT EXISTS).\n"
                   "Exécuter avant ingest.cypher. Requiert Neo4j 5.7+ (Community) ; section Enterprise : 5.11+.")]
    out.append("// ===== 1. Contraintes Community + Enterprise =====")
    out.extend(community)
    out.append("// ===== 2. Index =====")
    out.extend(indexes or ["// (aucun index supplémentaire : les contraintes UNIQUE créent leur index)"])
    out.append("// ===== 3. Plein texte (optionnel, interrogé par db.index.fulltext.queryNodes) =====")
    out.append(fulltext or "// (aucune propriété textuelle)")
    out.append("// ===== 4. Enterprise Edition uniquement (décommenter) =====\n"
               "// NODE KEY remplace la contrainte UNIQUE de même schéma (une seule autorisée par schéma) ;\n"
               "// IS NOT NULL et IS :: <TYPE> (5.9+, LIST 5.10+) sont refusés par Community Edition.")
    out.extend(_commented(s) for s in enterprise)
    out.append("// ===== 5. Non contraignable nativement =====")
    out.extend(notes or ["// (rien)"])
    out.append("// ===== 6. Pertes (constats lost) =====")
    out.extend(lost_lines or ["// (aucune)"])
    return "\n\n".join(out) + "\n"


def _header(pg: PGModel, fname: str, text: str) -> str:
    meta = f"{pg.meta.name or 'model'}" + (f" <{pg.meta.iri}>" if pg.meta.iri else "")
    return _comment(f"{fname} — généré par OntoForge {pg.meta.ontoforge_version} — {meta}\n{text}")


# ---------------------------------------------------------------------------
# ingest.cypher
# ---------------------------------------------------------------------------
def _ingest(m: _Model) -> str:
    out = [_header(m.pg, "ingest.cypher",
                   "Ingestion idempotente : un paramètre $rows (liste de maps) par instruction, nœuds puis relations.\n"
                   "Lots conseillés : 1 000 à 10 000 lignes par transaction côté driver ; en une seule requête :\n"
                   "  UNWIND $rows AS row CALL (row) { … } IN TRANSACTIONS OF 1000 ROWS  (Neo4j 5.23+ ; avant : CALL { WITH row … })\n"
                   "Les dates sont attendues en ISO 8601 (chaînes), les durées en ISO 8601 (P1DT2H).\n"
                   "Une valeur absente (null) supprime la propriété : rechargement complet par type.")]
    out.append("// ===== Nœuds =====")
    for nt in m.nodes:
        lab = nt.labels[0] if nt.labels else nt.name
        if nt.abstract:
            out.append(f"// :{lab} est abstrait (label secondaire porté par ses sous-types) : pas d'ingestion directe.")
            continue
        key = m.key(nt)
        props = m.all_props(nt)
        shape = ", ".join(p.name + ("[]" if p.is_list else "") for p in props)
        lines = [f"// :{':'.join(nt.labels or [nt.name])} — $rows : [{{{shape}}}]"]
        if not key:
            lines.append("// ATTENTION : aucune clé → CREATE (non idempotent)")
            lines.append("UNWIND $rows AS row")
            lines.append(f"CREATE (n:{quote(lab)})")
        else:
            lines.append("UNWIND $rows AS row")
            ml = m.merge_label(nt)
            kp = ", ".join(f"{quote(k)}: {m._key_cast(nt, k, 'row.' + quote(k))}" for k in key)
            lines.append(f"MERGE (n:{quote(ml)} {{{kp}}})")
        extra = [l for l in (nt.labels or [nt.name]) if l != (m.merge_label(nt) if key else lab)]
        if extra:
            lines.append("SET n" + "".join(":" + quote(l) for l in extra))
        sets = [f"n.{quote(p.name)} = {_cast(p, 'row.' + quote(p.name))}" for p in props if p.name not in key]
        if sets:
            lines.append("SET " + ",\n    ".join(sets))
        out.append("\n".join(lines) + ";")

    out.append("// ===== Relations =====")
    for e in m.edges:
        if e.derived:
            out.append(f"// [:{e.name}] est dérivée (matérialisée par validation.cypher) : pas d'ingestion.")
            continue
        props = e.properties
        shape = ", ".join(["from{…clé " + e.from_ + "}", "to{…clé " + e.to + "}"] + [p.name for p in props])
        lines = [f"// ({e.from_})-[:{e.name}]->({e.to}) — $rows : [{{{shape}}}]"]
        lines.append("UNWIND $rows AS row")
        pa, pb = m.node_pattern("a", e.from_, "row.from"), m.node_pattern("b", e.to, "row.to")
        if pa is None or pb is None:
            missing = [n for n, pt in ((e.from_, pa), (e.to, pb)) if pt is None]
            out.append("// À COMPLÉTER : relation non ingérée, le type " + ", ".join(missing) +
                       " n'a ni clé ni propriété IRI/unique : un motif vide apparierait tous les nœuds du label.\n"
                       + _commented("\n".join(lines) + "\nMATCH (a), (b) // clé à définir\nMERGE (a)-[r:" + quote(e.name) + "]->(b);"))
            continue
        lines.append("MATCH " + pa)
        lines.append("MATCH " + pb)
        mkeys = [p for p in props if p.unique]
        mk = (" {" + ", ".join(f"{quote(p.name)}: {_cast(p, 'row.' + quote(p.name))}" for p in mkeys) + "}") if mkeys else ""
        arrow = f"-[r:{quote(e.name)}{mk}]-" + ("" if (e.symmetric or not e.directed) else ">")
        lines.append(f"MERGE (a){arrow}(b)")
        sets = [f"r.{quote(p.name)} = {_cast(p, 'row.' + quote(p.name))}" for p in props if not p.unique]
        if sets:
            lines.append("SET " + ",\n    ".join(sets))
        if e.symmetric or not e.directed:
            lines.insert(1, "// symétrique : MERGE non orienté (crée a→b si aucun sens n'existe)")
        out.append("\n".join(lines) + ";")
    return "\n\n".join(out) + "\n"


# ---------------------------------------------------------------------------
# validation.cypher
# ---------------------------------------------------------------------------
def _ret(v: Validation, var: str, detail: str, iri: str = "null") -> str:
    return (f"RETURN {literal(v.id)} AS validation, {literal(v.severity)} AS severity, elementId({var}) AS focus, "
            f"{iri} AS uri, {detail} AS detail")


def _card_bounds(v: Validation, e: Optional[EdgeType]) -> tuple[Optional[int], Optional[int]]:
    lo, hi = v.params.get("min"), v.params.get("max")
    if lo is None and hi is None and e is not None:
        c = e.cardinality.out if v.params.get("direction", "out") == "out" else e.cardinality.in_
        lo = {"1": 1, "1..*": 1}.get(c)
        hi = {"1": 1, "0..1": 1}.get(c)
    return lo, hi


def _rel_pat(var: str, edge: str, direction: str = "out", target: Optional[str] = None) -> str:
    tgt = f"(:{quote(target)})" if target else "()"
    if direction == "in":
        return f"({var})<-[:{quote(edge)}]-{tgt}"
    return f"({var})-[:{quote(edge)}]->{tgt}"


def _xsd_regex(pattern: str) -> str:
    """sh:pattern / xsd:pattern → =~ (Cypher : correspondance de la chaîne entière, regex Java)."""
    p = pattern
    p = p[1:] if p.startswith("^") else ".*" + p
    p = p[:-1] if p.endswith("$") and not p.endswith("\\$") else p + ".*"
    return p


def _validation(m: _Model, v: Validation) -> str:
    head = f"// {v.id} [{v.kind}] {v.description}" + (f" (source : {v.source})" if v.source else "")
    e = m.edge_by_name.get(v.edge_type) if v.edge_type else None
    nt_name = v.node_type or (e.from_ if e else None)
    lab = m.label(nt_name)
    prop = m.prop(v.node_type, v.edge_type, v.property)
    rel_scope = bool(v.property and v.edge_type and not v.node_type)
    if rel_scope:
        var, match = "r", f"MATCH ()-[r:{quote(v.edge_type)}]->()"
    else:
        var, match = "n", (f"MATCH (n:{quote(lab)})" if lab else "MATCH (n)")
    qp = quote(v.property) if v.property else None
    acc = f"{var}.{qp}" if qp else None
    k = v.kind
    body: Optional[str] = None
    iri_node = nt_name if not rel_scope else None

    def ret(var_: str, detail: str) -> str:
        return _ret(v, var_, detail, m.iri_expr(var_, iri_node) if var_ == "n" or not rel_scope else "null")

    if k in ("cardinality", "functional") and v.edge_type and not (k == "functional" and v.property):
        lo, hi = _card_bounds(v, e)
        if k == "functional":
            lo, hi = None, 1
        pat = _rel_pat("n", v.edge_type, v.params.get("direction", "out"), v.params.get("target"))
        conds = ([f"cnt < {lo}"] if lo else []) + ([f"cnt > {hi}"] if hi is not None else [])
        if conds:
            body = (f"{match}\nWITH n, COUNT {{ {pat} }} AS cnt\nWHERE {' OR '.join(conds)}\n"
                    + ret("n", "'count=' + toString(cnt)"))
    elif k == "functional" and acc:
        body = f"{match}\nWHERE {acc} IS :: LIST<ANY> AND size({acc}) > 1\n" + ret(var, f"size({acc})")
    elif k == "existence":
        if acc:
            body = f"{match}\nWHERE {acc} IS NULL\n" + ret(var, literal(f"{v.property} absent"))
        elif v.edge_type:
            pat = _rel_pat("n", v.edge_type, v.params.get("direction", "out"), v.params.get("target"))
            body = f"{match}\nWHERE NOT EXISTS {{ {pat} }}\n" + ret("n", literal(f"aucune relation {v.edge_type}"))
    elif k == "disjoint":
        others = list(v.params.get("with") or v.params.get("targets") or [])
        others = [o for o in others if o != nt_name]
        if lab and others:
            cond = " OR ".join(f"n:{quote(m.label(o) or o)}" for o in others)
            body = f"{match}\nWHERE {cond}\n" + ret("n", "labels(n)")
    elif k == "allValuesFrom":
        tgt = v.params.get("target")
        if v.edge_type and tgt:
            body = (f"MATCH (n{':' + quote(lab) if lab else ''})-[:{quote(v.edge_type)}]->(m)\n"
                    f"WHERE NOT m:{quote(m.label(tgt) or tgt)}\n" + ret("n", "labels(m)"))
        elif acc and v.params.get("type"):
            body = f"{match}\nWHERE {acc} IS NOT NULL AND NOT {acc} IS :: {v.params['type']}\n" + ret(var, acc)
    elif k == "enum" and acc:
        values = v.params.get("values") or (prop.enum if prop else [])
        if prop is not None and prop.is_list:
            body = (f"{match}\nWHERE any(x IN coalesce({acc}, []) WHERE NOT x IN {literal(values)})\n"
                    + ret(var, acc))
        else:
            body = f"{match}\nWHERE {acc} IS NOT NULL AND NOT {acc} IN {literal(values)}\n" + ret(var, acc)
    elif k == "irreflexive" and v.edge_type:
        body = (f"MATCH (n{':' + quote(lab) if lab else ''})-[r:{quote(v.edge_type)}]->(n)\n"
                + ret("n", literal("boucle " + v.edge_type)))
    elif k == "asymmetric" and v.edge_type:
        t = quote(v.edge_type)
        body = (f"MATCH (n{':' + quote(lab) if lab else ''})-[:{t}]->(m)-[:{t}]->(n)\n"
                f"WHERE elementId(n) < elementId(m)\n" + ret("n", "elementId(m)"))
    elif k == "hasValue":
        val = v.params.get("value")
        if acc:
            body = f"{match}\nWHERE {acc} IS NULL OR {acc} <> {literal(val)}\n" + ret(var, acc)
        elif v.edge_type:
            tgt_iri = m.iri_name(m.pg.node_types.get(e.to)) if e else None
            if tgt_iri:
                body = (f"{match}\nWHERE NOT EXISTS {{ (n)-[:{quote(v.edge_type)}]->({{{quote(tgt_iri)}: {literal(val)}}}) }}\n"
                        + ret("n", literal(f"{v.edge_type} ≠ {val}")))
    elif k == "pattern" and acc:
        pattern = v.params.get("pattern") or (prop.pattern if prop else None)
        if pattern:
            body = (f"// regex SHACL/XSD convertie en correspondance complète Java : {pattern}\n"
                    f"{match}\nWHERE {acc} IS NOT NULL AND NOT toString({acc}) =~ {literal(_xsd_regex(pattern))}\n"
                    + ret(var, acc))
    elif k == "range" and acc:
        conds = []
        for key, op in (("min", "<"), ("minInclusive", "<"), ("max", ">"), ("maxInclusive", ">"),
                        ("minExclusive", "<="), ("maxExclusive", ">=")):
            if key in v.params:
                conds.append(f"{acc} {op} {literal(v.params[key])}")
        if conds:
            body = f"{match}\nWHERE {' OR '.join(conds)}\n" + ret(var, acc)
    elif k == "closed" and lab:
        allowed = v.params.get("allowed")
        if allowed is None and nt_name in m.pg.node_types:
            allowed = sorted(p.name for p in m.all_props(m.pg.node_types[nt_name]))
        body = (f"{match}\nWITH n, [k IN keys(n) WHERE NOT k IN {literal(sorted(allowed or []))}] AS extra\n"
                f"WHERE size(extra) > 0\n" + ret("n", "extra"))

    if body is None:
        tpl = f"{match}\nWHERE /* À COMPLÉTER : {v.description} */ false\n" + ret(var, "null")
        return head + "\n// Pas de traduction automatique pour ce cas : patron à compléter.\n" + _commented(tpl)
    return head + "\n" + body + ";"


def _materialization(m: _Model, x: Materialization) -> str:
    head = f"// {x.id} [{x.kind}] {x.description}" + (f" (source : {x.source})" if x.source else "")
    tgt = m.edge_by_name.get(x.edge_type) if x.edge_type else None
    k = x.kind
    stmts: list[str] = []
    pattern = ""
    by_source = {e.source: e.name for e in reversed(m.edges) if e.source and not e.derived}
    x = x.model_copy(update={"chain": [c if c in m.edge_by_name else by_source.get(c, c) for c in x.chain]})

    def from_to(edge: Optional[EdgeType]) -> tuple[str, str]:
        if not edge:
            return "", ""
        return ":" + quote(m.label(edge.from_) or edge.from_), ":" + quote(m.label(edge.to) or edge.to)

    if k == "transitiveClosure":
        base = x.chain[0] if x.chain else x.edge_type
        be = m.edge_by_name.get(base)
        fl, tl = from_to(be)
        pattern = f"MATCH (a{fl})-[:{quote(base)}*1..]->(b{tl}) RETURN a, b"
        if tgt and tgt.derived and base != x.edge_type:
            d = quote(tgt.name)
            stmts = [f"MATCH ()-[r:{d}]->() DELETE r;",
                     f"MATCH (a{fl})-[:{quote(base)}*1..]->(b{tl})\nWHERE a <> b\nMERGE (a)-[:{d}]->(b);"]
    elif k == "propertyChain" and x.chain:
        first = m.edge_by_name.get(x.chain[0])
        last = m.edge_by_name.get(x.chain[-1])
        fl = from_to(first)[0]
        tl = from_to(last)[1]
        path = "".join(f"-[:{quote(c)}]->" + ("()" if i < len(x.chain) - 1 else "")
                       for i, c in enumerate(x.chain))
        pattern = f"MATCH (a{fl}){path}(b{tl}) RETURN a, b"
        if tgt and tgt.derived:
            d = quote(tgt.name)
            stmts = [f"MATCH ()-[r:{d}]->() DELETE r;", f"MATCH (a{fl}){path}(b{tl})\nMERGE (a)-[:{d}]->(b);"]
    elif k == "superProperty" and x.edge_type and x.parent:
        fl, tl = from_to(tgt)
        pattern = f"MATCH (a)-[:{quote(x.edge_type)}|{quote(x.parent)}]->(b) RETURN a, b"
        pe = m.edge_by_name.get(x.parent)
        if pe and pe.derived:
            stmts = [f"MATCH ()-[r:{quote(x.parent)}]->() DELETE r;",
                     f"MATCH (a{fl})-[:{quote(x.edge_type)}]->(b{tl})\nMERGE (a)-[:{quote(x.parent)}]->(b);"]
        elif pe:
            stmts = [f"MATCH (a{fl})-[:{quote(x.edge_type)}]->(b{tl})\nMERGE (a)-[:{quote(x.parent)}]->(b);"]
    elif k == "classification" and x.node_type:
        parent = m.label(x.parent) if x.parent else None
        pl = ":" + quote(parent) if parent else ""
        tpl = (f"MATCH (n:{quote(x.node_type)}) REMOVE n:{quote(x.node_type)};\n"
               f"MATCH (n{pl})\nWHERE /* À COMPLÉTER : {x.definition or x.description} */ false\n"
               f"SET n:{quote(x.node_type)};")
        return head + "\n// Classification (pas de raisonneur) : condition à écrire puis rejouer après ingestion.\n" + _commented(tpl)
    elif k == "inverse" and x.edge_type:
        pattern = f"MATCH (b)<-[:{quote(x.edge_type)}]-(a) RETURN b, a  // lecture de {x.parent or 'l’inverse'} sans le stocker"
    elif k == "symmetric" and x.edge_type:
        t = quote(x.edge_type)
        pattern = f"MATCH (a)-[:{t}]-(b) RETURN a, b"
        stmts = [f"// contrôle : la relation ne doit être stockée que dans un sens\n"
                 f"MATCH (a)-[r1:{t}]->(b)-[r2:{t}]->(a)\nWHERE elementId(r1) < elementId(r2)\n"
                 f"RETURN {literal(x.id)} AS validation, 'Warning' AS severity, elementId(r2) AS focus, "
                 f"{m.iri_expr('a', tgt.from_ if tgt else None)} AS uri, 'doublon symétrique' AS detail;"]
    elif k == "sameAs":
        pattern = ("MATCH (a), (b) WHERE a.`uri` IN b.sameAs  // adapter au nom de la propriété IRI\n"
                   "CALL apoc.refactor.mergeNodes([a, b]) YIELD node RETURN node  // APOC — À VÉRIFIER")

    parts = [head]
    if pattern:
        parts.append(_comment("patron : " + pattern))
    if stmts:
        parts.append("\n".join(stmts))
    elif not pattern:
        parts.append("// (pas de patron généré)")
    return "\n".join(parts)


def _validations(m: _Model) -> str:
    out = [_header(m.pg, "validation.cypher",
                   "Partie A : requêtes de détection (une par validation) — chacune retourne\n"
                   "  validation, severity, focus (elementId), uri, detail ; 0 ligne = conforme.\n"
                   "Partie B : matérialisations / patrons de requête (à rejouer après chaque ingestion).\n"
                   "COUNT { } et EXISTS { } : Neo4j 5 ; IS :: : prédicat de type Cypher 5.")]
    out.append("// ===== A. Validations =====")
    for v in sorted(m.pg.validations, key=lambda v: v.id):
        out.append(_validation(m, v))
    out.append("// ===== B. Matérialisations et patrons =====")
    for x in sorted(m.pg.materializations, key=lambda x: x.id):
        out.append(_materialization(m, x))
    return "\n\n".join(out) + "\n"


# ---------------------------------------------------------------------------
# model.mmd (Mermaid classDiagram)
# ---------------------------------------------------------------------------
def _mmd_id(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_]", "_", name)


def _mermaid(m: _Model) -> str:
    lines = ["classDiagram", "  direction LR",
             "  %% généré par OntoForge — membres soulignés = clé ; --> relation ; .. > relation dérivée"]
    for nt in m.nodes:
        key = set(m.key(nt)) if nt.key else set()
        lines.append(f"  class {_mmd_id(nt.name)} {{")
        if nt.abstract:
            lines.append("    <<abstract>>")
        for p in nt.properties:
            t = f"List~{p.type}~" if p.is_list else p.type
            lines.append(f"    +{t} {p.name}" + ("$" if p.name in key else ""))
        lines.append("  }")
        if nt.icon:
            lines.append(f'  note for {_mmd_id(nt.name)} "icône : {nt.icon}"')
    for nt in m.nodes:
        for a in m.ancestors(nt):
            lines.append(f"  {_mmd_id(a.name)} <|-- {_mmd_id(nt.name)}")
    for e in m.edges:
        label = e.name + (f" ({', '.join(p.name for p in e.properties)})" if e.properties else "")
        arrow = "..>" if e.derived else ("--" if (e.symmetric or not e.directed) else "-->")
        lines.append(f"  {_mmd_id(e.from_)} {arrow} {_mmd_id(e.to)} : {label}")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# README-neo4j.md
# ---------------------------------------------------------------------------
def _readme(m: _Model, files: dict[str, str]) -> str:
    pg = m.pg
    s = pg.summary()
    n_comm = sum(1 for l in files["schema.cypher"].splitlines() if l.startswith("CREATE CONSTRAINT"))
    n_ent = sum(1 for l in files["schema.cypher"].splitlines() if l.startswith("// CREATE CONSTRAINT"))
    n_idx = sum(1 for l in files["schema.cypher"].splitlines() if re.match(r"CREATE (TEXT |FULLTEXT )?INDEX", l))
    rows = ["| Label(s) | Clé | Propriétés |", "|---|---|---|"]
    for nt in m.nodes:
        labels = ":" + ":".join(nt.labels or [nt.name]) + (" *(abstrait)*" if nt.abstract else "")
        rows.append(f"| `{labels}` | {', '.join(m.key(nt)) or '—'} | {', '.join(p.name for p in nt.properties)} |")
    rels = ["| Relation | De → Vers | Propriétés | Remarque |", "|---|---|---|---|"]
    for e in m.edges:
        rem = ", ".join(x for x in ("dérivée" if e.derived else "", "symétrique" if e.symmetric else "",
                                    f"card. {e.cardinality.out}" if e.cardinality.out != "0..*" else "") if x)
        rels.append(f"| `:{e.name}` | {e.from_} → {e.to} | {', '.join(p.name for p in e.properties) or '—'} | {rem or '—'} |")
    lost = [f"- `{f.id}` — {f.title} (choix : {f.chosen or f.recommended or 'non arbitré'})"
            for f in sorted(pg.findings, key=lambda f: f.id) if f.severity == "lost"]
    pending = [f"- `{f.id}` — {f.title}" for f in sorted(pg.findings, key=lambda f: f.id)
               if f.severity in ("review", "lost") and not f.chosen]
    return f"""# Schéma Neo4j — {pg.meta.name or 'modèle'}

Généré par OntoForge {pg.meta.ontoforge_version}{' depuis `' + pg.meta.iri + '`' if pg.meta.iri else ''}.
Constats : {s['auto']} auto, {s['review']} à arbitrer, {s['lost']} perdus ({s['decided']} décidés, {s['pending']} en attente).

## Fichiers
| Fichier | Rôle |
|---|---|
| `schema.cypher` | {n_comm} contraintes actives (Community), {n_idx} index, {n_ent} contraintes Enterprise commentées |
| `ingest.cypher` | une instruction `UNWIND $rows … MERGE … SET` par type de nœud puis par relation |
| `validation.cypher` | {len(pg.validations)} requêtes de détection + {len(pg.materializations)} matérialisations / patrons |
| `model.mmd` | diagramme Mermaid (classDiagram) |

## Ordre d'exécution
1. `schema.cypher` (cypher-shell : `cypher-shell -f schema.cypher`) — avant toute donnée.
2. `ingest.cypher` — chaque instruction reçoit `$rows` (driver : lots de 1 000 à 10 000 lignes) ; nœuds avant relations.
3. `validation.cypher` partie B (matérialisations), puis partie A : chaque requête doit retourner 0 ligne.

## Community vs Enterprise
- Community : contraintes `IS UNIQUE` (nœuds ; relations depuis 5.7), index RANGE / TEXT / FULLTEXT.
- Enterprise : `IS NODE KEY`, `IS NOT NULL`, `IS :: <TYPE>` (5.9+, listes 5.10+) — section 4 de `schema.cypher`, à décommenter.
  En Community, existence et types sont contrôlés par `validation.cypher`.
- Jamais natif : cardinalité de relation, disjonction de labels, énumérations, regex → `validation.cypher`.

## Nœuds
{chr(10).join(rows)}

## Relations
{chr(10).join(rels)}

## Pertes (constats `lost`)
{chr(10).join(lost) or '- aucune'}

## Constats non arbitrés
{chr(10).join(pending) or '- aucun'}
"""


# ---------------------------------------------------------------------------
def generate(pg: PGModel, onto: Any = None) -> dict[str, str]:
    """PGModel → fichiers Neo4j (nom → contenu). `onto` est accepté pour le contrat mais non utilisé."""
    m = _Model(pg)
    files = {
        "schema.cypher": _schema(m),
        "ingest.cypher": _ingest(m),
        "validation.cypher": _validations(m),
        "model.mmd": _mermaid(m),
    }
    files["README-neo4j.md"] = _readme(m, files)
    return dict(sorted(files.items()))
