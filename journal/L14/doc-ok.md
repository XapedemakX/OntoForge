# L14 — doc-ok (documentaliste, 4 novembre 2026)

Statut : **documentation de l'itération 2 à jour**, sous réserve des points ci-dessous.

Mis à jour : `docs/guide/utilisateur.md` (parcours it. 2 : tableau de bord, éditeur et gestes, saisie rapide, périmètres, assistant plein écran, Paramètres, requêtage interactif, Krakie), `architecture.md` (settings, editing, queries/builder+nl, shell/kit/i18n/krakie, store de proposition, stockage), `api.md` (routes CONTRACTS §4-7 avec exemples), `limites.md`, `CHANGELOG.md` (0.2.0), `glossaire.md`, `README.md` (« Parcours de démo », « Ce qu'il faut savoir »), `journal/doc/questions.md` (11 questions traitées, 3 nouvelles).

Vérifié contre le code : routes (`api/*.py`), plafonds (upload 2 Mo, LIMIT 5000, 200 niveaux d'annulation), noms de fonctions, registre des écrans, schémas Krakie, état de `core/pg_model.py`. Captures consultées : L11 tableau, L9 éditeur, L15 langage naturel ; les autres sont citées d'après les rapports.

Réserves :
- Tests backend non rejoués (`httpx` absent) : 528 verts cités d'après la revue L15.
- Exemples `api.md` it. 2 dérivés des contrats, non rejoués contre un backend (Q-DOC-14).
- Écarts hors périmètre doc : `docs/RULES.md` / `catalog.py` D05 (Q-DOC-04), `Severity` `info` et `NodeType.icon` non implémentés (Q-DOC-12), nom du skill `agent-team-delivery` (Q-DOC-11), `skills/technical-documentation/SKILL.md` non modifié.
