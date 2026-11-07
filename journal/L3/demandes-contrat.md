# L3 — Demandes d'évolution du contrat (core/*.py) — non bloquantes

| # | Modèle | Demande | Contournement actuel |
|---|---|---|---|
| 1 | `PGType` | Ajouter `Decimal` (Curiosity FieldType.Decimal, D05 xsd:decimal sans perte) | `Float` + constat D05 (option `string_lexical`) |
| 2 | `ValidationKind` | Ajouter `unique` (K02 `uri_key`, unicité composite) | `kind="other"`, `params.unique` |
| 3 | `MaterializationKind` | Ajouter `key` (K05 clé recopiée / concaténée) | propriété avec `note`, sans matérialisation |
| 4 | `Cardinality` | Bornes numériques `{min, max}` (O16 `min 4 Wheel`, revue w3c §4) | `Validation.params.n` |
| 5 | `ObjectProperty.inverse_of` | `list[str]` (plusieurs owl:inverseOf légaux, revue w3c it1 §2) | premier inverse seulement |
| 6 | `Finding` | Champ `compensation` (texte) pour le rapport | dérivé du catalogue + validations / matérialisations liées par id |
