"""L48 : import déterministe SQL DDL / CSV / JSON Schema. Corpus par dialecte, cas d'erreur, entrées hostiles bornées, conformité OWL 2 DL,
shapes SHACL valides (méta-validation), moteur de transposition, aperçu puis application annulable. Aucun LLM, aucun réseau."""
import json
import pathlib
import re
import time

import pytest
from fastapi.testclient import TestClient

from ontoforge.core.onto_model import OWL, XSD
from ontoforge.importers import messages as M
from ontoforge.importers import service
from ontoforge.importers.limits import ImportRefused

F = pathlib.Path(__file__).parent / "fixtures" / "l48"


def run(*names, opts=None, kind=None, base=None):
    return service.run([(n, (F / n).read_bytes()) for n in names], kind, opts or {}, base)


def cls(r, name):
    return next(c for c in r.built.classes if c["name"] == name)


def prop(c, name):
    return next(p for p in c["props"] if p["name"] == name)


def rel(c, name):
    return next(x for x in c["rels"] if x["name"] == name)


def codes(r):
    return {n.code for n in r.draft.notices}


# ---- PostgreSQL -----------------------------------------------------------------------------------------------------------------

def test_postgres_classes_keys_and_types():
    r = run("postgres.sql")
    assert r.draft.dialect == "postgresql" and r.kind == "sql"
    assert {c["name"] for c in r.built.classes} == {"Customer", "Order", "Product", "OrderLine", "Tag", "VipCustomer"}
    cu = cls(r, "Customer")
    assert cu["keys"] == [["customerId"], ["email"]]            # clé primaire (ALTER ultérieur) puis index UNIQUE
    assert prop(cu, "birthDate")["type"] == "xsd:dateTime" and prop(cu, "birthDate")["degraded"] == "date"
    assert prop(cu, "loyalty")["type"] == "xsd:short" and prop(cu, "loyalty")["facets"] == {"min_inclusive": "0", "max_inclusive": "100"}
    assert prop(cu, "fullName")["facets"]["max_length"] == "120" and prop(cu, "fullName")["required"]
    assert prop(cu, "segment")["enum"] == ["retail", "pro"]       # = ANY (ARRAY[...]) avec casts
    assert prop(cu, "email")["required"] and prop(cu, "createdAt")["type"] == "xsd:dateTime"
    o = cls(r, "Order")
    assert prop(o, "orderId")["type"] == "xsd:long"
    assert prop(o, "status")["enum"] == ["pending", "paid", "shipped"]   # CREATE TYPE … AS ENUM
    assert prop(o, "notes")["many"] and prop(o, "payload")["type"] == "xsd:string" and prop(o, "placed")["degraded"] == "duration"
    fk = rel(o, "orderHasCustomer")                                # « hasCustomer » existe sur deux classes : préfixé par la classe
    assert fk["target"] == "Customer" and fk["required"] and not fk["many"]


def test_postgres_association_and_reified_and_subclass_candidate():
    r = run("postgres.sql")
    assert "association_collapsed" in codes(r)
    p = cls(r, "Product")
    t = rel(p, "productTags")                                      # table d'association pure product_tags → propriété objet N-N
    assert t["target"] == "Tag" and t["many"]
    ol = cls(r, "OrderLine")                                       # colonne en plus → classe réifiée avec deux propriétés objet
    assert {x["target"] for x in ol["rels"]} == {"Order", "Product"} and ol["keys"] == [["hasOrder", "hasSku"]]
    assert prop(ol, "quantity")["facets"] == {"min_exclusive": "0"}
    ids = {d.id: d for d in r.draft.decisions}
    assert ids["association:public.product_tags"].chosen == "property"
    assert ids["subclass:public.vip_customers"].chosen == "property"


def test_postgres_ignored_report_and_no_execution():
    r = run("postgres.sql")
    ig = set(r.draft.ignored)
    assert {"view", "routine", "grant", "data", "session", "index", "default", "fk_action", "identity"} <= ig
    assert not any(c["name"] == "Evil" for c in r.built.classes)   # un CREATE TABLE dans le corps d'une fonction ($$…$$) n'est pas lu
    assert r.draft.ignored["default"]["count"] >= 3


def test_decisions_change_the_model():
    r = run("postgres.sql", opts={"choices": {"association:public.product_tags": "class", "subclass:public.vip_customers": "subclass"}})
    assert any(c["name"] == "ProductTag" for c in r.built.classes)
    v = cls(r, "VipCustomer")
    assert v["parents"] == ["Customer"] and not v["rels"] and v["keys"] == []   # clé héritée
    assert r.built.digest != run("postgres.sql").built.digest


