# L25 : corrections it1 (lead)

Les deux revues (w3c, scout) sont OK, sans bloquant. Traité ici : les non-bloquants utiles à la démo.

| # | Point | Fait |
|---|---|---|
| 1 | 21 W07 « libellé manquant en anglais » | `LintSummary` sort W07 du compteur : une ligne d'information grise et repliable (« 21 libellé(s) absent(s) dans l'autre langue de l'interface »), avec l'explication. L'orange et « Contrôle W3C : n avertissement(s) » ne servent plus qu'aux vrais constats ; sans constat : « aucun avertissement » en vert. |
| 2 | 30 éléments | `ProposalCards` : groupes Classes (sous-classes comprises), Relations, Propriétés de données, avec compteurs, repliables ; filtre texte (nom, détail, extrait) dès 8 éléments ; « Tout accepter » par groupe (`acceptIds`, nouveau dans lib/proposal.ts, dépendances acceptées d'abord) ; une ligne de 30 px par élément, extrait déplié au clic sur le nom ; l'aperçu du graphe est replié pour un brouillon issu d'un document. Mesuré par la recette à 1440×900 : 12 éléments visibles (contre 5). |
| 3 | Lien de démo | `GET /api/assistant/document/demo` (lecture seule, nom de fichier fixe, 404 si absent) et lien « Essayer avec le cahier des charges de démo » sous la zone de dépôt (plein écran et Krakie). Un clic, 0,3 s jusqu'à l'estimation. Tests : `test_demo_document_route_is_read_only_pdf`. |
| 4 | Toast et bandeau mock | Bandeau : le texte coupé n'était pas un recouvrement mais le défilement du journal sur le début du résultat ; le journal montre maintenant le début du message « J'ai lu… » pour un résultat de document, et `.as-note`, `.as-head`, `.as-compose` ne se compriment plus (`flex-shrink: 0`). Toast : sorti du coin bas droit (il cachait Envoyer), placé dans la zone vide de la barre du haut sur ordinateur, en haut sur mobile, `pointer-events: none`. |
| 5 | Capture « fournisseur hébergé » | `l25_document.mjs` crée un fournisseur `anthropic` factice (clé bidon), le choisit, charge la démo : avertissement et case à cocher (captures `09-hosted-avant.png` case décochée, bouton grisé, et `09-hosted.png` case cochée). Aucun appel n'a lieu (estimation seule) ; la recette vérifie aussi la 409 sans confirmation et zéro requête hors machine. |

Repris des non-bloquants w3c : l'attribut `lang` du `<blockquote>` suit la langue détectée du document (`document.lang`, ajout à la réponse de `/document/draft`). Non traités, hors démo : noms de propriétés génériques, élisions « dateDachat », « Proposer des termes » pour les questions non couvertes, entrée unique « Importer un fichier », message final de fin de boucle. Ils restent à planifier.

Gardes : pytest 755 verts (pas de nouvelle régression), `npm run build` vert, `l25_document.mjs` 0 KO (35 contrôles), `e2e_ui.mjs` 30/30, `english_scan.mjs` 0 suspect. Captures relues : le bandeau, la liste à 12 lignes, le panneau Krakie et le mobile sont lisibles.
