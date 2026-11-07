# Revue W3C — L3 moteur de mapping (itération 2)

Relecteur : w3c — 3 nov. 2026. J'ai rejoué m1, m2 et m3 (scratchpad) sur samples/automaint et sur les cas adverses, puis relu `fix-moteur-it1.md` et la section it2 d'`ecarts-oracle.md`. Suite de tests : 460 verts et 2 rouges, dans test_assistant_api et test_assistant_service (statut du fournisseur mock). Ces deux échecs sont hors L3, à signaler au lead.

```
verdict: OK
bloquants:
  (aucun)
non-bloquants:
  - Les 5 bloquants de l'it1 sont levés et vérifiés :
    1. Ordre des chaînes conservé.
    2. O08 est écrit « p ∘ q ⊑ r » et R est stockée dans les deux cibles (Neo4j compris).
    3. domain(A ⊓ B) : la propriété est rattachée à A et à B, avec un constat D12 et une validation all_of. Inférence correcte.
    4. Party.BrandName n'est plus obligatoire ; les validations WorksAt et HasEngine portent discriminator + values, et target_discriminator_values pour le filler.
    5. Deux `some` sur HasEngine donnent 0..*.
  - Bruit sur automaint : review + lost passe à 49 (Curiosity) et 52 (Neo4j). Les changements d'oracle sont sémantiquement justifiés :
    - C07 auto en Curiosity : la disjonction est garantie par construction (types distincts ou discriminant scalaire). Elle reste lost en Neo4j, où le multi-label permet la violation.
    - D13 `max 1` → auto : la propriété scalaire est déjà le défaut, donc aucune perte.
    - K03 → auto si la clé est l'IRI : identité OWL = IRI.
    - C02 : une décision par racine de hiérarchie.
    - `exactly 1` reste review : c'est un renforcement monde clos, à décider une fois via D13:*.
  - O09 ×10 et O10 ×5 restent review, un par restriction. Utiliser par défaut la décision groupée O09:* et O10:* dans l'interface.
skill: rien (owl-to-property-graph complété par le lead).
```
