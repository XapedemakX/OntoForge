# Contribuer : comment l'équipe d'agents travaille

OntoForge est construit par une **équipe d'agents Claude qui s'auto-valident**, sous le pilotage de Jerem (qui ne valide que les démos, D-009). Ce guide décrit le fonctionnement pour qu'un nouvel agent — ou un humain — puisse reprendre le travail sans historique. Sources : `docs/TEAM.md` (protocole normatif), `docs/PLAN.md`, `docs/PLAN-IT2.md`, `lots/`, `journal/decisions.md`, `skills/ontoforge-delivery/SKILL.md`.

## 1. Les rôles

| id | Agent | Fiche | Skill maintenu |
|---|---|---|---|
| `chef` | Chef de projet : contrats de lot, backlog MoSCoW, décisions, recette ; **ne code jamais** | `.claude/agents/chef-de-projet.md` | `skills/ontoforge-delivery` |
| `lead` | Lead dev : orchestration, moteur de mapping, front, assistant IA, stockage, API | — | `skills/owl-to-property-graph`, `skills/ontology-rapid-design` |
| `w3c` | Expert W3C : import/export RDF, conformité OWL 2, oracle, revues sémantiques | `.claude/agents/expert-w3c.md` | `skills/w3c-ontology-conformance` |
| `shacl` | Expert SHACL : import/export, génération, validation, traduction vers contraintes PG | `.claude/agents/expert-shacl.md` | `skills/shacl-modeling` |
| `query` | Expert requêtage : traduction SPARQL, GraphQL, questions de compétence | `.claude/agents/expert-requetage.md` | `skills/graph-query-translation` |
| `curiosity` | Expert Curiosity : profil et générateur C# | `.claude/agents/expert-curiosity.md` | `skills/curiosity-schema-design` |
| `neo4j` | Expert Neo4j : profil et générateur Cypher | `.claude/agents/expert-neo4j.md` | `skills/neo4j-schema-design` |
| `doc` | Documentaliste (itération 2) : tout le guide ; **aucune clôture de lot sans son passage** | `.claude/agents/documentaliste.md` | `skills/technical-documentation` |
| `scout` | Éclaireur produit (itération 2) : carnet d'idées, priorisé ; ne code pas | `.claude/agents/eclaireur-produit.md` | `skills/product-discovery` |

Modèles : Sonnet par défaut, Opus pour le design et les revues sémantiques, Haiku pour exécuter la recette ; quatre agents en parallèle au maximum (`docs/PLAN-IT2.md`).

## 2. Le cycle d'un lot

Un **lot** (`lots/Lx.md`) est l'unité de travail. Cycle (`docs/TEAM.md`) :

1. **Contrat** (chef) : objectif, livrables, fichiers possédés par agent, **critères d'acceptation exécutables** (commande + résultat attendu), relecteurs.
2. **Production** (pilote) : code, tests, mise à jour de son skill ; il ne touche qu'aux fichiers que le contrat lui attribue.
3. **Auto-contrôle** : `cd backend && pytest -q` (ou la commande du contrat) vert, build du front vert.
4. **Revue croisée** : chaque relecteur écrit `journal/Lx/review-<relecteur>-it<N>.md` :
   ```
   verdict: OK | KO
   bloquants:
     - [fichier:ligne] constat → correction attendue
   non-bloquants:
     - ...
   skill: <remarque à intégrer dans un skill, ou "rien">
   ```
5. **Correction** : le pilote répond à **chaque bloquant** dans `journal/Lx/fix-it<N>.md` (ce qui a été fait, ou pourquoi refusé), relance les tests, redemande une revue (itération N+1).
6. **Escalade** : après **3 itérations** sans OK, le chef tranche (`journal/decisions.md`). Question métier → `journal/questions-jerem.md` : on avance avec l'hypothèse la plus raisonnable, notée.
7. **Clôture** : tests verts + tous les verdicts OK + skills à jour + `journal/Lx/cloture.md` (chef) + **`journal/Lx/doc-ok.md` (documentaliste)** depuis l'itération 2.

Exemple vécu : la revue W3C de L4 (`journal/L4/review-w3c-it1.md`, KO) a fait corriger le traducteur (classe absente = motif vide + perte) ; l'itération 2 (KO) a révélé le même défaut pour les propriétés, corrigé ensuite.

## 3. Règles du jeu

