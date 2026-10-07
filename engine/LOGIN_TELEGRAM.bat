@echo off
cd /d %~dp0
call venv\Scripts\activate.bat
python login_telegram.py
pause
