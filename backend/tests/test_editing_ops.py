"""L9 — opérations d'édition unitaires, atomicité, annuler / rétablir, icônes, graphe."""
import pytest
from fastapi.testclient import TestClient

from ontoforge.io.rdf_import import parse_ontology
from ontoforge.main import app

NS = "https://example.org/t#"
XSD = "http://www.w3.org/2001/XMLSchema#"


def c(n):
    return NS + n


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("ONTOFORGE_DATA", str(tmp_path))
    return TestClient(app)


@pytest.fixture
def pid(client):
    r = client.post("/api/projects", json={"name": "Édition"})
    assert r.status_code == 201
    pid = r.json()["id"]
    r = client.post(f"/api/projects/{pid}/ops", json={"ops": [
        {"op": "add_class", "iri": c("Vehicle"), "label": "Véhicule"},
        {"op": "add_class", "iri": c("Car"), "parent": c("Vehicle")},
        {"op": "add_class", "iri": c("Garage")},
        {"op": "add_object_property", "iri": c("servicedAt"), "domain": c("Vehicle"), "range": c("Garage")},
        {"op": "add_datatype_property", "iri": c("vin"), "domain": c("Vehicle"), "range": XSD + "string"},
    ]})
    assert r.json()["ok"], r.text
    return pid


def ops(client, pid, *o):
    return client.post(f"/api/projects/{pid}/ops", json={"ops": list(o)}).json()


def proj(client, pid):
    return client.get(f"/api/projects/{pid}").json()


def err(r, frag=None):
    assert r["ok"] is False and r["applied"] == 0 and r["errors"], r
    if frag:
        assert frag in r["errors"][0]["message"], r["errors"]


def test_add_and_atomicity(client, pid):
    before = proj(client, pid)
    r = ops(client, pid, {"op": "add_class", "iri": c("Truck"), "label": "Camion"},
            {"op": "add_subclass", "iri": c("Truck"), "parent": c("Vehicle")},
            {"op": "add_subclass", "iri": c("Truck"), "parent": c("Nope")})
    err(r, "inconnue")
    assert r["errors"][0]["index"] == 2
    assert proj(client, pid)["onto"] == before["onto"]  # rien n'a été appliqué
    r = ops(client, pid, {"op": "add_class", "iri": c("Truck"), "label": "Camion"},
            {"op": "add_subclass", "iri": c("Truck"), "parent": c("Vehicle")})
    assert r["ok"] and r["applied"] == 2
    assert proj(client, pid)["onto"]["classes"][c("Truck")]["sub_class_of"] == [c("Vehicle")]
    # IRI construite à partir de l'IRI de l'ontologie
    r = ops(client, pid, {"op": "add_class", "name": "Bus"})
    assert r["ok"] and "https://w3id.org/ontoforge/new#Bus" in r["project"]["onto"]["classes"]
    err(ops(client, pid, {"op": "add_class", "name": "bad name"}), "Nom local")


def test_invalid_inputs(client, pid):
    err(ops(client, pid, {"op": "add_class", "iri": "pas une iri"}), "IRI invalide")
    err(ops(client, pid, {"op": "add_class", "iri": c("Car")}), "existe déjà")
    err(ops(client, pid, {"op": "add_class", "iri": c("servicedAt")}), "existe déjà")  # punning refusé
    err(ops(client, pid, {"op": "bogus"}), "inconnue")
    err(ops(client, pid, {"foo": 1}), "« op »")
    err(ops(client, pid, {"op": "add_datatype_property", "iri": c("p"), "range": XSD + "nope"}), "inconnu")
    err(ops(client, pid, {"op": "add_datatype_property", "iri": c("p"), "range": "https://x.org/foo"}), "inconnu")
    err(ops(client, pid, {"op": "move_node", "iri": c("Car"), "x": "a", "y": 1}), "nombre")
    err(ops(client, pid, {"op": "set_icon", "iri": c("Car"), "icon": "user"}), "invalide")
    assert client.post(f"/api/projects/{pid}/ops", json={"ops": []}).json()["ok"] is False


def test_datatype_outside_owl2_map_warns(client, pid):
    r = ops(client, pid, {"op": "add_datatype_property", "iri": c("built"), "domain": c("Vehicle"), "range": XSD + "date"})
    assert r["ok"] and any("carte de datatypes" in w for w in r["warnings"])


def test_subclass_cycles(client, pid):
    err(ops(client, pid, {"op": "add_subclass", "iri": c("Vehicle"), "parent": c("Car")}), "Cycle")
    err(ops(client, pid, {"op": "add_subclass", "iri": c("Car"), "parent": c("Car")}), "Cycle")
    r = ops(client, pid, {"op": "remove_subclass", "iri": c("Car"), "parent": c("Vehicle")})
    assert r["ok"]
    err(ops(client, pid, {"op": "remove_subclass", "iri": c("Car"), "parent": c("Vehicle")}), "pas une sous-classe")


