<#
.SYNOPSIS
  Vérifie que le code C# généré par OntoForge (cible Curiosity) compile avec le vrai package Curiosity.Library.

.DESCRIPTION
  1. dézippe l'export OntoForge (zip contenant Schema.cs, Edges.cs, RegisterSchema.cs, Connector.cs) ;
  2. crée un projet .NET 8 temporaire ;
  3. ajoute le package NuGet Curiosity.Library ;
  4. copie les .cs et lance `dotnet build` ;
  5. affiche clairement les erreurs (fichier, ligne, code) ou « COMPILATION OK ».

.PARAMETER Zip
  Chemin du zip d'export OntoForge (cible Curiosity).
.PARAMETER Version
  Version du package Curiosity.Library (défaut : la dernière stable).
.PARAMETER Keep
  Conserve le projet temporaire (sinon supprimé).

.EXAMPLE
  .\check-curiosity.ps1 -Zip C:\temp\ontoforge-curiosity.zip
#>
param(
  [Parameter(Mandatory = $true)][string]$Zip,
  [string]$Version = "",
  [switch]$Keep
)
$ErrorActionPreference = "Stop"

function Fail($msg) { Write-Host "ERREUR : $msg" -ForegroundColor Red; exit 2 }

if (-not (Test-Path $Zip)) { Fail "zip introuvable : $Zip" }
if (-not (Get-Command dotnet -ErrorAction SilentlyContinue)) { Fail "dotnet introuvable : installer le SDK .NET 8 (https://dotnet.microsoft.com/download)" }
$sdks = (& dotnet --list-sdks) -join "`n"
if ($sdks -notmatch "(?m)^8\.") { Write-Host "Attention : aucun SDK 8.x détecté (SDK présents : $sdks). Le build peut échouer." -ForegroundColor Yellow }

$work = Join-Path ([System.IO.Path]::GetTempPath()) ("ontoforge-check-" + [guid]::NewGuid().ToString("N").Substring(0, 8))
$src = Join-Path $work "export"
$proj = Join-Path $work "CheckCuriosity"
New-Item -ItemType Directory -Path $src, $proj | Out-Null

try {
  Expand-Archive -Path $Zip -DestinationPath $src -Force
  $cs = Get-ChildItem -Path $src -Recurse -Filter *.cs
  if (-not $cs) { Fail "aucun fichier .cs dans $Zip (export de la cible Curiosity attendu)" }
  Write-Host "Fichiers C# trouvés : $($cs.Name -join ', ')"

  # Bibliothèque de classes : pas besoin de point d'entrée (Main) pour vérifier la compilation.
  Push-Location $proj
  & dotnet new classlib -f net8.0 -n CheckCuriosity -o . --force | Out-Null
  if ($LASTEXITCODE -ne 0) { Fail "dotnet new a échoué" }
  Remove-Item -ErrorAction SilentlyContinue (Join-Path $proj "Class1.cs")

  $addArgs = @("add", "package", "Curiosity.Library")
  if ($Version) { $addArgs += @("--version", $Version) }
  Write-Host "Ajout du package NuGet Curiosity.Library ..."
  & dotnet @addArgs
  if ($LASTEXITCODE -ne 0) { Fail "impossible d'ajouter Curiosity.Library (réseau, source NuGet ou nom du package à vérifier)" }

  foreach ($f in $cs) { Copy-Item $f.FullName -Destination $proj -Force }

  Write-Host "dotnet build ..."
  $out = & dotnet build --nologo -v minimal 2>&1
  $code = $LASTEXITCODE
  Pop-Location

  $errors = $out | Where-Object { $_ -match ": error " } | Sort-Object -Unique
  $warns = $out | Where-Object { $_ -match ": warning " } | Sort-Object -Unique
  if ($code -eq 0) {
    Write-Host ""
    Write-Host "COMPILATION OK ($($cs.Count) fichiers, $($warns.Count) avertissement(s))." -ForegroundColor Green
    exit 0
  }
  Write-Host ""
  Write-Host "ECHEC DE COMPILATION : $($errors.Count) erreur(s)" -ForegroundColor Red
  foreach ($e in $errors) { Write-Host "  $e" -ForegroundColor Red }
  if (-not $errors) { $out | ForEach-Object { Write-Host $_ } }
  Write-Host ""
  Write-Host "Renvoyer ces lignes (ou le fichier $work\build.log) à l'équipe OntoForge." -ForegroundColor Yellow
  $out | Out-File (Join-Path $work "build.log") -Encoding utf8
  $Keep = $true
  exit 1
}
finally {
  if (Get-Location | Where-Object { $_.Path -eq $proj }) { Pop-Location }
  if ($Keep) { Write-Host "Projet conservé : $work" } else { Remove-Item -Recurse -Force $work -ErrorAction SilentlyContinue }
}
