# L32 : raisonner avec HermiT

Demande de Jerem : « on n'a pas ajouté le raisonneur HermiT pour valider l'ontologie ». HermiT n'était qu'une ligne d'information optionnelle ; il a maintenant un bouton, une route, une carte de résultats et une intention Krakie.

## Ce qui a vraiment été exécuté
- Environnement : `owlready2==0.47` déjà présent dans le venv, Java OpenJDK 21 déjà installé. HermiT 1.3.8.1099 (jar d'owlready2) a donc tourné pour de vrai : 10 tests pytest sur l'API et le module, recette Playwright de bout en bout, aucun test ignoré.
- Non exécuté : les images Docker (Docker indisponible). Le `deploy/cloudrun/Dockerfile` et `backend/Dockerfile` ne sont pas construits ici.

## Réalisé
- `backend/ontoforge/conformance/hermit.py` : lance `org.semanticweb.HermiT.cli.CommandLine` dans un sous-processus Java (classpath d'owlready2, `-Xmx` configurable, groupe de processus tué à l'expiration, dossier temporaire supprimé dans tous les cas, 2 calculs en parallèle au plus). On n'utilise pas `sync_reasoner_hermit` d'owlready2 : il charge un monde en mémoire et ne rend ni durée ni diagnostic.
- `POST /api/projects/{id}/reason` : cohérence, classes insatisfiables, sous-classes et équivalences nouvelles par rapport à la hiérarchie déclarée, individus reclassés, durée, version. 501 explicite sans Java ou sans owlready2, 503 si trop de calculs, délai dépassé = `status: timeout` sans résultat. Hors OWL 2 DL : avertissement en tête, HermiT lancé quand même.
- Incohérence : HermiT en ligne de commande ne fournit AUCUNE justification. OntoForge renvoie des candidats par heuristique syntaxique (individu dans deux classes disjointes, classe insatisfiable évidente, sameAs contre differentFrom) et le dit (`explanation.justification = false`).
- Front : carte dans Conformité (badge, classes insatisfiables cliquables, inférences avec « Ajouter au modèle » par `/ops` annulable, individus reclassés). Le clic ouvre l'éditeur, centre la classe et la met en rouge par le mécanisme d'erreur existant (`lib/reasonerFlags.ts`), avec un bandeau pour effacer.
- Krakie : `assistant/reasoning.py`, branché avant le LLM ; « raisonne », « vérifie la cohérence », « run the reasoner », « check consistency »… en français et en anglais, résumé et bouton vers la carte.
- Images : `deploy/cloudrun/Dockerfile` a `WITH_REASONER=1` par défaut (environ 290 Mo de plus, noté dans le fichier) ; `docker-compose.yml` passe déjà par `backend/Dockerfile`, qui installe Java et `.[reasoner]`. Il n'existe pas de guide de déploiement dans `docs/guide/` : les variables sont documentées dans CONTRACTS §11 et dans le Dockerfile.
- Tests : `backend/tests/test_reason_hermit.py` (cohérente, incohérente, insatisfiable, sous-classe inférée par définition, équivalence, individu reclassé, hors DL, délai avec nettoyage, 501 sans Java et sans owlready2, intention Krakie fr/en) ; ontologies pièges dans `backend/tests/fixtures/reasoner/` (le dossier `samples/trap` reste intact : un test en fixe le contenu).
- Recette : `tools/recette/l32_hermit.mjs`, 7/7, captures dans `journal/L32/screens/` regardées une par une. Deux défauts corrigés grâce aux captures : le corps de la carte était écrasé par une classe CSS `.stack` déjà utilisée ailleurs, et l'éditeur n'avait pas recentré la classe cliquée.

## Gardes
- pytest : 877 passed. `npm run build` : OK. `e2e_ui.mjs` : 30/30 (deux passages précédents à 29/30 à cause de builds concurrents d'autres agents qui remplaçaient `dist/`, 404 sur des assets). `english_scan.mjs` : 0 texte suspect.

## Limites honnêtes
- Pas de justification d'incohérence ; les pistes sont heuristiques.
- Les équivalences inférées ne sont pas ajoutables au modèle : le moteur d'opérations n'a pas d'opération d'équivalence. Les types inférés des individus ne le sont pas non plus (pas d'`add_individual`).
- La hiérarchie inférée est directe (sortie de HermiT) : une sous-classe déjà déclarée par un chemin plus long n'est pas signalée.
- Le périmètre actif n'est pas pris en compte : HermiT raisonne sur toute l'ontologie.

## Relectures
Voir `demande-relectures.md` : w3c (second expert, sémantique), scout (écran), doc, puis humain. Aucune n'est faite à la clôture du pilote.
