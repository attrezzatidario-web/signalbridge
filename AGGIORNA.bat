@echo off
cd /d %~dp0\..
echo Scarico aggiornamenti da GitHub...
git pull
cd engine
call venv\Scripts\activate.bat
pip install -q -r requirements.txt
echo.
echo FATTO. Chiudi la finestra del motore e riapri AVVIA.bat
pause
