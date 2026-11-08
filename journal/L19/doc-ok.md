# L19 : vérification documentaire (it2)
Vérifié contre le code et les tests (backend/ontoforge/localstore/, tests/test_local_store*.py, 753 tests verts) :
- docs/guide/utilisateur.md §11 : union sans doublon, FROM, GRAPH ?g, écart avec un endpoint externe, délai 20 s, plafond d'inférence 30 000, hasKey : exacts. Ajout : attente de la reconstruction de l'union (environ 4 s pour 186 000 triplets) et chargement annulé en cas d'échec.
- docs/CONTRACTS.md §6.1 : conforme. Ajout : coût chiffré, reconstruction sous verrou (jamais d'union périmée ou partielle), chargement tout ou rien.
- docs/veille/triplestore-embarque.md : écart corrigé (« l'unicité des clés se vérifie avec SHACL » est faux, prp-key déduit sameAs) ; ajout du coût de l'union, les mesures du tableau précèdent D-L19-01.
- Décision D-L19-01 : conforme au code (rebuild_union, dataset_clause, fusion des FROM multiples).
- CHANGELOG 0.3.0 : « en correction » remplacé par une ligne finale.
Reste pour l'humaniseur : passe de style sur ces sections.
