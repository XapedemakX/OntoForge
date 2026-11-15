"""L36a — Carte métier : zones (5 stratégies), cadres, rôles, mise en page, aller-retour PUT/GET, source cible, effectifs, confidentialité."""
import math
import pathlib
import re
import time

import pytest
from fastapi.testclient import TestClient

from ontoforge.core.onto_model import ObjectProperty, OntClass, OntoModel, OntologyMeta
from ontoforge.main import app

AM = "https://w3id.org/ontoforge/automaint#"
NS = "https://example.org/synth#"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("ONTOFORGE_DATA", str(tmp_path))
    return TestClient(app)


@pytest.fixture
def pid(client):
    r = client.post("/api/projects", json={"name": "Automaint", "sample": "automaint"})
    assert r.status_code in (200, 201), r.text
    return r.json()["id"]


def synth_onto(classes: dict, rels: list, ns: str = NS, parents: dict | None = None, ns_of: dict | None = None) -> dict:
    """OntoModel synthétique : classes {nom: [parents]}, relations [(nom, domaine, image)]."""
    parents = parents or {}
    iri = lambda n: (ns_of or {}).get(n, ns) + n
    cls = {iri(n): OntClass(iri=iri(n), labels={"fr": n}, sub_class_of=[iri(p) for p in parents.get(n, [])]) for n in classes}
    props = {}
    for name, d, r in rels:
        doms = [d] if isinstance(d, str) else d  # plusieurs domaines : une même propriété partagée par plusieurs classes
        props[ns + name] = ObjectProperty(iri=ns + name, labels={"fr": name}, domain_union=[iri(x) for x in doms], range=[iri(r)])
    m = OntoModel(meta=OntologyMeta(iri=ns.rstrip("#")), classes=cls, object_properties=props)
    return m.model_dump(mode="json")


def synth_pid(client, onto: dict) -> str:
    pid = client.post("/api/projects", json={"name": "Synthèse"}).json()["id"]
    assert client.put(f"/api/projects/{pid}/onto", json=onto).status_code == 200
    return pid


def big_synth(n: int = 60) -> dict:
    """n classes en grappes de 6, relations internes et quelques liens entre grappes."""
    names = [f"T{i:02d}" for i in range(n)]
    rels = []
    for i, a in enumerate(names):
        g = i // 6
        rels.append((f"in{i}", a, names[g * 6 + (i + 1) % 6 if g * 6 + (i + 1) % 6 < n else g * 6]))
        if i % 3 == 0:
            rels.append((f"x{i}", a, names[(i * 7 + 13) % n]))
    return synth_onto({k: [] for k in names}, rels)


def get_map(client, pid, source="ontology"):
    r = client.get(f"/api/projects/{pid}/business-map", params={"source": source})
    assert r.status_code == 200, r.text
    return r.json()


def assert_inside(m):
    z = {x["id"]: x["rect"] for x in m["zones"]}
    for n in m["nodes"]:
        rc = z[n["zone"]]
        assert rc["x"] <= n["x"] - n["r"] and n["x"] + n["r"] <= rc["x"] + rc["w"], n["id"]
        assert rc["y"] <= n["y"] - n["r"] and n["y"] + n["r"] <= rc["y"] + rc["h"], n["id"]


def assert_no_overlap(m):
    ns = m["nodes"]
    for i, a in enumerate(ns):
        for b in ns[i + 1:]:
            assert math.hypot(a["x"] - b["x"], a["y"] - b["y"]) >= a["r"] + b["r"], (a["id"], b["id"])


