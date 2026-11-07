"""Générateur GraphQL (SDL) depuis un PGModel — propriétaire : query.

`generate(pg, onto=None) -> {"schema.graphql": ..., "README-graphql.md": ...}`

Règles :
- un type objet par NodeType ; champs scalaires typés (PGType → scalaire GraphQL, scalaires custom Date/DateTime…),
  listes (`is_list`), non-null (`required`) ; enums pour les propriétés à valeurs énumérées ;
- héritage aplati (NodeType.discriminator) → `interface <Type>` + un type concret par valeur du discriminant
  (+ `Base<Type>` si le type n'est pas abstrait) ; avec l'ontologie, les propriétés propres à une sous-classe
  ne vont que sur le type concret correspondant ;
- relations dans les deux sens : champ aller sur `from`, champ retour (nom = `reverse`) sur `to` ;
  cible neo4j → directives `@relationship(type:, direction:)` de la Neo4j GraphQL Library (À VÉRIFIER) ;
- `type Query` : lookup par clé (`vehicle(vin: String!)`) et liste paginée (`vehicles(first:, offset:)`).
Sortie déterministe (tri par nom).
"""
from __future__ import annotations

import re
from typing import Optional

from ..core.onto_model import OntoModel, local_name
from ..core.pg_model import EdgeType, NodeType, PGModel, PGProperty

SCALAR_MAP = {"String": "String", "Integer": "Int", "Float": "Float", "Decimal": "Decimal", "Boolean": "Boolean", "Date": "Date",
              "DateTime": "DateTime", "LocalDateTime": "LocalDateTime", "Time": "Time", "Duration": "Duration"}
CUSTOM_SCALARS = {
    "Decimal": "Décimal exact sérialisé en chaîne (\"12.50\") — xsd:decimal",
    "Date": "Date ISO 8601 (AAAA-MM-JJ) — xsd:date",
    "DateTime": "Date-heure ISO 8601 avec fuseau — xsd:dateTime",
    "LocalDateTime": "Date-heure ISO 8601 sans fuseau",
    "Time": "Heure ISO 8601 — xsd:time",
    "Duration": "Durée ISO 8601 (PnYnMnDTnHnMnS) — xsd:duration",
}
_NAME_RE = re.compile(r"[^_0-9A-Za-z]")


# ---- conventions de nommage (partagées avec queries/translate.py) ------------------------------
def _words(name: str) -> list[str]:
    name = _NAME_RE.sub("_", name)
    parts: list[str] = []
    for chunk in name.split("_"):
        parts += re.findall(r"[A-Z]+(?=[A-Z][a-z]|\d|$)|[A-Z]?[a-z]+|\d+|[A-Z]+", chunk)
    return [p for p in parts if p]


def pascal(name: str) -> str:
    w = _words(name)
    return "".join(x[:1].upper() + x[1:].lower() if x.isupper() and len(x) > 1 else x[:1].upper() + x[1:] for x in w) or "X"


def camel(name: str) -> str:
    p = pascal(name)
    m = re.match(r"^[A-Z]+(?=[A-Z][a-z])|^[A-Z]+$|^[A-Z]", p)
    return (p[: m.end()].lower() + p[m.end():]) if m else p


def upper_snake(name: str) -> str:
    return "_".join(w.upper() for w in _words(name)) or "X"


def plural(name: str) -> str:
    if re.search(r"[^aeiou]y$", name):
        return name[:-1] + "ies"
    if re.search(r"(s|x|z|ch|sh)$", name):
        return name + "es"
    return name + "s"


def gql_name(name: str) -> str:
    n = _NAME_RE.sub("_", name)
    return ("_" + n) if (not n or n[0].isdigit()) else n


def enum_value(v: str) -> str:
    n = _NAME_RE.sub("_", str(v)).upper().strip("_") or "EMPTY"
    if n[0].isdigit():
        n = "_" + n
    return "_TRUE" if n in ("TRUE", "FALSE", "NULL") and False else n


def edge_cypher_type(pg: PGModel, e: EdgeType) -> str:
    return e.name if pg.target == "neo4j" else upper_snake(e.name)


def relation_fields(pg: PGModel) -> dict[int, tuple[str, Optional[str]]]:
    """Index d'edge → (nom du champ aller sur `from`, nom du champ retour sur `to` ou None si symétrique/boucle
    identique). Les noms évitent toute collision avec les propriétés et les autres relations."""
    used: dict[str, set[str]] = {n: {p.name for p in nt.properties} for n, nt in pg.node_types.items()}
    out: dict[int, tuple[str, Optional[str]]] = {}

    def alloc(node: str, base: str) -> str:
        s = used.setdefault(node, set())
        name, i = base, 2
        while name in s:
            name, i = f"{base}{i}", i + 1
        s.add(name)
        return name

    for i, e in sorted(enumerate(pg.edge_types), key=lambda t: (t[1].from_, t[1].name, t[1].to)):
        fwd = alloc(e.from_, camel(e.name))
        if e.symmetric and e.from_ == e.to:
            out[i] = (fwd, None)
            continue
        rev_base = camel(e.reverse) if e.reverse else camel(e.name) + "Inverse"
        out[i] = (fwd, alloc(e.to, rev_base))
    return out


