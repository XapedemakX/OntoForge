"""L13 : PGType Decimal (D-L13-01)."""
import pathlib

from ontoforge.core.pg_model import NodeType, PGModel, PGProperty
from ontoforge.io.rdf_import import parse_ontology
from ontoforge.mapping.engine import analyze

AM = "https://w3id.org/ontoforge/automaint#"
P = pathlib.Path(__file__).resolve().parents[2] / "samples" / "automaint" / "automaint.ttl"


def _pg(target):
    m, _ = parse_ontology(P.read_text(encoding="utf-8"), filename=P.name)
    return analyze(m, None, target)


def _types(pg):
    return {p.source: p.type for nt in pg.node_types.values() for p in nt.properties}


def test_curiosity_decimal_lossless():
    pg = _pg("curiosity")
    assert _types(pg)[AM + "unitPrice"] == "Decimal"
    assert not [f for f in pg.findings if f.rule == "D05" and f.subject == AM + "unitPrice"]


def test_neo4j_decimal_stays_float_with_loss():
    pg = _pg("neo4j")
    assert _types(pg)[AM + "unitPrice"] == "Float"
    assert [f for f in pg.findings if f.rule == "D05" and f.subject == AM + "unitPrice"]


def test_generators():
    from ontoforge.targets import curiosity, graphql
    pg = PGModel(target="curiosity", node_types={"Item": NodeType(name="Item", labels=["Item"], key=["id"], properties=[
        PGProperty(name="id", type="String"), PGProperty(name="price", type="Decimal")])})
    cs = "\n".join(curiosity.generate(pg).values())
    assert "decimal price" in cs
    gql = graphql.generate(pg)
    gql = "\n".join(gql.values()) if isinstance(gql, dict) else gql
    assert "scalar Decimal" in gql and "price: Decimal" in gql
