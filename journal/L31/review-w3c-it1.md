verdict: OK
bloquants:
  - aucun (après la correction ci-dessous)
non-bloquants:
  - [standards.json shacl] L'identifiant « 1.0 » (REC du 20/07/2017) est exact. La note disait « parfois appelée 1.1 », ce qui entretenait une version inexistante. Corrigé (fr et en) : « SHACL 1.1 n'existe pas officiellement » ; la valeur 1.1 reste lue comme synonyme de 1.0 par tolérance (`aliases`, jamais affichée comme version). Guide et CHANGELOG alignés.
  - [statuts] RDF 1.2 = CR (7/04/2026), SPARQL 1.2 = WD (1/11/2026), SHACL 1.2 Core = WD (2/11/2026) : identiques à docs/veille/normes.md. RDF 1.1 REC 2014-02-25, SPARQL 1.1 REC 2013-03-21, OWL 2 REC 2012-12-11 exacts. Dates non relues en ligne aujourd'hui.
  - [construction 1.2] Aucune n'est émise : `shacl_header` n'écrit qu'un commentaire ; les six fonctions 1.2 ont `implemented: false`. test_shacl_features_are_marked_and_disabled_in_1_0 couvre l'export.
skill: w3c-ontology-conformance : ne jamais afficher « SHACL 1.1 » comme version.
Corrections faites : notes SHACL (standards.json), guide, CHANGELOG.
Robustesse (agent.py reconstruit) : nouveau backend/tests/test_assistant_intents.py (28 cas fr + en : classe, propriété, obligatoire, suppression, contrainte, recherche, shapes, aide, raisonner, versions, mise à jour, actions LLM invalides). Bogue trouvé et corrigé : « help » seul recevait une réponse en français (agent.py `_EN_WORDS`).
