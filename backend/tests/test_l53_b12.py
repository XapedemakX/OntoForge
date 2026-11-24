"""L53 : DF-B12 — FILTER EXISTS, FILTER NOT EXISTS et MINUS dont le sous-motif se réduit à un typage.

Avant : `WHERE [NOT] EXISTS { MATCH  }` (Cypher invalide) sur les deux cibles, lossy=false sans note, et le typage du
sous-motif modifiait le type de la variable extérieure (classe perdue, C# inversé). Voir journal/L53/corrections-b12.md."""
from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient

AM = "https://w3id.org/ontoforge/automaint#"
P = f"PREFIX am: <{AM}> "
EMPTY_MATCH = re.compile(r"\bMATCH\s*(?:WHERE\b|\}|,|$)", re.M)


@pytest.fixture(scope="module")
def tr(tmp_path_factory):
    mp = pytest.MonkeyPatch()
    mp.setenv("ONTOFORGE_DATA", str(tmp_path_factory.mktemp("b12")))
    mp.setenv("ONTOFORGE_LLM_PROVIDER", "mock")
    from ontoforge.main import app
    client = TestClient(app, raise_server_exceptions=False)
    r = client.post("/api/projects", json={"name": "t", "sample": "automaint"})
    assert r.status_code in (200, 201), r.text
    pid = r.json()["id"]

    def run(where: str, target: str, select: str = "?v") -> dict:
        r = client.post(f"/api/projects/{pid}/queries/translate?target={target}",
                        json={"sparql": P + f"SELECT {select} WHERE {{ " + where + " }"})
        assert r.status_code == 200, r.text
        return r.json()
    yield run
    mp.undo()


def _where(j: dict) -> str:
    return next(line for line in j["cypher"].split("\n") if line.startswith("WHERE "))[len("WHERE "):]


# ---- neo4j : label général (Vehicle) + label propre (ElectricVehicle) posés par targets/neo4j.py → prédicat de label
NEO4J = [
    ("?v a am:Vehicle . FILTER EXISTS { ?v a am:Vehicle }", "MATCH (v:Vehicle)", "v:Vehicle"),
    ("?v a am:Vehicle . FILTER EXISTS { ?v a am:ElectricVehicle }", "MATCH (v:Vehicle)", "v:ElectricVehicle"),
    ("?v a am:Vehicle . FILTER NOT EXISTS { ?v a am:ElectricVehicle }", "MATCH (v:Vehicle)", "NOT v:ElectricVehicle"),
    ("?v a am:Vehicle . MINUS { ?v a am:ElectricVehicle }", "MATCH (v:Vehicle)", "NOT v:ElectricVehicle"),
    # classe disjointe sous une variable déjà typée par un sous-type
    ("?v a am:ElectricVehicle . FILTER NOT EXISTS { ?v a am:CombustionVehicle }", "MATCH (v:ElectricVehicle)",
     "NOT v:CombustionVehicle"),
    ("?v a am:ElectricVehicle . FILTER EXISTS { ?v a am:CombustionVehicle }", "MATCH (v:ElectricVehicle)",
     "v:CombustionVehicle"),
    ("?v a am:ElectricVehicle . MINUS { ?v a am:ElectricVehicle }", "MATCH (v:ElectricVehicle)", "NOT v:ElectricVehicle"),
]

# ---- curiosity : type aplati Vehicle + discriminant VehicleKind ; coalesce : un nœud sans discriminant n'est pas exclu à tort
CUR_EV = "(v:Vehicle AND coalesce(v.VehicleKind = 'ElectricVehicle', false))"
CUR_CV = "(v:Vehicle AND coalesce(v.VehicleKind = 'CombustionVehicle', false))"
CURIOSITY = [
    ("?v a am:Vehicle . FILTER EXISTS { ?v a am:Vehicle }", "v:Vehicle"),
    ("?v a am:Vehicle . FILTER EXISTS { ?v a am:ElectricVehicle }", CUR_EV),
    ("?v a am:Vehicle . FILTER NOT EXISTS { ?v a am:ElectricVehicle }", "NOT " + CUR_EV),
    ("?v a am:Vehicle . MINUS { ?v a am:ElectricVehicle }", "NOT " + CUR_EV),
    ("?v a am:ElectricVehicle . FILTER NOT EXISTS { ?v a am:CombustionVehicle }",
     "v.VehicleKind = 'ElectricVehicle' AND NOT " + CUR_CV),
    ("?v a am:ElectricVehicle . FILTER EXISTS { ?v a am:CombustionVehicle }",
     "v.VehicleKind = 'ElectricVehicle' AND " + CUR_CV),
]