# ----------------------------------------------------------------------------- GET initial
def test_initial_map_ontology(client, pid):
    m = get_map(client, pid)
    assert m["source"] == "ontology" and m["meta"]["generated"] is True
    assert m["meta"]["n_types"] == 24 and m["meta"]["n_relations"] == len([e for e in m["edges"] if e["kind"] == "relation"])
    keys = {"id", "label", "role", "zone", "count", "faded", "pinned", "x", "y", "r"}
    assert all(keys <= set(n) for n in m["nodes"])
    ids = [n["id"] for n in m["nodes"]]
    assert len(ids) == 24 == len(set(ids))
    placed = [x for z in m["zones"] for x in z["members"]]
    assert sorted(placed) == sorted(ids)  # chaque nœud dans une seule zone
    assert all(z["rect"]["w"] > 0 and z["color"] for z in m["zones"])
    assert m["canvas"]["width"] > 0 and m["canvas"]["height"] > 0
    assert {"title", "model_date", "n_types", "n_relations"} <= set(m["meta"])
    assert_inside(m)
    assert_no_overlap(m)
    kinds = {e["kind"] for e in m["edges"]}
    assert {"relation", "subclass"} <= kinds
    # inverses fusionnées : une seule arête « both » avec les deux noms
    both = [e for e in m["edges"] if e["direction"] == "both"]
    assert {(e["label"], e["inverse_label"]) for e in both if e["id"].startswith(AM + "concerns")} == {("concerne", "a pour ordre de réparation")}
    assert not [e for e in m["edges"] if e["id"].startswith(AM + "hasRepairOrder")]
    # lecture suivante : même proposition (gardée en mémoire) ; L41 : la lecture n'écrit rien dans le projet
    assert get_map(client, pid) == {**m, "meta": {**m["meta"]}}
    p = client.get(f"/api/projects/{pid}").json()
    assert "ontology" not in p["business_maps"]


def test_bad_source_and_unknown_project(client, pid):
    assert client.get(f"/api/projects/{pid}/business-map", params={"source": "x"}).status_code == 422
    assert client.get("/api/projects/nope/business-map").status_code == 404


# ----------------------------------------------------------------------------- rôles
def test_role_heuristics(client):
    cls = {n: [] for n in ("Status", "Doc", "Line", "Hub", "A", "B", "C", "D", "Manual")}
    rels = [(f"hasStatus{n}", n, "Status") for n in ("A", "B", "C")] + [(f"linkHub{n}", n, "Hub") for n in ("A", "B", "C", "D")] + \
           [("hubRef", "Hub", "A"), ("hubRef2", "Hub", "B"), ("lineOf", "Line", "Doc"), ("partOfDoc", "Line", "Doc")]
    pid = synth_pid(client, synth_onto(cls, rels))
    roles = {n["id"].split("#")[1]: n["role"] for n in get_map(client, pid)["nodes"]}
    assert roles["Status"] == "lookup"  # ciblé par 3 types, aucune relation sortante
    assert roles["Hub"] == "hub"  # ciblé par 4 types
    assert roles["Line"] == "component" and roles["Doc"] == "main"  # relation « partie de »
    assert roles["Manual"] == "document"  # nom de document
    m = get_map(client, pid)
    assert {l["role"] for l in m["legend"]} >= {"lookup", "hub", "component", "main"}
    assert all(l["color"].startswith("#") for l in m["legend"])


# ----------------------------------------------------------------------------- zones
STRATS = ("perimeters", "hierarchy", "namespace", "communities", "llm")


def covers(m_ids, zones):
    placed = [x for z in zones for x in z["members"]]
    return sorted(placed) == sorted(m_ids) and all(z["title"] for z in zones)


def test_suggest_zones_all_strategies(client, pid):
    ids = [n["id"] for n in get_map(client, pid)["nodes"]]
    classes = sorted(ids)
    for name, cs in (("Parc", [AM + "Vehicle", AM + "Part", AM + "Warranty"]), ("Atelier", [AM + "RepairOrder", AM + "Garage", AM + "Technician"])):
        assert client.post(f"/api/projects/{pid}/perimeters", json={"name": name, "classes": cs}).status_code == 201
    out = {}
    for s in STRATS:
        r = client.post(f"/api/projects/{pid}/business-map/suggest-zones", json={"strategy": s, "provider_id": "mock"})
        assert r.status_code == 200, (s, r.text)
        j = r.json()
        out[s] = j
        assert j["applied"] is False and covers(classes, j["zones"]), s
        assert all(z["id"] and z["color"] for z in j["zones"])
    assert {z["title"] for z in out["perimeters"]["zones"]} >= {"Parc", "Atelier"}
    assert len(out["hierarchy"]["zones"]) >= 3
    assert out["namespace"]["strategy"] == "namespace" and out["namespace"]["warnings"]  # un seul espace de noms : repli signalé
    assert len(out["communities"]["zones"]) >= 2
    # repli mock : titres déterministes, sous-titres non vides
    again = client.post(f"/api/projects/{pid}/business-map/suggest-zones", json={"strategy": "llm", "provider_id": "mock"}).json()
    assert [(z["title"], z["subtitle"]) for z in again["zones"]] == [(z["title"], z["subtitle"]) for z in out["llm"]["zones"]]
    assert all(z["subtitle"] for z in out["llm"]["zones"] if z["id"] != "other")
    assert client.post(f"/api/projects/{pid}/business-map/suggest-zones", json={"strategy": "nope"}).status_code == 422
    # rien n'est enregistré sans apply : la carte reste la proposition initiale (L41 : même la lecture ne l'enregistre plus)
    assert "ontology" not in client.get(f"/api/projects/{pid}").json()["business_maps"]


