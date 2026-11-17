# L49 : rapport du pilote (w3c)

Bonnes pratiques d'ontologie : fiche complète, dépréciation, version sémantique, métadonnées d'en-tête. Contrat : `lots/L49.md`. Décisions : D-L49-01 (vocabulaires), D-L49-02 (règles du diff SemVer). Contrat d'interface : `docs/CONTRACTS.md` §18. Question ouverte : Q-L49-1.

## Livré

1. **Fiche complète.** `conformance/practices.py` : règles BP08 à BP16 (info ou warning, jamais error, hors profil DL), score de complétude par entité et pour l'ontologie, score de l'en-tête. `ConformanceReport.completeness`. W07 accepte `skos:prefLabel`. Fiche éditable dans l'inspecteur du graphe et la vue liste (`screens/practices/EntityCard.tsx`, score recalculé côté client par `card.ts`, miroir de `entity_card`). Écran Conformité : carte « Complétude des fiches ».
2. **Dépréciation.** Opération `set_deprecated` (owl:deprecated, `dcterms:isReplacedBy`, statut `archaic`) ; bouton « Déprécier » / « Ne plus déprécier » dans la fiche ; entité barrée et étiquetée dans le graphe, l'arbre et la vue liste. A03 passe en `review` (exclure par défaut, garder avec drapeau `[DÉPRÉCIÉ]` sur nœud, relation **et** propriété, ce qui manquait). Rapport de transposition : section « Entités dépréciées » (fr/en). BP12/BP13 : remplaçant absent, introuvable ou déprécié, entité dépréciée encore utilisée.
3. **Version sémantique.** `projects/releases.py` + `api/releases.py` : diff de deux OntoModel, niveau majeure / mineure / correctif, numéro proposé, note de version Markdown (fr/en), `releases.json` (30 versions, instantané pour le diff suivant). L'enregistrement pose `owl:versionInfo`, `owl:versionIRI` (IRI de l'ontologie + `/x.y.z`), `owl:priorVersion`, `dcterms:modified` par une opération journalisée (annulable). BP14 (versionInfo SemVer), BP15 (versionIRI distincte, pas de version dans l'espace de noms).
4. **En-tête.** `GET /metadata` + opérations `set_annotations` (liste fermée de propriétés) et `set_version_iri` ; carte « En-tête de l'ontologie » : titre, objectif, version, IRI de version, dates, auteurs, contributeurs, vocabulaires réutilisés, mots-clés, sources, licence. BP16 en-tête incomplet.

## Choix de vocabulaires (références)

| Besoin | Retenu | Référence |
|---|---|---|
| Définition | `skos:definition` (ou `rdfs:comment`) | SKOS Reference §7 ; OWL 2 SS §5.5 |
| Libellés fr / en | `rdfs:label` ou `skos:prefLabel` | OWL 2 SS §5.5 ; SKOS Reference §5 (prefLabel sous-propriété de rdfs:label) |
| Auteur, contributeur, source | `dcterms:creator`, `contributor`, `source` | DCMI Metadata Terms |
| Statut de revue | `vs:term_status` (unstable, testing, stable, archaic) | Semantic Web Vocabulary Status (publié par le W3C, non normatif) |
| Justification d'une caractéristique | `skos:editorialNote` (toute sous-propriété de `skos:note` acceptée) | SKOS Reference §7 |
| Dépréciation | `owl:deprecated true` + `dcterms:isReplacedBy` | OWL 2 SS §5.5 ; DCMI |
| Version | `owl:versionInfo` SemVer, `owl:versionIRI` ≠ IRI d'ontologie, `owl:priorVersion` | OWL 2 SS §3.1, §3.3, §5.5 ; Semantic Versioning 2.0.0 |
| En-tête | `dcterms:title`, `description`, `created`, `modified`, `subject`, `license`, `references` | DCMI ; OWL 2 SS §3.5 |
| Déclarations | propriétés d'annotation non prédéfinies déclarées `owl:AnnotationProperty` | OWL 2 SS §5.8 |
| Dates | `xsd:dateTime` (`xsd:date` hors carte DL) | OWL 2 SS §4 |

Alternatives écartées (D-L49-01) : `adms:status`, `bibo:status`, `voaf:reliesOn` (hors W3C/DCMI) ; annotation d'axiome pour la justification (plus précise, OWL 2 MAP §2.3.2, mais non éditable simplement ; conservée si importée).

## Auto-contrôle

- `cd backend && /home/claude/venv/bin/python -m pytest -q` : **1337 réussis, 0 échec** (après les corrections it2). Nouveau : `tests/test_l49_practices.py` (règles, complétude, opérations, aller-retour Turtle sans perte avec profil DL conservé, dépréciation de bout en bout sur les deux cibles, marques dans les fichiers générés, shapes désactivées, diff SemVer, annulation d'une version, API).
- `npm run build` (tsc + vite) : OK.
- Recette `BACKEND_PORT=9149 FRONT_PORT=5149 node tools/recette/l49_bonnes_pratiques.mjs` : **14/14** (it2 : annulation d'une version, marques dans les fichiers générés) (captures `journal/L49/screens/`).
- i18n : 67 clés ajoutées en fr et en (écriture atomique, parité et espaces réservés vérifiés).
- Aucune nouvelle dépendance. Aucune référence à un document client dans le dépôt.

## Corrections de l'itération 1
Voir `fix-it1.md` : annulation d'une version cohérente avec `releases.json`, shapes des propriétés dépréciées désactivées, drapeau `[DÉPRÉCIÉ]` dans `Edges.cs` et dans tous les fichiers Neo4j, pertes induites par l'exclusion d'une classe dépréciée explicites (A03 + constats `lost` + colonne du rapport).

## Corrections de l'itération 2
Voir `fix-it2.md` : pertes induites calculées avec la résolution de la construction (cas O02 : restriction seule), pertes partielles (union, plusieurs domaines) notées « en partie » sans passer en `lost`, référence d'API et guide alignés.

## Effets à connaître

- A03 `auto` → `review` : chaque entité dépréciée ajoute un point « à arbitrer » (trap : +1, `expected-findings.yaml` mis à jour ; `docs/RULES.md` et `regles*.md` aussi). Cohérent avec L47 (un vrai choix avec perte reste à arbitrer).
- Volume de constats `info` : sur automaint, BP08 (définition manquante) donne une ligne par entité (62). BP09 est regroupé en une ligne quand aucune entité n'a d'auteur, de source ni de statut. Les brouillons de l'assistant n'ont pas ces règles (`lint(..., practices=False)` dans `docdraft.py`).
- `test_collab.py` : ajout de `version` au remplissage des modèles de routes (nouvelle route `/releases/{version}`).
- `localize_pg_for_export` traduit maintenant aussi le préfixe `[DÉPRÉCIÉ]` des descriptions de relations.

## Points à relire

- **query** : `projects/releases.py` (`diff` : comparaison champ à champ, listes comparées comme ensembles sauf chaînes et clés ; annotations posées par l'enregistrement exclues) ; route `POST /releases` (opération journalisée puis `releases.json`, sous `history.lock()`).
- **shacl** : aucune shape générée pour les nouvelles annotations ; `owl_to_shacl` lit déjà `deprecated` (inchangé). À vérifier : faut-il marquer `sh:deactivated` les shapes d'une classe dépréciée exclue ?
- **curiosity / neo4j** : A03 en `review` ; `flag_deprecated` préfixe maintenant aussi propriétés et relations ; section « Entités dépréciées » du rapport. Vérifier le rendu de `[DÉPRÉCIÉ]` dans les commentaires C# / Cypher générés.
- **scout / mobile** : cartes de l'écran Conformité (grille `auto-fit` 240 px) et fiche dans l'inspecteur / la feuille du bas ; non vérifié sur téléphone dans ce lot.
- **doc / humain** : section `#bonnes-pratiques-fiche-versions` (fr/en), CHANGELOG, api, CONTRACTS §18.

## Limites

- Le score de la fiche est calculé deux fois (Python pour la conformité, TypeScript pour la fiche à la volée) : mêmes critères, à garder alignés.
- Le diff compare à la dernière version enregistrée, pas entre deux versions quelconques.
- La note de version est générée dans la langue de l'interface au moment de l'enregistrement.