def lookup_field(nt_name: str) -> str:
    return camel(nt_name)


def list_field(nt_name: str) -> str:
    return plural(camel(nt_name))


# ---- génération -----------------------------------------------------------------------------
def _doc(text: Optional[str], indent: str = "") -> list[str]:
    if not text:
        return []
    t = text.replace('"""', "'''").replace("\\", "\\\\").strip()
    if t.endswith('"'):
        t += " "
    return [f'{indent}"""{t}"""']


def _enum_name(nt: NodeType, p: PGProperty) -> str:
    return pascal(nt.name) + pascal(p.name)


def _scalar_type(nt: NodeType, p: PGProperty, enums: dict[str, list[str]]) -> str:
    if p.enum:
        base = _enum_name(nt, p)
        enums[base] = p.enum
    else:
        base = SCALAR_MAP.get(p.type, "String")
    if p.is_list:
        return f"[{base}!]!" if p.required else f"[{base}!]"
    return base + ("!" if p.required else "")


def _prop_field(nt: NodeType, p: PGProperty, enums: dict[str, list[str]]) -> list[str]:
    desc = p.description or ""
    extra = []
    if p.source:
        extra.append(f"source: {p.source}")
    if p.lang:
        extra.append(f"langue: {p.lang}")
    if p.note:
        extra.append(p.note)
    lines = _doc(" — ".join(x for x in [desc] + extra if x), "  ")
    lines.append(f"  {gql_name(p.name)}: {_scalar_type(nt, p, enums)}")
    return lines


def _card_type(target: str, card: str) -> str:
    if card == "1":
        return f"{target}!"
    if card == "0..1":
        return target
    return f"[{target}!]!"


def _subtype_props(nt: NodeType, onto: Optional[OntoModel]) -> dict[str, set[str]]:
    """Valeur du discriminant → noms de propriétés propres à cette sous-classe (via domaines OWL)."""
    out: dict[str, set[str]] = {v: set() for v in nt.discriminator_values}
    if onto is None:
        return out
    by_local = {local_name(s): s for s in nt.source}
    for v in nt.discriminator_values:
        cls = by_local.get(v)
        if not cls:
            continue
        family = {cls, *onto.descendants(cls)} if cls in onto.classes else {cls}
        for p in nt.properties:
            dp = onto.datatype_properties.get(p.source or "")
            if dp and dp.domain and set(dp.domain) <= family:
                out[v].add(p.name)
    return out


