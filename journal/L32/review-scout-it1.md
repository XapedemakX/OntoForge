# L32 : revue scout, itération 1 (carte « Raisonner avec HermiT »)

verdict: OK

Recette relancée : `node tools/recette/l32_hermit.mjs` 7/7, captures `journal/L32/screens/01` à `06` regardées.

Parcours bouton → résultat → classe surlignée → ajout : clair. La carte est placée juste sous les profils, le bouton est visible sans défiler, le badge Cohérente / Incohérente se lit d'un coup d'œil, la classe insatisfiable est un bouton rouge qui ouvre l'éditeur sur la classe, cadrée et en rouge, avec un bandeau qui explique pourquoi (04). L'ajout donne un toast « annulable » et un badge « Ajouté » (03).

bloquants: aucun

non-bloquants :
  - Corrigé (`frontend/src/screens/Conformance.tsx`) : « Annuler le dernier ajout » effaçait tous les badges « Ajouté » alors qu'une seule opération était annulée ; les autres relations redevenaient ajoutables en double. La carte garde maintenant une pile : seule la dernière est retirée, le bouton reste tant qu'il reste des ajouts.
  - Attente : pendant le calcul, seul le libellé du bouton change (« HermiT raisonne… ») et l'intro annonce « moins d'une seconde ». Rien n'indique que l'attente peut aller jusqu'à 30 s, ni le temps écoulé, ni comment annuler. Proposer : sous le bouton, « jusqu'à 30 s » et un compteur de secondes après 3 s. Krakie forgeronne (lot L29, en cours) serait le bon signal d'attente ici : à brancher par L29, pas intégré ici.
  - Badge vert « Cohérente » alors qu'une classe est insatisfiable (02) : l'utilisateur peut croire que tout va bien. Proposer « Cohérente · 1 classe insatisfiable » en orange.
  - « Inférences utiles » n'a pas de compteur, contrairement aux deux autres sous-titres. Pas de « Tout ajouter » : avec dix inférences, dix clics.
  - Ontologie incohérente (05) : les pistes ne sont pas cliquables (individu, classes) ; un clic vers la vue liste ou l'éditeur aiderait. Le tableau de conformité répète en dessous « L'ontologie est incohérente (voir les notes du raisonneur) » : renvoyer vers la carte.
  - Éditeur (04) : le bandeau dit combien de classes sont insatisfiables mais pas pourquoi ; ajouter un lien « Retour à la carte HermiT ».
  - Les avertissements ajoutés par la revue w3c (imports non suivis, classe ≡ owl:Thing) s'affichent dans la liste d'avertissements existante de la carte, sans changement d'interface.

skill: rien

## Complément : attente avec Krakie forgeronne (fait par le scout, 8 nov.)

Le non-bloquant « attente » est traité : pendant le calcul, la carte affiche Krakie forgeronne (même composant `KrakieStatus`, pose `forge` que L29) avec « HermiT raisonne… (jusqu'à 30 s) » ; à la fin, trophée 2 s et « Ontologie cohérente. » si cohérente, Krakie inquiète et « Ontologie incohérente : voir les pistes. » sinon. Mouvement réduit : image fixe. Fichiers : `frontend/src/screens/Conformance.tsx`, `frontend/src/krakie/Krakie.tsx` (`donePose`), i18n fr / en. Recette `l32_hermit.mjs` : 10/10 (réponse ralentie de 2,5 s ; R8 vérifie forge animée, trophée, inquiète, image fixe). Captures `journal/L32/screens/07-attente-forge.png`, `08-fin-trophee.png`, `09-fin-inquiete.png`. Reste à faire : compteur de secondes après 3 s et moyen d'annuler.
