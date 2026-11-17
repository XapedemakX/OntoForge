---
name: deploiement-cloud-run-powershell
description: Déployer pas à pas une application conteneurisée sur Google Cloud Run depuis un poste Windows (PowerShell), avec secrets, bucket monté, domaine personnalisé et mise à jour en une commande ; à utiliser pour guider quelqu'un qui n'a pas gcloud sous la main ou quand une commande gcloud se comporte autrement sous PowerShell ou cmd.
---

# Déploiement Cloud Run sous PowerShell

Procédure complète et à jour : `deploy/cloudrun/README.md` (source unique, à citer plutôt que recopier). Ce skill garde le raisonnement et les pièges.

## 1. Répartition des rôles
L'agent prépare dans le dépôt tout ce qui peut l'être (Dockerfile, `cloudbuild.yaml`, `env.yaml`, scripts, doc). Les actions sur le compte cloud et chez le registraire sont faites par la personne, guidée une commande à la fois ; l'agent ne voit jamais ses identifiants. Une étape = un bloc de commandes + ce qu'on doit voir si ça a marché.

## 2. Ordre des étapes
0. Variables de session (`$PROJECT`, `$REGION`, `$BUCKET`, `$SA`, `$IMAGE`).
1. Activer les API (Run, Artifact Registry, Cloud Build, Secret Manager, Storage).
2. Dépôt d'images, bucket de données, compte de service dédié (rôle `storage.objectUser` sur le bucket seulement).
3. Secrets (Secret Manager) : jamais dans l'image ni dans le dépôt ; accès donné au compte de service.
4. `gcloud builds submit --config … --substitutions "_IMAGE=$IMAGE"` (compter une dizaine de minutes).
5. `gcloud run deploy` avec secrets, `--env-vars-file`, volume monté.
6. Domaine : vérification de propriété, `domain-mappings create`, enregistrement DNS chez le registraire.
7. Mises à jour : un script `deploy-demo.ps1` (git pull, image étiquetée à la date, `run services update`) et un `.bat` à double-clic avec journal.
8. Déploiement automatique à chaque push sur `main` (L50, `deploy/cloudrun/README.md` §8) : compte de service dédié `ontoforge-build` aux quatre rôles ciblés (`artifactregistry.writer` sur le dépôt, `run.developer` sur le service, `iam.serviceAccountUser` sur le compte d'exécution, `logging.logWriter` sur le projet) ; connexion GitHub de 2e génération (`gcloud builds connections create github`, lien à autoriser dans le navigateur, `repositories create`) ; déclencheur créé **par fichier** (`gcloud builds triggers import`, `trigger-main.yaml`) avec approbation manuelle ; `cloudbuild-trigger.yaml` = build, push explicite, `gcloud run services update --image` (ni `env.yaml` ni secrets réappliqués : un changement de variables ou de secrets reste un déploiement à la main).

## 3. Pièges (tous rencontrés)
- **`gcloud` est un script `.cmd`** : dans un script PowerShell, appeler `gcloud.cmd`. cmd.exe supprime les `^` et mange les guillemets ; le séparateur personnalisé `--set-env-vars "^@^A=1@B=2"` est donc cassé. Solution : **un fichier `env.yaml`** passé par `--env-vars-file` (clé: "valeur"), valable dans tous les terminaux.
- **stderr n'est pas une erreur** : gcloud et git écrivent leur progression sur stderr ; avec `$ErrorActionPreference = "Stop"` PowerShell 5.1 s'arrête à tort. Mettre `Continue` et juger sur `$LASTEXITCODE` après chaque commande.
- **Fichier de secret** : écrire avec `Out-File -NoNewline -Encoding ascii` (sinon retour à la ligne ou BOM dans le secret) ; supprimer les fichiers temporaires ensuite (`Remove-Item`). Saisir les valeurs dans le Bloc-notes, pas dans l'historique du terminal.
- **`.gcloudignore`** : `gcloud builds submit` envoie le répertoire courant ; sans ce fichier partent `.env`, `.git`, le journal, les dépendances. Ancrer les dossiers avec un `/` initial (`/design/`), sinon la règle touche aussi `frontend/src/design/`. Même règle que `.dockerignore`, et re-tester ce dernier après chaque ajout de dossier de doc (`docs/*` puis `!docs/guide/`).
- **Volume Cloud Storage** : le bucket appartient à root par défaut ; ajouter `mount-options=uid=10001;gid=10001` (utilisateur non root du conteneur), sinon l'appli ne peut pas écrire. Le volume impose la 2e génération d'environnement.
- **Une seule instance** quand l'état (verrous, limiteur, présence) est en mémoire : `--max-instances 1`, `--min-instances 0` (le moins cher, démarrage à froid de 20 à 40 s).
- **`--allow-unauthenticated`** laisse passer jusqu'à l'application, qui impose sa propre connexion ; une règle d'organisation peut l'interdire (le message le dit).
- **Région** : choisir une région qui accepte le mappage de domaine Cloud Run (`europe-west1`, pas toutes).
- **Domaine** : `gcloud domains verify` ouvre la Search Console (preuve de propriété, une fois) ; ensuite `gcloud beta run domain-mappings describe` indique l'enregistrement à créer (en général `CNAME sous-domaine → ghs.googlehosted.com.`, point final compris). Chez le registraire (zone DNS, par ex. OVH : entrée CNAME ; interface exacte À VÉRIFIER), supprimer d'abord un éventuel enregistrement A/AAAA ou redirection existant sur ce sous-domaine. Le certificat est émis seul en 15 min à quelques heures ; pendant l'attente, le HTTPS échoue, ce n'est pas une panne.
- **Docker Hub ou registre inaccessible dans l'environnement de build** : la construction réelle se fait chez la personne ; l'agent relit le Dockerfile statiquement et la recette reproduit l'environnement (`recette-playwright-par-lot`, §4).

- **`^` sous `gcloud.cmd`** : cmd.exe retire le `^` d'un `--branch-pattern='^main$'` (le motif devient `main$` et accepte `feature/main`). Créer le déclencheur par fichier YAML (`triggers import`) ou saisir le motif dans la console ; contrôler avec `triggers describe --format="value(repositoryEventConfig.push.branch)"` (déclencheur 2e génération ; `--format=yaml` si vide), pas `github.push.branch` (1re génération).
- **Approbation en attente** : avec `approvalRequired`, toute construction (push ou `triggers run`) reste PENDING jusqu'à `gcloud builds approve <ID> --region=…` ou au clic dans la console.
- **Trafic épinglé après un retour arrière** : `update-traffic --to-revisions=<rév>=100` fige le trafic ; les déploiements suivants ne le reçoivent plus tant qu'on n'a pas lancé `update-traffic --to-latest`.
- **`SHORT_SHA` vide hors déclencheur** : `cloudbuild-trigger.yaml` ne se lance pas par `gcloud builds submit` (étiquette `auto-` invalide).
- **Qui pousse sur `main` décide de la production** : un compte de construction qui déploie sous le compte d'exécution hérite de ses accès (secrets, bucket) ; protection de la branche et approbation sont des contrôles de sécurité.

## 4. Sécurité et coût
Authentification obligatoire hors `/health` ; protection SSRF (IP privées, link-local, métadonnées) pour tout appel sortant ; utilisateur non root ; alertes de budget ; arrêt : `gcloud run services delete` (bucket et secrets restent, à supprimer à part). Relecture croisée : deploy + secu + expert domaine (voir `audit-securite-cve-cwe`). Le lot n'est clos qu'après un déploiement réel vérifié par la personne.
