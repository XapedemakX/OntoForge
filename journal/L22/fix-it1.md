# L22 — corrections, itération 1

Réponse point par point aux revues w3c, shacl et scout. pytest 672 verts, build vert, `l22_files.mjs` 23/23 (captures relues : 01, 02, 02b, 03, 04), `e2e_ui.mjs` 30/30, `english_scan.mjs` 0 français.

## Bloquants

### 1. Commentaires (w3c, scout)
**Choix : conserver le texte saisi** (et non seulement avertir), avec repli sur le canonique.
- Le texte Turtle appliqué est stocké dans `editor-sources.json` du projet, avec l'etag du texte canonique du modèle au moment de l'application. À la lecture, on le sert tant que cet etag est celui du canonique courant. Le canonique étant déterministe, même etag veut dire graphes isomorphes : l'invariant « on ne sert le texte source que s'il est isomorphe au graphe du projet » est vérifié sans réanalyse.
- À l'application, le texte n'est conservé que si son graphe est isomorphe au graphe canonique résultant (`rewritten == 0`). Sinon (AllDisjointClasses éclaté, `rdf:Property` retypée…), on écrit le canonique et les commentaires sont réellement perdus.
- Modification venue d'un autre écran ou annulation vers un autre état : le canonique change, on sert le canonique, avec une note dans l'éditeur (« …affiché sous forme normalisée, N ligne(s) de commentaire supprimées »).
- Aperçu : avertissement visible (`role=alert`) « N ligne(s) de commentaire seront supprimées à l'application » quand la perte est réelle, avec le mot « supprimées ». Quand le texte est conservé : « Vos N lignes de commentaire sont conservées », et une note sous le diff qui dit à quelle condition (l'ancien texte « normalisé » est retiré). Le diff compare maintenant l'état actuel au texte réellement obtenu : l'utilisateur voit ses commentaires disparaître dans le cas où ils disparaissent.
- Pourquoi ce choix : c'est faisable proprement (un fichier, une comparaison d'etag), il évite la perte silencieuse dans le cas courant et il règle aussi la remarque w3c sur les textes sans `@prefix` (le texte saisi est servi tel quel).
- Conséquence : un texte qui ne change que la forme (commentaires, ordre) est enregistré sans toucher au modèle ni à l'historique `/ops` (pas d'annulation possible pour ce cas). `test_diff_ignores_blank_node_labels_and_order` est adapté : `changed` est vrai (le texte change), 0 / 0 triplet, 0 réécriture.
- Limite : un commentaire à l'intérieur d'une chaîne multiligne `"""` n'est pas distingué dans le comptage.

### 2. Compteur +N / −M
`summary.rewritten` = `graph_diff(graphe du texte saisi, graphe canonique résultant)` : `count` (triplets de votre texte réécrits), `added`, échantillons `from` / `to`. Affiché dans l'aperçu : « N triplet(s) de votre texte réécrits de façon équivalente à l'import », détail dépliable, **déplié d'office** quand N > 0 (scout). Cas « 0 / 0 » : message « Aucun triplet ne change : seul le texte est enregistré ». Les échantillons +N / −M (déjà dans la réponse) sont aussi dépliables (scout). Le libellé « équivalente » repose sur les équivalences vérifiées par la revue w3c (tableaux 1 et 2 du mapping) ; l'utilisateur voit le détail avant / après pour en juger.

### 3. Préfixes perdus
Cause trouvée : à la création d'un projet depuis un exemple, `samples.describe` triait les fichiers par nom et `api/projects.py` prend `ontology[:1]`, donc `automaint.owl` (RDF/XML, sans préfixe `am:`) passait avant `automaint.ttl`. Ni l'import (`collect_prefixes` conserve bien `am:` depuis le Turtle), ni le stockage, ni la sérialisation n'étaient en cause.
- `samples.py` : à rôle égal, les `.ttl` passent en premier.
- Filet de sécurité générique (scout) : `canonical_turtle` lie un préfixe à l'espace de noms dominant des entités s'il n'en a aucun, dérivé de l'IRI d'ontologie (`automaint:`), sinon `onto:`, sans jamais écraser un préfixe déclaré (RDF/XML sans préfixe, import futur).
- Vérifié : onto.ttl (2 IRI complètes au lieu de 226), shapes.ttl (`am:` et `ams:`), export Turtle de l'ontologie et des shapes. Tests : `test_sample_keeps_source_prefixes_in_all_views`, `test_prefixless_source_gets_a_derived_prefix` (`tests/test_files_editor_fix_it1.py`) ; contrôle dans `l22_files.mjs`.

## Non-bloquants
- **Messages pySHACL** : traduits par famille (type de donnée, nature de nœud, cardinalités, xone NodeShape/PropertyShape, liste RDF), message brut gardé dans `detail`, dédoublonnage (la cascade ListShape / ListNodeShape / hasValue / or donne un seul constat sur `sh:in`). Fait.
- **NodeShape portant sh:path** : contrôle maison `shacl-nodeshape-path` (avertissement). Fait.
- **Limite du corps HTTP** : 8 Mo sur les routes `/files` (Content-Length, puis comptage des octets reçus pour les corps en morceaux), réponse 413. Fait.
- Fait par effet de bord : texte sans `@prefix` (w3c), point « . » manquant et autres diagnostics non touchés.
- **Non traités** (hors périmètre simple, notés) : action rapide « Déclarer le préfixe » (scout), position du « point attendu » en fin de ligne précédente, jeton fautif des étiquettes de langue invalides, IRI relative résolue par `@base` dans `Locator`, normalisation des formes lexicales numériques (à dire dans le guide), message d'import des sévérités littérales et `sh:maxCount -1` (propriétaire : import shapes), étape « Fichiers » de la visite (décision du chef).
- **Refusé volontairement** : IRI relative dans `io/rdf_import.py`, laissée pour un lot d'import comme demandé.
