---
name: agent-team-delivery
description: Piloter une équipe d'agents Claude qui s'auto-valident pour livrer un logiciel dans un délai court — découpage en lots, contrats de lot à critères exécutables, attribution de fichiers sans recouvrement, revues croisées à verdict OK/KO, escalade, clôture et suivi en direct. À utiliser quand on orchestre plusieurs agents spécialisés (chef de projet, lead dev, experts) sur un même dépôt, qu'on rédige un contrat de lot, qu'on relit le livrable d'un autre agent ou qu'on doit replanifier sous contrainte de délai.
---

# Piloter une équipe d'agents qui s'auto-valident

Méthode éprouvée sur OntoForge (6 agents, 4 jours puis 20 h). Générique : remplacer les noms de lots, d'agents et de fichiers.

## 1. Principes
1. **Le contrat avant le code.** Les modèles de données et l'API sont figés en premier par un seul propriétaire, dans des fichiers versionnés (code + un document normatif). Les contrats de lot **y renvoient** sans les recopier : deux définitions divergent toujours.
2. **Un fichier = un propriétaire par lot.** Toute modification du fichier d'un autre passe par la revue. Les fichiers transverses (manifeste de dépendances, Dockerfile, point d'entrée) ont un propriétaire permanent.
3. **Critère d'acceptation = commande + résultat attendu.** Pas de « fonctionne correctement ». Si un critère ne peut pas être exécuté dans l'environnement de build, on le dit et on le déplace vers une recette humaine unique.
4. **Un oracle écrit par un autre agent que l'implémenteur.** Pour le cœur métier, un expert écrit en parallèle un jeu piège + les résultats attendus (fichier machine-lisible). Les tests de l'implémenteur le consomment tel quel.
5. **Aucune perte silencieuse.** Tout ce qui n'est pas traité produit un signal visible (warning, constat générique). C'est ce qui permet de couper du périmètre sans mentir.
6. **L'humain ne fait que les démos.** Questions métier non bloquantes → fichier de questions avec hypothèse retenue ; on n'attend jamais une réponse.
7. **Le délai gagne.** Tout ce qui menace la livraison est coupé selon un **ordre de coupe décidé à l'avance**, et tracé.

## 2. Cycle d'un lot
1. **Contrat** (chef) — gabarit §5.
2. **Production** (pilote) — code + tests + mise à jour de son skill, uniquement dans ses fichiers.
3. **Auto-contrôle** — la commande de test du contrat est verte avant toute demande de revue.
4. **Revue croisée** — chaque relecteur écrit sa revue (gabarit §6). Un écart à une norme est toujours bloquant.
5. **Correction** — le pilote répond bloquant par bloquant (`fix-itN`), relance les tests, redemande une revue.
6. **Escalade** — après 3 itérations KO, le chef tranche en citant les arguments, dans le journal des décisions.
7. **Clôture** (chef) — il **relance lui-même** les commandes, vérifie les verdicts OK et les skills, écrit la clôture (gabarit §7).

## 3. Rôle du chef de projet (agent qui ne code pas)
- Tient : backlog MoSCoW (Must = ce qui est recetté à la prochaine échéance), contrats de lot, journal des décisions (numérotées, jamais réécrites : une décision en remplace une autre), questions à l'humain.
- Vérifie l'environnement **avant** d'écrire les critères : interpréteur, registres de paquets joignables, outils présents (compilateur, base de données, navigateur), images de base. Exemple vécu : registre Docker inaccessible → tout critère Docker devient revue statique + recette humaine ; image `python:X-slim` passée à une nouvelle Debian → paquet système disparu.
- Cherche des **substituts exécutables** quand l'outil cible manque : analyseur syntaxique (tree-sitter pour C#), parseur de schéma (graphql-core), regex de formes autorisées (DDL), validateur de référence (pySHACL), client HTTP simulé (`MockTransport`) pour un fournisseur d'API.
- Publie ses événements dans le canal de suivi (start, progress, review, done), un toutes les quelques minutes au plus.

