verdict: OK
bloquants:
non-bloquants:
  - security.py : `SecurityHeaders` ne conserve la CSP de la réponse que si elle est égale à `STRICT_CSP` (comparaison d'octets, plus de préfixe) ; `justification.CSP` importe la même constante : plus de dérive possible. Tests test_security* et test_l47_justification verts.
  - POST /decisions/{target}/branch : avec `option`, une décision d'un autre compte ou sans auteur connu (ancien format, `note is None`) n'est remplacée que si `overwrite: true` ; sinon `skipped`. Le front n'envoie `overwrite` que sur « Imposer ». Route toujours classée écriture (test_routes_classees), lecteur refusé. Le contrôle est côté serveur, pas seulement dans l'écran : OK. Réserve : `overwrite` est un simple booléen du client, sans second geste côté serveur ; acceptable (même droit d'écriture que l'ancienne décision).
  - Markdown : `://` est échappé (`:\/\/`) : les URL en `http(s)://` ne deviennent plus des liens. Les autolinks GFM `www.exemple.fr` et les adresses `a@b.fr` restent cliquables dans un rendu Markdown (vérifié : `_md("www.evil.com et a@b.fr")` renvoie le texte tel quel). Les textes viennent de l'ontologie et des raisons saisies ; risque faible (lien, pas d'exécution) ; neutraliser `www.` et `@` si on veut une garantie complète.
  - Toujours à décider (signalé en it1) : le login d'un administrateur `as_admin` visible des lecteurs dans les traces du dossier.
skill: audit-securite-cve-cwe : une politique de réponse « resserrable » se compare à égalité avec une constante partagée, jamais par préfixe.
