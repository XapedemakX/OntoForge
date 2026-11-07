"""Tests du générateur Curiosity (targets/curiosity.py)."""
from __future__ import annotations

import json
import pathlib
import re

import pytest

from ontoforge.core.pg_model import PGModel
from ontoforge.targets.curiosity import CS_KEYWORDS, cs_ident, generate

FIX = pathlib.Path(__file__).parent / "fixtures" / "pg_curiosity_automaint.json"
FILES = {"Schema.cs", "Edges.cs", "RegisterSchema.cs", "Connector.cs", "README-curiosity.md"}


@pytest.fixture(scope="module")
def pg() -> PGModel:
    return PGModel.model_validate(json.loads(FIX.read_text(encoding="utf-8")))


@pytest.fixture(scope="module")
def out(pg):
    return generate(pg)


def _strip(src: str) -> str:
    src = re.sub(r"//[^\n]*", "", src)
    src = re.sub(r'"(?:\\.|[^"\\])*"', '""', src)
    return src


def test_files_and_determinism(pg, out):
    assert set(out) == FILES
    assert generate(pg) == out


def test_header_and_unverified_marker(out):
    for name in FILES - {"README-curiosity.md"}:
        assert "Généré par OntoForge" in out[name]
    assert "Généré par OntoForge" in out["README-curiosity.md"]
    assert "API à valider" in out["README-curiosity.md"] or "À VÉRIFIER" in out["README-curiosity.md"]
    assert "À VÉRIFIER" in out["Connector.cs"]


def test_schema_constructs(pg, out):
    s = out["Schema.cs"]
    code = re.sub(r"//[^\n]*", "", s)
    concrete = [n for n, t in pg.node_types.items() if not t.abstract]
    assert code.count("[Node]") == len(concrete)
    assert code.count("[Key]") == len(concrete)  # exactement une clé par type
    assert "[Property]" in s and "[Timestamp]" in s and "/// <" in s
    assert code.count("[Timestamp]") <= len(concrete)
    # les types abstraits ne sont pas générés
    for n, t in pg.node_types.items():
        if t.abstract:
            assert f"class {n}\n" not in s


def test_one_key_per_class_is_string(out):
    s = out["Schema.cs"]
    s = re.sub(r"//[^\n]*", "", s)
    for block in re.split(r"\[Node\]", s)[1:]:
        body = block.split("\n    }\n")[0]
        keys = re.findall(r"\[Key\] public (\S+) ", body)
        assert keys == ["string"], keys
        assert len(re.findall(r"\[Timestamp\]", body)) <= 1


def test_edges_in_pairs(pg, out):
    e = out["Edges.cs"]
    assert "static class Edges" in e
    for et in pg.edge_types:
        assert cs_ident(et.name) in e
        if et.reverse:
            assert cs_ident(et.reverse) in e


def test_register_and_connector(out):
    r, c = out["RegisterSchema.cs"], out["Connector.cs"]
    assert "CreateNodeSchemaAsync" in r and "CreateEdgeSchemaAsync" in r
    assert "AddOrUpdate" in c and "Link(" in c and "CommitPendingAsync" in c
    assert "Validation" in c or "validation" in c


@pytest.mark.parametrize("name", sorted(FILES - {"README-curiosity.md"}))
def test_braces_balanced(out, name):
    src = _strip(out[name])
    assert src.count("{") == src.count("}")
    if name != "Connector.cs":  # chaînes interpolées $"{...}" : parenthèses non fiables
        assert src.count("(") == src.count(")")
    assert src.count("[") == src.count("]")


def test_identifiers_valid(out):
    for name in ("Schema.cs", "Edges.cs"):
        for ident in re.findall(r"public (?:class|static class|const string|[\w\[\]<>?]+) @?(\w+)", out[name]):
            assert re.fullmatch(r"[A-Za-z_]\w*", ident)
    # aucun mot-clé C# nu comme nom de propriété
    for m in re.finditer(r"\[(?:Key|Property|Timestamp)\] public [\w\[\]<>?]+ (\S+) \{", out["Schema.cs"]):
        assert m.group(1) not in CS_KEYWORDS


def test_cs_ident():
    assert cs_ident("class") == "@class" and cs_ident("1abc") == "_1abc"
    assert cs_ident("a-b c") == "a_b_c" and cs_ident("") == "_"


def test_empty_model_no_exception():
    out = generate(PGModel(target="curiosity"))
    assert set(out) == FILES
    assert "Généré par OntoForge" in out["README-curiosity.md"]
    assert generate(PGModel(target="curiosity"), None) == out


