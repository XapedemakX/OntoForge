"""Processus fils des requêtes du triplestore local (L19) : isolé, lecture seule, tuable.

Lancé par `ontoforge.localstore.runner` avec `python -I _worker.py` : n'importe que pyoxigraph (aucun module OntoForge, aucun
réseau côté Python). Entrée JSON sur stdin `{path, query, limit, cell_chars}`, sortie JSON sur stdout. La base est ouverte
en LECTURE SEULE (`Store.read_only`) : même une requête qui échapperait aux contrôles amont ne pourrait rien écrire.
"""
import itertools
import json
import sys

import pyoxigraph as ox

XSD_STRING = "http://www.w3.org/2001/XMLSchema#string"
LANG_STRING = "http://www.w3.org/1999/02/22-rdf-syntax-ns#langString"


def cell(t, cap):
    if isinstance(t, ox.NamedNode):
        return {"type": "uri", "value": t.value[:cap]}
    if isinstance(t, ox.BlankNode):
        return {"type": "bnode", "value": t.value}
    if isinstance(t, ox.Literal):
        d = {"type": "literal", "value": t.value[:cap]}
        if t.language:
            d["xml:lang"] = t.language
        elif t.datatype.value not in (XSD_STRING, LANG_STRING):
            d["datatype"] = t.datatype.value
        return d
    return {"type": "literal", "value": str(t)[:cap]}  # triplet cité (RDF-star) : représentation texte


def run_query(store, query, dataset):
    """Sans `FROM` : le graphe par défaut du magasin est déjà l'union dédupliquée des graphes nommés (matérialisée à l'écriture).
    Avec `FROM` / `FROM NAMED` : jeu de données de la requête (§13.2) ; un seul `FROM` se lit en place, plusieurs sont fusionnés
    dans un magasin mémoire temporaire pour que le graphe par défaut reste un ensemble (§13.1)."""
    if not dataset:
        return store.query(query)
    default = [ox.NamedNode(g) for g in dataset["default"]]
    named = [ox.NamedNode(g) for g in dataset["named"]]
    if len(default) <= 1:
        return store.query(query, default_graph=default, named_graphs=named)
    tmp = ox.Store()
    d = ox.DefaultGraph()
    for g in default:
        tmp.bulk_extend(ox.Quad(q.subject, q.predicate, q.object, d) for q in store.quads_for_pattern(None, None, None, g))
    for g in named:
        tmp.bulk_extend(ox.Quad(q.subject, q.predicate, q.object, g) for q in store.quads_for_pattern(None, None, None, g))
    return tmp.query(query, default_graph=[d], named_graphs=named)


def main() -> None:
    req = json.loads(sys.stdin.read())
    limit, cap = int(req["limit"]), int(req.get("cell_chars", 4000))
    try:
        store = ox.Store.read_only(req["path"])
        res = run_query(store, req["query"], req.get("dataset"))
    except SyntaxError as exc:
        print(json.dumps({"error": "syntax", "message": str(exc)[:300]}))
        return
    except OSError as exc:
        print(json.dumps({"error": "io", "message": str(exc)[:300]}))
        return
    if isinstance(res, ox.QueryBoolean):
        print(json.dumps({"form": "ASK", "boolean": bool(res)}))
        return
    if isinstance(res, ox.QuerySolutions):
        cols = [v.value for v in res.variables]
        rows = []
        for sol in itertools.islice(res, limit + 1):
            rows.append({c: (cell(sol[c], cap) if sol[c] is not None else None) for c in cols})
        form = "SELECT"
    else:  # CONSTRUCT / DESCRIBE : triplets s, p, o
        cols = ["s", "p", "o"]
        rows = [{"s": cell(t.subject, cap), "p": cell(t.predicate, cap), "o": cell(t.object, cap)}
                for t in itertools.islice(res, limit + 1)]
        form = "CONSTRUCT"
    print(json.dumps({"form": form, "columns": cols, "rows": rows[:limit], "truncated": len(rows) > limit}))


main()