def test_suggest_zones_namespace_and_apply(client):
    A, B = "https://example.org/a#", "https://example.org/b#"
    names = ["A1", "A2", "A3", "B1", "B2", "B3"]
    ns_of = {n: (A if n[0] == "A" else B) for n in names}
    onto = synth_onto({n: [] for n in names}, [("r1", "A1", "A2"), ("r2", "B1", "B2")], ns_of=ns_of)
    pid = synth_pid(client, onto)
    j = client.post(f"/api/projects/{pid}/business-map/suggest-zones", json={"strategy": "namespace", "apply": True}).json()
    assert j["strategy"] == "namespace" and not j["warnings"]
    groups = sorted(sorted(x.split("#")[1] for x in z["members"]) for z in j["zones"])
    assert groups == [["A1", "A2", "A3"], ["B1", "B2", "B3"]]
    assert j["map"]["meta"]["generated"] is False
    assert {z["id"] for z in get_map(client, pid)["zones"]} == {z["id"] for z in j["zones"]}


def test_hierarchy_branches(client):
    cls = {"Root": [], "X": ["Root"], "Y": ["Root"], "X1": ["X"], "X2": ["X"], "Y1": ["Y"], "Y2": ["Y"], "Z": [], "Z1": ["Z"]}
    parents = {k: v for k, v in cls.items() if v}
    pid = synth_pid(client, synth_onto(cls, [], parents=parents))
    j = client.post(f"/api/projects/{pid}/business-map/suggest-zones", json={"strategy": "hierarchy"}).json()
    groups = sorted(sorted(x.split("#")[1] for x in z["members"]) for z in j["zones"])
    assert ["X", "X1", "X2"] in groups or ["Root", "X", "X1", "X2"] in groups
    assert any({"Y", "Y1", "Y2"} <= set(g) for g in groups) and ["Z", "Z1"] in groups


def test_communities_split_two_clusters(client):
    a = [f"P{i}" for i in range(5)]
    b = [f"Q{i}" for i in range(5)]
    rels = [(f"pa{i}{j}", a[i], a[j]) for i in range(5) for j in range(i + 1, 5)] + [(f"qb{i}{j}", b[i], b[j]) for i in range(5) for j in range(i + 1, 5)]
    rels.append(("bridge", "P0", "Q0"))
    pid = synth_pid(client, synth_onto({k: [] for k in a + b}, rels))
    j = client.post(f"/api/projects/{pid}/business-map/suggest-zones", json={"strategy": "communities"}).json()
    groups = sorted(sorted(x.split("#")[1] for x in z["members"]) for z in j["zones"])
    assert groups == [a, b]


# ----------------------------------------------------------------------------- cadres
def frame_onto():
    cls = {n: [] for n in ("A", "B", "C", "D", "T1", "T2", "T3")}
    rels = [("uses1", ["A", "B", "C", "D"], "T1"), ("uses2", ["A", "B", "C"], "T2"), ("own", "A", "T3")]
    return synth_onto(cls, rels)