def generate(pg: PGModel, onto: Optional[OntoModel] = None) -> dict[str, str]:
    neo = pg.target == "neo4j"
    enums: dict[str, list[str]] = {}
    used_scalars: set[str] = {"Date", "DateTime"}
    rel_names = relation_fields(pg)
    # relations par type de nœud : (field, gqlType, directive, doc)
    rels: dict[str, list[tuple[str, str, str, str]]] = {n: [] for n in pg.node_types}
    edge_prop_types: list[list[str]] = []
    for i, e in enumerate(pg.edge_types):
        fwd, rev = rel_names[i]
        rtype = edge_cypher_type(pg, e)
        props_arg = ""
        if e.properties and neo:
            pt = pascal(e.name) + "Properties"
            props_arg = f', properties: "{pt}"'
            block = [f"type {pt} @relationshipProperties {{"]
            for p in e.properties:
                fake = NodeType(name=e.name)
                block += _prop_field(fake, p, enums)
                used_scalars.add(SCALAR_MAP.get(p.type, "String"))
            block.append("}")
            edge_prop_types.append(block)
        d_fwd = f' @relationship(type: "{rtype}", direction: OUT{props_arg})' if neo else ""
        d_rev = f' @relationship(type: "{rtype}", direction: IN{props_arg})' if neo else ""
        und = f' @relationship(type: "{rtype}", direction: NONE{props_arg})' if neo else ""  # À VÉRIFIER NONE
        doc_f = f"edge {e.name}" + (f" (reverse {e.reverse})" if e.reverse else "") + (f" — source: {e.source}" if e.source else "")
        if e.properties and not neo:
            doc_f += " — propriétés d'arête ignorées (Curiosity : edges sans propriétés)"
        if e.note:
            doc_f += f" — {e.note}"
        if e.from_ in rels and e.to in pg.node_types:
            if rev is None:
                rels[e.from_].append((fwd, f"[{gql_name(e.to)}!]!", und if neo else "", doc_f + " — symétrique"))
            else:
                rels[e.from_].append((fwd, _card_type(gql_name(e.to), e.cardinality.out), d_fwd, doc_f))
        if rev is not None and e.to in rels and e.from_ in pg.node_types:
            rels[e.to].append((rev, _card_type(gql_name(e.from_), e.cardinality.in_), d_rev,
                               f"sens retour de {e.name}" + (f" (edge {e.reverse})" if e.reverse else "")))

    for nt in pg.node_types.values():
        for p in nt.properties:
            used_scalars.add(SCALAR_MAP.get(p.type, "String"))

    type_blocks: list[list[str]] = []
    query_fields: list[str] = []
    for name in sorted(pg.node_types):
        nt = pg.node_types[name]
        g = gql_name(nt.name)
        node_doc = " — ".join(x for x in [nt.description, ("source: " + ", ".join(nt.source)) if nt.source else None] if x)
        rel_lines: list[str] = []
        for f, t, d, doc in sorted(rels.get(name, [])):
            rel_lines += _doc(doc, "  ") + [f"  {f}: {t}{d}"]
        node_dir = ""
        if neo and len(nt.labels) > 1:
            node_dir = " @node(labels: [" + ", ".join(f'"{l}"' for l in nt.labels) + "])"  # À VÉRIFIER (v4+)
        elif neo and nt.labels and nt.labels[0] != nt.name:
            node_dir = f' @node(labels: ["{nt.labels[0]}"])'
        if nt.discriminator and nt.discriminator_values:
            own = _subtype_props(nt, onto)
            specific = set().union(*own.values()) if own else set()
            common = [p for p in nt.properties if p.name not in specific]
            blk = _doc(node_doc + f" — interface (héritage aplati, discriminant `{nt.discriminator}`)") + [f"interface {g} {{"]
            for p in common:
                blk += _prop_field(nt, p, enums)
            blk += rel_lines + ["}"]
            type_blocks.append(blk)
            concretes = [(pascal(v), v) for v in nt.discriminator_values]
            if not nt.abstract:
                concretes.append(("Base" + pascal(nt.name), None))
            for cname, v in sorted(concretes):
                cdoc = (f"{nt.name} avec {nt.discriminator} = \"{v}\"" if v else
                        f"{nt.name} sans sous-type (instance directe de la classe parente)")
                blk = _doc(cdoc) + [f"type {gql_name(cname)} implements {g}{node_dir} {{"]
                for p in common:
                    blk += _prop_field(nt, p, enums)
                for p in nt.properties:
                    if p.name in specific and (v is None or p.name in own.get(v, set())):
                        blk += _prop_field(nt, p, enums)
                blk += rel_lines + ["}"]
                type_blocks.append(blk)
        else:
            blk = _doc(node_doc + (" — abstrait" if nt.abstract else "")) + [f"type {g}{node_dir} {{"]
            for p in nt.properties:
                blk += _prop_field(nt, p, enums)
            blk += rel_lines + ["}"]
            type_blocks.append(blk)
        # Query racine
        props = {p.name: p for p in nt.properties}
        key = [k for k in nt.key if k in props] or (["uri"] if "uri" in props else [])
        if key:
            args = ", ".join(f"{gql_name(k)}: {SCALAR_MAP.get(props[k].type, 'String')}!" for k in key)
            query_fields.append(f'  """{nt.name} par clé ({", ".join(key)})"""')
            query_fields.append(f"  {lookup_field(nt.name)}({args}): {g}")
        query_fields.append(f'  """Liste paginée de {nt.name} (offset)"""')
        query_fields.append(f"  {list_field(nt.name)}(first: Int = 50, offset: Int = 0): [{g}!]!")

    out: list[str] = [
        "# Schéma GraphQL généré par OntoForge depuis le PGModel "
        f"« {pg.meta.name or 'sans nom'} » (cible {pg.target}).",
        "# Ne pas éditer à la main : regénérer depuis OntoForge.",
    ]
    lost = [f for f in pg.findings if f.severity == "lost"]
    if lost:
        out.append("#")
        out.append("# Pertes signalées par l'analyse (non représentées dans ce schéma) :")
        out += [f"# LOST {f.id} — {f.title}" for f in sorted(lost, key=lambda f: f.id)]
    out.append("")
    if neo:
        out += [
            "# --- Déclarations des directives Neo4j GraphQL Library : utiles pour valider ce fichier hors",
            "# --- de la librairie ; À RETIRER si les typeDefs sont passées à `new Neo4jGraphQL({ typeDefs })`.",
            "enum RelationshipDirection { IN OUT NONE }",
            "directive @relationship(type: String!, direction: RelationshipDirection!, properties: String) on FIELD_DEFINITION",
            "directive @relationshipProperties on OBJECT",
            "directive @node(labels: [String!]) on OBJECT",
            "# --- fin des déclarations",
            "",
        ]
    for s in sorted(used_scalars):
        if s in CUSTOM_SCALARS:
            out += [f'"""{CUSTOM_SCALARS[s]}"""', f"scalar {s}", ""]
    for en in sorted(enums):
        vals = enums[en]
        out.append(f"enum {gql_name(en)} {{")
        for v in vals:
            ev = enum_value(v)
            out += ([f'  """valeur source : {v}"""'] if ev != v else []) + [f"  {ev}"]
        out += ["}", ""]
    for blk in edge_prop_types:
        out += blk + [""]
    for blk in type_blocks:
        out += blk + [""]
    out += ["type Query {"] + query_fields + ["}", ""]
    schema = "\n".join(out)
    return {"schema.graphql": schema, "README-graphql.md": _readme(pg)}


