# L3 — Écarts volontaires par rapport à l'oracle et au contrat de lot

Auteur : lead, 3 nov. 2026. Oracle : `samples/trap/expected-findings.yaml`. Couverture : **79/79 constats** et
**6/6 `must_not`**, pour Curiosity et Neo4j (`backend/tests/test_mapping_oracle.py`). Aucun écart sur l'oracle.

Écarts volontaires (contrat de lot L3 / interprétations), signalés à w3c :

1. **66 règles implémentées dès l'itération 1, aucun `X00`.** L3 A2a demandait `implemented=True` pour les 28 règles
   D-032 « et elles seules ». Toutes sont implémentées : `REGISTRY[r].implemented` est vrai pour les 66 et le drapeau
   `it1` marque les 28 de D-032. Le test `test_registry` vérifie ce comportement. → A2a et A11 à reformuler par le chef.
2. **Règles d'outillage hors catalogue** : S01 (conflit OWL/SHACL), S02 (propriété SHACL non déclarée), G02 (décision
   invalide). Elles sont hors des 66 (`rules.EXTRA`) et documentées dans `docs/RULES.md`.
3. **Granularité de K01 et I01** : un constat par individu nommé (sujet attendu `am:veh_001`, `am:Petrol`). La
   recommandation d'I01 vaut `reference_nodes` pour les membres d'une énumération ou d'un référentiel, et `ignore`
   pour les données d'exemple (surcharge par constat).
4. **Sujets des constats anonymes** : C13 a pour sujet la classe conclue (`am:RequiresDPFCheck`), G01 l'individu
   ancre ou l'IRI de l'ontologie. Le suffixe est `sha1(forme canonique)[:8]`, conformément à D-035.
5. **C04** (heuristique OWA, « probablement abstraite ») exige en plus de l'oracle : pas de hasKey, pas de restriction,
   au plus une propriété objet impliquée, pas de disjointUnion. Sans ces conditions, Vehicle, Part et ElectricVehicle
   seraient signalées à tort. Dans le piège, C04 vise MotorVehicle, Party et Engine.
6. **O02** n'est pas émis quand l'inverse porte domaine et portée (`partOf`) ni pour une propriété équivalente
   (`ownedBy`, O19). La résolution est alors triviale.
7. **Curiosity `multi_label`** (C02/C03), option proposée pour permettre l'arbitrage A8 : il est émulé par une
   propriété liste `<Classe>Types`. Ce n'est pas un vrai multi-type, À VÉRIFIER par l'expert curiosity.
8. **Neo4j, clés héritées** : un sous-type (labels[1:]) reprend la clé de son ancêtre (`Car.key = [vin]`), sans
   recopier la propriété. Le générateur Neo4j résout la clé par les labels.

## Itération 2 (revue w3c it1) — modifications de l'oracle et de la granularité

| Point | Changement | Effet sur `expected-findings.yaml` |
|---|---|---|
| C07 Curiosity | `auto` quand la disjonction est garantie par construction (types distincts ou discriminant scalaire), `lost` sinon ; Neo4j inchangé (`lost`) | f-C07a, f-C07b : `curiosity.severity: auto` (nouveau champ facultatif `severity` par cible, documenté dans l'en-tête du YAML) |
| C02 | une décision par racine concrète de hiérarchie (sujet = racine, `related` = sous-classes) | aucun : f-C02 vise déjà `am:Vehicle` (MotorVehicle est abstraite) |
| D13 | `max 1` seul → `auto` ; `exactly 1` reste `review`, groupable via `D13:*` | aucun : f-D13 (`exactly 1` sur openedAt) reste `review` |
| K03 | `auto` si la clé est l'IRI ; `review` seulement si les instances sont des nœuds blancs | aucun : f-K03 (MileageReading) reste `review` / `generated_key` |
| O08 | texte en inclusion « ⊑ », relation stockée dans les deux cibles | aucun |
| Décisions | clé groupée `<règle>:*` | aucun |

## L13 (3/11) — doublon I01 / C08 et Decimal
- **f-I01 (am:Petrol) retiré** de `samples/trap/expected-findings.yaml`, remplacé par un `must_not` I01 sur `am:Petrol` : un individu membre d'un `owl:oneOf` est porté par C08 (`reference_nodes` crée les nœuds de référence, libellés compris). I01 reste émis pour les autres individus (membres d'un `AllDifferent` seul, individus de plage, données d'exemple).
- **D05 xsd:decimal** : Curiosity → `Decimal` sans perte, donc plus de constat D05 pour `decimal` côté Curiosity ; Neo4j garde D05 (Float avec perte). L'oracle ne listait pas ces D05 : aucun changement d'entrée.
- **f-D05a (am:mileageKm, xsd:decimal)** : côté Curiosity l'entrée devient `absent: true` (type `Decimal`, sans perte, pas de D05) ; côté Neo4j inchangé (`native_type`, Float avec perte). Le test d'oracle comprend `absent: true`.
