"""L22 — revue croisée (w3c, shacl) de l'éditeur de fichiers : aller-retour sans perte, diff par isomorphisme,
diagnostics Turtle (IRI relative, IRI invalide, littéral mal typé), méta-shape SHACL, garde-fous d'accès."""
import logging
from pathlib import Path

import pytest
import rdflib
from fastapi.testclient import TestClient
from rdflib.compare import graph_diff, isomorphic, to_isomorphic

from ontoforge.editing import files as fm
from ontoforge.io.rdf_import import parse_ontology
from ontoforge.main import app
from ontoforge.shacl.import_shapes import parse_shapes

SAMPLES = Path(__file__).resolve().parents[2] / "samples"
P = ("@prefix ex: <http://e.org/o#> .\n@prefix owl: <http://www.w3.org/2002/07/owl#> .\n"
     "@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .\n@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .\n"
     "<http://e.org/o> a owl:Ontology .\n")


@pytest.fixture(autouse=True)
def _quiet_rdflib():
    logging.disable(logging.CRITICAL)  # rdflib journalise une trace par littéral mal typé
    yield
    logging.disable(logging.NOTSET)


def _turtle(text: str) -> rdflib.Graph:
    return rdflib.Graph().parse(data=text, format="turtle")


def _onto_roundtrip(text: str) -> tuple[rdflib.Graph, str]:
    model, _ = parse_ontology(text, "turtle")
    out = fm.canonical_turtle(fm.onto_graph(model))
    return _turtle(text), out


# ---- aller-retour sans perte -----------------------------------------------------------------------------------

@pytest.mark.parametrize("rel", ["automaint/automaint.ttl"])
def test_onto_roundtrip_lossless_on_sample(rel):
    src, out = _onto_roundtrip((SAMPLES / rel).read_text(encoding="utf-8"))
    assert isomorphic(src, _turtle(out)), "triplets perdus ou ajoutés à l'aller-retour"


def test_onto_roundtrip_trap_only_documented_rewrites():
    """trap.ttl : seules réécritures admises, sémantiquement équivalentes et annoncées par un avertissement :
    owl:AllDisjointClasses n-aire → owl:disjointWith par paires ; owl:distinctMembers (OWL 1) → owl:members."""
    text = (SAMPLES / "trap/trap.ttl").read_text(encoding="utf-8")
    _, warns = parse_ontology(text, "turtle")
    assert any(w.startswith("[nary_disjoint_expanded]") for w in warns)
    src, out = _onto_roundtrip(text)
    _, lost, added = graph_diff(to_isomorphic(src), to_isomorphic(_turtle(out)))
    OWL, RDF = rdflib.OWL, rdflib.RDF
    assert {p for _, p, _ in lost} <= {RDF.type, OWL.members, OWL.distinctMembers, RDF.first, RDF.rest}
    assert {p for _, p, _ in added} <= {OWL.disjointWith, RDF.type, OWL.members, RDF.first, RDF.rest}
    assert {o for _, p, o in lost if p == RDF.type} == {OWL.AllDisjointClasses, OWL.AllDifferent}
    # rien de ce qui n'est pas une réécriture n'a disparu : chaque IRI du texte source reste présente
    iris = lambda g: {x for t in g for x in t if isinstance(x, rdflib.URIRef)}  # noqa: E731
    assert iris(src) - {OWL.AllDisjointClasses, OWL.distinctMembers} <= iris(_turtle(out))


@pytest.mark.parametrize("rel", ["automaint/automaint-shapes.ttl", "trap/trap-shapes.ttl"])
def test_shapes_roundtrip_lossless_on_samples(rel):
    text = (SAMPLES / rel).read_text(encoding="utf-8")
    model, _ = parse_shapes(text, "turtle")
    out = fm.canonical_turtle(fm.shapes_graph(model))
    assert isomorphic(_turtle(text), _turtle(out))
    again, _ = parse_shapes(out, "turtle")
    assert fm.canonical_turtle(fm.shapes_graph(again)) == out  # texte canonique stable (idempotent)


