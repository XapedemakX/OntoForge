# Revue W3C — L1 io (itération 1)

Relecteur : w3c — 3 nov. 2026. Fichiers relus : `backend/ontoforge/io/{rdf_import,rdf_export,dsl}.py`, `samples/automaint/*`.
Vérifications (scratchpad) : 189 tests verts ; aller-retour import → export comparé par isomorphisme de graphes (`rdflib.compare`) sur automaint.ttl, automaint.owl, trap.ttl, trap-nondl.ttl et 15 mini-ontologies (ill-typed, @fr-CA, owl:Axiom, `[owl:inverseOf p]` dans une restriction, QCR data, union en domaine, NegativePropertyAssertion data, hasKey, chaîne, facettes, disjointUnion, hasSelf, individus anonymes…).

```
verdict: OK
bloquants:
  (aucun)
non-bloquants:
  - [samples/automaint/automaint.ttl] Ontologie de démo passée dans conformance.profiles.check_conformance (graphe + OWL RL) : OWL 2 DL = vrai, cohérente, 0 classe insatisfiable, datatypes tous dans la carte OWL 2 (dateTime, decimal, integer, nonNegativeInteger, string + am:ModelYear défini par facettes). EL/QL/RL = faux, à cause des cardinalités, de ObjectOneOf (FuelType) et de InverseObjectProperties (concerns, readingOf) : c'est attendu. automaint.ttl et automaint.owl font tous deux un aller-retour isomorphe (578 triplets).
  - [samples/automaint/automaint.ttl] am:hasMileageReading n'a de rdfs:label ni en fr ni en en (W07). Ajouter "has mileage reading"@en, "a pour relevé kilométrique"@fr.
  - [io/rdf_import.py:811-844] owl:AllDisjointClasses devient des owl:disjointWith deux à deux (trap.ttl : 1 axiome C07 donne 15 triplets). Le sens est le même (SS §9.1.3), mais l'axiome n-aire est perdu à l'export et la règle C07 ne peut plus le reconnaître sur un graphe ré-exporté. Il faudrait garder la forme n-aire (comme pour AllDifferent, qui ressort bien en owl:members).
  - [io/rdf_import.py:836-837] owl:distinctMembers est accepté en lecture et owl:members est écrit à l'export : c'est conforme à MAP Table 2, rien à changer.
  - [io/rdf_import.py:183-206] Le littéral "abc"^^xsd:integer est importé sans aucun avertissement (rdflib le signale seulement dans les logs). Un warning d'import `ill_typed_literal` serait utile (Literal.ill_typed). Le contrôle bloquant est demandé au lot L2.
  - [io/dsl.py:66-73] `A.born : date` donne en silence le datatype local <base#date>, non déclaré : l'ontologie sort d'OWL 2 DL (W02 au contrôle). Il faudrait que le DSL avertisse (« date : datatype inconnu ; xsd:date est hors de la carte OWL 2, utiliser dateTime ») ou qu'il déclare l'IRI en rdfs:Datatype.
skill: w3c-ontology-conformance — ajouter au § pièges : « AllDisjointClasses / AllDisjointProperties : garder la forme n-aire à l'aller-retour (MAP Table 2) ; owl:distinctMembers en lecture seulement ».
```
