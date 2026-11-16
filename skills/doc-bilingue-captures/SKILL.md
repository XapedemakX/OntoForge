---
name: doc-bilingue-captures
description: Produire une documentation utilisateur bilingue fr/en avec ancres d'aide communes et captures d'écran reproductibles par script Playwright ; à utiliser quand un guide doit exister en deux langues, être relié à un bouton « ? » ou à un assistant, ou que les captures doivent se régénérer en une commande.
---

# Documentation bilingue avec captures reproductibles

Complète `technical-documentation` (contenu) par la mécanique fr/en et l'outillage d'images.

## 1. Fichiers et ancres
- Un fichier par langue et par page : `page.md` (français) et `page.en.md`. Même plan, mêmes titres dans le même ordre.
- Chaque titre se termine par un identifiant explicite : `## Créer un projet {#creer-un-projet}`. On traduit le texte du titre, **jamais l'identifiant** : le bouton d'aide, l'assistant et la table `help_map.json` pointent vers `page#id`.
- Un test automatique compare les ancres fr et en (`backend/tests/test_help_map.py`) et échoue en cas d'écart. Pour poser les identifiants sur un fichier qui n'en a pas : `python tools/doc_ids.py page.md` (même algorithme de slug que le test).
- Écrire l'anglais directement, avec les règles de style adaptées (skill `humanizer`), plutôt que de traduire mot à mot ; citer les libellés d'interface tels qu'ils sont dans `en.json`.
- Les pages qu'on ne traduit pas gardent un bandeau explicite (« French only »).

## 2. Captures reproductibles
- Un générateur unique (`tools/docs/captures.mjs`) lit une liste déclarative (`captures-list.mjs`, `cap(groupe, nom, async c => { … c.snap(nom) })`), lance un backend jetable (IA simulée) et le front buildé, puis prend chaque capture dans les deux langues : `docs/guide/img/<fr|en>/<nom>.png`, mêmes noms.
- Fenêtre fixe (1440×900), thème clair, mêmes données dans les deux langues. Les libellés viennent du dictionnaire (`c.t('clé')`).
- Annotations (pastilles numérotées, cadres) injectées dans la page juste avant la prise puis retirées ; la légende du guide les cite : `![alt](img/fr/x.png "1 la liste, 2 la recherche")`.
- Options utiles : `--lang`, `--only nom1,groupe`, `--no-optimize`, `--keep-servers`, `REUSE=1`.
- On ne retouche jamais une capture à la main ; un lot qui change un écran relance le générateur, regarde quelques images dans les deux langues (outil Read sur le PNG) et committe images et texte ensemble.

## 3. Optimisation et contrôle
- `python -I tools/docs/optimize.py docs/guide/img` : largeur 1280 px max, palette 128 couleurs (repli 64 puis 32), cible 100 Ko, plafond 150 Ko ; écrit `sizes.json` pour réserver la place dans la page (pas de saut de mise en page).
- Texte français resté dans une capture anglaise : `python -I tools/docs/scan_fr_in_en.py` (OCR tesseract). À relire à la main : les données d'exemple en `@fr` et le bruit d'OCR sont attendus.
- Images chargées à la demande (`loading=lazy`, clic pour agrandir).

## 4. Pièges
- Le texte généré côté serveur (rapports, commentaires de fichiers exportés) reste dans la langue du serveur : le signaler dans la FAQ des limites plutôt que de le cacher.
- Une capture montre un état de données : fixer le jeu d'exemple, sinon les chiffres changent d'une régénération à l'autre.
- Ports du générateur distincts de ceux des recettes (voir `recette-playwright-par-lot`).
- Chaque affirmation du guide est vérifiée contre le code ou un test avant `doc-ok.md` ; l'humaniseur passe ensuite, puis le documentaliste vérifie que le sens n'a pas bougé.
- Aucune vraie clé dans une capture : valeurs factices (`sk-ant-FACTICE-…`, `sparql.example.org`).
