# L19 : triplestore local embarqué (agent query)

Verdict : faisable proprement, moteur retenu pyoxigraph 0.5.13 (épinglé dans `backend/pyproject.toml`, installé par le Dockerfile, aucune autre version touchée, D-L21-02). Évaluation chiffrée : `docs/veille/triplestore-embarque.md`.

## Chiffres clés (mesurés)
- Requête guidée Diesel, ×50 (207 k triplets) : rdflib 42 s, Oxigraph 1 ms ; chargement ×50 : 5,3 s contre 0,8 s ; mémoire 237 Mo contre 144 Mo.
- Prototype de bout en bout : 55 à 185 ms par requête (processus fils compris), 10 lignes Diesel sur les données de démo.
- owlrl : 1,6 s (RDFS) / 2,9 s (OWL RL) sur 4,7 k triplets, linéaire ; `owl:hasKey` rend OWL RL inutilisable (plus de 10 min), retiré et signalé.
- Non mesuré : Fuseki et tailles d'image Docker (réseau et registres bloqués dans le bac à sable), marqués À VÉRIFIER.

## Livré
- `backend/ontoforge/localstore/` (store, runner, deux processus fils), `api/local_store.py` : `POST /store/load`, `GET /store/stats`, `DELETE /store`, `POST /store/validate` (SHACL) ; `endpoint: {kind:"local"}` dans `/query/run` et `/query/values` ; `local=true` dans `/query/options`.
- Persistance : `projects/<id>/triplestore/` (volume Docker), supprimée avec le projet ; resynchronisation de la TBox quand l'ontologie change.
- Écran Requêtes : option « Triplestore local (test) », panneau (compte de triplets par origine, démo, fichier, inférence RDFS / OWL RL / les deux, SHACL, vider, actualiser). i18n fr + en, messages serveur traduits (`localize/phrases.py`).
- Tests : `backend/tests/test_local_store.py` (24 tests), `tools/recette/l19_local_store.mjs` (9/9, captures dans `journal/L19/screens/`). Gardes : pytest 612 verts, build vert, `e2e_ui.mjs` 30/30.
- Docs : CONTRACTS §6.1, guide utilisateur §11.

## Points d'attention pour les relecteurs
- w3c : choix des faits matérialisés (`_infer_worker.py:useful`), retrait de `owl:hasKey`, séparation TBox / individus / données / inféré en graphes nommés, union comme graphe par défaut, individus = triplets dont le sujet est un individu de l'éditeur, JSON-LD refusé si contexte distant.
- query (relecture croisée) : `SERVICE` détecté dans l'algèbre rdflib + filet lexical (pas de faux positif sur un littéral « service », testé) ; LIMIT forcé identique à §6 ; `DESCRIBE` renvoie des colonnes s, p, o.
- scout : libellés du panneau, case Inférence + choix du type, message de plafond.
- Pièges rencontrés : RocksDB reste verrouillé tant qu'une référence à l'objet survit (traceback d'exception compris) ; `updated_at` n'a qu'une résolution d'une seconde (empreinte de l'ontologie utilisée à la place) ; l'identifiant `local` n'est pas réservé (un endpoint enregistré peut le porter).
- Pendant le lot, `frontend/src/i18n/fr.json` a été vidé par une écriture concurrente d'un autre agent : restauré depuis HEAD avec les clés `q.local.*` et les clés de en.json absentes. Vérifier qu'aucune clé française récente d'un autre lot n'a été perdue.
- Hors périmètre : un seul processus serveur (verrou en mémoire) ; pas d'UPDATE ; données non versionnées avec le projet.

Relecture demandée : W3C (puis query, scout, doc selon la matrice de docs/TEAM.md).
