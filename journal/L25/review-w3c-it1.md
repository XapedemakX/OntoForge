verdict: OK
bloquants:
  - aucun restant. Six écarts avérés et simples ont été corrigés pendant la relecture (voir « Corrigé par le relecteur ») ; le pilote les relit dans fix-it1.
non-bloquants:
  - [backend/ontoforge/assistant/docheur.py, motifs « X a un Y »] noms de propriétés génériques (`date`, `reference`, `dimension`) avec un seul rdfs:domain. rdfs:domain est global (RDF Schema 1.1 §3.2.2) : dès qu'une 2e classe aura une `date`, l'inférence la classera ControleTechnique. Proposer `dateControle`, `referencePneu`, ou laisser le domaine vide et passer par une forme SHACL. La fusion signale maintenant le conflit, elle ne le règle pas.
  - [docheur.py, `name = "possede" + …`] la relation tirée de « est équipé de » s'appelle `possedePneu` / « possède pneu » : le verbe du texte (`estEquipeDe`) serait plus fidèle. Le choix relation plutôt que sous-classe est juste (partie-tout ≠ rdfs:subClassOf), vérifié par test.
  - [docheur.py] « date d'achat » donne `dateDachat` : retirer les élisions (d', l') avant le camelCase → `dateAchat`.
  - [lint W07 sur le brouillon] les 21 avertissements « label manquant en en » disent une seule chose : le document est en français. L'interface les regroupe (W07 ×21) mais le titre orange « Contrôle W3C : 21 avertissement(s) » inquiète à tort. Proposition : sortir W07-labels du compteur, afficher une ligne d'info « 21 éléments n'ont de libellé qu'en fr (langue du document) », et garder le compteur pour les vrais constats. Les autres W07 (versionIRI, préfixes) ne portent pas sur le brouillon et sont déjà filtrés.
  - [convert.py `_comments`] un `comment` sans langue reste @fr pour tout l'assistant conversationnel (hors L25). Corrigé seulement dans le chemin document (suit la langue du document).
  - [docdraft.py cycle] la remontée dans l'ontologie existante ne suit que `sub_class_of[0]` : en héritage multiple un cycle peut passer. Sans effet aujourd'hui (une classe existante n'est jamais reparentée par le brouillon), à reprendre si cela change.
  - [document.py `locate`] un extrait à cheval sur deux pages n'est pas retrouvé et l'élément est écarté. Acceptable (prudent), à signaler dans le guide.
  - [ProposalCards.tsx] `<blockquote lang="">` : renseigner la langue détectée du document (BCP 47) pour les lecteurs d'écran.
skill: ajouter à skills/w3c-ontology-conformance/SKILL.md, section « brouillons générés » : (1) une IRI = une seule sorte d'entité, vérifier contre l'ontologie existante ET le brouillon (SS §5.9) ; (2) le langString suit la langue de la source, jamais celle de l'interface ; (3) un nom local qui commence par « http » n'est pas une IRI absolue ; (4) lint d'un brouillon : filtrer par sorte d'entité, pas par IRI, sinon une erreur de punning sur une IRI existante est masquée.

## Ce qui a été vérifié

| Point | Résultat | Test |
|---|---|---|
| IRIs sur la base du projet | oui, sauf noms locaux commençant par « http » (corrigé) | `test_to_onto_never_makes_relative_iris` |
| Accents et ligatures | accents repliés en ASCII dans l'IRI, gardés dans le libellé ; œ/æ/ß perdus (corrigé) | `test_ligatures_are_transliterated` |
| Collisions | « !!! », « 車 », « 車車 » fusionnaient en une classe `X` (corrigé) ; punning objet/données (corrigé) | `test_trapped_llm_output_duplicate_cycle_invalid_iri` |
| Libellés et langue | langue de l'interface au lieu de celle du document, nom local en @en (corrigé) | `test_labels_follow_document_language_not_ui`, `test_english_document_comment_is_tagged_en`, `test_inverse_label_in_document_language` |
| Domaines, portées, XSD | justes sur la démo ; `dimension` était xsd:decimal (corrigé → string) | `test_demo_owl_quality` |
| Hiérarchie | Voiture ⊂ Véhicule, Pneu ⊂ Pièce ; « équipé de » en relation ; aucun cycle ; cycle à 3 cassé sur une seule arête | `test_demo_owl_quality`, test piégé |
| Lint appliqué au brouillon | oui ; 21 W07 = 1 par élément, sujets = éléments du brouillon. Mais une erreur W04 sur une IRI existante était filtrée (corrigé) | `test_lint_reports_punning_on_existing_iri` |
| Extrait source | mot pour mot sur la page annoncée, ≤ 300 caractères, pour les 21 éléments | `test_demo_excerpts_are_verbatim_on_their_page` |
| Fusion entre morceaux | doublons fusionnés ; un 2e domaine différent était perdu en silence (signalé désormais) | `test_merge_signals_conflicting_domains` |
| Sortie LLM piégée | doublon de l'existant → `skipped` ; cycle → arête retirée ; IRI invalide → écartée ; extrait inventé → écarté (test du pilote) | test piégé |
| Confidentialité | 409 sans `confirm_hosted` par l'API, aucun appel avant ; mock sans réseau (test du pilote). Un Ollama distant passait pour local (corrigé) | `test_api_hosted_provider_409_without_confirmation`, `test_remote_ollama_counts_as_hosted` |

## Corrigé par le relecteur

1. `assistant/convert.py` : `ciri` / `piri` / range / annotations testaient `startswith("http")`. Une propriété `httpUrl` ou `httpsEndpoint` devenait l'IRI relative `httpUrl` (RFC 3987, RDF 1.1 Concepts §3.2 : IRI absolue exigée). Nouveau `is_absolute_iri` (`http://`, `https://`, `urn:`), aussi utilisé par docdraft. Touche aussi l'assistant conversationnel, dans le bon sens.
2. `assistant/docdraft.py` `_valid_name` : un nom sans lettre latine donnait « X » ; plusieurs se fusionnaient en une seule classe avec le libellé de l'une d'elles. Ils sont maintenant écartés avec motif.
3. `docdraft.py` `consolidate` : une propriété de données de même IRI qu'une propriété objet (existante ou du brouillon) était gardée. Le punning objet/données est interdit en OWL 2 DL (SS §5.9). Elle est écartée, avec un message qui demande un renommage.
4. `docdraft.py` `_lint` : `mine` retirait toute IRI déjà présente dans l'ontologie, quelle que soit sa sorte, donc l'erreur W04 ci-dessus disparaissait. Le filtre se fait maintenant sorte par sorte.
5. `docdraft.py` : libellés des classes citées mais non déclarées, des éléments sans libellé et des inverses, et commentaires sans langue, dans la langue du document (`docheur.detect_lang`) et non celle de l'interface. Le nom local n'est plus posé en @en (« MainDUvre »@en devient « Main d'œuvre »@fr).
6. `assistant/naming.py` : œ, æ, ß translittérés (NFKD ne les décompose pas) : « main-d'œuvre » → `MainDOeuvre` et non `MainDUvre`.
7. `docdraft.py` `_merge_into` : un domaine ou une portée différents venus d'un autre morceau étaient ignorés en silence. L'écart est maintenant signalé.
8. `docdraft.py` `is_hosted` : un Ollama dont l'URL n'est pas locale (IP ou nom avec un point) est traité comme hébergé : estimation, case à cocher et 409. Boucle locale, `host.docker.internal` et nom de service sans point (`ollama` en docker compose) restent locaux.
9. `docheur.py` : « dimension » retiré des mots décimaux (la dimension d'un pneu, « 205/55 R16 », est une chaîne).

Tests : `backend/tests/test_document_draft_review.py` (18 tests). pytest 743 verts, `npm run build` vert, `l25_document.mjs` 22/22.