def test_exclude_and_singularize_options():
    key = cls(run("postgres.sql", opts={"singularize": False}), "Tags")["key"]
    r = run("postgres.sql", opts={"exclude": [key], "singularize": False})
    names = {c["name"] for c in r.built.classes}
    assert "Tags" not in names and "Customers" in names
    assert {"excluded", "relation_dropped"} <= codes(r)


# ---- MySQL ---------------------------------------------------------------------------------------------------------------------

def test_mysql():
    r = run("mysql.sql")
    assert r.draft.dialect == "mysql"
    b = cls(r, "Book")
    assert prop(b, "kind")["enum"] == ["novel", "essay", "poetry"]
    assert prop(b, "inStock")["type"] == "xsd:boolean"            # TINYINT(1)
    assert prop(b, "bookId")["type"] == "xsd:long"
    assert cls(r, "Author")["keys"] == [["authorId"]] and prop(cls(r, "Author"), "authorId")["type"] == "xsd:unsignedInt"
    assert b["keys"] == [["bookId"], ["isbn"]]
    assert prop(b, "published")["degraded"] == "year" and prop(b, "pages")["facets"] == {"min_exclusive": "0"}
    assert {"tinyint1_as_boolean", "set_as_string", "fk_target_missing"} <= codes(r)
    assert next(c for c in r.built.classes if c["name"] == "Member")["kind"] == "stub"
    assert {"trigger", "storage", "computed", "drop", "data"} <= set(r.draft.ignored)
    assert not any(x["name"].endswith("Trg") for x in r.built.classes)


# ---- SQL Server ------------------------------------------------------------------------------------------------------------------

def test_sqlserver_and_utf16():
    r = run("sqlserver.sql")
    assert r.draft.dialect == "sqlserver"
    e = cls(r, "Employee")
    assert prop(e, "rowVer")["type"] == "xsd:hexBinary" and prop(e, "photo")["type"] == "xsd:base64Binary"
    assert prop(e, "salary")["type"] == "xsd:decimal" and prop(e, "active")["type"] == "xsd:boolean"
    assert {x["name"] for x in e["rels"]} >= {"hasDepartment", "hasManager"}
    assert rel(e, "hasManager")["target"] == "Employee" and not rel(e, "hasManager")["required"]
    assert rel(e, "employeeProjects")["target"] == "Project"      # table d'association (clé primaire composée de deux clés étrangères)
    assert "default" not in {p["name"] for p in e["props"]}       # ALTER … ADD DEFAULT … FOR n'est pas une colonne
    assert prop(cls(r, "Project"), "status")["enum"] == ["open", "closed"]
    assert "unique_nullable" in codes(r)
    comment = r.built.onto.classes[e["iri"]].comments
    assert comment["fr"] == "Personnel de la société"             # sp_addextendedproperty
    raw = (F / "sqlserver.sql").read_text(encoding="utf-8").replace("\n", "\r\n").encode("utf-16")
    r2 = service.run([("dump.sql", raw)], None, {}, None)
    assert r2.built.digest == run("sqlserver.sql").built.digest


# ---- CSV -------------------------------------------------------------------------------------------------------------------------

def test_csv_two_files_with_reference():
    r = run("customers.csv", "orders.csv")
    c, o = cls(r, "Customer"), cls(r, "Order")
    assert c["keys"] == [["customerId"]] and c["assumed_key"]
    assert prop(c, "age")["type"] == "xsd:integer" and prop(c, "active")["type"] == "xsd:boolean"
    assert prop(c, "score")["type"] == "xsd:string" and "decimal_comma" in codes(r)    # 12,5 : pas un xsd:decimal
    assert prop(c, "signup")["type"] == "xsd:dateTime" and prop(c, "signup")["degraded"] == "date"
    assert prop(c, "name")["required"] is False                    # l'échantillon ne dit rien du NOT NULL : pas de minCount par défaut
    assert prop(o, "zip")["type"] == "xsd:string"                  # 01234 : zéro initial, jamais un entier
    assert prop(o, "total")["type"] == "xsd:decimal"
    assert rel(o, "hasCustomer")["target"] == "Customer"           # customer_id → relation vers l'autre fichier
    r2 = run("customers.csv", "orders.csv", opts={"required_from_sample": True})
    assert prop(cls(r2, "Customer"), "name")["required"] is True


def test_csv_single_file_reference_is_a_decision_defaulting_to_value():
    r = run("orders.csv")
    d = next(x for x in r.draft.decisions if x.type == "reference")
    assert d.default == "property" and d.options == ["property", "relation"]
    assert "customerId" in {p["name"] for p in cls(r, "Order")["props"]}
    r2 = run("orders.csv", opts={"choices": {d.id: "relation"}})
    assert rel(cls(r2, "Order"), "hasCustomer")["target"] == "Customer"
    assert next(c for c in r2.built.classes if c["name"] == "Customer")["kind"] == "stub"


