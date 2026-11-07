"""Famille K — identité et clés : K01–K05."""
from __future__ import annotations

from ...core.pg_model import PGProperty
from ._base import Ctx, add_validation, finding, lower_first, props_of, sha8
from .classes import node_targets, scope, scope_text


def detect_k01(ctx: Ctx):
    return [finding(ctx, "K01", i, f"Individu nommé {ctx.short(i)} : identité = IRI (propriété uri).")
            for i in sorted(ctx.onto.individuals)]


def _key_kind(ctx: Ctx, key: list[str]) -> str:
    return "K05" if any(ctx.is_obj_prop(k) for k in key) else "K02"


def detect_k02(ctx: Ctx):
    out = []
    for c, v in sorted(ctx.onto.classes.items()):
        for i, key in enumerate(v.has_keys):
            if _key_kind(ctx, key) == "K02":
                out.append(finding(ctx, "K02", c, f"HasKey({ctx.short(c)} {' '.join(ctx.short(k) for k in key)}) : "
                                   "en OWL, deux individus nommés de mêmes valeurs sont owl:sameAs ; ni existence ni "
                                   "unicité ne sont imposées.", related=key, suffix=str(i + 1) if i else None))
    return out


def detect_k05(ctx: Ctx):
    out = []
    for c, v in sorted(ctx.onto.classes.items()):
        for i, key in enumerate(v.has_keys):
            if _key_kind(ctx, key) == "K05":
                out.append(finding(ctx, "K05", c, f"HasKey({ctx.short(c)} {' '.join(ctx.short(k) for k in key)}) "
                                   "inclut une propriété objet : la clé dépend d'un autre nœud.", related=key,
                                   suffix=str(i + 1) if i else None))
    return out


def _anon_classes(ctx: Ctx) -> set[str]:
    return {t for a in ctx.anon_individuals() for t in a["types"]}


def detect_k03(ctx: Ctx):
    from .classes import is_probably_abstract
    out, anon = [], _anon_classes(ctx)
    for c, v in sorted(ctx.onto.classes.items()):
        if v.has_keys or any(ctx.onto.classes[a].has_keys for a in ctx.ancestors(c) if a in ctx.onto.classes):
            continue
        if v.deprecated or ctx.class_definitions(c) or is_probably_abstract(ctx, c) or ctx.parents(c):
            continue  # sous-classes : clé héritée de la racine ; classes définies : calculées
        gen = c in anon
        out.append(finding(ctx, "K03", c, f"{ctx.short(c)} n'a pas de clé métier (owl:hasKey)"
                           + (" et ses instances sont des nœuds blancs (sans IRI)." if gen else " : l'IRI sert de clé."),
                           reco={"curiosity": "generated_key", "neo4j": "generated_key"} if gen else None,
                           severity=None if gen else "auto"))
    return out


def detect_k04(ctx: Ctx):
    out = []
    for a in ctx.anon_individuals():
        ctx.consume(a["node"])
        out.append(finding(ctx, "K04", a["anchor"], f"Valeur anonyme de {ctx.short(a['property'])} sur "
                           f"{ctx.short(a['anchor'])} (types : {', '.join(ctx.short(t) for t in a['types']) or '?'}) : "
                           "aucune IRI, clé à générer.", suffix=sha8(a["canon"]), related=a["types"] + [a["property"]]))
    return out


DETECT = {"K01": detect_k01, "K02": detect_k02, "K03": detect_k03, "K04": detect_k04, "K05": detect_k05}


# ================================================================================================ construction
def build_uri(ctx: Ctx) -> None:
    """K01 : propriété uri sur chaque type, clé par défaut (Curiosity : [Key] ; Neo4j : UNIQUE)."""
    uri = ctx.profile.prop("uri")
    for nt in ctx.pg.node_types.values():
        if not any(p.name == uri for p in nt.properties):
            nt.properties.insert(0, PGProperty(name=uri, type="String", required=True, unique=True, indexed=True,
                                               source="urn:ontoforge:iri", description="IRI de la ressource (K01)."))
        if not nt.key:
            nt.key = [uri]


def _key_props(ctx: Ctx, nt, key: list[str]) -> list:
    out = []
    for k in key:
        for p in nt.properties:
            if p.source == k:
                out.append(p)
                break
    return out


