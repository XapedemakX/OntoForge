# L53 : relecture déploiement de DF-B13, itération 2

Relecteur : deploy. Branche `lot/L53-b13`, commit def5e40 (correction it1). J'ai lu `journal/L53/fix-b13-it1.md`, `journal/L53/corrections-b13.md` (section « Itération 1 »), la décision D-L53-02 de `journal/decisions.md` (« Les deux » : plafond total et purge), `deploy/cloudrun/` (env.yaml, README, deploy-demo.ps1, cloudbuild-trigger.yaml), `backend/ontoforge/localstore/store.py`, `api/local_store.py` et `backend/tests/test_l53_b13.py`.

Je n'ai lancé aucune commande gcloud, touché aucun identifiant, rien installé ni poussé. Les 18 tests de `test_l53_b13.py` et `test_l53_b17.py` passent (24/11). J'ai fait les mesures hors dépôt (`/home/claude/tmp-deploy-l53`), avec le code de la branche.

## Verdict

| # | Point | Verdict |
|---|---|---|
| B1 | Les deux chemins de mise à jour appliquent `env.yaml`, `--memory 2Gi`, `--max-instances 1` et redonnent les secrets | **OK.** Les options sont dans `deploy-demo.ps1` et dans `cloudbuild-trigger.yaml`, avec les mêmes noms de secrets que l'étape 5. Un test de garde vérifie leur présence, et le §7 donne la commande de contrôle. Redonner les secrets est la bonne prudence : la référence gcloud de `services update` dit seulement, pour `--env-vars-file`, « All existing environment variables will be removed before the new environment variables are added ». Elle dit aussi de `--set-secrets` « All existing secrets will be removed first ». Elle ne dit pas si les variables issues de secrets survivent au premier ; avec les deux options, le résultat ne dépend plus de ce point |
| B1-bis | Compte Cloud Build sans rôle Secret Manager | **À VÉRIFIER acceptable, mais le repli écrit est faux : B3** |
| B2 | Place de chargement, 50 000 triplets, 5 Mo par fichier | **OK.** `load_slot()` est prise avant la lecture du fichier, pour l'envoi comme pour l'exemple ; 503 avec `Retry-After` si elle est occupée ; un test le vérifie. 124 Mo comptés pour une hausse mesurée de 101 Mo à 50 000 triplets ; mes mesures d'it1 donnaient environ 1 Mo pour 1 000 triplets, la formule de 1,7 Mo pour 1 000 en couvre l'écart |
| V1 | Le test de somme calcule-t-il le serveur honnêtement ? | **OK avec réserve.** Le serveur au repos (175 pour 121 à 146 mesurés) et le chargement sont maintenant deux lignes séparées, calculées depuis `env.yaml`. Deux consommations restent hors calcul : les corps de requête et la mémoire non rendue après un chargement (R1) |
| V2 | Marge de 63 Mo pour une démo | **Défendable**, parce que la somme est très prudente : les fils sont comptés à leur plafond d'espace d'adressage (704 Mo pour le triplestore, 32 à 92 Mo résidents mesurés). Je propose quand même un réglage qui la double (ci-dessous) |
| V3 | Plafond disque de 64 Mo et purge à 30 min | **Cohérents** (calcul ci-dessous). Une réserve sur l'inférence (R2) |
| B3 | Repli du README §8 : « ajouter `roles/secretmanager.secretAccessor` » au compte de construction | **KO, bloquant (documentation, une phrase)** |

**Bloquant : B3 seulement.** B1 et B2 sont levés.

## B3 : ne pas donner l'accès aux secrets au compte de construction

Le README §8 propose : si Cloud Run refuse `--set-secrets` pour le compte de construction, « ajouter `roles/secretmanager.secretAccessor` sur les deux secrets ». C'est inutile, et c'est contraire au même README.
- La documentation Cloud Run (« Configure secrets for services », section des rôles requis) sépare les deux comptes. Le **compte d'exécution du service** doit avoir Secret Manager Secret Accessor pour que Cloud Run lise le secret. Le **déployeur** a besoin des rôles Cloud Run sur le service et de Service Account User sur ce compte d'exécution, pas d'accès aux secrets. Ici le compte d'exécution a déjà le rôle (README, étape 3, l. 56-57), et le compte de construction a déjà `roles/run.developer` et `roles/iam.serviceAccountUser` (§8.2).
- Le §8.2 dit au contraire que ce compte « n'a pas d'accès direct aux secrets ». Le donner permettrait à toute construction approuvée de lire la clé maîtresse et les comptes.

Correction demandée (texte seulement) : remplacer ce repli par « si Cloud Run refuse la mise à jour, lire le message d'erreur : le compte de construction doit avoir `roles/run.developer` sur le service et `roles/iam.serviceAccountUser` sur `ontoforge-run` (§8.2) ; le compte `ontoforge-run` doit avoir `roles/secretmanager.secretAccessor` sur les deux secrets (étape 3). Ne jamais donner l'accès aux secrets au compte de construction, ni `roles/run.admin`. » Garder le second repli (retirer `--set-secrets` du déclencheur seulement, puis contrôler avec la commande du §7). Le point reste À VÉRIFIER au premier déclenchement : la documentation cite `roles/run.admin` comme rôle de référence du déployeur, et elle ne dit pas explicitement que `roles/run.developer` suffit pour poser des références de secrets. Ce n'est pas bloquant : `deploy-demo.ps1` tourne avec le compte de Jerem, et le déclencheur demande une approbation manuelle.

## Valeurs

### Somme au pire (1985 Mo, marge 63 Mo)