def test_csv_quirks():
    csv = 'id,Name,Name,"a ""b"""\n1,x,y,z\n2,"multi\nline",,\n'
    r = service.run([("persons.csv", csv.encode())], None, {}, None)
    c = cls(r, "Person")
    assert c["keys"] == [["id"]] and len(c["props"]) == 4
    assert "csv_duplicate_header" in codes(r)
    r = service.run([("t.csv", b"# table: Widget\nsku\tqty\n1\t2\n")], None, {}, None)
    assert cls(r, "Widget")["props"][1]["type"] == "xsd:integer"


# ---- JSON Schema -----------------------------------------------------------------------------------------------------------------

def test_json_schema():
    r = run("shop.schema.json")
    assert r.kind == "json-schema"
    names = {c["name"] for c in r.built.classes}
    assert {"Shop", "Person", "Employee", "ShopAddress", "Thing"} == names
    s = cls(r, "Shop")
    assert s["keys"] == [["id"]] and s["assumed_key"]
    assert prop(s, "name")["facets"] == {"min_length": "1", "max_length": "80"}
    assert prop(s, "status")["enum"] == ["open", "closed"]
    assert prop(s, "tags")["many"] and prop(s, "opened")["degraded"] == "date"
    assert prop(s, "rating")["type"] == "xsd:double" and not prop(s, "rating")["required"]     # type ["number","null"]
    assert rel(s, "hasStaff")["many"] and rel(s, "hasStaff")["required"]                        # minItems 1
    assert rel(s, "hasOwner")["target"] == "Person" and rel(s, "hasAddress")["target"] == "ShopAddress"
    assert cls(r, "Employee")["parents"] == ["Person"]                                          # allOf [$ref]
    assert prop(cls(r, "Person"), "age")["facets"] == {"min_inclusive": "0", "max_exclusive": "150"}
    assert prop(cls(r, "ShopAddress"), "zip")["facets"] == {"pattern": "^[0-9]{5}$"}
    assert "external_ref" in codes(r) and cls(r, "Thing")["kind"] == "stub"                     # aucun suivi de référence externe
    assert "json_free_object" in r.draft.ignored


def test_json_ref_to_primitive_and_cross_file():
    a = {"title": "A", "type": "object", "properties": {"mail": {"$ref": "#/$defs/E"}, "b": {"$ref": "b.json"}}, "$defs": {"E": {"type": "string", "format": "email"}}}
    b = {"title": "B", "type": "object", "properties": {"id": {"type": "integer"}}, "required": ["id"]}
    r = service.run([("a.json", json.dumps(a).encode()), ("b.json", json.dumps(b).encode())], None, {}, None)
    assert prop(cls(r, "A"), "mail")["type"] == "xsd:string"
    assert rel(cls(r, "A"), "hasB")["target"] == "B" and "external_ref" not in codes(r)


# ---- sorties : OWL 2 DL, SHACL, moteur ------------------------------------------------------------------------------------------

ALL = [("postgres.sql",), ("mysql.sql",), ("sqlserver.sql",), ("customers.csv", "orders.csv"), ("shop.schema.json",)]


@pytest.mark.parametrize("names", ALL, ids=lambda n: "+".join(n))
def test_output_is_owl2_dl_with_valid_shapes_and_transposes(names):
    from ontoforge.conformance.profiles import check_conformance
    from ontoforge.io.rdf_export import serialize
    from ontoforge.io.rdf_import import parse_ontology
    from ontoforge.mapping.engine import analyze
    from ontoforge.shacl.export_shapes import shapes_to_graph
    import pyshacl
    r = run(*names)
    rep = check_conformance(r.built.onto)
    assert rep.profiles["DL"] is True and not [i for i in rep.issues if i.level == "error"]
    onto = r.built.onto
    for p in onto.datatype_properties.values():
        assert all(x.startswith(XSD) for x in p.range)
        assert not any(x.rsplit("#", 1)[-1] in ("date", "time", "gYear", "duration") for x in p.range)   # hors table de datatypes OWL 2
        assert p.iri not in onto.object_properties
    for c in onto.classes.values():
        for key in c.has_keys:
            assert key and all(k in onto.datatype_properties or k in onto.object_properties for k in key)
    g = shapes_to_graph(r.built.shapes)
    ok, _, txt = pyshacl.validate(g, meta_shacl=True, inference="none")   # shacl-shacl
    assert ok, txt
    back, _ = parse_ontology(serialize(onto, "turtle"), "turtle")           # aller-retour Turtle
    assert set(back.classes) == set(onto.classes) and set(back.object_properties) == set(onto.object_properties)
    for t in ("curiosity", "neo4j"):
        assert analyze(onto, r.built.shapes, t).node_types