def test_suggest_frames_and_frame_edges(client):
    pid = synth_pid(client, frame_onto())
    j = client.post(f"/api/projects/{pid}/business-map/suggest-frames", json={}).json()
    assert len(j["frames"]) == 1
    f = j["frames"][0]
    assert sorted(x.split("#")[1] for x in f["members"]) == ["A", "B", "C"]
    assert len(f["shared"]) >= 2 and f["note"] and f["title"]
    j = client.post(f"/api/projects/{pid}/business-map/suggest-frames", json={"apply": True}).json()
    m = j["map"]
    assert len(m["frames"]) == 1 and m["frames"][0]["rect"]["w"] > 0
    fe = [e for e in m["edges"] if e["kind"] == "frame"]
    assert fe and all(e["source_kind"] == "frame" and e["source"] == m["frames"][0]["id"] and len(e["members"]) == len(e["replaces"]) for e in fe)
    replaced = {r for e in fe for r in e["replaces"]}
    assert not replaced & {e["id"] for e in m["edges"]}  # les relations remplacées ne sont plus dessinées une par une
    assert get_map(client, pid)["frames"][0]["id"] == m["frames"][0]["id"]


def test_no_frame_when_less_than_two_shared(client):
    cls = {n: [] for n in ("A", "B", "T1", "T2")}
    pid = synth_pid(client, synth_onto(cls, [("r1", ["A", "B"], "T1"), ("r2", "A", "T2")]))
    assert client.post(f"/api/projects/{pid}/business-map/suggest-frames", json={}).json()["frames"] == []


# ----------------------------------------------------------------------------- mise en page
def test_layout_automaint(client, pid):
    m = get_map(client, pid)
    j = client.post(f"/api/projects/{pid}/business-map/layout", json={"seed": 3}).json()
    assert set(j["positions"]) == {n["id"] for n in m["nodes"]} and j["stats"]["elapsed_ms"] < 5000
    assert j["stats"]["crossings"] <= j["stats"]["initial_crossings"]
    assert client.get(f"/api/projects/{pid}/business-map").json()["nodes"][0]["x"] == m["nodes"][0]["x"]  # sans apply : rien n'est enregistré
    j2 = client.post(f"/api/projects/{pid}/business-map/layout", json={"seed": 3, "apply": True}).json()
    assert j2["positions"] == j["positions"]  # déterministe pour une graine
    m2 = j2["map"]
    assert_inside(m2)
    assert_no_overlap(m2)


def test_layout_respects_pins(client, pid):
    m = get_map(client, pid)
    z = {x["id"]: x["rect"] for x in m["zones"]}
    n0 = m["nodes"][0]
    rc = z[n0["zone"]]
    pin = {"x": rc["x"] + rc["w"] - n0["r"] - 40, "y": rc["y"] + rc["h"] - n0["r"] - 50}
    r = client.put(f"/api/projects/{pid}/business-map", json={"pinned": [n0["id"]], "positions": {n0["id"]: pin}})
    assert r.status_code == 200, r.text
    j = client.post(f"/api/projects/{pid}/business-map/layout", json={"iterations": 3000, "apply": True}).json()
    assert j["positions"][n0["id"]] == pin
    node = next(n for n in j["map"]["nodes"] if n["id"] == n0["id"])
    assert node["pinned"] is True and (node["x"], node["y"]) == (pin["x"], pin["y"])
    assert_inside(j["map"])
    assert_no_overlap(j["map"])


def test_layout_60_nodes_fast(client):
    pid = synth_pid(client, big_synth(60))
    t = time.perf_counter()
    m = get_map(client, pid)  # proposition initiale : zones + mise en page
    j = client.post(f"/api/projects/{pid}/business-map/layout", json={"seed": 1, "apply": True}).json()
    assert time.perf_counter() - t < 8  # deux mises en page de moins de 5 s chacune
    assert j["stats"]["elapsed_ms"] < 5000
    assert len(m["nodes"]) == 60
    m2 = j["map"]
    assert_inside(m2)
    assert_no_overlap(m2)
    assert j["stats"]["crossings"] <= j["stats"]["initial_crossings"]
    # zones de taille proportionnelle au nombre de membres
    by = sorted(m2["zones"], key=lambda z: len(z["members"]))
    areas = [z["rect"]["w"] * z["rect"]["h"] for z in by]
    assert areas[0] <= areas[-1]