def test_labels_comments_icon_move(client, pid):
    r = ops(client, pid, {"op": "set_label", "iri": c("Car"), "text": "Voiture", "lang": "fr"},
            {"op": "set_comment", "iri": c("Car"), "text": "Auto", "lang": "fr"},
            {"op": "set_icon", "iri": c("Car"), "icon": "fa-car"},
            {"op": "move_node", "iri": c("Car"), "x": 10.5, "y": -3},
            {"op": "set_collapsed", "iri": c("Vehicle")})
    assert r["ok"] and not r["warnings"]
    p = r["project"]
    assert p["onto"]["classes"][c("Car")]["labels"] == {"fr": "Voiture"}
    assert p["view"]["icons"][c("Car")] == "fa-car"
    assert p["view"]["positions"][c("Car")] == {"x": 10.5, "y": -3.0}
    assert p["view"]["collapsed"] == [c("Vehicle")]
    r = ops(client, pid, {"op": "set_label", "iri": c("Car"), "text": ""})
    assert r["project"]["onto"]["classes"][c("Car")]["labels"] == {}
    r = ops(client, pid, {"op": "set_icon", "iri": c("Car"), "icon": "fa-zzz-inconnu"})
    assert r["ok"] and r["warnings"]


def test_restrictions_and_simple_property_rule(client, pid):
    r = ops(client, pid, {"op": "set_restriction", "iri": c("Car"), "property": c("servicedAt"), "kind": "min", "n": 1, "filler": c("Garage")})
    assert r["ok"]
    rs = r["project"]["onto"]["classes"][c("Car")]["restrictions"]
    assert rs[0]["kind"] == "min" and rs[0]["n"] == 1
    # remplacement du même (propriété, kind)
    r = ops(client, pid, {"op": "set_restriction", "iri": c("Car"), "property": c("servicedAt"), "kind": "min", "n": 2})
    assert len(r["project"]["onto"]["classes"][c("Car")]["restrictions"]) == 1
    # rendre la propriété transitive la rend non simple : refusé car elle est dans une cardinalité
    err(ops(client, pid, {"op": "set_characteristic", "iri": c("servicedAt"), "characteristic": "transitive"}), "non simple")
    # cardinalité sur une propriété déjà transitive : refusé
    ops(client, pid, {"op": "add_object_property", "iri": c("partOf"), "domain": c("Car"), "range": c("Car"), "characteristics": ["transitive"]})
    err(ops(client, pid, {"op": "set_restriction", "iri": c("Car"), "property": c("partOf"), "kind": "max", "n": 1}), "non simple")
    err(ops(client, pid, {"op": "set_restriction", "iri": c("Car"), "property": c("partOf"), "kind": "self"}), "non simple")
    # some est permis sur une non simple
    assert ops(client, pid, {"op": "set_restriction", "iri": c("Car"), "property": c("partOf"), "kind": "some", "filler": c("Car")})["ok"]
    # propriété fonctionnelle + transitive refusée aussi
    err(ops(client, pid, {"op": "set_characteristic", "iri": c("partOf"), "characteristic": "functional"}), "simple")
    # validations de forme
    err(ops(client, pid, {"op": "set_restriction", "iri": c("Car"), "property": c("vin"), "kind": "min"}), "« n »")
    err(ops(client, pid, {"op": "set_restriction", "iri": c("Car"), "property": c("vin"), "kind": "some"}), "datatype")
    err(ops(client, pid, {"op": "set_restriction", "iri": c("Car"), "property": c("vin"), "kind": "self"}), "propriétés d'objet")
    err(ops(client, pid, {"op": "set_restriction", "iri": c("Car"), "property": c("Nope"), "kind": "some"}), "inconnue")
    assert ops(client, pid, {"op": "remove_restriction", "iri": c("Car"), "property": c("servicedAt")})["ok"]
    err(ops(client, pid, {"op": "remove_restriction", "iri": c("Car"), "property": c("servicedAt")}), "Aucune restriction")


def test_non_simple_via_subproperty(client, pid):
    ops(client, pid, {"op": "add_object_property", "iri": c("sub"), "domain": c("Car"), "range": c("Garage"), "characteristics": ["transitive"]},
        {"op": "set_restriction", "iri": c("Car"), "property": c("servicedAt"), "kind": "max", "n": 3})
    # sub ⊑ servicedAt avec sub transitive ⇒ servicedAt non simple ; on ne peut pas poser la cardinalité
    p = proj(client, pid)
    p["onto"]["object_properties"][c("sub")]["sub_property_of"] = [c("servicedAt")]
    # (via PUT onto, hors éditeur) puis le lot suivant n'aggrave rien, mais toute nouvelle cardinalité est refusée
    assert client.put(f"/api/projects/{pid}/onto", json=p["onto"]).status_code == 200
    err(ops(client, pid, {"op": "set_restriction", "iri": c("Garage"), "property": c("servicedAt"), "kind": "min", "n": 1}), "non simple")