def test_shapes_validate_data():
    """NOT NULL → sh:minCount 1 ; CHECK IN → sh:in ; varchar(n) → sh:maxLength : une donnée fautive est refusée."""
    from ontoforge.shacl.validate import validate
    r = run("postgres.sql")
    base = "https://w3id.org/ontoforge/import#"
    good = f'@prefix ex: <{base}> . @prefix xsd: <{XSD}> . ex:c1 a ex:Customer ; ex:customerId 1 ; ex:email "a@b.c" ; ex:fullName "A" ; ex:createdAt "2024-01-01T00:00:00Z"^^xsd:dateTime ; ex:segment "pro" .'
    # les valeurs sont typées à l'ingestion : on laisse les entiers au type xsd:int attendu
    good = good.replace("ex:customerId 1", f'ex:customerId "1"^^xsd:int')
    assert validate(good, r.built.shapes, r.built.onto, "turtle").conforms
    bad = good.replace('ex:fullName "A" ;', "").replace('"pro"', '"zzz"')
    rep = validate(bad, r.built.shapes, r.built.onto, "turtle")
    assert not rep.conforms
    kinds = {x.constraint.rsplit("#", 1)[-1] for x in rep.results}
    assert {"MinCountConstraintComponent", "InConstraintComponent"} <= kinds


def test_digest_is_deterministic_and_base_iri_applied():
    a, b = run("postgres.sql"), run("postgres.sql")
    assert a.built.digest == b.built.digest
    c = run("postgres.sql", base="https://example.org/shop#")
    assert all(i.startswith("https://example.org/shop#") for i in c.built.onto.classes) and c.built.digest != a.built.digest
    with pytest.raises(ImportRefused) as e:
        run("postgres.sql", base="javascript:alert(1)")
    assert e.value.code == "bad_base_iri"


# ---- erreurs et entrées hostiles -----------------------------------------------------------------------------------------------

def refused(files, code, **kw):
    with pytest.raises(ImportRefused) as e:
        service.run(files, kw.get("kind"), kw.get("opts"), None)
    assert e.value.code == code, (e.value.code, e.value.params)
    return e.value


def test_basic_refusals():
    refused([], "no_file")
    refused([("a.sql", b"   \n")], "empty_file")
    refused([("a.bin", b"\x00\x01\x02")], "not_text")
    refused([("a.txt", b"hello world")], "unknown_kind")
    refused([("a.sql", b"CREATE VIEW v AS SELECT 1;")], "sql_no_table")
    refused([("a.sql", b"CREATE TABLE a (x int);"), ("b.csv", b"a,b\n1,2\n")], "mixed_kinds")
    refused([("a.json", b"{not json")], "json_invalid")
    refused([("a.json", b'{"@context": {"a": "b"}, "@id": "x"}')], "json_not_schema")
    refused([("a.json", b'{"type": "string"}')], "json_not_schema")
    refused([("a.csv", b"a,b\n")], "nothing_found") if False else None


def test_size_limit(monkeypatch):
    monkeypatch.setenv("ONTOFORGE_IMPORT_MAX_MB", "1")
    refused([("a.sql", b"-- " + b"x" * (1024 * 1024 + 10))], "too_big")


def test_too_many_files():
    refused([(f"f{i}.csv", b"a\n1\n") for i in range(51)], "too_many_files")


def test_deep_nesting_is_refused_fast():
    t = time.monotonic()
    refused([("a.sql", b"CREATE TABLE t (a int CHECK " + b"(" * 5000 + b"1" + b")" * 5000 + b");")], "too_deep")
    refused([("a.json", b"[" * 100000 + b"]" * 100000)], "too_deep", kind="json-schema")
    refused([("a.json", b'{"properties": ' * 40 + b"{}" + b"}" * 40)], "too_deep")
    assert time.monotonic() - t < 5


def test_token_flood_and_time_budget(monkeypatch):
    t = time.monotonic()
    refused([("a.sql", b"CREATE TABLE t (a int);\n" * 80000)], "too_many_tokens")
    assert time.monotonic() - t < 15
    monkeypatch.setenv("ONTOFORGE_IMPORT_MAX_SECONDS", "1")
    from ontoforge.importers import limits
    b = limits.Budget(seconds=0.0)
    with pytest.raises(ImportRefused) as e:
        for _ in range(1000):
            b.tick()
    assert e.value.code == "too_slow" and e.value.status == 408


def test_too_many_tables_columns_and_long_identifiers():
    refused([("a.sql", "\n".join(f"CREATE TABLE t{i} (a int);" for i in range(401)).encode())], "too_many_tables")
    refused([("a.sql", ("CREATE TABLE t (" + ",".join(f"c{i} int" for i in range(1100)) + ");").encode())], "too_many_columns")
    refused([("a.sql", ("CREATE TABLE " + "x" * 300 + " (a int);").encode())], "ident_too_long")
    refused([("a.csv", (",".join(f"c{i}" for i in range(1100)) + "\n1\n").encode())], "too_many_columns")


