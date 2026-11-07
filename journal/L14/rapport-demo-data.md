# L14 — rapport : jeu de données de démo AutoMaint (agent shacl)

Tests : `cd backend && pytest -q` -> 524 verts (6 nouveaux dans `tests/test_demo_data.py`). Fichiers existants inchangés.

## Livré
- `samples/automaint/automaint-demo-data.ttl` (~4100 triplets) : 8 modèles / 7 marques (thermique essence et diesel, électrique, hybride), 40 véhicules, 6 garages (Toulouse, Lyon, Bordeaux, Nantes, Lille, Marseille), 15 techniciens, 30 clients (noms inventés), 120 ordres 2025-2026 (opérations, pièces installées, technicien, garage, `concerns`/`hasRepairOrder`), 160 relevés kilométriques strictement croissants par véhicule, 12 codes défaut OBD (P0300, P0420, P0171…), codes actifs sur 14 véhicules, 3 rappels (modèles + référence concernée), garanties, un plan d'entretien par modèle. Labels fr.
- `tools/demo/generate_demo_data.py` : graine fixe, sortie identique à chaque exécution (`python tools/demo/generate_demo_data.py`).
- Conformité : pyshacl `inference="none"` -> 0 violation. Pour cela les super-classes visées par les shapes sont typées explicitement (Vehicle, Engine).

## Points à signaler
- **Pas de propriété « ville »** dans l'ontologie : la ville est dans `am:displayName` du garage (« Garage du Capitole — Toulouse »). Une requête « Toulouse » = filtre « nom affiché contient ».
- Hybrides : typées `am:Vehicle` seulement, avec deux moteurs (thermique + électrique) ; ni Combustion ni Electric (classes disjointes).
- Marques et modèles réels (Renault, Peugeot…) ; références de pièces, VIN, plaques et personnes inventés.
- Ordres ouverts (sans `closedAt`) : ceux postérieurs au 20/10/2026.
- Le fichier se liste comme « données » (suffixe `-data`) à côté de `automaint-data.ttl` (4 violations attendues) : le front doit laisser choisir.
- Tests de requêtes : véhicule -> ordre -> technicien, ordres en garage de Toulouse, véhicules avec code actif, rappel -> modèle -> marque (via `queries.builder` sur graphe rdflib local).
