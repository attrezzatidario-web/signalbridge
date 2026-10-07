@echo off
cd /d %~dp0
echo Installazione librerie...
py -3 -m venv venv
call venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt
if not exist .env copy .env.example .env
echo.
echo FATTO. Ora apri il file .env con il Blocco note e compila i dati.
pause