def test_hostile_names():
    from ontoforge.core.pg_model import NodeType, PGProperty
    pg = PGModel(target="curiosity", node_types={
        "class": NodeType(name="class", labels=["class"], key=["Key"],
                          properties=[PGProperty(name="Key", type="String"), PGProperty(name="Type", type="Integer"),
                                      PGProperty(name="9x y", type="DateTime")]),
        "Edges": NodeType(name="Edges", labels=["Edges"], properties=[])})
    s = generate(pg)["Schema.cs"]
    assert "class @class" in s and "TypeValue" in s and s.count("{") == s.count("}")


# --- Itération 2 : revue neo4j (clé composite, arêtes symétriques / collisions, exhaustivité des validations) ---
NEO_FIX = FIX.parent / "pg_neo4j_automaint.json"


def _neo_pg() -> PGModel:
    return PGModel.model_validate(json.loads(NEO_FIX.read_text(encoding="utf-8")))


def test_composite_key_escapes_percent_and_rejects_empty_components():
    out = generate(_neo_pg())
    s, c = out["Schema.cs"], out["Connector.cs"]
    assert 'Replace("%", "%25").Replace("|", "%7C")' in s
    assert '?? ""' not in s  # null n'est plus confondu avec ""
    # contrôle des composants AVANT WithComputedKey
    for m in re.finditer(r"WithComputedKey\(\); // clé composite", c):
        before = c[:m.start()].rsplit("foreach", 1)[1]
        assert "IsNullOrWhiteSpace" in before and "composant de clé vide" in before


def _encode(parts):  # miroir Python de BuildKey
    return "|".join(p.replace("%", "%25").replace("|", "%7C") for p in parts)


def test_key_encoding_is_injective():
    assert _encode(["a%7Cb", "c"]) != _encode(["a|b", "c"])
    assert _encode(["a", "b|c"]) != _encode(["a|b", "c"])


def test_symmetric_edge_same_constant_both_sides():
    out = generate(_neo_pg())
    e = out["Edges.cs"]
    assert "ColleagueOf" in e and "COLLEAGUEOF" not in e and "HASMODEL" not in e
    assert len(re.findall(r"const string ColleagueOf\b", e)) == 1
    assert re.search(r"Edges\.ColleagueOf, Edges\.ColleagueOf", out["Connector.cs"])
    assert "HasModel" in e and "ModelOf" in e


def test_edge_consts_unique_and_no_collision_with_node_types():
    from ontoforge.core.pg_model import EdgeType, NodeType
    pg = PGModel(target="curiosity",
                 node_types={n: NodeType(name=n, labels=[n], properties=[]) for n in ("Warranty", "Car")},
                 edge_types=[EdgeType(name="Warranty", from_="Car", to="Warranty"),
                             EdgeType(name="A_B", from_="Car", to="Car"),
                             EdgeType(name="AB", from_="Car", to="Car")])
    e = generate(pg)["Edges.cs"]
    idents = re.findall(r"public const string (\w+) =", e)
    assert len(idents) == len(set(idents))
    assert "const string Warranty " not in e and "WarrantyEdge" in e
    assert "AB " in e and "AB" != "ABEdge"


@pytest.mark.parametrize("fixture", [FIX, NEO_FIX])
def test_every_validation_has_executable_code(fixture):
    pg = PGModel.model_validate(json.loads(fixture.read_text(encoding="utf-8")))
    c = generate(pg)["Connector.cs"]
    code = "\n".join(l for l in c.splitlines() if not l.strip().startswith("//"))
    for v in pg.validations:
        assert f'"{v.id}"' in code, v.id  # Report / NotChecked / Guaranteed émis à l'exécution
    assert "private static void NotChecked" in c


def test_unimplementable_validations_warn_at_runtime():
    c = generate(_neo_pg())["Connector.cs"]
    for vid in ("V12", "V14", "V15", "V16"):
        assert re.search(rf'NotChecked\("{vid}"', c), vid
    assert re.search(r'Report\("V08"', c) and re.search(r'Report\("V04"', c)


def test_absent_property_validation_is_notchecked_not_guaranteed():
    import re as _re
    c = generate(_neo_pg())["Connector.cs"]
    assert not _re.search(r'Guaranteed\("V12"', c)
    assert len(_re.findall(r'NotChecked\("V12"', c)) >= 2  # Validate* et CheckGraph
