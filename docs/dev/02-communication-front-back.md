# 02. Communication front ↔ back {#communication-front-back}

Comment le navigateur et le serveur se parlent : qui ajoute quel en-tête, ce que le serveur refuse et pourquoi, ce que l'interface fait de chaque refus. La partie serveur (routes FastAPI, modèles pydantic, dépendances) est dans la section « Côté serveur », plus bas. Retour au [sommaire](README.md).

État vérifié le 23 novembre 2026 sur la branche `lot/L51`. Les points non exécutés sont marqués `À CONFIRMER`.

## 1. Rôle {#role}

- Tout passe par HTTP JSON sous le préfixe `/api`. Pas de WebSocket, pas de SSE : la « collaboration » est un sondage (présence toutes les 20 s) plus une concurrence optimiste (`If-Match`).
- Le front n'a pas de client unique : un `fetch` global est **corrigé au démarrage** (`frontend/src/auth/AuthGate.tsx`) pour ajouter jeton CSRF, version du projet, file d'attente d'écritures et réaction aux 401 / 403 / 409 / 428. Ensuite sept clients, `api.ts` compris (un par zone), formatent les appels et les erreurs.
- Le serveur renvoie du JSON, sauf les exports (texte) et le zip (octets).

## 2. Fichiers et responsabilités {#fichiers}

