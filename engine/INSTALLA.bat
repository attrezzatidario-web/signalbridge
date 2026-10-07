@echo off
cd /d %~dp0
echo === Installazione SignalBridge ===
py -3 -m venv venv
call venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt
echo Scarico Caddy (HTTPS automatico)...
powershell -NoProfile -ExecutionPolicy Bypass -Command "Invoke-WebRequest -Uri 'https://caddyserver.com/api/download?os=windows&arch=amd64' -OutFile caddy.exe"
echo Apro le porte 80 e 443 nel firewall...
netsh advfirewall firewall add rule name="SignalBridge HTTP" dir=in action=allow protocol=TCP localport=80 >nul
netsh advfirewall firewall add rule name="SignalBridge HTTPS" dir=in action=allow protocol=TCP localport=443 >nul
if not exist .env copy .env.example .env
echo.
echo FATTO. Ora apri il file .env con il Blocco note e compila i dati.
pause
