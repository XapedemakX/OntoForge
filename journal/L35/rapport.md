# L35 : bandeau latéral repliable en icônes

## Livré
- Mode replié de 56 px : icônes centrées (la géométrie est commune aux deux modes, l'icône ne bouge pas pendant la transition), logo `mark`, étapes en pastilles 1 à 4 qui séparent les groupes, trait au-dessus d'Outils, badge d'Analyse en pastille sur l'icône (et dans l'aria-label : « Analyse & arbitrage (42) »).
- Infobulle unique en position fixe (le conteneur défilant du bandeau couperait une infobulle CSS), au survol et au focus clavier, Échap la ferme ; `aria-label` partout, `aria-current="page"` sur l'actif (fond + liseré).
- Bouton « Replier / Déplier » en bas (chevrons) et Ctrl/Cmd+B, ignoré dans un champ de saisie, une boîte de dialogue ou CodeMirror. Aucun conflit trouvé (l'éditeur n'utilise que Z, Y, Suppr, F2, Échap ; Krakie Ctrl+K).
- Trois préférences dans `localStorage` (`ontoforge.side` : auto, open, closed, en try/catch, repli mémoire) ; le bouton bascule vers open ou closed ; Paramètres › Affichage (nouvel onglet) choisit Automatique / Ouvert / Replié.
- Repli automatique : drapeau `collapseAuto` du registre sur ontologie, ontologie-liste, fichiers, documentation (écrans plein canevas qui ont leur propre arbre ou sommaire). Assistant reste ouvert (conversation).
- Transition de la colonne de la grille (0,18 s) ; l'éditeur recadre le graphe à la fin si le cadrage initial a moins de 2 s (évènement `of:side-settled`), sinon le zoom de l'utilisateur est respecté ; React Flow suit la largeur seul. `prefers-reduced-motion` : aucune transition. Mobile (< 900 px) : aucune règle ni bouton, tiroir inchangé.
- Visite guidée : l'étape « nav » vise toujours `[data-tour="nav"]` ; vérifié dans les deux modes (trou et bulle bien placés).
- Doc : section « Bandeau latéral » `{#bandeau-lateral}` (utilisateur.md et .en.md, placée après le tableau de bord pour que la première image du guide reste celle des projets, voir l28), CHANGELOG fr et en, captures `bandeau-replie` (fr, en) et recapture des écrans éditeur, liste, fichiers, documentation, hermit-classe-rouge, krakie-contexte, editeur-perimetre.

## Écarts
- Déconnexion, thème et langue sont dans l'en-tête, pas dans le bandeau : rien à passer en icônes.
- Le mode « automatique » ne s'applique pas à Paramètres ni à la liste des projets ; la préférence « Replié » s'y applique.

## Vérifications
Build, e2e_ui 30/30, tour 47/47, english_scan 0 suspect, l28_docs 70/70, pytest test_docs_bilingual + test_help_map 44 verts, l35_sidebar 43/43. Captures : journal/L35/screens/ (regardées : badge, infobulle du bas, éditeur replié).

## Relecture demandée à l'éclaireur produit (scout, UX)
À vérifier : (1) le bouton bascule vaut choix explicite (déplier à la main sur l'éditeur = « toujours ouvert ») : est-ce le bon compromis ou faut-il un retour visuel ? (2) les pastilles d'étape n'ont pas d'infobulle au clavier (non focusables) ; (3) les quatre écrans en repli automatique conviennent-ils, faut-il y ajouter l'assistant ? (4) le projet courant n'est plus nommé en mode replié (le fil d'Ariane de l'en-tête le porte).