| Fichier | Responsabilité |
|---|---|
| `frontend/src/api.ts::api` | client typé principal (projets, analyse, génération, comptes, versions…) ; types miroirs de `backend/ontoforge/core/*.py` |
| `frontend/src/api.ts::req` | l'appel de base : URL, corps JSON ou `FormData`, erreur normalisée |
| `frontend/src/api.ts::ApiError` | erreur portant `status` et `code` (code stable du serveur) |
| `frontend/src/auth/AuthGate.tsx` | **remplace `window.fetch`** : CSRF, `If-Match`, `ETag`, file par projet, événements 401 / 403 / 409 / 428 ; porte la session (`GET /api/auth/session`) |
| `frontend/src/collab/rev.ts` | version connue par projet (`getRev`, `noteRev`, `forceRev`), `queued` (file d'écritures), `conflictFrom` (rejouabilité) |
| `frontend/src/collab/useCollab.ts::useCollab` | battement de présence, détection « quelqu'un d'autre a enregistré » |
| `frontend/src/collab/Banners.tsx::ConflictDialog` | dialogue de conflit, « recharger et réappliquer » |
| `frontend/src/screens/editor/types.ts::eapi` | client de l'éditeur graphe (`/graph`, `/ops`, périmètres, icônes) |
| `frontend/src/screens/files/fapi.ts::fapi` | client de l'éditeur de fichiers ; renvoie `{status, ok, data}` au lieu de lever |
| `frontend/src/screens/queries/qapi.ts::qapi` | client des requêtes guidées |
| `frontend/src/screens/assistant/aapi.ts::aapi` | client de l'assistant plein écran |
| `frontend/src/assistant-global/gapi.ts::gapi` | client du panneau Krakie |
| `frontend/src/screens/settings/settingsApi.ts::settingsApi` | client des Paramètres (`/api/settings`) |
| `frontend/src/lib/proposal.ts::acceptItem` | appel direct de `POST /ops` pour accepter une proposition de l'assistant |
| `frontend/vite.config.ts` | proxy de développement `/api` |
| `frontend/nginx.conf` | proxy de la version Docker locale |
| `backend/ontoforge/security.py::SpaStatic` | sert le front compilé en production (Cloud Run) |

## 3. Flux d'un appel d'écriture {#flux-ecriture}

Exemple : l'éditeur graphe ajoute une classe (`POST /api/projects/{id}/ops`) sur une instance avec authentification.

```mermaid
sequenceDiagram
  participant E as Écran (Editor.tsx)
  participant C as eapi.call
  participant F as window.fetch corrigé (AuthGate.tsx)
  participant Q as file par projet (rev.ts::queued)
  participant RL as RateLimit
  participant A as AuthMiddleware
  participant K as CollabMiddleware
  participant R as route FastAPI (editing.py)
  E->>C: eapi.ops(pid, ops, label)
  C->>F: fetch('/api/projects/p1/ops', POST, JSON)
  F->>F: ajoute X-CSRF-Token (jeton de la session)
  F->>Q: met l'écriture en file pour p1
  Q->>F: send() : ajoute If-Match "7"
  F->>RL: requête + cookie de session
  RL->>A: quota 60 s par IP et par session OK
  A->>A: session valide ? Origin = Host ? CSRF = jeton ?
  A->>K: identité posée (scope.state.auth_user)
  K->>K: rôle suffisant ? If-Match = version 7 ?
  K->>R: verrou du projet, la route s'exécute
  R-->>K: 200 {ok, project…}
  K-->>F: ETag "8" ajouté ; version +1 si project.json a changé
  F->>F: noteRev(p1, 8)
  F-->>C: Response
  C-->>E: OpResult
  Note over F,K: si la version a changé : 409 {code: conflict} puis événement ontoforge:conflict
```

Dans le schéma :

1. URL de base : toujours relative (`/api/...`, constante `BASE` dans `frontend/src/api.ts`). Le navigateur parle donc à l'origine qui l'a servi ; c'est ce qui rend CORS inutile en usage normal.
2. Corps : JSON (`Content-Type: application/json` posé par le client) ou `FormData` pour les envois de fichiers (le navigateur fixe le `Content-Type` avec la frontière).
3. Cookie de session : posé par `POST /api/auth/login` ; le navigateur le renvoie seul (même origine, aucun `credentials` à régler). Nom `__Host-ontoforge_session` quand le cookie est `Secure`, `ontoforge_session` sinon (`ONTOFORGE_COOKIE_SECURE=0`, test en http) ; attributs `HttpOnly`, `SameSite=Lax`, chemin `/`. Voir `backend/ontoforge/auth/config.py` et `backend/ontoforge/api/auth.py::login`.
4. Jeton CSRF : renvoyé par `GET /api/auth/session` et par le login (champ `csrf`), gardé dans une variable de module de `AuthGate.tsx`, jamais dans le stockage du navigateur. Ajouté en `X-CSRF-Token` à toute requête `/api` qui n'est pas `GET` / `HEAD` / `OPTIONS`.
5. Contrôle d'origine : côté serveur seulement. Pour une écriture, si `Origin` est présent, son hôte doit être celui de `Host` (ou de `X-Forwarded-Host`) ; sinon 403 `bad_origin`. Un client sans `Origin` (script) passe ce contrôle mais doit quand même fournir le CSRF.

## 4. Détails du protocole {#protocole}

### 4.1 Authentification et CSRF {#auth-csrf}

- Sans authentification (`ONTOFORGE_AUTH` absent, usage local), `GET /api/auth/session` répond `enabled: false` et l'application s'ouvre directement ; aucun jeton, aucun contrôle d'origine.
- Avec authentification (`backend/ontoforge/auth/middleware.py::AuthMiddleware`) : toute route `/api/*` sauf `/api/health` et `/api/auth/*` exige une session valide (401 `auth_required`). Les écritures exigent en plus `Origin` cohérent et `X-CSRF-Token` égal au jeton de la session (403 `csrf`).
- Un `GET` qui écrit : la génération (`GET /api/projects/{id}/generate/{cible}` et `/zip`) écrit l'historique. Elle est traitée comme une écriture des deux côtés : regex `WRITE_GET` dans `AuthGate.tsx`, `csrf_required` / `_WRITE_GET` dans `auth/middleware.py` (décision D-L42-01). Si on ajoute un `GET` qui écrit, il faut modifier **les deux** listes (et `collab/routes.py` côté serveur) : sinon CSRF 403 ou version non envoyée.
- Un 401 hors `/api/auth/*` déclenche l'événement `ontoforge:auth-required` : `AuthGate` oublie le jeton et affiche la page de connexion. Un 403 `password_change_required` déclenche `ontoforge:must-change` (écran de changement du mot de passe provisoire).
- Le login (`frontend/src/auth/Login.tsx`) appelle `fetch` directement : 429 ou 401 avec `retry_after` fait attendre le bouton (compte à rebours), sans rappel automatique.

### 4.2 Version du projet : `ETag`, `If-Match`, 409, 428 {#if-match}

Décision D-L40-01 (concurrence optimiste, sans temps réel).

| Étape | Qui | Détail |
|---|---|---|
| Chargement | `api.loadProject` / `api.getProject` | `GET` avec l'en-tête **interne** `X-OntoForge-Load: 1` ; le `fetch` corrigé le retire avant l'envoi et, à la réponse, fixe la version connue (`forceRev`) d'après `ETag`. |
| Lecture simple | `api.peekProject` | pas d'en-tête de chargement : la version connue ne change pas (affichage seul). |
| Écriture | `window.fetch` corrigé | si une version est connue pour ce projet, ajoute `If-Match: "<n>"` (sauf si l'appelant l'a déjà posé). Les routes `/presence`, `/access`, `/activity` sont exclues (`rev.ts::tracksRev`). |
| Réponse d'écriture | idem | `ETag` lu et mémorisé (`noteRev`, seulement si plus grand). |
| Concurrence locale | `rev.ts::queued` | deux écritures du même projet partent l'une après l'autre dans cet onglet, jamais en parallèle. Le serveur fait de même (verrou par projet). |

Réponses du serveur (`backend/ontoforge/collab/access.py::check_precondition`) :

- 409 `{code: "conflict", current_rev, last_actor, last_at}` : la version envoyée n'est pas la version courante. Rien n'a été enregistré.
- 428 `{code: "precondition_required", current_rev}` : pas d'`If-Match` alors que le projet est partagé et que l'instance a des comptes. Sur un projet non partagé, ou sans authentification, l'absence d'`If-Match` est acceptée (scripts, recettes) ; `If-Match: *` aussi.
- Le front réagit : le `fetch` corrigé lève l'événement `ontoforge:conflict` ; `ConflictDialog` (monté dans `Shell.tsx`) recharge le projet puis **rejoue** l'écriture si elle est dans la liste sûre `REPLAYABLE` de `rev.ts` (opérations, décisions, périmètres, requêtes enregistrées, versions). Pour les autres (PUT du projet entier, import…), le dialogue demande de refaire le geste à la main.
- Un 403 `read_only` sur une écriture lève `ontoforge:readonly` (toast « lecture seule ») ; l'interface désactive déjà les boutons (`collab/readonly.ts::useReadOnlyGuard`), le serveur reste l'autorité.

### 4.3 Présence et sondage {#presence}

`useCollab` appelle `POST /api/projects/{id}/presence` (`api.presence`) à l'ouverture, toutes les 20 s (`BEAT_MS`) tant que l'onglet est visible, et au retour de visibilité. Le serveur oublie un compte après 60 s sans battement. La réponse porte `rev`, `last_actor`, `role` : si `rev` dépasse la version connue et que l'auteur n'est pas l'utilisateur courant, `StaleBanner` propose « recharger » (événement `ontoforge:reload-project`, géré par `Shell.tsx`). Le rôle (`reader`) sert aussi à passer l'interface en lecture seule.

### 4.4 Limiteur de débit et 429 {#limiteur}

`backend/ontoforge/ratelimit.py::RateLimit` : fenêtre glissante de 60 s, par adresse IP et par empreinte de cookie de session. Trois plafonds par minute : global 900, assistant 20, « lourd » 120 (le raisonneur : 10 au plus). Réglables par `ONTOFORGE_RATE_*`, désactivable par `ONTOFORGE_RATE_LIMIT=0` (les tests le coupent dans `backend/tests/conftest.py`). Réponse : 429 `{detail, code: "rate_limited", retry_after}` avec `Retry-After`. Le front **n'a pas de logique de reprise** : le message du serveur s'affiche tel quel (toast ou `ErrorView`). Seul le login décompte l'attente. Derrière nginx ou Cloud Run, l'IP vient de `X-Forwarded-For` au rang `ONTOFORGE_PROXY_HOPS` (1 dans `docker-compose.yml`, 1 par défaut en mode public).

### 4.5 Format des erreurs et traduction {#erreurs}

Tous les refus sont du JSON `{"detail": "...", "code": "..."}` (le `code` est stable, le `detail` est du texte pour l'humain). Exceptions de forme :

- 422 (validation pydantic) : `{"detail": "Entrée invalide — champ : message ; ...", "errors": [...]}` ; construit dans `backend/ontoforge/main.py::_handlers`, sans les valeurs saisies (un mot de passe trop long ne revient pas).
- 503 `{code: "busy", retry_after}` : trop de validations SHACL en parallèle.
- 413 : corps trop gros (`security.BodyLimit`, 32 Mo par défaut ; nginx accepte 50 Mo).
- 501 : module ou fonction absente (`backend/ontoforge/api/_common.py::service`) ; l'écran affiche « bientôt disponible » (`ui.tsx::ErrorView`). Piège : `POST /reason` répond aussi 501 quand l'image est construite sans HermiT (`WITH_REASONER=0`) ; l'écran Conformité affiche alors le message du serveur tel quel, sans « bientôt disponible ».

**Qui traduit quoi.** Le serveur écrit en français et traduit vers l'anglais à la frontière HTTP quand la langue de l'utilisateur est `en` (`backend/ontoforge/localize/__init__.py::ui_lang` : langue du compte, sinon `settings.language.ui`). Le front **n'ajoute rien** : il affiche `detail` tel quel. Il traduit seulement ses propres messages : `ui.http` (« Erreur {s} », corps non JSON) et `ui.unreachable` (le serveur ne répond pas, `status` 0) dans `frontend/src/i18n/fr.json` et `en.json`.

Normalisation côté client : `req` lit `detail` (texte ou liste de `{msg}`), recopie `code` dans `ApiError.code`. Les six autres clients répètent ce bloc avec de légères variantes (voir Pièges).

### 4.6 Téléchargements (blob) {#telechargements}

- Texte (ontologie Turtle, shapes, justification, fichiers générés) : l'API renvoie du texte (`req(..., text = true)`), l'écran appelle `frontend/src/ui.tsx::download(nom, contenu, mime)` qui fabrique un `Blob`, une URL d'objet et un lien `<a download>` cliqué par programme.
- Zip : `api.zip` fait un `fetch` **ordinaire** (donc porteur du CSRF et de la version, c'est une écriture : D-L42-01) et lit `r.blob()` ; `api.downloadZip` crée le lien et révoque l'URL après 4 s. Plus de lien direct `<a href="/api/…/zip">` : il n'aurait ni jeton ni version.
- Export SVG / PNG du graphe : tout est local (`frontend/src/screens/editor/exporter.ts`), aucun appel serveur.

### 4.7 Proxy de développement et production {#proxy}

| Contexte | Qui sert quoi | Détails |
|---|---|---|
| Dev (`npm run dev`) | Vite sur 5173 sert le front ; `server.proxy['/api']` relaie vers `ONTOFORGE_API` (défaut `http://localhost:8000`) | `frontend/vite.config.ts`. Le navigateur reste sur l'origine 5173 : cookies et `Origin` cohérents sans CORS. `À CONFIRMER` : en-tête `Host` conservé par le proxy (réglage `changeOrigin` par défaut de Vite) avec l'authentification activée ; non exécuté ici. |
| `vite preview` (recettes) | même proxy | les recettes interceptent aussi `/api` dans le navigateur vers le backend jetable (`tools/recette/e2e_ui.mjs`). |
| Docker local (`docker compose up`) | nginx (port 8080 du conteneur, publié sur `ONTOFORGE_PORT`, 8088) sert le front et relaie `/api/` vers `backend:8000` | `frontend/nginx.conf` : `Host $http_host` (garde le port : le contrôle d'origine compare `Origin` et `Host`), `X-Forwarded-For $remote_addr`, délai 300 s, corps 50 Mo, `Cache-Control: no-store` sur l'API, en-têtes de `frontend/security-headers.conf`. |
| Cloud Run (production) | un seul conteneur : uvicorn sert l'API **et** le front compilé via `security.SpaStatic` | `deploy/cloudrun/Dockerfile` ; `SpaStatic` renvoie le fichier, ou `index.html` pour les routes du front, 404 JSON pour un `/api/` inconnu, vrai 404 pour un fichier statique absent. |

## 5. Ordre des couches côté serveur {#ordre-middlewares}

Ordre d'exécution d'une requête (de l'extérieur vers la route), tel que construit par `backend/ontoforge/main.py::create_app` :
`RateLimit` → `BodyLimit` → `SecurityHeaders` (si public, authentification ou front servi) → CORS (si `ONTOFORGE_CORS_ORIGINS`) → `AuthMiddleware` (si authentification) → `CollabMiddleware` → routes. Les fichiers statiques sont montés sur `/` dans le routeur : ils passent donc aussi par ces couches, mais `AuthMiddleware` ne s'occupe que de `/api`.

## 6. Côté serveur {#cote-serveur}

Sources lues : `backend/ontoforge/main.py`, `backend/ontoforge/api/__init__.py`, `backend/ontoforge/api/_common.py`, `backend/ontoforge/api/*.py`, `backend/ontoforge/collab/routes.py`, `backend/ontoforge/collab/access.py`, `backend/tests/test_api_contract.py`.

### 6.1 Routeurs {#serveur-routeurs}

`backend/ontoforge/api/__init__.py::ROUTERS` liste les seize routeurs inclus par `create_app` : `system` (`/api/health`, `/api/samples`), `auth`, `projects`, `analysis`, `assistant`, `settings`, `editing`, `business_map`, `files`, `queries`, `local_store`, `versions`, `releases`, `sharing`, `admin`, `schema_import`. Chacun déclare son préfixe (`/api`, `/api/projects/{pid}`, `/api/projects/{pid}/store`, `/api/assistant`…). Il n'y a pas de dépendance FastAPI (`Depends`) pour l'identité ni pour les droits : ils sont posés par les middlewares (section 5) et lus par `backend/ontoforge/collab/access.py::current`.

La liste des chemins du contrat est vérifiée par `backend/tests/test_api_contract.py` ; la classification des routes de projet par `backend/tests/test_collab.py::test_every_route_is_classified` (chapitre [12](12-comptes-partage-admin.md#cloisonnement)).

### 6.2 Forme d'une route {#serveur-forme}

Le motif commun, par exemple dans `backend/ontoforge/api/projects.py` et `backend/ontoforge/api/analysis.py` :

1. Accès et chargement : `backend/ontoforge/api/_common.py::load_project(pid, level)` refait le contrôle d'accès (`access.enforce`) puis lit le projet ; 404 si le projet est inconnu ou inaccessible, 403 si le rôle ne suffit pas.
2. Service paresseux : `service("io.rdf_import", "parse_ontology")` importe le module au moment de l'appel ; un module ou une fonction absente donne 501 `module … pas encore disponible` (héritage du lot L1, où l'API existait avant les modules). `optional_service` renvoie `None` au lieu de lever.
3. Erreurs de lecture : `parse_error(quoi, exc)` transforme une exception de lecture en 422 lisible (message coupé à 800 caractères).
4. Sortie : soit un modèle déclaré (`response_model=Project`, `PGModel`), soit un dictionnaire passé par `dump`, qui sérialise les modèles pydantic **avec leurs alias** (`from`, `in`, `class`). Les textes produits par le moteur passent par `localize` avant de partir (`localize_pg`, `tr_deep`).
5. Calculs longs : les routes `async` qui lisent un fichier délèguent le travail à `run_in_threadpool` (validation SHACL, imports de schémas) pour ne pas bloquer la boucle d'événements. Les routes `def` sont déjà exécutées dans le pool de fils par FastAPI.
6. Écriture : `store.save(p)` (chapitre [13](13-projets-versions.md#ecritures)) ; la version et le journal d'activité sont gérés ensuite par `CollabMiddleware`, pas par la route.

### 6.3 Modèles échangés {#serveur-modeles}

Les corps et réponses principaux sont les modèles normatifs de `backend/ontoforge/core/` (chapitre [03](03-modele-interne.md)) : `Project`, `OntoModel`, `ShapesModel`, `PGModel`. Les corps propres à une route sont de petits modèles pydantic déclarés dans le fichier de la route (`ProjectCreate`, `DslRequest`, `ReasonRequest`, `BranchRequest`, `RunRequest`…). Exceptions : `PUT /decisions/{target}` et `POST /ops` reçoivent un `dict` libre, validé à la main (deux formats acceptés pour rester compatibles). Le front tient ses types miroirs à la main (`frontend/src/api.ts`) : un champ ajouté côté serveur n'y apparaît pas tout seul.

### 6.4 Erreurs HTTP {#serveur-erreurs}

Gestionnaires de `backend/ontoforge/main.py::_handlers` :

| Exception | Réponse |
|---|---|
| `HTTPException` (dont `CollabError`, `AccountError`) | `{detail, …payload}` ; `detail` traduit en anglais si la langue de la requête est `en` ; `CollabError.payload` ajoute `code` et les champs utiles (`current_rev`, `last_actor`, `role`) |
| `ShaclBusyError` | 503 `{detail, code: "busy", retry_after}` et `Retry-After` |
| `RequestValidationError` | 422 `{detail: "Entrée invalide — champ : message ; …", errors}` ; les clés `input`, `ctx` et `url` sont retirées de `errors` (une valeur saisie, un mot de passe par exemple, ne revient jamais) |

Les refus des middlewares (401, 403 `csrf`, `bad_origin`, `admin_only`, `unclassified`, 413, 429) sont écrits directement en JSON par la couche ASGI, sans passer par ces gestionnaires (voir DF-F03 pour la langue).

## 7. Décisions {#decisions}

- D-L40-01 : concurrence optimiste (`ETag` / `If-Match`), 409 explicite, présence sans temps réel, `If-Match` facultatif sur projet non partagé, 428 sur projet partagé.
- D-L42-01 : la génération (et son zip) est une écriture : CSRF, version, file ; le verbe `GET` est conservé pour ne pas casser les clients.
- D-L41-01 : contrôle des adresses sortantes dès que l'authentification est active (détail au chapitre 16).
- D-L39 (SEC-02, SEC-10) : CORS fermé par défaut, limiteur de débit : voir `backend/ontoforge/hardening.py::add_cors`.

## 8. Pièges {#pieges}

- Le `fetch` est modifié globalement, à l'import de `AuthGate.tsx` (garde `window.__ofFetch`). Un test ou un script qui n'importe pas ce module appelle le vrai `fetch` : pas de CSRF, pas de `If-Match`. Toute nouvelle écriture doit passer par `window.fetch` (pas `XMLHttpRequest`, pas `navigator.sendBeacon`).
- Sept clients, un format : `api.ts::req`, `eapi`, `fapi`, `qapi`, `aapi`, `gapi`, `settingsApi` recopient le même bloc d'erreur. Corriger l'un ne corrige pas les autres. `fapi` ne lève jamais (il renvoie `status`) ; les autres lèvent `ApiError`, `SettingsError` ou une simple `Error`.
- Messages d'erreur du réseau codés en dur dans quatre clients (`'Serveur injoignable'`), alors que `ui.unreachable` existe : voir `journal/L51/defauts.md` (DF-F01).
- Messages des couches ASGI en français seulement (CSRF, origine, 413…) : ils ne passent pas par `localize` ; DF-F03.
- Rejeu : n'ajoutez une route à `REPLAYABLE` (`rev.ts`) que si rejouer le corps après rechargement ne peut rien écraser.
- 429 non géré : aucune reprise automatique ; un enchaînement d'appels lourds (analyse, génération) peut afficher une erreur au lieu d'attendre.
- Ajouter un `GET` qui écrit : trois endroits (voir 4.1).
- Présence ≠ version : les trois routes `/presence`, `/access`, `/activity` ne mettent pas à jour la version connue ; si vous en ajoutez de semblables, complétez `tracksRev`.

## 9. Comment ajouter… {#comment-ajouter}

### … un appel d'API (lecture ou écriture) {#ajouter-appel}

1. Côté serveur : route et modèle (voir la section « Côté serveur » plus bas) ; si la route porte `{pid}`, la classer dans `backend/ontoforge/collab/routes.py` (une route de projet non classée est refusée en 403 `unclassified`).
2. Côté front : ajouter la méthode dans le client de la zone, avec son type (miroir du modèle pydantic). Pour un appel général : `frontend/src/api.ts::api`, avec `p(id)` pour l'URL.
3. Une écriture n'a rien de spécial à porter : CSRF et `If-Match` sont ajoutés par le `fetch` global. Un téléchargement binaire : suivre `api.zip`.
4. Texte d'erreur nouveau côté serveur : l'écrire en français et l'ajouter aux tables de traduction (chapitre 12 ou `backend/ontoforge/localize/`), sinon il reste en français en interface anglaise.
5. Test : un test d'API (`backend/tests/test_api_contract.py` donne le modèle) et, si l'écran change, une recette (chapitre 18).

### … un en-tête échangé entre front et back {#ajouter-entete}

Côté front, dans le `fetch` corrigé (`AuthGate.tsx`) ; côté serveur, lire l'en-tête dans la couche concernée ; ajouter le nom à `CORS_HEADERS` de `backend/ontoforge/hardening.py` si l'on veut qu'il passe en CORS.