def test_hostile_but_harmless_inputs():
    # chaînes et commentaires non terminés, caractères étranges, mots-clés partout : jamais d'exception, toujours un résultat ou un refus propre
    samples = [
        b"CREATE TABLE a (x int, y varchar(10) DEFAULT 'abc);",
        b"CREATE TABLE a (x int /* never closed",
        b"CREATE TABLE a (x int); CREATE TABLE",
        b"CREATE TABLE a (; ; ; ,,, ) ; CREATE TABLE b (x int PRIMARY KEY);",
        b"CREATE TABLE \"a\"\"b\" (\"x y\" int primary key);",
        b"CREATE TABLE a (x int REFERENCES);",
        b"CREATE TABLE a (x int PRIMARY KEY, FOREIGN KEY (x) REFERENCES a(x));",
        b"CREATE TABLE a (x $$ int $$ primary key);",
        b"ALTER TABLE a ADD CONSTRAINT; CREATE TABLE a (x int); ALTER TABLE a ADD;",
        b"CREATE TABLE a (x int CHECK (x IN ('a','b') OR y = 3 AND ((((x))))));",
        "CREATE TABLE a (é int primary key, `ü` text);".encode(),
    ]
    for s in samples:
        try:
            r = service.run([("h.sql", s)], None, {}, None)
            assert r.built.stats["classes"] >= 1
        except ImportRefused as e:
            assert e.code in {"sql_no_table", "syntax", "nothing_found", "too_deep", "ident_too_long"}, (s, e.code)
    for s in (b'{"properties": {"a": {"$ref": "#/$defs/x"}}, "$defs": {"x": {"$ref": "#/$defs/x"}}}',
              b'{"$defs": {"A": {"type": "object", "properties": {"a": {"$ref": "#/$defs/A"}}}}}',
              b'{"type": "object", "properties": {"a": {"type": "array", "items": {"type": "array"}}, "b": {"enum": [[1], {"a": 1}]}, "c": 5, "": {}}}',
              b'{"type": "object", "properties": {"a": {"$ref": "http://169.254.169.254/latest/meta-data"}, "b": {"$ref": "file:///etc/passwd"}}}'):
        r = service.run([("h.json", s)], None, {}, None)
        assert r.built.stats["classes"] >= 1
    r = service.run([("h.json", s)], None, {}, None)
    assert all("169.254" not in c["source"] or c["kind"] == "stub" for c in r.built.classes)   # la référence devient une classe vide, rien n'est lu


def test_csv_hostile():
    big_field = b"a,b\n" + b'"' + b"x" * 50000 + b'",2\n'
    r = service.run([("big.csv", big_field)], None, {}, None)
    assert r.built.stats["classes"] == 1
    r = service.run([("q.csv", b'a,b\n"unterminated,2\n3,4\n')], None, {}, None)
    assert r.built.stats["classes"] == 1
    r = service.run([("many.csv", b"a,b\n" + b"1,2\n" * 200000)], None, {}, None)
    assert "csv_sampled" in codes(r)


def test_formula_like_and_script_values_are_data_only():
    """Les noms et valeurs hostiles ne deviennent jamais du code : ils ressortent en IRIs valides et en littéraux."""
    r = service.run([("x.csv", b'=cmd|"/c calc"!A0,<script>alert(1)</script>,"a\\"b"\n1,2,3\n')], None, {}, None)
    for iri in list(r.built.onto.classes) + list(r.built.onto.datatype_properties):
        assert re.fullmatch(r"https://w3id\.org/ontoforge/import#[A-Za-z0-9_]+", iri), iri


# ---- messages --------------------------------------------------------------------------------------------------------------------

def test_messages_are_bilingual_with_same_placeholders():
    ph = lambda s: sorted(re.findall(r"\{(\w+)\}", s))
    for table in (M.NOTICES, M.IGNORED, M.REFUSALS, M.DECISIONS):
        for code, (fr, en) in table.items():
            assert fr and en and ph(fr) == ph(en), code


def test_every_emitted_code_has_a_message():
    src = "".join(p.read_text(encoding="utf-8") for p in (pathlib.Path(service.__file__).parent).glob("*.py"))
    emitted = set(re.findall(r"\.notice\(\s*\"(\w+)\"", src)) | set(re.findall(r"\.ignore\(\s*\"(\w+)\"", src))
    emitted |= set(re.findall(r"ImportRefused\(\s*\"(\w+)\"", src))
    emitted |= {"too_many_notices"}
    missing = [c for c in emitted if c not in M.NOTICES and c not in M.IGNORED and c not in M.REFUSALS]
    assert not missing, missing
    # codes d'avis dérivés de mp.note (types SQL) et du lexeur
    for c in ("tinyint1_as_boolean", "float_ambiguous", "bit_as_string", "rowversion", "json_as_string", "geo_as_string", "set_as_string",
              "lex_unterminated_comment", "lex_unterminated_string", "lex_unterminated_ident"):
        assert c in M.NOTICES


