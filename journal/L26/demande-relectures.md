# L26 : relectures à lancer

## w3c (fidélité VOWL et OWL des encodages)
- Valider ou refuser chaque écart de `rapport.md` § « Écarts assumés ». Un écart à OWL 2 est bloquant ; un écart à VOWL non justifié aussi.
- `backend/ontoforge/editing/graph.py` : `external` (préfixe `meta.iri` + `#` ou `/`), `equivalent`, nœuds `anonymous` (`and` → ∩, `or` → ∪, `not` → ¬), nœuds `thing` pour un domaine ou une image absent (lecture OWA : absent = `owl:Thing`, RDFS §2.3 / OWL 2 Structural §9.5). Une propriété libre des deux côtés reste dans `skipped` : est-ce le bon choix ?
- `view.ts` : fusion des équivalentes (classes nommées seulement ; la classe déclarée est le représentant). Une classe externe équivalente à une classe déclarée est-elle correctement « absorbée » ?
- Datatypes : un nœud par propriété (règle VOWL « split by property »), `rdfs:Literal` en pointillé.
- Caractéristiques : `functional` d'une propriété de données affiché entre crochets ; transitive / symétrique etc. des propriétés objet.
- Confronter les couleurs hexadécimales à `vowl.css` de WebVOWL (copie tierce lue seulement).

## scout (UX)
- Légende : lisibilité des mini-dessins (88 × 38 px), choix de ne lister que les éléments présents, états toujours affichés, fermée par défaut.
- Graphe de 25 classes : vue d'ensemble à 42 % de zoom peu lisible en VOWL ; faut-il un ajustement automatique plus agressif, un repli par défaut ?
- Types de données masqués d'emblée au-delà de 16 classes : bonne règle ?
- Barre de l'éditeur plus chargée (mode, Afficher, compteur) : deux lignes à 1440 px.
- Export : légende incluse par défaut, absence de pictogrammes dans les nœuds.

## doc, puis humain
- Guide : section « Lire le graphe : légende et notation VOWL » et deux tableaux ; CONTRACTS §5 ; CHANGELOG 0.3.0.
