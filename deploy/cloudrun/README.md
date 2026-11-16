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

Trois valeurs, jamais dans l'image ni dans le dépôt :

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
- `deploy/cloudrun/env.yaml` : variables non secrètes (administrateur, hôtes joignables, plafonds). Ajouter un endpoint SPARQL public à `ONTOFORGE_EGRESS_ALLOW` (séparé par une virgule). Un fichier évite les pièges de séparateurs : avec `gcloud.cmd`, cmd.exe supprime les `^` d'un `--set-env-vars "^@^…"`.
  (ajouter `@sparql.exemple.org` etc. pour un endpoint SPARQL public).
- `mount-options=uid=10001;gid=10001` : le bucket appartient à l'utilisateur sans privilèges du conteneur (10001), sinon il appartient à root et l'application ne peut pas écrire (doc Google : « Configure Cloud Storage volume mounts for Cloud Run services »). Les montages de volume imposent l'environnement d'exécution de 2e génération, choisi automatiquement.

La commande affiche l'adresse `https://ontoforge-….run.app` : s'y connecter avec `jerem`.

## 6. Domaine `ontoforge.ajlx.fr` (facultatif)

```powershell
gcloud domains verify ajlx.fr            # ouvre la Search Console pour prouver que le domaine est à toi (une fois)
gcloud beta run domain-mappings create --service ontoforge --domain ontoforge.ajlx.fr --region $REGION
gcloud beta run domain-mappings describe --domain ontoforge.ajlx.fr --region $REGION
```

Chez ton registraire, créer l'enregistrement DNS indiqué par la dernière commande (en général `CNAME ontoforge → ghs.googlehosted.com.`).
Le certificat HTTPS est émis automatiquement, en 15 min à quelques heures.

## 7. Mettre à jour

En une commande, depuis la racine du dépôt : `.\deploy\cloudrun\deploy-demo.ps1` (git pull, construction d'une image étiquetée à la date, mise à jour du service). Sinon, à la main :


Nouvelle étiquette d'image (`demo-2`…), puis étapes 4 et 5 avec `$IMAGE` mis à jour. Les projets et comptes restent dans le bucket.

## Coûts et arrêt

Avec `--min-instances 0`, Cloud Run ne facture que pendant les requêtes ; le bucket et les secrets coûtent quelques centimes par mois.
Arrêter la démo : `gcloud run services delete ontoforge --region $REGION` (le bucket et les secrets restent, à supprimer à part).