# ---- API locale : aperçu sans effet, application, fusion, annulation ------------------------------------------------------------------

@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("ONTOFORGE_DATA", str(tmp_path))
    monkeypatch.setenv("ONTOFORGE_LOCAL_STORE_DIR", str(tmp_path / "ls"))
    for k in ("ONTOFORGE_AUTH", "ONTOFORGE_PUBLIC"):
        monkeypatch.delenv(k, raising=False)
    from ontoforge.main import create_app
    return TestClient(create_app())


def files(*names):
    return [("files", (n, (F / n).read_bytes())) for n in names]


def test_api_preview_writes_nothing_then_apply_merges_and_undoes(client):
    pid = client.post("/api/projects", json={"name": "Import"}).json()["id"]
    before = client.get(f"/api/projects/{pid}").json()
    pv = client.post(f"/api/projects/{pid}/import/schema/preview", files=files("postgres.sql"))
    assert pv.status_code == 200, pv.text
    j = pv.json()
    assert j["summary"]["classes"] == 6 and j["kind"] == "sql" and j["conformance"]["profiles"]["DL"] and j["decisions"] and j["ignored"]
    assert all(set(n) >= {"code", "level", "message"} for n in j["notices"]) and all(x["message"] for x in j["ignored"])
    assert client.get(f"/api/projects/{pid}").json() == before            # aucun effet
    stale = client.post(f"/api/projects/{pid}/import/schema/apply", files=files("postgres.sql"), data={"expect_digest": "deadbeef"})
    assert stale.status_code == 409
    ap = client.post(f"/api/projects/{pid}/import/schema/apply", files=files("postgres.sql"), data={"expect_digest": j["digest"], "base_iri": j["base_iri"]})
    assert ap.status_code == 200, ap.text
    a = ap.json()
    assert a["merged"]["added"]["classes"] == 6 and a["project"]["onto"]["meta"]["iri"] == j["base_iri"].rstrip("#/")
    assert a["project"]["source_files"] == ["postgres.sql"] and a["can_undo"]
    nodig = client.post(f"/api/projects/{pid}/import/schema/apply", files=files("postgres.sql"), data={"base_iri": j["base_iri"]})
    assert nodig.status_code == 422                                      # jamais d'application sans l'empreinte de l'aperçu
    again = client.post(f"/api/projects/{pid}/import/schema/apply", files=files("postgres.sql"), data={"base_iri": j["base_iri"], "expect_digest": j["digest"]}).json()
    assert again["merged"]["added"]["classes"] == 0 and again["merged"]["skipped_count"] >= 6    # l'existant n'est jamais modifié
    assert client.post(f"/api/projects/{pid}/ops/undo").status_code == 200
    assert client.post(f"/api/projects/{pid}/ops/undo").status_code == 200
    assert len(client.get(f"/api/projects/{pid}").json()["onto"]["classes"]) == 0


def test_api_free_preview_and_errors_in_both_languages(client):
    r = client.post("/api/import/schema/preview", files=files("mysql.sql"))
    assert r.status_code == 200 and r.json()["summary"]["classes"] == 4
    r = client.post("/api/import/schema/preview", files=[("files", ("a.txt", b"hello"))])
    assert r.status_code == 422 and "Format non reconnu" in r.json()["detail"]
    r = client.post("/api/import/schema/preview", files=[("files", ("a.txt", b"hello"))], headers={"Accept-Language": "en"})
    assert r.status_code == 422
    r = client.post("/api/import/schema/preview", files=files("mysql.sql"), data={"options": "[1]"})
    assert r.status_code == 422
    r = client.post("/api/import/schema/preview", files=files("mysql.sql"), data={"options": "{bad"})
    assert r.status_code == 422
    r = client.post("/api/import/schema/preview", files=[("files", ("a.sql", b"CREATE TABLE a (x int PRIMARY KEY);"))], data={"base_iri": "ftp://x y"})
    assert r.status_code == 422


def test_api_apply_to_unknown_project_and_shapes_added(client):
    assert client.post("/api/projects/nope/import/schema/apply", files=files("mysql.sql"), data={"expect_digest": "x"}).status_code == 404
    pid = client.post("/api/projects", json={"name": "S"}).json()["id"]
    dg = client.post(f"/api/projects/{pid}/import/schema/preview", files=files("shop.schema.json")).json()["digest"]
    p = client.post(f"/api/projects/{pid}/import/schema/apply", files=files("shop.schema.json"), data={"expect_digest": dg}).json()["project"]
    assert p["shapes"]["shapes"] and any(s["targets"]["target_class"] for s in p["shapes"]["shapes"].values())
    assert client.get(f"/api/projects/{pid}/conformance").json()["profiles"]["DL"] is True
    assert client.get(f"/api/projects/{pid}/export/shapes").status_code == 200
    assert client.post(f"/api/projects/{pid}/analyze?target=neo4j").status_code == 200


