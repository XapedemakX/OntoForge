"""Profil Neo4j : capacités, types XSD, nommage, recommandations (vocabulaire de l'oracle trap)."""
from pathlib import Path

import pytest
import yaml

from ontoforge.mapping.profile_api import get_profile
from ontoforge.mapping.profiles import curiosity as cur
from ontoforge.mapping.profiles import neo4j as p

ROOT = Path(__file__).resolve().parents[2]
XSD = "http://www.w3.org/2001/XMLSchema#"
OWL2_DATATYPES = [
    "owl:real", "owl:rational", "xsd:decimal", "xsd:integer", "xsd:nonNegativeInteger", "xsd:nonPositiveInteger",
    "xsd:positiveInteger", "xsd:negativeInteger", "xsd:long", "xsd:int", "xsd:short", "xsd:byte",
    "xsd:unsignedLong", "xsd:unsignedInt", "xsd:unsignedShort", "xsd:unsignedByte", "xsd:double", "xsd:float",
    "xsd:string", "xsd:normalizedString", "xsd:token", "xsd:language", "xsd:Name", "xsd:NCName", "xsd:NMTOKEN",
    "xsd:boolean", "xsd:hexBinary", "xsd:base64Binary", "xsd:anyURI", "xsd:dateTime", "xsd:dateTimeStamp",
    "rdf:PlainLiteral", "rdf:XMLLiteral", "rdfs:Literal",
]
PREFIX = {"owl": "http://www.w3.org/2002/07/owl#", "xsd": XSD, "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
          "rdfs": "http://www.w3.org/2000/01/rdf-schema#"}


def _iri(curie):
    pre, loc = curie.split(":")
    return PREFIX[pre] + loc


def test_capabilities_neo4j5():
    c = p.CAPABILITIES
    assert c["multi_label"] and c["edge_properties"] and c["composite_key"] and c["unique_constraint"]
    assert c["native_reverse_edges"] is False
    assert c["decimal_type"] in (False, "none")
    assert c["node_key"] == "enterprise" and c["existence_constraint"] == "enterprise"
    assert c["type_constraint"] == "enterprise" and c["unique_constraint"] in (True, "native")
    assert c["relationship_cardinality"] in (False, "none")
    assert set(p.CAPABILITY_NOTES) <= set(c)


@pytest.mark.parametrize("curie", OWL2_DATATYPES)
def test_xsd_map_covers_owl2_datatypes(curie):
    d = p.map_xsd(_iri(curie))
    assert d["type"] in p.PG_TO_CYPHER_TYPE


def test_xsd_losses():
    assert p.map_xsd(XSD + "decimal")["lossy"] is True
    assert p.map_xsd(XSD + "decimal")["type"] == "Float"
    assert p.map_xsd(XSD + "hexBinary")["lossy"] is True
    assert p.map_xsd(XSD + "dateTime")["type"] == "DateTime" and not p.map_xsd(XSD + "dateTime")["lossy"]
    assert p.map_xsd(XSD + "integer")["type"] == "Integer"
    assert p.map_xsd(XSD + "date")["type"] == "Date"
    unk = p.map_xsd("http://example.org/myType")
    assert unk["type"] == "String" and unk["lossy"] is True
    assert p.map_xsd(None)["type"] == "String"


def test_naming_conventions():
    assert p.node_name("repair order") == "RepairOrder"
    assert p.node_name("https://example.org/auto#electricVehicle") == "ElectricVehicle"
    assert p.edge_name("isPartOf") == "IS_PART_OF"
    assert p.edge_name("has-part") == "HAS_PART"
    assert p.prop_name("VIN_Code") == "vinCode" or p.prop_name("VIN_Code").startswith("vin")
    assert p.prop_name("firstRegistrationDate") == "firstRegistrationDate"
    assert p.prop_name("label", "fr") == "label_fr"
    assert not p.node_name("2fast")[0].isdigit()
    # Neo4j ne stocke pas d'inverse (O04) : jamais de type inverse
    assert p.reverse_name("isPartOf", "hasPart") is None and p.reverse_name("isPartOf") is None


def test_recommendations_cover_catalogue():
    assert set(cur.RECOMMENDATIONS) <= set(p.RECOMMENDATIONS)
    assert len([k for k in p.RECOMMENDATIONS if k != "X00"]) >= 66
    for rule, e in p.RECOMMENDATIONS.items():
        ids = [o["id"] for o in e["options"]]
        assert e["recommended"] in ids, rule
        assert len(ids) == len(set(ids)), rule
        assert e["rationale"], rule


def test_recommendations_match_oracle():
    y = yaml.safe_load((ROOT / "samples/trap/expected-findings.yaml").read_text(encoding="utf-8"))
    lines = (ROOT / "samples/trap/expected-findings.yaml").read_text(encoding="utf-8").splitlines()
    start = next(i for i, l in enumerate(lines) if "Vocabulaire d'options" in l) + 1
    body = []
    for l in lines[start:]:
        if not l.startswith("#   "):
            break
        body.append(l[1:].strip())
    vocab = {w.strip() for w in " ".join(body).split(",") if w.strip()}
    assert "multi_label" in vocab and "node_type" in vocab
    seen = {}
    for f in y["findings"]:
        n = f.get("neo4j")
        if not n:
            continue
        ids = [o["id"] for o in p.RECOMMENDATIONS[f["rule"]]["options"]]
        assert n["recommended"] in ids, (f["rule"], n["recommended"])
        seen.setdefault(f["rule"], set()).add(n["recommended"])
        if f["rule"] not in ("C09", "D05", "O13", "R01"):
            assert p.recommend(f["rule"]) == n["recommended"], f["rule"]
    assert len(seen) >= 60
    # tous les ids d'options sont du vocabulaire de l'oracle (hors extensions documentées)
    allowed_extra = {"edge_pair"}
    for rule, e in p.RECOMMENDATIONS.items():
        for o in e["options"]:
            assert o["id"] in vocab or o["id"] in allowed_extra, (rule, o["id"])


def test_r01_context_and_options_model():
    assert p.recommend("R01") == "dereify_relationship"
    assert p.recommend("R01", {"links": 4}) == "keep_node"
    opts = p.options("C02")
    assert [o.id for o in opts][0] == "multi_label"
    assert [o.id for o in opts if "neo4j" in o.recommended_for] == ["multi_label"]
    assert p.options("ZZZ") == [] and p.recommend("ZZZ") is None


def test_profile_api_integration():
    prof = get_profile("neo4j")
    assert prof.source.endswith("profiles.neo4j")
    assert prof.multi_label and prof.edge_properties and not prof.native_reverse
    assert prof.node("repair order") == "RepairOrder"
    assert prof.edge("isPartOf") == "IS_PART_OF"
    assert prof.datatype(XSD + "decimal")[:2] == ("Float", True)
    assert prof.rationale("C02")


def test_langstring_not_owl2_but_tolerated():
    d = p.map_xsd("http://www.w3.org/1999/02/22-rdf-syntax-ns#langString")
    assert d["owl2"] is False and d["type"] == "String" and d["lossy"] is True
    assert p.map_xsd("http://www.w3.org/1999/02/22-rdf-syntax-ns#PlainLiteral")["owl2"] is True
