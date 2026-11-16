# L45 : rapport — téléphone : modèle de Krakie, panneaux repliables, raccourcis retirés

Agent : mobile. Recette : `tools/recette/mobile_l45.mjs` (local et web ; iPhone 15, Pixel 7, iPad mini ; lecteur `bob` en web).

## 1. Choix du fournisseur dans Krakie
- Sur ordinateur, le choix est un `<select>` dans l'en-tête du panneau : liste = `providers` de `GET /assistant/status` (id, nom, type, modèle, `configured` ; ni clé ni adresse), valeur dans l'état partagé `ontoforge.assistant.ui.provider`, transmise en `provider_id` à chaque appel. Aucun contrôle de rôle : tout compte connecté, lecteur compris, choisit parmi les fournisseurs configurés.
- Le téléphone réutilise exactement ce mécanisme (même état, même API, même droit). Un sélecteur « Modèle de Krakie » (44 px, 16 px, pleine largeur) est posé dans la zone fixe du bas de la feuille, au-dessus de la saisie : il ne défile pas et n'est jamais coupé. Un seul fournisseur : ligne en lecture « Modèle utilisé : … ». Un identifiant mémorisé devenu inconnu est remplacé par le fournisseur par défaut (téléphone seulement).
- Les suggestions de la feuille passent à 44 px (elles étaient à 36 px).

## 2. Panneaux repliables (`Fold`, `kit/index.tsx`)
Bouton `aria-expanded`/`aria-controls` dans un `h2`, clavier natif (Entrée, Espace), contenu masqué par `hidden` (l'état des formulaires est conservé), état par `écran/panneau` dans `ontoforge.fold.v1` (try/catch, repli en mémoire). Replié : titre + « — » + description grise de 13 px ; ouvert : titre seul. Au-dessus de 700 px le composant rend la même carte qu'avant (ou le contenu tel quel avec `bare`).
Inventaire des écrans du téléphone :
| Écran | Panneaux | Ouvert par défaut |
|---|---|---|
| Accueil | Constats restants par cible, Générer, Périmètres (« Scopes »), Activité du projet (si authentification) | aucun (le bloc principal « À faire maintenant » et le parcours ne sont pas des panneaux) |
| Versions | Écarts avec la référence, Versions visées, Fonctions SHACL 1.2, Bibliothèques | Versions visées (et Écarts s'il y a des points à traiter) |
| Requêtes | Requêtes sauvegardées (et questions de compétence) | non |
Déjà adaptés par L44, laissés tels quels : légende du graphe (bouton repliable), filtres et cible (feuilles du bas), fiches. Écrans à onglets ou à bloc unique (Paramètres, Administration, Exports, Modèle, Conformité, Arbitrer) : un seul panneau principal par onglet, non replié. Descriptions fr/en : clés `fold.<écran>.<panneau>`.

## 3. Raccourcis retirés sous 700 px
Carte « Raccourcis » de l'accueil (doublon des onglets) et titre « Ctrl+K » du bouton Krakie. Les autres mentions de touches (aide de la saisie de Krakie, éditeur de fichiers, bandeau latéral) étaient déjà absentes ou réservées à l'ordinateur ; la recette le vérifie sur 9 écrans. Le parcours en quatre lignes de l'accueil (états Concevoir, Vérifier, Transposer, Générer) est conservé : il porte un état, pas seulement un lien.

## Corrigé en route
La liste des étapes de l'accueil était écrasée à 0 px par le conteneur flex dès qu'il y avait plus de panneaux (`.is-mobile .dash > * { flex-shrink: 0 }`).

## Vérifications
`npm run build` ; `mobile_l45` vert (local, web ; 3 appareils) ; `mobile_l44` vert ; `e2e_ui` 30/30 ; `l35_sidebar` 43/43 ; `l36_business_map` 32/32 ; `l37_aquarium` ; `l38_settings_krakie` 37/37 ; `tour` 50/50 ; `english_scan` 0 suspect ; `test_help_map`, `test_docs_bilingual` (44 tests). Pas de pytest backend complet (aucun backend touché).

## Reste
Version mobile de Paramètres, Administration, Exports, Modèle, Conformité non recomposée en panneaux (un bloc par onglet). Pas de test sur un vrai iPhone (sélecteur natif iOS).
