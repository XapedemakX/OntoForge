verdict: OK
bloquants:
  - aucun.
non-bloquants:
  - [frontend/src/i18n/fr.json:1177] le message d'erreur réseau est long (deux phrases, avec le port) et passe maintenant dans les bandeaux d'erreur de l'assistant, de l'éditeur et des requêtes. Sur un téléphone étroit il prend plusieurs lignes ; la recette `mobile_l45` ne coupe pas le serveur et ne vérifie donc pas ce rendu. Un message plus court (voir la revue scout) règle les deux. Non vérifié à l'écran faute de parcours « serveur coupé » sur mobile.
  - [tools/recette/mobile_l45.mjs] aucune vérification du parcours « connexion puis écran ouvert » ni « changement de projet » sur téléphone avec instance protégée (la recette mobile tourne sans authentification). Le risque propre à DF-F04 est écarté par lecture du code (aucun écouteur n'existait), mais un test de bout en bout de la reconnexion sur téléphone n'existe dans aucune recette. À ajouter dans un prochain lot si Jerem utilise l'instance protégée sur mobile.
constats :
  - Aucun écran, composant ni style du front n'est modifié par le lot (seuls des clients réseau, un évènement mort et des tests) : pas de risque de mise en page.
  - Rafraîchissement après connexion et après changement de projet, téléphone et ordinateur : mêmes composants (`Shell`, `AuthGate`) ; `MobileHeader`, `MobileTabBar`, `ContextSheet` et `Fiche` n'émettent ni n'écoutent `ontoforge:authed` ou `ontoforge:project` (grep). `Shell.tsx` recharge le projet par `api.loadProject(pid)` à chaque changement de `pid`. Aucune régression.
  - Rejoué : `mobile_l45` (ports 9853 / 5853, web et local, trois appareils dont iPad mini) : « Tout est vert », aucune erreur de console ; `e2e_ui` (version mobile `m-01` à `m-13` incluse) : 30 OK / 0 KO. Captures versionnées réécrites restaurées (29 fichiers, `git status` propre).
  - Hors périmètre mais à signaler : au moment de la relecture, des `vite preview` des ports 5752 à 5754 (lancés à 07:44 à 07:46, avant ma recette) tournaient encore dans le worktree ; je ne les ai pas touchés. Mon propre `vite preview` (5852) resté en route a été arrêté par son PID.
skill: audit-mobile-refonte : ajouter un parcours « serveur coupé » (bandeau d'erreur réseau en 390 px) et un parcours « session expirée puis reconnexion » à la recette mobile, car la centralisation du client réseau fait passer toutes les erreurs par un même message.
