# L15 — revue W3C du requêtage guidé et NL (itération 2, contrôle)

Agent : w3c (relecteur). J'ai rejoué les scripts de l'it1, lancé les tests `test_w3c_*` (verts), puis exécuté la requête générée avec `translateQuery(initNs={})` sur un graphe de test.

verdict: OK

## Bloquants « jeudi » : contrôle
- Préfixes : levé. `PREFIX rdf:` et `PREFIX rdfs:` sont émis, et la requête est traduite sans espace de noms implicite.
- OPTIONAL : levé. Le filtre et l'étape en aval d'une variable optionnelle sont imbriqués dans le groupe OPTIONAL, ce qui donne bien une jointure gauche.
- Validation du JSON du LLM : levé. Une IRI inventée, un langtag injecté et un datatype hors carte sont retirés et listés dans `unmatched` ; la requête produite est propre.

## Bloquants « vendredi » : contrôle
- Négation : levé. Elle produit `FILTER NOT EXISTS { ?v p ?x FILTER(...) }` sans triplet obligatoire.
- `equals` sur un langString : levé. `STR(?v) = "Clio"` trouve bien `"Clio"@fr` (1 résultat).
- Dates : levé. `dateTimeStamp` passe en `xsd:dateTime`, et un sous-typage sur des instances de Car trouve 1 résultat.
- Domaine effectif sur la chaîne de super-propriétés : levé. Le test `test_w3c_domain_on_superproperty_chain` le couvre.

## non-bloquants
- La comparaison d'un `xsd:dateTime` sans fuseau avec des données qui en ont un dépend du fuseau implicite de l'endpoint (XPath F&O §10.4). → Le mentionner dans les `notes`.
- Restent ouverts : doublons dus à `LANG(?l) = "" || LANGMATCHES`, et proposition d'une relation depuis une super-classe (« restreint à … »).
- Des PREFIX rdf et rdfs sont émis même quand seul `a` sert. C'est sans effet, uniquement cosmétique.

skill: ajouter « vérifier le SPARQL généré avec translateQuery(initNs={}) et non avec le parseur seul (rdflib prédéfinit rdf, rdfs et xsd) ».
