# L21 : vérification documentaire (doc)

verdict: OK après corrections (liste ci-dessous). Vérifié contre `journal/L21/rapport.md`, les trois revues it1, `journal/decisions.md` (D-L21-01 à 03), `backend/pyproject.toml`, `.github/` et le code.

## Écarts corrigés

1. `processus-mise-a-jour.md`, « Réponse courte » : « trois choses » puis quatre points. Reformulé : trois étapes automatisées (détecter, proposer, prouver) et une quatrième, humaine (décider).
2. Décisions D-L21-01, D-L21-02 et D-L21-03 : ajoutées dans `normes.md` (bloc « Décisions de Jerem », synthèse, note de la partie 4, suite donnée aux actions A1 à A8) et dans `processus-mise-a-jour.md` (réponse courte, §1 tâche non créée, §2 Dependabot, §3.1 à 3.3, §6 avec colonne « État »). Les analyses ne sont pas réécrites.
3. `IDEES.md` V-01, V-02, V-03, V-04, V-05, V-06 et V-19 : renvoi aux décisions.
4. `normes.md` l. 4 : « relecture attendue » remplacé par l'état réel (w3c, neo4j, curiosity OK ; shacl et query restent à faire).
5. `normes.md` synthèse : « publiés cette semaine » remplacé par les dates (SPARQL 1.2 Query 01/11, SHACL 1.2 Core 02/11), demande de la revue w3c.
6. Dérive avec le code : pyoxigraph est épinglé (0.5.13) depuis L19 et pypdf (7.0.0) depuis L25, alors que `normes.md` disait « non ajouté » ; ligne pypdf ajoutée. RDF-star : `localstore/_worker.py` rend un triplet cité en texte ; la mention « aucune occurrence » est corrigée.
7. `processus-mise-a-jour.md` : « quatre bibliothèques » sémantiques, alors que le groupe en compte cinq (owlready2), idem le commentaire de `.github/dependabot.yml` ; « montées majeures de React, Vite… » alors que toutes les majeures sont ignorées ; « pas d'écosystème github-actions tant qu'aucun workflow n'existe » alors que `ci.yml` existe (L24) et que l'écosystème est configuré ; tâche 4 de §6 (workflow CI) faite par L24.
8. `processus-mise-a-jour.md` §4 : la référence à `IDEES.md` disait V-01 au lieu de V-11 ; les déclencheurs clavier de l'easter egg sont déjà pris (L20), le geste du panneau reste à choisir. §3.1 : cas de test OWL 2 rattachés à la REC *OWL 2 Conformance*, demande de la revue w3c.
9. `skills/product-discovery/SKILL.md` : frontmatter YAML invalide (deux-points dans la description non entouré de guillemets, signalé dans `journal/L23/rapport.md`). Phrase reformulée ; les `SKILL.md` de `skills/` se chargent tous avec `yaml.safe_load`.

## Cohérence versions et dates

Curiosity.Library 26.11.7740 (05/11/2026) est identique dans `normes.md` (synthèse, §3, A2), `processus-mise-a-jour.md` (§3.3, `standards.json`), `IDEES.md` (V-02) et `journal/L21/rapport.md`. Aucune trace de 26.10.6546 hors de la mention de correction. Neo4j 2026.10.0 (20/10/2026), 5.26 LTS, pyshacl 0.40.2, rdflib 7.6.0, owlrl 7.6.2 : concordants entre les fiches et les revues.

## Restes

- `journal/L21/rapport.md` (journal, non modifié) garde les questions ouvertes à Jerem et les « trois actions prioritaires » écrites avant les décisions du 7/11.
- Restent ouverts : relectures shacl et query, version de pypdf la plus récente non relevée, date de 2026.10.1 et de pyshacl 0.40.2 (PyPI contre journal), tous À VÉRIFIER dans `normes.md`.
