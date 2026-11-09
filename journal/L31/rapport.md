# Lot L31 : versions des normes et des cibles

Agent : neo4j + curiosity (générateurs). Brouillon, non relu.

## Livré
- `backend/ontoforge/standards/` : `standards.json` (référence bilingue) et module (statuts, `check`, capacités Neo4j, préfixe Cypher).
- Modèle : `Project.target_versions`, `Settings.versions`, `PGMeta.target_versions` ; API `/api/standards`, `/versions`, `/versions/check`, `/api/settings`.
- Générateurs : Neo4j (préfixe par requête, contraintes selon la version, 4.4 en syntaxe ASSERT), Curiosity (en-têtes, README), rapport, en-tête Turtle SHACL pour une cible non 1.0.
- Front : écran Versions, panneau Paramètres, bulle de Krakie, action `versions` (confirmée, annulable). Krakie : intentions fr/en.
- Tests : `backend/tests/test_versions.py` (34) ; recette `tools/recette/l31_versions.mjs` (12/12), captures `journal/L31/screens/`.

## Écarts et choix à connaître
- SHACL : la Recommandation s'appelle « 1.0 » dans `normes.md` ; l'id est `1.0`, « 1.1 » est accepté comme synonyme. Aucun générateur n'écrit de construction 1.2 : les fonctions sont seulement listées, marquées 1.2 et désactivées.
- Défaut Neo4j 5.26 / Cypher 5 (base stable, D-L21-02). Neo4j 2026.10 est « supportée », pas « recommandée ».
- Neo4j 4.4 : seul `schema.cypher` a une variante ; ingestion et validations restent en syntaxe Neo4j 5. Marqué À VÉRIFIER.
- Préfixe `CYPHER 5` omis sur 5.x (acceptation par 5.26 non vérifiée). Graph types non générés.
- L'export Turtle des shapes reste identique pour SHACL 1.0 (test de contrat existant).
- Le fichier de référence est dans `backend/ontoforge/standards/`, pas dans `docs/veille/`.

## Relectures demandées
neo4j (syntaxes par version, préfixes), curiosity (en-têtes, version NuGet), w3c (statuts et dates), doc, humain (humaniseur sur le guide et les messages), et Jerem pour la décision sur les défauts.
