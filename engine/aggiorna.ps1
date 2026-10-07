$ErrorActionPreference = "Stop"
$t = Join-Path $env:TEMP "sb_update"
if (Test-Path $t) { Remove-Item $t -Recurse -Force }
New-Item -ItemType Directory $t | Out-Null
$zip = Join-Path $t "r.zip"
Invoke-WebRequest "https://github.com/attrezzatidario-web/signalbridge/archive/refs/heads/main.zip" -OutFile $zip
Expand-Archive $zip $t
$src = Join-Path $t "signalbridge-main\engine"
Copy-Item (Join-Path $src "*") $PSScriptRoot -Recurse -Force
Write-Host "Aggiornato."
