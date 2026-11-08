"""Processus fils de la matérialisation d'inférence (L19) : owlrl sur un graphe N-Triples lu sur stdin.

Écrit sur stdout les seuls triplets NOUVEAUX et UTILES (N-Triples). Tuable par le parent (délai). Aucun réseau.
Sémantiques : rdfs | owlrl (OWL 2 RL) | both (RDFS + OWL RL). Filtrage : voir `useful()`.
"""
import sys

import owlrl
import rdflib
from rdflib import OWL, RDF, RDFS, BNode, Literal, Namespace, URIRef

ERR = Namespace("http://www.daml.org/2002/03/agents/agent-ont#")  # messages d'incohérence d'owlrl (owlrl.Closure, À VÉRIFIER si owlrl change)

NOISE_TYPES = {RDFS.Resource, OWL.Thing, RDFS.Class, OWL.Class, RDF.Property, RDFS.Datatype, OWL.NamedIndividual,
               OWL.ObjectProperty, OWL.DatatypeProperty, OWL.AnnotationProperty, OWL.Ontology, RDFS.Literal, OWL.Nothing,
               OWL.Restriction}


def useful(s, p, o, schema: set) -> bool:
    """Garde les faits sur les individus : types de classes du domaine, valeurs de propriétés (sous-propriétés, inverses,
    symétriques, transitives, sameAs). Écarte le bruit : rdfs:Resource / owl:Thing, sujets littéraux ou anonymes, reflexivité,
    fermeture du vocabulaire (schéma) et axiomes.
    Objets anonymes écartés aussi (revue w3c L19 it1) : le parent recharge ce flux dans un graphe à part et Oxigraph renomme les
    nœuds anonymes à chaque chargement, si bien qu'un `ex:i ex:p _:b` inféré pointerait vers un nœud orphelin, sans ses triplets."""
    if isinstance(s, (Literal, BNode)) or s == OWL.Nothing:
        return False
    if s in schema or p in (RDFS.subClassOf, RDFS.subPropertyOf, RDFS.domain, RDFS.range, OWL.equivalentClass,
                            OWL.equivalentProperty, OWL.inverseOf, OWL.disjointWith):
        return False
    if p == RDF.type:
        return isinstance(o, URIRef) and o not in NOISE_TYPES
    if p in (OWL.sameAs, OWL.differentFrom):
        return s != o and isinstance(o, URIRef)
    return not isinstance(o, BNode)


def main() -> None:
    sem = {"rdfs": owlrl.RDFS_Semantics, "owlrl": owlrl.OWLRL_Semantics, "both": owlrl.RDFS_OWLRL_Semantics}[sys.argv[1]]
    g = rdflib.Graph()
    g.parse(data=sys.stdin.buffer.read(), format="nt")
    before = set(g)
    schema = {s for s, o in g.subject_objects(RDF.type) if o in (OWL.Class, RDFS.Class, OWL.ObjectProperty, OWL.DatatypeProperty,
                                                                OWL.AnnotationProperty, RDF.Property, OWL.Restriction, OWL.Ontology)}
    # owl:hasKey : la règle prp-key d'owlrl est quasi inutilisable (mesuré : plus de 10 min sur 4,7 k triplets, 3,7 s sans les clés).
    # On les retire AVANT calcul ; le parent le signale à l'utilisateur.
    # RDFS ignore owl:hasKey : la note ne concerne que les sémantiques OWL RL.
    keys = list(g.triples((None, OWL.hasKey, None)))
    for t in keys:
        g.remove(t)
    if keys and sys.argv[1] != "rdfs":
        sys.stderr.write(f"NOTE hasKey {len(keys)}\n")
    owlrl.DeductiveClosure(sem, axiomatic_triples=False, datatype_axioms=False).expand(g)
    # Incohérences détectées par owlrl (cax-dw, prp-irp, cls-nothing2…) : nœud anonyme ERR:ErrorMessage, que `useful` écarterait.
    for m in g.objects(None, ERR.error):
        sys.stderr.write("ERROR " + " ".join(str(m).split())[:300] + "\n")
    out = rdflib.Graph()
    for t in g:
        if t not in before and useful(*t, schema):
            out.add(t)
    same = sum(1 for s, o in out.subject_objects(OWL.sameAs))
    if same:
        sys.stderr.write(f"NOTE sameAs {same}\n")
    sys.stdout.buffer.write(out.serialize(format="nt", encoding="utf-8"))


main()