## 4. Replanifier sous contrainte (leçons)
- Quand l'échéance avance : **itération 1 = un parcours de bout en bout très étroit** (charger → analyser → arbitrer → exporter), le reste devient Should de l'itération 2 ; chaque critère porte une colonne `It.`.
- Paralléliser par **contrat figé + données de test construites à la main** : un générateur se teste sur un modèle pivot écrit dans ses tests sans attendre le moteur qui le produira ; l'intégration réelle a un créneau dédié avant la clôture.
- Identifier le **goulot humain-agent** (souvent le lead : moteur + front + IA) et écrire dans les contrats ce qui sera coupé à quelle heure s'il glisse.
- Quand le travail a démarré avant les contrats : réécrire les contrats comme **contrats d'acceptation et de revue** du travail en cours, aligner les décisions (« remplace D-xxx ») et ne rien redéfinir.
- Horaires cibles absolus (jour + heure, fuseau) dans chaque contrat : revue 1 h avant la clôture.

## 5. Gabarit — contrat de lot (`lots/Lx.md`)
```markdown
# Lx — <titre>
> Contrat d'acceptation et de revue. Normatif : <docs/CONTRACTS.md §…, fichiers de modèles>. Rien n'est redéfini ici.

| | |
|---|---|
| Pilote(s) | <agent> (<fichiers clés>) |
| Relecteurs | <agents, angle de chacun> |
| Dépend de | <lots, livrables précis> |
| Heure cible | <jour HH:MM → jour HH:MM, fuseau> — revue <HH:MM> |
| Itération | <1 / 2 : ce qui est dans chaque> |
| Besoin couvert | <points de la définition du « fait »> |

## Périmètre
- It1 : …   - It2 : …

## Fichiers (un fichier, un propriétaire)
| Agent | Fichiers |

## Critères d'acceptation (exécutables ici)
| # | It. | Commande | Résultat attendu |
| A1 | 1 | `<cmd test globale>` | exit 0, aucun test des lots précédents cassé |
| A2 | 1 | `<cmd ciblée sur l'oracle>` | <égalité exacte avec le fichier attendu> |
| … | | | |
Recette non exécutable ici : <où, par qui, quand>.

## Relecture
## Risques
| Risque | Proba | Parade (avec heure de coupe) |
```

## 6. Gabarit — revue (`journal/Lx/review-<relecteur>-it<N>.md`)
```markdown
verdict: OK | KO
périmètre relu: <fichiers, commit/heure>
commandes rejouées:
  - `<cmd>` → <résultat obtenu>
bloquants:
  - [fichier:ligne] constat → correction attendue
non-bloquants:
  - …
skill: <remarque à intégrer dans un skill, ou "rien">
```
Règles : un bloquant cite un fichier et propose la correction exacte ; une revue OK peut contenir des non-bloquants ; on rejoue soi-même au moins une commande du contrat ; on vérifie la couverture (chaque règle / exigence du référentiel a au moins un cas de test).

## 7. Gabarit — clôture (`journal/Lx/cloture.md`)
```markdown
# Clôture Lx — <date heure>
- Critères : A1 ✅ (<sortie résumée>) · A2 ✅ · … · A9 ⏭ It2
- Revues : <relecteur> itN OK · …
- Coupes / reports : <élément> → <itération / décision D-xxx>
- Points « À VÉRIFIER » : <liste>
- Durée réelle vs cible : <h> / <h> ; itérations de revue : <n>
- Skills mis à jour : <liste>
- Leçon pour le skill de pilotage : <1-3 lignes>
```

## 8. Événement de suivi (canal partagé)
```
doc_id: e<YYYYMMDDHHMMSS>-<agent>
{ ts, agent, type: start|progress|message|review_ok|review_ko|fix|decision|done|blocked|question,
  status: working|reviewing|fixing|waiting|blocked|done|idle, lot, to?, task: "<1 ligne>", text: "<1-3 phrases lisibles par l'humain>" }
