"""Périmètres : restriction de l'ontologie à un sous-ensemble de classes / propriétés (repris des « configs » d'ontoSparq)."""
from __future__ import annotations

from typing import Optional

from ..core.onto_model import ClassExpr, OWL, OntoModel, local_name
from ..core.pg_model import Finding
from ..core.project import Perimeter, Project
from ..core.shapes_model import ShapesModel


class PerimeterNotFound(KeyError):
    pass


def get_perimeter(p: Project, perimeter_id: Optional[str]) -> Optional[Perimeter]:
    """None / « all » / « none » = ontologie complète. Un id inconnu lève PerimeterNotFound."""
    if not perimeter_id or perimeter_id in ("all", "none"):
        return None
    for per in p.perimeters:
        if per.id == perimeter_id:
            return per
    raise PerimeterNotFound(perimeter_id)


def class_set(onto: OntoModel, per: Perimeter) -> set[str]:
    cs = {c for c in per.classes if c in onto.classes}
    if per.include_descendants:
        for c in list(cs):
            cs.update(onto.descendants(c))
    return cs


def expr_refs(e: Optional[ClassExpr]) -> tuple[set[str], set[str]]:
    """(IRIs nommées, propriétés) référencées par une expression de classe."""
    names: set[str] = set()
    props: set[str] = set()
    if e is None:
        return names, props
    if e.iri:
        names.add(e.iri)
    if e.property:
        props.add(e.property)
    for a in ([e.filler] if e.filler else []) + list(e.args):
        n, pr = expr_refs(a)
        names |= n
        props |= pr
    return names, props


def _short(onto: OntoModel, iri: str) -> str:
    return onto.label(iri, "fr") if iri != OWL + "Thing" else "owl:Thing"


