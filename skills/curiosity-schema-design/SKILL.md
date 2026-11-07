---
name: curiosity-schema-design
description: Modéliser un schéma de données pour la plateforme Curiosity (graphe de connaissances, Curiosity.Library en C#) à partir d'une ontologie OWL ou d'un besoin métier. À utiliser pour décider des types de nœuds, clés, arêtes, énumérations, héritage, réification et pour écrire ou relire le Schema.cs / Edges.cs / connecteur généré par OntoForge.
---

# Concevoir un schéma Curiosity depuis une ontologie

Cible n°1 d'OntoForge. Implémentation : `backend/ontoforge/mapping/profiles/curiosity.py` (règles, types, nommage),
`backend/ontoforge/targets/curiosity.py` (génération C#). Tout point non confirmé par les sources ci-dessous porte
`À VÉRIFIER` ; ne jamais l'affirmer au client sans test sur son instance.

## Sources (vérifiées le 2026-11-02)
- [S1] https://docs.curiosity.ai/data-connector/schemas : schémas, classes `[Node]`, paires d'arêtes
- [S2] https://docs.curiosity.ai/workspace-api/schema-reference : attributs, types de champs, champs réservés
- [S3] https://docs.curiosity.ai/workspace-api/sdk-csharp : `Graph.Connect`, `AddOrUpdate`, `Link`, `CommitPendingAsync`
- [S4] https://docs.curiosity.ai/workspace-build/guides-and-best-practices/tutorials/custom-connector-from-scratch
- [S5] https://docs.curiosity.ai/workspace-build/guides-and-best-practices/tutorials/technical-support/data-model et https://github.com/curiosity-ai/technical-support
- [S6] https://docs.curiosity.ai/workspace-api/graph-query-language
- [S7] https://docs.curiosity.ai/workspace-build/search-and-nlp/search-configuration/filters-facets

## Contraintes de la plateforme
| Sujet | Fait (source) | Conséquence |
|---|---|---|
| Typage des nœuds | Un nœud = un type, nommé d'après la classe C# `[Node]` (S1, S2). Pas de multi-label. | L'héritage OWL est aplati. |
| Clé | Exactement une propriété `[Key]`, `string`, non vide, identité du nœud (upsert) (S2). | Clé composite = concaténation déterministe ; jamais d'UUID aléatoire. |
| Horodatage | Au plus un `[Timestamp]` (`DateTimeOffset`) (S2). | Choisir la date métier principale. |
| Noms réservés | Type, UID, Key, Timestamp, Edges, EdgeCount (S2). | Suffixer `Value` (`Type` -> `TypeValue`). |
| Arêtes | Un nom, sans propriété, non adressables par clé ; déclarées par paires (aller/retour) ; `Link(a, b, aller, retour)` crée les deux sens (S1, S2, S5). | Relation porteuse d'attributs = nœud. |
| Contraintes | Aucune cardinalité, existence, unicité hors clé (S2). | Tout dans le connecteur (bloc de validations). |
| Types | string, bool, entiers, float/double, decimal, Time (`DateTimeOffset`), GeoPoint, Language, UID128, listes, dictionnaires (S2). | Pas de date seule, heure, durée : `DateTime` minuit / texte ISO 8601. `int?` replié en `int`. |
| Recherche | Plein texte et facettes configurés dans l'espace de travail (S7), pas dans le schéma. | Le générateur recommande, l'humain configure. |

## Patterns
1. **Classe -> type de nœud** (C01). Nom PascalCase. Une classe abstraite sans instance directe n'a pas de type (C04).
2. **Héritage aplati + discriminant** (C02/C03) : recopier les propriétés héritées dans chaque feuille, ajouter `VehicleKind` (string, valeurs = sous-classes, filtrable en facette). Héritage multiple : parent principal (clé + plus de propriétés), autres appartenances en booléens.
3. **Réification en nœud** (R01/R02) : classe de relation porteuse d'attributs ou n-aire -> type de nœud + une paire d'arêtes par participant, clé calculée (`ownerKey|partKey|date`).
4. **Énumération -> nœuds de référence** (C08/I01) : un type, une instance par valeur (clé = valeur), arête vers lui ; donne des facettes liées et suit les renommages. Petit ensemble figé : propriété string + validation (`enum_property`). Punning classe/individu (C12) : nommer distinctement le type et le nœud.
5. **Clés** (K01-K05) : clé métier (`owl:hasKey`) si une seule propriété string ; sinon concaténation `a|b` ; sans clé : IRI. Clé incluant un objet : clé du nœud cible concaténée (K05).
6. **Arêtes** (O01-O05) : paire aller/retour ; inverse OWL = retour nommé ; `hasPart` -> `PartOf` ; symétrique : même nom (`À VÉRIFIER`). Un nom d'arête peut servir plusieurs couples de types (O03).
7. **Perte assumée** : transitivité, chaînes, sous-propriétés -> matérialiser l'arête dérivée dans le connecteur ou traverser à la requête ; disjonction, cardinalité, `only`, réflexivité -> validation applicative.
8. **Littéraux multilingues** (D06) : une propriété par langue (`LabelFr`).

## API C# vérifiée
```csharp
[Node] public class Vehicle { [Key] public string Vin { get; set; } [Property] public string Model { get; set; } [Timestamp] public DateTimeOffset UpdatedAt { get; set; } }
public static class Edges { public const string HasPart = nameof(HasPart); public const string PartOf = nameof(PartOf); }
using var graph = Graph.Connect(endpoint, token, "connecteur");     // S3, S4
await graph.CreateNodeSchemaAsync<Vehicle>();                       // S1
await graph.CreateEdgeSchemaAsync(typeof(Edges));                   // S1
var v = graph.AddOrUpdate(new Vehicle { ... });                     // S3 ; TryAdd pour ne pas écraser
graph.Link(v, p, Edges.HasPart, Edges.PartOf);                      // S3
await graph.CommitPendingAsync();                                   // S3
```
`À VÉRIFIER` : type de retour exact de `AddOrUpdate`, `Link(a, b, X, X)` symétrique, ingestion de `T[]` par classe attribuée, indexation d'un `Dictionary`, version de `Curiosity.Library` à aligner sur l'espace de travail.

## Checklist avant livraison
- [ ] Chaque type concret a exactement une `[Key]` string stable ; clés composites documentées.
- [ ] Aucun nom réservé ni mot-clé C# ; aucun type n'est nommé `Edges`, `Connector`, `RegisterSchema`.
- [ ] Toute arête a son retour ; les arêtes porteuses d'attributs sont des nœuds.
- [ ] Les constats « lost / review » sont arbitrés ou listés dans le rapport (jamais perdus en silence).
- [ ] Validations applicatives présentes pour cardinalités, existence, only, disjonctions.
- [ ] Énumérations utiles aux filtres -> nœuds de référence ; champs de recherche listés pour Manage -> Search.
- [ ] Les `À VÉRIFIER` sont testés sur la version de Curiosity du client.
- [ ] Clé composite : échapper le caractère d'échappement (`%`) avant le séparateur (`|`), rejeter tout composant nul ou vide AVANT de calculer la clé.
- [ ] Arête symétrique : retour = même constante ; noms d'arêtes dérivés avec séparateurs conservés (`HAS_MODEL` -> `HasModel` / `ModelOf`), sans collision avec un type de nœud ni entre arêtes.
- [ ] Chaque validation non transposable produit un avertissement à l'exécution (`NotChecked`), jamais un simple commentaire.
