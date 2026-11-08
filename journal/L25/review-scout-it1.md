verdict: OK
bloquants:
  - aucun. Le parcours complet tient en une minute avec le PDF de démo, et la recette `l25_document.mjs` passe (22/22). Les points ci-dessous rendent la démo plus nette et préparent les vrais documents (30 éléments et plus).
non-bloquants:
  - [ProposalCards.tsx, liste `.as-items`] lisibilité à 30 éléments : une carte fait environ 83 px, donc 5 cartes visibles sur 1440×900 (capture 03). À 30 éléments il faut 6 écrans de défilement, sans regroupement ni filtre, et 21 boutons « Extrait source » à ouvrir un par un. Proposition (M) : grouper par classe (la classe, puis ses attributs et ses relations en lignes d'une hauteur), afficher la 1re ligne de l'extrait en gris sous le nom sans clic, et ajouter un filtre Classes / Relations / Attributs avec compteurs. Inspiration : la liste de mapping de Neo4j Data Importer, et les « suggestions » de Protégé Cellfie.
  - [ProposalCards.tsx `LintSummary`] « Contrôle W3C : 21 avertissement(s) » en orange, sur un brouillon sain, inquiète en démo. Les 21 avertissements disent « pas de libellé en anglais ». Afficher plutôt une ligne d'info « Libellés en fr seulement (langue du document) » et réserver l'orange aux vrais constats. Même avis côté w3c.
  - [DocResult.tsx, badge « Non couvert »] le badge et la ligne « Aucun terme du brouillon ne correspond à cette question » se comprennent (capture 03, « Quel mécanicien… »). Il manque l'action suivante : un bouton « Proposer des termes pour cette question » qui relance l'assistant sur la question et ses phrases du document. « Couvert » est trompeur dans un cas : « date du dernier contrôle » est couvert par « date d'achat ». Une infobulle « couvert = au moins un mot en commun, à vérifier » suffirait.
  - [DocImport.tsx] démo en 1 minute : il faut aller chercher `samples/automaint/automaint-cahier-des-charges.pdf` dans le sélecteur de fichiers, ce qui fait perdre 15 à 20 s devant un client. Ajouter un lien « Essayer avec le cahier des charges de démo » dans la zone de dépôt (S). Chrono estimé sinon : ouvrir l'Assistant, Amorcer, déposer, Lancer (≈ 1 s en repli), lire les questions, Examiner, Tout accepter, Voir dans l'éditeur = 7 actions, ≈ 45 s.
  - [index.tsx / AssistantDock] deux entrées voisines, « Brouillon depuis ce fichier » et « Amorcer depuis un document », avec des libellés proches. Pour un nouvel utilisateur, rien ne dit laquelle prendre pour un PDF. Proposition : une seule entrée « Importer un fichier » qui choisit le traitement selon le type (CSV/SQL → squelette, txt/md/pdf → amorçage avec questions).
  - [DocImport.tsx, confirmation d'envoi] le chemin « fournisseur hébergé » (case à cocher, appels, caractères) n'a pas de capture : la recette tourne en mock. Ajouter une capture avec un fournisseur factice hébergé, puisque c'est l'écran que Jerem montrera pour rassurer sur la confidentialité. Bon point : la case est décochée à chaque nouveau fichier ou changement de fournisseur (DocImport.tsx l. 29 et 36), le consentement porte donc sur un envoi précis.
  - [captures 03, 04, 08] le bandeau « Seul le fournisseur de démonstration… » recouvre la première ligne du message de l'assistant (« J'ai lu… » coupé). Sur mobile (08), il prend un tiers de la hauteur et le toast « 1 élément(s) à confirmer » masque le bouton Envoyer ; idem dans Krakie (07), où le toast cache l'aide sous la saisie. Défaut antérieur à L25, mais très visible dans ce flux.
  - [capture 06, éditeur] après « Tout accepter », les 12 propriétés de données ne se voient pas dans le graphe (seulement « 4 attr. » dans l'aperçu de la proposition). Un message final « 6 classes, 3 relations, 12 attributs ajoutés, voir la vue liste » fermerait la boucle de la démo.
  - [capture 07, Krakie] « 20 élément(s) déjà présent(s) dans l'ontologie, non reproposé(s) » après une première acceptation : clair et utile. Garder.
skill: skills/product-discovery/SKILL.md : ajouter au gabarit de revue d'écran le « test des 30 éléments » (densité d'une liste de propositions à volume réaliste, pas seulement sur l'exemple) et le « test de la démo chronométrée » (actions et secondes, chemin vers le fichier de démo compris).

## Parcours relu (captures journal/L25/screens/, recette relancée)

| Étape | Clair ? | Remarque |
|---|---|---|
| Déposer (01) | oui | glisser-déposer et bouton, formats annoncés |
| Estimer (02) | oui | « Analyse locale sans LLM… rien n'est envoyé hors de cette machine » : rassurant et précis |
| Confirmer l'envoi | non vu | pas de capture du cas hébergé (voir plus haut) |
| Questions de compétence (03) | oui | 4 sur 5 couvertes, badge vert / orange lisible |
| Cartes à confirmer (03, 04) | oui à 21, juste à 30 | badge « À confirmer » partout, extrait replié, page affichée |
| Appliquer (05) | oui | élément par élément, rejet, Tout accepter |
| Voir dans l'éditeur (06) | oui | hiérarchie Pièce > Pneu, Véhicule > Voiture et relations visibles |
| Krakie (07) et mobile (08) | oui | même flux, toast gênant |
