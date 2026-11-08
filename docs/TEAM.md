# Protocole de l'équipe OntoForge

## Rôles
| id | Agent | Fiche | Skill(s) maintenu(s) |
|---|---|---|---|
| chef | Chef de projet | .claude/agents/chef-de-projet.md | skills/ontoforge-delivery |
| lead | Lead dev (orchestrateur, moteur de mapping, front, assistant IA) | — | skills/owl-to-property-graph, skills/ontology-rapid-design |
| w3c | Expert W3C | .claude/agents/expert-w3c.md | skills/w3c-ontology-conformance |
| shacl | Expert SHACL | .claude/agents/expert-shacl.md | skills/shacl-modeling |
| query | Expert requêtage | .claude/agents/expert-requetage.md | skills/graph-query-translation |
| curiosity | Expert Curiosity | .claude/agents/expert-curiosity.md | skills/curiosity-schema-design |
| neo4j | Expert Neo4j | .claude/agents/expert-neo4j.md | skills/neo4j-schema-design |
| doc | Documentaliste | .claude/agents/documentaliste.md | skills/technical-documentation |
| scout | Éclaireur produit | .claude/agents/eclaireur-produit.md | skills/product-discovery |
| veille | Veille technologique et normative | .claude/agents/veille-techno.md | skills/tech-watch |
| humain | Humaniseur (dernière passe de rédaction) | .claude/agents/humaniseur.md | skills/humanizer |
| git | Versionnage, CI, livraisons | .claude/agents/git-release.md | — |
| deploy | Déploiement (Cloud Run, ontoforge.ajlx.fr) | .claude/agents/deploiement.md | — |

## Cycle d'un lot
1. **Contrat** — `lots/Lx.md` (chef) : objectif, livrables, fichiers possédés par agent, critères d'acceptation vérifiables (commandes de test, entrées → sorties attendues), relecteurs.
2. **Production** — le pilote code + tests + met à jour son skill. Il ne touche qu'aux fichiers que le contrat lui attribue.
3. **Auto-contrôle** — avant de demander une revue : `make test` (ou la commande du contrat) vert, lint OK.
4. **Revue croisée** — chaque relecteur écrit `journal/Lx/review-<relecteur>-it<N>.md` :
   ```
   verdict: OK | KO
   bloquants:
     - [fichier:ligne] constat → correction attendue
   non-bloquants:
     - ...
   skill: <remarque à intégrer dans un skill, ou "rien">
   ```
5. **Correction** — le pilote traite tous les bloquants, répond dans `journal/Lx/fix-it<N>.md` (bloquant → ce qui a été fait / pourquoi refusé), relance les tests, redemande une revue. Itération N+1.
6. **Escalade** — après 3 itérations sans OK, le chef tranche (`journal/decisions.md`). Question métier → `journal/questions-jerem.md` (Jerem répond quand il veut ; on avance avec l'hypothèse la plus raisonnable, notée).
7. **Clôture** — tests verts + tous les verdicts OK + skills à jour + `journal/Lx/cloture.md` (chef).

## Règles
- Un fichier = un propriétaire par lot. Besoin de modifier le fichier d'un autre → demander dans la revue / via le lead.
- Les contrats d'interface (`backend/ontoforge/core/*.py`, `docs/CONTRACTS.md`) ne changent que par décision tracée dans `journal/decisions.md`.
- Rien d'inventé : une API externe (Curiosity.Library, Neo4j, pySHACL…) dont on n'est pas sûr est marquée `# À VÉRIFIER` et listée dans le rapport du lot.
- Pas de données d'entreprise réelles dans le dépôt : exemples génériques uniquement.
- Français pour la doc et les messages, anglais pour le code.

## Salle des agents (suivi en direct)
URL : https://claude.ai/artifact/UoUzdNu1a6md7T9GN6qmKq — base de données, collection `events`.
Chaque agent publie ses événements avec l'outil `ArtifactData` (le charger via `ToolSearch` : `select:ArtifactData`) :
```
action: "set", url: <URL>, collection: "events", doc_id: "e<YYYYMMDDHHMMSS>-<agent>",
data: { ts: "<ISO 8601 UTC>", agent: "<id>", type: "<start|progress|message|review_ok|review_ko|fix|decision|done|blocked|question>",
        status: "<working|reviewing|fixing|waiting|blocked|done|idle>", lot: "Lx", to: "<id destinataire, optionnel>",
        task: "<ce sur quoi je travaille, 1 ligne>", text: "<message lisible par Jerem, 1-3 phrases>" }
```
Au minimum : au démarrage, à chaque verdict de revue (avec `to` = pilote), à chaque correction (avec `to` = relecteur), à la fin. Pas plus d'un événement toutes les quelques minutes. Si l'outil est indisponible, ajouter la même ligne JSON dans `journal/events.jsonl` (le lead la republiera).

## Limite d'usage (règle du 4/11)
- Dès qu'un agent échoue avec une erreur 429, le lead programme **dans la même réponse** une reprise `send_later` à l'heure de remise à zéro indiquée.
- Filet de sécurité : relances automatiques toutes les 3 à 4 h jusqu'à la livraison du vendredi (mercredi 19h, 22h ; jeudi 1h, 4h, 7h30, 11h, 14h30, 18h démo). À chaque relance : lire les notifications, relancer les agents arrêtés, continuer le plan, ne rien faire s'il n'y a rien à faire.
- Maximum 4 agents en parallèle ; Sonnet par défaut, Opus pour les revues sémantiques et le design.

## Relectures croisées (matrice, depuis le 7/11)
| Type de livrable | Relecteurs obligatoires | Dernière passe |
|---|---|---|
| Code sémantique (OWL, RDF, SPARQL, triplestore) | w3c + query | doc |
| Shapes / validation | shacl + w3c | doc |
| Générateurs Curiosity / Neo4j | curiosity / neo4j + w3c | doc |
| Écran ou fonction d'interface | scout (UX) + expert du domaine | doc |
| Fiche de veille | expert du domaine | humain |
| Documentation | doc (exactitude) | humain (style), puis doc vérifie que le sens n'a pas bougé |
| Livraison | chef + git (CI verte, tag) | — |
| Déploiement / sécurité réseau | deploy + query (SSRF) + scout (connexion) | doc |

Un lot n'est clos qu'avec : tests verts, verdicts OK des relecteurs, `journal/<lot>/doc-ok.md`, passage de l'humaniseur sur la doc du lot, puis push par l'agent git.
