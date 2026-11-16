verdict: KO (un bloquant connu, en correction par l'agent mobile)

Recette : `mobile_l44.mjs` (ports 9041/5041) vert, 201 contrôles, local et web. `e2e_ui.mjs` (9043/5043) 30/30 : rien ne change au-delà de 700 px.
Premier passage rouge puis corrigé : « Unable to preload CSS » sur iPad, causé par mon propre `npm run build` lancé pendant la recette (hachages d'assets remplacés), pas par l'appli. Un second passage a échoué sur l'attente de la liste des projets (délai, serveurs tués par un `pkill` concurrent) ; le troisième est vert.

bloquants:
  - [frontend/src/screens/editor/Editor.tsx, graphe mobile ; docs/guide/img/fr|en/mobile-graphe.png ; journal/L44/recette/web-iphone15-graphe-appui-long.png] Scénario : iPhone 15, Ontologie > Graphe. Aucune arête n'est tracée, et le cadrage initial est minuscule (26 nœuds au centre sur 1/4 de l'écran, étiquettes de 5 px illisibles). La capture du guide montre donc le contraire de sa légende (« les étiquettes ne sont pas coupées »). Signalé par Jerem ; en correction par l'agent mobile. Attendus : arêtes visibles, « Tout voir » plein cadre au chargement, recette qui échoue si 0 arête (la recette actuelle ne le détecte pas : elle vérifie l'échelle et le toucher, pas la présence des arêtes), captures du guide régénérées.
non-bloquants:
  - [shell, barre du haut iPad mini 768 px] Le dernier bouton à droite de la barre est rogné par le bord (capture web-ipadmini-graphe.png). La recette mesure « pas de débordement horizontal » sur le document, pas sur la barre. À corriger ou à replier sous le menu.
  - [screens/analysis/Deck.tsx + AssistantDock] Krakie (56 px) recouvre la fin du texte de l'option « Ignorer » sur la carte d'arbitrage (mobile-arbitrage.png). Le défilement le dégage, mais la capture du guide le montre ; ajouter un retrait à droite (padding) du contenu des cartes ou ranger le bouton sur cet écran.
  - [Arbitrer] Incohérence de comptes : badge 42, « 0 sur 42 arbitrés », onglet « À arbitrer 41 » + « Perdus 1 ». Déjà au rapport ; un lecteur y verra un oubli. Afficher la même somme partout (ou expliquer 41 + 1).
  - [Arbitrer, texte d'option] Des accents graves apparaissent en clair : « Arête dérivée `<nom>Transitive` recalculée… ». Venue du texte des règles (backend), à nettoyer côté affichage mobile.
  - [Accueil] La liste Concevoir / Vérifier / Transposer est coupée en bas de la carte sur la capture (défilement interne, pas de signe qu'on peut défiler). Laisser la carte à sa hauteur naturelle.
  - [Plus] Les sous-titres tronqués (« Zones et relations, sc… ») sont raccourcis (voir revue-humain).
OK : navigation par onglets claire, retour, badge, mention « Sur ordinateur » lisible ; fiche (aperçu puis feuille) lisible ; modification limitée présente pour l'éditeur et absente pour le lecteur (badge « Lecture seule ») ; menu d'appui long adapté au rôle ; Krakie plein écran avec puce de contexte, champ à 16 px ; thème sombre propre ; anglais : aucune clé manquante (recette `english_scan` non rejouée ici).
Non vérifiable ici : clavier virtuel et zones sûres sur un vrai iPhone (À VÉRIFIER, déjà au rapport).
skill: les recettes de graphe doivent compter les arêtes rendues, pas seulement l'échelle.
