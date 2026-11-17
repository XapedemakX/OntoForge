# L50 : rapport — finitions mobiles L45 et déploiement automatique préparé

Agents : mobile (finitions) puis deploy (Cloud Build). Recettes : `tools/recette/mobile_l50.mjs` (nouvelle), `mobile_l45.mjs`, `mobile_l44.mjs`. Aucune commande `gcloud` exécutée.

## 1. Libellé du fournisseur en double
`AssistantDock.tsx` (`provLabel`) ajoutait « · <modèle> » dès que le modèle différait du nom : « Mock (démonstration) · mock ». Le modèle n'est plus ajouté pour le fournisseur `mock`, ni quand le nom le contient déjà. Fournisseur réel : « Claude (test) · claude-sonnet-5-5 » inchangé. Vérifié par `mobile_l50`.

## 2. Légendes du guide
Les captures « téléphone » ne portent aucune pastille (elles sont produites par `tools/docs/mobile_captures.mjs`, sans annotation) alors que 7 légendes citaient « 1 », « 2 », « 3 » : toutes les légendes de `mobile-*.png`, fr et en (`docs/guide/utilisateur.md` et `.en.md`), sont réécrites sans repères numérotés. Alt-text, ancres et images inchangés.

## 3. Écrans secondaires du téléphone (iPhone 15, 393 px, version web, rôle administrateur)
Mesure sur 26 vues (écrans du projet, Paramètres par onglet, Administration par onglet, Documentation). Aucune page ne déborde horizontalement. Constats :

| Écran | État avant | Décision |
|---|---|---|
| Paramètres › Fournisseurs LLM, Endpoints SPARQL | tableau empilé sans titres ni libellés (« — — — ») : illisible | **recomposé** : cartes, `data-l` devant chaque valeur, cellules vides masquées |
| Shapes (détail d'une shape), Validation | champs à 12,5–13,5 px (zoom iOS) | **corrigé** : 16 px, 44 px de haut (`mobile.css`) |
| Documentation (guide) | recherche à 13,5 px | **corrigé** : 16 px |
| Administration › Comptes | déjà en cartes étiquetées (L42) | rien |
| Paramètres : bandeau d'onglets | défile horizontalement dans son propre cadre (6 onglets) | laissé : défilement local, pas de débordement de page |

**Non recomposés (laissés tels quels, listés pour un lot ultérieur)** :
- Shapes : grille d'édition des contraintes (820 px de large, défilement horizontal interne) ; écran marqué « Lecture seule par téléphone ».
- Éditeur de fichiers (`fichiers`) : arbre et éditeur à défilement interne ; réservé à l'ordinateur, marqué « Sur ordinateur ».
- Conformité : tableaux des constats (413 px dans un cadre de 367 px, défilement interne).
- Modèle cible : tableaux (497 px dans 367 px, défilement interne).
- Documentation : blocs de code (480 à 683 px) et tableaux du guide en défilement interne.
- Versions (tableaux `ver-table` de Paramètres et de l'écran Versions) : empilés en cartes sans libellés (343 px, lisibles mais sans titres de colonnes).
- Administration › Journal d'administration : lu en liste, non revérifié en détail au-delà de l'absence de débordement.
- Pas de test sur un vrai iPhone (sélecteur natif iOS), ni paysage ni Pixel 7 pour les écrans secondaires (iPhone 15 seul pour L50 ; Pixel 7 et iPad mini couverts par `mobile_l44` et `mobile_l45`).

## 4. Déploiement automatique
- `deploy/cloudrun/cloudbuild-trigger.yaml` : trois étapes (docker build, docker push, `gcloud run services update --image`), mêmes réglages que `deploy-demo.ps1` (`services update` : secrets, variables, volume et limites du service conservés). Image `ontoforge:auto-$SHORT_SHA`. Aucun secret ni `secretEnv` ; substitutions `_REGION`, `_REPO`, `_SERVICE` ; `logging: CLOUD_LOGGING_ONLY` (compte de service dédié). YAML relu et chargé avec PyYAML (structure valide) ; non soumis à `gcloud builds` (pas d'accès au compte).
- README Cloud Run, section 8 : variables, compte `ontoforge-build` avec 4 rôles ciblés (`artifactregistry.writer` sur le dépôt, `run.developer` sur le service, `iam.serviceAccountUser` sur `ontoforge-run`, `logging.logWriter` sur le projet), connexion GitHub (connexion de 2e génération, lien à ouvrir dans le navigateur), déclencheur sur `^main$` avec `--require-approval`, essai, retour arrière, suppression.
- Points À VÉRIFIER (signalés dans le README) : options exactes de `gcloud builds connections/repositories/triggers` ; perte du `^` par `gcloud.cmd` (vérification et repli indiqués) ; droit éventuel sur les secrets lors de `services update`.
- Hors périmètre signalé : `env.yaml` n'est pas réappliqué par le déclencheur ; un changement de variables ou de secrets reste un déploiement à la main (étape 5).

## Vérifications
Commandes depuis la racine du worktree, `BACKEND_PORT=9150 FRONT_PORT=5150` :
- `npm run build` : OK.
- `node tools/recette/mobile_l50.mjs` : 6/6 (version web, iPhone 15).
- `node tools/recette/mobile_l45.mjs` : 157 OK, 0 KO (local et web, iPhone 15, Pixel 7, iPad mini).
- `node tools/recette/mobile_l44.mjs --mode=web` : 113 OK, 0 KO ; `--mode=local` : 106 OK, 0 KO. Deux lancements d'une seule traite (local puis web) ont chacun eu un KO différent et isolé (« première décision en 1 toucher » Pixel 7, « barre d'onglets présente » web) qui n'est pas reproduit au rejeu : attentes à durée fixe sensibles à la charge de la machine (plusieurs recettes en parallèle dans les autres worktrees). Aucun lien avec L50 (écrans non touchés).
- `pytest tests/test_help_map.py tests/test_docs_bilingual.py` : 44 passés (aucun backend touché, pas de pytest complet).
- Captures : seule `mobile-krakie.png` (fr, en) change (libellé « Mock (démonstration) » sans doublon), régénérée par `tools/docs/mobile_captures.mjs` + `mobile_captures.py` (ONLY=krakie) ; les autres captures téléphone sont identiques au rendu précédent et laissées intactes. i18n : aucune clé ajoutée ni modifiée (fr/en à parité, 0 changement).
- Non exécutés : `e2e_ui`, `l35`, `l38`, `tour`, `english_scan` (écrans de bureau non touchés ; à rejouer en clôture si le chef le souhaite).