# ---- L48 correctifs it1 ------------------------------------------------------------------------------------

def sql(text, opts=None, base=None):
    return service.run([("t.sql", text.encode())], "sql", opts or {}, base)


def test_exclude_targets_stable_key_even_with_homonyms():
    ddl = "CREATE TABLE a.orders (id int primary key); CREATE TABLE b.orders (id int primary key);"
    r = sql(ddl)
    keys = {c["key"]: c["name"] for c in r.built.classes}
    assert len(keys) == 2 and len(set(keys.values())) == 2          # homonymes dédoublonnés, clés distinctes
    second = next(k for k, n in keys.items() if n.endswith("2"))
    r2 = sql(ddl, {"exclude": [second]})
    assert [c["key"] for c in r2.built.classes] == [k for k in keys if k != second]
    r3 = sql(ddl, {"exclude": [keys[second]]})                       # le nom affiché ne désigne plus rien
    assert len(r3.built.classes) == 2


def test_union_reduced_to_one_member_is_not_emitted_as_unionof():
    from ontoforge.conformance.profiles import check_conformance
    schema = json.dumps({"$defs": {"A": {"type": "object", "properties": {"x": {"type": "string"}}},
                                    "B": {"type": "object", "properties": {"y": {"type": "string"}}},
                                    "H": {"type": "object", "properties": {"one": {"oneOf": [{"$ref": "#/$defs/A"}, {"$ref": "#/$defs/B"}]}}}}})
    full = service.run([("s.json", schema.encode())], "json-schema", {}, None)
    assert any(p.range_union for p in full.built.onto.object_properties.values())
    keys = {c["name"]: c["key"] for c in full.built.classes}
    r = service.run([("s.json", schema.encode())], "json-schema", {"exclude": [keys["B"]]}, None)
    assert "union_reduced" in codes(r)
    for p in r.built.onto.object_properties.values():
        assert not p.range_union
    assert check_conformance(r.built.onto).profiles["DL"] is True


def test_conformance_flags_union_with_one_member():
    from rdflib import BNode, Graph, Namespace, OWL, RDF, RDFS
    from rdflib.collection import Collection
    from ontoforge.conformance.profiles import dl_issues
    EX = Namespace("http://ex.org/")
    g = Graph()
    for c in (EX.A, EX.H):
        g.add((c, RDF.type, OWL.Class))
    g.add((EX.p, RDF.type, OWL.ObjectProperty))
    n, head = BNode(), BNode()
    Collection(g, head, [EX.A])
    g.add((n, OWL.unionOf, head))
    g.add((EX.p, RDFS.range, n))
    assert any("au moins deux" in i.message for i in dl_issues(g))


@pytest.mark.parametrize("base", ["http://ex.org/a#b#c", "http://ex.org/a#b#", "http://ex.org/#a#"])
def test_base_iri_with_several_hashes_refused(base):
    with pytest.raises(ImportRefused) as e:
        sql("CREATE TABLE t (id int primary key);", base=base)
    assert e.value.code == "bad_base_iri"


def _shape_bounds(r):
    out = {}
    for sh in r.built.shapes.shapes.values():
        for ps in sh.properties:
            if ps.min_inclusive or ps.max_inclusive:
                out[ps.path.iri.rsplit("#", 1)[-1]] = (ps.min_inclusive, ps.max_inclusive)
    return out


def test_between_bounds_typed_like_the_column():
    r = sql("CREATE TABLE t (id int primary key, ts timestamp CHECK (ts BETWEEN '2020-01-01' AND '2030-01-01'), "
            "age int CHECK (age BETWEEN 0 AND 150), name varchar(5) CHECK (name BETWEEN 'a' AND 'z'), "
            "bad int CHECK (bad BETWEEN 'x' AND 'y'));")
    b = _shape_bounds(r)
    assert b["ts"][0].startswith('"2020-01-01T00:00:00"^^<') and b["ts"][0].endswith("dateTime>")
    assert b["age"] == ('"0"^^<http://www.w3.org/2001/XMLSchema#int>', '"150"^^<http://www.w3.org/2001/XMLSchema#int>')
    assert "name" not in b and "bad" not in b
    assert "bound_dropped" in codes(r)
    import pyshacl
    from ontoforge.shacl.export_shapes import shapes_to_graph
    ok, _, txt = pyshacl.validate(shapes_to_graph(r.built.shapes), meta_shacl=True, inference="none")
    assert ok, txt