def test_characteristics_inverse_disjoint_key(client, pid):
    assert ops(client, pid, {"op": "set_characteristic", "iri": c("servicedAt"), "characteristic": "asymmetric"})["ok"]
    err(ops(client, pid, {"op": "set_characteristic", "iri": c("servicedAt"), "characteristic": "symmetric"}), "symétrique")
    err(ops(client, pid, {"op": "set_characteristic", "iri": c("servicedAt"), "characteristic": "bogus"}), "characteristic")
    err(ops(client, pid, {"op": "set_characteristic", "iri": c("vin"), "characteristic": "transitive"}), "fonctionnelle")
    r = ops(client, pid, {"op": "set_characteristic", "iri": c("vin"), "characteristic": "functional"})
    assert r["project"]["onto"]["datatype_properties"][c("vin")]["functional"] is True
    r = ops(client, pid, {"op": "add_object_property", "iri": c("services"), "domain": c("Garage"), "range": c("Vehicle")},
            {"op": "set_inverse", "iri": c("services"), "inverse": c("servicedAt")})
    assert r["project"]["onto"]["object_properties"][c("services")]["inverse_of"] == c("servicedAt")
    err(ops(client, pid, {"op": "set_inverse", "iri": c("services"), "inverse": c("services")}), "symétrique")
    # disjonction
    assert ops(client, pid, {"op": "add_disjoint", "iri": c("Car"), "other": c("Garage")})["ok"]
    r = ops(client, pid, {"op": "add_disjoint", "iri": c("Garage"), "other": c("Car")})
    assert r["ok"] and r["warnings"]
    err(ops(client, pid, {"op": "add_disjoint", "iri": c("Car"), "other": c("Vehicle")}), "sous-classe")
    err(ops(client, pid, {"op": "add_disjoint", "iri": c("Car"), "other": c("servicedAt")}), "deux classes")
    assert ops(client, pid, {"op": "remove_disjoint", "iri": c("Garage"), "other": c("Car")})["ok"]
    # clé
    r = ops(client, pid, {"op": "set_key", "iri": c("Vehicle"), "properties": [c("vin")]})
    assert r["project"]["onto"]["classes"][c("Vehicle")]["has_keys"] == [[c("vin")]]
    err(ops(client, pid, {"op": "set_key", "iri": c("Vehicle"), "properties": [c("zzz")]}), "inconnue")
    r = ops(client, pid, {"op": "set_key", "iri": c("Vehicle"), "properties": []})
    assert r["project"]["onto"]["classes"][c("Vehicle")]["has_keys"] == []


def test_domain_range(client, pid):
    r = ops(client, pid, {"op": "set_domain_range", "iri": c("servicedAt"), "domain": [c("Car")], "range": None})
    o = r["project"]["onto"]["object_properties"][c("servicedAt")]
    assert o["domain"] == [c("Car")] and o["range"] == []
    err(ops(client, pid, {"op": "set_domain_range", "iri": c("vin"), "range": [c("Car")]}), "Datatype")
    err(ops(client, pid, {"op": "set_domain_range", "iri": c("servicedAt"), "range": [XSD + "string"]}), "Classe inconnue")
    err(ops(client, pid, {"op": "set_domain_range", "iri": c("servicedAt")}), "domain")


def test_rename_and_delete(client, pid):
    ops(client, pid, {"op": "set_restriction", "iri": c("Car"), "property": c("servicedAt"), "kind": "some", "filler": c("Garage")},
        {"op": "set_icon", "iri": c("Garage"), "icon": "fa-warehouse"}, {"op": "set_key", "iri": c("Vehicle"), "properties": [c("vin")]})
    r = ops(client, pid, {"op": "rename_entity", "iri": c("Garage"), "new_iri": c("Workshop")})
    assert r["ok"]
    o = r["project"]["onto"]
    assert c("Garage") not in o["classes"] and c("Workshop") in o["classes"]
    assert o["object_properties"][c("servicedAt")]["range"] == [c("Workshop")]
    assert o["classes"][c("Car")]["restrictions"][0]["filler"] == c("Workshop")
    assert r["project"]["view"]["icons"] == {c("Workshop"): "fa-warehouse"}
    err(ops(client, pid, {"op": "rename_entity", "iri": c("Workshop"), "new_iri": c("Car")}), "existe déjà")
    # suppression : références nettoyées, modèle toujours valide
    r = ops(client, pid, {"op": "delete_entity", "iri": c("Workshop")})
    assert r["ok"] and r["warnings"]
    o = r["project"]["onto"]
    assert c("Workshop") not in o["classes"]
    assert o["object_properties"][c("servicedAt")]["range"] == []
    assert o["classes"][c("Car")]["restrictions"] == []
    assert c("Workshop") not in r["project"]["view"]["icons"]
    r = ops(client, pid, {"op": "delete_entity", "iri": c("Vehicle")})
    assert r["ok"] and r["project"]["onto"]["classes"][c("Car")]["sub_class_of"] == []
    err(ops(client, pid, {"op": "delete_entity", "iri": c("Vehicle")}), "inconnue")
    assert client.get(f"/api/projects/{pid}/export/ontology").status_code == 200  # export toujours possible


