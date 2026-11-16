---
name: ontoforge-cloture-lot
description: Checklist de clôture d'un lot OntoForge (tests, revues croisées selon la matrice, doc-ok, humaniseur, captures, skills, journal, publication) ; à utiliser en fin de lot pour ne rien oublier et choisir le bon modèle pour chaque passe.
---

# Clôturer un lot OntoForge

Propre au dépôt : s'appuie sur `docs/TEAM.md` (protocole normatif), `lots/`, `journal/`. Méthode générique : `ontoforge-delivery`.

## Ordre
1. **Auto-contrôle** (pilote) : `cd backend && pytest -q`, `cd frontend && npm run build`, commande du contrat de lot. Rien à demander en revue tant que c'est rouge.
2. **Revues croisées** : consulter la matrice de `docs/TEAM.md` (type de livrable → relecteurs obligatoires → dernière passe). Chaque relecteur écrit `journal/Lx/review-<id>-it<N>.md` (verdict OK/KO, bloquants `fichier:ligne`, `skill:`). Tout lot touchant aux entrées, fichiers, appels sortants, secrets, authentification ou à l'assistant : revue sécurité (`audit-securite-cve-cwe`). Front, CSS : mobile + UX.
3. **Corrections** : `journal/Lx/fix-it<N>.md` bloquant par bloquant ; 3 itérations KO max, puis le chef tranche (`journal/decisions.md`, décision numérotée jamais réécrite). Question métier : `journal/questions-jerem.md` avec hypothèse retenue.
4. **Recette** : recette Playwright du lot + `e2e_ui.mjs` (`recette-playwright-par-lot`) ; captures régénérées si un écran change, committées à part (`doc-bilingue-captures`).
5. **Documentation** : documentaliste vérifie chaque affirmation contre le code → `journal/Lx/doc-ok.md` ; humaniseur ensuite ; documentaliste revérifie que le sens n'a pas bougé. i18n par `i18n-ecriture-sure`.
6. **Skills** : mettre à jour les skills du rôle (lignes `skill:` des revues), tenir `docs/skills-inventaire.md` et le tableau « Skills maintenus » de `docs/TEAM.md`.
7. **Clôture** (chef) : relance lui-même les commandes, écrit `journal/Lx/cloture.md` (critères, revues, coupes, « À VÉRIFIER », leçon).
8. **Publication** (agent git) : `tools/git/publish.sh "Lot Lx : sujet"` (`publication-github-securisee`) ; `--push` seulement sur demande.

## Modèles (règle de coût du 8/11)
Haiku : publication, événements, rejeu de recettes. Sonnet par défaut : production, corrections, relectures UX/doc, humaniseur. Opus : relectures sémantiques W3C sensibles et design visuel. Après une limite d'usage (429), reprise programmée dans la même réponse ; relancer l'agent arrêté par message plutôt qu'en créer un nouveau. Maximum 4 agents en parallèle.

## Suivi
Événements dans la Salle des agents (`ArtifactData`, collection `events`) au démarrage, à chaque verdict, à chaque correction, à la fin ; repli `journal/events.jsonl`.
