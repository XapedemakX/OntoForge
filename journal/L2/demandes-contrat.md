# Demandes de modification de contrat (L2)

## shacl -> lead : docs/CONTRACTS.md, signature de `shacl/validate.py`
Le défaut `inference: str = "rdfs"` doit devenir `inference: str = "none"` (revue W3C §4 : valider sans inférence ;
l'inférence RDFS fait échouer `sh:closed` sur les super-propriétés déduites, piège D11). Le code (`validate.py`) applique déjà `"none"` ;
CONTRACTS.md ligne `shacl/validate.py` à aligner. Précisions : `ShaclReport` ajoute `inference`, `warnings`, `text` et `counts()` ;
`data` accepte aussi un `rdflib.Graph`, `onto` accepte aussi un `rdflib.Graph`, inférence `"both"` acceptée.