# it2 (revue query L53 it1) : un typage disjoint (ElectricVehicle / CombustionVehicle) est une intersection non
# représentable, perte comme au niveau principal, sans changer le prédicat
DISJOINT = "?v a am:ElectricVehicle . FILTER"
INTER_LOSS = "intersection non représentable"


def _loss_ok(j, where):
    if where.startswith(DISJOINT):
        assert j["lossy"] and any(n.startswith("[perte]") and INTER_LOSS in n for n in j["notes"]), j["notes"]
    else:
        assert not j["lossy"], j["notes"]


@pytest.mark.parametrize("where,match,cond", NEO4J)
def test_b12_neo4j_type_only_subpattern_is_a_label_predicate(tr, where, match, cond):
    j = tr(where, "neo4j")
    assert not EMPTY_MATCH.search(j["cypher"]), j["cypher"]
    assert j["cypher"] == f"{match}\nWHERE {cond}\nRETURN v.uri AS v", j["cypher"]
    _loss_ok(j, where)


@pytest.mark.parametrize("where,cond", CURIOSITY)
def test_b12_curiosity_type_only_subpattern_is_a_discriminator_predicate(tr, where, cond):
    j = tr(where, "curiosity")
    assert not EMPTY_MATCH.search(j["cypher"]), j["cypher"]
    assert _where(j) == cond, j["cypher"]
    _loss_ok(j, where)


def test_b12_curiosity_csharp_keeps_the_restriction(tr):
    """Avant : NOT EXISTS { ?v a am:ElectricVehicle } donnait en C# un filtre « = ElectricVehicle » (sens inversé)."""
    j = tr("?v a am:Vehicle . FILTER NOT EXISTS { ?v a am:ElectricVehicle }", "curiosity")
    cs = j["curiosity"]
    assert '.Where(n => !(n.GetString(N.Vehicle.VehicleKind) == "ElectricVehicle"))' in cs, cs
    assert "WhereString" not in cs and "Traduction partielle" not in cs, cs
    j = tr("?v a am:Vehicle . MINUS { ?v a am:ElectricVehicle }", "curiosity")
    assert '!(n.GetString(N.Vehicle.VehicleKind) == "ElectricVehicle")' in j["curiosity"], j["curiosity"]
    j = tr("?v a am:Vehicle . FILTER EXISTS { ?v a am:ElectricVehicle }", "curiosity")
    assert '.Where(n => n.GetString(N.Vehicle.VehicleKind) == "ElectricVehicle")' in j["curiosity"], j["curiosity"]
    # cible neo4j, sous-type disjoint : décidé par le type du nœud
    j = tr("?v a am:ElectricVehicle . FILTER EXISTS { ?v a am:CombustionVehicle }", "neo4j")
    assert j["curiosity"].count("StartAt(N.ElectricVehicle.Type)") == 1
    assert ".Where(n => false)  // aucun résultat (type du nœud)" in j["curiosity"], j["curiosity"]
    j = tr("?v a am:ElectricVehicle . FILTER NOT EXISTS { ?v a am:CombustionVehicle }", "neo4j")
    assert ".Where(" not in j["curiosity"], j["curiosity"]


def test_b12_neo4j_outer_type_is_not_changed_by_the_subpattern(tr):
    """Avant : le typage du sous-motif remplaçait le type extérieur (C# StartAt(ElectricVehicle) pour NOT EXISTS)."""
    j = tr("?v a am:Vehicle . FILTER NOT EXISTS { ?v a am:ElectricVehicle }", "neo4j")
    assert "ElectricVehicle.Type" not in (j["curiosity"] or "")
    assert any("[curiosity]" in n and "types multiples" in n for n in j["notes"]), j["notes"]


