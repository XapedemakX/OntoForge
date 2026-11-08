# L19 : corrections après relecture it1 (agent query)

## Bloquant : union dédupliquée (w3c bloquant 1, query bloquant 1) : CORRIGÉ
- `store.rebuild_union()` : après chaque écriture (`_with_store` en lecture-écriture : chargement, vidage, inférence, synchronisation de l'ontologie), le graphe par défaut est vidé puis reconstruit depuis tous les graphes nommés, par blocs de 50 000 quads ; le magasin est un ensemble par graphe, la déduplication est donc gratuite.
- `use_default_graph_as_union` n'est plus utilisé (`_worker.run_query`). Sans `FROM`, la requête lit le graphe par défaut tel quel.
- `FROM` / `FROM NAMED` : `runner.dataset_clause()` extrait les IRI (rdflib) ; le fils passe `default_graph=` / `named_graphs=` à Oxigraph (mesuré : ils remplacent les clauses du texte). Un seul `FROM` : lu en place. Plusieurs `FROM` : fusion dans un magasin mémoire temporaire (ensemble), `FROM NAMED` copiés aussi. Sans `FROM NAMED`, `GRAPH ?g` ne rend rien (§13.2). Choix retenu plutôt que réécrire la requête : aucune manipulation du texte SPARQL.
- `GRAPH ?g` voit toujours les graphes nommés. Statistiques : le total et le contrôle de plafond excluent le graphe par défaut (`_total`) ; comptes par graphe vérifiés par test (`by[a] == by[b] == 1`, total = somme).
- Test inversé et étendu : `test_union_is_a_deduplicated_set` (COUNT = 1, GRAPH ?g = 2, FROM multiples = 1, FROM seul sans GRAPH, statistiques, remplacement d'un fichier).

### Mesures (jeu ×50 : 186 166 triplets distincts, deux graphes, machine 2 cœurs)
| | avant (option d'union) | après (union matérialisée) |
|---|---|---|
| chargement | 3,2 s | 3,6 s + reconstruction de l'union 4,0 s (≈ 7,6 s au total) |
| quads / disque | 186 k / 137 Mo | 372 k / 220 Mo (+60 %, base RocksDB brute avant compaction) |
| COUNT(*) | 68 ms | 35 ms |
| DISTINCT ?p (Part) | 45 ms | 31 ms |
| GROUP BY ?s ORDER BY | 111 ms | 62 ms |
| mémoire (pic RSS de la reconstruction) | — | +0 Mo mesuré (lecture par blocs, pas de copie en Python) |
Lecture : les requêtes sont plus rapides (plus de multi-ensemble à agréger) ; le coût est à l'écriture (≈ 4 s pour 186 k triplets, soit 20 s par million, plus que les « 1 s » estimées en revue) et en disque. Il est payé à chaque écriture, même sans changement. Piste non faite : reconstruction incrémentale (ajouter / retirer le seul graphe modifié ne suffit pas à cause des doublons entre graphes).

## Non-bloquants traités
- Verrou à la suppression du projet : `localstore.store.drop()` (vide sous le verrou d'écriture puis oublie l'entrée de `_LOCKS`), appelé par `DELETE /projects/{id}`. Test `test_project_deletion_drops_store_and_lock`.
- Précisions : CONTRACTS §6.1 (union dédupliquée, FROM, écart avec un endpoint externe, RDFS contre OWL RL, DESCRIBE, `.owl`, sameAs et incohérences) et guide §11 (même contenu, plus hasKey par GROUP BY / HAVING). Décision D-L19-01 dans `journal/decisions.md`.
- Analyse en flux : `parse_to_store` utilise `ox.parse` par blocs de 20 000 et s'arrête au plafond de triplets (413 « analyse interrompue ») ; le Turtle compact à des millions de quads n'est plus matérialisé. Test `test_parse_stops_at_triple_cap`. Reste : Starlette reçoit le corps entier sur disque (nginx `client_max_body_size` à prévoir) et `raw` reste en mémoire (≤ 25 Mo).

## Non traité (hors demande)
Troncature des IRI à 4 000 caractères, `.owl` non RDF/XML, `base_iri` des IRI relatives, individus anonymes : inchangés. Mises à jour de skills (w3c, graph-query-translation) laissées aux relecteurs.

## Gardes
pytest 744 verts, `node tools/recette/l19_local_store.mjs` 9/9, front non touché.
