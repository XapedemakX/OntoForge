# L50 — revue secu, itération 1

verdict: OK

Relu : `cloudbuild-trigger.yaml`, `env.yaml`, `deploy-demo.ps1`, README §8, `.gcloudignore`. Documentation Google consultée pour les droits (Cloud Run « Configure secrets for services », Cloud Build « Connect to a GitHub repository » et référence `triggers create github`). Aucune commande gcloud exécutée.

Constats
- Aucun secret dans le YAML : pas de `secretEnv`, pas de `availableSecrets`, aucune valeur sensible ; seuls `PROJECT_ID`, la région et des noms de ressources. `env.yaml` : non secret (administrateur, hôtes autorisés, plafonds), inchangé. Pas de substitution acceptant un secret.
- Rôles minimaux du compte `ontoforge-build` : adaptés. `artifactregistry.writer` sur le seul dépôt `ontoforge` ; `run.developer` sur le seul service ; `iam.serviceAccountUser` sur `ontoforge-run` seulement (la doc Cloud Run demande au déployeur Service Account User sur l'identité du service) ; `logging.logWriter` sur le projet (exigé avec `CLOUD_LOGGING_ONLY`). Pas d'`editor`, `owner`, `run.admin`. `run.developer` suffit pour `services update` (le README fait bien de ne pas exiger `setIamPolicy`).
- `roles/secretmanager.secretAccessor` pour `services update` : non nécessaire pour le compte de construction. La documentation Cloud Run attribue `secretAccessor` à l'**identité du service** (`ontoforge-run`, déjà fait à l'étape 3), pas au déployeur ; le déployeur a besoin de `run.admin`/`run.developer` sur le service et de Service Account User sur l'identité. La page indique que les révisions suivantes reprennent la configuration des secrets et que Cloud Run contrôle les secrets utilisés au déploiement ; elle ne traite pas explicitement la mise à jour d'image seule. → garder une mention « À VÉRIFIER au premier essai » (non bloquant), avec la conduite à tenir : si l'erreur nomme le compte d'exécution, c'est `ontoforge-run` qui manque de droit sur le secret, pas `ontoforge-build`.
- Approbation manuelle `--require-approval` : bon réglage pour une instance sur Internet. Elle protège de « push sur main = production ».

bloquants:
  - aucun

non-bloquants:
  - [deploy/cloudrun/README.md:154] « Il n'a **pas** accès aux secrets, au bucket de données ni à tes comptes » : vrai pour un accès direct, mais le compte peut déployer une image arbitraire sous `ontoforge-run`, qui lit les secrets et le bucket. Le vrai périmètre de confiance est donc « qui peut pousser sur `main` et approuver une construction ». → reformuler, et rappeler que `main` doit rester protégée (CI, relecture) et que l'approbation est la dernière barrière. Ne pas retirer `--require-approval` sans cela.
  - Qui approuve : `roles/cloudbuild.builds.approver` suffit ; le propriétaire du projet l'a. Ne pas l'étendre à d'autres comptes.
  - Journaux de construction : le compte écrit dans Cloud Logging, donc lisibles par les lecteurs du projet ; le YAML n'imprime aucune valeur sensible. À garder tel quel.
  - Le déclencheur clone le dépôt (pas de `.gcloudignore`) : `.dockerignore` doit continuer à exclure `.env` (c'est le cas dans le dépôt ; une construction par déclencheur n'a de toute façon pas de `.env` non versionné).
  - Application GitHub « Cloud Build » : limiter l'accès au seul dépôt (« Only select repositories »), déjà écrit au §8.3.
  - Pas d'`secretmanager.*` ni de `storage.*` donné à `ontoforge-build` : à conserver.

skill: audit-securite-cve-cwe : ajouter à la checklist déploiement « un compte de construction qui peut déployer sous le compte d'exécution hérite de ses accès : la protection de la branche et l'approbation sont des contrôles de sécurité, pas du confort ».