@pytest.mark.parametrize("target,cond", [
    ("neo4j", "EXISTS { MATCH (o)-[:CONCERNS]->(v) WHERE v:ElectricVehicle }"),
    ("curiosity", "EXISTS { MATCH (o)-[:CONCERNS]->(v) WHERE (v:Vehicle AND v.VehicleKind = 'ElectricVehicle') }"),
])
def test_b12_type_and_relation_in_subpattern(tr, target, cond):
    """Sous-motif avec un type et une relation (revue query L52) : la classe du sous-motif reste une condition."""
    j = tr("?o am:concerns ?v . FILTER EXISTS { ?o am:concerns ?v . ?v a am:ElectricVehicle }", target)
    assert _where(j) == cond, j["cypher"]
    assert not j["lossy"], j["notes"]  # ElectricVehicle porte le label Vehicle : pas de perte
    # revue curiosity it1 : l'EXISTS avec relation n'est pas traduit en C#, la sortie est donc marquée partielle
    assert "Traduction partielle" in j["curiosity"], j["curiosity"]


@pytest.mark.parametrize("target,prop", [("neo4j", "vin"), ("curiosity", "Vin")])
def test_b12_data_only_subpattern_is_anchored(tr, target, prop):
    """Sous-motif sans nouveau nœud (requête guidée « n'a pas de … ») : ancré sur le nœud extérieur, valeur exigée."""
    j = tr("?v a am:Vehicle . FILTER NOT EXISTS { ?v am:vin ?x }", target)
    assert _where(j) == f"NOT EXISTS {{ MATCH (v) WHERE v.{prop} IS NOT NULL }}", j["cypher"]
    j = tr('?v a am:Vehicle . FILTER NOT EXISTS { ?v am:vin ?x FILTER(CONTAINS(?x, "12o")) }', target)
    assert _where(j) == f"NOT EXISTS {{ MATCH (v) WHERE v.{prop} IS NOT NULL AND v.{prop} CONTAINS '12o' }}", j["cypher"]


@pytest.mark.parametrize("target", ["neo4j", "curiosity"])
def test_b12_absent_class_in_subpattern(tr, target):
    """Classe absente du PG dans le sous-motif : EXISTS faux ; sous NOT, jamais un résultat élargi (it2 : false aussi)."""
    j = tr("?v a am:Vehicle . FILTER EXISTS { ?v a am:NoSuchClass }", target)
    assert _where(j) == "false" and j["lossy"]
    for where in ("?v a am:Vehicle . FILTER NOT EXISTS { ?v a am:NoSuchClass }",
                  "?v a am:Vehicle . MINUS { ?v a am:NoSuchClass }",
                  "?o am:concerns ?v . FILTER NOT EXISTS { ?o am:concerns ?v . ?v a am:NoSuchClass }",
                  "?v a am:Vehicle . FILTER NOT EXISTS { ?o am:concerns ?v . ?o a am:NoSuchClass }",
                  "?v a am:Vehicle . FILTER NOT EXISTS { ?v am:noSuchProp ?x }"):
        j = tr(where, target)
        assert _where(j) == "false" and j["lossy"], (where, j["cypher"])


def test_b12_type_predicate_inside_an_expression(tr):
    j = tr('?v a am:Vehicle ; am:vin ?vin . FILTER(STRSTARTS(?vin, "VF") || NOT EXISTS { ?v a am:ElectricVehicle })',
           "neo4j")
    assert _where(j) == "(v.vin STARTS WITH 'VF' OR NOT v:ElectricVehicle)", j["cypher"]


def test_b12_generic_guard_refuses_an_empty_match():
    """Garde générique : un MATCH vide n'est jamais renvoyé (note [perte], supported=false)."""
    from ontoforge.core.pg_model import PGModel
    from ontoforge.queries import translate as T

    def broken(self, algebra):
        return "MATCH (v)\nWHERE EXISTS { MATCH  }\nRETURN v", {}
    mp = pytest.MonkeyPatch()
    mp.setattr(T._Translator, "run", broken)
    try:
        r = T.translate("SELECT ?v WHERE { ?v a <urn:x:C> }", PGModel(target="neo4j"))
    finally:
        mp.undo()
    assert r.cypher is None and not r.supported and r.lossy
    assert any(n.startswith("[perte]") and "MATCH sans motif" in n for n in r.notes), r.notes