# ----------------------------------------------------------------------------- PUT / GET
def test_put_get_roundtrip(client, pid):
    m = get_map(client, pid)
    ids = [n["id"] for n in m["nodes"]]
    vehicle, order, part = AM + "Vehicle", AM + "RepairOrder", AM + "Part"
    zones = [{"id": "z1", "title": "Parc", "subtitle": "ce qui roule", "color": "#aabbcc", "members": [vehicle, part]},
             {"id": "z2", "title": "Atelier", "subtitle": "", "color": "#ddeeff", "members": [order]}]
    body = {"zones": zones, "roles": {vehicle: "pivot-libre", order: "main"}, "role_colors": {"pivot-libre": "#112233"},
            "faded": [part], "pinned": [vehicle], "positions": {vehicle: {"x": 300, "y": 280}},
            "frames": [{"id": "f1", "title": "Cadre", "members": [order, part], "note": "n"}],
            "scenarios": [{"id": "s1", "name": "Lecture", "description": "d", "edge_styles": {f"{AM}ownedBy|{vehicle}|{AM}Customer": "scored"}, "nodes": [vehicle]}]}
    r = client.put(f"/api/projects/{pid}/business-map", json=body)
    assert r.status_code == 200, r.text
    got = get_map(client, pid)
    z = {x["id"]: x for x in got["zones"]}
    assert z["z1"]["title"] == "Parc" and z["z1"]["subtitle"] == "ce qui roule" and z["z1"]["color"] == "#aabbcc"
    assert z["z1"]["members"] == [vehicle, part] and z["z2"]["members"] == [order]
    assert "other" in z and len(z["other"]["members"]) == len(ids) - 3  # les nœuds sans zone vont dans « Autres »
    n = {x["id"]: x for x in got["nodes"]}
    assert n[vehicle]["role"] == "pivot-libre" and n[vehicle]["role_source"] == "manual"
    assert n[order]["role"] == "main" and n[order]["role_source"] == "auto"  # égal au rôle déduit : pas de surcharge enregistrée
    assert n[part]["faded"] is True and n[vehicle]["pinned"] is True
    assert (n[vehicle]["x"], n[vehicle]["y"]) == (300, 280)
    assert next(l for l in got["legend"] if l["role"] == "pivot-libre")["color"] == "#112233"
    assert got["frames"][0]["id"] == "f1" and got["frames"][0]["members"] == [order, part] and got["frames"][0]["note"] == "n"
    sc = got["scenarios"][0]
    assert sc["id"] == "s1" and sc["edge_styles"] and sc["nodes"] == [vehicle]
    assert got["meta"]["generated"] is False
    # persistance dans le projet, rechargé
    assert client.get(f"/api/projects/{pid}").json()["business_maps"]["ontology"]["pinned"] == [vehicle]
    # changer d'avis : un PUT partiel garde le reste
    assert client.put(f"/api/projects/{pid}/business-map", json={"faded": []}).status_code == 200
    again = get_map(client, pid)
    assert [x["id"] for x in again["nodes"] if x["faded"]] == [] and again["frames"][0]["id"] == "f1"


def test_put_validation(client, pid):
    v, p = AM + "Vehicle", AM + "Part"
    url = f"/api/projects/{pid}/business-map"
    assert client.put(url, json={"zones": [{"id": "a", "title": "A", "members": [v]}, {"id": "b", "title": "B", "members": [v]}]}).status_code == 422
    assert client.put(url, json={"zones": [{"id": "a", "title": "A"}, {"id": "a", "title": "B"}]}).status_code == 422
    assert client.put(url, json={"scenarios": [{"id": "s", "name": "n", "edge_styles": {"x": "fluo"}}]}).status_code == 422
    assert client.put(url, json={"roles": {v: ""}}).status_code == 422
    assert client.put(url, json={"frames": [{"id": "f", "members": [v, p]}, {"id": "f", "members": [v, p]}]}).status_code == 422
    # membres inconnus : ignorés à la lecture
    r = client.put(url, json={"zones": [{"id": "a", "title": "A", "members": [v, AM + "Fantome"]}]})
    assert r.status_code == 200
    assert AM + "Fantome" not in [x["id"] for x in r.json()["nodes"]]
    for style in ("scored", "gate", "read", "context", "context_off", "grouped", "disabled", "both", "mention", "oneway"):
        assert client.put(url, json={"scenarios": [{"id": "s", "name": "n", "edge_styles": {"e": style}}]}).status_code == 200


