---
name: recette-playwright-par-lot
description: Écrire et rejouer une recette Playwright par lot (backend jetable, front buildé, ports uniques, captures, compte de pièges connus) ; à utiliser dès qu'un lot touche une interface web et qu'il faut prouver le parcours de bout en bout, en local ou en reproduisant la version déployée.
---

# Recette Playwright par lot

Méthode éprouvée sur OntoForge (une trentaine de scripts `tools/recette/*.mjs`, un par lot). Générique : remplace les chemins, la commande de démarrage du backend et le jeu de données.

## 1. Principes
1. Un script par lot (`tools/recette/lNN_sujet.mjs`), autonome : il démarre son backend jetable (fournisseur d'IA simulé, dossier de données temporaire) et un serveur de front, déroule le parcours, écrit un rapport OK/KO par vérification et sort avec un code non nul au premier échec.
2. Le front est construit avant (`cd frontend && npm run build`) ; la recette ne le reconstruit pas.
3. Aucun vrai secret : comptes et mots de passe tirés au hasard à l'exécution (`randomBytes`), clés d'API factices assemblées à la volée (le détecteur de secrets du dépôt ne doit rien voir).
4. Une recette ne remplace pas les tests unitaires : elle vérifie ce que ceux-ci ne voient pas (CSP, cookies, gestes, rendu, parcours multi-rôles).

## 2. Ports uniques
Chaque script a ses ports par défaut, surchargeables : `BACKEND_PORT=89xx FRONT_PORT=49xx node tools/recette/lNN.mjs`. Convention : ne jamais réutiliser les ports d'un autre script ; relever les ports déjà pris avant d'écrire (`grep -rhoE "(8|9)[0-9]{3}|(4|5)[0-9]{3}" tools/recette | sort -u`). Deux agents qui lancent des recettes en parallèle avec les mêmes ports se parasitent sans erreur claire (mauvais serveur qui répond). Variable `REUSE=1` : réutiliser des serveurs déjà lancés.

## 3. Squelette
```js
import { createRequire } from 'node:module'
const require = createRequire(import.meta.url)
let chromium
try { ({ chromium } = require('playwright')) } catch { ({ chromium } = require('/opt/node22/lib/node_modules/playwright')) }
// 1. spawn backend (env : données temporaires, IA simulée) + vite preview --strictPort
// 2. attendre /api/health (boucle 80 x 500 ms) puis le front
// 3. créer les données par l'API, pas par l'interface (rapide, reproductible)
// 4. parcours UI ; chaque vérification : check('libellé', condition) ; capture à chaque étape clé
// 5. finally : tuer les processus (process.on('exit', stopAll)), écrire le rapport
```

## 4. Reproduire la version déployée
Une recette « locale » ne voit ni la CSP, ni le cookie `Secure`, ni l'authentification. Pour cela, un module commun (`web_server.mjs`) reproduit l'environnement du Dockerfile de production : API et front servis par le même processus, variables lues dans le fichier de déploiement (`deploy/cloudrun/env.yaml`, jamais recopiées), frontal HTTPS avec certificat auto-signé généré par `openssl`, en-têtes `X-Forwarded-*` ajoutés mais non crus par le serveur, latence ajoutable (`WEB_LATENCY_MS`). Usage : `const srv = await startWeb({ mode: 'web' })` … `await srv.stop()` ; le contexte Playwright doit avoir `ignoreHTTPSErrors: true`.

## 5. Pièges connus
- Attendre un état, jamais une durée : `locator.waitFor`, `expect`-like maison ; les `sleep` fixes cassent en CI lente.
- Le premier démarrage du backend est lent (import des bibliothèques) : boucle d'attente de 40 s, pas 5.
- Port occupé par un processus orphelin d'une recette précédente : `ss -ltnp | grep :89xx` puis tuer ; toujours nettoyer dans `finally`.
- Pour les gestes tactiles, utiliser CDP (`Input.dispatchTouchEvent`) ; `page.touchscreen.tap` ne fait ni glisser ni pincer.
- Mesurer sur appareil émulé (`playwright.devices['iPhone 13']`) avec le DPR de l'appareil ; réduire les captures avant de les committer.
- Erreurs de console et violations de CSP : les collecter (`page.on('console')`, `securitypolicyviolation`) et les compter comme échec.
- Données de la recette qui polluent les exemples : toujours un dossier de données temporaire (`mkdtempSync`).
- Un test d'interface qui dépend de libellés doit les lire dans le dictionnaire i18n (`fr.json`), pas les recopier.
- Les captures versionnées réécrites par une recette : les committer à part (« recettes : captures régénérées »).

## 6. Rejouer
`cd frontend && npm run build && node tools/recette/lNN_sujet.mjs` ; en lot de clôture, rejouer aussi `e2e_ui.mjs` (non-régression générale). Le rapport du lot cite la commande et le nombre de vérifications (« 70/70 »). Rejouer une recette existante est une tâche mécanique : un modèle léger suffit.
