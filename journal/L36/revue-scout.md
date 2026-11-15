# L36 Carte métier : revue scout (éclaireur produit)

verdict: KO (un bloquant fonctionnel, le reste est non bloquant)

Vérifié : `pytest -q` 1009 réussis ; `npm run build` OK ; recette `l36_business_map.mjs` 27/27 (voir note de flakiness en 7) ; captures 01, 07, 09 relues.

bloquants:
  1. [backend/ontoforge/businessmap/service.py:155 ; frontend/src/screens/bmap/useBMap.ts:39-41] Une zone vide disparaît au rechargement et le PUT suivant l'efface du serveur.
     Reproduction : écran Zones, « Ajouter une zone », la zone s'affiche (gardée localement) ; recharger la page (F5) : la zone n'est plus là ; déplacer un seul nœud : le PUT envoie `zones` sans elle, le serveur la supprime définitivement. Reproduit côté API (PUT avec une zone `members: []`, puis GET : absente ; le PUT suivant sans elle la retire de l'état stocké). L'utilisateur qui prépare ses zones avant de les remplir perd son travail sans message. Voir revue-w3c.md et la correction minimale ci-dessous.

non-bloquants (priorité décroissante):
  2. [journal/L36/screens/09-mobile.png ; frontend/src/screens/bmap/BusinessMap.tsx] Sur mobile la carte s'ajuste à 14 % : types, libellés et légende sont illisibles, et le pincement n'existe pas (rapport front, « non couvert »). Le bandeau « consultation » apparaît deux fois (haut de page et dans l'inspecteur). Proposition : ouvrir à un zoom lisible centré sur la première zone, liste des zones cliquable pour zoomer, un seul bandeau.
  3. [journal/L36/screens/01-carte-claire.png] À l'ajustement (39 %) les libellés d'arête et les sous-titres de zone sont à peine lisibles ; un facteur de taille minimale des polices (en pixels écran) ou un zoom initial par zone aiderait. Les arêtes `subClassOf` portent le texte brut « subClassOf » (non traduit) sur chaque lien : à remplacer par un libellé court localisé ou à masquer (la légende dit déjà « est un type de »).
  4. [frontend/src/screens/bmap/render.ts:50] Le libellé d'une flèche de cadre est `relation · Partagent : r1 → T1, r2 → T2…` : la liste complète des relations partagées est répétée sur chaque flèche du cadre, ce qui est long et redondant. Mettre la note du cadre une seule fois (titre ou inspecteur).
  5. [frontend/src/screens/bmap/Panels.tsx:31 ; i18n bm.insp.noScenario] Pour styler une relation il faut d'abord créer un scénario ; l'inspecteur le dit mais ne propose pas de bouton « Créer un scénario ». Ajouter l'action directe.
  6. [frontend/src/screens/bmap/types.ts:86] Réorganiser applique directement (annulable) alors que zones et cadres passent par un aperçu : incohérent mais défendable ; au minimum signaler dans l'infobulle que les positions non épinglées seront recalculées.
  7. [tools/recette/l36_business_map.mjs:136] Flakiness : au premier lancement, la recette s'arrête à l'étape 8 (`waitForSelector [data-testid=mo-bmap]`, 15 s dépassées : l'écran Modèle attend `api.analyze`). Le second lancement donne 27/27. Relever le délai à 30 s ou attendre la fin de l'analyse.
  8. [journal/L36/screens/01-carte-claire.png] Tous les volumes affichent « 0 » sur l'exemple automaint : lecture ambiguë (« aucun individu connu » ou « vide » ?). Afficher « — » ou masquer quand la provenance est `ontology` sans individus.
  9. Sombre : le rendu est correct (zones teintées assombries, rôles distincts, texte lisible, bordure pointillée visible). Rien à corriger, hormis le contraste faible des libellés d'arête fins (points 3).

Note : lots/L36.md n'existe pas (le dossier lots/ s'arrête à L25) : pas de critères d'acceptation vérifiables pour ce lot ; à régulariser par le chef.
skill: product-discovery : ajouter « un élément créé mais vide doit survivre à un rechargement » à la checklist des écrans d'édition.

## Contre-relecture (15 nov. 2026)

verdict: OK

Relancé : `pytest -q` 1018 réussis ; `npm run build` OK ; recette `l36_business_map.mjs` (ports 8991/4991) 32/32.

- Bloquant 1 (zone vide perdue) : corrigé dans le code. `service.py:157` calcule les tailles sur toutes les zones (`{z.id: len(z.members) for z in state.zones}`, plus de filtre `if z.members`) ; le contournement local de `useBMap.ts` a disparu (le PUT adopte la carte renvoyée par le serveur) ; test `test_empty_zone_survives_put_get` (PUT, GET, second PUT calqué sur la réponse) et recette 5c2 / 5c3 (rechargement de page) verts.
- Non-bloquants traités et vérifiés : 2 (mobile : ouverture à 45 % minimum, « Tout voir », recette 11b/11c), 3 en partie (« subClassOf » remplacé par « est un », `bm.edge.subclass`), 7 (recette stable : analyse du modèle cible attendue côté API, délai 120 s ; 32/32 au premier lancement ici).
- Non-bloquants non traités (4, 5, 6, 8, doublon du bandeau « consultation » en 2, lisibilité des petits libellés à l'ajustement en 3) : reportés dans `journal/L36/reste-a-faire.md`, pas en KO.