# ----------------------------------------------------------------------------- source cible
def test_target_source(client, pid):
    m = get_map(client, pid, "target")
    assert m["source"] == "target" and m["meta"]["target"] == "curiosity"
    names = {n["id"] for n in m["nodes"]}
    assert {"Vehicle", "RepairOrder", "Customer"} <= names and AM + "Vehicle" not in names
    assert m["meta"]["n_types"] == len(names)
    assert all(e["source"] in names and e["target"] in names for e in m["edges"])
    assert next(n for n in m["nodes"] if n["id"] == "Vehicle")["role"] == "hub"
    assert_inside(m)
    assert_no_overlap(m)
    # cartes indépendantes par source
    client.put(f"/api/projects/{pid}/business-map", params={"source": "target"}, json={"title": "Cible"})
    assert get_map(client, pid, "target")["meta"]["title"] == "Cible"
    assert get_map(client, pid, "ontology")["meta"]["title"] != "Cible"
    zones = client.post(f"/api/projects/{pid}/business-map/suggest-zones", params={"source": "target"}, json={"strategy": "communities"}).json()
    assert covers(sorted(names), zones["zones"])
    cur = client.get(f"/api/projects/{pid}").json()
    assert cur["business_maps"]["target"]["title"] == "Cible"


# ----------------------------------------------------------------------------- effectifs
def test_counts_from_local_store(client, pid):
    m = get_map(client, pid)
    assert m["meta"]["counts"] == "ontology"
    r = client.post(f"/api/projects/{pid}/store/load", data={"sample": "demo"})
    assert r.status_code == 200, r.text
    m = get_map(client, pid)
    assert m["meta"]["counts"] == "store"
    c = {n["id"]: n["count"] for n in m["nodes"]}
    assert c[AM + "Vehicle"] and c[AM + "Vehicle"] > 0
    assert any(v is not None for v in c.values())


def test_counts_null_without_data(client):
    pid = synth_pid(client, synth_onto({"A": [], "B": []}, [("r", "A", "B")]))
    m = get_map(client, pid)
    assert all(n["count"] is None for n in m["nodes"]) and m["meta"]["counts"] == "none"


def test_empty_zone_survives_put_get(client, pid):
    """L36c (revue scout 1, W3C C) : une zone vide enregistrée revient au GET avec un rectangle, et un PUT calqué sur la réponse la garde."""
    url = f"/api/projects/{pid}/business-map"
    v = AM + "Vehicle"
    zones = [{"id": "z1", "title": "Pleine", "members": [v]}, {"id": "vide", "title": "En préparation", "subtitle": "à remplir", "members": []}]
    assert client.put(url, json={"zones": zones}).status_code == 200
    got = get_map(client, pid)
    z = {x["id"]: x for x in got["zones"]}
    assert "vide" in z and z["vide"]["members"] == [] and z["vide"]["rect"]["w"] > 0 and z["vide"]["rect"]["h"] > 0
    assert z["vide"]["title"] == "En préparation" and z["vide"]["subtitle"] == "à remplir"
    assert_inside(got)
    # le front renvoie les zones reçues : la zone vide ne disparaît pas au PUT suivant
    again = [{k: x[k] for k in ("id", "title", "subtitle", "color", "members")} for x in got["zones"]]
    assert client.put(url, json={"zones": again, "pinned": []}).status_code == 200
    assert "vide" in {x["id"] for x in get_map(client, pid)["zones"]}
    # la zone ne recouvre aucune autre
    rs = [x["rect"] for x in get_map(client, pid)["zones"]]
    for i, a in enumerate(rs):
        for b in rs[i + 1:]:
            assert a["x"] + a["w"] <= b["x"] or b["x"] + b["w"] <= a["x"] or a["y"] + a["h"] <= b["y"] or b["y"] + b["h"] <= a["y"]