- **Un fichier = un propriétaire par lot.** Le fichier d'un autre agent ne se modifie pas : on le demande dans la revue ou via le lead. Fichiers transverses à propriétaire permanent : `backend/pyproject.toml`, `Dockerfile`, `docker-compose.yml`, `main.py`, `tests/conftest.py`, `frontend/**` → lead (D-015).
- **Les contrats d'interface sont normatifs** : `backend/ontoforge/core/*.py` et `docs/CONTRACTS.md` (D-028) ne changent que par une décision tracée dans `journal/decisions.md`. Une demande d'évolution s'écrit dans `journal/Lx/demandes-contrat.md`.
- **Décisions numérotées, jamais réécrites** : `D-NNN | date | décideur | décision | justification`. Une nouvelle décision en remplace une ancienne (« remplace D-xxx »).
- **Rien d'inventé** : une API externe dont on n'est pas sûr (Curiosity.Library, Neo4j, pySHACL…) est marquée `À VÉRIFIER` dans le code et listée dans le rapport du lot.
- **Aucune perte silencieuse** : tout ce qui n'est pas transposé produit un signal visible (constat, G01, note du rapport).
- **Un oracle écrit par un autre agent** : l'expert W3C a écrit `samples/trap/` + `expected-findings.yaml` en parallèle du moteur ; les tests du moteur le rejouent.
- **Pas de données réelles** dans le dépôt : exemples génériques uniquement (domaine : maintenance automobile, espace de noms `am:` = `https://w3id.org/ontoforge/automaint#`).
- **Langues** : français pour la documentation et les messages, anglais pour le code.
- **Ordre de coupe** si le délai menace (D-018) : HermiT/owlready2 → traduction Curiosity des requêtes → GraphQL → ingestion/validations Neo4j → fournisseurs LLM autres qu'Anthropic → DDL Neo4j. Jamais coupés : import, conformité de base, validation SHACL, analyse et génération Curiosity, arbitrage, export.
- **Limite d'usage** : au premier refus (429), ne rien relancer ; reprise programmée à l'heure de remise à zéro (`journal/reprise.md`).

## 4. Questions aux experts (documentaliste)

Quand une décision ou une limite n'est pas expliquée par le code, le documentaliste **ne devine jamais** : il écrit la question dans `journal/doc/questions.md` (question, destinataire parmi `w3c`, `shacl`, `query`, `curiosity`, `neo4j`, `lead`, `chef`, contexte). Le lead relaie et note la réponse ; en attendant, le guide porte la mention `À CONFIRMER`.

## 5. Salle des agents (suivi en direct)

Base de données de l'artifact `https://claude.ai/artifact/UoUzdNu1a6md7T9GN6qmKq`, collection `events`. Chaque agent publie avec l'outil `ArtifactData` (à charger via `ToolSearch` : `select:ArtifactData`) :

```
action: "set", url: <URL>, collection: "events", doc_id: "e<YYYYMMDDHHMMSS>-<agent>",
data: { ts: "<ISO 8601 UTC>", agent: "<id>", type: "<start|progress|message|review_ok|review_ko|fix|decision|done|blocked|question>",
        status: "<working|reviewing|fixing|waiting|blocked|done|idle>", lot: "Lx", to: "<id destinataire, optionnel>",
        task: "<ce sur quoi je travaille, 1 ligne>", text: "<message lisible par Jerem, 1-3 phrases>" }
```

Au minimum : au démarrage, à chaque verdict de revue (avec `to` = pilote), à chaque correction (avec `to` = relecteur), à la fin. Pas plus d'un événement toutes les quelques minutes. Outil indisponible : ajouter la même ligne JSON dans `journal/events.jsonl` (le lead la republiera).

## 6. Skills

Un skill (`skills/<nom>/SKILL.md`, frontmatter `name` / `description`) est une **méthode réutilisable** maintenue par son agent à chaque lot : ce que le projet a appris, hors du contexte d'OntoForge autant que possible. Les relecteurs y reportent leurs remarques (ligne `skill:` de la revue). État : 9 skills — transposition OWL → LPG, SHACL, conformité W3C, Curiosity, Neo4j, requêtes, conception rapide d'ontologies, pilotage d'équipe d'agents, découverte produit — plus `technical-documentation` (documentation d'un logiciel construit par une équipe d'agents).

## 7. Travailler sur le code

```bash
cd backend && python -m venv .venv && . .venv/bin/activate && pip install -e ".[dev]"
ONTOFORGE_LLM_PROVIDER=mock uvicorn ontoforge.main:app --port 8000   # API sur :8000, /docs
pytest -q                                                             # 462 tests (3 nov. 2026)
cd ../frontend && npm install && npm run dev                          # http://localhost:5173, proxy /api → :8000
npm run build                                                         # doit rester vert
```

Conventions de test : `backend/tests/test_<module>.py`, fixtures dans `samples/`, **aucun accès réseau** (fournisseur `mock`). Les générateurs se testent par déterminisme, invariants et formes autorisées, pas par fichiers « golden » (D-038). Pour ajouter ou modifier une règle de transposition : modifier `mapping/rules/catalog.py` (source unique), la détection dans le module de famille correspondant, l'oracle si le comportement attendu change, puis régénérer `docs/RULES.md` ; le documentaliste met à jour [`regles.md`](regles.md).

## 8. Documentation : définition de « terminé »

Depuis l'itération 2, un lot n'est clos que si la documentation reflète le lot : `journal/<lot>/doc-ok.md` écrit par le documentaliste après vérification **contre le code ou un test** (chaque affirmation cite sa source). Le guide vit dans `docs/guide/` : [`utilisateur.md`](utilisateur.md), [`architecture.md`](architecture.md), [`api.md`](api.md), [`regles.md`](regles.md), [`glossaire.md`](glossaire.md), [`limites.md`](limites.md), [`CHANGELOG.md`](CHANGELOG.md) et ce fichier. `api.md` est généré depuis l'application FastAPI (`app.openapi()`) et complété d'exemples réels.