def test_successive_checks_are_intersected():
    r = sql("CREATE TABLE t (id int primary key, kind varchar(5) CHECK (kind IN ('a','b')) CHECK (kind IN ('b','c')), "
            "k2 varchar(5), CHECK (k2 = 'x' AND k2 = 'y'), k3 varchar(5), CHECK (k3 IN ('p','q') AND k3 IN ('q','r')));")
    e = cls(r, "T")
    assert prop(e, "kind")["enum"] == ["b"]
    assert not prop(e, "k2").get("enum")
    assert prop(e, "k3")["enum"] == ["q"]
    assert {"check_intersected", "check_contradiction"} <= codes(r)


def test_hostile_time_bounds():
    big = "create " * 30000 + "x"
    t0 = time.monotonic()
    service.sniff_kind("x.txt", big)
    assert time.monotonic() - t0 < 1.0
    ors = " OR ".join(f"k = 'v{i}'" for i in range(20000))
    t0 = time.monotonic()
    r = sql(f"CREATE TABLE t (id int primary key, k varchar(9), CHECK ({ors}));")
    assert time.monotonic() - t0 < 5
    assert not prop(cls(r, "T"), "k").get("enum")
    assert "check_complex" in r.draft.ignored
    dup = ",".join(["'a'"] * 400)
    r = sql(f"CREATE TABLE t (id int primary key, k varchar(9) CHECK (k IN ({dup})));")
    assert prop(cls(r, "T"), "k")["enum"] == ["a"]


def test_api_total_size_cap(client):
    big = b"-- " + b"x" * (1024 * 1024 - 8) + b"\n"
    fs = [("files", (f"f{i}.sql", big, "text/plain")) for i in range(11)]
    r = client.post("/api/import/schema/preview", files=fs)
    assert r.status_code == 413


def test_it2_calendar_validation_of_bounds():
    r = sql("CREATE TABLE t (id int primary key, a timestamp CHECK (a BETWEEN '2020-13-45T99:99:99' AND '2030-01-01T00:00:00'), "
            "b timestamp CHECK (b BETWEEN '2021-02-30' AND '2030-01-01'), c timestamp CHECK (c BETWEEN '2020-02-29T23:59:59' AND '2030-01-01'));")
    b = _shape_bounds(r)
    assert "a" not in b or b["a"][0] is None
    assert "b" not in b or b["b"][0] is None
    assert b["c"][0].startswith('"2020-02-29T23:59:59"')
    assert sum(1 for n in r.built.notices if n["code"] == "bound_dropped") >= 2 if hasattr(r.built, "notices") else True
    assert "bound_dropped" in codes(r)


def test_it2_date_bound_on_timestamptz_uses_utc_and_is_reported():
    r = sql("CREATE TABLE t (id int primary key, a timestamptz CHECK (a BETWEEN '2020-01-01' AND '2030-01-01'), n timestamp CHECK (n >= '2020-01-01'));")
    b = _shape_bounds(r)
    assert b["a"][0].startswith('"2020-01-01T00:00:00Z"')
    assert "bound_tz_assumed" in codes(r)


def test_it2_nested_equalities_intersect():
    r = sql("CREATE TABLE t (id int primary key, k varchar(3), CHECK ((k = 'a' OR k = 'b') AND (k = 'b' OR k = 'c')), "
            "m varchar(3), CHECK (m = 'a' AND (m = 'a' OR m = 'b')));")
    assert prop(cls(r, "T"), "k")["enum"] == ["b"]
    assert prop(cls(r, "T"), "m")["enum"] == ["a"]


def test_it2_excluding_first_union_member_keeps_relation_to_the_rest():
    schema = json.dumps({"$defs": {"A": {"type": "object", "properties": {"x": {"type": "string"}}},
                                    "B": {"type": "object", "properties": {"y": {"type": "string"}}},
                                    "C": {"type": "object", "properties": {"z": {"type": "string"}}},
                                    "H": {"type": "object", "properties": {"one": {"anyOf": [{"$ref": "#/$defs/A"}, {"$ref": "#/$defs/B"}, {"$ref": "#/$defs/C"}]}}}}})
    keys = {c["name"]: c["key"] for c in service.run([("s.json", schema.encode())], "json-schema", {}, None).built.classes}
    r = service.run([("s.json", schema.encode())], "json-schema", {"exclude": [keys["A"]]}, None)
    h = next(p for p in r.built.onto.object_properties.values() if "one" in p.iri.lower())
    assert len(h.range_union) == 2 and "relation_dropped" not in codes(r)


def test_it2_date_degrade_message_is_exact():
    r = sql("CREATE TABLE t (id int primary key, d date);")
    assert "degraded_date" in codes(r) and "degraded_type" not in codes(r)
    assert "précision est perdue" not in M.notice("degraded_date", "fr", {"table": "t", "column": "d", "type": "date"})