@pytest.mark.parametrize("body", [
    # deux restrictions identiques (nœuds blancs automorphes) : ne doivent pas fusionner
    "ex:p a owl:ObjectProperty . ex:C a owl:Class .\n"
    "ex:A a owl:Class ; rdfs:subClassOf [ a owl:Restriction ; owl:onProperty ex:p ; owl:someValuesFrom ex:C ] .\n"
    "ex:B a owl:Class ; rdfs:subClassOf [ a owl:Restriction ; owl:onProperty ex:p ; owl:someValuesFrom ex:C ] .\n",
    # deux listes RDF identiques : pas de partage de nœuds de liste (interdit par le mapping OWL 2 → RDF)
    "ex:X a owl:Class . ex:Y a owl:Class .\n"
    "ex:A a owl:Class ; owl:equivalentClass [ a owl:Class ; owl:unionOf ( ex:X ex:Y ) ] .\n"
    "ex:B a owl:Class ; owl:equivalentClass [ a owl:Class ; owl:unionOf ( ex:X ex:Y ) ] .\n",
    # énumération (liste dans owl:oneOf)
    "ex:Col a owl:Class ; owl:equivalentClass [ a owl:Class ; owl:oneOf ( ex:red ex:green ex:blue ) ] .\n"
    "ex:red a owl:NamedIndividual, ex:Col . ex:green a owl:NamedIndividual, ex:Col . ex:blue a owl:NamedIndividual, ex:Col .\n",
    # triplets hors modèle, nœud blanc d'annotation, littéraux typés et étiquette de langue avec région
    'ex:Z ex:foo "bar" . ex:A a owl:Class ; rdfs:comment "c" ; ex:note [ ex:k "v" ] .\n'
    'ex:d a owl:DatatypeProperty . ex:i a owl:NamedIndividual ; ex:d "1.50"^^xsd:decimal, "true"^^xsd:boolean ;'
    ' rdfs:label "Voiture"@fr-FR .\n',
])
def test_roundtrip_blank_nodes_and_lists(body):
    src, out = _onto_roundtrip(P + body)
    back = _turtle(out)
    assert len(back) == len(src)
    assert isomorphic(src, back)


# ---- diff +N / −M par isomorphisme ------------------------------------------------------------------------------

@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("ONTOFORGE_DATA", str(tmp_path))
    return TestClient(app)


@pytest.fixture
def pid(client):
    r = client.post("/api/projects", json={"name": "Revue L22", "sample": "automaint"})
    assert r.status_code == 201
    return r.json()["id"]


def _diff(client, pid, path, content):
    r = client.post(f"/api/projects/{pid}/files/diff", json={"path": path, "content": content})
    assert r.status_code == 200, r.text
    return r.json()


def test_diff_ignores_blank_node_labels_and_order(client, pid):
    """Même graphe, nœuds blancs ré-étiquetés et triplets dans un autre ordre : 0 / 0, rien à appliquer.
    (Avec un texte sans @prefix, le diff reste 0 / 0 mais « changed » est vrai : les préfixes du projet sont remplacés
    par ns1, ns2… — voir la revue w3c L22.)"""
    cur = client.get(f"/api/projects/{pid}/files/onto.ttl").json()["content"]
    g = _turtle(cur)
    shuffled = rdflib.Graph()
    for pfx, ns in g.namespaces():
        shuffled.bind(pfx, ns)
    relabel: dict = {}
    for s, p, o in sorted(g, reverse=True):
        s = relabel.setdefault(s, rdflib.BNode()) if isinstance(s, rdflib.BNode) else s
        o = relabel.setdefault(o, rdflib.BNode()) if isinstance(o, rdflib.BNode) else o
        shuffled.add((s, p, o))
    d = _diff(client, pid, "onto.ttl", shuffled.serialize(format="turtle"))
    # le texte change (ordre, étiquettes), le graphe non : 0 / 0, aucune réécriture, et le modèle n'est pas touché (L22 it1)
    assert (d["summary"]["added"], d["summary"]["removed"]) == (0, 0)
    assert d["summary"]["rewritten"]["count"] == 0 and d["summary"]["source_kept"] is True


def test_diff_counts_one_restriction_change_locally(client, pid):
    """Changer la cardinalité d'une seule restriction ne doit pas faire « tout changer » : seule la restriction
    (nœud blanc ré-étiqueté) et son rattachement apparaissent."""
    cur = client.get(f"/api/projects/{pid}/files/onto.ttl").json()["content"]
    g = _turtle(cur)
    OWL = rdflib.OWL
    r = next(s for s in g.subjects(OWL.cardinality, None) if isinstance(s, rdflib.BNode))
    old = g.value(r, OWL.cardinality)
    g.set((r, OWL.cardinality, rdflib.Literal(int(old) + 1, datatype=rdflib.XSD.nonNegativeInteger)))
    d = _diff(client, pid, "onto.ttl", g.serialize(format="turtle"))
    added, removed = d["summary"]["added"], d["summary"]["removed"]
    assert d["changed"] and added == removed
    assert 1 <= added <= 4, d["summary"]  # rdf:type, onProperty, cardinality + le subClassOf qui la porte


# ---- diagnostics Turtle ---------------------------------------------------------------------------------------

def _diags(path, text):
    return fm.validate(None, path, text, "fr")


def test_relative_iri_without_base_is_an_error_and_never_resolved_on_server_path():
    d = _diags("onto.ttl", P + "<Truc> a owl:Class .\n")
    assert [x["code"] for x in d] == ["turtle-relative-iri"]
    assert (d[0]["line"], d[0]["col"]) == (6, 1)
    g, errs = fm.syntax_diagnostics(P + "<Truc> a owl:Class .\n")
    assert g is None and errs