def test_default_roles_are_generic_and_legacy_ids_migrate(client, pid):
    from ontoforge.businessmap.model import BUILTIN_ROLES, LEGACY_ROLES, canonical_role
    from ontoforge.businessmap.roles import ROLE_COLORS, ROLE_LABELS
    assert BUILTIN_ROLES == ("main", "component", "hub", "lookup", "context", "reference", "document", "settings")
    assert set(ROLE_COLORS) == set(BUILTIN_ROLES) == set(ROLE_LABELS) and len(set(ROLE_COLORS.values())) == 8
    assert set(LEGACY_ROLES.values()) <= set(BUILTIN_ROLES)
    v = AM + "Vehicle"
    assert client.put(f"/api/projects/{pid}/business-map", json={"roles": {v: "classifier"}}).status_code == 200  # ancien id
    n = {x["id"]: x for x in get_map(client, pid)["nodes"]}
    assert n[v]["role"] == "lookup" and n[v]["role_source"] == "manual"
    assert client.get(f"/api/projects/{pid}").json()["business_maps"]["ontology"]["roles"][v] == "lookup"
    assert canonical_role("issue") == "main" and canonical_role("mon-rôle") == "mon-rôle" and canonical_role("") is None


def test_no_domain_specific_words_in_role_heuristics():
    import ontoforge.businessmap.graph as G
    import ontoforge.businessmap.roles as R
    for rx in (R.DOCUMENT, R.SETTINGS, R.REFERENCE, G.HAS_PART):
        for word in ("recall", "rappel", "warranty", "garantie", "bulletin", "reading", "operation"):
            assert not rx.search(word), (rx.pattern, word)


def test_disjoint_union_is_not_abstract(client):
    onto = synth_onto({"Parent": [], "A": ["Parent"], "B": ["Parent"]}, [])
    onto["classes"][NS + "Parent"]["disjoint_union_of"] = [[NS + "A", NS + "B"]]
    pid = synth_pid(client, onto)
    assert all(not n["abstract"] for n in get_map(client, pid)["nodes"])


def test_skipped_properties_reported(client):
    onto = synth_onto({"A": [], "B": []}, [("ok", "A", "B")])
    onto["object_properties"][NS + "orphan"] = {"iri": NS + "orphan", "labels": {"fr": "orpheline"}, "domain": [NS + "A"]}  # pas d'image
    pid = synth_pid(client, onto)
    m = get_map(client, pid)
    assert [s["id"] for s in m["meta"]["skipped"]] == [NS + "orphan"] and m["meta"]["skipped"][0]["label"] == "orpheline"
    assert m["meta"]["n_relations"] == 1


def test_union_edges_flagged_and_link_kinds(client):
    onto = synth_onto({"A": [], "B": [], "X": [], "Y": []}, [("u", ["A", "B"], "X"), ("plain", "A", "Y")])
    onto["object_properties"][NS + "twin"] = {"iri": NS + "twin", "labels": {"fr": "jumelle"}, "domain": [NS + "X"], "range": [NS + "Y"], "characteristics": ["symmetric"]}
    onto["object_properties"][NS + "fwd"] = {"iri": NS + "fwd", "labels": {"fr": "aller"}, "domain": [NS + "X"], "range": [NS + "B"], "inverse_of": NS + "back"}
    onto["object_properties"][NS + "back"] = {"iri": NS + "back", "labels": {"fr": "retour"}, "domain": [NS + "B"], "range": [NS + "X"], "inverse_of": NS + "fwd"}
    pid = synth_pid(client, onto)
    m = get_map(client, pid)
    by = {e["id"].split("|")[0].split("#")[-1]: e for e in m["edges"] if e["kind"] == "relation"}
    assert by["twin"]["link"] == "symmetric" and by["back"]["link"] == "inverse" and by["plain"]["link"] is None
    assert by["plain"]["union"] is False
    u = [e for e in m["edges"] if e["id"].startswith(NS + "u|")]
    assert len(u) == 2 and all(e["union"] for e in u) and m["meta"]["n_union"] == 2


# ----------------------------------------------------------------------------- effectifs : fermeture rdfs:subClassOf
def _with_individuals(onto: dict, inds: dict) -> dict:
    onto["individuals"] = {NS + k: {"iri": NS + k, "types": [NS + t for t in ts]} for k, ts in inds.items()}
    return onto


