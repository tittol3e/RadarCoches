param([switch]$Volumen)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$radarCommand = if ($Volumen) { 'volume' } else { 'demo' }
& '.\.venv\Scripts\python.exe' -m actividad_ingesta.pipeline $radarCommand --root data/laboratorio
exit $LASTEXITCODE