def restrict(onto: OntoModel, per: Perimeter, shapes: Optional[ShapesModel] = None
             ) -> tuple[OntoModel, Optional[ShapesModel], list[Finding]]:
    cs = class_set(onto, per)
    explicit = set(per.properties)
    notes: list[Finding] = []

    def info(rule: str, subject: str, title: str, detail: str, related: list[str], suffix: str = "") -> None:
        notes.append(Finding(id=f"{rule}:{subject}{suffix}", rule=rule, severity="info", title=title, detail=detail,
                             subject=subject, related=related))

    def inherited(ends) -> list[str]:
        """Classes du périmètre qui héritent d'une extrémité hors périmètre (sous-classes de cette extrémité)."""
        got: set[str] = set()
        for e in ends:
            if e in onto.classes and e not in cs:
                got |= cs & set(onto.descendants(e))
        return sorted(got)

    def outside(iris) -> list[str]:
        return sorted({i for i in iris if i in onto.classes and i not in cs})

    def project(lst: list[str], union: list[str], expr) -> Optional[tuple[list[str], list[str]]]:
        """Extrémité unique hors périmètre → ses descendants du périmètre (une propriété de domaine V s'applique aussi à
        Car ⊑ V). Une seule cible : liste ; plusieurs : union. Sinon None (non projetable)."""
        if expr is not None or union or len(lst) != 1 or lst[0] in cs or lst[0] not in onto.classes:
            return None
        t = sorted(cs & set(onto.descendants(lst[0])))
        if not t:
            return None
        return ([t[0]], []) if len(t) == 1 else ([], t)

    projections: dict[str, dict[str, tuple[list[str], list[str]]]] = {}
    keep_obj: dict[str, object] = {}
    keep_dat: dict[str, object] = {}
    for iri, pr in onto.object_properties.items():
        d_l, d_u, r_l, r_u = list(pr.domain), list(pr.domain_union), list(pr.range), list(pr.range_union)
        done: dict[str, tuple[list[str], list[str]]] = {}
        if not (explicit and iri not in explicit):
            if outside(d_l + d_u) and (pj := project(d_l, d_u, pr.domain_expr)):
                done["domain"] = pj
                d_l, d_u = pj
            if outside(r_l + r_u) and (pj := project(r_l, r_u, pr.range_expr)):
                done["range"] = pj
                r_l, r_u = pj
        ends = d_l + d_u + r_l + r_u
        n, _ = expr_refs(pr.domain_expr)
        n2, _ = expr_refs(pr.range_expr)
        ends += list(n | n2)
        out = outside(ends)
        reason = None
        if explicit and iri not in explicit:
            reason = "elle n'est pas listée dans les propriétés du périmètre"
        elif out:
            reason = "son domaine ou sa portée contient des classes hors périmètre : " + ", ".join(_short(onto, o) for o in out)
        if reason:
            inh = inherited(ends)
            if any(e in cs for e in ends) or inh or iri in explicit:
                extra = (" Elle serait héritée par " + ", ".join(_short(onto, x) for x in inh) + " (domaine ou portée = ancêtre hors périmètre).") if inh else ""
                info("P01", iri, f"Relation exclue : {_short(onto, iri)}", f"La propriété d'objet {_short(onto, iri)} est écartée du périmètre « {per.name} » : {reason}.{extra}",
                     sorted(set(ends)))
        else:
            keep_obj[iri] = pr
            if done:
                projections[iri] = done
                what = " et ".join({"domain": "domaine", "range": "portée"}[k] for k in done)
                info("P01", iri, f"Relation restreinte : {_short(onto, iri)}",
                     f"Le {what} de {_short(onto, iri)} est un ancêtre hors du périmètre « {per.name} » : la propriété est conservée, "
                     "restreinte aux classes du périmètre qui en descendent (" +
                     ", ".join(_short(onto, x) for pj in done.values() for x in pj[0] + pj[1]) + ").", sorted(set(ends)))
    for iri, pr in onto.datatype_properties.items():
        d_l, d_u = list(pr.domain), list(pr.domain_union)
        done = {}
        if not (explicit and iri not in explicit) and outside(d_l + d_u) and (pj := project(d_l, d_u, pr.domain_expr)):
            done["domain"] = pj
            d_l, d_u = pj
        n, _ = expr_refs(pr.domain_expr)
        ends = d_l + d_u + list(n)
        out = outside(ends)
        reason = None
        if explicit and iri not in explicit:
            reason = "elle n'est pas listée dans les propriétés du périmètre"
        elif out:
            reason = "son domaine contient des classes hors périmètre : " + ", ".join(_short(onto, o) for o in out)
        if reason:
            inh = inherited(ends)
            if any(e in cs for e in ends) or inh or iri in explicit:
                extra = (" Elle serait héritée par " + ", ".join(_short(onto, x) for x in inh) + " (domaine = ancêtre hors périmètre).") if inh else ""
                info("P01", iri, f"Attribut exclu : {_short(onto, iri)}", f"La propriété de données {_short(onto, iri)} est écartée du périmètre « {per.name} » : {reason}.{extra}",
                     sorted(set(ends)))
        else:
            keep_dat[iri] = pr
            if done:
                projections[iri] = done
                info("P01", iri, f"Attribut restreint : {_short(onto, iri)}",
                     f"Le domaine de {_short(onto, iri)} est un ancêtre hors du périmètre « {per.name} » : l'attribut est conservé, "
                     "restreint aux classes du périmètre qui en descendent (" + ", ".join(_short(onto, x) for x in d_l + d_u) + ").", sorted(set(ends)))
    kept_props = set(keep_obj) | set(keep_dat)

    new = onto.model_copy(deep=True)
    new.classes = {k: v for k, v in new.classes.items() if k in cs}
    new.object_properties = {k: v for k, v in new.object_properties.items() if k in keep_obj}
    new.datatype_properties = {k: v for k, v in new.datatype_properties.items() if k in keep_dat}
    for iri, done in projections.items():
        tgt = new.object_properties.get(iri) or new.datatype_properties.get(iri)
        if "domain" in done:
            tgt.domain, tgt.domain_union = done["domain"]
        if "range" in done:
            tgt.range, tgt.range_union = done["range"]

    def ok_expr(e: ClassExpr) -> bool:
        n, pr = expr_refs(e)
        return not outside(n) and all(x in kept_props or x not in onto.object_properties and x not in onto.datatype_properties for x in pr)

    for c in new.classes.values():
        for par in [x for x in c.sub_class_of if x in onto.classes and x not in cs]:
            info("P02", c.iri, f"Sous-classe coupée : {_short(onto, c.iri)}", f"{_short(onto, c.iri)} est sous-classe de {_short(onto, par)}, hors du périmètre « {per.name} » : le lien d'héritage est ignoré.",
                 [par], ":" + par)
        c.sub_class_of = [x for x in c.sub_class_of if x not in onto.classes or x in cs]
        keep_r = []
        for r in c.restrictions:
            f_out = r.filler in onto.classes and r.filler not in cs
            if r.property in kept_props and not f_out and (r.filler_expr is None or ok_expr(r.filler_expr)):
                keep_r.append(r)
            else:
                info("P03", c.iri, f"Restriction coupée : {_short(onto, c.iri)}", f"La restriction « {r.kind} » sur {_short(onto, r.property)} de {_short(onto, c.iri)} est ignorée (propriété ou classe cible hors périmètre).",
                     [r.property], ":" + r.property)
        c.restrictions = keep_r
        for fld in ("super_expressions", "equivalent_to"):
            kept = []
            for e in getattr(c, fld):
                if ok_expr(e):
                    kept.append(e)
                else:
                    info("P03", c.iri, f"Axiome coupé : {_short(onto, c.iri)}", f"Une expression ({fld}) de {_short(onto, c.iri)} fait référence à des éléments hors périmètre et est ignorée.",
                         sorted(expr_refs(e)[0]), f":{fld}")
            setattr(c, fld, kept)
        c.disjoint_with = [x for x in c.disjoint_with if x in cs or x not in onto.classes]
        c.disjoint_union_of = [u for u in c.disjoint_union_of if all(x in cs for x in u)]
        c.has_keys = [k for k in c.has_keys if all(x in kept_props for x in k)]
    for pr in list(new.object_properties.values()) + list(new.datatype_properties.values()):
        pr.sub_property_of = [x for x in pr.sub_property_of if x in kept_props or x not in onto.object_properties and x not in onto.datatype_properties]
        pr.equivalent_to = [x for x in pr.equivalent_to if x in kept_props]
        pr.disjoint_with = [x for x in pr.disjoint_with if x in kept_props]
    for pr in new.object_properties.values():
        if pr.inverse_of and pr.inverse_of not in keep_obj:
            pr.inverse_of = None
        pr.chains = [ch for ch in pr.chains if all(x in keep_obj for x in ch)]
    kept_ind = {}
    for iri, ind in new.individuals.items():
        if ind.types and any(t in onto.classes and t not in cs for t in ind.types):
            continue
        ind.types = [t for t in ind.types if t not in onto.classes or t in cs]
        ind.facts = [f for f in ind.facts if f.property in kept_props or f.property in new.annotation_properties
                     or (f.property not in onto.object_properties and f.property not in onto.datatype_properties)]
        kept_ind[iri] = ind
    dropped = len(new.individuals) - len(kept_ind)
    new.individuals = kept_ind
    new.all_different = [g for g in new.all_different if all(x in kept_ind for x in g)]

    new_shapes = None
    if shapes is not None:
        new_shapes = shapes.model_copy(deep=True)
        for sid, sh in list(new_shapes.shapes.items()):
            tc = sh.targets.target_class
            if tc and all(t in onto.classes and t not in cs for t in tc):
                del new_shapes.shapes[sid]

    ex_cls = len(onto.classes) - len(new.classes)
    ex_obj = len(onto.object_properties) - len(new.object_properties)
    ex_dat = len(onto.datatype_properties) - len(new.datatype_properties)
    notes.append(Finding(
        id="P00:" + per.id, rule="P00", severity="info", title=f"Périmètre « {per.name} »",
        detail=(f"Analyse restreinte au périmètre « {per.name} » : {len(new.classes)} classe(s) conservée(s) ({ex_cls} hors périmètre), "
                f"{len(new.object_properties)} propriété(s) d'objet ({ex_obj} exclue(s)), {len(new.datatype_properties)} propriété(s) de données "
                f"({ex_dat} exclue(s)), {len(new.individuals)} individu(s) ({dropped} exclu(s)). Les constats P01–P03 expliquent ce qui est coupé ; "
                "les décisions d'arbitrage restent partagées avec les autres périmètres."),
        subject=per.id, related=[]))
    notes.sort(key=lambda f: f.id)
    return new, new_shapes, notes


def scope(p: Project, perimeter_id: Optional[str]) -> tuple[OntoModel, Optional[ShapesModel], list[Finding]]:
    """(ontologie, shapes, constats d'information) à analyser pour ce projet et ce périmètre."""
    per = get_perimeter(p, perimeter_id)
    has_shapes = bool(p.shapes.shapes or p.shapes.property_shapes)
    if per is None:
        return p.onto, (p.shapes if has_shapes else None), []
    onto, shapes, notes = restrict(p.onto, per, p.shapes if has_shapes else None)
    return onto, shapes, notes