def test_counts_closed_under_subclass_ontology(client):
    onto = synth_onto({"Vehicle": [], "Electric": [], "Truck": [], "Owner": []}, [("ownedBy", "Vehicle", "Owner")], parents={"Electric": ["Vehicle"], "Truck": ["Vehicle"]})
    # v3 est typé par les deux sous-classes : il compte une seule fois pour la mère ; v4 par la mère et une fille
    _with_individuals(onto, {"v1": ["Electric"], "v2": ["Electric"], "v3": ["Electric", "Truck"], "v4": ["Vehicle", "Truck"], "o1": ["Owner"]})
    pid = synth_pid(client, onto)
    m = get_map(client, pid)
    assert m["meta"]["counts"] == "ontology"
    c = {n["id"].split("#")[1]: n["count"] for n in m["nodes"]}
    assert c == {"Vehicle": 4, "Electric": 3, "Truck": 2, "Owner": 1}


def test_counts_closed_and_distinct_with_store(client):
    onto = synth_onto({"Vehicle": [], "Electric": [], "Owner": []}, [("ownedBy", "Vehicle", "Owner")], parents={"Electric": ["Vehicle"]})
    pid = synth_pid(client, onto)
    ttl = f"@prefix ex: <{NS}> .\nex:v1 a ex:Electric , ex:Vehicle .\nex:v2 a ex:Electric .\nex:v3 a ex:Vehicle .\nex:o1 a ex:Owner .\n"
    r = client.post(f"/api/projects/{pid}/store/load", files={"file": ("d.ttl", ttl.encode())}, data={"inference": "none"})
    assert r.status_code == 200, r.text
    m = get_map(client, pid)
    assert m["meta"]["counts"] == "store"
    c = {n["id"].split("#")[1]: n["count"] for n in m["nodes"]}
    assert c == {"Vehicle": 3, "Electric": 2, "Owner": 1}  # v1 typé deux fois : une seule fois pour Vehicle


def test_counts_target_no_double_count():
    """Cible : un individu typé par deux classes sources fusionnées dans un même type n'est compté qu'une fois."""
    from ontoforge.businessmap.counts import apply_counts
    from ontoforge.businessmap.graph import SchemaGraph, SNode
    from ontoforge.core.onto_model import Individual
    onto = OntoModel(meta=OntologyMeta(iri=NS.rstrip("#")), classes={NS + n: OntClass(iri=NS + n) for n in ("A", "B")})
    onto.individuals[NS + "i1"] = Individual(iri=NS + "i1", types=[NS + "A", NS + "B"])
    onto.individuals[NS + "i2"] = Individual(iri=NS + "i2", types=[NS + "B"])
    g = SchemaGraph(nodes={"AB": SNode(id="AB", label="AB", sources=[NS + "A", NS + "B"])})
    assert apply_counts(g, onto, None) == "ontology"
    assert g.nodes["AB"].count == 2


# ----------------------------------------------------------------------------- confidentialité
# Les noms interdits sont écrits à l'envers pour que ce fichier ne les contienne pas lui-même.
_REV = ("metiblA", "mi1y", "bla", "rsq", "mst", "subria", "uft", "i" "si")
_NAMES = [w[::-1] for w in _REV]
_NAMES[1] = "1y" "im"
FORBIDDEN = re.compile(r"\b(" + "|".join(_NAMES) + r")\b", re.I)


def test_no_confidential_names_in_backend():
    root = pathlib.Path(__file__).resolve().parents[1] / "ontoforge"
    bad = []
    for f in root.rglob("*"):
        if f.suffix in (".py", ".json", ".md", ".txt", ".html", ".js", ".ts") and f.is_file():
            for i, line in enumerate(f.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
                if FORBIDDEN.search(line):
                    bad.append(f"{f.relative_to(root)}:{i}")
    assert not bad, f"noms interdits trouvés : {bad}"


def test_no_confidential_names_strict_in_businessmap():
    """Le grep de la consigne (sans borne de mot au début) doit être vide pour les fichiers de la carte métier."""
    n = _NAMES
    strict = re.compile(f"{n[0]}|{n[1]}|\\b{n[2]}\\b|{n[3]}|{n[4]}\\b|{n[5]}|{n[6]}|{n[7]}\\b", re.I)
    base = pathlib.Path(__file__).resolve().parents[1] / "ontoforge"
    files = list((base / "businessmap").glob("*.py")) + [base / "api" / "business_map.py"]
    bad = [f"{f.name}:{i}" for f in files for i, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1) if strict.search(line)]
    assert not bad, bad
