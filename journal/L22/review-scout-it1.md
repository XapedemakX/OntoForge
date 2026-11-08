# L22 — revue scout (UX), itération 1

Relecteur : éclaireur produit (agent `scout`). Date : 7/11/2026. Matière : `journal/L22/screens/01-erreur-diagnostic.png`, `02-diff-avant-application.png`, `03-graphe-apres-application.png`, `frontend/src/screens/files/`, textes `fx.*`, et le texte servi par l'API sur le projet exemple automaint.
Recette `node tools/recette/l22_files.mjs` **non relancée** : au moment de la revue, `frontend/src/i18n/fr.json` est vide sur disque (réécriture en cours par un autre agent), et la compilation du front ne peut pas passer. Je me fonde sur les captures et sur le résultat 16/16 du pilote.

## Impression d'ensemble
L'écran est cohérent avec l'application : même barre latérale, mêmes jetons de couleur, bouton d'action principal vert à droite, Krakie en bas à droite, cadenas sur les fichiers générés. La disposition IDE se lit vite : arbre, onglet avec point « modifié », panneau Problèmes avec compteurs, barre d'état. L'aperçu avant application (vue fusionnée et « +2 triplets / −0 triplets ») inspire confiance. Le conflit à trois choix est bien formulé.

## Verdict

```
verdict: KO
bloquants:
  - [backend/ontoforge/editing/files.py:59 (canonical_turtle) ; capture 01] sur le projet exemple, le texte servi n'a **pas de préfixe pour l'espace de noms de l'ontologie** : 226 IRI complètes `<https://w3id.org/ontoforge/automaint#…>` dans onto.ttl (`meta.prefixes` du projet = dcterms, skos ; le préfixe `am:` du fichier source est perdu à la création du projet). Pour l'ontologue, c'est le premier contact avec l'écran, et il est illisible. → Si un espace de noms d'entités n'a pas de préfixe, en lier un dans `canonical_turtle`, dérivé de l'IRI d'ontologie (par exemple le dernier segment, sinon `onto:`), et chercher pourquoi l'import de l'exemple perd `am:` (`api/projects.py` → `_parse_onto` / `collect_prefixes`). Un test : « onto.ttl de l'exemple automaint contient moins de 10 IRI complètes de l'espace am ».
  - [frontend/src/i18n/fr.json:1245 ; index.tsx:289] voir la revue w3c : les commentaires saisis sont supprimés à l'application, mais l'avertissement est une ligne grise en bas de l'aperçu qui parle de « normalisation ». Pour l'utilisateur, c'est une perte de travail silencieuse. Il faut un avertissement visible et chiffré dans l'aperçu (« 3 commentaires seront supprimés »), et le mot « supprimés ».
non-bloquants:
  - [capture 01] l'erreur « préfixe non déclaré » est bien soulignée (point rouge en marge, ligne 607). Le libellé « ajouter @prefix foo: <…> . » gagnerait une action rapide « Déclarer le préfixe » qui insère la ligne en tête, comme dans VS Code.
  - [capture 02] l'aperçu affiche « 30 lignes inchangées / 573 lignes inchangées » : bien. Le compteur +N / −M serait plus parlant avec un échantillon cliquable (les `samples` existent déjà dans la réponse).
  - [capture 02] les remarques de lecture (« {n} remarque(s) ») sont repliées par défaut. Si l'import a réécrit des triplets (voir w3c), les déplier.
  - Les diagnostics de la méta-shape SHACL restent en anglais dans l'interface française (voir la revue shacl).
  - Point « . » manquant : l'erreur pointe sur la ligne suivante. L'utilisateur cherche au mauvais endroit (voir w3c).
  - Visite guidée sans étape « Fichiers » (borne de 18 étapes) : je propose de remplacer une étape existante peu utile plutôt que de relever la borne. À trancher par le chef.
  - Mobile en lecture seule : cohérent avec le reste de l'appli.
skill: product-discovery → « Pour tout éditeur texte qui réécrit le contenu (normalisation), l'aperçu doit montrer ce que l'utilisateur perd par rapport à SON texte, pas seulement par rapport à l'état précédent. Vérifier le premier affichage sur l'exemple livré : c'est lui qui fait la première impression. »
```
