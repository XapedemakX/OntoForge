# L53 : clôture (24/11/2026)

**Livré.** Six défauts corrigés. Synthèse : `journal/L53/corrections.md` ; détail : `corrections-b12.md`, `corrections-b13.md`.

- Requêtes : DF-B12 (EXISTS / NOT EXISTS / MINUS réduits à un typage : Cypher invalide), DF-B14 (MINUS sans variable partagée), DF-B15 (FILTER sur une variable d'OPTIONAL placé trop tôt) et DF-B18 (OPTIONAL ou BIND d'un sous-motif qui débordait dans la requête principale). Les variables d'OPTIONAL non liées suivent SPARQL (§18.5, §18.6) ou sont signalées comme perte.
- Serveur et Cloud Run : DF-B13 (places bornées pour les fils du triplestore local, plafonds mesurés), DF-B17 (analyseur SPARQL de rdflib sous un verrou unique, il renvoyait au hasard des 422 sur des requêtes simultanées), anomalie CI (installation avec `backend/constraints.txt`).
- Décision D-L53-02 de Jerem : plafond disque total (64 Mo) et purge des bases inactives (30 min).
- Somme au pire sur Cloud Run : 1933 Mo, marge de 115 Mo sous 2 Gio. Le script de mise à jour applique maintenant `env.yaml`.

**Relectures.**
- B12 : query et curiosity KO en it1 et it2, OK en it3 ; neo4j OK dès it2 ; finitions ensuite.
- B13 : deploy KO en it1 (env.yaml non appliqué, mémoire des chargements) et it2 (repli Secret Manager du README), OK en it3 ; devback OK en it1, KO en it2 (test pySHACL qui ne pouvait pas échouer), OK en it3 ; devfront OK en it1.
- Documentaliste : `doc-ok.md`. Humaniseur : `humaniseur.md`.

**Vérification sur la version fusionnée.** Suite backend 1724 réussis ; front `npm test` 22/22, `npm run build` OK ; recettes e2e_ui 30/30, l19_local_store 9/9, l40_partage, mobile_l45, l48_import, l49_bonnes_pratiques 14/14 vertes (l48 relancée après une collision de port de la recette, sans rapport avec le code).

**À faire par Jerem.** Déployer avec `deploy-demo.ps1` (ou l'étape 5 du README), puis contrôler avec la commande du README §7. À vérifier à ce moment : secrets gardés avec `--env-vars-file`, rôles du compte Cloud Build, marge mémoire réelle dans le tableau de bord Cloud Run. Formes Cypher à confirmer sur une vraie base Neo4j 5.

**Reste ouvert.** DF-B16 (fausse perte sur une relation vers un sous-type, Neo4j), limites consignées (attente des chargements pendant une longue requête, budget disque estimé, ordre des colonnes de `SELECT *`), cinq choix de L52 et sept À CONFIRMER du manuel.
