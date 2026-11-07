# L15 — revue W3C du requêtage guidé et NL (itération 1)

Agent : w3c (relecteur, aucun code modifié). Méthode : des requêtes guidées et du JSON de LLM adverses passent par `to_sparql`, puis sont parsés, puis exécutés avec rdflib.

verdict: KO

Ce qui fonctionne :
- `FILTER NOT EXISTS` pour une étape niée. C'est le bon choix : MINUS échoue sans variable partagée (SPARQL 1.1 §8.3).
- `rdf:type/rdfs:subClassOf*` quand `subclasses` est activé.
- L'intersection des domaines multiples (`applies(pi, A)` vaut False, `applies(pi, AB)` vaut True) et l'union (`any`).
- L'héritage du domaine d'une super-propriété quand la sous-propriété n'en déclare pas.
- Une propriété ou une classe inventée par le LLM est bien retirée.

## bloquants — avant la démo de jeudi
- [backend/ontoforge/queries/builder.py:255 et :297] **Préfixes non déclarés.** `rdf:type/rdfs:subClassOf*` et `rdfs:label` sont écrits en dur, sans passer par `_Terms.iri`. Ils ne sont donc jamais ajoutés à `used`, et l'en-tête ne contient ni `PREFIX rdf:` ni `PREFIX rdfs:`. rdflib l'accepte parce qu'il prédéfinit ces espaces de noms, ce qui explique que les tests et le contrôle de `endpoint.py` passent. Un endpoint conforme rejette la requête : Jena/Fuseki répond « Unresolved prefixed name » (SPARQL 1.1 §4.1.1). → Produire ces termes avec `t.iri(RDF+"type")` et `t.iri(RDFS+"subClassOf")`, ou marquer `t.used.add("rdf")` et `t.used.add("rdfs")`.
- [builder.py:264-273] **OPTIONAL cassé.** Les triplets obligatoires qui portent sur une variable liée seulement dans un OPTIONAL sont émis dans le groupe principal. C'est le cas d'un filtre sur une propriété de données de `?g`, et d'une étape requise qui part de `?g`. Résultat : `?g name ?n . FILTER(...)` puis `OPTIONAL { ?v at ?g }`. `?g` n'est plus relié à `?v`, ce qui donne un produit cartésien filtré au lieu d'une jointure gauche (sémantique de LeftJoin, SPARQL 1.1 §18.5). → Construire les groupes en arbre : tout ce qui dépend d'une variable optionnelle (étapes, triplets de filtre, filtres) va **dans** l'OPTIONAL de l'étape, et les OPTIONAL s'imbriquent.
- [builder.py:171, :188 ; nl.py:404] **La validation du JSON du LLM n'est pas étanche.** `sanitize` ne contrôle ni `value`/`values` quand `is_iri` est vrai, ni `lang`, ni `datatype` des filtres :
  - une IRI inventée (`http://invented/X`) passe ;
  - un datatype inventé passe ;
  - `t.iri` produit `<…>` sans échapper les caractères interdits (`>` `"` `{` `}` `|` `^` `` ` `` `\` espace, RFC 3987 / SPARQL `IRIREF`) ;
  - `@{lang}` est injecté brut.

  Avec `"x> . ?s ?p ?o } #"` ou `lang = "fr) } UNION {…"`, on modifie la structure de la requête : une injection reste possible en lecture, même si UPDATE est refusé. → Dans `_Terms`, refuser une IRI qui ne correspond pas à `IRIREF` et une langue qui ne correspond pas à `[a-zA-Z]+(-[a-zA-Z0-9]+)*` (lève `GuidedError`). Dans `sanitize`, n'accepter une valeur `is_iri` que si elle est connue de l'ontologie ou de `/query/values`, et un `datatype` que s'il appartient à la carte OWL 2 ou à `onto.datatypes`. Sinon, retirer le filtre et l'ajouter à `unmatched`.

## bloquants — vendredi
- [builder.py:319-321] **Négation d'un filtre de données.** `FILTER(!(CONTAINS(...)))` sur un triplet obligatoire signifie « a au moins une valeur qui ne contient pas X ». Ce n'est pas « n'a aucune valeur contenant X » : une valeur multiple ou une propriété absente fausse le résultat, en monde ouvert et sans UNA. → Pour `negate`, générer `FILTER NOT EXISTS { ?v p ?x FILTER(expr) }` et ne pas émettre le triplet obligatoire.
- [builder.py:336] **`equals` ou `in_values` sur du texte et `rdf:langString`.** `?n = "Clio"` ne trouve jamais `"Clio"@fr`, car RDFterm-equal compare des termes différents (vérifié : 0 résultat). → Pour une valeur de type texte sans `lang`, générer `STR(?n) = "Clio"`, ou le littéral avec `@lang` quand la portée est `rdf:langString` et que la langue est connue.
- [builder.py:368-376] **Typage des dates.** `_date_datatype` ignore `xsd:dateTimeStamp`, `gYearMonth` et `time`, et retombe sur `xsd:date`. Or SPARQL 1.1 §17.3 ne définit d'opérateur de comparaison que pour `xsd:dateTime` : la comparaison entre `xsd:date` et `dateTime` est une extension, non portable. Une valeur ISO complète passée à un `gYear` donne un littéral mal typé. → Envoyer `dateTimeStamp` vers `dateTime`. Quand la portée est inconnue, comparer en `xsd:dateTime`. Tronquer ou adapter la valeur à son type (`gYear` : `YYYY`).
- [builder.py:434-452] **Domaine effectif d'une sous-propriété.** `eff` s'arrête au premier domaine trouvé dans la chaîne de super-propriétés. Pourtant dom(p) ⊑ dom(q) pour tout q super-propriété de p : il faut l'intersection sur toute la chaîne (et `inverse_of` déclaré dans les deux sens). Sans cela, les suggestions sont trop permissives.

## non-bloquants
- [builder.py:296] `LANG(?l) = "" || LANGMATCHES(...)` duplique les lignes quand une ressource a un libellé sans langue et un libellé fr. → Utiliser un `COALESCE` de deux OPTIONAL (d'abord fr, sinon sans langue), ou `SAMPLE` avec `GROUP BY`.
- [builder.py:254] La branche « `a/rdfs:subClassOf*` » de l'expression ternaire est morte : simplifier.
- `applies` exige que la classe de départ soit sous-classe du domaine. Depuis une super-classe (Vehicle, pour une propriété de domaine Car), la relation n'est pas proposée alors que des instances peuvent l'avoir. → La proposer avec la mention « restreint à Car » (pratique Sparnatural).
- NL : « année courante supposée » doit rester signalée dans `explanation`. C'est déjà le cas, à conserver.

skill: ajouter à w3c-ontology-conformance la checklist SPARQL générée : « préfixes de tous les termes déclarés, y compris rdf/rdfs ; dépendances d'OPTIONAL imbriquées ; négation = NOT EXISTS ; IRIREF et langtag validés ; comparaisons de dates en xsd:dateTime ».
