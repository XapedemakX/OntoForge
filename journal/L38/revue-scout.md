verdict: OK
relecteur: scout UX (commit 2d411b6) ; captures vues : `journal/L38/screens/*` (panneau clair, sombre, mobile clair et sombre, section mise en évidence, diagnostic, guide) et `docs/guide/img/fr|en/krakie-parametres.png`.

bloquants:
  - aucun.

non-bloquants:
  - [desktop-clair-panneau.png, desktop-sombre-panneau.png] le panneau (460 px) recouvre la droite de la page : les boutons « Tester la connexion », « Modifier » et la colonne « Assistant » de l'onglet Langues sont coupés pendant que Krakie explique justement ces écrans. Déjà connu pour l'en-tête (limites) ; prévoir un décalage du contenu ou un panneau repliable en pied sur ces écrans.
  - [toutes captures du panneau] à l'arrivée d'une réponse longue, la vue est calée en bas : on voit la fin des étapes et les cartes, pas l'état de la configuration (première phrase, la plus utile du diagnostic). Faire défiler au début du nouveau message.
  - [panneau, onglet Langues] question sur le LLM posée depuis l'onglet Langues : la réponse est bien sur les LLM (sujet de la question), mais la carte « Aller à la section » le dit seulement par « Onglet « Fournisseurs LLM » » ; correct, juste à surveiller (la pastille de contexte reste « Langues »).
  - [panneau] le sélecteur de fournisseur est tronqué (« Mock (démor ») ; lisible en anglais (« Mock (demo) »), pas en français.
  - [réponses intégrées] longues listes numérotées en texte brut sans mise en forme ; lisibles, mais l'état, les étapes et la suggestion finale se fondent dans un seul bloc. Un saut de ligne plus net ou un gras sur « Pas à pas » aiderait.
  - [mobile-*-parametres.png] onglets défilants coupés à droite (« Affic ») : défilement horizontal sans indice visible ; antérieur au lot.

constaté bon:
  - Réponses sans LLM claires : état, puis pas à pas, puis cartes ; le test n'est proposé que si un fournisseur réel est configuré (carte absente avec seulement le mock, présente avec « Claude (test) »).
  - Cartes cohérentes (icône, titre, résumé, un seul bouton principal), contrastes corrects en clair et en sombre, boutons de 32 px et plus sur mobile, panneau plein écran en mobile sans débordement, aquarium sans recouvrement du contenu.
  - Mise en évidence de la section (contour) visible ; captures du guide fr et en avec repères 1 et 2 lisibles ; anglais complet.
