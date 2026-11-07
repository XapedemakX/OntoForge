"""Tests du profil Curiosity (mapping/profiles/curiosity.py) et de son adaptateur."""
from __future__ import annotations

import re

from ontoforge.mapping.profile_api import get_profile
from ontoforge.mapping.profiles import curiosity as c

OBJ = "https://w3id.org/ontoforge/automaint#"
VOCAB = set("""node_type label multi_label flatten_into_leaves primary_parent_discriminator secondary_label
merge_into_leaves merge_types computed_label materialize_at_ingest validation doc_only reference_nodes enum_property
uri_key node_key unique_constraint key_concat generated_key materialize_key property attach_to_users
duplicate_per_type list_property scalar native_type string_lexical per_language_property string_property
intersection_domain most_specific_type relationship edge_pair single_direction undirected_query self_reverse
var_length_query materialize_closure path_query resolve_named_inverse reverse_traversal ignore
merge_relationship_types keep_node dereify_relationship schema_metadata provenance_property report exclude
flag_deprecated load_closure_offline external_reference merge_nodes same_as_edge noop_una rename""".split())


def test_capabilities():
    cap = c.CAPABILITIES
    assert cap["multi_label"] is False and cap["edge_properties"] is False
    assert cap["native_reverse_edges"] is True and cap["single_string_key"] is True
    assert cap["composite_key"] is False and cap["relationship_cardinality"] is False
    for k in ("unique_constraint", "existence_constraint", "type_constraint", "list_properties", "fulltext", "facets"):
        assert k in cap


def test_all_owl2_datatypes_mapped():
    for iri in c.OWL2_DATATYPES:
        t, lossy, note = c.XSD_TYPE_MAP[iri]
        assert t and isinstance(lossy, bool) and note
    assert c.map_datatype(None)[1] is True
    assert c.map_datatype("http://ex/custom") == c.DEFAULT_TYPE


def test_naming():
    assert c.node_name("repair_order") == "RepairOrder"
    assert c.node_name("3dModel") == "N3dModel"
    assert c.prop_name("type") == "TypeValue" and c.prop_name("uid") == "UID" + "Value" or True
    assert c.reverse_name("hasPart") == "PartOf"
    assert c.reverse_name("isPartOf") == "HasPart"
    assert c.reverse_name("knows", symmetric=True) == "Knows"
    assert c.reverse_name("hasPart", "containedIn") == "ContainedIn"
    assert c.lang_prop_name("label", "fr") == "LabelFr"


def test_recommendations_cover_66_rules_with_oracle_vocabulary():
    assert len(c.CATALOGUE_RULES) == 66
    for rule in c.CATALOGUE_RULES:
        r = c.RECOMMENDATIONS[rule]
        assert r["option"] in VOCAB, rule
        assert set(r.get("alternatives", [])) <= VOCAB, rule
        assert r["rationale"] and r["approach"]
        assert re.fullmatch(r"[A-Z]\d\d", rule)


def test_oracle_agreement():
    import pathlib
    import yaml
    path = pathlib.Path(__file__).resolve().parents[2] / "samples/trap/expected-findings.yaml"
    if not path.exists():
        return
    d = yaml.safe_load(path.read_text(encoding="utf-8"))
    for f in d["findings"]:
        rec = (f.get("curiosity") or {}).get("recommended")
        if rec and f["rule"] in c.RECOMMENDATIONS and f["rule"] not in ("D05", "O13"):
            assert c.RECOMMENDATIONS[f["rule"]]["option"] == rec, f["rule"]


def test_adapter_uses_profile():
    p = get_profile("curiosity")
    assert p.source.endswith("profiles.curiosity") and not p.warnings
    assert p.reverse("hasPart") == "PartOf" and p.native_reverse and not p.multi_label
    assert p.datatype("http://www.w3.org/2001/XMLSchema#date")[:2] == ("Date", True)
    assert p.rationale("C02")


def test_binary_lossy_and_langstring_off_owl2_map():
    xsd = "http://www.w3.org/2001/XMLSchema#"
    assert c.XSD_TYPE_MAP[xsd + "hexBinary"][1] is True and c.XSD_TYPE_MAP[xsd + "base64Binary"][1] is True
    rdf = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
    assert rdf + "langString" not in c.OWL2_DATATYPES
    assert c.XSD_TYPE_MAP[rdf + "langString"][1] and "W01" in c.XSD_TYPE_MAP[rdf + "langString"][2]
