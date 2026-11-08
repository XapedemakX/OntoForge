verdict: OK
bloquants:
  - aucun restant. Trois écarts OWL avérés ont été corrigés pendant la relecture (voir « Corrigé par le relecteur ») ; le pilote les relit dans fix-it1.
non-bloquants:
  - [backend/ontoforge/editing/graph.py, propriétés objet] plusieurs `rdfs:domain` (ou `rdfs:range`) se lisent comme une intersection (RDF Schema 1.1 §3.2.2, OWL 2 SS §9.2.5) ; le graphe tire une arête par classe, ce qui se lit comme une union. `domain_union` (ex. am:hasOwner → Company ∪ Person) devrait donner un nœud anonyme ∪ en VOWL, comme les équivalences. Comportement antérieur à L26, pas une régression ; à reprendre si l'on veut une VOWL stricte.
  - [graph.py, propriétés de données] une propriété de données sans domaine (am:emissionStandard, am:mileageKm dans samples/trap) reste dans `skipped` ; VOWL la rattache à owl:Thing. Même traitement possible que pour les propriétés objet (`include=thing`).
  - [graph.py] une propriété objet libre des deux côtés (am:interchangeableWith, am:relatedTo) reste dans `skipped`. Choix acceptable : la dessiner Thing → Thing n'apprend rien au lecteur ; le guide le dit désormais.
  - [view.ts, inverses] seule la première arête de chaque propriété est appariée ; avec plusieurs domaines, les autres arêtes de l'inverse restent dessinées à part. Correct (rien n'est perdu), un peu redondant.
  - [Legend / vowl.tsx] le complément ¬ n'a pas le petit cercle intérieur de WebVOWL (OwlComplementOf.js) et les sous-propriétés, cardinalités et individus ne sont pas dessinés : écarts déclarés dans rapport.md, acceptés.
  - [classe abstraite] l'anneau pointillé intérieur ressemble au double cercle des équivalentes à faible zoom. Ajout OntoForge sans équivalent VOWL, accepté ; envisager l'italique seul en compact.
skill: ajouté à skills/w3c-ontology-conformance/SKILL.md §8 : (1) owl:Thing ne se dessine que si l'ontologie dit owl:Thing ou rien, jamais parce qu'une classe sort de la vue ; (2) fusion d'inverses seulement si les extrémités se répondent, et une inverse sans domaine ni image reçoit ceux de l'autre ; (3) « externe » se calcule sur l'espace de noms avec repli sur l'espace majoritaire.

## Sources

- `vowl.css` de WebVOWL, lu sur https://raw.githubusercontent.com/VisualDataWeb/WebVOWL/master/src/webvowl/css/vowl.css (le chemin `src/app/css/vowl.css` donné dans la demande renvoie 404 ; le fichier est sous `src/webvowl/css/`).
- Implémentations WebVOWL, même dépôt, `src/webvowl/js/elements/` : `OwlThing.js`, `ExternalClass.js`, `OwlDeprecatedClass.js`, `OwlEquivalentClass.js`, `OwlUnionOf.js`, `OwlComplementOf.js`, `RdfsLiteral.js`, `RdfsDatatype.js`, `OwlDisjointWith.js`, `RdfsSubClassOf.js`, `OwlObjectProperty.js`, `OwlDatatypeProperty.js`, `modules/colorExternalsSwitch.js`.
- OWL 2 Structural Specification (SS) §9.2.5 à §9.2.7 (domaine, image, inverses), RDF Schema 1.1 §3.2.

## Couleurs « À VÉRIFIER » : confirmées

| Rôle | rapport.md | WebVOWL | OntoForge clair (editor.css) |
|---|---|---|---|
| Classe | #acf | `.class { fill: #acf }` | #aaccff |
| Externe | #36c | commenté dans vowl.css, appliqué par `colorExternalsSwitch.js` (`d3.rgb("#36C")`), texte blanc (`.external + text { fill: #fff }`) | #3366cc, texte #ffffff |
| Dépréciée | #ccc | `.deprecated { fill: #ccc }` | #cccccc |
| Type de données / Literal | #fc3 | `.literal, .node .datatype { fill: #fc3 }` | #ffcc33 |
| Propriété de données | #9c6 | `.datatypeproperty { fill: #9c6 }` | #99cc66 |
| Pictogrammes (disjonction, ensembles) | #69c | `.symbol { fill: #69c }` | #6699cc |
| owl:Thing | blanc | `["white", "dashed"]` (OwlThing.js) | #ffffff, bord en tirets |
| Survol / focus | — | rouge `#f00` | teal (écart accepté, voir plus bas) |

La mention « À VÉRIFIER » de rapport.md peut être levée.

## Formes : vérifiées contre WebVOWL

