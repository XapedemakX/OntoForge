# L40 : revue de sécurité (secu, 15/11/2026)

**Verdict : KO pour publication en l'état.** Le cloisonnement des projets tient (aucune fuite de données de projet entre comptes), mais deux constats moyens contredisent des garanties écrites du lot ; ils se corrigent en peu de lignes. Les détails de reproduction sont dans `journal/securite/revue-L39-L40-2026-11-15.md` (non publié).

Base relue : commit `e7aa18c` plus le durcissement non commité de `SpaStatic`. Recettes : `pytest` 1199 réussis, `npm run build` OK.

## Ce qui a été attaqué et tient
- Compte B sans accès au projet de A, sur les 70 entrées de la table `ROUTES` (lecture, écriture, export, génération, analyse, requêtes, triplestore local, éditeur de fichiers, carte métier, versions, historique, partage, présence, activité) avec corps vide et corps plausible : 404 `not_found` partout (jamais un 404 d'une autre origine), même message qu'un projet inexistant.
- Routes de l'assistant à `project_id` dans le corps (`shapes`, `explain`, `chat`, `shapes/apply`, `document/draft`) : 404 pour B. Aucun websocket dans l'application (le garde d'authentification les ferme). Les routes sans projet n'acceptent aucun identifiant de projet.
- Lecteur : toutes les routes d'écriture et propriétaire répondent 403 ; il ne s'ajoute pas, ne change aucun rôle, ne retire personne, ne transfère rien. Éditeur : ni partage, ni suppression, ni transfert (403).
- Chemins forgés (`//api`, `/API`, `%2e%2e`, `%2f`, `;`, `%00`, `./`, `..`, point final, majuscules dans l'identifiant) essayés en HTTP brut sous uvicorn : jamais de contournement, jamais de donnée.
- `collab.json` et `activity.jsonl` : non atteignables par l'éditeur de fichiers (liste fermée), aucune valeur libre dans le journal (identifiants validés contre les comptes, rôle validé), pas d'injection ni de traversée.
- Table de routes : la couverture est réelle côté garde (échec fermé, 403 `unclassified`). Réserve : le test paramétré `test_all_routes_by_role` ne teste que la décision du garde avec un handler factice ; il ne prouve pas ce que fait le handler après le garde (voir L40-02).
- Réglages : un compte non administrateur ne peut écrire nulle part sous `/api/settings` (403) ni lancer de test ; `GET /api/settings` et `/endpoints` sont expurgés (ni adresse, ni clé).
- Mode local : identité implicite, aucune restriction ajoutée. Il écrit désormais `collab.json` et `activity.jsonl` dans chaque projet (sans effet fonctionnel).
- Administrateur : ne voit pas les projets des autres comptes (vérifié).

## Constats

| Id | Sévérité | CWE | Composant | Résumé |
|---|---|---|---|---|
| L40-01 | Moyenne (bloquant) | CWE-200, CWE-285 | `assistant/settings_help.py:101,472` ; `queries/endpoint.py:133,167` | L'assistant de l'écran Paramètres, et certains messages d'erreur de requête, donnent à un compte non administrateur le schéma, l'hôte et le port de l'endpoint (et du fournisseur) configurés par l'administrateur. Contredit « sans en voir l'adresse » (CONTRACTS §16, guide). Aucune clé ni aucun mot de passe n'est exposé. |
| L40-02 | Moyenne (bloquant) | CWE-862, CWE-367 | `collab/routes.py:21` ; `api/analysis.py:239-255` | `GET /generate/{target}` est classée « lecture » mais réécrit `project.json` en entier, hors du verrou d'écriture, sans contrôle de version et sans journal : un lecteur modifie donc le projet, et cette écriture peut écraser en silence les changements simultanés d'un éditeur (contre « jamais d'écrasement silencieux »). |
| L40-03 | Moyenne (non bloquant, à décider) | CWE-918 | `api/queries.py:35,72,144,261` ; `netguard.py:43` | Hors `ONTOFORGE_PUBLIC=1`, la protection des appels sortants est inactive : tout compte, même lecteur, peut faire émettre une requête au serveur vers une adresse interne et en lire le début de la réponse. Avant L40 c'était vrai de tout compte connecté ; la documentation d'ouverture au réseau (multi-comptes) rend le cas courant. |
| L40-04 | Faible | CWE-204 | `api/sharing.py:45` ; `collab/access.py:268` | Le partage distingue « compte inconnu », « déjà propriétaire » et succès : un propriétaire (tout compte peut en devenir un) liste les comptes existants, à 10 essais par minute. Le message n'est donc pas « neutre » comme annoncé. |
| L40-05 | Info | CWE-636 | `collab/access.py:123,131` | Sans `collab.json` lisible, le projet retombe chez le premier administrateur (ouverture par défaut). Pas d'exploitation par un compte ordinaire constatée. Fenêtre brève à la création (`store.save` avant `init_project`). |
| L40-06 | Info | CWE-1059 | `docs/guide/limites*.md` | Limites annonçant que la version du projet vit en mémoire : elle est écrite dans `collab.json`. Seule la présence est en mémoire. |

## Corrections minimales proposées
- L40-01 : construire `snapshot()` à partir de la vue expurgée quand l'appelant n'est pas administrateur (pas d'URL, ni dans la réponse, ni dans les actions) ; pour les erreurs de requête, ne pas répéter l'adresse ni le début du corps de réponse d'un endpoint enregistré quand l'appelant n'est pas administrateur.
- L40-02 : ne pas écrire dans le projet sur une route de lecture. Soit tenir l'historique des générations dans un fichier annexe (comme `collab.json`), soit classer la route en écriture avec l'action `generate` et garder une route de téléchargement en lecture. Dans les deux cas, recharger sous verrou avant d'écrire.
- L40-03 : activer le contrôle d'adresses dès que l'authentification est activée (liste blanche facultative), ou réserver aux administrateurs les endpoints temporaires en ligne ; corriger la phrase « pas de filtrage SSRF (outil mono-utilisateur) » du guide.
- L40-04 : acceptable tel quel si assumé ; sinon réponse identique pour inconnu et connu (invitation en attente) et mettre à jour la documentation.

## Test de non-régression à ajouter (après correction)
Un test qui rejoue chaque route de niveau « lecture » avec un lecteur et compare le contenu du dossier du projet avant et après ; un test sur l'assistant des Paramètres avec un compte non administrateur.

## Contre-relecture L41 (15/11)
Verdict : KO (un point bloquant). Les corrections de L40-02 à L40-06 et de L39-01 à L39-07 sont réelles dans le code et vérifiées par rejeu des scripts d'attaque ; les effets de bord de L41 (lecture de la carte métier sans écriture, `generations.json` sous verrou, `ONTOFORGE_EGRESS_ALLOW_INTERNAL`, `childproc.py`) sont corrects. L40-03 est corrigé. L40-01 reste incomplet : un message d'erreur d'appel à un fournisseur LLM enregistré peut encore donner à un compte non administrateur une indication d'adresse. Détail et correction minimale dans `journal/securite/contre-relecture-L41-2026-11-15.md` (non publié). `pytest` : 1254 réussis, 1 test chronométré en échec sous charge et réussi seul ; `npm run build` OK.


## Correction L41-R1 (lead, 15/11) : OK
- Erreur d'un fournisseur LLM refusé par la protection des adresses : message générique, sans hôte ni adresse résolue, pour tous les comptes (`assistant/providers/base.py`). Test : `tests/test_l41_r1.py` (nom interne et IP privée) ; `test_netguard.py` aligné. Script de rejeu de la contre-relecture (assistant/chat, shapes, query/nl, carte métier) : aucune fuite.
- Assistant des Paramètres : échec fermé, un appel sans contexte est traité comme non administrateur.
- Suite complète : 1257 tests verts.
