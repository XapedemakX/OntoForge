"""Génération de shapes SHACL depuis une ontologie OWL (OntoModel) — `generate_shapes(onto)`.

Principe : OWL **infère** en monde ouvert (OWA, pas d'UNA) ; SHACL **valide** en monde clos (CWA).
Les shapes générées expriment la lecture « contrat de données » de l'ontologie : ce qu'un jeu de
données *explicite* (après inférence éventuelle) doit respecter. Chaque traduction non équivalente
est signalée dans les notes (préfixe entre crochets = catégorie stable, réutilisable par le front) :

  [OWA]        sens différent : l'axiome OWL infère, la shape rejette (ex. `only`, domaine/portée) ;
  [RENFORCÉ]   la shape est plus stricte que l'axiome (ex. hasKey → minCount 1) ;
  [PARTIEL]    seule une partie de l'axiome est vérifiée (ex. classe définie : condition nécessaire) ;
  [NON-CORE]   non exprimable en SHACL Core (unicité de clé, transitivité, chaînes…) ;
  [HÉRITAGE]   dépend de la présence des rdfs:subClassOf dans le graphe validé (ont_graph) ;
  [IGNORÉ]     construit non traduit.

Règles de traduction (une NodeShape `<Classe>Shape`, sh:targetClass <Classe>, par classe nommée) :
- propriété de domaine D (data/objet) → property shape sur la shape de D ; portée → sh:datatype / sh:class ;
  propriété sans domaine → shape `<prop>UsageShape` (sh:targetSubjectsOf) ; domaine en union → idem + sh:or.
- fonctionnelle → sh:maxCount 1 ; inverse-fonctionnelle → sh:targetObjectsOf + ^p maxCount 1.
- restrictions : some → minCount 1 (qualifié si le filler diffère de la portée) ; min/max/exactly →
  minCount/maxCount (qualifiés si besoin) ; only → sh:class / sh:datatype ; value → sh:hasValue ;
  self → note [NON-CORE].
- oneOf (classe énumérée) → sh:in sur la shape de la classe et sur les propriétés dont c'est la portée.
- hasKey → minCount 1 + maxCount 1 sur chaque propriété clé + note d'unicité [NON-CORE].
- disjointWith → sh:not [sh:class X] ; disjointUnionOf → sh:xone ; superclasse union nommée → sh:or.
- DataRange / datatype personnalisé (facettes, oneOf, unionOf) → contraintes de valeur.
- disjointWith / equivalentTo entre propriétés → sh:disjoint / sh:equals.

N'importe que `core/` (contrat) : aucune dépendance aux modules io/conformance.
"""
from __future__ import annotations

from typing import Optional

from ..core.onto_model import (OWL, RDF, RDFS, XSD, ClassExpr, DataRange, LiteralValue, OntoModel, Restriction,
                               local_name)
from ..core.shapes_model import NodeShape, Path, PropertyShape, QualifiedShape, ShapesModel, Targets

THING = OWL + "Thing"
LITERAL_TYPES = {RDFS + "Literal", None}
FACETS = {
    XSD + "minInclusive": "min_inclusive", XSD + "maxInclusive": "max_inclusive",
    XSD + "minExclusive": "min_exclusive", XSD + "maxExclusive": "max_exclusive",
    XSD + "minLength": "min_length", XSD + "maxLength": "max_length", XSD + "pattern": "pattern",
    XSD + "length": "length",
}
_INT_TREE = {  # type dérivé → types dont les valeurs sont un sous-ensemble (XSD 1.1 Part 2 §3.4, hiérarchie des dérivés)
    "short": ["byte", "unsignedByte"], "int": ["short", "byte", "unsignedShort", "unsignedByte"],
    "long": ["int", "short", "byte", "unsignedInt", "unsignedShort", "unsignedByte"],
    "nonNegativeInteger": ["positiveInteger", "unsignedLong", "unsignedInt", "unsignedShort", "unsignedByte"],
    "nonPositiveInteger": ["negativeInteger"],
    "integer": ["long", "int", "short", "byte", "nonNegativeInteger", "positiveInteger", "nonPositiveInteger",
                "negativeInteger", "unsignedLong", "unsignedInt", "unsignedShort", "unsignedByte"],
    "string": ["normalizedString", "token", "language", "NMTOKEN", "Name", "NCName"],
    "normalizedString": ["token", "language", "NMTOKEN", "Name", "NCName"],
    "dateTime": ["dateTimeStamp"],
}
_INT_TREE["decimal"] = ["integer"] + _INT_TREE["integer"]
SUBTYPES = {XSD + k: [XSD + x for x in v] for k, v in _INT_TREE.items()}
BINARY_LEN = {XSD + "hexBinary", XSD + "base64Binary"}
_GENERAL_NOTES = [
    "[OWA] Les shapes valident les données explicites (monde clos) : un axiome OWL qui *déduirait* un fait "
    "manquant devient ici une violation. Valider avec inference='rdfs' ou 'owlrl' pour rapprocher les deux lectures.",
    "[HÉRITAGE] sh:targetClass couvre les instances des sous-classes uniquement si les triplets rdfs:subClassOf "
    "sont présents dans le graphe validé : fournir l'ontologie (ont_graph) à validate(). Les restrictions héritées "
    "(dont allValuesFrom) sont donc vérifiées via la shape de la superclasse, pas recopiées.",
]