def test_relative_iri_with_base_is_accepted():
    text = "@base <http://e.org/b/> .\n" + P + "<Truc> a owl:Class .\n"
    g, errs = fm.syntax_diagnostics(text)
    assert not errs and (rdflib.URIRef("http://e.org/b/Truc"), rdflib.RDF.type, rdflib.OWL.Class) in g


def test_iri_with_space_is_an_error():
    d = _diags("onto.ttl", P + "<http://e.org/a b> a owl:Class .\n")
    assert d and d[0]["code"] == "turtle-bad-iri" and d[0]["line"] == 6


def test_ill_typed_literal_is_a_warning_on_its_line():
    text = P + 'ex:d a owl:DatatypeProperty .\nex:i a owl:NamedIndividual ;\n  ex:d "abc"^^xsd:integer .\n'
    d = [x for x in _diags("onto.ttl", text) if x["code"] == "ill-typed-literal"]
    assert len(d) == 1 and d[0]["severity"] == "warning" and d[0]["line"] == 8


def test_undeclared_prefix_position_with_accents_and_decoys():
    text = P + '# commentaire àéè zz:faux\nex:Élan a owl:Class ;\n  ex:note "zz: dans une chaîne" ;\n  ex:r zz:B .\n'
    d = _diags("onto.ttl", text)
    assert len(d) == 1 and d[0]["severity"] == "error" and (d[0]["line"], d[0]["col"]) == (9, 8)


# ---- méta-validation SHACL (shacl-shacl) ----------------------------------------------------------------------

SH = "@prefix ex: <http://e.org/o#> .\n@prefix sh: <http://www.w3.org/ns/shacl#> .\n@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .\n"


def test_shacl_meta_shape_flags_datatype_literal_on_its_line():
    text = SH + 'ex:S a sh:NodeShape ;\n  sh:property [ sh:path ex:p ; sh:datatype "string" ] .\n'
    d = [x for x in _diags("shapes.ttl", text) if x["code"] == "shacl-shacl"]
    assert d and d[0]["line"] == 5 and "sh:datatype" in d[0]["message"]


def test_shacl_unappliable_shape_error_is_located_not_line_one(client, pid):
    text = SH + 'ex:S a sh:NodeShape ;\n  sh:targetClass ex:C ;\n  sh:property [ sh:path ex:p ; sh:minCount "x" ] .\n'
    errs = [x for x in _diags("shapes.ttl", text) if x["severity"] == "error"]
    assert errs and all(x["line"] == 6 for x in errs)
    assert {x["code"] for x in errs} == {"shacl-shacl", "shapes-import"}
    r = client.put(f"/api/projects/{pid}/files/shapes.ttl", json={"content": text})
    assert r.status_code == 422 and all(x["line"] == 6 for x in r.json()["diagnostics"])


def test_valid_shapes_have_no_meta_shape_finding():
    text = SH + 'ex:S a sh:NodeShape ;\n  sh:targetClass ex:C ;\n  sh:property [ sh:path ex:p ; sh:minCount 1 ; sh:datatype xsd:string ] .\n'
    assert not [x for x in _diags("shapes.ttl", text) if x["code"].startswith("shacl-shacl")]


# ---- garde-fous d'accès ---------------------------------------------------------------------------------------

@pytest.mark.parametrize("path", ["../../../../etc/passwd", "%2e%2e/%2e%2e/etc/passwd",
                                  "generated/../../etc/passwd", "/etc/passwd", "project.json"])
def test_no_path_traversal_on_read(client, pid, path):
    r = client.get(f"/api/projects/{pid}/files/{path}")
    assert r.status_code == 404
    assert "root:" not in r.text


@pytest.mark.parametrize("path", ["generated/../onto.ttl", "generated/../../project.json", "../onto.ttl", "onto.ttl/..", ""])
def test_no_path_traversal_in_file_module(path):
    """Le module ne touche jamais le disque : seuls les noms de la liste blanche ou les clés générées existent."""
    from ontoforge.core.project import Project
    p = Project(id="x", name="x", created_at="2026-11-07", updated_at="2026-11-07")
    with pytest.raises(fm.FileNotFound):
        fm.read(p, path)


def test_generated_files_are_read_only_even_with_force(client, pid):
    gen = next(f["path"] for f in client.get(f"/api/projects/{pid}/files").json()["files"] if f["generated"])
    before = client.get(f"/api/projects/{pid}/files/{gen}").json()["content"]
    r = client.put(f"/api/projects/{pid}/files/{gen}", json={"content": "// pirate\n", "force": True})
    assert r.status_code == 403
    r = client.post(f"/api/projects/{pid}/files/diff", json={"path": gen, "content": "// pirate\n"})
    assert r.status_code == 403
    assert client.get(f"/api/projects/{pid}/files/{gen}").json()["content"] == before


def test_oversized_content_is_refused(client, pid):
    big = P + "# " + "x" * (fm.MAX_BYTES + 10) + "\n"
    r = client.put(f"/api/projects/{pid}/files/onto.ttl", json={"content": big})
    assert r.status_code == 422 and r.json()["diagnostics"][0]["code"] == "too-large"
