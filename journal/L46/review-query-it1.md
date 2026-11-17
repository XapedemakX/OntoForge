# Revue query (SSRF, netguard, httpx), lot L46, itération 1

Relecteur : query. Date : 17/11/2026. Commit relu : f358c82 (branche lot/L46). Venv du lot `.venv-l46` (Python 3.13, fastapi 0.133.0, starlette 1.3.1, python-multipart 0.0.31, httpx 0.28.1, httpcore 1.0.9, uvicorn 0.32.1).

verdict: OK

bloquants:
  - aucun

non-blocants:
  - [backend/ontoforge/netguard.py:193] `guarded_client` remplace `transport._pool._network_backend` (attribut privé d'httpx/httpcore). Le contrôle ne dépend pas de FastAPI ni de Starlette, mais il casserait silencieusement à une montée d'httpx/httpcore. Le test `tests/test_netguard.py` le couvrirait (il échouerait), et j'ai vérifié que le backend en service est bien `_GuardedBackend` avec httpx 0.28.1. À garder en tête pour toute montée d'httpx : Starlette 1.3.1 accepte `httpx<0.29.0,>=0.27.0` pour son TestClient, donc la prochaine borne à surveiller est 0.29.
  - [journal/L46/rapport.md:42] « netguard inchangé » est exact (`git diff HEAD~1 HEAD -- backend/ontoforge` est vide) ; le rapport pourrait ajouter que les tests SSRF ont été rejoués contre un serveur réel et pas seulement par TestClient (c'est ce que je fais ci-dessous).
  - [tests] aucun test automatique ne fait de requête sortante réelle avec redirection vers une adresse interne par le serveur uvicorn : la couverture vient de `test_netguard.py` (transport simulé). Je l'ai rejouée à la main (voir « Preuves ») ; un test avec serveur local temporaire (port éphémère, `ONTOFORGE_EGRESS_ALLOW_INTERNAL=127.0.0.1`) pourrait être ajouté dans un lot ultérieur.
  - [backend/tests] 1718 avertissements en suite complète (DeprecationWarning d'anyio dans `starlette/testclient.py:53`, pyparsing dans rdflib) : sans effet, à surveiller.

skill: skills/graph-query-translation : rien. À ajouter dans skills/audit-securite-cve-cwe (secu) : « après toute montée de FastAPI/Starlette/httpx, rejouer les refus SSRF contre un backend réel sous uvicorn (mode public + authentification), avec un serveur de redirection local, en plus des tests simulés ».

## Preuves

- Suite complète depuis `backend/` avec `.venv-l46` : **1307 réussis**, 0 échec (8 min 02 s). Tests ciblés `test_netguard.py`, `test_sec_network.py`, `test_sec_settings.py`, `test_sec_front.py` : 68 réussis.
- Backend lancé hors dépôt sous l'utilisateur `nobody`, `ONTOFORGE_PUBLIC=1`, `ONTOFORGE_AUTH=password`, port 9246, liste blanche volontairement large (`example.com,127.0.0.1,localhost,169.254.169.254,metadata.google.internal,10.0.0.1,rebind.test`) pour que le contrôle d'adresse soit celui qui refuse. Connexion avec jeton CSRF et `Origin`, puis `POST /api/settings/sparql/test` :
  - refusés avec le message prévu : `http://127.0.0.1/`, `http://localhost/`, `http://169.254.169.254/computeMetadata/v1/`, `http://metadata.google.internal/`, `http://10.0.0.1/`, `http://2130706433/` et `http://0x7f.1/` (écritures numériques), `http://[::1]/`, `http://[::ffff:127.0.0.1]/`, `http://[::ffff:a9fe:a9fe]/` (IPv4 encapsulée), `http://0.0.0.0/`, `http://100.64.0.1/`, `http://user:pw@example.com/` (identifiants) ;
  - `file:///etc/passwd` et `ftp://example.com/` : 422 (schéma refusé dès la validation) ;
  - hôte absent de la liste blanche (`evil.example.org`, `127.0.0.1.nip.io`) : refusé ; nom qui ne se résout pas : message d'injoignable, rien d'émis.
  - `POST /api/projects/{pid}/query/endpoint-test` vers 169.254.169.254 : refusé. Endpoint enregistré `http://10.0.0.1/sparql` puis `POST /api/settings/endpoints/{id}/test` : refusé avec le message sans hôte ni adresse (conforme à L41/L40-01).
  - `GET /api/projects` sans session : 401.
- Redirections et rebinding, appelés directement sur `netguard.request` avec un serveur local de redirection (port 5246, premier saut autorisé par `ONTOFORGE_EGRESS_ALLOW_INTERNAL=127.0.0.1`), en GET et en POST : 302 vers `http://169.254.169.254/`, `http://10.0.0.1/`, `http://localhost:5246/`, `http://[::ffff:169.254.169.254]/`, `http://2130706433:5246/`, `file:///etc/passwd` : tous refusés au saut concerné ; boucle de redirections : arrêt après 3 sauts (« Trop de redirections ») ; redirection relative vers un chemin légitime : suivie (200). Sans la liste interne, la boucle locale est refusée dès le premier saut. Nom résolu vers 10.1.2.3 : refusé ; réponse DNS mélangée (adresse publique + 127.0.0.1) : refusée (toutes les adresses sont contrôlées) ; la connexion passe bien par `_GuardedBackend` (adresse épinglée).
- Aucun fichier de `backend/ontoforge` n'a changé dans f358c82 : netguard, security, collab/middleware et api/analysis sont ceux d'avant la montée, et se comportent à l'identique sous Starlette 1.3.1.