def _readme(pg: PGModel) -> str:
    ex = sorted(pg.node_types)[0] if pg.node_types else "Node"
    return f"""# Schéma GraphQL — {pg.meta.name or 'modèle'} (cible {pg.target})

Généré par OntoForge depuis le PGModel. `schema.graphql` contient :

- un type par NodeType, champs typés (`!` = propriété obligatoire, `[T!]` = propriété multivaluée) ;
- les scalaires custom `Date`, `DateTime` (+ `Time`, `Duration`, `LocalDateTime` s'ils sont utilisés) — à brancher
  sur un scalaire ISO 8601 (ex. `graphql-scalars`) ;
- un `enum` par propriété énumérée (valeurs normalisées en `UPPER_SNAKE`, valeur source en description) ;
- l'héritage aplati (discriminant) en `interface` + un type concret par sous-type (`Base<Type>` pour les instances
  directes du parent) : le résolveur `__resolveType` lit la propriété discriminante ;
- chaque relation dans les deux sens (champ aller sur la source, champ retour nommé d'après `reverse`) ;
- `type Query` : lookup par clé (`{lookup_field(ex)}(…)`) et listes paginées par offset (`first`, `offset`).

Les pertes de l'analyse (`# LOST <findingId>`) sont rappelées en tête de fichier : rien n'est perdu en silence.

## Neo4j — Neo4j GraphQL Library

Les relations portent `@relationship(type: "HAS_MODEL", direction: OUT|IN)` (et `properties:` pour les relations
porteuses de propriétés, typées `@relationshipProperties`). Les multi-labels utilisent `@node(labels: [...])`.

```js
import {{ Neo4jGraphQL }} from "@neo4j/graphql";            // À VÉRIFIER : version 5.x/6.x
const typeDefs = fs.readFileSync("schema.graphql", "utf8");
const neoSchema = new Neo4jGraphQL({{ typeDefs, driver }});
const schema = await neoSchema.getSchema();
```

À faire avant de passer le fichier à la librairie (À VÉRIFIER selon la version) :
1. retirer le bloc « Déclarations des directives » (la librairie les fournit) ;
2. retirer `type Query` : la librairie génère ses propres requêtes (`vehicles(where: …, limit: …)`, filtres,
   tri, connexions Relay) ; garder notre `Query` seulement pour une API custom ;
3. scalaires : `Date`, `DateTime`, `Duration`, `Time`, `LocalDateTime` sont natifs dans la librairie — retirer
   nos déclarations `scalar` si elle signale un doublon ;
4. interfaces : la librairie gère les interfaces sur les types de relation ; les types concrets se distinguent
   par label — vérifier que le discriminant est aussi posé en label, sinon utiliser `@node(labels:)`.

## Curiosity — API custom

Curiosity n'expose pas de GraphQL natif connu (À VÉRIFIER auprès de l'expert Curiosity) : le schéma sert de
contrat pour une API custom (ex. un endpoint Curiosity, ou une passerelle Node/.NET — HotChocolate, Apollo).
Les résolveurs s'appuient sur la Query API Curiosity (À VÉRIFIER, docs.curiosity.ai « Graph Query Language ») :

```csharp
// lookup par clé
Q().StartAt(N.Vehicle.Type, vin).Emit("N");
// relation (champ aller / retour) : nom d'edge Curiosity indiqué en description du champ
Q().StartAt(N.Vehicle.Type, vin).Out(N.RepairOrder.Type, E.HasRepairOrder).Emit("N");
// liste paginée
Q().StartAt(N.Vehicle.Type).Skip(offset).Take(first).Emit("N");
```

Les edges Curiosity ne portent pas de propriétés : aucune propriété de relation n'est exposée pour cette cible.
"""