def _is_datatype(onto: OntoModel, iri: Optional[str]) -> bool:
    if not iri:
        return False
    return (iri.startswith(XSD) or iri in (RDF + "langString", RDF + "PlainLiteral", RDFS + "Literal",
                                           RDF + "XMLLiteral", RDF + "HTML", RDF + "JSON")
            or iri in onto.datatypes)


class _Gen:
    def __init__(self, onto: OntoModel):
        self.o = onto
        self.notes: list[str] = list(_GENERAL_NOTES)
        self.m = ShapesModel(prefixes=dict(onto.meta.prefixes))
        self.props: dict[tuple[str, str, bool], PropertyShape] = {}  # (shape id, prop, inverse) → PS principale
        self.anon = 0
        self.anon_cache: dict[str, str] = {}
        self.enum_classes = {c.iri: c.one_of for c in onto.classes.values() if c.one_of}

    # -- identifiants ----------------------------------------------------------------------------
    def shape_id(self, iri: str, suffix: str = "Shape") -> str:
        cand = iri + suffix
        n = 2
        while cand in self.o.classes or cand in self.o.object_properties or cand in self.o.datatype_properties:
            cand = f"{iri}{suffix}{n}"
            n += 1
        return cand

    def class_shape(self, cls: str) -> NodeShape:
        sid = self.shape_id(cls)
        if sid not in self.m.shapes:
            c = self.o.classes.get(cls)
            labels = {}
            if c and c.labels:
                labels = {k: f"Forme {v}" if k == "fr" else f"{v} shape" for k, v in c.labels.items()}
            self.m.shapes[sid] = NodeShape(id=sid, targets=Targets(target_class=[cls]), labels=labels)
        return self.m.shapes[sid]

    def usage_shape(self, prop: str, inverse: bool = False) -> NodeShape:
        sid = self.shape_id(prop, "ObjectsShape" if inverse else "UsageShape")
        if sid not in self.m.shapes:
            t = Targets(target_objects_of=[prop]) if inverse else Targets(target_subjects_of=[prop])
            self.m.shapes[sid] = NodeShape(id=sid, targets=t)
        return self.m.shapes[sid]

    def anon_shape(self, **kw) -> str:
        """Shape anonyme (sh:class X, sh:datatype…) pour or/xone/not/qualifiedValueShape."""
        sig = repr(sorted(kw.items()))
        if sig in self.anon_cache:
            return self.anon_cache[sig]
        self.anon += 1
        key = "-".join(local_name(str(v if not isinstance(v, list) else v[0])) for v in kw.values()) or "x"
        sid = f"_:gen-{key}-{self.anon}"
        self.m.shapes[sid] = NodeShape(id=sid, **kw)
        self.anon_cache[sig] = sid
        return sid

    def prop_shape(self, ns: NodeShape, prop: str, inverse: bool = False) -> PropertyShape:
        key = (ns.id, prop, inverse)
        if key not in self.props:
            pid = f"{ns.id}-{'inv-' if inverse else ''}{local_name(prop)}"
            path = Path(kind="inverse", args=[Path(kind="predicate", iri=prop)]) if inverse else Path(
                kind="predicate", iri=prop)
            e = self.o.object_properties.get(prop) or self.o.datatype_properties.get(prop)
            names = dict(e.labels) if e and e.labels and not inverse else {}
            ps = PropertyShape(id=pid, path=path, names=names)
            ns.properties.append(ps)
            self.props[key] = ps
        return self.props[key]

    def extra_prop_shape(self, ns: NodeShape, prop: str, inverse: bool, tag: str) -> PropertyShape:
        base = self.prop_shape(ns, prop, inverse)  # garantit une PS principale (porte la portée)
        n = 2
        pid = f"{base.id}-{tag}"
        while any(p.id == pid for p in ns.properties):
            pid = f"{base.id}-{tag}{n}"
            n += 1
        ps = PropertyShape(id=pid, path=base.path.model_copy(deep=True))
        ns.properties.append(ps)
        return ps

    def set_datatype(self, ps: PropertyShape | NodeShape, dt: str, subject: str) -> None:
        """OWL raisonne sur l'espace de valeurs (xsd:int ⊂ xsd:integer ⊂ xsd:decimal) alors que sh:datatype exige
        l'IRI exacte : pour un type XSD ayant des sous-types, on génère sh:or de datatypes compatibles."""
        subs = SUBTYPES.get(dt)
        if subs and not ps.or_:
            ps.or_ = [self.anon_shape(datatype=d) for d in [dt] + subs]
            self.notes.append(f"[RENFORCÉ] {local_name(subject)} : portée {local_name(dt)} → sh:or des datatypes "
                              "XSD dérivés (sh:datatype exige le datatype exact ; les types sont listés pour "
                              "accepter ses sous-types, comme OWL).")
            return
        ps.datatype = dt
        if subs:
            self.notes.append(f"[RENFORCÉ] {local_name(subject)} : sh:datatype {local_name(dt)} exige ce datatype "
                              "exact ; les sous-types XSD valides en OWL sont rejetés (sh:or déjà utilisé).")

    # -- helpers de contraintes -------------------------------------------------------------------
    def apply_range(self, ps: PropertyShape, rng: str, subject: str) -> None:
        o = self.o
        if rng in LITERAL_TYPES or rng == THING:
            return
        if _is_datatype(o, rng):
            dd = o.datatypes.get(rng)
            if dd and dd.definition:
                self.apply_data_range(ps, dd.definition, subject)
                self.notes.append(f"[PARTIEL] {local_name(subject)} : datatype personnalisé {local_name(rng)} "
                                  "remplacé par sa base + facettes (SHACL ne connaît pas les datatypes définis).")
            elif rng in (RDF + "PlainLiteral",):
                ps.or_ = [self.anon_shape(datatype=XSD + "string"), self.anon_shape(datatype=RDF + "langString")]
            else:
                self.set_datatype(ps, rng, subject)
                if rng == RDF + "langString":
                    self.notes.append(f"[RENFORCÉ] {local_name(subject)} : rdf:langString → sh:datatype "
                                      "rdf:langString (sh:uniqueLang non généré : à décider).")
        else:
            if rng not in ps.class_:
                ps.class_.append(rng)
            if rng in self.enum_classes and not ps.in_:
                ps.in_ = list(self.enum_classes[rng] or [])

    def apply_data_range(self, ps: PropertyShape | NodeShape, dr: DataRange, subject: str) -> None:
        if dr.base and dr.base not in LITERAL_TYPES:
            self.set_datatype(ps, dr.base, subject)
        for f, v in dr.facets.items():
            attr = FACETS.get(f)
            if attr is None:
                self.notes.append(f"[IGNORÉ] {local_name(subject)} : facette {local_name(f)} non traduite.")
            elif attr in ("min_length", "max_length"):
                setattr(ps, attr, int(v))
            elif attr == "length":
                ps.min_length = ps.max_length = int(v)
            elif attr == "pattern":
                # facette XSD implicitement ancrée ; sh:pattern (REGEX SPARQL) cherche une sous-chaîne
                setattr(ps, attr, f"^(?:{v})$")
                self.notes.append(f"[PARTIEL] {local_name(subject)} : xsd:pattern traduit en ^(?:…)$ ; les "
                                  "échappements propres à XSD (\\i, \\c, soustraction de classes) ne sont pas traduits.")
            else:
                setattr(ps, attr, v)
        if dr.base in BINARY_LEN and any(FACETS.get(f, "").endswith("length") for f in dr.facets):
            self.notes.append(f"[PARTIEL] {local_name(subject)} : length/minLength/maxLength comptent des octets "
                              "pour hexBinary/base64Binary (XSD §4.3.1), des caractères pour sh:minLength.")
        if dr.one_of:
            ps.in_ = list(dr.one_of)
        if dr.union_of:
            ps.or_ = [self.anon_shape(datatype=d) for d in dr.union_of]

    def filler_is_trivial(self, prop: str, filler: Optional[str]) -> bool:
        if filler in (None, THING, RDFS + "Literal"):
            return True
        p = self.o.object_properties.get(prop) or self.o.datatype_properties.get(prop)
        return bool(p and filler in p.range)

    def filler_shape(self, filler: str) -> str:
        if _is_datatype(self.o, filler):
            return self.anon_shape(datatype=filler)
        return self.anon_shape(class_=[filler])

    # -- propriétés ------------------------------------------------------------------------------
    def gen_properties(self) -> None:
        o = self.o
        for coll, is_obj in ((o.object_properties, True), (o.datatype_properties, False)):
            for p in coll.values():
                if p.iri.startswith((OWL, RDFS, RDF)):
                    continue
                functional = ("functional" in p.characteristics) if is_obj else p.functional
                holders: list[NodeShape] = []
                if p.domain:
                    holders = [self.class_shape(d) for d in p.domain if d != THING]
                    if len(p.domain) > 1:
                        self.notes.append(f"[PARTIEL] {local_name(p.iri)} : domaine = intersection de "
                                          f"{len(p.domain)} classes — propriété portée par chacune.")
                if p.domain_union or p.domain_expr is not None or not holders:
                    us = self.usage_shape(p.iri)
                    holders.append(us)
                    if p.domain_union:
                        us.or_ = [self.anon_shape(class_=[c]) for c in p.domain_union]
                        self.notes.append(f"[OWA] {local_name(p.iri)} : domaine union → sh:targetSubjectsOf + sh:or "
                                          "(en OWL le domaine infère le type ; ici il est exigé).")
                    elif p.domain_expr is not None:
                        self.notes.append(f"[IGNORÉ] {local_name(p.iri)} : domaine complexe non traduit.")
                for d in p.domain:
                    if d != THING:
                        self.notes.append(
                            f"[OWA] {local_name(p.iri)} : rdfs:domain {local_name(d)} → propriété rattachée à la "
                            f"shape de {local_name(d)} ; l'usage sur un autre sujet n'est rejeté que si la shape est "
                            "fermée (sh:closed) — en OWL il infèrerait le type.")
                        break
                for h in holders:
                    ps = self.prop_shape(h, p.iri)
                    for r in p.range:
                        self.apply_range(ps, r, p.iri)
                    if not is_obj and getattr(p, "range_expr", None) is not None:
                        self.apply_data_range(ps, p.range_expr, p.iri)
                    if is_obj and p.range_union:
                        ps.or_ = [self.anon_shape(class_=[c]) for c in p.range_union]
                    if functional:
                        ps.max_count = 1 if ps.max_count is None else min(ps.max_count, 1)
                    for q in p.disjoint_with:
                        if q not in ps.disjoint:
                            ps.disjoint.append(q)
                    for q in p.equivalent_to:
                        if q not in ps.equals:
                            ps.equals.append(q)
                if p.range and is_obj and any(r != THING for r in p.range):
                    self.notes.append(f"[OWA] {local_name(p.iri)} : rdfs:range → sh:class : les objets doivent "
                                      "être typés explicitement (ou par inférence), OWL les typerait.")
                if functional:
                    self.notes.append(f"[OWA] {local_name(p.iri)} : fonctionnelle → sh:maxCount 1 ; en OWL deux "
                                      "valeurs seraient déclarées owl:sameAs (pas d'UNA), pas une erreur.")
                if p.equivalent_to:
                    self.notes.append(f"[PARTIEL] {local_name(p.iri)} : owl:equivalentProperty → sh:equals, vérifié "
                                      "sur les sujets portant la propriété uniquement.")
                if is_obj:
                    self.gen_object_characteristics(p)
                if p.sub_property_of:
                    self.notes.append(f"[HÉRITAGE] {local_name(p.iri)} ⊑ {', '.join(map(local_name, p.sub_property_of))} : "
                                      "avec inférence, la super-propriété est entaillée — une shape fermée doit la "
                                      "lister dans sh:ignoredProperties (piège sh:closed).")

    def gen_object_characteristics(self, p) -> None:
        ln = local_name(p.iri)
        if "inverseFunctional" in p.characteristics:
            us = self.usage_shape(p.iri, inverse=True)
            ps = self.prop_shape(us, p.iri, inverse=True)
            ps.max_count = 1
            self.notes.append(f"[OWA] {ln} : inverse-fonctionnelle → sh:targetObjectsOf + ^{ln} sh:maxCount 1.")
        for ch, why in (("transitive", "fermeture transitive = requête de chemin ou matérialisation"),
                        ("symmetric", "symétrie = règle d'inférence, pas de contrainte"),
                        ("asymmetric", "asymétrie : nécessite SHACL-SPARQL"),
                        ("reflexive", "réflexivité globale : sans objet en validation"),
                        ("irreflexive", "irréflexivité : nécessite SHACL-SPARQL (ou sh:not + sh:hasValue impossible "
                                        "sans focus)")):
            if ch in p.characteristics:
                self.notes.append(f"[NON-CORE] {ln} : {ch} — {why}.")
        if p.chains:
            self.notes.append(f"[NON-CORE] {ln} : owl:propertyChainAxiom non traduit (règle d'inférence).")
        if p.inverse_of:
            self.notes.append(f"[IGNORÉ] {ln} : owl:inverseOf {local_name(p.inverse_of)} — aucune contrainte "
                              "(cohérence à assurer par l'ingestion ou par inférence owlrl).")

    # -- classes ---------------------------------------------------------------------------------
    def gen_classes(self) -> None:
        o = self.o
        for c in o.classes.values():
            if c.iri == THING or c.iri.startswith((OWL, RDFS, RDF)):
                continue
            ns = self.class_shape(c.iri)
            ln = local_name(c.iri)
            if c.deprecated:
                ns.deactivated = True
                self.notes.append(f"[IGNORÉ] {ln} : classe dépréciée → shape désactivée (sh:deactivated).")
            for r in c.restrictions:
                self.gen_restriction(ns, c.iri, r)
            if c.one_of:
                ns.in_ = list(c.one_of)
                self.notes.append(f"[RENFORCÉ] {ln} : owl:oneOf → sh:in (liste fermée ; en OWL, sans UNA, "
                                  "un autre individu pourrait être sameAs d'un membre).")
            for keys in c.has_keys:
                for k in keys:
                    ps = self.prop_shape(ns, k)
                    ps.min_count = max(ps.min_count or 0, 1)
                    ps.max_count = 1 if ps.max_count is None else min(ps.max_count, 1)
                    p = o.datatype_properties.get(k) or o.object_properties.get(k)
                    if p is not None:
                        for r in p.range:
                            self.apply_range(ps, r, k)
                self.notes.append(
                    f"[RENFORCÉ] {ln} : owl:hasKey({', '.join(map(local_name, keys))}) → minCount 1 + maxCount 1 "
                    "(OWL n'impose ni existence ni unicité : il infère owl:sameAs entre individus nommés de même clé).")
                self.notes.append(
                    f"[NON-CORE] {ln} : unicité de la clé ({', '.join(map(local_name, keys))}) non exprimable en "
                    "SHACL Core — à garantir par contrainte d'unicité / NODE KEY (Neo4j) ou [Key] (Curiosity), "
                    "ou par une contrainte SHACL-SPARQL.")
            for d in c.disjoint_with:
                sid = self.anon_shape(class_=[d])
                if sid not in ns.not_:
                    ns.not_.append(sid)
            if c.disjoint_with:
                self.notes.append(f"[OWA] {ln} : owl:disjointWith → sh:not [sh:class …] (en OWL : incohérence "
                                  "détectée par le raisonneur ; ici violation sur les données).")
            for parts in c.disjoint_union_of:
                ns.xone = [self.anon_shape(class_=[x]) for x in parts]
                self.notes.append(f"[PARTIEL] {ln} : owl:disjointUnionOf → sh:xone : chaque instance doit être "
                                  "typée explicitement par exactement une sous-classe (OWL l'admettrait inconnue).")
            for e in c.super_expressions:
                if e.op == "or" and all(a.op == "named" and a.iri for a in e.args):
                    ns.or_ = [self.anon_shape(class_=[a.iri]) for a in e.args]
                    self.notes.append(f"[PARTIEL] {ln} : superclasse union → sh:or (types explicites exigés).")
                else:
                    self.notes.append(f"[IGNORÉ] {ln} : superclasse anonyme « {e.op} » non traduite.")
            for e in c.equivalent_to:
                if e.op == "named":
                    self.notes.append(f"[IGNORÉ] {ln} ≡ {local_name(e.iri or '')} : classes équivalentes — une seule "
                                      "shape par classe, la fusion relève du mapping (règle C05).")
                else:
                    self.gen_definition(ns, c.iri, e)

    def gen_definition(self, ns: NodeShape, cls: str, e: ClassExpr) -> None:
        """Classe définie (C ≡ expr) : on vérifie la condition nécessaire C ⊑ expr ; la condition
        suffisante (classification) est perdue."""
        ln = local_name(cls)
        parts = e.args if e.op == "and" else [e]
        translated = 0
        for a in parts:
            if a.op == "named" and a.iri:
                translated += 1  # superclasse nommée : couverte par la shape du parent (héritage)
            elif a.op in ("some", "only", "min", "max", "exactly", "value") and a.property:
                filler = a.filler.iri if a.filler is not None and a.filler.op == "named" else a.data_range
                complex_filler = a.filler is not None and a.filler.op != "named"
                self.gen_restriction(ns, cls, Restriction(property=a.property, inverse=a.inverse, kind=a.op, n=a.n,
                                                          filler=filler, value=a.value,
                                                          filler_expr=a.filler if complex_filler else None))
                translated += 1
        self.notes.append(
            f"[PARTIEL] {ln} : classe définie (owl:equivalentClass) — seule la condition nécessaire est validée "
            f"({translated}/{len(parts)} conjoint(s) traduits) ; la classification automatique (condition suffisante) "
            "est perdue : à matérialiser à l'ingestion ou à calculer par requête.")

    def gen_restriction(self, ns: NodeShape, cls: str, r: Restriction) -> None:
        ln, pl = local_name(cls), local_name(r.property)
        if r.filler_expr is not None:
            self.notes.append(f"[IGNORÉ] {ln} : restriction {r.kind} {pl} avec filler complexe non traduite.")
            return
        if r.kind == "self":
            self.notes.append(f"[NON-CORE] {ln} : ObjectHasSelf({pl}) non exprimable en SHACL Core.")
            return
        main = self.prop_shape(ns, r.property, r.inverse)
        trivial = self.filler_is_trivial(r.property, r.filler)
        if r.kind == "value":
            if r.value is not None and r.value not in main.has_value:
                main.has_value.append(r.value)
            self.notes.append(f"[OWA] {ln} : hasValue {pl} → sh:hasValue (OWL déduirait la valeur ; ici elle est "
                              "exigée — candidate valeur par défaut côté graphe).")
            return
        if r.kind == "only":
            if r.filler and r.filler != THING:
                if _is_datatype(self.o, r.filler):
                    self.set_datatype(main, r.filler, r.property)
                elif r.filler not in main.class_:
                    main.class_.append(r.filler)
            self.notes.append(f"[OWA] {ln} : only {pl} {local_name(r.filler or '')} → sh:class/sh:datatype : en OWL "
                              "allValuesFrom *type* les valeurs, ici une valeur non typée explicitement est rejetée ; "
                              "restriction héritée par les sous-classes via la shape de " + ln + ".")
            return
        lo = {"some": 1, "min": r.n, "exactly": r.n}.get(r.kind)
        hi = {"max": r.n, "exactly": r.n}.get(r.kind)
        if trivial:
            if lo is not None:
                main.min_count = max(main.min_count or 0, lo)
            if hi is not None:
                main.max_count = hi if main.max_count is None else min(main.max_count, hi)
        else:
            ps = self.extra_prop_shape(ns, r.property, r.inverse, "q" + local_name(r.filler or ""))
            ps.qualified.append(QualifiedShape(shape=self.filler_shape(r.filler or THING), min_count=lo, max_count=hi))
        if lo:
            self.notes.append(f"[OWA] {ln} : {r.kind} {pl} → minCount {lo} : en OWL l'existence est supposée "
                              "(valeur inconnue), ici une valeur explicite est exigée.")
        if hi is not None:
            self.notes.append(f"[OWA] {ln} : cardinalité max {hi} sur {pl} → maxCount : sans UNA, OWL fusionnerait "
                              "des valeurs (sameAs) au lieu de signaler une erreur.")

    def run(self) -> tuple[ShapesModel, list[str]]:
        self.gen_classes()
        self.gen_properties()
        # dédoublonnage des notes en gardant l'ordre
        seen, notes = set(), []
        for n in self.notes:
            if n not in seen:
                seen.add(n)
                notes.append(n)
        sh = "http://www.w3.org/ns/shacl#"
        self.m.prefixes.setdefault("sh", sh)
        self.m.prefixes.setdefault("xsd", XSD)
        return self.m, notes


def generate_shapes(onto: OntoModel) -> tuple[ShapesModel, list[str]]:
    """OntoModel → (ShapesModel, notes). Les notes listent tout ce qui n'est pas équivalent (voir module)."""
    return _Gen(onto).run()
