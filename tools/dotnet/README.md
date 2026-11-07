# Vérification de compilation C# (cible Curiosity)

`check-curiosity.ps1` vérifie que le code généré par OntoForge compile avec le vrai package NuGet `Curiosity.Library`.
À lancer sous Windows (PowerShell 5.1 ou 7), avec le SDK .NET 8 et un accès à nuget.org.

## Usage
1. Dans OntoForge, exporter la cible Curiosity (zip contenant `Schema.cs`, `Edges.cs`, `RegisterSchema.cs`, `Connector.cs`).
2. Lancer :
   ```powershell
   .\tools\dotnet\check-curiosity.ps1 -Zip C:\chemin\ontoforge-curiosity.zip
   # options : -Version 1.2.3 (version du package)   -Keep (garder le projet temporaire)
   ```
3. Le script crée une bibliothèque de classes .NET 8 temporaire, ajoute `Curiosity.Library`, copie les `.cs` et lance `dotnet build`.

## Résultat
- `COMPILATION OK` (code retour 0) : le C# généré compile.
- `ECHEC DE COMPILATION` (code 1) : chaque erreur est listée (`fichier(ligne,col): error CSxxxx: ...`) et le journal est gardé dans `build.log` du dossier temporaire affiché. Renvoyer ces lignes à l'équipe : elles servent à lever les points `# À VÉRIFIER` du générateur (noms d'API Curiosity, types, attributs).
- Code 2 : prérequis manquant (zip, SDK .NET, package introuvable).

Le script n'envoie rien en ligne hormis le téléchargement NuGet, et ne modifie rien hors du dossier temporaire.