def test_undo_redo(client, pid):
    base = proj(client, pid)["onto"]
    ops(client, pid, {"op": "add_class", "iri": c("Bike")})
    ops(client, pid, {"op": "rename_entity", "iri": c("Bike"), "new_iri": c("Cycle")}, {"op": "set_icon", "iri": c("Cycle"), "icon": "fa-bicycle"})
    h = client.get(f"/api/projects/{pid}/ops/history").json()
    assert h["can_undo"] and not h["can_redo"] and h["undo"][0]["label"].startswith("rename_entity")
    r = client.post(f"/api/projects/{pid}/ops/undo").json()
    assert r["can_redo"] and c("Bike") in r["project"]["onto"]["classes"] and r["project"]["view"]["icons"] == {}
    r = client.post(f"/api/projects/{pid}/ops/redo").json()
    assert c("Cycle") in r["project"]["onto"]["classes"] and r["project"]["view"]["icons"][c("Cycle")] == "fa-bicycle"
    client.post(f"/api/projects/{pid}/ops/undo")
    client.post(f"/api/projects/{pid}/ops/undo")
    assert proj(client, pid)["onto"] == {**base, "classes": base["classes"]} or c("Bike") not in proj(client, pid)["onto"]["classes"]
    # une nouvelle opération vide la pile « rétablir »
    ops(client, pid, {"op": "add_class", "iri": c("Boat")})
    assert not client.get(f"/api/projects/{pid}/ops/history").json()["can_redo"]
    assert client.post(f"/api/projects/{pid}/ops/redo").status_code == 409
    # échec : rien n'est journalisé
    n = len(client.get(f"/api/projects/{pid}/ops/history").json()["undo"])
    ops(client, pid, {"op": "add_class", "iri": "x"})
    assert len(client.get(f"/api/projects/{pid}/ops/history").json()["undo"]) == n


def test_undo_empty_and_limit(client, pid, monkeypatch):
    from ontoforge.editing import history
    monkeypatch.setattr(history, "LIMIT", 3)
    for i in range(6):
        ops(client, pid, {"op": "add_class", "iri": c(f"K{i}")})
    h = client.get(f"/api/projects/{pid}/ops/history").json()
    assert len(h["undo"]) == 3
    for _ in range(3):
        assert client.post(f"/api/projects/{pid}/ops/undo").status_code == 200
    assert client.post(f"/api/projects/{pid}/ops/undo").status_code == 409


def test_icons_catalog(client):
    r = client.get("/api/icons").json()
    assert 60 <= r["total"] <= 120
    ids = {i["id"] for i in r["icons"]}
    assert "fa-car" in ids and all(i.startswith("fa-") for i in ids)
    assert all(i["label"]["fr"] and i["label"]["en"] and i["keywords"] for i in r["icons"])
    assert any(i["id"] == "fa-car" for i in client.get("/api/icons", params={"q": "véhicule"}).json()["icons"])
    assert any(i["id"] == "fa-car" for i in client.get("/api/icons", params={"q": "VEHICLE"}).json()["icons"])
    assert client.get("/api/icons", params={"q": "zzzzqq"}).json()["total"] == 0


