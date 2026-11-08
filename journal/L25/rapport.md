# L25 : amorcer une ontologie depuis un document

Pilote : lead (assistant). Origine : veille L21 (`docs/veille/nvidia-auto-ontology.md`, idées N1, N3, N4) et demande de Jerem du 7/11.

## Livré

| Zone | Contenu |
|---|---|
| Backend | `assistant/document.py` (lecture .txt, .md, .pdf par pypdf 7.0.0, limites configurables, découpage, localisation des extraits), `assistant/docheur.py` (repli déterministe fr/en), `assistant/docdraft.py` (questions de compétence, appels LLM, fusion, contrôles, lint W3C, couverture) |
| API | `POST /api/assistant/document/{upload,estimate,draft}` (contrat : `docs/CONTRACTS.md` §9). Aucune route n'applique quoi que ce soit |
| Front | `screens/assistant/{DocImport,DocResult,ProposalCards}.tsx` + `doc.css` ; bouton dans l'Assistant et dans le panneau Krakie, dépôt d'un PDF dans la conversation ; cartes de proposition avec extrait source repliable, badge « À confirmer », Accepter / Rejeter / Tout accepter ; questions avec badge Couvert / Non couvert |
| Exemple | `samples/automaint/automaint-cahier-des-charges.pdf` (2 pages, fr) et `make_cahier_des_charges.py` (reportlab s'il est installé, sinon PDF écrit à la main ; le fichier versionné est celui à la main) |
| Dépendance | `pypdf==7.0.0` dans `backend/pyproject.toml`. Il n'existe pas de `requirements.txt` ; le Dockerfile fait `pip install ".[reasoner]"`, donc il l'installe |
| Tests | `backend/tests/test_document_draft.py` (21 tests) ; `tools/recette/l25_document.mjs` (21 contrôles) ; captures dans `journal/L25/screens/` |
| Docs | `docs/CONTRACTS.md` §9, `docs/guide/utilisateur.md` section « Amorcer depuis un document » |

## Choix et limites à connaître

1. « Aucun appel réseau » s'entend comme : rien vers un service hébergé. `mock` et le repli n'appellent rien (test avec httpx remplacé par un faux qui échoue) ; `ollama` n'appelle que l'URL locale configurée (test qui relève les URL appelées). Les fournisseurs `anthropic` et `openai_compat` sont traités comme hébergés : l'API répond 409 sans `confirm_hosted`, et l'interface demande une case à cocher après avoir affiché appels et caractères estimés.
2. Individus exclus du brouillon : le moteur d'opérations n'a pas d'`add_individual`. Classes, relations et propriétés de données sont tracées.
3. Pas d'OCR : un PDF sans couche texte est refusé (422), de même qu'un PDF chiffré.
4. Extrait obligatoire et vérifié : un élément dont l'extrait n'est pas retrouvé dans le document est écarté (anti-invention). La page affichée est celle où l'extrait se trouve, pas celle annoncée par le modèle. Un texte .txt / .md est découpé en « pages » virtuelles d'environ 3 000 caractères.
5. Repli approximatif : sur le PDF de démo il trouve Véhicule, Garage, Pneu, Contrôle technique, Voiture, Pièce, 3 relations et 12 propriétés de données. Il ne connaît que des tournures simples ; un nom propre composé est ignoré ; les libellés ne sont donnés que dans la langue du document, d'où 21 avertissements W07 « libellé manquant » (regroupés dans l'interface).
6. Couverture des questions : un mot significatif en commun avec un nom ou un libellé suffit. C'est volontairement large : « non couvert » signale un vrai trou, « couvert » ne garantit pas que la question trouve sa réponse. La couverture est calculée à l'analyse, pas recalculée quand on accepte ou rejette.
7. Correction d'un défaut existant : `lib/proposal.ts` appliquait les éléments dans l'ordre de la liste, donc un enfant avant son parent donnait « Classe parente inconnue » avec Tout accepter. Les éléments dont dépend un autre passent désormais d'abord.
8. Incident : mon premier script d'ajout de clés i18n a vidé `fr.json` (ouverture en écriture avant lecture). Le lead l'a réparé ; les clés `doc.*` ont ensuite été ajoutées par écriture atomique.
9. À VÉRIFIER : le comportement de pypdf 7.0.0 sur des PDF réels (colonnes, tableaux) : seul le PDF de démo et des PDF sans texte ont été essayés. La visite guidée n'est pas touchée.

## Vérifications

pytest 663 verts ; `npm run build` vert ; `node tools/recette/e2e_ui.mjs` 30/30 ; `node tools/recette/english_scan.mjs` : 64 vues, 0 texte français ; `node tools/recette/l25_document.mjs` : tous les contrôles OK. Les écrans du flux (import, estimation, questions, cartes, panneau Krakie) ont aussi été relus en anglais à la main : seuls l'extrait et les questions du document restent dans la langue du document, ce qui est voulu.

## Relectures demandées (non faites par le pilote)

- w3c : qualité OWL du brouillon (hiérarchie, domaines et portées, usage du lint) ; `journal/L25/review-w3c-it1.md`.
- scout : UX des cartes, du badge « à confirmer », de l'avertissement de confidentialité ; captures dans `journal/L25/screens/` ; `review-scout-it1.md`.
- doc : exactitude de CONTRACTS §9 et du guide ; `journal/L25/doc-ok.md`.
- humain : passe de style sur la doc du lot, puis vérification du sens par doc.
