# L36 Carte métier : revue expert W3C (cohérence sémantique) et confidentialité

verdict: KO (les écarts de sémantique sont des affirmations fausses ou trop fortes de la carte ; la confidentialité est OK sauf la réserve sur les rôles)

## A. Sémantique : ce que la carte affirme à tort

bloquants:
  1. [frontend/src/i18n/fr.json et en.json : `bm.style.both` ; frontend/src/screens/bmap/types.ts:86 ; backend/ontoforge/businessmap/graph.py:133-137] La légende et la doc disent « inverse stockée aussi (nom propre) » pour tout style `both`. Or `both` est posé (a) pour une propriété symétrique (`sym`, graph.py:133,136), qui n'a pas d'inverse nommé, et (b) pour une propriété dont `owl:inverseOf` désigne une propriété non déclarée dans l'ontologie (graph.py:136-137 : `piri in inv_of and not q`). Dans une ontologie il n'est pas question de « stockage » : `owl:inverseOf` (OWL 2 Structural Spec §9.2.1 ; Mapping to RDF) est une équivalence d'axiomes, pas une double écriture. Correction : libellé « a une propriété inverse » pour l'ontologie, « inverse stockée aussi » seulement pour la source `target` ; pour une symétrique, un libellé distinct (« symétrique »). Reproduction : projet avec `ex:marriedTo a owl:SymmetricProperty` ; la carte dessine « inverse stockée aussi (nom propre) » alors qu'aucun nom propre n'existe.
  2. [frontend/src/i18n/*.json `bm.style.oneway` « sens unique : pas de relation inverse »] Sous l'hypothèse du monde ouvert, l'absence de `owl:inverseOf` ne prouve pas l'absence d'inverse. Le style est manuel (jamais auto, types.ts:81-87), mais le libellé affirme un fait sémantique. Reformuler : « sens unique choisi pour ce scénario (pas d'inverse déclaré) ». 
  3. [backend/ontoforge/businessmap/counts.py:100-103,141] Les volumes comptent les individus typés directement (`?s a ?c`) dans le triplestore, ou les individus déclarés de l'ontologie, sans fermeture par `rdfs:subClassOf` : une classe mère (ex. Véhicule) affiche 0 alors que ses sous-classes ont des individus, ce que la carte présente comme « volume d'instances sous chaque type » (fr.json `bm.subtitle`). Sous RDFS (rdfs9), les instances d'une sous-classe sont aussi instances de la mère. Pour une cible fusionnée, `sum(...)` (counts.py:141) peut compter deux fois un même individu typé par deux classes sources. Reproduction : charger un individu `ex:v1 a ex:VehiculeElectrique` (sous-classe de Véhicule) : Véhicule = 0. Correction : `COUNT(DISTINCT ?s)` sur `?s a/rdfs:subClassOf* ?c`, ou afficher « directs » dans le libellé ; pour la cible, compter les individus distincts de l'union des sources. Ajouter la mention « 0 = aucun individu connu (monde ouvert) ».
  4. [backend/ontoforge/businessmap/graph.py:87] `abstract=bool(c.disjoint_union_of)` : un `owl:disjointUnionOf` n'exprime pas qu'une classe est abstraite (OWL 2 §9.1.4 : la classe est l'union disjointe de ses membres ; elle peut avoir des individus directs si les membres ne la couvrent pas, l'axiome impose au contraire la couverture). Le champ `abstract` est exposé dans compose (service.py:206). S'il est affiché, il affirme une propriété que l'ontologie n'a pas. Renommer `covered_by_subclasses` ou ne pas l'exposer. (Côté front il n'est pas affiché aujourd'hui : écart latent.)

non-bloquants:
  5. [graph.py:70-71,99] Domaine/image : `_ends` prend l'union des `rdfs:domain` multiples (qui sont une conjonction, RDFS §3.2) et des `unionOf`, puis dessine le produit cartésien domaines × images. Pour `domain_union={A,B}` et `range_union={X,Y}`, la carte dessine A→Y et B→X, non entailés. Les arêtes issues d'une union devraient être marquées « une parmi » ou signalées dans `warnings`.
  6. [graph.py:113-117 ; service.py compose `warnings`] Les propriétés objet sans domaine ou image (`g.skipped`) sont silencieusement absentes de la carte. Remonter `skipped` dans `warnings` (« N propriétés non dessinées : domaine ou image manquant ») ; sinon la carte semble complète.
  7. [graph.py:133 vs 118] Une relation symétrique ou à inverse externe est fusionnée en `both` mais n'affiche que le premier nom ; le nom de l'inverse n'apparaît que dans l'inspecteur (Panels.tsx:31), pas sur la carte.
  8. Sous-classes : OK. Arête `subClassOf` enfant → parent (graph.py:90), flèche vers le parent, légende « est un type de » : correct. Pour la cible Curiosity l'héritage est aplati (limite déjà documentée dans le rapport backend). Inverses fusionnées (graph.py:118-131) : l'union des paires de la 2e propriété retournées est une conséquence valide de `owl:inverseOf`. Cadres (frames.py:68-81) : une flèche de cadre n'existe que si tous les membres ont la même relation vers la même cible : fidèle.
  9. Rôles (roles.py) : déduits par heuristique (structure et noms), `role_source: auto|manual` est exposé (service.py:204) ; bien, mais l'écran doit montrer « déduit » dans l'inspecteur pour que « classificateur » ne soit pas lu comme un fait de l'ontologie. `n.enumerated` (`owl:oneOf`) pour `classifier` est correct.

## B. Confidentialité

verdict confidentialité: OK pour le contenu, réserve sur les rôles.
- Recherche insensible à la casse, sur tout le dépôt (hors node_modules, .git, dist), des noms du workspace de référence (liste tenue hors dépôt) : seul résultat `Albi` (ville) dans un test de réglages, sans rapport.
- `pytest tests/test_business_map.py` : 19 réussis, y compris `test_no_confidential_names_in_backend` et `..._strict_in_businessmap`.
- Réserve [backend/ontoforge/businessmap/model.py:11 ; roles.py:31-45] : `BUILTIN_ROLES = (issue, detail, key, classifier, context, catalogue, knowledge, config)` reprend, dans le même ordre, les catégories de la légende du zip (réf. : issue, detail, facet, bridge, knowledge, catalogue, context, config ; `facet` et `bridge` renommés `classifier` et `key`, six noms sur huit identiques) avec les mêmes teintes de rôle (ROLE_COLORS). Ce sont des mots génériques, donc pas bloquant juridiquement, mais la ressemblance est trop fidèle pour un dépôt qui s'interdit les données d'entreprise. Aussi, des motifs trop métier : `recall|rappel|warranty|garantie|bulletin` (roles.py:26) et `reading|operation|line|detail` dans HAS_PART (graph.py:16) trahissent un domaine (maintenance) ; ils sont déjà visibles dans l'exemple automaint (`hasMileageReading`).
- Proposition de jeu générique (migration : alias lecture, rôles posés par l'humain à convertir) :
  | actuel | proposé (fr / en) | sens |
  |---|---|---|
  | issue | principal / main | enregistrement central autour duquel le reste s'organise |
  | detail | composant / component | partie d'un enregistrement principal |
  | key | pivot / hub | type référencé par beaucoup d'autres |
  | classifier | liste de valeurs / lookup | petit référentiel, énumération |
  | context | contexte / context | environnement, acteurs, lieux |
  | catalogue | référentiel / reference | données de référence plus larges |
  | knowledge | document / document | contenu documentaire |
  | config | paramétrage / settings | configuration, règles |
  Changer aussi les teintes (palette indépendante de la légende d'origine) et retirer de KNOWLEDGE/HAS_PART les mots propres au domaine (garder document|guide|report|notice et part|component|detail).

## C. Zones vides : bug backend, à corriger

C'est un bug côté backend (pas seulement front). PUT puis GET ne conserve pas une zone vide : `prepare` n'alloue de rectangle qu'aux zones non vides (service.py:155 `if z.members`), `compose` écarte toute zone sans rectangle (service.py:208-209 `if z.id in c.rects`). L'état persisté garde la zone (normalize ne retire que « Autres » vide, service.py:88 ; PUT enregistre `st.zones = zs`, ligne 287), donc GET ne la renvoie pas, et le PUT suivant du front, qui renvoie seulement les zones qu'il a reçues, la supprime vraiment. Le contournement du front (useBMap.ts:39-41) ne vaut que jusqu'au prochain rechargement.
Vérifié par script (hors dépôt, fichier temporaire) : PUT avec 5 zones dont une vide : réponse à 4 zones ; état stocké à 5 ; PUT suivant à 4 : 4 stockées ; avec la correction ci-dessous simulée par monkeypatch : la zone vide revient avec un rectangle (x=890, y=1410, w=310, h=330).
Correction minimale : dans `backend/ontoforge/businessmap/service.py:155`, remplacer
  `sizes = {z.id: len(z.members) for z in state.zones if z.members}`
par
  `sizes = {z.id: len(z.members) for z in state.zones}`
(`zone_size(0)` donne déjà une case : layout.py:67-70 ; les ancres et le recuit ignorent les zones sans membre.) Ajouter un test : PUT d'une zone `members: []`, GET, la zone est présente avec `rect.w > 0`, et un second PUT (calqué sur la réponse) la conserve. Ensuite retirer le contournement useBMap.ts:39-41 et la phrase de utilisateur.md:212.

## Contre-relecture (15 nov. 2026)

verdict: OK

Relancé : `pytest -q` 1018 réussis (dont `tests/test_business_map.py`, 19 tests d'origine plus ceux de L36c) ; recette 32/32.

A. Sémantique, point par point dans le code :
- 1 (`both` / « stockée aussi ») : corrigé. `edge.link` vaut `inverse` ou `symmetric` (`graph.py:44,142,152,195-207`) ; styles `bm.style.both` « relation déclarée dans les deux sens (propriété inverse) » et `bm.style.symmetric` distinct ; test `test_union_edges_flagged_and_link_kinds`.
- 2 (`oneway`) : corrigé. `bm.style.oneway` = « un seul sens retenu pour ce scénario », style resté manuel ; la doc dit que l'absence d'inverse déclarée ne prouve rien (monde ouvert).
- 3 (volumes) : corrigé. `counts.py` : `closure_of` (fermeture `rdfs:subClassOf`), `COUNT(DISTINCT)` avec `VALUES`, cible sans double compte ; tests `test_counts_closed_under_subclass_ontology`, `..._and_distinct_with_store`, `..._target_no_double_count`. « 0 = aucun individu connu » figure dans le guide et `limites`.
- 4 (`abstract`) : corrigé. `graph.py:91` pose `abstract=False` ; `test_disjoint_union_is_not_abstract`.
- 5 (unions) : traité par signalement (`union: true`, `meta.n_union`, bandeau `bm-unions`, mention dans l'inspecteur). Les arêtes restent, marquées « possibilité » : acceptable.
- 6 (propriétés non dessinées) : corrigé. `meta.skipped`, bandeau `bm-skipped` avec liste ; `test_skipped_properties_reported`.
- 9 (rôle déduit ou choisi) : corrigé (`Panels.tsx:63`, `bm.insp.derived` / `bm.insp.chosen`).
- 7 (nom de l'inverse sur la carte) : non traité, voir `reste-a-faire.md`.

B. Confidentialité / rôles : `BUILTIN_ROLES` = main, component, hub, lookup, context, reference, document, settings, avec libellés fr/en, teintes nouvelles et migration `LEGACY_ROLES` / `canonical_role`. Les motifs métier (`recall`, `garantie`, `reading|operation|line`) sont retirés de `roles.py` et `graph.py` ; `test_no_domain_specific_words_in_role_heuristics` et les deux tests de noms confidentiels sont verts. Un grep des noms interdits sur les fichiers texte du dépôt ne trouve que la ligne de commande citée dans ce fichier de revue lui-même (sans nom réel de projet).

C. Zones vides : corrigé (voir contre-relecture scout, même correctif).

Réserve résiduelle, non bloquante pour cette revue : `docs/CONTRACTS.md` §13 décrit encore les anciens rôles (voir contre-relecture de `revue-doc.md`).
