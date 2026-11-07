# Demandes de contrat — L9 (lead)

1. **`Severity` += `"info"`** (`core/pg_model.py`) : les constats P00–P03 de périmètre sont aujourd'hui émis en `auto`, ce qui gonfle le compteur « auto » de `PGModel.summary()`. Un niveau `info` (hors compteurs d'arbitrage) serait plus juste.
2. **Icône dans le PGModel** : proposer `NodeType.icon: Optional[str]` (nom Font Awesome, repris de `Project.view.icons`) pour que les générateurs / le rapport puissent l'exporter (ex. métadonnée Curiosity). Non fait : le contrat n'autorise pas de nouveau champ sans décision. Les générateurs n'en dépendent pas.
3. **`OntClass.abstract`** : l'éditeur déduit `abstract` (union disjointe ou annotation `urn:ontoforge:abstract`). Un champ explicite éviterait la convention.