def test_b12_subpattern_guard_without_translatable_pattern():
    """Sous-motif sans aucun nœud traduisible : condition false et note [perte], pas de MATCH vide."""
    from ontoforge.core.pg_model import PGModel
    from ontoforge.queries.translate import translate
    r = translate("SELECT ?v WHERE { ?v ?p ?o . FILTER EXISTS { ?a ?b ?c } }", PGModel(target="neo4j"))
    assert r.cypher is None or not EMPTY_MATCH.search(r.cypher), r.cypher
    assert r.lossy


@pytest.mark.parametrize("target", ["neo4j", "curiosity"])
def test_b12_csharp_untranslated_exists_is_partial(tr, target):
    """Revue curiosity it1 : un EXISTS / NOT EXISTS non traduit en Query API marque la sortie C# partielle."""
    j = tr("?v a am:RepairOrder . FILTER NOT EXISTS { ?v am:concerns ?x }", target)
    assert j["curiosity"] and "StartAt(N.RepairOrder.Type)" in j["curiosity"], j
    assert "Traduction partielle" in j["curiosity"], j["curiosity"]


def test_b12_guard_ignores_string_literals(tr):
    """Revue query it1 : la garde ne refuse plus un littéral qui contient « MATCH } »."""
    j = tr('?v a am:Vehicle ; am:vin ?vin . FILTER(?vin = "MATCH }")', "neo4j")
    assert j["supported"] and j["cypher"] and "'MATCH }'" in j["cypher"], j


# ---- DF-B14 : MINUS sans variable partagée n'exclut rien (SPARQL 1.1 §8.3.3)
@pytest.mark.parametrize("target", ["neo4j", "curiosity"])
def test_b14_minus_without_shared_variable_removes_nothing(tr, target):
    j = tr("?v a am:Vehicle . MINUS { ?o a am:RepairOrder }", target)
    assert "WHERE" not in j["cypher"] and "EXISTS" not in j["cypher"], j["cypher"]
    assert not j["lossy"] and any("§8.3.3" in n for n in j["notes"]), j["notes"]
    j = tr("?v a am:Vehicle . MINUS { ?v a am:ElectricVehicle }", target)  # variable partagée : exclusion gardée
    assert "NOT " in _where(j), j["cypher"]


# ---- DF-B15 : FILTER sur une variable d'OPTIONAL placé après l'OPTIONAL MATCH
@pytest.mark.parametrize("flt,cond", [
    ("FILTER(!BOUND(?v))", "NOT (v IS NOT NULL)"),
    # it3 (revue query it2) : ?v non liée → sous-motif évalué sur tout le graphe (§18.6) ; forme exacte, donc sans perte
    ("FILTER NOT EXISTS { ?v a am:ElectricVehicle }",
     "CASE WHEN v IS NULL THEN NOT EXISTS { MATCH (_any1) WHERE _any1:ElectricVehicle } ELSE NOT v:ElectricVehicle END"),
])
def test_b15_filter_on_optional_variable_comes_after_optional_match(tr, flt, cond):
    j = tr("?o a am:RepairOrder . OPTIONAL { ?o am:concerns ?v } " + flt, "neo4j")
    lines = j["cypher"].split("\n")
    assert lines[:4] == ["MATCH (o:RepairOrder)", "OPTIONAL MATCH (o)-[:CONCERNS]->(v:Vehicle)", "WITH *", f"WHERE {cond}"], lines
    assert not j["lossy"], j["notes"]


def test_b15_filter_on_main_variable_stays_in_first_where(tr):
    j = tr('?v a am:Vehicle ; am:vin ?vin . OPTIONAL { ?o am:concerns ?v } FILTER(?vin = "X")', "neo4j")
    lines = j["cypher"].split("\n")
    assert lines[1] == "WHERE v.vin = 'X'" and "WITH *" not in lines, lines


