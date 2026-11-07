# L5 - Rapport front (lead)

Build : `cd frontend && npm run build` OK (tsc strict + vite). Dev : `npm run dev` (proxy /api vers :8000).

## Livré (frontend/src)
- `api.ts` : client typé unique (types miroir de core/*.py, ApiError avec `notReady` pour 501, utilitaires IRI/CURIE).
- `ui.tsx` : useLoad, erreurs lisibles + « bientôt disponible » (501), toasts, CodeMirror 6 (lecture/édition, diagnostics par ligne, Turtle/Cypher/SPARQL/JSON).
- `App.tsx` : navigation latérale par projet (hash `#/projet/<id>/<écran>`), cible Curiosity/Neo4j persistée, compteur « à arbitrer », thème clair/sombre.
- `screens/` : Projects (créer vide/exemple, glisser-déposer), Ontology (arbre multi-parents, 4 listes, éditeur complet, ajout/suppression avec nettoyage des références, PUT /onto, import, export Turtle/RDF-XML/JSON-LD, Saisie rapide DSL avec aide/exemple/erreurs par ligne), Conformance, Shacl (shapes, générer, importer, Turtle, validation), Analysis (synthèse, barres de triage et de progression, perdus/à arbitrer en avant, auto repliés, options radios, recommandation, Expliquer, accepter tout), Model (cytoscape + tableaux), Exports (visionneuse, copier, télécharger, zip), Queries (SPARQL vers Cypher/Curiosity/GraphQL, notes, questions de compétence), Assistant (texte/CSV/SQL, diff Accepter/Rejeter par élément, fusion via PUT /onto, statut).

## Vérifié (Playwright, captures dans journal/L5/screens/)
Backend réel : projets, ontologie, DSL, conformité, SHACL, export. `mapping.engine` répondait 501 : l'écran affiche « bientôt disponible ». Analyse, modèle, exports, assistant testés avec réponses simulées (page.route) conformes à CONTRACTS ; aucune erreur JS. Thème sombre contrôlé.

## Limites / à revoir
- Analyse, modèle, exports, requêtes et assistant non testés contre le vrai backend (modules absents au moment du test).
- L'IRI d'une entité n'est pas renommable dans l'éditeur (création seulement).
- Domaine/portée en union, chaînes, équivalences et facts d'individus sont en lecture seule.
- Pas de GET d'aide DSL côté API : l'aide est embarquée dans le front (à resynchroniser avec DSL_HELP).
- Bundle > 500 ko (CodeMirror + cytoscape), sans impact fonctionnel.

## Intégration (moteur réel, projet AutoMaint, cibles Curiosity et Neo4j)
- Types TS conformes aux vraies réponses (analyze, generate, translate) : aucun écart. Seul `queries/competency` répond encore 501 (module queries.translate) : l'écran affiche « bientôt disponible ».
- Analyse : constats regroupés par règle (titre, nombre, progression, option dominante recommandée), bouton « Appliquer la recommandation à toute la règle » (un seul PUT /decisions), dépliage pour arbitrer constat par constat ; groupes « perdus » puis « à arbitrer » en tête, « auto » repliés. Synthèse et filtre « restants seulement » conservés. Vérifié sur 80 constats non auto.
- Modèle cible : cose sur les nœuds connectés, nœuds isolés rangés à droite, noms de relations au survol, multi-labels visibles (14 nœuds Curiosity, 24 Neo4j), dérivées en pointillé. Requêtes : le préfixe SPARQL par défaut suit l'IRI du projet.
- Captures : journal/L5/screens/real-*.png (analyse, modèle, exports, requêtes, assistant). `npm run build` vert.
