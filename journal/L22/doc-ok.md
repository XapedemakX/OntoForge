# L22 — doc-ok

Section « Éditeur de fichiers » de `docs/guide/utilisateur.md` et `docs/CONTRACTS.md` §8 relues contre le code (`editing/files.py`, `api/files.py`, écran Fichiers) et corrigées :
- texte saisi conservé (`editor-sources.json`, etag canonique, champ `source`), préfixe de repli ;
- `summary.rewritten`, `comment_lines`, `source_kept`, `comments_lost` ; changement de texte seul sans entrée d'historique ;
- limite 8 Mo (413), diagnostics `turtle-relative-iri`, `turtle-bad-iri`, `ill-typed-literal`, `shacl-nodeshape-path`.
Verdicts it2 : w3c OK, scout OK. Reste pour la clôture : passe de l'humaniseur sur ces deux textes (matrice du 7/11).
