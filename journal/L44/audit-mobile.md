# L44 — Audit mobile (phase 1)

Agent : mobile — 16/11/2026. Aucune modification de l'application dans cette phase.

## Méthode

- Outil : `tools/recette/mobile_audit.mjs`, avec Playwright (Chromium) et les profils d'appareils de Playwright : **iPhone 15** (393 × 659 utiles, DPR 3), **Pixel 7** (412 × 839), **iPad Mini** en portrait (768 × 1024). Tactile activé, `isMobile`, langue fr-FR.
- Deux versions de l'application :
  - **web**, reproduite par `tools/recette/web_server.mjs`, qui a été vérifié et sert tel quel : uvicorn sert l'API et le front compilé ; on retrouve les variables du Dockerfile Cloud Run et de `deploy/cloudrun/env.yaml`, l'authentification par mot de passe, un frontal HTTPS avec certificat auto-signé, la CSP et un cookie `__Host-` ;
  - **locale**, avec l'option `--local` : backend sans authentification, en-têtes de `frontend/security-headers.conf`.
- Ports `BACKEND_PORT=9021`, `FRONT_PORT=5021`. Les comptes jerem (administrateur), alice et bob, la clé secrète et les mots de passe sont tirés au hasard à l'exécution. Projet « Automaint » créé depuis `samples/automaint`.
- Parcours : connexion, projets, tiroir de navigation, tableau de bord, ontologie (éditeur graphique et vue liste), carte métier, analyse et arbitrage, modèle cible, exports, requêtes, assistant, versions, SHACL, fichiers, Krakie ouvert, partage, paramètres, administration. Thème clair sur les trois appareils, sombre sur l'iPhone 15.
- Mesures automatiques par écran : éléments interactifs visibles dans la fenêtre, cibles de moins de 44 px, débordement horizontal, textes coupés (ellipse), champs en moins de 16 px, éléments recouverts par Krakie ou l'aquarium, erreurs de console et violations de CSP.
- Gestes sur l'éditeur graphique et la carte métier, envoyés par CDP (`Input.dispatchTouchEvent`) : glisser à un doigt, pincer à deux doigts, toucher un nœud, appui long de 900 ms.
- Toutes les captures ont été regardées une par une. Elles sont dans `journal/L44/avant/` (réduites à 480 px de large, 640 px pour l'iPad). Mesures brutes : `avant/mesures-web.json` et `avant/mesures-local.json`.

Relance : `cd frontend && npm run build`, puis `BACKEND_PORT=9021 FRONT_PORT=5021 node tools/recette/mobile_audit.mjs [--local] [--devices=iphone15,pixel7,ipadmini] [--dark]`.

## Les 5 constats majeurs

1. **L'en-tête et les bandeaux prennent la moitié de l'écran.** Sur téléphone, l'en-tête d'un projet fait 3 lignes (115 px sur 659) : menu, logo, fil d'Ariane, cible Curiosity/Neo4j, périmètre, avatar, présence, endpoint SPARQL, aide, visite guidée, thème, compte, déconnexion. Les écrans d'édition ajoutent le bandeau « Sur mobile, cet écran est en consultation… » (environ 60 px). Sur l'éditeur graphique viennent ensuite 4 lignes d'outils et la légende, ouverte par-dessus le canevas : **le premier nœud n'apparaît qu'à 49 % de la hauteur**. Sur la carte métier, le dessin commence sous un titre, deux lignes de commandes et un message d'aide de 3 lignes. Captures : `iphone15-clair-04-ontologie.png`, `-06-carte-metier.png`.
2. **Presque aucune cible n'est utilisable au doigt.** Sur iPhone 15, 359 éléments interactifs sur 407 (88 %) font moins de 44 px. C'est 89 % sur Pixel 7 et 91 % sur iPad mini. Les icônes de l'en-tête font 35 × 30 px, le menu du compte 37 × 16, les lignes du tiroir 32 px de haut, le triangle qui déplie une règle d'analyse 31 × 16, les boutons + et − du graphe 36 px. Les champs sont en 11,5 à 13,5 px (Nouveau projet, recherche de classe, filtre d'analyse, Krakie, paramètres) : **iOS zoome à chaque saisie**.
3. **La navigation est profonde et sans repère.** Tout passe par un tiroir latéral de 15 entrées, réparties en 4 étapes, plus Administration et Paramètres. Il n'y a pas de retour, et le fil d'Ariane ne se touche pas. Les actions rares occupent la meilleure place : la cible Curiosity/Neo4j et le périmètre sont toujours visibles. Les actions utiles sont loin : arbitrer demande 3 touchers et 2 écrans de défilement avant le premier choix. Partager est une icône sans libellé de 32 × 22 px.
4. **Le graphe et la carte métier ne sont qu'en partie utilisables au doigt.**
   - Éditeur graphique (@xyflow/react) : glisser déplace bien la vue et pincer zoome (échelle passée de 0,3 à 0,9). Toucher un nœud le sélectionne et ouvre l'inspecteur, mais dans la moitié basse, sous le canevas déjà réduit. **L'appui long ne fait rien.** Les nœuds sont déplaçables au doigt : on déplace un nœud par erreur en voulant déplacer la vue. Les noms sont coupés par une ellipse sur des nœuds de largeur fixe (11 libellés coupés à l'écran : « Moteu… », « Perso… », « Opéra… »). La recherche est un champ de 13,5 px. La mini-carte et les contrôles prennent de la place sans servir au doigt.
   - Carte métier : glisser déplace la vue et toucher sélectionne. **Pincer ne zoome pas** : la carte ne gère qu'un pointeur, le second doigt déplace la vue (échelle restée à 0,45). L'appui long ne fait rien. Le panneau du type sélectionné s'ouvre hors de l'écran.
   - Modèle cible (Cytoscape) : nœuds qui se chevauchent (« Warranty » sur « Vehicle », « Technician » sur « RepairOrder ») et texte énorme au zoom initial.
5. **Krakie et son aquarium gênent plus qu'ils n'aident sur petit écran.**
   - Le bouton fait 201 × 150 px mais ne réagit que sur le sprite de Krakie, qui nage (environ 36 px, toujours en mouvement), et sur le récif (`Aquarium.tsx`, `hit()`). Au doigt, la cible bouge. Un toucher au centre du bouton tombe sur ce qui est dessous : sur le tableau de bord de l'iPhone 15, c'est la carte d'étape qui reçoit le toucher (mesuré). À l'inverse, le récif capte les touchers destinés aux boutons qu'il recouvre.
   - Éléments recouverts : « Nouvelle classe » à 29 % (vue liste) ; « Appliquer la recommandation à toute la règle » à 19 % et l'en-tête de règle à 22 % (analyse) ; « Ajuster » à 81 % (carte métier, Pixel 7) ; le nœud « Garage » à 56 % (graphe) ; les cartes d'étape du tableau de bord à 14 et 20 %.
   - Ouvert, Krakie prend tout l'écran. Le choix du modèle est coupé (« Mock (démo »), le rappel « Entrée pour envoyer… Ctrl+K » ne sert à rien au doigt, et le champ en police à chasse fixe de 12 px déclenche le zoom.

## Autres constats, par priorité

### P1 (gênant tous les jours)
- **Projets** : le formulaire « Nouveau projet » et la zone de dépôt remplissent le premier écran ; le seul projet existant n'apparaît qu'en bas, coupé (`iphone15-clair-01-projets.png`).
- **Vue liste de l'ontologie** : la plus lisible sur téléphone (lignes de 45 px, compteurs). Mais ses pastilles de compteurs font moins de 44 px. Dans le script, le toucher sur une ligne n'a pas ouvert de fiche visible : la fiche de classe n'a pas été capturée, il faudra vérifier à l'implémentation.
- **iPad mini en portrait** : il passe sous le seuil de 900 px. Il a donc le tiroir, et le bandeau « Sur mobile, cet écran est en consultation » alors qu'il a la place d'éditer. L'invitation « Première fois ici ? » s'affiche par-dessus la mini-carte, et Krakie recouvre « Pas maintenant » à 61 % (`ipadmini-clair-04-ontologie.png`).
- **Analyse** : le bilan chiffré (5 nombres et 2 barres) passe avant la première décision. Les cartes de règle repliées ne montrent l'option recommandée qu'en dépliant.
- **Exports** : le code est lisible (retour à la ligne), mais 24 cibles sur 25 font moins de 44 px. Copier et Télécharger font 30 px.
- **Partage** : la feuille est correcte, mais le champ identifiant et le sélecteur de rôle font 30 px, en 13,5 px.

### P2 (finition)
- Tableau de bord : le grand Krakie « inquiet » occupe le haut de la carte « 1 constat(s) perdus ». Les pluriels « constat(s) » et « règle(s) » se répètent partout.
- Légende du graphe ouverte au premier affichage (décision L26). Sur téléphone, elle recouvre le haut du canevas.
- Paramètres et administration : lisibles, mais les champs et les boutons font 30 px ; le tableau des comptes est étroit.
- Paysage (iPhone) non mesuré dans cette phase : à ajouter à la recette mobile.

### Ce qui va bien
- **Aucun débordement horizontal de page**, sur aucun écran ni aucun appareil.
- **Aucune erreur de console ni violation de CSP** pendant les parcours, en version web comme en version locale.
- Le thème sombre est cohérent (`iphone15-sombre-*.png`) et les contrastes des jetons tiennent.
- Le tiroir se ferme au changement d'écran. Le canevas de l'éditeur gère déjà le pincement.
- Versions web et locale : mêmes constats. La version web ajoute seulement l'écran de connexion et les entrées liées aux comptes.

## Actions par tâche (iPhone 15, depuis la liste des projets)

| Tâche | Aujourd'hui | Avec la maquette |
|---|---|---|
| Ouvrir la fiche d'une classe (vue liste) | 4 touchers (projet, menu, Vue liste, classe) et 1 défilement | 3 touchers (projet, Ontologie, classe) ; ou 2 par la recherche |
| Voir une classe dans le graphe | 4 touchers (projet, menu, Ontologie, fermer la légende), des gestes, toucher le nœud ; fiche sous un canevas réduit | 3 touchers (projet, Ontologie, recherche puis choix) ; fiche en feuille du bas |
| Arbitrer un constat | 5 touchers (projet, menu, Analyse, ▸ 31 × 16, option, appliquer) et 2 défilements | 3 touchers (projet, Arbitrer, Valider) ; 4 si l'on change d'option |
| Demander à Krakie | 1 toucher sur une cible mouvante d'environ 36 px | 1 toucher sur un bouton fixe de 56 px |
| Partager | 2 touchers (projet, icône sans libellé de 32 × 22 px) | 2 touchers (projet, Partager dans l'en-tête de l'Accueil) |
| Changer de cible | 1 toucher, toujours visible (action rare, place prioritaire) | 2 touchers (sous-titre de l'Accueil ou Plus) |

## Éléments visibles par écran (interactifs / dont moins de 44 px)

| Écran | iPhone 15 | Pixel 7 | iPad mini |
|---|---|---|---|
| Connexion | 5 / 5 | 5 / 5 | 5 / 5 |
| Projets | 16 / 15 | 17 / 16 | 17 / 16 |
| Tiroir ouvert | 34 / 29 | 38 / 32 | 40 / 34 |
| Tableau de bord | 17 / 13 | 18 / 13 | 23 / 18 |
| Ontologie, graphe | **47 / 46** | 47 / 46 | **93 / 90** |
| Ontologie, liste | 33 / 30 | 40 / 37 | 51 / 50 |
| Carte métier | 17 / 16 | 21 / 20 | 28 / 27 |
| Analyse | 19 / 17 | 28 / 25 | 37 / 36 |
| Modèle cible | 17 / 16 | 23 / 22 | 24 / 23 |
| Exports | 25 / 24 | 31 / 30 | 25 / 24 |
| Requêtes | 21 / 15 | 32 / 23 | 26 / 15 |
| Krakie ouvert | 24 / 20 | — | 27 / 22 |
| Partage | 21 / 17 | 25 / 20 | 24 / 19 |
| Paramètres | 17 / 11 | 22 / 16 | 18 / 17 |
| Administration | 14 / 14 | 15 / 15 | 16 / 16 |

« — » : sur Pixel 7, le script n'a pas obtenu l'écran Krakie ouvert (bouton non trouvé visible au moment du test) ; à reprendre dans la recette mobile.

## Gestes mesurés

| Geste | Éditeur graphique | Carte métier |
|---|---|---|
| Glisser à un doigt (vue) | oui | oui |
| Pincer (zoom) | oui (0,3 → 0,9) | **non** (échelle fixe à 0,45, le second doigt déplace la vue) |
| Toucher un nœud | sélection et inspecteur, en bas, sous le canevas | sélection, panneau hors de l'écran |
| Appui long | **rien** | **rien** |
| Recherche qui centre | champ de 13,5 px, recherche et centre | absente |
| Tout voir | bouton de 36 px (Controls) | bouton « Ajuster », recouvert par Krakie sur Pixel 7 |

## Captures de référence (avant)

- `avant/iphone15-clair-04-ontologie.png` : en-tête de 3 lignes, bandeau, 4 lignes d'outils, légende, noms coupés.
- `avant/iphone15-clair-04-ontologie-toucher-noeud.png` : inspecteur en bas, canevas réduit à une bande.
- `avant/iphone15-clair-07-analyse.png` : bilan avant décision, Krakie sur « Appliquer ».
- `avant/iphone15-clair-06-carte-metier.png` : la carte commence à mi-écran.
- `avant/iphone15-clair-02-menu-tiroir.png` : 15 entrées.
- `avant/iphone15-clair-20-krakie-ouvert.png` : plein écran, sélecteur coupé, rappel clavier.
- `avant/ipadmini-clair-04-ontologie.png` : bandeau « consultation » sur tablette, invitation par-dessus la mini-carte.
- `avant/iphone15-sombre-*.png` : thème sombre.

## Suite

Maquette : `journal/L44/maquette/index.html`, avec les captures `maquette/*.png`. Plan d'implémentation : `journal/L44/plan.md`. Jerem valide la maquette avant toute modification de l'application.
