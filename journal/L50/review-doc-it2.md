# L50 — revue doc (exactitude), itération 2

verdict: OK

Relu : `docs/guide/utilisateur.en.md` (légendes des images, lignes 626 à 670, diff 914cbf7), `docs/guide/utilisateur.md` (parité), `deploy/cloudrun/README.md` (§3, §5, §7, §8). Contrôle des titres d'images fait par script (analyse de chaque `![alt](src "titre")` des deux guides). Le test `backend/tests/test_docs_bilingual.py` n'a pas pu être rejoué ici : la collecte échoue (dépendances Python absentes de l'environnement, rien installé, comme demandé) ; le contrôle par script le remplace pour les légendes.

bloquants:
  - aucun

Points levés depuis l'it1 :
- `utilisateur.en.md:626, 636, 644, 658` : les guillemets internes du titre sont devenus `'To do now'`, `'Send me the link'`, `'Fit all'`, `'Validate this choice'` ; les titres sont de nouveau bien formés. Les guillemets droits restent dans le texte alternatif entre crochets, ce qui est valide. Résultat du script : 78 images dans la version française, 0 titre mal formé ; 99 dans la version anglaise (les 2 occurrences de `\"` des lignes 99 et 113 sont échappées, donc valides et antérieures à L50). Les 7 légendes `mobile-*` correspondent aux images listées.
- README : « Deux valeurs » (le tableau en liste deux) ; la phrase dupliquée sur l'endpoint SPARQL est supprimée (reste la ligne 85) ; « Sinon, à la main : » est complété (nouvelle étiquette `demo-2`, étape 4, puis `gcloud run services update ontoforge --region $REGION --image $IMAGE`) avec la limite « `services update` ne change que l'image » : exact, et cohérent avec le §8.

non-bloquants:
  - [deploy/cloudrun/README.md:85-86] La puce `mount-options=uid=10001;gid=10001` est maintenant imbriquée sous la puce `env.yaml` (indentation de deux espaces) alors qu'elle décrit une autre option de la commande. Le sens reste compréhensible, mais le rendu les présente comme parent et enfant : la remettre au niveau de la puce `env.yaml`.
  - Le contrôle de motif du §8.4 et la commande `builds approve` portent chacun une réserve (« à confirmer ») : formulation honnête, à lever au premier déploiement réel.

skill: technical-documentation : la règle « pas de guillemets droits dans le titre d'une image » est toujours à intégrer, avec un test qui analyse les images des deux guides (le script de cette revue peut servir de base).
