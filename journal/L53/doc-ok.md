# L53 : doc-ok

verdict: OK (documentaliste, 24/11/2026, branche `integration/L53`, après fusion de `lot/L53-b12` et `lot/L53-b13`)

## Ce qui a été vérifié

- **Valeurs Cloud Run.** `deploy/cloudrun/env.yaml` relu variable par variable, somme refaite : 175 + 320 + 256 + 342 + 640 + 124 + 64 + 12 = **1933 Mo**, marge **115 Mo** sous 2048. Mêmes valeurs dans `deploy/cloudrun/README.md`, `docs/dev` chapitres 06, 10, 16, 17 (fr, en) et le CHANGELOG fr / en : 640 (fils du triplestore), 12 Mo (corps de requête), 64 Mo (disque), purge 30 min, 50 000 triplets et 5 Mo (chargement), 124 (chargement), 175 (serveur), 342 (HermiT). Défauts du code relus dans `localstore/store.py` et `security.py` (places 2, chargements 4, plafond de corps 32, triplets 1 000 000, fichier 25 Mo, mémoire 3072) : le manuel les donne comme défauts, avec la valeur Cloud Run entre parenthèses. Aucune trace des anciennes valeurs (1985, 704, 63 Mo, 1861) hors des journaux d'itération, qui les citent comme historique.
- **Parité fr / en.** Chapitres 05, 06, 09, 10, 16, 17 : même nombre de lignes, de titres et de lignes de tableau dans les deux langues. CHANGELOG fr / en : même liste de points.
- **Liens et ancres.** `tests/test_dev_docs.py` : 195 verts. Avec `test_docs_bilingual.py`, `test_help_map.py` et `test_l53_b13.py` : 252 verts. Aucune référence extérieure aux anciennes ancres des deux sections L53 du CHANGELOG.
- **Statuts de `journal/L51/defauts.md`.** DF-B12, B13, B14, B15, B17 et B18 « corrigé L53 » avec renvoi vers `corrections-b12.md` ou `corrections-b13.md` ; DF-B16 « ouvert, lot à venir ». Les ancres cibles existent. Cohérent avec le chapitre 09 (DF-B16 ouvert, B17 corrigé).
- **README de `docs/dev`.** Les sept points `À CONFIRMER` ne sont pas concernés par L53 et restent ouverts. Aucun point nouveau.
- **Journaux du lot.** `corrections-b12.md` et `corrections-b13.md` : chaque défaut a Problème, Correction, Résultat, Reste ; tests cités présents (`test_l53_b12.py`, `test_l53_b13.py`, `test_l53_b17.py`).

## Corrections de la doc (aucun code touché)

- CHANGELOG fr et en : les deux sections L53 (parties DF-B12 et DF-B13) fusionnées en une seule, titre et ancre nouveaux (`#l53-corrections-24-nov-2026`), introduction commune (défauts traités, DF-B16 ouvert, renvois), tous les points conservés, ligne « Développeurs » unique.
- `docs/guide/utilisateur.md` et `.en.md` : la section du triplestore local donnait 25 Mo et un contenu « conservé entre deux sessions » sans dire que la démo en ligne a des limites plus basses. Ajouté : 5 Mo, 50 000 triplets, 64 Mo au total (413), purge après 30 minutes d'inactivité, 503 si occupé. Mentionné dans le CHANGELOG.
- `docs/dev/09-requetes.md` et `.en.md` : limite connue ajoutée, ordre des colonnes de `SELECT *` non déterministe (relevé par la revue query it3, présent avant L53).
- `docs/dev/README.md` et `.en.md` : la référence aux défauts dit maintenant « corrigés en L52 et L53 » et signale DF-B16 ouvert.
- Créé : `journal/L53/corrections.md` (synthèse pour Jerem).

## Points laissés

- Le C# cosmétique des éléments absents sous négation et les limites de disponibilité des chargements sont décrits dans `journal/L53/corrections.md` et pour la seconde au chapitre 10 ; le premier n'a pas de ligne dans le manuel (revues curiosity, sortie marquée partielle).
- Aucune commande gcloud ni base Neo4j n'a été essayée : les points À VÉRIFIER sont listés dans `corrections.md`, section « Ce que Jerem doit faire ».
- Rien tiré de `journal/securite/` dans les documents publics ; DF-B13 est décrit sans détail d'exploitation, sans nom de client.
- Passage de l'humaniseur sur la doc du lot : à faire avant le push.