175 serveur + 320 SHACL + 256 OWL RL + 342 HermiT + 704 fils du triplestore + 124 chargement + 64 disque = 1985. L'arithmétique du test (`cloudrun_worst_case`) donne la même valeur à partir d'`env.yaml`.

**R1, hors calcul, non bloquant** : les corps de requête. `ONTOFORGE_MAX_BODY_MB` vaut 32 par défaut (`security.py`) et n'est pas posé dans `env.yaml`. Un envoi multipart est reçu et mis en tampon (fichier temporaire, donc en mémoire sur Cloud Run) **avant** que le gestionnaire prenne la place de chargement. Plusieurs envois simultanés reçoivent bien un 503, mais seulement après avoir occupé jusqu'à 32 Mo chacun. S'y ajoute la mémoire que Python ne rend pas forcément après un chargement (le pic ne redescend pas toujours à la valeur au repos), et les fichiers temporaires de HermiT. Tout cela est pris sur la marge.

### Réglage proposé (précis)

1. **`ONTOFORGE_LOCAL_STORE_MEMORY_MB: "640"`** (au lieu de 704), soit 64 Mo de gagnés. Les bases font maintenant 50 000 triplets au plus, et le plancher de 640 Mo a été mesuré pour une base de 1 000 000. Ma mesure du 24/11, sur une base de 50 000 triplets (Turtle compact, union refaite), requête agrégée `GROUP BY` / `ORDER BY` / `COUNT`, 10 essais par plafond :

   | Plafond (Mo) | 512 | 576 | 608 | 640 | 704 |
   |---|---|---|---|---|---|
   | Réussites | 8/10 | 9/10 | 10/10 | 10/10 | 10/10 |

   Sous 608 Mo, les échecs sont des créations de fil refusées par RocksDB (« Resource temporarily unavailable », code -6), au hasard. À 640 Mo, il reste environ 32 Mo au-dessus du dernier échec observé. L'inférence au plafond de 30 000 triplets sources passait à 576 Mo dans les mesures du pilote. Le seul coût : une très grosse requête atteint plus tôt le message « mémoire ou temps CPU plafonnés » (502), sans arrêter l'instance.
2. **`ONTOFORGE_MAX_BODY_MB: "8"`** dans `env.yaml`. C'est assez pour un fichier de 5 Mo et l'enveloppe multipart, et pour les imports d'ontologie (`api/files.py` : 4 × 2 Mo = 8 Mo). Cela divise par quatre ce que chaque corps peut occuper avant le 503 (R1). À vérifier par le pilote : aucun autre point d'entrée n'a besoin de plus de 8 Mo.

Avec les deux réglages, la somme passe à 1921 Mo, soit **127 Mo de marge**. Le test (valeur attendue), `env.yaml` et le README sont à mettre à jour en même temps. Si le pilote préfère garder 704, la marge de 63 Mo reste acceptable pour une démo à un administrateur ; le point 2 est alors d'autant plus utile.

### Disque : 64 Mo et purge à 30 min

- Le refus a lieu quand `(taille actuelle + 500 o × triplets nouveaux) × 1,25 > 64 Mio`. Sur un dossier vide, cela laisse 64 Mio / 1,25 / 500 o ≈ **107 000 triplets nouveaux, tous projets confondus** : deux projets au plafond de 50 000, ou un plein et quelques petits. Une base d'ontologie seule pèse 2 à 3 Mo, d'après la mesure de 2,5 Mo pour 4 700 triplets.
- Avec le chiffre de 312 Mo par million, soit environ 312 o par triplet, la taille réelle est plus basse que l'estimation à 500 o. Une fois chargées, les bases occupent moins que ce qu'on a réservé, et la place libre réapparaît au chargement suivant : environ 160 000 triplets si tout est mesuré à 312 o. Mes mesures d'it1 (161 Mo pour 990 000 triplets, union comprise) vont dans le même sens. Pour une démo, c'est cohérent.
- La purge à 30 min se fait au prochain usage, sans tâche de fond, et sous verrou pris sans attendre. Elle libère la place des démonstrations passées sans gêner une session en cours. Un troisième utilisateur peut recevoir un 413 si deux projets pleins ont servi il y a moins de 30 min ; le message le dit et propose de vider un projet. C'est acceptable.
- **R2, non bloquant** : `check_disk_budget(n_new)` compte les triplets du fichier, pas ceux que l'inférence ajoute ensuite (graphe inféré, puis union refaite). Le plafond de 64 Mo est donc estimé, pas strict. L'inférence est bornée à 30 000 triplets sources, et le surplus tient dans la marge. Pour le pilote : compter une estimation du graphe inféré (par exemple 2 × les sources) quand l'inférence est demandée, ou refaire la vérification après l'inférence et rétablir l'état précédent si elle dépasse, comme le fait déjà le chargement tout ou rien.

## Remarques

- Commande de contrôle du §7 : bonne. Elle n'affiche que les noms et les `secretKeyRef`, et la liste de ce qu'il faut y lire est complète.
- La mention « À VÉRIFIER » du tmpfs est levée avec la citation du contrat d'exécution : OK.
- Le déploiement de L53 doit être fait par `deploy-demo.ps1` ou par l'étape 5 complète, puis contrôlé avec le §7. Le lot n'est clos qu'après ce déploiement réel, vérifié par Jerem.

Sources : référence gcloud `run services update` (docs.cloud.google.com/sdk/gcloud/reference/run/services/update) ; « Configure secrets for services » (docs.cloud.google.com/run/docs/configuring/secrets) ; contrat d'exécution Cloud Run (docs.cloud.google.com/run/docs/container-contract).
