# L9 — revue W3C (itération 1)

Agent : w3c (relecteur, aucun code modifié). Vérifications par script sur `editing/ops.py` et `editing/perimeter.py` (cas adverses construits en mémoire).

verdict: KO

Ce qui tient : la cardinalité nommée suivie de transitive est refusée ; l'inverse d'une propriété transitive rend la propriété non simple, et la caractéristique fonctionnelle est alors refusée ; un xsd inconnu est refusé ; un cycle de sous-classes est refusé ; une clé est renommée ; l'atomicité tient.

## bloquants — avant la démo de jeudi
- [backend/ontoforge/editing/ops.py:246] Les cardinalités et `self` ne sont contrôlées que dans `cls.restrictions`. `C ≡ ≥2 p.B` (dans `equivalent_to`), suivi de `set_characteristic p transitive`, est accepté. Cela viole OWL 2 Structural Spec §11.2. → Parcourir récursivement toutes les `ClassExpr` (`equivalent_to`, `super_expressions`, `filler_expr`, `domain_expr`, `range_expr`) avec `op in (min, max, exactly, self)`.
- [backend/ontoforge/editing/ops.py:243] La disjonction n'est testée que du côté de la propriété qui porte `disjoint_with`. `add_disjoint p q`, avec p simple et q transitive, est accepté (§11.2 : DisjointObjectProperties exige des propriétés simples). → Signaler la violation dès que p **ou** un élément de `p.disjoint_with` appartient à `ns`.
- [backend/ontoforge/editing/ops.py:132 et :344] Le vocabulaire réservé est accepté comme IRI d'entité. `add_class xsd:string`, `add_class rdf:type` et `rename_entity A → owl:Thing` passent. Cela viole §2.4 (vocabulaire réservé) et §5.8.1 (contraintes de typage). → Refuser toute IRI nouvelle ou renommée dans les espaces `rdf:`, `rdfs:`, `owl:` et `xsd:`.
- [backend/ontoforge/editing/ops.py:269 (`_scrub`), appelé par `_op_delete_entity`] La suppression retire seulement l'opérande qui porte l'IRI. Sur `delete A`, on obtient :
  - `domain_union [A,B]` → `[B]` : renforcement de A⊔B en B, axiome inventé ;
  - `C ≡ A⊓B` → `C ≡ and(B)` : implique B ⊑ C, et l'intersection n'a plus qu'un opérande, ce que §8.1.1 interdit (ObjectIntersectionOf/UnionOf demandent au moins 2 opérandes) ;
  - `not(A)` → `not()` : expression vide, invalide.

  → Faire comme Protégé : retirer **l'axiome entier** qui mentionne l'IRI supprimée (`domain_union`, `range_union`, tout élément de `equivalent_to` ou `super_expressions`, `filler_expr`, `one_of`), puis lister les axiomes retirés dans l'avertissement.
- [backend/ontoforge/editing/perimeter.py:82 et :98] Une propriété héritée est perdue en silence. Périmètre {Car, G} avec `d` de domaine V (Car ⊑ V) : `d` est exclue **sans P01**, car `touched` ne regarde que les classes du périmètre et ignore leurs ancêtres. → Inclure dans `touched` les ancêtres des classes du périmètre (`any(e in cs or cs & descendants(e) ...)`), pour que P01 dise « héritée par Car, domaine V hors périmètre ».

## bloquants — vendredi
- [backend/ontoforge/editing/perimeter.py:70-100] Une propriété dont le domaine ou la portée est un **ancêtre** d'une classe du périmètre doit rester disponible. Pour l'instant `s` (V→G) est exclue alors que Car l'hérite. → Projeter le domaine ou la portée sur les classes maximales du périmètre qui en descendent (V → Car), avec un constat P01 « domaine restreint ». Même logique pour `domain_union` (garder les membres du périmètre seulement si c'est explicitement signalé, sinon exclure comme aujourd'hui).
- [backend/ontoforge/editing/ops.py:536] Un littéral `hasValue` peut être mal typé (`"abc"^^xsd:integer`). L'ontologie devient alors incohérente (OWL 2 Direct Semantics §2.3, littéral hors espace lexical). → Contrôler la forme lexicale des types de la carte (entiers, décimaux, booléen, dateTime) ; refuser aussi `lang` combiné à un `datatype` autre que `rdf:langString`.
- [backend/ontoforge/editing/ops.py:250] Une disjonction entre classes **équivalentes** (A ≡ B nommée) n'est pas détectée : la classe devient insatisfiable. → Inclure les équivalences nommées dans `ancestors` pour ce contrôle.

## non-bloquants
- [ops.py:160] xsd:date, time et gYear sont acceptés avec avertissement, ce qui sort d'OWL 2 DL (§4 : hors carte des datatypes). C'est acceptable par contrat, mais l'avertissement doit aussi apparaître dans le profil ou l'analyse, pas seulement dans la réponse de `/ops`.
- [ops.py:310 `_replace`] Le renommage réécrit aussi les littéraux dont la valeur est égale à l'ancienne IRI (annotations `is_iri=false`, faits). → Limiter le remplacement aux champs IRI.
- Le cycle de sous-classes est refusé alors qu'OWL l'autorise (il implique une équivalence). Le refus reste un garde-fou acceptable : le message devrait proposer `equivalentClass`.
- [history.py `_swap`] Annuler après un PUT /onto ou un import restaure un état ancien sans prévenir, et les shapes ou périmètres non journalisés dans l'entrée peuvent alors pointer des entités absentes. → Garder une empreinte de l'état « après » dans l'entrée et renvoyer 409 si l'état courant en diffère.
- [perimeter.py] Il reste des shapes dont `sh:path` ou `sh:class` vise une propriété ou une classe exclue (seules les cibles sont filtrées). → Les retirer ou les signaler (P03).

skill: ajouter à w3c-ontology-conformance la checklist « §11.2 sur toutes les ClassExpr, y compris imbriquées » et la règle « suppression = retrait de l'axiome entier, jamais d'un opérande (n-aires ≥ 2) ».
