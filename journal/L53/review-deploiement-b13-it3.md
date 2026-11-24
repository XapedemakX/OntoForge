# L53 : relecture déploiement de DF-B13, itération 3

Relecteur : deploy. Branche `lot/L53-b13`, commit ce8cf1d. Lu : `journal/L53/fix-b13-it2.md`, `corrections-b13.md` (section it2), `deploy/cloudrun/env.yaml`, `deploy/cloudrun/README.md`, `backend/tests/test_l53_b13.py`, ainsi que les plafonds d'envoi du code (`security.py`, `assistant/document.py`, `importers/limits.py`, `api/schema_import.py`, `api/files.py`). Aucune commande gcloud lancée. Les 21 tests de `test_l53_b13.py` et `test_l53_b17.py` passent (24/11).

## Verdict

| # | Point | Verdict |
|---|---|---|
| B3 | README §8 : repli `secretAccessor` pour le compte de construction | **OK, levé.** Le repli est retiré. Le texte demande maintenant de vérifier les rôles existants : `run.developer` sur le service et `iam.serviceAccountUser` sur `ontoforge-run` pour le compte de construction, `secretAccessor` pour `ontoforge-run` seulement. L'interdiction est écrite (« Ne jamais donner l'accès aux secrets au compte de construction, ni `roles/run.admin` »). Le repli « retirer `--set-secrets` du déclencheur seulement, puis contrôler avec le §7 » est gardé. Le point À VÉRIFIER `run.developer` / `run.admin` est maintenu, comme demandé |
| R1 | `ONTOFORGE_LOCAL_STORE_MEMORY_MB` = 640 | **OK.** Conforme à la mesure d'it2 (10/10 à 608 et 640 Mo sur une base de 50 000 triplets) |
| R2 | `ONTOFORGE_MAX_BODY_MB` = 12, et non 8 | **OK, l'argument du pilote est vérifié.** Les documents de l'assistant vont jusqu'à 10 Mio (`assistant/document.py`, `ONTOFORGE_DOC_MAX_MB` 10, envoi multipart `UploadFile`). Les imports de schémas vont jusqu'à 10 Mio cumulés par requête (`importers/limits.py::MAX_TOTAL_MB`, contrôlé dans `api/schema_import.py`). Avec 8, ces deux envois permis seraient refusés par l'intergiciel (`security.BodyLimit`) avant d'atteindre leur propre message ; ma proposition d'it2 était donc fausse. 12 Mio couvrent 10 Mio plus l'enveloppe multipart. Les autres envois tiennent dans 12 : ontologies 8 Mo (`api/files.py`), triplestore 5 Mo, assistant 2 Mo. `ONTOFORGE_IMPORT_MAX_MB` peut monter jusqu'à 20 Mo par fichier, mais il n'est pas posé sur Cloud Run (2 Mo par défaut) |
| R3 | Somme 1933 Mo, marge 115 Mo, corps compté | **OK.** 175 + 320 + 256 + 342 + 640 + 124 + 64 + 12 = 1933. Le test ajoute la ligne `corps_de_requete` calculée depuis `env.yaml` et attend 1933. Un seul corps est compté, et les envois simultanés suivants sont pris sur la marge (115 / 12, environ 9 envois avant leur 503) ; c'est écrit dans `env.yaml` et dans le README. Ce choix est acceptable pour une démo : les fils restent comptés à leur plafond d'espace d'adressage, très au-dessus de leur mémoire réelle |
| C1 | Cohérence README / `env.yaml` / test | **OK.** Mêmes lignes et mêmes valeurs (640, 12, total 1933, marge 115) dans le tableau du README, le commentaire et les variables d'`env.yaml`, et dans `cloudrun_worst_case`. La phrase sur les fichiers temporaires de HermiT renvoie bien à la marge de 115 Mo |

**Bloquants : aucun.** Mon verdict de déploiement est OK pour la partie dépôt. La clôture du lot attend toujours le déploiement réel (`deploy-demo.ps1` ou étape 5 complète) et le contrôle du §7 par Jerem.

## Non bloquants (texte)

- `docs/dev/10-triplestore-local.md` et `.en.md`, ligne de `ONTOFORGE_LOCAL_STORE_MEMORY_MB` : la cellule dit bien « Cloud Run : 640 », mais elle finit encore sur « 704 Mo en laissent environ 100 », un reste d'it1. À remplacer par la phrase du README (« 640 Mo laissent environ 30 Mo au-dessus du dernier échec ») dans les deux langues.
- `journal/L53/corrections-b13.md`, section DF-B13 d'origine (tableau « Valeurs retenues » et liste des tests) : on y lit encore 704 et 1985. C'est l'historique et la section it2 donne les bonnes valeurs ; un renvoi « (valeurs finales : section it2) » éviterait une lecture de travers.
- README, ligne du triplestore : « ouvrir la base … 10 essais sur 10 à 608 Mo ». Ma mesure portait sur une requête agrégée (`GROUP BY` / `ORDER BY` / `COUNT`), pas seulement sur l'ouverture de la base, et donnait aussi 9/10 à 576. C'est une précision de formulation, sans effet sur la valeur.
