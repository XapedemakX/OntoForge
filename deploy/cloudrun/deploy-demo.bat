@echo off
rem Lance la mise a jour de https://ontoforge.ajlx.fr (voir deploy-demo.ps1). Journal : deploy-demo.log a la racine du depot.
cd /d "%~dp0..\.."
powershell -NoProfile -ExecutionPolicy Bypass -Command "& .\deploy\cloudrun\deploy-demo.ps1 *>&1 | Tee-Object -FilePath deploy-demo.log"
echo.
echo Fin. Le journal est dans deploy-demo.log
pause
