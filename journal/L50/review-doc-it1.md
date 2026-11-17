# L50 — revue doc (exactitude), itération 1

verdict: KO

Relu : `deploy/cloudrun/README.md` (§8 surtout), `docs/guide/CHANGELOG.md` / `.en.md`, légendes `docs/guide/utilisateur.md` / `.en.md`, `journal/L50/rapport.md`.

bloquants:
  - [docs/guide/utilisateur.en.md:626, 636, 644, 658] Les légendes anglaises contiennent des guillemets droits non échappés dans le titre de l'image (`"… "To do now" …"`, `"Send me the link"`, `"Fit all"`, `"Validate this choice"`). Le titre Markdown se ferme au premier `"` interne : la syntaxe d'image n'est plus valide et l'image s'affichera en texte brut. La version précédente utilisait des guillemets simples (`'Send me the link'`). → remplacer les guillemets internes par `'…'` ou « … » (ou échapper `\"`), sur ces quatre lignes ; relancer `tests/test_docs_bilingual.py`. La version française (« … ») est correcte.
  - [deploy/cloudrun/README.md:189-190] Exactitude du piège `^` : la commande de contrôle `--format="value(github.push.branch)"` vise le champ des déclencheurs de 1re génération ; un déclencheur lié à un dépôt 2e génération (`--repository=…`) stocke le motif dans `repositoryEventConfig.push.branch` (À CONFIRMER avec `describe --format=yaml`) : la commande afficherait une ligne vide. De plus, cmd.exe retire seulement le `^` : le résultat attendu est `main$`, pas `main` comme écrit, et `main$` accepterait aussi `feature/main`. → voir revue deploy.
  - [deploy/cloudrun/README.md:172-173, 156] Les « À VÉRIFIER » sur les options de `gcloud builds connections / repositories / triggers` sont levés par la documentation Google (voir revue deploy) : la syntaxe du README est exacte. → retirer ces mentions et les remplacer par la formulation confirmée.
  - [deploy/cloudrun/README.md:195-201] Le §8.5 annonce « WORKING puis SUCCESS » alors qu'avec `--require-approval` toute construction (y compris `triggers run`) reste en attente d'approbation (PENDING) tant qu'on ne l'a pas validée ; la procédure ne dit pas comment (console, ou `gcloud builds approve <ID> --region=$REGION`). → ajouter l'étape.

non-bloquants:
  - CHANGELOG fr / en : conformes au rapport et au code (libellé Krakie, cartes Paramètres, champs 16 px dans Shapes et recherche du guide, légendes, déploiement préparé), parité fr/en, ancre cohérente. Le CHANGELOG ne dit pas que seule la liste des fournisseurs est prouvée en recette (voir scout) : sans importance pour l'utilisateur.
  - [deploy/cloudrun/README.md:102-107] Phrase « Sinon, à la main : » suivie d'une ligne vide (bloc de commandes disparu, antérieur à L50). À réparer : rappeler `gcloud builds submit …` puis `gcloud run services update ontoforge --image $IMAGE`.
  - [deploy/cloudrun/README.md:38] « Trois valeurs » mais le tableau n'en liste que deux ; [85-86] phrase dupliquée sur l'ajout d'un endpoint (antérieur à L50).
  - [deploy/cloudrun/README.md:124] `$GH_OWNER = "XapedemakX"` correspond au dépôt cité ailleurs (`docs/guide/contribuer.md`, `git-release.md`, qui écrit `OntoForge` avec majuscules : GitHub est insensible à la casse ; la connexion Cloud Build aussi, À CONFIRMER).
  - Dans `deploy/cloudrun/cloudbuild-trigger.yaml:8`, `$BUILD_ID` est cité mais n'est pas utilisé.

skill: technical-documentation : vérifier que les légendes d'images ne contiennent pas de guillemets droits dans le titre Markdown (`![alt](src "titre")`) ; ajouter un test qui parse les images du guide.
