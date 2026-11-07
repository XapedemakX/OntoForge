# Rapport L2 — conformité W3C (agent w3c)

Livrés : `conformance/report.py`, `profiles.py`, `lint.py`, `reasoner.py`, `samples/trap/trap-nondl.ttl`, `tests/test_conformance_profiles.py`, section 7 du skill.

Résultats : trap.ttl → DL vrai, 0 erreur, cohérent (OWL RL, prp-key contourné), EL/QL/RL faux avec les raisons de l'oracle ; trap-nondl.ttl → W01–W07 détectés ; mini-ontologies EL, QL, RL testées.

Choix et limites
- Codes : W01–W07 et BP01–BP07 (et non W3C-00x de l'oracle : à arbitrer par le chef).
- Contrôles sur le graphe RDF ; `check_conformance(..., graph=None)` reconstruit le graphe par `rdf_export`.
- `DisjointUnion` classé hors EL/QL/RL : À VÉRIFIER (OWL 2 Profiles).
- W06 : heuristique RL (disjonction/complément/Nothing) ; pas de propagation par les restrictions. HermiT optionnel via owlready2 (sous-processus, 30 s, jamais bloquant) : intégration non testée sur une ontologie non triviale.
- Datatypes de la carte EL/QL/RL : listes de PROF recopiées de mémoire, à relire.
- Appel supplémentaire non prévu au contrat : `run_reasoner`, `hermit`, `timeout` (mots-clés, valeurs par défaut sûres).
