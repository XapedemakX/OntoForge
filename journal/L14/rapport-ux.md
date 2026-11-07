# L14 - Corrections d'usage B2, B3, B4 et non-bloquants (revue scout)

B1 (éditeur) non touché : traité par un autre agent.

## B2 Tableau de bord
- Zone « Prochaine action » selon l'état : ontologie vide (Créer une classe / Importer / Assistant), non conforme (Conformité), pas de shapes, perdus ou à arbitrer (Arbitrer), tout arbitré (« Générer pour Curiosity » en un clic, génération sur place), génération obsolète (régénérer), déjà généré (Télécharger le zip, Voir les fichiers, Requêtes).
- Carte « Générer » : bouton primaire quand restants = 0, secondaire sinon (avec le nombre de constats restants), lien zip, historique.
- Historique côté serveur : `Project.generations` (50 max, rétrocompatible), enregistré à chaque `GET /generate/{target}` sans avancer `updated_at` ; `GET /projects/{id}/generations` ; `project_updated_at` sert à « Obsolète / À jour ». `PUT /projects/{id}` ne l'écrase pas. Journal local `lib/generations.ts` supprimé.
- Tests : `backend/tests/test_generations.py` (3). CONTRACTS §2 et §7 mis à jour.

## B3 Projets
- Zone de dépôt : CSV/TSV/SQL/texte/Markdown proposent « Créer un projet et ouvrir l'assistant avec ce fichier » ; le fichier est déjà joint (aperçu des colonnes) à l'arrivée (transmission par sessionStorage). Ontologie/shapes : import direct comme avant. JSON Schema non géré (pas d'import côté assistant).
- Renommage en ligne + description (crayon, Entrée/Échap). Suppression avec confirmation dans la carte nommant le projet (plus de `confirm()`).
- Cartes distinguables : cible, classes / relations / propriétés de données / shapes, origine (fichier d'exemple ou « projet vide »), date de création et de modification (`GET /projects` expose `created_at`, `source_files`). État vide avec Krakie.

## B4 Analyse
- « Accepter toutes les recommandations » passe en bouton secondaire, ouvre une confirmation dans la page : n auto (rien à décider), n à arbitrer, n perdus, case « Seulement les constats à arbitrer, pas les perdus » cochée par défaut ; dans ce mode les perdus ne sont jamais décidés. Pas de champ « pourquoi » (pas de support serveur).
- Un seul sélecteur de cible (en-tête) : retiré d'Analyse et d'Exports ; Analyse et Modèle affichent seulement la cible en pastille.

## Non-bloquants
- Tutoiement : chaînes i18n (tableau, assistant, paramètres, mobile), Ontologie liste. Reste du vouvoiement éventuel dans `ed.*` (éditeur, hors périmètre) : à vérifier par l'agent de l'éditeur.
- Vocabulaire : « Nouvelle classe » (ontologie liste), « Propriété de données » (assistant), « relations » pour les propriétés objet dans Projets, « libellé » = rdfs:label (aucune occurrence de « nom affiché » hors éditeur).
- Bannière NL : `/query/nl` répond ; la bannière ne s'affiche que sur 404/501, renommée « Service indisponible » avec le conseil « sans LLM ».
- Tiroir mobile : en Paramètres, tiroir superposé avec voile, page non décalée (ux-14, ux-15).
- États vides avec Krakie : Périmètres (action « Créer un périmètre » + exemple), Ontologie liste (3 gestes), Projets.
- Non traités : colonnes de requête repliées, jargon « À VÉRIFIER », regroupement mobile de l'en-tête, badge de cible sur Analyse (la pastille « Cible » est ajoutée dans la page, pas dans le badge latéral).

## Vérifications
`npm run build` vert ; `pytest` 528 verts ; Playwright (backend mock) : captures `journal/L14/screens/ux-01..16-*.png`, aucune erreur console.
Note : un `vite` externe sur le port 5180 a été arrêté par erreur au cours des tests (relancer si besoin).