def test_graph(client, pid):
    ops(client, pid, {"op": "set_icon", "iri": c("Car"), "icon": "fa-car"}, {"op": "move_node", "iri": c("Car"), "x": 1, "y": 2},
        {"op": "add_object_property", "iri": c("services"), "domain": c("Garage"), "range": c("Vehicle"), "inverse_of": c("servicedAt")},
        {"op": "add_object_property", "iri": c("floating")}, {"op": "add_disjoint", "iri": c("Car"), "other": c("Garage")})
    g1 = client.get(f"/api/projects/{pid}/graph").json()
    g2 = client.get(f"/api/projects/{pid}/graph").json()
    assert g1 == g2
    nodes = {n["id"]: n for n in g1["nodes"]}
    assert set(nodes) == {c("Vehicle"), c("Car"), c("Garage")}
    assert nodes[c("Car")]["icon"] == "fa-car" and nodes[c("Car")]["position"] == {"x": 1.0, "y": 2.0}
    assert nodes[c("Vehicle")]["label"] == "Véhicule" and nodes[c("Garage")]["position"] is None
    kinds = {}
    for e in g1["edges"]:
        kinds.setdefault(e["kind"], []).append(e)
    assert kinds["subClassOf"][0]["source"] == c("Car") and kinds["subClassOf"][0]["target"] == c("Vehicle")
    assert {e["iri"] for e in kinds["objectProperty"]} == {c("servicedAt"), c("services")}
    assert len(kinds["inverseOf"]) == 1 and len(kinds["disjointWith"]) == 1
    assert c("floating") in g1["skipped"]
    assert [e["id"] for e in g1["edges"]] == sorted(e["id"] for e in g1["edges"])
    g3 = client.get(f"/api/projects/{pid}/graph", params={"include": "datatypes"}).json()
    assert any(n["kind"] == "datatype" for n in g3["nodes"]) and any(e["kind"] == "datatypeProperty" for e in g3["edges"])
    assert client.get(f"/api/projects/{pid}/graph", params={"perimeter": "nope"}).status_code == 404


# ---- revue W3C it1 : un test par bloquant --------------------------------------------------------------

def put_onto(client, pid, mutate):
    p = proj(client, pid)
    mutate(p["onto"])
    assert client.put(f"/api/projects/{pid}/onto", json=p["onto"]).status_code == 200


def test_w3c1_nested_cardinality_blocks_non_simple(client, pid):
    def m(o):
        o["classes"][c("Garage")]["equivalent_to"] = [{"op": "and", "args": [
            {"op": "named", "iri": c("Vehicle")},
            {"op": "min", "property": c("servicedAt"), "n": 2, "filler": {"op": "named", "iri": c("Garage")}}]}]
    put_onto(client, pid, m)
    err(ops(client, pid, {"op": "set_characteristic", "iri": c("servicedAt"), "characteristic": "transitive"}), "non simple")
    # idem pour une expression de superclasse et un filler_expr de restriction aplatie
    def m2(o):
        o["classes"][c("Garage")]["equivalent_to"] = []
        o["classes"][c("Garage")]["super_expressions"] = [{"op": "not", "args": [
            {"op": "self", "property": c("servicedAt")}]}]
    put_onto(client, pid, m2)
    err(ops(client, pid, {"op": "set_characteristic", "iri": c("servicedAt"), "characteristic": "transitive"}), "non simple")


def test_w3c2_disjoint_properties_need_simple_on_both_sides(client, pid):
    ops(client, pid, {"op": "add_object_property", "iri": c("q"), "domain": c("Car"), "range": c("Garage"), "characteristics": ["transitive"]})
    err(ops(client, pid, {"op": "add_disjoint", "iri": c("servicedAt"), "other": c("q")}), "non simple")
    err(ops(client, pid, {"op": "add_disjoint", "iri": c("q"), "other": c("servicedAt")}), "non simple")
    # rendre transitive après coup une propriété déjà disjointe de l'autre côté : refusé aussi
    ops(client, pid, {"op": "add_object_property", "iri": c("r"), "domain": c("Car"), "range": c("Garage")},
        {"op": "add_disjoint", "iri": c("servicedAt"), "other": c("r")})
    err(ops(client, pid, {"op": "set_characteristic", "iri": c("r"), "characteristic": "transitive"}), "non simple")


@pytest.mark.parametrize("bad", [XSD + "string", "http://www.w3.org/1999/02/22-rdf-syntax-ns#type",
                                 "http://www.w3.org/2002/07/owl#Thing", "http://www.w3.org/2000/01/rdf-schema#label"])
def test_w3c3_reserved_vocabulary(client, pid, bad):
    err(ops(client, pid, {"op": "add_class", "iri": bad}), "réservé")
    err(ops(client, pid, {"op": "add_object_property", "iri": bad}), "réservé")
    err(ops(client, pid, {"op": "rename_entity", "iri": c("Garage"), "new_iri": bad}), "réservé")


