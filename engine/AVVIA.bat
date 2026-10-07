@echo off
title SignalBridge
cd /d %~dp0
call venv\Scripts\activate.bat
:loop
python main.py
echo Motore fermato. Riavvio tra 10 secondi... (chiudi la finestra per uscire)
timeout /t 10
goto loop
