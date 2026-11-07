# Plan de reprise après la limite d'usage (décision Jerem, 2 nov. 23h11)

Prévue à 2 h 58 (réinitialisation à 2 h 50). Règle des modèles :
- **Opus** : moteur de mapping (reprise de l'agent existant via SendMessage), revues W3C.
- **Sonnet** : nouveaux agents qui reprennent à partir des fichiers sauvegardés : io RDF, SHACL, conformité, Curiosity, Neo4j, requêtes, front, assistant, chef de projet.
- **Haiku** : tests, vérification des critères d'acceptation, salle des agents, journal.
- 4 à 5 agents en parallèle au maximum. En cas de 429 : ne rien relancer, reprogrammer la reprise à l'heure de réinitialisation.

Vague 1 : moteur L3 (Opus, reprise), io W3C (Sonnet), Curiosity (Sonnet), SHACL (Sonnet).
Vague 2 : front (Sonnet), Neo4j (Sonnet), conformité (Sonnet).
Vague 3 : requêtes (Sonnet), assistant (Sonnet), chef it2 contrats (Sonnet), puis les revues croisées (Opus W3C + Sonnet experts) et la recette (Haiku pour l'exécution des critères).

Chaque nouvel agent Sonnet reçoit la même consigne que l'agent interrompu, plus : « un agent précédent a commencé ce travail ; lis l'état actuel de tes fichiers et `git log`, ne repars pas de zéro ».