def test_w3c4_delete_removes_whole_axioms(client, pid):
    def m(o):
        o["classes"][c("Car")]["equivalent_to"] = [{"op": "and", "args": [{"op": "named", "iri": c("Garage")}, {"op": "named", "iri": c("Vehicle")}]}]
        o["classes"][c("Vehicle")]["super_expressions"] = [{"op": "not", "args": [{"op": "named", "iri": c("Garage")}]},
                                                           {"op": "or", "args": [{"op": "named", "iri": c("Car")}, {"op": "named", "iri": c("Vehicle")}]}]
        o["classes"][c("Garage")]["restrictions"] = [{"property": c("servicedAt"), "kind": "some", "filler": None,
                                                      "filler_expr": {"op": "or", "args": [{"op": "named", "iri": c("Garage")}, {"op": "named", "iri": c("Car")}]}}]
        o["object_properties"][c("servicedAt")]["domain_union"] = [c("Garage"), c("Vehicle")]
        o["object_properties"][c("servicedAt")]["range_union"] = [c("Garage"), c("Car")]
    put_onto(client, pid, m)
    r = ops(client, pid, {"op": "delete_entity", "iri": c("Garage")})
    assert r["ok"], r
    o = r["project"]["onto"]
    assert o["classes"][c("Car")]["equivalent_to"] == []  # pas de and(Vehicle)
    sup = o["classes"][c("Vehicle")]["super_expressions"]
    assert len(sup) == 1 and sup[0]["op"] == "or" and len(sup[0]["args"]) == 2  # not(...) retiré entier, l'autre intact
    p = o["object_properties"][c("servicedAt")]
    assert p["domain_union"] == [] and p["range_union"] == []
    assert any("axiome" in w and "jamais tronqués" in w for w in r["warnings"])
    # aucune expression n-aire de moins de 2 opérandes ni not() vide
    def walk(e):
        assert e["op"] not in ("and", "or") or len(e["args"]) >= 2
        assert e["op"] != "not" or len(e["args"]) == 1
        for a in e["args"]:
            walk(a)
    for k in o["classes"].values():
        for e in k["equivalent_to"] + k["super_expressions"]:
            walk(e)


def test_w3c4_delete_keeps_prefix_lookalikes(client, pid):
    ops(client, pid, {"op": "add_class", "iri": c("GarageBis")})
    def m(o):
        o["classes"][c("Car")]["equivalent_to"] = [{"op": "and", "args": [{"op": "named", "iri": c("GarageBis")}, {"op": "named", "iri": c("Vehicle")}]}]
    put_onto(client, pid, m)
    r = ops(client, pid, {"op": "delete_entity", "iri": c("Garage")})
    assert len(r["project"]["onto"]["classes"][c("Car")]["equivalent_to"]) == 1


def test_w3c5_inherited_property_reports_p01(client, pid):
    ops(client, pid, {"op": "add_object_property", "iri": c("d"), "domain": c("Vehicle"), "range": c("Garage")},
        {"op": "add_datatype_property", "iri": c("e"), "domain": c("Vehicle"), "range": XSD + "string"})
    per = client.post(f"/api/projects/{pid}/perimeters", json={"name": "Hérité", "classes": [c("Car"), c("Garage")]}).json()
    prev = client.get(f"/api/projects/{pid}/perimeters/{per['id']}/preview").json()
    by = {x["id"].split(":", 1)[1]: x for x in prev["excluded"] if x["rule"] == "P01"}
    assert c("d") in by and c("e") in by
    assert "restreint" in by[c("d")]["detail"] and "Car" in by[c("d")]["detail"]  # it2 : projetée sur Car (plus exclue)
    assert "Car" in by[c("e")]["detail"]
    a = client.post(f"/api/projects/{pid}/analyze", params={"target": "neo4j", "perimeter": per["id"]})


def test_d_l9_02_info_severity_and_icon(client, pid, monkeypatch):
    from ontoforge.core.pg_model import Finding, PGModel
    pg = PGModel(target="neo4j", findings=[
        Finding(id="a", rule="X", severity="auto", title="t", detail="d", subject="s"),
        Finding(id="P00:x", rule="P00", severity="info", title="t", detail="d", subject="s")])
    s = pg.summary()
    assert s == {"auto": 1, "review": 0, "lost": 0, "decided": 0, "pending": 0}
    ops(client, pid, {"op": "set_icon", "iri": c("Car"), "icon": "fa-car"})
    per = client.post(f"/api/projects/{pid}/perimeters", json={"name": "Auto", "classes": [c("Car")]}).json()
    r = client.post(f"/api/projects/{pid}/analyze", params={"target": "neo4j", "perimeter": per["id"]})
    assert r.status_code == 200, r.text
    nts = r.json()["node_types"]
    assert any(nt["icon"] == "fa-car" for nt in nts.values())
    assert all(f["severity"] == "info" for f in r.json()["findings"] if f["rule"].startswith("P"))
    files = client.get(f"/api/projects/{pid}/generate/neo4j", params={"perimeter": per["id"]}).json()["files"]
    assert "icône : fa-car" in files["model.mmd"]


# ---- revue W3C it2 : bloquants « vendredi » -------------------------------------------------------------

