---
name: ontology-rapid-design
description: Concevoir rapidement une ontologie OWL 2 (ou un modèle de données) exploitable ensuite en graphe de propriétés (Curiosity, Neo4j). Couvre le périmètre, les questions de compétence, la réutilisation de vocabulaires, les patterns, le nommage, les cardinalités, les clés, les itérations, et la dérivation depuis un CSV, un schéma SQL ou un texte. À utiliser dès qu'on part d'une feuille blanche, d'une table ou d'une description métier.
---
# Conception rapide d'ontologie

## Méthode en 7 étapes (30 à 60 min pour un premier modèle)
1. Périmètre : une phrase (« suivi de maintenance d'un parc de véhicules »), 3 à 5 utilisateurs/usages, ce qui est hors périmètre.
2. Questions de compétence (CQ) : 5 à 10 questions que le modèle doit permettre de poser (« quelles pièces ont été posées sur le véhicule X ? »). Chaque classe/propriété doit servir au moins une CQ ; sinon, ne la modélisez pas (anti sur-modélisation). Les CQ deviennent ensuite des requêtes de test.
3. Inventaire : noms → classes candidates, verbes → relations, adjectifs/mesures → propriétés de données.
4. Réutilisation avant création : `skos:Concept/ConceptScheme` (vocabulaires), `schema:Person/Organization/Place`, `prov:Activity/Agent/wasGeneratedBy` (traçabilité), `dcterms:*` (métadonnées). Exprimer par `skos:exactMatch` / `closeMatch` plutôt qu'importer tout le vocabulaire.
5. Structure : hiérarchie, domaines/portées, cardinalités, clés (voir ci-dessous).
6. Validation : lister les CQ couvertes, générer les shapes (patterns, plages), passer la conformité OWL 2 DL.
7. Itérer : montrer le modèle à un expert métier, corriger, versionner (owl:versionIRI).

## Nommage
- Classes : PascalCase singulier (`RepairOrder`). Propriétés d'objet : verbe/relation camelCase (`ownedBy`, `hasEngine`, `concernsVehicle`) ; propriétés de données : nom camelCase (`mileage`, `orderNumber`).
- IRI stables, opaques si possible pour les individus ; `rdfs:label` en fr et en sur tout, `rdfs:comment` d'une phrase, `skos:definition` si définition formelle.
- Pas de préfixe type dans le nom (`hasX` pour une relation oui, `ClassVehicle` non).

## Patterns (ODP) utiles
- Rôle (Owner, Technician) : sous-classes si le rôle est permanent ; sinon classe `Role`/relation datée (pattern « n-aire »). Signaler le choix.
- Relation n-aire / avec attributs (pièce posée avec quantité) : classe d'association (`PartUsage` avec `usesPart`, `quantity`). Une jointure SQL avec colonnes en plus est presque toujours cela.
- Énumération : classe de valeurs (`FuelType` + individus) ou `skos:ConceptScheme` si extensible ; `owl:oneOf` seulement si fermée.
- Partie-tout : une propriété `hasPart` + inverse `partOf` ; transitive seulement si utile.
- Temporalité/provenance : `prov:Activity` + dates ; ne pas dupliquer des « version » de classes.

## Cardinalités et clés
- `functional` = au plus 1 valeur ; `min 1` (required) = obligatoire. En OWL (monde ouvert) ce n'est pas validé : les shapes SHACL le font.
- Clés : identifiant métier de chaque entité (`owl:hasKey`, ex. VIN) → deviennent des contraintes d'unicité côté graphe. Toujours en proposer une, sinon le dire.
- Disjonction entre sous-classes sœurs exclusives (`Car` / `Truck`) : elle protège les données et guide la transposition (labels multiples).

## Pièges OWL 2 DL
- Pas de `xsd:date`, `xsd:gYear`, `xsd:time` dans la table de datatypes OWL 2 : utiliser `xsd:dateTime`, `xsd:integer`, ou un datatype dérivé.
- Une propriété ne peut être à la fois d'objet et de données. Pas de propriété transitive ou à chaîne avec cardinalité (non simple).
- Ne pas mélanger classes et individus (punning) sans le vouloir.

## Dériver depuis une source
- CSV : une ligne d'en-tête = une classe (nom : colonne `xxx_id`, ou fichier) ; colonne `id`/`xxx_id` propre = clé ; colonne `autre_id` = relation vers une autre classe ; types inférés (entier, décimal, booléen, dateTime) ; colonne 100 % remplie = required ; un CSV ne dit rien des relations M-N ni des hiérarchies.
- SQL : table → classe (singulier) ; PK → clé ; FK → propriété d'objet (`hasX`), jamais attribut ; colonne NOT NULL → required ; UNIQUE → clé candidate ; table de jointure pure → relation N-N, avec colonnes en plus → classe d'association ; héritage « table par type » → sous-classe ; colonne `type`/`kind` → hiérarchie ou énumération (à arbitrer).
- Texte : souligner noms/verbes, en déduire CQ puis classes ; demander à l'assistant un JSON structuré et relire.
- Dans OntoForge : `POST /api/assistant/draft` (kind `text|csv|sql`) renvoie une proposition jamais appliquée sans revue humaine + avertissements ; sans LLM configuré, CSV/SQL donnent un squelette déterministe.

## Checklist avant de passer au graphe
- [ ] Chaque classe/propriété sert une CQ ; aucune classe orpheline sans raison.
- [ ] Labels fr + en ; commentaire d'une phrase.
- [ ] Domaine et portée sur toutes les propriétés ; inverse déclaré quand on navigue dans les deux sens.
- [ ] Clé sur chaque classe concrète ; cardinalités min/max réfléchies.
- [ ] Rôles, énumérations, n-aires : choix explicités.
- [ ] Datatypes OWL 2 DL ; pas de xsd:date.
- [ ] Shapes générées (patterns de VIN, plages de kilométrage...) ; ontologie sans erreur de conformité.
- [ ] Constats de transposition relus et arbitrés (héritage multiple, n-aire, restrictions complexes).

## Prompts types pour l'assistant
- « Voici la description du métier : … Propose 8 questions de compétence puis l'ontologie minimale qui y répond. »
- « Revois ce modèle : quelles classes sont inutiles ? quels rôles devraient être des relations ? quelles clés manquent ? »
- « Cette table `order_parts` est-elle une relation N-N ou une classe d'association ? Justifie. »
- « Quelles propriétés méritent un pattern ou une plage SHACL ? Ne propose que des contraintes sûres. »
- « Explique pourquoi ce constat est risqué pour Neo4j et quelle option recommander. »
