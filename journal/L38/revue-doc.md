verdict: KO
relecteur: documentaliste (commit 2d411b6) ; `tests/test_help_map.py` et `tests/test_docs_bilingual.py` verts (inclus dans les 1050 réussis).

bloquants:
  - [docs/CONTRACTS.md §14 « Confidentialité », docs/guide/utilisateur.md et .en.md « Krakie dans les Paramètres », docs/guide/CHANGELOG.md et .en.md L38] la doc affirme que Krakie « ne reçoit jamais » de jeton et que les adresses sont « envoyées sans identifiants ni paramètres ». Faux dans deux cas constatés (voir revue-securite.md) : jeton placé dans le chemin de l'URL, et IRI de base à port invalide (identifiants renvoyés tels quels). Soit corriger le code, soit réécrire l'énoncé (« sans identifiants ni paramètres de requête ; le chemin est transmis tel quel : n'y mettez pas de secret »). Dès la correction du code, relire la phrase.
  - [docs/guide/limites.md et limites.en.md] la limite « `GET /api/settings` renvoie les URL telles que saisies ; un identifiant collé dans une URL est visible dans l'écran Paramètres » figure dans CONTRACTS §14 et le rapport, pas dans les limites du guide. À ajouter (fr et en), avec la limite du masquage (formes usuelles de clés seulement, pas les encodages ni les formats inconnus).

non-bloquants:
  - [docs/CONTRACTS.md §14 « Entrée »] « `provider_id` inconnu ou non configuré : réponse intégrée avec un avertissement » : seul l'inconnu en émet un (settings_help.py:456-457) ; un fournisseur non configuré donne la réponse intégrée sans avertissement. Aligner.
  - [docs/CONTRACTS.md §14 « Réponses »] « langue du message, de l'assistant et de l'interface » : conforme à `reply_lang` (anglais si l'un des trois est en anglais) ; préciser « anglais dès que l'un des trois l'est ».
  - [docs/guide/utilisateur.md « Affichage »] « L'onglet Versions est décrit à la section suivante » : exact (section 15), mais l'ancre `settings-versions` pointe vers « Versions des normes et des cibles », hors de la section 14 ; cohérent, à garder en tête si la numérotation bouge.
  - [docs/guide/utilisateur.md, Krakie dans les Paramètres] ne dit pas que l'état « Affichage » (stocké dans le navigateur) n'est pas connu de Krakie (indiqué dans le rapport seulement).

conforme au code:
  - `help_map.json` : `settings`, `settings-llm`, `-lang`, `-defaults`, `-versions`, `-display`, `-sparql` → ancres toutes présentes dans `utilisateur.md` et `utilisateur.en.md` ({#parametres-fournisseurs-llm}, -langues, -valeurs-par-defaut, -affichage, -endpoints-sparql, #versions-des-normes-et-des-cibles, #parametres).
  - Guide fr et en : mêmes sous-sections et mêmes ancres, captures `krakie-parametres` présentes dans les deux langues avec dimensions dans `img/sizes.json` ; actions, trois cartes, `#/aide/<page>/<ancre>`, redaction, repli sans LLM : conformes. API fr/en, limites fr/en (ajout `[TASK:settings]` non éprouvé), CHANGELOG fr/en : parallèles et conformes au code (422 hors contexte settings, actions `settings_goto`, `settings_test`, `help`, `proposal: null`).
  - CONTRACTS §14 : format des actions (au plus 4), masquage (8 caractères en sous-chaîne, 4 à 7 en mot entier, formes listées dont AWS et Slack en plus), `settings_test` retiré pour mock et non configuré : conformes.


## Contre-relecture (chef, 15 nov. 2026) : OK
- CONTRACTS §14, guide fr/en et CHANGELOG fr/en décrivent maintenant la règle réelle (hôte et port seulement, IRI de base à segments opaques masqués, masquage des secrets collés limité aux formes usuelles).
- `limites.md` et `limites.en.md` : nouvelle question « Que voit Krakie dans les Paramètres… » avec les deux limites (masquage, `GET /api/settings` qui réaffiche les URL saisies).
