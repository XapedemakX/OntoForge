# L39-secu : revue de sécurité (secu, 15/11/2026)

**Verdict : OK, avec trois réserves non bloquantes** (L39-01 à L39-03). Chaque correction annoncée a été rejouée avec les scripts d'attaque de l'audit et des variantes ; aucune ne régresse. Détails dans `journal/securite/revue-L39-L40-2026-11-15.md` (non publié). Le durcissement `SpaStatic` non commité est validé. Rappel : la publication prend HEAD, donc L40 (verdict KO, voir `journal/L40/revue-securite.md`) bloque aussi ce lot.

Base relue : commit `146416e` plus `security.py` et les deux fichiers de tests non commités. Recettes : `pytest` 1199 réussis (dont les deux tests SEC-03, qui ne sont plus ignorés), `npm run build` OK.

## Constats de l'audit : rejeu
| SEC | État constaté |
|---|---|
| 01, 02, 12 | Corrigés (liaison locale du compose, CORS fermé, CSP et en-têtes identiques dans nginx et le backend, `Cache-Control: no-store` sur l'API). À vérifier sous Docker par Jerem. |
| 03 | Corrigé : un compte non administrateur n'écrit rien dans les réglages ; le secret est lié à l'origine (schéma, hôte, port) et effacé au changement ; les routes de test n'envoient jamais un secret enregistré ailleurs. |
| 04, 07 | Corrigés : DOCTYPE refusé en 11 variantes (UTF-8, UTF-16 avec et sans BOM, Latin-1, commentaire avant, entités externes et paramètres, TriX), aucun appel sortant ; contexte JSON-LD distant refusé. |
| 05 | Corrigé : délai réellement appliqué (4 s mesurés avec un délai réglé à 4 s), processus supprimé et récupéré (aucun zombie après 9 exécutions, dont 8 en parallèle), arguments fixes, données par l'entrée standard. Réserves L39-01 à L39-03. |
| 06 | Corrigé (plafonds de canonisation et de triplets non reconnus). |
| 08, 17 | Corrigés (liens limités à `http(s)` et `mailto`, aucune image ; données balisées). |
| 10 | Corrigé, voir L39-04 (limiteur : `X-Forwarded-For` forgé inopérant avec un saut de confiance, casse et formes de chemin sans effet). |
| 11, 13, 16, 21 | Corrigés sur les fichiers ; clé maître créée en 600 dans un dossier en 700 ; un fichier de clé préexistant n'est pas resserré (L39-05). |
| 14 | Partiel comme annoncé (condensats d'images À VÉRIFIER). |
| SpaStatic | `//api/…` et `/API/…` répondent 404 JSON, sans donnée, y compris en HTTP brut sous uvicorn avec un compte connecté. Le « P03 » du contre-audit était bien un faux positif : l'ancien comportement renvoyait la page d'accueil du front. Pas de régression constatée sur les routes du front. |

## Constats

| Id | Sévérité | CWE | Composant | Résumé |
|---|---|---|---|---|
| L39-01 | Moyenne (non bloquant) | CWE-770 | `shacl/validate.py:112-130` | Aucun plafond de validations SHACL simultanées : chaque processus peut prendre 2 Go d'espace d'adressage pendant 30 s ; le plafond de débit (120 par minute) laisse des dizaines de processus vivants. Risque d'arrêt du conteneur par manque de mémoire. Le modèle existe déjà dans `conformance/hermit.py:39` (sémaphore). |
| L39-02 | Faible | CWE-833 | `shacl/validate.py:119` | `preexec_fn` dans un processus à plusieurs fils : blocage possible entre `fork` et `exec`, avant que le délai ne s'applique. Appliquer les limites depuis le processus fils lui-même. |
| L39-03 | Faible | CWE-526 | `shacl/validate.py:118` | Le processus fils hérite de tout l'environnement (clé maître, clés d'API). Sans exécution de code attaquant constatée (SPARQL fédéré, `FROM`, `GRAPH` : aucun appel sortant), c'est de la défense en profondeur ; passer un environnement minimal. L'en-tête du module dit « aucun réseau » : ce n'est pas imposé. |
| L39-04 | Info | CWE-770 | `ratelimit.py:43-50` | Les routes `conformance`, `graph`, `ops`, `export`, `files`, `query/values` et les écritures `onto`/`shapes` ne sont limitées que par le plafond global (900 par minute). `.env.example` annonce 30 pour les routes lourdes, le code applique 120. |
| L39-05 | Info | CWE-732 | `settings/crypto.py:68-70` | Un fichier de clé déjà présent avec des droits larges est lu sans avertissement ni resserrement ; `.env` de ce poste est en 644 (déjà signalé au démarrage). |
| L39-06 | Info | CWE-522 | `netguard.py:177` | À la redirection, les identifiants ne sont retirés que si le nom d'hôte change (pas un changement de schéma ou de port). Exige un endpoint hostile enregistré par un administrateur. |
| L39-07 | Info (fonctionnel) | — | `frontend/nginx.conf:12` | `Host $host` perd le port : avec l'authentification activée et le compose sur le port 8088, le contrôle d'origine refuse toute écriture du navigateur (403 `bad_origin`). Utiliser `$http_host`. Non lié à la sécurité du lot, mais bloque l'usage documenté « ouvrir au réseau ». |

## Documentation publique (point 3)
- Aucun détail exploitable, ni secret, ni valeur d'exemple suspecte ; le détecteur de `publish.sh` n'est pas déclenché.
- À reformuler : `journal/L40/rapport.md:28` et `lots/L40.md:27` nomment starlette et python-multipart comme non montés en version (indique des composants vulnérables) ; écrire « montées de dépendances reportées (D-L21-02) ». `lots/L39-secu.md` cite SEC-09 et SEC-18 comme reportés : acceptable sans le détail.
- À corriger : `journal/L39-secu/rapport.md` (« 2 tests ignorés », « SEC-03 à rejouer ») est périmé ; `docs/guide/limites*.md` et CONTRACTS §4 disent « pas de filtrage SSRF, outil mono-utilisateur » alors que `netguard` existe en mode public et que L40 rend l'usage multi-comptes officiel.

## Contre-relecture L41 (15/11)
Verdict : KO (un point bloquant). Les corrections de L40-02 à L40-06 et de L39-01 à L39-07 sont réelles dans le code et vérifiées par rejeu des scripts d'attaque ; les effets de bord de L41 (lecture de la carte métier sans écriture, `generations.json` sous verrou, `ONTOFORGE_EGRESS_ALLOW_INTERNAL`, `childproc.py`) sont corrects. L40-03 est corrigé. L40-01 reste incomplet : un message d'erreur d'appel à un fournisseur LLM enregistré peut encore donner à un compte non administrateur une indication d'adresse. Détail et correction minimale dans `journal/securite/contre-relecture-L41-2026-11-15.md` (non publié). `pytest` : 1254 réussis, 1 test chronométré en échec sous charge et réussi seul ; `npm run build` OK.
