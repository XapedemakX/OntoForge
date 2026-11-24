# L52, partie front : corrections de DF-F01, F02, F04, F05, F06, F07, F08

Pilote : devfront. Source : `journal/L51/defauts.md`. Branche `lot/L52-front` (un défaut, un commit). Les tests citent « avant » = sources de L51 (`016a02b`) avec le test posé dessus, « après » = fin du lot.

Contrôles de fin de lot : `npm run build` vert ; `npm test` 19 / 19 (avant : 4 tests existants, 7 des nouveaux garde-fous échouent sur les sources de L51) ; `pytest tests/test_dev_docs.py tests/test_docs_bilingual.py tests/test_front_guards.py` 206 verts ; recettes `e2e_ui` 30 OK / 0 KO, `l35_sidebar` 43 OK / 0 KO, `l38_settings_krakie` 37 / 37, `mobile_l45` (local et web, trois appareils) « Tout est vert » (deux passages : le premier, coupé par mon délai à 153 OK / 0 KO, relancé en entier), `l40_partage` « tout est vert ». Les captures versionnées réécrites par les recettes ont été restaurées, aucune n'est commitée.

Choix de lieu pour DF-F08 : test Node dans `frontend/tests/` (les deux dictionnaires sont dans `frontend/src/i18n`, aucune dépendance, il tourne avec `npm test` et désormais dans la CI), relayé par `backend/tests/test_front_guards.py` pour que la suite pytest le lance aussi (même schéma que `test_sec_front.py`).

## DF-F01
**Problème.** Réseau injoignable : `aapi.ts`, `gapi.ts`, `editor/types.ts` et `qapi.ts` (deux fois) lançaient `'Serveur injoignable'` en dur ; `api.ts`, `fapi.ts` et `settingsApi.ts` utilisaient `tr('ui.unreachable')`. Reproduction : interface en anglais, arrêter le backend, ouvrir l'assistant ou l'éditeur : le bandeau d'erreur est en français (`Server unreachable. Check…` côté Paramètres, `Serveur injoignable` ailleurs). `qapi.ts` en prime ajoutait un point final.

**Correction.** Traité par DF-F02 : plus aucun client ne porte son propre message ; `lib/http.ts::request` renvoie `tr('ui.unreachable')` (clé fr et en déjà présente). Le message est désormais identique partout, y compris dans `lib/proposal.ts` (avant : message brut du navigateur, `Failed to fetch`).

**Résultat.** Test : `frontend/tests/api_clients.test.mjs`, « aucun Serveur injoignable en dur ». Avant : échoue (4 fichiers cités). Après : passe.

**Reste.** `Login.tsx` gère lui-même l'erreur réseau (clé `auth.net`, déjà traduite) : volontairement hors du client commun.