# ---- it3 (revues query et curiosity it2) : sous-motif sur une variable d'OPTIONAL non liée
OPT = "?o a am:RepairOrder . OPTIONAL { ?o am:concerns ?v } "
CUR_EV_ANY = "(_any1:Vehicle AND _any1.VehicleKind = 'ElectricVehicle')"


def _post_where(j):
    lines = j["cypher"].split("\n")
    assert lines[1].startswith("OPTIONAL MATCH") and lines[2] == "WITH *", lines
    return lines[3][len("WHERE "):]


@pytest.mark.parametrize("target,sub,cond", [
    # MINUS : domaines disjoints quand ?v n'est pas liée → ligne gardée (§18.5)
    ("neo4j", "MINUS { ?v a am:ElectricVehicle }", "(v IS NULL OR NOT v:ElectricVehicle)"),
    ("curiosity", "MINUS { ?v a am:ElectricVehicle }", "(v IS NULL OR NOT " + CUR_EV + ")"),
    # EXISTS / NOT EXISTS : ?v non liée → sur tout le graphe (§18.6)
    ("neo4j", "FILTER NOT EXISTS { ?v a am:ElectricVehicle }",
     "CASE WHEN v IS NULL THEN NOT EXISTS { MATCH (_any1) WHERE _any1:ElectricVehicle } ELSE NOT v:ElectricVehicle END"),
    ("curiosity", "FILTER NOT EXISTS { ?v a am:ElectricVehicle }",
     f"CASE WHEN v IS NULL THEN NOT EXISTS {{ MATCH (_any1) WHERE {CUR_EV_ANY} }} ELSE NOT {CUR_EV} END"),
    ("neo4j", "FILTER EXISTS { ?v a am:ElectricVehicle }",
     "CASE WHEN v IS NULL THEN EXISTS { MATCH (_any1) WHERE _any1:ElectricVehicle } ELSE v:ElectricVehicle END"),
    ("curiosity", "FILTER EXISTS { ?v a am:ElectricVehicle }",
     f"CASE WHEN v IS NULL THEN EXISTS {{ MATCH (_any1) WHERE {CUR_EV_ANY} }} ELSE {CUR_EV} END"),
])
def test_it3_subpattern_on_unbound_optional_variable_is_exact(tr, target, sub, cond):
    j = tr(OPT + sub, target)
    assert _post_where(j) == cond, j["cypher"]
    assert not j["lossy"], j["notes"]


@pytest.mark.parametrize("target", ["neo4j", "curiosity"])
@pytest.mark.parametrize("sub", ["FILTER NOT EXISTS { ?v am:vin ?x }", "FILTER EXISTS { ?o am:concerns ?v . ?v am:vin ?x }",
                                 "MINUS { ?o am:concerns ?v . ?v a am:ElectricVehicle }"])
def test_it3_subpattern_on_optional_variable_without_exact_form_is_a_loss(tr, target, sub):
    j = tr(OPT + sub, target)
    assert j["lossy"] and any(n.startswith("[perte]") and "OPTIONAL" in n for n in j["notes"]), j["notes"]
    assert not EMPTY_MATCH.search(j["cypher"]), j["cypher"]


def test_it3_csharp_filter_on_optional_node_marks_partial(tr):
    """Revue curiosity it2 : le filtre C# sur ?v (OPTIONAL, hors traversée) n'est pas écrit → sortie partielle + note."""
    for sub in ("FILTER NOT EXISTS { ?v a am:ElectricVehicle }", "MINUS { ?v a am:ElectricVehicle }",
                "FILTER EXISTS { ?v a am:ElectricVehicle }"):
        j = tr(OPT + sub, "curiosity")
        assert "Traduction partielle" in j["curiosity"], (sub, j["curiosity"])
        assert any(n.startswith("[curiosity] Filtre sur ?v") for n in j["notes"]), j["notes"]
    j = tr(OPT + "MINUS { ?v a am:ElectricVehicle }", "neo4j")  # neo4j : sous-type, le type seul ne tranche pas
    assert "Traduction partielle" in j["curiosity"], j["curiosity"]


