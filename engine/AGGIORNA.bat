@echo off
cd /d %~dp0
echo Scarico l'ultima versione da GitHub...
powershell -NoProfile -ExecutionPolicy Bypass -File aggiorna.ps1
if errorlevel 1 (echo ERRORE durante il download & pause & exit /b 1)
call venv\Scripts\activate.bat
pip install -q -r requirements.txt
echo.
echo FATTO. Chiudi la finestra del motore e riapri AVVIA.bat
pause
