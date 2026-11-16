# Met à jour l'instance OntoForge en ligne (https://ontoforge.ajlx.fr) avec la version du dépôt.
# Usage, depuis la racine du dépôt (Documents\GIT\OntoForge) dans PowerShell :  .\deploy\cloudrun\deploy-demo.ps1
#   (si PowerShell refuse les scripts :  powershell -ExecutionPolicy Bypass -File .\deploy\cloudrun\deploy-demo.ps1)
$ErrorActionPreference = "Stop"
$PROJECT = "gen-lang-client-0070486409"
$REGION  = "europe-west1"
$TAG     = "demo-" + (Get-Date -Format "yyyyMMdd-HHmm")
$IMAGE   = "$REGION-docker.pkg.dev/$PROJECT/ontoforge/ontoforge:$TAG"

Write-Host "1/3  Mise à jour du dépôt (git pull)…" -ForegroundColor Cyan
git pull --ff-only origin main

Write-Host "2/3  Construction de l'image $TAG par Cloud Build (2 à 10 min)…" -ForegroundColor Cyan
gcloud.cmd builds submit --project $PROJECT --config deploy/cloudrun/cloudbuild.yaml --substitutions "_IMAGE=$IMAGE"
if ($LASTEXITCODE -ne 0) { throw "La construction a échoué : voir les lignes ci-dessus." }

Write-Host "3/3  Mise à jour du service Cloud Run…" -ForegroundColor Cyan
gcloud.cmd run services update ontoforge --project $PROJECT --region $REGION --image $IMAGE
if ($LASTEXITCODE -ne 0) { throw "La mise à jour du service a échoué : voir les lignes ci-dessus." }

Write-Host "Terminé : https://ontoforge.ajlx.fr (image $TAG)" -ForegroundColor Green
