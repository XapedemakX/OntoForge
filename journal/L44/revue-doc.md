verdict: OK sous réserve de la capture mobile-graphe (en correction)

Vérifié contre le code : onglets (MobileTabBar), « Plus de détails » (mob.dash.more), menu d'appui long (MobileGraphBar : voir la fiche, centrer ; sous-classe et propriété réservées à qui peut modifier), « Passer » (Deck), « Appliquer … aux N » avec annulation de 5 s (D-L44-01), seuil 700 px, bouton Krakie 56 px, `help_map` : entrée `mobile` (ancre `sur-telephone-et-tablette`, présente dans les deux guides). CHANGELOG fr/en et lots/L44.md cohérents avec le code. `test_help_map` et `test_docs_bilingual` : 44 passés.
Corrigé :
  - [docs/guide/utilisateur.md:648, utilisateur.en.md:648] « journal d'activité et annulation » : la fiche mobile n'offre pas d'annulation (elle appartient à l'éditeur de bureau) ; « et annulation » retiré.
  - [utilisateur.md:641, utilisateur.en.md:641] l'appui long propose sous-classe et propriété seulement si l'on peut modifier ; précisé.
  - [utilisateur.md:624, utilisateur.en.md:624] « Depuis L44 » : référence interne retirée du guide utilisateur.
bloquant (pas à moi) :
  - [img/fr|en/mobile-graphe.png + légende « les étiquettes ne sont pas coupées »] La capture montre un graphe sans arêtes et minuscule. À régénérer par l'agent mobile après correction, puis relire la légende.
non-bloquant :
  - [utilisateur.md « Krakie sur téléphone »] « le clavier du téléphone ne cache pas la zone de saisie » est affirmé sans test sur appareil réel (À VÉRIFIER, déjà au rapport) ; à nuancer si Jerem le préfère.
  - Les légendes numérotées (« 1 … 2 … 3 ») ne correspondent à aucun repère visible sur les captures mobiles (pas d'annotations) ; mobile-plus ne montre pas « M'envoyer le lien » (en bas de liste, hors cadre).
`doc-ok.md` non écrit : en attente de la capture du graphe.
