# L22 — revue scout (UX), itération 2

Relecteur : éclaireur produit (agent `scout`). Recette `node tools/recette/l22_files.mjs` ouverte moi-même : 23/23, aucune erreur console.

## Bloquants de l'itération 1
- **Premier affichage illisible** : résolu. `onto.ttl` de l'exemple automaint porte `@prefix am:` et moins de 10 IRI complètes (contrôle dans la recette), shapes avec `am:` et `ams:`.
- **Perte silencieuse des commentaires** : résolu. Cas nominal : « vos N lignes de commentaire sont conservées » et le texte revient tel quel à la relecture ; cas de perte : alerte visible et chiffrée « N ligne(s) de commentaire seront supprimées ». Les réécritures s'affichent dépliées.

## Usage après modification venue d'ailleurs
Le fichier rouvre en forme normalisée avec une bannière qui chiffre les commentaires non affichés ; l'annulation ramène le texte saisi. C'est cohérent, mais la formulation prête à confusion quand l'utilisateur a lui-même annulé (voir non-bloquant).

```
verdict: OK
bloquants: []
non-bloquants:
  - [fx.note.canonicalN] « modifié depuis un autre écran… ont été supprimées » est inexact après une annulation (le texte reviendra au rétablissement). Dire « Vos N lignes de commentaire ne sont plus affichées ; elles reviennent si vous annulez la modification ».
  - Un changement de commentaires seul n'est pas annulable : le dire dans l'aperçu (le guide le dit désormais).
  - Action rapide « Déclarer le préfixe », étape « Fichiers » de la visite : toujours à trancher.
skill: product-discovery -> « Une note d'état doit dire ce qui est réversible : "supprimé" ne convient que si rien ne revient. »
```
