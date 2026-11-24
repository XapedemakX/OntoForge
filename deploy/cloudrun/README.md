# Déployer OntoForge sur Google Cloud Run (instance de démonstration)

Commandes pour **PowerShell sous Windows**, lancées depuis la racine du dépôt (`Documents\GIT\OntoForge`).
Une instance Cloud Run, un bucket Cloud Storage monté en `/data` pour les projets et les comptes, les secrets dans Secret Manager,
la page de connexion Krakie activée. Région : `europe-west1` (Belgique), qui accepte le mappage de domaine Cloud Run.

> Contraintes connues : **une seule instance** (`--max-instances 1` : présence, verrous et limiteur sont en mémoire), démarrage à froid
> d'environ 20 à 40 s après une période sans visite (`--min-instances 0`, le moins cher), raisonneur HermiT inclus dans l'image.

## 0. Variables de la session PowerShell

```powershell
$PROJECT = "<id-de-ton-projet-gcp>"
$REGION  = "europe-west1"
$BUCKET  = "$PROJECT-ontoforge-data"
$SA      = "ontoforge-run@$PROJECT.iam.gserviceaccount.com"
$IMAGE   = "$REGION-docker.pkg.dev/$PROJECT/ontoforge/ontoforge:demo-1"
gcloud config set project $PROJECT
```

## 1. Activer les services (une fois)

```powershell
gcloud services enable run.googleapis.com artifactregistry.googleapis.com cloudbuild.googleapis.com secretmanager.googleapis.com storage.googleapis.com
```

## 2. Dépôt d'images, bucket de données, compte de service (une fois)

```powershell
gcloud artifacts repositories create ontoforge --repository-format=docker --location=$REGION
gcloud storage buckets create "gs://$BUCKET" --location=$REGION --uniform-bucket-level-access
gcloud iam service-accounts create ontoforge-run --display-name "OntoForge Cloud Run"
gcloud storage buckets add-iam-policy-binding "gs://$BUCKET" --member "serviceAccount:$SA" --role roles/storage.objectUser
```

## 3. Secrets (une fois, puis à chaque changement de compte)

Deux valeurs, jamais dans l'image ni dans le dépôt :