def apply_k02(ctx: Ctx, f, opt):
    for nt_name in node_targets(ctx, f.subject):
        nt = ctx.pg.node_types[nt_name]
        props = _key_props(ctx, nt, f.related)
        if not props:
            continue
        names = [p.name for p in props]
        sc = scope(ctx, f.subject, nt_name)
        if sc:  # hasKey d'une sous-classe repliée : la clé du type racine ne change pas
            add_validation(ctx, f, "other", f"Unicité de ({', '.join(names)}) sur {nt_name}{scope_text(sc)} (hasKey).",
                           node_type=nt_name, params={"unique": names, "discriminator": sc["discriminator"],
                                                      "values": sc["values"]})
            continue
        if opt == "node_key":
            nt.key = names
            for p in props:
                p.required, p.unique, p.indexed = True, len(props) == 1, True
                p.note = "Clé (hasKey) : existence + unicité imposées — renforcement par rapport à OWL."
        elif opt == "unique_constraint":
            for p in props:
                p.unique, p.indexed = len(props) == 1, True
            if len(props) > 1:
                add_validation(ctx, f, "other", f"Unicité composite ({', '.join(names)}) sur {nt_name}.",
                               node_type=nt_name, params={"unique": names})
        elif opt == "key_concat":
            kname = ctx.profile.prop(lower_first(ctx.local(f.subject)) + "Key")
            nt.properties.append(PGProperty(name=kname, type="String", required=True, unique=True, indexed=True,
                                            source=f.subject, note="Clé concaténée : " + " | ".join(names)))
            nt.key = [kname]
        else:  # uri_key
            for p in props:
                p.indexed = True
            add_validation(ctx, f, "other", f"Unicité de ({', '.join(names)}) sur {nt_name} (hasKey OWL, contrôle "
                           "applicatif ; la clé reste uri).", node_type=nt_name, params={"unique": names})


def apply_k05(ctx: Ctx, f, opt):
    for nt_name in node_targets(ctx, f.subject):
        nt = ctx.pg.node_types[nt_name]
        data = _key_props(ctx, nt, [k for k in f.related if ctx.is_data_prop(k)])
        objs = [k for k in f.related if ctx.is_obj_prop(k)]
        names = [p.name for p in data]
        if opt == "materialize_key":
            for o in objs:
                loc = ctx.local(o)
                loc = loc[3:] if loc.startswith("has") and len(loc) > 3 else loc
                kname = ctx.profile.prop(lower_first(loc) + "Key")
                if not any(p.name == kname for p in nt.properties):
                    nt.properties.append(PGProperty(name=kname, type="String", required=True, indexed=True, source=o,
                                                    note=f"Copie de la clé du nœud cible de {ctx.short(o)} (K05)."))
                names.append(kname)
            for p in data:
                p.required = True
            nt.key = names
        elif opt == "key_concat":
            kname = ctx.profile.prop(lower_first(ctx.local(f.subject)) + "Key")
            parts = names + [f"clé({ctx.short(o)})" for o in objs]
            nt.properties.append(PGProperty(name=kname, type="String", required=True, unique=True, indexed=True,
                                            source=f.subject, note="Clé concaténée : " + " + '|' + ".join(parts)))
            nt.key = [kname]
        else:
            add_validation(ctx, f, "other", f"Unicité composite ({', '.join(names + [ctx.short(o) for o in objs])}) "
                           f"sur {nt_name}.", node_type=nt_name, params={"unique": names, "via_edges": objs})


def apply_generated(ctx: Ctx, f, opt):
    classes = [f.subject] if f.rule == "K03" else [t for t in f.related if ctx.is_class(t)]
    uri = ctx.profile.prop("uri")
    for c in classes:
        for nt_name in node_targets(ctx, c):
            nt = ctx.pg.node_types[nt_name]
            if opt == "generated_key":
                for p in nt.properties:
                    if p.name == uri:
                        p.note = "Clé générée à l'ingestion : hash déterministe ou IRI skolem /.well-known/genid/ (K03/K04)."
            elif opt == "property":
                cands = [p for p in nt.properties if p.source and ctx.is_data_prop(p.source) and not p.is_list
                         and ctx.onto.datatype_properties[p.source].functional]
                if cands:
                    cands[0].required = cands[0].unique = True
                    nt.key = [cands[0].name]


APPLY_BUILD = {"K02": apply_k02, "K05": apply_k05, "K03": apply_generated, "K04": apply_generated}
