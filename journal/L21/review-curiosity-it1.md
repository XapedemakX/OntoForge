# L21 — revue curiosity, itération 1

Relecteur : expert Curiosity (agent `curiosity`). Date : 7/11/2026. Périmètre : `docs/veille/normes.md` partie 3, idées V-02, V-13 et V-15, au regard de `backend/ontoforge/targets/curiosity.py`.
Sources relues le 7/11/2026 : page NuGet Curiosity.Library, docs.curiosity.ai/workspace-api/sdk-csharp, docs.curiosity.ai/workspace-customization/data-connector/schemas.

```
verdict: OK
bloquants:
  (aucun après correction ; les trois erreurs factuelles ont été corrigées, voir plus bas)
non-bloquants:
  - [backend/ontoforge/targets/curiosity.py:470] le SDK documente `CreateNodeSchemaAsync<T>(overwrite)`. Le code généré l'appelle sans argument, donc avec une valeur par défaut supposée. À VÉRIFIER par compilation (A2) : si `overwrite` est obligatoire, ajouter `overwrite: false`. Le point est ajouté à normes.md l. 69.
  - [backend/ontoforge/targets/curiosity.py:804] `Link(a, b, edge, reverse)` est confirmé par la surcharge documentée `Link(a, b, edgeAtoB, edgeBtoA, …)`. Le commentaire `[S3][S5]` peut citer la page SDK. Le À VÉRIFIER de la l. 737 (arête symétrique `Link(a, b, X, X)`) reste ouvert : la page ne parle pas du cas où les deux noms sont égaux.
  - [backend/ontoforge/targets/curiosity.py:262] `[Timestamp]` : la doc montre un seul champ `DateTimeOffset` et ne dit pas « au plus un ». La règle d'OntoForge (au plus un) est prudente, à garder ; la limite elle-même reste À VÉRIFIER.
  - [docs/veille/normes.md:74] compatibilité paquet NuGet / serveur : toujours non documentée (la page du SDK ne donne aucune version). À VÉRIFIER auprès de Curiosity. Épingler dans le README généré la version testée, pas « la dernière » : le paquet sort plusieurs versions par semaine.
  - [docs/veille/normes.md:72] page « release notes » 2.5.0 non datée : non relue ici. L'avis « ne pas s'y fier » est maintenu.
  - Idée normes.md l. 70 (fabrique `Schema` / `FieldType`) : à garder en Surveiller. Les attributs restent la voie documentée dans la page des connecteurs.
corrigé par le relecteur :
  - normes.md l. 14, 66, 124 ; processus-mise-a-jour.md l. 141 et 181 ; journal/L21/rapport.md l. 44 et 48 ; docs/IDEES.md (V-02) : dernière version **26.11.7740 du 05/11/2026**, et non 26.10.6546 du 09/10. 20 versions entre le 24/09 et le 05/11 ; la cible net11.0 apparaît aussi.
  - normes.md l. 67 : la fiche disait « `[Timestamp]` non généré ». Faux : curiosity.py l. 262-266 génère déjà un `[Timestamp]` (premier DateTime scalaire obligatoire, sinon premier).
  - normes.md l. 69 : l'ordre `Link(source, cible, aller, retour)` est maintenant documenté (surcharge à deux noms d'arête). Seul le type de retour `Node` de `AddOrUpdate` reste À VÉRIFIER.
skill: curiosity-schema-design → « Link(a, b, edgeAtoB, edgeBtoA) documenté (SDK C#, relu le 7/11/2026) ; CreateNodeSchemaAsync<T>(overwrite) : paramètre à confirmer par compilation. »
```