def test_w3c_it2_inherited_property_is_projected_on_perimeter_subclass(client, pid):
    ops(client, pid, {"op": "add_object_property", "iri": c("s"), "domain": c("Vehicle"), "range": c("Garage")},
        {"op": "add_datatype_property", "iri": c("e"), "domain": c("Vehicle"), "range": XSD + "string"})
    per = client.post(f"/api/projects/{pid}/perimeters", json={"name": "Proj", "classes": [c("Car"), c("Garage")]}).json()
    g = client.get(f"/api/projects/{pid}/graph", params={"perimeter": per["id"]}).json()
    edges = {(e["source"], e["target"]) for e in g["edges"] if e["kind"] == "objectProperty" and e["iri"] == c("s")}
    assert edges == {(c("Car"), c("Garage"))}
    prev = client.get(f"/api/projects/{pid}/perimeters/{per['id']}/preview").json()
    p01 = {x["id"].split(":", 1)[1]: x for x in prev["excluded"] if x["rule"] == "P01"}
    assert "restreint" in p01[c("s")]["title"] and "Car" in p01[c("s")]["detail"] and c("e") in p01
    r = client.post(f"/api/projects/{pid}/analyze", params={"target": "neo4j", "perimeter": per["id"]}).json()
    assert any(et["from"] == "Car" and et["to"] == "Garage" for et in r["edge_types"]), r["edge_types"]
    # propriété explicitement non listée : toujours exclue (pas de projection)
    per2 = client.post(f"/api/projects/{pid}/perimeters", json={"name": "Autre", "classes": [c("Car"), c("Garage")], "properties": [c("servicedAt")]}).json()
    g2 = client.get(f"/api/projects/{pid}/graph", params={"perimeter": per2["id"]}).json()
    assert not any(e["iri"] == c("s") for e in g2["edges"])


def test_w3c_it2_hasvalue_literal_must_be_well_typed(client, pid):
    base = {"op": "set_restriction", "iri": c("Car"), "property": c("vin"), "kind": "value"}
    err(ops(client, pid, {**base, "value": "abc", "datatype": XSD + "integer"}), "forme lexicale")
    err(ops(client, pid, {**base, "value": "300", "datatype": XSD + "byte"}), "intervalle")
    err(ops(client, pid, {**base, "value": "maybe", "datatype": XSD + "boolean"}), "forme lexicale")
    err(ops(client, pid, {**base, "value": "hier", "datatype": XSD + "dateTime"}), "forme lexicale")
    err(ops(client, pid, {**base, "value": "x", "datatype": XSD + "string", "value_lang": "fr"}), "langue")
    assert ops(client, pid, {**base, "value": "42", "datatype": XSD + "integer"})["ok"]
    assert ops(client, pid, {**base, "value": "VIN123"})["ok"]
    assert ops(client, pid, {**base, "value": "2026-11-04T10:00:00Z", "datatype": XSD + "dateTime"})["ok"]
    assert ops(client, pid, {**base, "value": "bonjour", "datatype": "http://www.w3.org/1999/02/22-rdf-syntax-ns#langString", "value_lang": "fr"})["ok"]


def test_w3c_it2_disjoint_equivalent_classes_refused(client, pid):
    ops(client, pid, {"op": "add_class", "iri": c("Auto")}, {"op": "add_class", "iri": c("Wagon")}, {"op": "add_class", "iri": c("Other")})
    def m(o):
        o["classes"][c("Auto")]["equivalent_to"] = [{"op": "named", "iri": c("Car")}]
        o["classes"][c("Wagon")]["equivalent_to"] = [{"op": "named", "iri": c("Auto")}]
    put_onto(client, pid, m)
    err(ops(client, pid, {"op": "add_disjoint", "iri": c("Auto"), "other": c("Car")}), "équivalentes")   # directe
    err(ops(client, pid, {"op": "add_disjoint", "iri": c("Wagon"), "other": c("Car")}), "équivalentes")  # par chaîne
    err(ops(client, pid, {"op": "add_disjoint", "iri": c("Wagon"), "other": c("Vehicle")}), "équivalentes")  # via sous-classe d'une équivalente
    assert ops(client, pid, {"op": "add_disjoint", "iri": c("Wagon"), "other": c("Other")})["ok"]


# ---- L26 : graphe enrichi pour la notation VOWL (champs additifs, include=external,anonymous,thing) -----------

