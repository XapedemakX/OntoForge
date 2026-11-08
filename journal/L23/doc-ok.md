# L23 : vérification du documentaliste (seconde passe de l'humaniseur)

Agent : doc. Périmètre : les diffs de `0123c40` à la fin de la seconde passe, sur 12 fichiers (utilisateur.md, CONTRACTS.md, api.md, CHANGELOG.md, trois fiches de veille, rapports L19, L20, L21, L22, L25). Critère unique : aucun fait n'a bougé.

verdict: OK

Contrôles faits
- Blocs de code, code en ligne, liens, nombres, nombre de lignes de tableau et occurrences de `À VÉRIFIER` : identiques avant et après sur les 12 fichiers.
- CONTRACTS.md : toutes les lignes de tableau sont identiques caractère pour caractère.
- Comparaison des mots (sans ponctuation ni gras, hors ordre) : seuls écarts, dans utilisateur.md, l'intro réécrite (« est organisée autour du », « avec » remplacés par « suit », « comporte ») et la phrase « C'est le cœur de l'outil » supprimée ; dans les veilles, un « et » déplacé ou remplacé pour couper une phrase. Aucun nom, valeur, commande, décision ou chemin touché.
- Relecture des remplacements sensibles : les parenthèses de CONTRACTS §5 « Validations » (propriétés non simples, datatypes hors carte) ont gardé la même portée ; « Diagnostics. `onto.ttl` : » ouvre toujours la liste des diagnostics `onto.ttl` / `shapes.ttl` / `decisions.json` ; le paragraphe sur l'union dans triplestore-embarque.md garde ses mesures (186 000 triplets, 4 s, +60 %, 35 ms contre 68 ms).
- Guide utilisateur : la section « Easter egg » est inchangée et ne révèle ni le code ni la séquence (indice dans Paramètres, sans plus).

Constats
- api.md ne décrit aucune route de L19 (`/store/*`), L22 (`/files`) ni L25 (`/assistant/document/*`). Elles ne sont documentées que dans CONTRACTS §6.1, §8 et §9. Écart de contenu, pas de style : hors du travail de l'humaniseur, à confier au documentaliste (lot suivant).
- Pas de changement de sens à signaler. Les titres avec tiret long et les cellules « - » des tableaux sont laissés exprès.