# ---- DF-B18 : OPTIONAL ou BIND d'un sous-motif ne débordent pas dans la requête principale
@pytest.mark.parametrize("target", ["neo4j", "curiosity"])
def test_b18_optional_inside_subpattern_stays_inside(tr, target):
    j = tr("?v a am:Vehicle . FILTER NOT EXISTS { ?o a am:RepairOrder OPTIONAL { ?o am:concerns ?v } }", target)
    assert "OPTIONAL MATCH" not in j["cypher"], j["cypher"]
    assert not j["lossy"], j["notes"]  # OPTIONAL sans effet sur l'existence : exact
    j = tr("?v a am:Vehicle . MINUS { ?o a am:RepairOrder OPTIONAL { ?o am:concerns ?v } }", target)
    assert "OPTIONAL MATCH" not in j["cypher"], j["cypher"]
    assert j["lossy"] and any("OPTIONAL dans un MINUS" in n for n in j["notes"]), j["notes"]


@pytest.mark.parametrize("target", ["neo4j", "curiosity"])
def test_b18_bind_inside_subpattern_stays_inside(tr, target):
    j = tr("?v a am:Vehicle . MINUS { ?o a am:RepairOrder BIND(?o AS ?v) }", target)
    assert "o AS v" not in j["cypher"] and j["lossy"], (j["cypher"], j["notes"])
    # BIND local, sur une variable propre au sous-motif : traduit dans le sous-motif, rien ne déborde
    j = tr('?v a am:Vehicle ; am:vin ?vin . FILTER EXISTS { ?o am:concerns ?v BIND("X" AS ?k) FILTER(?vin != ?k) }', target)
    prop = "vin" if target == "neo4j" else "Vin"
    assert _where(j) == f"EXISTS {{ MATCH (o:RepairOrder)-[:CONCERNS]->(v) WHERE v.{prop} <> 'X' }}", j["cypher"]
    assert "k" not in j["cypher"].split("RETURN ")[1], j["cypher"]


@pytest.mark.parametrize("target", ["neo4j", "curiosity"])
def test_b18_subpattern_variables_do_not_leak_into_projection(tr, target):
    """Variable propre au sous-motif : hors de portée (§18.2.1) → aucune colonne avec SELECT * (finitions L53) ;
    null + [info] seulement si elle est nommée dans le SELECT. Avant L53 : `o.uri AS o`, o non défini."""
    where = "?v a am:Vehicle FILTER NOT EXISTS { ?o am:concerns ?v . ?v am:vin ?x }"
    j = tr(where, target, select="*")
    ret = j["cypher"].split("RETURN ")[1]
    assert ret in ("v.uri AS v", "v.Uri AS v"), j["cypher"]
    assert not j["lossy"] and any("§18.2.1" in n for n in j["notes"]), j["notes"]
    j = tr(where, target, select="?v ?o")
    assert j["cypher"].split("RETURN ")[1].endswith("null AS o"), j["cypher"]
    assert not j["lossy"] and any("comme en SPARQL" in n for n in j["notes"]), j["notes"]


@pytest.mark.parametrize("target", ["neo4j", "curiosity"])
def test_finish_variable_of_ignored_optional_in_exists_is_info(tr, target):
    """?w d'un OPTIONAL ignoré dans un EXISTS : propre au sous-motif, null exact → [info], pas [perte]."""
    j = tr("?v a am:Vehicle . FILTER EXISTS { ?o am:concerns ?v OPTIONAL { ?o am:concerns ?w } }", target, select="?v ?w")
    assert j["cypher"].split("RETURN ")[1].endswith("null AS w"), j["cypher"]
    assert not j["lossy"], j["notes"]


@pytest.mark.parametrize("target", ["neo4j", "curiosity"])
def test_finish_untranslated_filter_marks_csharp_partial(tr, target):
    """Branche générique « FILTER non traduit en Query API » : sortie C# partielle (finitions L53)."""
    j = tr("?o a am:RepairOrder . OPTIONAL { ?o am:concerns ?v } FILTER(!BOUND(?v))", target, select="?o")
    assert j["curiosity"] and "StartAt(N.RepairOrder.Type)" in j["curiosity"], j
    assert "Traduction partielle" in j["curiosity"], j["curiosity"]