def test_graph_l26_additive_flags_and_includes(client, pid):
    def m(o):
        o["meta"]["iri"] = "https://example.org/t"
        o["classes"][c("Car")]["equivalent_to"] = [{"op": "named", "iri": c("Garage")}]
        o["classes"][c("Garage")]["equivalent_to"] = [{"op": "or", "args": [{"op": "named", "iri": c("Car")}, {"op": "named", "iri": "http://xmlns.com/foaf/0.1/Person"}]}]
        o["classes"][c("Vehicle")]["sub_class_of"] = ["http://xmlns.com/foaf/0.1/Agent"]
        o["classes"][c("Vehicle")]["super_expressions"] = [{"op": "not", "args": [{"op": "named", "iri": c("Garage")}]}]
    put_onto(client, pid, m)
    assert ops(client, pid, {"op": "add_object_property", "iri": c("owns"), "domain": c("Garage"), "characteristics": ["functional", "symmetric"]})["ok"]
    base = client.get(f"/api/projects/{pid}/graph").json()
    # rétrocompatible : mêmes nœuds qu'avant, deux champs en plus, aucun nouveau type
    assert {n["kind"] for n in base["nodes"]} == {"class"} and {n["id"] for n in base["nodes"]} == {c("Vehicle"), c("Car"), c("Garage")}
    assert all(n["external"] is False and "equivalent" in n for n in base["nodes"])
    assert {n["id"]: n["equivalent"] for n in base["nodes"]}[c("Car")] is True
    assert c("owns") in base["skipped"]
    g = client.get(f"/api/projects/{pid}/graph", params={"include": "external,anonymous,thing,datatypes"}).json()
    nodes = {n["id"]: n for n in g["nodes"]}
    assert nodes["http://xmlns.com/foaf/0.1/Agent"]["external"] is True and nodes["http://xmlns.com/foaf/0.1/Agent"]["kind"] == "class"
    anon = [n for n in g["nodes"] if n["kind"] == "anonymous"]
    assert {n["op"] for n in anon} == {"or", "not"} and {n["label"] for n in anon} == {"∪", "¬"}
    assert any(e["kind"] == "anonymousOf" and e["label"] == "unionOf" for e in g["edges"])
    assert any(e["kind"] == "equivalentClass" and e["target"].startswith("anon|") for e in g["edges"])
    things = [n for n in g["nodes"] if n["kind"] == "thing"]
    assert len(things) == 1 and things[0]["label"] == "Thing"
    owns = [e for e in g["edges"] if e["iri"] == c("owns")]
    assert owns and owns[0]["characteristics"] == ["functional", "symmetric"] and owns[0]["target"] == things[0]["id"]
    dp = [e for e in g["edges"] if e["kind"] == "datatypeProperty"]
    assert dp and dp[0]["deprecated"] is False and dp[0]["functional"] is False
    assert g == client.get(f"/api/projects/{pid}/graph", params={"include": "external,anonymous,thing,datatypes"}).json()


# ---- revue w3c L26 it1 : owl:Thing, inverses sans extrémités, espace de noms de repli --------------------------

def test_graph_l26_w3c_it1_thing_inverse_namespace(client, pid):
    from ontoforge.core.project import ProjectView
    from ontoforge.editing.graph import build_graph
    inc = {"external", "anonymous", "thing", "datatypes"}

    # 1) domaine déclaré mais hors de la vue (classe externe non demandée) : pas de nœud owl:Thing inventé
    def m(o):
        o["meta"]["iri"] = "https://example.org/t"
        o["object_properties"][c("servicedAt")]["domain"] = ["http://xmlns.com/foaf/0.1/Agent"]
    put_onto(client, pid, m)
    g = client.get(f"/api/projects/{pid}/graph", params={"include": "thing"}).json()
    assert not [n for n in g["nodes"] if n["kind"] == "thing"] and c("servicedAt") in g["skipped"]
    g = client.get(f"/api/projects/{pid}/graph", params={"include": "thing,external"}).json()
    e = [x for x in g["edges"] if x["iri"] == c("servicedAt")]
    assert e and e[0]["source"] == "http://xmlns.com/foaf/0.1/Agent"

    # 2) samples/trap : am:hasPart owl:inverseOf am:partOf, partOf sans domaine ni image → libellé porté par hasPart
    onto, _ = parse_ontology(open("../samples/trap/trap.ttl").read(), filename="trap.ttl")
    am = "https://w3id.org/ontoforge/automaint#"
    g = build_graph(onto, ProjectView(), "en", inc)
    hp = [x for x in g["edges"] if x["iri"] == am + "hasPart"]
    assert hp and all(x["inverse_label"] == "part of" for x in hp) and am + "partOf" not in g["skipped"]
    chars = {x["iri"]: x["characteristics"] for x in g["edges"] if x["kind"] == "objectProperty"}
    assert chars[am + "isComponentOf"] == ["transitive"] and set(chars[am + "supersedes"]) == {"asymmetric", "irreflexive"}
    assert chars[am + "hasRepairOrder"] == ["inverseFunctional"] and chars[am + "ofModel"] == ["functional"]
    assert not [n for n in g["nodes"] if n["external"]]  # tout est dans https://w3id.org/ontoforge/automaint#

    # 3) IRI d'ontologie distincte du vocabulaire : repli sur l'espace de noms majoritaire, rien n'est « externe » à tort
    onto.meta.iri = "https://example.org/other-ontology/1.0"
    g = build_graph(onto, ProjectView(), "en", inc)
    assert not [n for n in g["nodes"] if n["kind"] == "class" and n["external"] and n["id"].startswith(am)]
