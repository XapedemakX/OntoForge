# Revue W3C — L2 shacl + conformance (itération 2)

Relecteur : w3c — 3 nov. 2026. J'ai rejoué les scripts c2.py, c4.py, c1.py et c5.py de l'it1 sur le code actuel. La suite complète passe (412 tests).

```
verdict: OK
bloquants:
  (aucun)
non-bloquants:
  - Les 7 bloquants conformance sont levés, chacun vérifié sur son cas d'origine :
    - DatatypeDefinition est admise dans les 3 profils ; ModelYear reste hors profil pour « DatatypeRestriction ».
    - Data ranges conformes à PROF : Intersection permise partout, Union refusée partout, OneOf seulement en EL.
    - FunctionalDataProperty : EL oui, QL non.
    - Assertions négatives : QL non, EL oui.
    - DataSomeValuesFrom en sous-classe QL : rdfs:Literal exigé.
    - owl:Thing refusé en RL.
    - "abc"^^xsd:integer donne W01 error.
  - Les 2 bloquants shacl sont levés : le pattern est ancré en ^(?:…)$ et "ABCDE" est désormais rejeté. Les portées integer et decimal deviennent un sh:or des sous-types XSD, et xsd:int / xsd:integer sont acceptés (vérifié sous pySHACL). Les notes [RENFORCÉ] et [PARTIEL] sont présentes.
  - [shacl/owl_to_shacl.py set_datatype] Le sh:or généré pour xsd:string accepte les sous-types (normalizedString, token…) mais pas rdf:langString. C'est conforme : xsd:string et rdf:langString sont des espaces disjoints. À garder ainsi.
skill: rien (les deux skills ont été mis à jour par les pilotes).
```
