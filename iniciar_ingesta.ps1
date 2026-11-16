param([ValidateSet('local','apis','kafka','distributed')][string]$Modo = 'local', [switch]$Volumen)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$radarPython = '.\.venv\Scripts\python.exe'
switch ($Modo) {
    'local' { & $radarPython -m actividad_ingesta.pipeline demo --root data/laboratorio }
    'apis' {
        Write-Host 'APIs DEMO en 127.0.0.1:8771 y :8772; Ctrl+C detiene ambas.'
        & $radarPython scripts/run_source_apis.py
    }
    'kafka' { docker compose -f actividad_ingesta/docker-compose.yml up -d }
    'distributed' {
        if ($Volumen) { & $radarPython scripts/run_distributed.py --volume }
        else { & $radarPython scripts/run_distributed.py }
    }
}
exit $LASTEXITCODE