```
Au minimum : démarrage, chaque verdict (to = pilote), chaque correction (to = relecteur), fin. Si l'outil est indisponible : ligne JSON dans `journal/events.jsonl`.

## 9. Vérifier un oracle (jeu piège + résultats attendus)
1. Il se charge sans erreur avec l'outil de référence (parseur, validateur).
2. Chaque règle du référentiel apparaît dans l'oracle (script de couverture : règles manquantes = bloquant).
3. Chaque sujet attendu existe dans le jeu de test ; identifiants d'entrées uniques.
4. Les résultats chiffrés sont reproduits à la main avec l'outil de référence (ex. nombre exact de violations).
5. Les attentes sont machine-lisibles (pas seulement dans des commentaires) et précisent comparaison exacte vs ensemble minimal, et les **interdits** (`must_not`).
6. Toute modification du référentiel (nouvelles règles, sévérités changées) est une décision tracée avec justification.

## Leçons du projet
- (L0) Le planning a changé deux fois en une heure (échéance avancée de 4 jours, contrats figés par le lead en parallèle) : écrire les contrats de lot **après** avoir relu l'état réel du dépôt, et les formuler en critères d'acceptation plutôt qu'en ordres de démarrage.
- (L0) Vérifier les registres de paquets dès le cadrage a permis d'imposer des contrôles syntaxiques réels (tree-sitter, graphql-core) au lieu de « relecture visuelle ».
- (L0) L'oracle écrit par l'expert a étendu le référentiel (36 → 66 règles) : prévoir dès le contrat qu'un oracle peut changer le référentiel, et le tracer.

## 10. Budget d'usage et pilotage multi-agents (leçons OntoForge, nuit du 2 au 3 nov.)
- **La limite d'usage est une contrainte de planning, pas un incident.** Dix agents Opus en parallèle ont atteint la limite de 5 h ; tout le travail non commité a failli être perdu. Règles : **vagues de 4 à 5 agents** au plus ; **commit après chaque livrable** (un commit « sauvegarde avant pause » vaut mieux qu'un fichier jamais écrit) ; chaque agent écrit son rapport (`journal/Lx/rapport-*.md`) dès qu'il a un état stable.
- **Choix du modèle par nature de tâche.** *Sonnet par défaut* (io, SHACL, générateurs, front, assistant, chef de projet). *Opus* pour le cœur sémantique (moteur de mapping, catalogue de règles) et les **revues** (un écart de norme se détecte mieux avec le modèle le plus fort). *Haiku* pour l'exécution mécanique : rejouer les commandes des critères, tests, journal, événements de suivi. Écrire ce plan dans un fichier (`journal/reprise.md`) avant la coupure pour qu'il survive à la reprise.
- **Contrats d'interface figés tôt pour paralléliser.** Les modèles (`core/*.py`) et l'API (`docs/CONTRACTS.md`) ont été figés par le lead en une heure ; cinq agents ont ensuite travaillé sans se bloquer, chacun testant contre un modèle pivot construit à la main. Corollaire : **les contrats de lot rédigés avant ou pendant le gel divergent** (36 endpoints vs 27, `auto:` vs `am:`, goldens vs invariants). Après gel, le chef ré-écrit les lots en critères d'acceptation **sur les noms réels de fichiers de tests et de commandes `-k`** et rejoue la suite lui-même.
- **Reprendre un agent interrompu à partir des fichiers.** Ne pas repartir de zéro : donner au nouvel agent la même consigne que l'ancien, plus « un agent précédent a commencé ; lis l'état de tes fichiers, `git log` et son rapport, puis complète ». Faire lister d'abord ce qui existe et ce qui manque (état repris / livré / points ouverts, comme dans les rapports L4). Pour les agents qui gardent leur contexte, la reprise par message est moins chère qu'un agent neuf (moteur de mapping en Opus).
- **Les agents avancent plus vite que les contrats.** Au bout d'une nuit, plusieurs lots avaient livré des éléments de l'itération 2 : décider (et tracer) de les **garder hors de la clôture** plutôt que de les défaire ; les rejouer en recette sans élargir le périmètre.
- **Repérer le chemin critique par l'absence de fichiers**, pas par les déclarations : `ls` du moteur, du rapport, du service d'assistant, des scripts front. Une liste de fichiers attendus par lot, avec heure de jalon et seuil de coupe, remplace le « ça avance ».
- **Les environnements de livraison cassent en silence** : une image de base qui change de distribution (paquet Java disparu), une fixture ajoutée à un dossier d'exemples qui change ce que charge l'exemple, des paquets de test absents du manifeste. Les critères « statiques » (`grep` sur le Dockerfile, test de listing des exemples) les attrapent ; les rejouer à chaque tour.
- **Repli sans canal de suivi** : `journal/events.jsonl` quand l'outil de suivi n'est pas chargé ; le lead (ou le chef) republie en lot.
