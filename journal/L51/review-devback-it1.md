# L51 : relecture de devback, itération 1 (chapitres de devfront : 01, 02, 15, 17, 18, README)

Portée : exactitude des affirmations qui touchent le backend, les tests, la CI et le déploiement, vérifiées dans le code et par exécution (venv des agents, Python 3.13). Le chapitre 15 (front) n'a été relu que pour ses interactions avec le serveur ; son contenu propre au front relève de mobile, scout et doc. Tests de doc : `pytest -q tests/test_dev_docs.py tests/test_docs_bilingual.py` vert (203 passés) après la livraison des chapitres de devback.

verdict: OK
bloquants:
  - aucun
non-bloquants:
  - [docs/dev/01-vue-ensemble-demarrage.md, §3, §5.3 ; docs/dev/18-tests.md, en-tête et §3] « 1412 tests collectés » : `pytest --collect-only -q` donne 1607 le 23/11 après la livraison des chapitres 03 à 16 (les tests de doc sont paramétrés par fichier et par citation). → dater sans nombre exact, ou « environ 1600 au 23/11 », ou citer seulement l'ordre de grandeur (le skill technical-documentation déconseille les nombres qui bougent).
  - [docs/dev/01-vue-ensemble-demarrage.md, §5.2] « reasoner : seulement pour HermiT (Java 21 requis) » : le code n'exige aucune version (`conformance/hermit.py::locate` cherche `java` dans le PATH) ; Java 21 est la version testée ici, l'image installe `default-jre-headless`. → « Java requis (21 testé) ».
  - [docs/dev/18-tests.md, §3, tableau] `test_localize*` : aucun fichier de ce nom (seul `test_english.py` et `test_generation_lang.py`). La docstring de `localize/__init__.py` cite un `test_localize_en.py` absent (DF-B11). → retirer `test_localize*` de la ligne.
  - [docs/dev/18-tests.md, §2] `conftest.py` « isole `ONTOFORGE_DATA` dans un dossier temporaire de session » : vrai seulement si la variable n'est pas déjà posée (`os.environ.setdefault`). Un `ONTOFORGE_DATA` exporté dans le shell fait écrire les tests dans ce dossier. → ajouter ce piège au §10.
  - [docs/dev/README.md, ligne du chapitre 11] « agent, outils, fournisseurs LLM » : Krakie n'utilise pas d'appel d'outil natif (sortie JSON par consigne, actions revalidées). → « agent, actions proposées, fournisseurs LLM, garde-fous ».
  - [docs/dev/02-communication-front-back.md, §5] ordre des middlewares : exact (vérifié dans `main.py::create_app` et `hardening.install`). Rien à changer ; la section 6 « Côté serveur » est maintenant remplie par devback.
  - [docs/dev/17-build-ci-deploiement.md, §6] « le triplestore local vit dans `/tmp` » : exact, par `ONTOFORGE_LOCAL_STORE_DIR=/tmp/ontoforge-triplestore` posé dans `deploy/cloudrun/Dockerfile` (lu par `localstore/store.py::local_dir`). → citer la variable, pour qu'un lecteur sache d'où vient le comportement.
  - [docs/dev/17-build-ci-deploiement.md, §7] la liste des familles de secrets recherchées par `publish.sh` est utile, mais n'ajoutez pas les motifs exacts ni la liste des clés d'exemple autorisées (sans intérêt pour un développeur, utile à qui voudrait passer le filtre).
skill: technical-documentation : ajouter « un nombre de tests ou de constats cité dans un manuel bouge dès qu'on ajoute un chapitre paramétré : écrire l'ordre de grandeur et la date ».