| Secret | Contenu |
|---|---|
| `ontoforge-secret-key` | clé maître (signe les sessions, chiffre les clés d'API) : `docker compose exec backend python -m ontoforge.auth secret` |
| `ontoforge-auth-users` | la valeur de `ONTOFORGE_AUTH_USERS`, **sans** les apostrophes (`jerem:$argon2id$…;alice:…`) |

```powershell
# Clé maître : générée puis écrite dans un fichier temporaire sans retour à la ligne
docker compose exec backend python -m ontoforge.auth secret | Out-File -NoNewline -Encoding ascii $env:TEMP\of-key.txt
gcloud secrets create ontoforge-secret-key --replication-policy=automatic --data-file="$env:TEMP\of-key.txt"

# Comptes : copier la valeur de ONTOFORGE_AUTH_USERS du .env (entre les apostrophes) dans le fichier
notepad $env:TEMP\of-users.txt
gcloud secrets create ontoforge-auth-users --replication-policy=automatic --data-file="$env:TEMP\of-users.txt"

Remove-Item $env:TEMP\of-key.txt, $env:TEMP\of-users.txt

gcloud secrets add-iam-policy-binding ontoforge-secret-key --member "serviceAccount:$SA" --role roles/secretmanager.secretAccessor
gcloud secrets add-iam-policy-binding ontoforge-auth-users --member "serviceAccount:$SA" --role roles/secretmanager.secretAccessor
```

Pour ajouter une version plus tard : `gcloud secrets versions add ontoforge-auth-users --data-file=...`, puis redéployer (étape 5).
Les comptes créés depuis le panneau Administration vivent dans le bucket et n'ont pas besoin de secret.

## 4. Construire l'image (Cloud Build, environ 10 min)

```powershell
gcloud builds submit --config deploy/cloudrun/cloudbuild.yaml --substitutions "_IMAGE=$IMAGE"
```

`.gcloudignore` exclut `.env`, `.git`, le journal et les dépendances installées : seuls le code, la doc embarquée et les exemples partent.

## 5. Déployer

```powershell
gcloud run deploy ontoforge `
  --image $IMAGE --region $REGION --service-account $SA `
  --allow-unauthenticated `
  --max-instances 1 --min-instances 0 --cpu 1 --memory 2Gi --port 8080 --timeout 300 `
  --set-secrets "ONTOFORGE_SECRET_KEY=ontoforge-secret-key:latest,ONTOFORGE_AUTH_USERS=ontoforge-auth-users:latest" `
  --env-vars-file deploy/cloudrun/env.yaml `
  --add-volume "mount-path=/data,type=cloud-storage,bucket=$BUCKET,mount-options=uid=10001;gid=10001"
```

- `--allow-unauthenticated` : Google laisse passer tout le monde jusqu'à l'application, qui impose sa propre page de connexion.
  Si une règle d'organisation l'interdit, la commande le dira.
- `deploy/cloudrun/env.yaml` : variables non secrètes (administrateur, hôtes joignables, plafonds). Les plafonds sont réglés pour le conteneur de 2 Gio : une place par famille de processus fils (SHACL, OWL RL, HermiT, triplestore local), chacune plafonnée de façon que la somme au pire tienne dans 2048 Mo (calcul ci-dessous, section « Plafonds et somme au pire »). Ajouter un endpoint SPARQL public à `ONTOFORGE_EGRESS_ALLOW` (séparé par une virgule). Un fichier évite les pièges de séparateurs : avec `gcloud.cmd`, cmd.exe supprime les `^` d'un `--set-env-vars "^@^…"`.
- `mount-options=uid=10001;gid=10001` : le bucket appartient à l'utilisateur sans privilèges du conteneur (10001), sinon il appartient à root et l'application ne peut pas écrire (doc Google : « Configure Cloud Storage volume mounts for Cloud Run services »). Les montages de volume imposent l'environnement d'exécution de 2e génération, choisi automatiquement.

La commande affiche l'adresse `https://ontoforge-….run.app` : s'y connecter avec `jerem`.

### Plafonds et somme au pire (L53, DF-B13)

Le conteneur a 2048 Mo et une seule instance. Chaque plafond (`ONTOFORGE_*_MEMORY_MB`, `ONTOFORGE_HERMIT_MAX_MB`) borne UN processus fils ; le risque est la somme de tous les fils vivants en même temps. Le calcul se fait donc avec toutes les places prises : serveur + (places × plafond) pour chaque famille. Si la somme dépasse 2048 Mo, Cloud Run arrête l'instance (déni de service).

| Famille | Places | Plafond | Au pire | Mesure du 24/11 (jeux du dépôt) |
|---|---|---|---|---|
| Serveur au repos (processus Python) | 1 | — | 175 | mesuré 121 à 146 Mo (application chargée, un projet) ; 175 retenus |
| SHACL (`ONTOFORGE_SHACL_SLOTS`, `ONTOFORGE_SHACL_MEMORY_MB`) | 1 | 320 | 320 | trap : 64 Mo suffisent (38 Mo résidents, inférence `both` comprise) ; 42 000 triplets de données : 192 Mo suffisent, 124 Mo résidents |
| OWL RL du contrôle de conformité (`ONTOFORGE_OWLRL_SLOTS`, `ONTOFORGE_OWLRL_MEMORY_MB`) | 1 | 256 | 256 | 7 000 triplets (10 s) : 96 Mo suffisent (52 Mo résidents) ; à 22 000 triplets le délai de 30 s tombe avant tout plafond mémoire (104 Mo résidents) |
| HermiT (`ONTOFORGE_HERMIT_SLOTS`, `ONTOFORGE_HERMIT_MAX_MB`) | 1 | tas 192 + JVM 150 = 342 | 342 | trap : tas de 128 Mo suffisant (172 Mo résidents) ; automaint avec ses données (4 700 triplets) : tas de 128 Mo suffisant (225 Mo résidents) ; JVM seule (tas de 32 Mo) : 130 Mo résidents |
| Triplestore local, fils de requête et d'inférence (`ONTOFORGE_LOCAL_STORE_SLOTS`, `ONTOFORGE_LOCAL_STORE_MEMORY_MB`) | 1 | 640 | 640 | requête agrégée sur une base de 50 000 triplets : 10 essais sur 10 à 608 Mo et à 640 Mo, 8 sur 10 à 512 Mo (échecs de création de fils de RocksDB, au hasard) ; 640 Mo pour 1 000 000 triplets (312 Mo sur disque), 32 Mo résidents ; inférence `both` à 31 000 triplets sources : 576 Mo suffisent (92 Mo résidents) ; 640 Mo laissent environ 30 Mo au-dessus du dernier échec |
| Triplestore local, chargement d'un fichier **dans le serveur** (`ONTOFORGE_LOCAL_STORE_LOAD_SLOTS`, `ONTOFORGE_LOCAL_STORE_MAX_TRIPLES`, `ONTOFORGE_LOCAL_STORE_MAX_UPLOAD_MB`) | 1 | (50 000 + 20 000) triplets × 1,7 Mo / 1 000 + fichier 5 Mo | 124 | l'analyse et l'écriture se font dans le processus du serveur : +101 Mo pour 50 000 triplets, +164 Mo pour 100 000, +249 Mo pour 200 000 (mesuré le 24/11, pic résident au-dessus du serveur au repos) ; 20 000 triplets = un bloc d'analyse au-delà du plafond ; une place, 503 avec `Retry-After: 5` si prise |
| Triplestore local, disque en mémoire (`ONTOFORGE_LOCAL_STORE_TOTAL_MB`) | — | 64 | 64 | environ 470 octets par triplet sur disque (union comprise), pic de compaction jusqu'à 1,24 fois la taille finale ; 50 000 triplets font environ 24 Mo |
| Corps de requête (`ONTOFORGE_MAX_BODY_MB`) | 1 | 12 | 12 | un envoi est reçu en entier (tampon, donc mémoire) avant que le gestionnaire prenne une place de chargement : 12 Mo couvrent le plus gros envoi permis (document de l'assistant 10 Mo, imports de schémas 10 Mo cumulés ; défaut sans réglage : 32 Mo). Plusieurs envois simultanés occupent chacun jusqu'à 12 Mo avant leur 503 : ils sont pris sur la marge (environ 9 envois) |
| **Total au pire** | | | **1933** | marge de 115 Mo sous 2048 |

Lecture :
- Le plafond est un plafond d'**espace d'adressage** (`RLIMIT_AS`) pour les fils Python, donc supérieur à la mémoire réellement utilisée : la somme réelle mesurée est bien plus basse (de l'ordre de 0,7 Gio avec tous les fils au maximum). Le calcul garde le plafond, pas la mesure, pour que la garantie tienne quel que soit le contenu des fichiers.
- Le tas HermiT (`-Xmx`) ne couvre pas la JVM elle-même (métaespace, piles, code natif) : 150 Mo sont ajoutés (130 Mo mesurés pour une JVM presque vide, `-Xmx32m`).
- Plus de places par famille ou un plafond plus haut demande de refaire la somme. Le test `test_b13_cloudrun_env_sum_at_worst_fits_in_2_gib` (backend/tests/test_l53_b13.py) lit `env.yaml`, refait cette somme (fils, chargement, disque) et échoue si elle dépasse 2048 Mo.
- Une seule place pour le triplestore local signifie qu'une seule requête ou inférence tourne à la fois sur toute l'instance (tous projets), et un seul chargement de fichier à la fois ; les autres reçoivent 503 avec `Retry-After: 5`, comme pour SHACL. Le plafond de 50 000 triplets par projet (au lieu de 1 000 000) borne la mémoire du serveur pendant un chargement ; au-delà, 413.
- Un jeu de données plus gros que les mesures ci-dessus déclenche le message « mémoire ou temps de calcul plafonnés » au lieu d'arrêter l'instance : c'est le but des plafonds.
- Le système de fichiers de l'instance est **en mémoire** (documentation Cloud Run, contrat d'exécution du conteneur : « It is an in-memory file system, so writing to it uses the instance's memory ») : les bases du triplestore local, dans `/tmp/ontoforge-triplestore` (`ONTOFORGE_LOCAL_STORE_DIR`), comptent dans les 2 Gio. Deux garde-fous, tous deux réglables (décision D-L53-02) :
  - **Plafond total** `ONTOFORGE_LOCAL_STORE_TOTAL_MB` (64 sur Cloud Run, 0 = sans plafond ailleurs) : avant chaque chargement, la taille du dossier est calculée. Si cette taille, plus le coût estimé du fichier (500 octets par triplet), le tout majoré de 25 % pour les compactions de RocksDB, dépasse le plafond, le chargement est refusé (413, message qui dit l'espace utilisé et propose de vider un autre projet ou d'attendre la purge). La création de la base d'un projet vérifie aussi qu'il reste de la place.
  - **Purge des bases inactives** `ONTOFORGE_LOCAL_STORE_IDLE_MIN` (30 sur Cloud Run, 0 = jamais) : une base non utilisée depuis ce nombre de minutes est supprimée, sous le verrou d'écriture de son projet pris sans attendre (une base en cours d'usage est laissée). Il n'y a pas de tâche de fond : la purge se fait au prochain usage du triplestore par n'importe quel projet. **La purge fait perdre les fichiers de données chargés** ; l'ontologie et les individus du projet sont recréés à la demande. L'utilisateur le voit : le panneau du triplestore affiche un message (« N fichier(s) de données chargé(s) … ont été supprimé(s) après 30 min d'inactivité … rechargez vos fichiers ») jusqu'à ce qu'un fichier soit rechargé.
  Les fichiers temporaires de HermiT (`/tmp/ontoforge-hermit-*`) sont aussi en mémoire, petits et supprimés après usage : couverts par la marge de 115 Mo.

## 6. Domaine `ontoforge.ajlx.fr` (facultatif)

```powershell
gcloud domains verify ajlx.fr            # ouvre la Search Console pour prouver que le domaine est à toi (une fois)
gcloud beta run domain-mappings create --service ontoforge --domain ontoforge.ajlx.fr --region $REGION
gcloud beta run domain-mappings describe --domain ontoforge.ajlx.fr --region $REGION
```

Chez ton registraire, créer l'enregistrement DNS indiqué par la dernière commande (en général `CNAME ontoforge → ghs.googlehosted.com.`).
Le certificat HTTPS est émis automatiquement, en 15 min à quelques heures.

## 7. Mettre à jour

En une commande, depuis la racine du dépôt : `.\deploy\cloudrun\deploy-demo.ps1` (git pull, construction d'une image étiquetée à la date, mise à jour du service). Sinon, à la main : choisir une nouvelle étiquette d'image (`demo-2`…) dans `$IMAGE`, refaire l'étape 4 (`gcloud builds submit …`), puis :

```powershell
gcloud run services update ontoforge --region $REGION --image $IMAGE
```

Depuis L53, `deploy-demo.ps1` et le déclencheur (§8) appliquent aussi `deploy/cloudrun/env.yaml` : `services update … --image … --memory 2Gi --max-instances 1 --env-vars-file deploy/cloudrun/env.yaml --set-secrets "…"`, mêmes options que l'étape 5. Les deux secrets sont redonnés par leurs noms : la documentation de `--env-vars-file` n'a pas pu être consultée (accès refusé), donc on ne sait pas s'il retire les variables issues de Secret Manager. Ainsi le résultat ne dépend pas de ce point. L'étape 5 complète reste utile pour le volume du bucket ou un changement de secret. Les projets et comptes restent dans le bucket.

**À contrôler après la première mise à jour de L53** (lecture seule ; ne montre aucune valeur de secret, seulement les noms) :

```powershell
gcloud run services describe ontoforge --region $REGION --format="yaml(spec.template.spec.containers[0].env,spec.template.spec.containers[0].resources,spec.template.metadata.annotations)"
```

Attendu : `ONTOFORGE_SECRET_KEY` et `ONTOFORGE_AUTH_USERS` présents avec `valueFrom.secretKeyRef` ; `ONTOFORGE_SHACL_MEMORY_MB: 320`, `ONTOFORGE_LOCAL_STORE_SLOTS: 1`, `ONTOFORGE_LOCAL_STORE_TOTAL_MB: 64`, `ONTOFORGE_LOCAL_STORE_IDLE_MIN: 30` ; `memory: 2Gi` ; `autoscaling.knative.dev/maxScale: '1'`. Si une variable manque ou si un secret a disparu, refaire l'étape 5.

## 8. Déploiement automatique à chaque push sur main

Objectif : dès qu'un commit arrive sur la branche `main` de GitHub, Cloud Build construit l'image et met le service à jour, sans lancer `deploy-demo.ps1`.
Le fichier de construction est `deploy/cloudrun/cloudbuild-trigger.yaml` (construire, envoyer dans Artifact Registry, `gcloud run services update` avec l'image, `env.yaml`, 2 Gi, une instance, comme `deploy-demo.ps1`). Il ne contient aucune valeur de secret, seulement leurs noms : le contenu reste dans Secret Manager et ne passe jamais par Cloud Build. À VÉRIFIER au premier essai : le compte de service de construction n'a pas de rôle sur Secret Manager (§8.2) ; si Cloud Run refuse la mise à jour, lire le message d'erreur et contrôler les rôles existants : le compte de construction doit avoir `roles/run.developer` sur le service et `roles/iam.serviceAccountUser` sur `ontoforge-run` (§8.2) ; le compte d'exécution `ontoforge-run` doit avoir `roles/secretmanager.secretAccessor` sur les deux secrets (étape 3, c'est lui qui lit les secrets). **Ne jamais donner l'accès aux secrets au compte de construction, ni `roles/run.admin`.** À VÉRIFIER aussi : la documentation cite `roles/run.admin` comme rôle de référence pour déployer, sans dire que `roles/run.developer` suffit pour poser des références de secrets. Repli : retirer `--set-secrets` du déclencheur SEULEMENT (les secrets restent ceux posés par `deploy-demo.ps1`, étape 5), puis contrôler le résultat avec la commande du §7.
`deploy-demo.ps1` continue de marcher : les deux chemins peuvent coexister.

> Ce que cette section ne fait pas : elle ne crée ni le service, ni le bucket, ni les secrets (étapes 1 à 5, à faire avant, une fois). Depuis L53, chaque
> déploiement applique `env.yaml` ; un changement de secret ou de volume se fait toujours à la main (étape 5).

Les commandes ci-dessous sont à lancer par toi, dans PowerShell, après les variables de l'étape 0. Aucune n'a été exécutée par l'équipe.

### 8.1 Variables supplémentaires

```powershell
$GH_OWNER = "XapedemakX"          # propriétaire du dépôt GitHub
$GH_REPO  = "ontoforge"           # nom du dépôt
$BUILD_SA = "ontoforge-build@$PROJECT.iam.gserviceaccount.com"   # compte de service qui exécutera les constructions
```

### 8.2 Compte de service de construction, avec les rôles minimaux

Un compte dédié, qui ne sert qu'à cela (on évite le compte de service par défaut de Cloud Build, plus large). Il reçoit quatre droits, chacun posé sur la ressource concernée
quand c'est possible :

```powershell
gcloud iam service-accounts create ontoforge-build --display-name "OntoForge Cloud Build (déploiement automatique)"

# 1. envoyer des images, dans le seul dépôt « ontoforge »
gcloud artifacts repositories add-iam-policy-binding ontoforge --location=$REGION --member "serviceAccount:$BUILD_SA" --role roles/artifactregistry.writer
# 2. mettre à jour le seul service « ontoforge » (et pas les autres services du projet)
gcloud run services add-iam-policy-binding ontoforge --region=$REGION --member "serviceAccount:$BUILD_SA" --role roles/run.developer
# 3. avoir le droit de « se faire passer » pour le compte d'exécution du service (obligatoire pour déployer une révision)
gcloud iam service-accounts add-iam-policy-binding $SA --member "serviceAccount:$BUILD_SA" --role roles/iam.serviceAccountUser
# 4. écrire les journaux de construction (seul rôle posé sur le projet entier)
gcloud projects add-iam-policy-binding $PROJECT --member "serviceAccount:$BUILD_SA" --role roles/logging.logWriter
```

| Rôle | Où | Pourquoi |
|---|---|---|
| `roles/artifactregistry.writer` | dépôt `ontoforge` | pousser l'image |
| `roles/run.developer` | service `ontoforge` | `run services update` |
| `roles/iam.serviceAccountUser` | compte `ontoforge-run` | autoriser la nouvelle révision à tourner sous ce compte |
| `roles/logging.logWriter` | projet | journaux de construction (le YAML demande `CLOUD_LOGGING_ONLY`) |

Ne donne ni `roles/editor`, ni `roles/owner`, ni `roles/run.admin` à ce compte. Il n'a pas d'accès direct aux secrets, au bucket de données ni à tes comptes, mais il peut déployer une image sous `ontoforge-run`, qui les lit : **le vrai périmètre de confiance est « qui peut pousser sur `main` et approuver une construction »**. Garde donc `main` protégée (relecture, CI verte avant fusion). La protection de la branche et l'approbation manuelle (8.4) sont des contrôles de sécurité, pas du confort. Ne donne le rôle `roles/cloudbuild.builds.approver` qu'à toi.
Si une étape échoue avec « permission denied », le message nomme la permission manquante : ajoute le rôle le plus étroit qui la contient, jamais un rôle large.
Pour créer le déclencheur avec ce compte (8.4), la personne qui lance la commande doit avoir `roles/iam.serviceAccountUser` sur `ontoforge-build` (acquis pour le propriétaire du projet).
À VÉRIFIER au premier essai : si la mise à jour réclame un droit sur un secret, lis le message : si c'est le compte d'exécution qui est nommé, c'est `ontoforge-run` qui manque de droit sur le secret (étape 3), pas `ontoforge-build`.

### 8.3 Connecter le dépôt GitHub (une fois, avec ton navigateur)

```powershell
gcloud builds connections create github ontoforge-github --region=$REGION
```

La commande affiche un lien à ouvrir dans le navigateur. Connecte-toi à GitHub, autorise l'application « Google Cloud Build » et ne lui donne accès qu'au dépôt `ontoforge`
(« Only select repositories »). Reviens ensuite au terminal, puis :

```powershell
gcloud builds connections describe ontoforge-github --region=$REGION     # doit afficher installationState: COMPLETE
gcloud builds repositories create ontoforge --connection=ontoforge-github --region=$REGION --remote-uri="https://github.com/$GH_OWNER/$GH_REPO.git"
```

Si `describe` indique que l'installation n'est pas terminée, le lien qu'il affiche sert à la finir. Syntaxe conforme à la documentation Google « Connect to a GitHub repository » (Cloud Build).

### 8.4 Créer le déclencheur

On crée le déclencheur à partir d'un fichier, parce que le motif de branche `^main$` perd son `^` en ligne de commande : `gcloud` est un script `.cmd` et cmd.exe retire le `^` (le motif deviendrait `main$`, qui accepterait aussi `feature/main`).
Le fichier `deploy/cloudrun/trigger-main.yaml` ne contient aucun secret, seulement des noms de ressources et `<PROJET>` à remplacer :

```powershell
(Get-Content deploy/cloudrun/trigger-main.yaml) -replace '<PROJET>', $PROJECT | Set-Content -Encoding ascii $env:TEMP\of-trigger.yaml
gcloud builds triggers import --source="$env:TEMP\of-trigger.yaml" --region=$REGION
Remove-Item $env:TEMP\of-trigger.yaml
```

Contrôle : `gcloud builds triggers describe ontoforge-deploy-main --region=$REGION --format="value(repositoryEventConfig.push.branch)"` doit afficher `^main$`
(si la ligne est vide, regarde `--format=yaml` : le nom exact du champ est à confirmer au premier essai). S'il affiche `main$`, le `^` a été perdu : corrige le motif dans la console (Cloud Build > Déclencheurs > modifier).
Repli si l'import échoue : créer le déclencheur dans la console (Cloud Build > Déclencheurs > Créer ; dépôt `ontoforge` de la connexion `ontoforge-github`, événement « Push vers une branche », branche `^main$`, configuration `deploy/cloudrun/cloudbuild-trigger.yaml`, compte de service `ontoforge-build`, case « Exiger l'approbation » cochée), ou essayer en ligne de commande `gcloud builds triggers create github --name=ontoforge-deploy-main --region=$REGION --repository="projects/$PROJECT/locations/$REGION/connections/ontoforge-github/repositories/ontoforge" --branch-pattern='^^main$' --build-config=deploy/cloudrun/cloudbuild-trigger.yaml --service-account="projects/$PROJECT/serviceAccounts/$BUILD_SA" --require-approval`, puis contrôler avec `describe`.

`approvalRequired: true` : chaque construction attend ton approbation avant de déployer (8.5). C'est le réglage prudent, puisque l'instance est sur Internet : un push sur `main` ne met rien en ligne sans toi. Ne le retire pas sans avoir protégé `main`.

### 8.5 Essayer et vérifier

```powershell
gcloud builds triggers run ontoforge-deploy-main --region=$REGION --branch=main      # lance une construction sans attendre un push
gcloud builds list --region=$REGION --limit=3                                         # PENDING tant que tu n'as pas approuvé, puis WORKING, puis SUCCESS (environ 10 min)
gcloud run services describe ontoforge --region=$REGION --format="value(spec.template.spec.containers[0].image)"
```

Avec l'approbation requise (8.4), la construction reste en attente (PENDING) jusqu'à ton accord. Approuve-la dans la console (Cloud Build > Historique > « Approuver »)
ou en ligne de commande, avec l'identifiant lu dans `gcloud builds list --region=$REGION --filter="status=PENDING"` (filtre à confirmer) :

```powershell
gcloud builds approve <ID-DE-LA-CONSTRUCTION> --region=$REGION
```

Avant le premier essai, vérifie aussi que le service ne suit pas déjà un trafic épinglé : `gcloud run services describe ontoforge --region=$REGION` (le trafic doit aller à « LATEST »).
La dernière commande doit afficher une image `…/ontoforge:auto-<7 caractères du commit>`. Ouvre ensuite `https://ontoforge.ajlx.fr` et connecte-toi. Le journal d'une construction se lit
dans la console (Cloud Build > Historique). Le lot n'est clos qu'après ce premier déploiement réel vérifié par toi.

### 8.6 Revenir en arrière, suspendre, supprimer

```powershell
gcloud run revisions list --service ontoforge --region=$REGION                                                        # anciennes révisions
gcloud run services update-traffic ontoforge --region=$REGION --to-revisions=<nom-de-la-révision>=100                 # retour à l'une d'elles (le trafic reste épinglé)
gcloud run services update-traffic ontoforge --region=$REGION --to-latest                                            # reprendre le suivi automatique de la dernière révision
gcloud builds triggers delete ontoforge-deploy-main --region=$REGION                                                  # supprimer le déclencheur
```

Pour suspendre le déploiement automatique sans le supprimer : console, Cloud Build > Déclencheurs > « Désactiver ». Le coût d'une construction (machine `E2_HIGHCPU_8`, une dizaine de minutes)
reste de quelques centimes ; une alerte de budget (étape « Coûts ») reste recommandée.

## Coûts et arrêt

Avec `--min-instances 0`, Cloud Run ne facture que pendant les requêtes ; le bucket et les secrets coûtent quelques centimes par mois.
Arrêter la démo : `gcloud run services delete ontoforge --region $REGION` (le bucket et les secrets restent, à supprimer à part).
