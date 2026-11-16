---
name: publication-github-securisee
description: Publier un dépôt de travail lourd vers un clone léger GitHub avec exclusions, recherche de secrets bloquante, trailers de commit et push seulement sur demande ; à utiliser avant tout push public, ou pour mettre en place ce circuit de publication dans un autre projet.
---

# Publication GitHub avec détecteur de secrets

Implémentation de référence : `tools/git/publish.sh` (documentée dans `docs/guide/contribuer.md`, §Publication).

## 1. Deux dépôts
- **Dépôt de travail** : historique lourd, journal, références, brouillons. Jamais poussé tel quel.
- **Clone de publication** (branche `main`) : seul à recevoir un `push`, et seulement quand le responsable le demande (tests verts, revues OK, `doc-ok`, passe de l'humaniseur).

## 2. Ce que fait le script
1. `git archive HEAD` : seul l'état **committé** part (les modifications non commitées sont signalées, pas publiées).
2. Exclusions : références volumineuses, vidéos, `*.whl`, **dossier des audits de sécurité**.
3. Recherche de secrets sur ce qui va partir ; **un seul hit non listé = aucun commit** :
   - motifs : clés d'API des fournisseurs (`sk-ant-`, `AIza`, `ghp_`, `nvapi-`…), blocs `-----BEGIN … KEY/CERTIFICATE`, hachages `$argon2id$…` complets ;
   - fichiers `.env*` (sauf `.env.example`), `settings.json` contenant `api_key` ;
   - liste blanche `KNOWN_EXAMPLES` : littéraux **exacts** des clés factices des tests, jamais un motif large.
4. Remplacement du contenu du clone (sauf `.git`), commit avec trailers, push seulement avec `--push`.

## 3. Règles
- Message : français, titre qui commence par le lot (« L22 : … »), trailers `Co-Authored-By` et `Claude-Session` tels que fournis par la session.
- Dépôt de travail : `git add` ciblé par fichier, jamais `git add -A` (plusieurs agents écrivent en parallèle).
- Annuler un commit d'essai : `git -C <clone> reset --hard HEAD~1`, dans le clone seulement.
- Tag `vX.Y.Z` après le push, notes tirées du CHANGELOG, version du manifeste alignée.
- CI : épingler les actions par SHA de commit (version en commentaire), caches pip/npm, aucun secret requis ; recettes navigateur en lancement manuel.
- Un faux positif se traite en ajoutant le littéral exact à la liste blanche (avec le fichier d'origine en commentaire), pas en affaiblissant le motif.

## 4. Pièges
- Les tests qui ont besoin d'une clé factice la **construisent à l'exécution** (concaténation) pour ne rien laisser au détecteur ; ne pas commiter la clé entière.
- Un nouveau type de secret (autre fournisseur, autre format de hachage) = un motif de plus, avec un test sur un faux exemple.
- Vérifier aussi `.dockerignore` et `.gcloudignore` : ce qui n'est pas publié sur GitHub ne doit pas non plus partir dans l'image ou le build.
- Le script ne remplace pas la vigilance : un secret collé dans un message de commit, une issue ou une capture n'est pas vu.
