# L40 : projets nominatifs et partage collaboratif : rapport

## Résultat
Chaque projet a un propriétaire ; il est visible et modifiable seulement par ses membres (propriétaire, éditeur, lecteur). Le partage se fait par identifiant de compte. La collaboration est sans temps réel : concurrence optimiste, présence, bandeau « modifié », journal d'activité. Le mode local (sans ONTOFORGE_AUTH) est inchangé.

## Choix (D-L40-01)
1. Contrôle côté serveur sur toutes les routes portant un project_id (table de classification (méthode, gabarit) vers (niveau, action), 403 « unclassified » si une route n'y est pas : échec fermé). Projet inaccessible = 404. Test paramétré sur toutes les routes FastAPI.
2. Rôles éditeur / lecteur ; changement de rôle, retrait, transfert de propriété ; un éditeur ne partage ni ne supprime ; message neutre pour un identifiant inconnu ; limiteur existant (10 par minute).
3. Réglages globaux : écriture réservée à l'administrateur (ONTOFORGE_AUTH_ADMINS, sinon le premier compte déclaré) ; lecture expurgée pour les autres.
4. Mode local : utilisateur implicite « local ».
5. Migration idempotente : les projets sans propriétaire vont au premier administrateur.
6. Concurrence optimiste (ETag / If-Match, 409 conflit, 428 si absent sur projet partagé), présence (battement 20 s, expiration 60 s), bandeau par sondage, journal d'activité.
7. Front : bouton Partager, panneau d'accès, mode lecture seule, colonne propriétaire et badge « partagé », i18n fr et en, aide Krakie.

Les données de collaboration vivent dans des fichiers annexes (collab.json, activity.jsonl), hors du modèle Project : un PUT client ne peut pas s'approprier un projet.

## Vérifications
- pytest complet dans un worktree propre : 1147 passed.
- npm run build : OK. Recette l40_partage : tout vert (deux comptes, fr/en, clair/sombre, aucune erreur console).
- e2e_ui : 30/30 (avec ONTOFORGE_RATE_LIMIT=0, voir ci-dessous). tour : 49 OK / 0 KO. english_scan : 0 suspect.
- test_help_map et test_docs_bilingual verts.

## Points d'attention
- Sans désactiver le limiteur de débit L39 (travail de l'autre agent, ratelimit.py, plafond « lourd » de 30/min), la partie mobile de e2e_ui prend des 429 sur /analyze. Ce n'est pas lié à L40 ; à régler côté L39 (plafond ou exemption de l'analyse).
- Garde de lecture seule du front au mieux ; le serveur (403 + toast) fait foi.
- Présence et révisions en mémoire : une seule instance. Granularité de révision = projet entier. If-Match facultatif sur projet non partagé.
- SEC-19 corrigé, SEC-20 clos, SEC-03 partiellement atténué (audit mis à jour, jamais publié).
- Montées de dépendances reportées (D-L21-02).