| Élément | WebVOWL | OntoForge | Verdict |
|---|---|---|---|
| owl:Thing | cercle r=30, blanc, tirets | petit cercle blanc en tirets, dupliqué | conforme |
| Classe externe | cercle #36c, texte blanc | idem, « [externe] » | conforme |
| Dépréciée | gris, indication « deprecated » | gris, « [déprécié] », le gris l'emporte | conforme |
| Équivalentes | double cercle (extérieur blanc, écart 4 px), une classe représentante | double cercle, autres noms entre crochets | conforme |
| Union / intersection / complément | nœud ensembliste (cercle) avec pictogramme #69c | cercle en tirets, symbole ∪ ∩ ¬ | acceptable (pictogramme simplifié, déclaré) |
| rdfs:Literal | rectangle #fc3 en tirets | idem | conforme |
| Datatype | rectangle #fc3 plein, un par propriété | idem | conforme |
| Caractéristiques | indications entre crochets sous le libellé | entre crochets, dans la langue de l'interface | conforme (traduction acceptée) |
| subClassOf | trait pointillé (`dotted`), pointe blanche, « Subclass of » | pointillé, pointe blanche, « Sous-classe de » | conforme |
| disjointWith | tirets, sans pointe, rectangle à deux disques #69c, « disjoint » | idem | conforme |
| Inverses | un lien, deux libellés, deux pointes | un lien, « a ⇄ b », deux pointes | acceptable (déclaré) |

Écarts de rapport.md : tous acceptés. La sélection en teal est justifiée (le rouge sert aux erreurs ; WebVOWL utilise le rouge pour le survol, pas pour une notion OWL). La classe abstraite n'est pas une notion OWL 2 (annotation `urn:ontoforge:abstract` ou DisjointUnion, SS §9.1.4) : son dessin ne contredit pas VOWL.

## Exactitude OWL des encodages (samples/trap/trap.ttl, include=external,anonymous,thing,datatypes)

| Point | Résultat |
|---|---|
| Caractéristiques | lues correctement : am:isComponentOf `transitive`, am:supersedes `asymmetric` + `irreflexive`, am:hasRepairOrder `inverseFunctional`, am:ofModel / am:madeBy `functional` ; propriétés de données : `functional` (am:vin, am:claimDate…) |
| Dépréciée | am:ServiceBooklet (`owl:deprecated true`) seule marquée |
| Classes anonymes | 5 trouvées (4 équivalences ∩/∪, 1 superclasse ∪) |
| Externes | aucune à tort (toutes les classes sont dans `https://w3id.org/ontoforge/automaint#`) |
| Inverses | **écart** : am:hasPart `owl:inverseOf` am:partOf, partOf sans domaine ni image → partOf passait dans `skipped` et disparaissait du graphe |
| owl:Thing | **écart** : voir ci-dessous |

## Corrigé par le relecteur

1. **owl:Thing inventé** (`graph.py`, calcul de `thing_d` / `thing_r`). Le test portait sur les extrémités *présentes dans la vue* : une propriété dont le domaine est une classe déclarée mais hors périmètre, ou une classe externe sans `include=external`, recevait un nœud Thing. Cela affiche `ObjectPropertyDomain(P, owl:Thing)`, un axiome faux (SS §9.2.5). Correction : Thing seulement si l'ontologie ne donne aucun domaine (image) autre qu'owl:Thing ; sinon l'arête n'est pas dessinée et la propriété va dans `skipped`.
2. **Inverses** (`view.ts`). La fusion masquait l'arête de l'inverse b sans vérifier qu'elle allait de l'image de a vers son domaine : une inverse déclarée avec ses propres domaine et image (ex. a : Person → Car, b : Vehicle → Agent) perdait les siens. Correction : fusion seulement si `a.source = b.target` et `a.target = b.source`. Inversement, une inverse sans domaine ni image (am:partOf) est maintenant portée par l'arête de l'autre : `InverseObjectProperties(P, Q)` et `ObjectPropertyDomain(P, C)` impliquent `ObjectPropertyRange(Q, C)` (OWL 2 Direct Semantics §2.3.2, axiomes de propriétés objet). Nouveau champ additif `inverse_label` sur les arêtes `objectProperty`, Q sort de `skipped`. Classique et VOWL l'affichent en « a ⇄ b ».
3. **Espace de noms** (`_namespaces`). Une ontologie dont l'IRI diffère du vocabulaire (IRI versionnée, `…/ontology` contre `…/vocab#`, cas courant) rendait toutes les classes « externes ». Repli : si aucune classe déclarée n'est dans l'espace de l'IRI d'ontologie, on prend l'espace majoritaire des classes déclarées. Une classe référencée non déclarée mais dans l'espace de l'ontologie n'est plus marquée externe.

Test ajouté : `backend/tests/test_editing_ops.py::test_graph_l26_w3c_it1_thing_inverse_namespace` (Thing non inventé, `inverse_label` sur am:hasPart, caractéristiques du trap, repli d'espace de noms).

## Rétrocompatibilité de /graph

Oui. Sans `include`, mêmes nœuds et arêtes qu'avant ; les champs ajoutés (`external`, `equivalent`, `characteristics`, `deprecated`, `functional`, `inverse_label`) sont additifs. Testé par `test_graph_l26_additive_flags_and_includes` (le nouveau test couvre le reste). Changements observables hors `include`, tous deux plus justes : une inverse sans domaine ni image sort de `skipped`, et `external` suit le repli d'espace de noms. CONTRACTS §5 mis à jour.
