verdict: OK
bloquants:
  - aucun
non-bloquants:
  - [targets/curiosity.py:122-131, 862-873] Aucun .csproj n'est généré : la version figure dans l'en-tête de Schema.cs, Edges.cs, RegisterSchema.cs, Connector.cs, dans README-curiosity.md et dans `dotnet add package Curiosity.Library --version 26.11.7740`. Cohérent avec la valeur d'usine 26.11.7740 (NuGet du 5/11/2026, relevée par la veille ; 26.10.6546 reste listée « supportée »). Vérifié par exécution du générateur et test_curiosity_version_in_headers_and_readme.
  - Version inconnue acceptée et marquée À VÉRIFIER ; compatibilité avec le serveur Curiosity marquée À VÉRIFIER. Correct : rien n'est inventé.
  - NuGet non relu en ligne : la veille du 7/11 fait foi.
skill: curiosity-schema-design : pas de csproj généré, version épinglée par la commande dotnet add package.
Corrections faites : aucune.
