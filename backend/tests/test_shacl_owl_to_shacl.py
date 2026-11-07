from ontoforge.core.onto_model import (OWL, XSD, DatatypeProperty, ObjectProperty, OntClass, OntologyMeta, OntoModel,
                                        Restriction)
from ontoforge.shacl.export_shapes import serialize_shapes
from ontoforge.shacl.owl_to_shacl import generate_shapes

NS = "https://example.org/t#"


def _onto():
    return OntoModel(
        meta=OntologyMeta(iri="https://example.org/t"),
        classes={
            NS + "Vehicle": OntClass(iri=NS + "Vehicle", has_keys=[[NS + "vin"]],
                                      restrictions=[Restriction(property=NS + "ofModel", kind="some")]),
            NS + "Model": OntClass(iri=NS + "Model"),
            NS + "Car": OntClass(iri=NS + "Car", sub_class_of=[NS + "Vehicle"], disjoint_with=[NS + "Bike"]),
            NS + "Bike": OntClass(iri=NS + "Bike", sub_class_of=[NS + "Vehicle"]),
        },
        object_properties={NS + "ofModel": ObjectProperty(iri=NS + "ofModel", domain=[NS + "Vehicle"], range=[NS + "Model"])},
        datatype_properties={NS + "vin": DatatypeProperty(iri=NS + "vin", domain=[NS + "Vehicle"], range=[XSD + "string"],
                                                           functional=True)},
    )


def test_generate_basic_constraints_and_notes():
    shapes, notes = generate_shapes(_onto())
    ttl = serialize_shapes(shapes)
    assert "sh:targetClass" in ttl and "sh:datatype" in ttl and "sh:class" in ttl
    assert "sh:maxCount 1" in ttl and "sh:minCount 1" in ttl
    assert any(n.startswith("[OWA]") for n in notes)
    assert any(n.startswith("[NON-CORE]") for n in notes)  # unicité de clé
    assert len(notes) == len(set(notes))


def test_generated_shapes_roundtrip_and_validate():
    from ontoforge.shacl.import_shapes import parse_shapes
    from ontoforge.shacl.validate import validate
    shapes, _ = generate_shapes(_onto())
    m2, w = parse_shapes(serialize_shapes(shapes))
    assert w == []
    data = f"@prefix t: <{NS}> . t:v a t:Vehicle ; t:vin 'A' ."
    r = validate(data, m2)
    assert not r.conforms  # ofModel manquant (restriction some)
    assert any(x.path == NS + "ofModel" for x in r.results)


def test_pattern_anchored_and_datatype_subtypes():
    from ontoforge.core.onto_model import DataRange, DatatypeDef
    from ontoforge.shacl.import_shapes import parse_shapes
    from ontoforge.shacl.validate import validate
    o = _onto()
    o.datatypes[NS + "Code"] = DatatypeDef(iri=NS + "Code", definition=DataRange(base=XSD + "string", facets={XSD + "pattern": "[A-Z]{3}"}))
    o.datatype_properties[NS + "code"] = DatatypeProperty(iri=NS + "code", domain=[NS + "Model"], range=[NS + "Code"])
    o.datatype_properties[NS + "count"] = DatatypeProperty(iri=NS + "count", domain=[NS + "Model"], range=[XSD + "decimal"])
    shapes, notes = generate_shapes(o)
    m, _ = parse_shapes(serialize_shapes(shapes))
    pre = f"@prefix t: <{NS}> . @prefix xsd: <{XSD}> . "
    ok = validate(pre + "t:m a t:Model ; t:code 'ABC' ; t:count 3, '5'^^xsd:int, 2.5 .", m)
    assert not [x for x in ok.results if x.path in (NS + "code", NS + "count")]
    bad = validate(pre + "t:m a t:Model ; t:code 'ABCDE' .", m)
    assert any(x.path == NS + "code" for x in bad.results)
    assert any("xsd:pattern" in n for n in notes) and any("XSD dérivés" in n for n in notes)
