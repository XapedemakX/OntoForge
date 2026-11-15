# L36a — Carte métier, rapport backend

## Livré
- Paquet `backend/ontoforge/businessmap/` : `model` (état persistant), `graph` (schéma neutre issu de l'ontologie ou du PGModel), `counts`, `roles`, `zones` (5 stratégies), `frames`, `layout` (recuit simulé), `service`.
- API `backend/ontoforge/api/business_map.py` : GET et PUT `/business-map`, POST `suggest-zones`, `suggest-frames`, `layout`, avec `?source=ontology|target`.
- `Project.business_maps` (champ optionnel, rétrocompatible) ; contrat complet et exemple sur automaint dans `docs/CONTRACTS.md` §13.
- Tests : `backend/tests/test_business_map.py` (19 tests). Suite complète : 1009 réussis.

## Décisions
- **numpy absent du venv et des dépendances** : recuit écrit en Python pur, coûts incrémentaux (seuls les termes qui touchent le nœud déplacé), calibrage de la vitesse après 100 itérations (nombre d'itérations réduit si le budget de temps ne suffit pas) ; 60 nœuds en 3,5 s au plus (D-L21-02 respectée, aucune dépendance ajoutée).
- La mise en page est reprise de l'idée du recuit de Jerem (pénalités de chevauchement, de passage près d'un nœud étranger, de croisements, d'arêtes courtes ou longues, d'ancrage), réécrite et générique ; aucun nom, type ou volume de son workspace n'entre dans le dépôt.
- Les rectangles de zone ne sont pas enregistrés : toujours recalculés (grille proportionnelle aux membres), pour qu'ils restent cohérents après une modification des zones.
- Une première lecture sans carte enregistre la proposition (`generated: true`) sans toucher `updated_at` du projet.
- Cadres : « même relation » = même propriété (même nom de type d'arête pour la cible) vers la même cible.
- `count` : 0 est une vraie valeur (classe sans individu dans la source retenue), `null` seulement sans aucune donnée.

## Limites connues
- Pour la source `target` avec Curiosity, les types d'arête portent toujours un `reverse` ; seules les inverses qui existent comme types d'arête distincts (ou symétriques) sont fusionnées en `both`, `inverse_label` renseigne le nom du retour dans tous les cas.
- Zones par `hierarchy` sur la cible Curiosity : l'héritage est aplati, la proposition initiale bascule alors sur les communautés si une zone dépasse 60 % des types.
- Le recuit est un compromis de temps : pour un schéma dense, relancer avec une autre graine ou plus de `time_limit_s`.
- Les styles de scénario sont validés, pas interprétés côté serveur.

## Vérifications
- `grep -rniE` de la consigne sur `backend/ontoforge/businessmap` et `backend/ontoforge/api/business_map.py` : vide. Le test `test_no_confidential_names_in_backend` borne les mots et parcourt tout `backend/ontoforge` ; certains mots français courants de d'anciens fichiers finissent par la même suite de lettres que l'un des noms interdits, d'où la borne de mot.