## DF-F02
**Problème.** Sept variantes du même bloc `fetch` + lecture de `detail` : `api.ts::req` (chaîne ou liste, `code`), `api.ts::zip` (chaîne seulement), `aapi.ts` (chaîne ou liste), `gapi.ts` (idem), `editor/types.ts` (chaîne seulement), `qapi.ts::call` (chaîne ou liste) et `formCall` (chaîne seulement), `settingsApi.ts` (liste avec préfixe du champ), `fapi.ts` (ne lève pas), plus `lib/proposal.ts` (chaîne seulement). Une correction sur l'un ne se propageait pas : une erreur de validation 422 en liste aurait donné `Erreur 422` dans l'éditeur et le zip, mais le détail dans les requêtes (le backend renvoie aujourd'hui une chaîne, donc pas de symptôme visible).

**Correction.**
- `frontend/src/lib/httpDetail.ts` : `detailMessage(body, repli, withLoc)` et `detailCode(body)`, fonctions pures (testables par `node --test`).
- `frontend/src/lib/http.ts` : `request(url, init, {withLoc})` appelle `fetch` (le `fetch` global de `AuthGate.tsx`, lu à chaque appel : CSRF et `If-Match` inchangés), puis renvoie `{ok, res}` ou `{ok: false, status, message, code, body}` ; erreur réseau = `status` 0 + `ui.unreachable` ; repli `ui.http`.
- Les huit clients (`api.ts` `req` et `zip`, `aapi`, `gapi`, `editor/types.ts`, `qapi` `call` et `formCall`, `settingsApi`, `fapi`, `proposal.ts`) ne gardent que leur type d'erreur : `ApiError`, `SettingsError`, `Error` avec `status` ou sans, `{status, ok, data}` pour `fapi` (qui ne lève toujours pas). URL, méthodes, corps et en-têtes sont copiés tels quels.
- Aucun changement visible attendu : `detail` en liste est désormais lu par tous les clients, par sécurité (le backend renvoie aujourd'hui une chaîne ; `aapi` et `gapi` lisaient déjà la liste). L'erreur réseau de `proposal.ts` est traduite. Relecture secu/scout/mobile : le message `ui.unreachable` ne cite plus « port 8000 » (conseil de développeur) et devient « Serveur injoignable. Réessayez dans un instant. ».

**Résultat.** Tests : `frontend/tests/http_detail.test.mjs` (chaîne, liste, `withLoc`, repli, code) ; `api_clients.test.mjs` : « les clients passent tous par lib/http.ts » et « `detail` n'est lu que dans httpDetail.ts ». Avant : les deux échouent (8 fichiers fautifs). Après : passent. Recettes : e2e_ui, l35, l38 vertes, sans erreur de console.

**Reste.** `Login.tsx`, `AuthGate.tsx` (session, déconnexion), `Banners.tsx` (rejeu d'écriture après conflit), `DocImport.tsx`, `activeEndpoint.ts`, `i18n/index.tsx` appellent encore `fetch` : ils ne lisent pas `detail` ou ont une logique propre (compte à rebours, rejeu). À rebrancher seulement si l'un d'eux doit lire une erreur du serveur. Le garde-fou « `detail` lu seulement dans httpDetail.ts » est une recherche de motifs dans les sources (accès `x.detail`, `['detail']`, `typeof …detail`) : il attrape les copies courantes, pas une lecture déguisée (variable intermédiaire, destructuration). La revue de code reste le dernier filet.

## DF-F04
**Problème.** `ontoforge:authed` (`AuthGate.tsx`) et `ontoforge:project` (`proposal.ts`, `assistant-global/run.ts::notify`) étaient émis sans `addEventListener` nulle part : code mort, et un lecteur du code croyait à un canal de rafraîchissement.

**Correction.** Suppression, plutôt que branchement. Le rafraîchissement du projet passe déjà par `bindProjectSetter`, `setP` et `onProject` ; écouter l'évènement en plus aurait doublé le rechargement. L'ouverture de session met déjà l'état à jour par `apply(s)`. Fichiers : `AuthGate.tsx`, `lib/proposal.ts` (commentaire d'en-tête corrigé), `assistant-global/run.ts` (la fonction `notify` disparaît).

**Résultat.** Tests : `api_clients.test.mjs`, « aucun évènement ontoforge:authed ou ontoforge:project » et « tout évènement ontoforge:* émis a un récepteur » (ce second test garde l'avenir, il suit aussi les noms portés par une constante). Avant : les deux échouent. Après : passent. Recettes : aucun parcours ne dépendait de ces évènements.

**Reste.** Rien.

## DF-F05
**Problème.** `ApiError.notReady` (`api.ts`) : commentaire « module backend pas encore livré » périmé, getter lu nulle part. Seul `SettingsError.notReady` sert (`EndpointsSection.tsx`). La 501 sert aujourd'hui aussi à signaler l'absence de HermiT ; `ui.tsx` lit `status === 501` directement.

**Correction.** Getter et commentaire supprimés de `ApiError`. `SettingsError.notReady` conservé (utilisé, son commentaire reste exact).

**Résultat.** Test : `api_clients.test.mjs`, « ApiError n'expose plus de getter notReady mort ». Avant : échoue. Après : passe. `tsc -b` confirme qu'aucun appelant n'existait.

**Reste.** Rien.

## DF-F06
**Problème.** `ORDER` de `frontend/src/lib/docs.ts` citait `deploiement`, absent de `docs/guide/` (la page est ignorée sans effet, mais l'ordre mentait).

**Correction.** `deploiement` retiré de `ORDER`. Décision : pas de création de page (le déploiement est décrit par le manuel, chapitre 17, et le skill de déploiement ; Jerem n'a pas demandé de page de guide).

**Résultat.** Test : `api_clients.test.mjs`, « chaque page citée dans ORDER existe dans docs/guide » (insensible à la casse, `changelog` ↔ `CHANGELOG.md`). Avant : échoue sur `deploiement`. Après : passe.

**Reste.** Si une page de guide sur le déploiement est voulue un jour, l'ajouter au dossier puis à `ORDER` : le test le permet.

## DF-F07
**Problème.** `.github/workflows/ci.yml`, job `recettes` : `npm install --no-save --no-package-lock playwright` sans version.

**Correction.** `playwright@1.63.0`. Version vérifiée : `/opt/node22/lib/node_modules/playwright/package.json` donne 1.63.0 (la machine des agents). Aucune autre version touchée.

**Résultat.** Pas de test automatique (le job est manuel). Avant : `playwright` (dernière version publiée à chaque exécution). Après : `playwright@1.63.0`. `docs/dev/17` et `18` mis à jour (fr et en).

**Reste.** Lancer le job `recettes` sur GitHub une fois pour confirmer que Chromium se télécharge à cette version (non vérifiable ici : pas de CI locale).

## DF-F08
**Problème.** Aucun test ne gardait la parité de `fr.json` et `en.json` (2201 clés de chaque côté au 23/11) ni celle des `{x}` ; la CI ne lançait pas `npm test`.

**Correction.** `frontend/tests/i18n_parity.test.mjs` : mêmes clés, mêmes espaces réservés par clé, aucune valeur vide ou non textuelle. Étape `npm test` ajoutée au job `frontend` de la CI. `backend/tests/test_front_guards.py` lance les trois nouveaux fichiers Node depuis `pytest`.

**Résultat.** Parité réelle aujourd'hui : les trois tests passent sur les dictionnaires actuels. Contrôle par mutation : retrait de `ui.http` dans `en.json` et ajout d'un `{n}` à `ui.unreachable` ⇒ échec avec « clés sans équivalent : fr seul ui.http » ; fichier restauré ensuite.

**Reste.** Le test ne vérifie pas les pluriels « (s) » (dette connue, chapitre 15) ni le contenu des traductions (le scan du français en anglais reste `tools/recette/english_scan.mjs`).

## Fichiers partagés touchés
`.github/workflows/ci.yml` (deux lignes), `docs/guide/CHANGELOG.md` et `.en.md` (section « L52, partie front » ; la partie back a sa propre section à fusionner), `journal/L51/defauts.md` (colonne Statut), `docs/dev/01, 02, 15, 17, 18` (fr et en).
