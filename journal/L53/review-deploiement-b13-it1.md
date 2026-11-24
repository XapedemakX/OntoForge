# L53 : relecture déploiement de DF-B13, DF-B17 et CI (itération 1)

Relecteur : deploy. Branche `lot/L53-b13`, commits 96517c2 (CI), 3ac8698 (DF-B13), e7fc8f7 (DF-B17) au-dessus de 23b0e1c. Source lue : `journal/L53/corrections-b13.md`, `deploy/cloudrun/` (env.yaml, README, deploy-demo.ps1, deploy-demo.bat, cloudbuild.yaml, cloudbuild-trigger.yaml, Dockerfile), `.github/workflows/ci.yml`, `backend/ontoforge/localstore/store.py`, `backend/tests/test_l53_b13.py`.

Aucune commande gcloud lancée, aucun identifiant touché, rien installé. `test_l53_b13.py` et `test_l53_b17.py` : 10 tests verts (24/11). Les mesures ci-dessous ont été faites hors dépôt (`/home/claude/tmp-deploy-l53`), avec le code de la branche.

## Verdict

| # | Point | Verdict |
|---|---|---|
| 1a | `env.yaml` : places et plafonds (SHACL 1 × 320, OWL RL 1 × 256, HermiT 1 × tas 192 + JVM 150, triplestore 1 × 768), somme 1861 Mo < 2048 | OK (arithmétique juste, valeurs dans les bornes acceptées par le code) |
| 1b | Le test `test_b13_cloudrun_env_sum_at_worst_fits_in_2_gib` compte-t-il tout ? | **KO** : il compte les fils (SHACL, OWL RL, HermiT avec la JVM hors tas, triplestore), mais le serveur est une constante de 175 Mo. Or le chargement d'un fichier dans le triplestore se fait **dans le serveur**, sans place ni plafond (voir B2). Le tmpfs n'est pas compté non plus (point 2) |
| 1c | Une seule place pour le triplestore local en démo | OK : acceptable pour une démo à un administrateur (une requête ou une inférence à la fois, les autres reçoivent 503 avec `Retry-After: 5`). Le front doit afficher ce 503 (à vérifier par devfront, déjà noté dans le journal) |
| 2 | tmpfs de Cloud Run | Constat confirmé (documentation Google, ci-dessous). Deux options décrites, choix à Jerem |
| 3 | Le script de mise à jour applique-t-il `env.yaml` ? | **KO** : `deploy-demo.ps1` (et `deploy-demo.bat`, qui l'appelle) fait `gcloud run services update --image` seulement ; le déclencheur `cloudbuild-trigger.yaml` aussi. `env.yaml` n'est appliqué que par l'étape 5 du README (`gcloud run deploy … --env-vars-file`). Voir B1 |
| 4 | CI : `pip install -c backend/constraints.txt -e "backend[dev]"` dans `audit-dependances` et `recettes` | OK : même ligne que le job `backend` (l. 39, 65, 109), même Python 3.12 |
| — | DF-B17 (verrou de l'analyseur SPARQL) | Sans effet sur le déploiement (un seul processus uvicorn, pas de nouvelle variable). Rien à signaler |

**Bloquants : B1 et B2.** Le lot ne peut pas être clos côté déploiement tant qu'ils ne sont pas traités ou explicitement acceptés par Jerem.

## B1 : la mise à jour en une commande n'applique pas `env.yaml`

Constat :
- `deploy/cloudrun/deploy-demo.ps1`, étape 3 : `gcloud.cmd run services update ontoforge --project … --region … --image $IMAGE`. Aucun `--env-vars-file`.
- `deploy/cloudrun/cloudbuild-trigger.yaml`, étape `deployer` : `run services update … --image=…`. Son commentaire le dit : « les variables d'environnement … déjà posées sur le service sont conservées ».
- README §7 et §8 : « `services update` ne change que l'image ; l'étape 5 complète n'est utile que si les secrets, `env.yaml` ou le volume changent ». Exact, mais L53 change justement `env.yaml`, et ni le journal L53, ni le CHANGELOG, ni le README ne demandent à Jerem de refaire l'étape 5 pour ce lot.

Conséquence : avec la procédure habituelle (`deploy-demo.bat` ou un push sur main), la nouvelle image tourne avec les anciennes variables. Si la dernière étape 5 complète a appliqué l'`env.yaml` de L52 (non vérifiable ici sans gcloud), le service a : SHACL 1 place × 2048 Mo (défaut du code, la variable n'était pas posée), OWL RL 1 × 1024, HermiT 2 places (défaut) × (768 + 150), triplestore 1024 Mo × **2 places (nouveau défaut du code, la variable n'existait pas)**. Somme au pire : 175 + 2048 + 1024 + 2 × 918 + 2 × 1024 = **7131 Mo** pour 2048. La correction DF-B13 ne serait donc pas en production, alors que le défaut serait affiché comme corrigé.

Correction proposée (non codée, à faire par le pilote puis à relire) :
1. `deploy-demo.ps1`, étape 3 : ajouter `--env-vars-file deploy/cloudrun/env.yaml` à `gcloud run services update`. Le fichier est lu depuis la racine du dépôt (le script y est lancé, `deploy-demo.bat` fait `cd` à la racine). Point **À VÉRIFIER** dans la documentation gcloud avant de livrer : `--env-vars-file` remplace toutes les variables simples du service ; il faut confirmer qu'il ne retire pas les variables issues de Secret Manager (`--set-secrets`, gérées par des options séparées) et le faire constater par Jerem après la première exécution (`gcloud run services describe ontoforge --region … --format=yaml`, section `env`, sans afficher de valeur secrète).
2. Même ajout dans `cloudbuild-trigger.yaml` (`--env-vars-file=deploy/cloudrun/env.yaml` : le déclencheur travaille sur le dépôt cloné à la révision poussée) et mise à jour de son commentaire « variables conservées ».
3. Ajouter aussi `--memory 2Gi --max-instances 1` à ces deux commandes : le calcul de L53 suppose 2 Gio et une instance ; les reposer à chaque mise à jour évite qu'un réglage changé à la main dans la console invalide la garantie.
4. README §7 et §8 : remplacer « l'étape 5 complète n'est utile que si … `env.yaml` … change » par la nouvelle règle (la mise à jour applique `env.yaml`) ; garder l'étape 5 pour les secrets et le volume.
5. Test de garde, comme pour la somme : lire `deploy-demo.ps1` et `cloudbuild-trigger.yaml` et vérifier la présence de `--env-vars-file` ; sinon, un futur changement de plafond retombe dans le même piège.
6. En attendant, pour ce lot : le journal L53 (« Reste ») et la procédure donnée à Jerem doivent dire explicitement que le déploiement de L53 demande l'étape 5 complète (ou la commande corrigée), puis la vérification des variables du service.

## B2 : le serveur n'est pas une constante de 175 Mo

Constat : `load_data` (`localstore/store.py`) appelle `parse_to_store` **dans le processus serveur** : le fichier est analysé dans un magasin Oxigraph en mémoire, puis copié dans la base RocksDB ouverte par le serveur, puis l'union est refaite (`rebuild_union`), toujours dans le serveur. Ce travail n'a ni place (`child_slot` ne couvre que les fils), ni plafond mémoire ; le verrou est par projet, donc deux chargements sur deux projets tournent en même temps. Le plafond est de 1 000 000 triplets par projet (`ONTOFORGE_LOCAL_STORE_MAX_TRIPLES`, non posé dans `env.yaml`) et de 25 Mo par fichier.

Mesure (24/11, script reprenant la séquence de `load_data` : `parse_to_store`, copie dans une base sur disque, `_dump_nt`, `rebuild_union` ; Turtle compact, 100 objets par sujet ; mémoire résidente maximale du processus) :

| Triplets chargés | Fichier | Pic résident du processus | Base sur disque |
|---|---|---|---|
| 200 000 | 1,0 Mo | 226 Mo | 32 Mo |
| 500 000 | 2,5 Mo | 536 Mo | 81 Mo |
| 990 000 | 5,0 Mo | 1004 Mo | 161 Mo |

Soit environ 1 Mo de mémoire du serveur pour 1 000 triplets chargés, avec un fichier bien sous les 25 Mo autorisés. Un seul chargement au plafond (environ 1 Go, plus la base du serveur) ajouté aux fils au pire (1686 Mo) dépasse 2048 Mo ; deux chargements simultanés sur deux projets suffisent à eux seuls. C'est le même défaut que DF-B13 (CWE-770, compte authentifié), sur un chemin que le calcul ne voit pas : le test de garde passe alors que la garantie annoncée (« la somme au pire tient dans 2 Gio avec le serveur ») ne tient pas.

Pistes (à choisir par le pilote et Jerem, non codées) :
- la plus simple, de configuration seule : poser `ONTOFORGE_LOCAL_STORE_MAX_TRIPLES` dans `env.yaml` à une valeur dont le coût entre dans la marge (par exemple 150 000 triplets, environ 150 Mo de plus dans le serveur ; à mesurer sur le serveur réel) et mettre ce coût dans la somme et dans le test ;
- sérialiser les chargements : une place (la même famille que les fils, ou une famille « chargement ») autour de `parse_to_store` et de l'écriture, pour qu'il n'y ait jamais deux chargements en mémoire à la fois ;
- à plus long terme, faire l'analyse et l'écriture dans un fils plafonné, comme les requêtes.

Dans tous les cas, le test de somme doit compter le serveur comme « base + chargement au plafond », pas comme 175 Mo fixes.

## Point 2 : tmpfs de Cloud Run (à trancher par Jerem)

Constat confirmé : la documentation Google du contrat d'exécution dit du système de fichiers du conteneur : « It is an in-memory file system, so writing to it uses the instance's memory » et « Data written to the file system doesn't persist when the instance stops » ([Container runtime contract](https://docs.cloud.google.com/run/docs/container-contract)). La mention « À VÉRIFIER » du README et du journal peut être levée. Le triplestore local vit dans `/tmp/ontoforge-triplestore` (`ONTOFORGE_LOCAL_STORE_DIR`, Dockerfile) : chaque base compte dans les 2 Gio, en plus des 1861 Mo. Taille mesurée : 161 Mo pour 990 000 triplets (mesure de B2), 312 Mo pour 1 000 000 dans les mesures du pilote (dépend des données) ; chaque projet peut aller jusqu'au plafond, il n'y a pas de limite sur la somme des projets ni de purge. Les fichiers temporaires de HermiT (`/tmp/ontoforge-hermit-*`) sont aussi en mémoire, mais petits et supprimés après usage.

Ce qui est perdu à la suppression d'une base : `ensure` reconstruit l'ontologie et les individus du projet, mais **pas les fichiers de données chargés**, qui ne vivent que dans la base. C'est déjà le cas à chaque arrêt de l'instance (min-instances 0).

| | Option A : plafond d'espace total | Option B : purge des bases inactives |
|---|---|---|
| Principe | Une variable (par exemple `ONTOFORGE_LOCAL_STORE_TOTAL_MB`) : un chargement qui ferait dépasser la taille totale de `/tmp/ontoforge-triplestore` est refusé (413), comme le plafond de triplets | Une base non utilisée depuis N minutes (ou au-delà des K projets les plus récents) est supprimée sous le verrou d'écriture du projet ; reconstruite à la demande par `ensure` |
| Garantie | Déterministe : le budget est une ligne de la somme au pire, vérifiable par le test de garde | Probabiliste : elle borne la durée, pas le volume ; plusieurs gros projets actifs en même temps restent possibles, il faut donc quand même un plafond par projet bas |
| Coût mémoire | Le budget doit être pris quelque part : la marge actuelle (187 Mo) ne suffit pas pour un projet au plafond d'un million de triplets ; il faut baisser `MAX_TRIPLES`, baisser un autre plafond, ou passer à une instance de 4 Gio (coût Cloud Run plus élevé pendant les périodes actives) | Aucun budget fixe, mais la somme au pire reste non bornée tant qu'il n'y a pas aussi un plafond |
| Coût pour l'utilisateur | Quand l'espace est plein, les chargements sont refusés même si les autres projets sont inactifs : il faut vider un triplestore à la main (bouton existant) | Les fichiers de données chargés disparaissent après l'inactivité et doivent être rechargés ; l'ontologie et les individus reviennent seuls |
| Coût de code | Calcul de la taille du dossier à chaque chargement (parcours du dossier ; RocksDB fait varier la taille pendant les compactions, donc garder une marge) ; message traduit ; test | Une tâche périodique ou une purge au moment du chargement, sous les verrous par projet (ne jamais supprimer une base pendant une requête) ; test de concurrence ; documentation de la perte des données |
| Combinaison possible | A seule suffit à la garantie | B seule ne suffit pas ; A + B évite les refus quand les projets anciens sont inactifs |

Je ne tranche pas : c'est à Jerem. Quelle que soit l'option, le budget du tmpfs doit apparaître dans la somme du README, d'`env.yaml` et du test.

## Point 4 : CI, détail

- Les trois installations du backend (`backend` l. 39, `audit-dependances` l. 65, `recettes` l. 109) sont maintenant identiques : `pip install -c backend/constraints.txt -e "backend[dev]"`, Python 3.12.
- `constraints.txt` ne fixe que les dépendances de production : les dépendances de `pytest` (extra `dev`, épinglé dans `pyproject.toml`) restent libres. Sans effet sur ce qui est livré ; pas un défaut.
- Les jobs installent `[dev]` sans `[reasoner]`, alors que l'image Cloud Run installe `[reasoner]` (owlready2). Situation antérieure au lot, sans rapport avec la correction ; l'audit de production (`pip-audit -r backend/constraints.txt`) couvre déjà owlready2. Pour information seulement.
- Première exécution réelle à regarder au prochain push (pas de GitHub Actions ici), comme le dit le journal.

## Remarques non bloquantes

- Le README garde « À VÉRIFIER » pour le tmpfs : à remplacer par la citation et le lien ci-dessus.
- `env.yaml` : commentaire de l'inférence à 31 000 triplets (576 Mo) alors que le plafond d'inférence est 30 000 : cohérent, rien à changer.
- `ONTOFORGE_OWLRL_MEMORY_MB` est borné à 256 au minimum par le code (`conformance/reasoner.py`) : la valeur retenue est déjà le plancher ; l'écrire dans le README évite qu'on essaie de la baisser pour gagner de la marge.
