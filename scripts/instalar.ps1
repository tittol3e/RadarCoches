param([switch]$SinRed,[switch]$BigData,[switch]$Desarrollo)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath (Split-Path $PSScriptRoot -Parent)
if (-not (Test-Path -LiteralPath '.venv\Scripts\python.exe')) { python -m venv .venv; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE } }
$radarArgs = @('-m','pip','install')
if ($SinRed) { $radarArgs += @('--no-index','--find-links','data/wheelhouse') }
$radarRequirements = if ($Desarrollo) {'requirements-dev.txt'} else {'requirements.txt'}
& '.\.venv\Scripts\python.exe' @radarArgs -r $radarRequirements
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
if ($BigData) {
    & '.\.venv\Scripts\python.exe' @radarArgs -r actividad_ingesta/requirements-bigdata.txt
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
& '.\.venv\Scripts\python.exe' -m pip check
exit $LASTEXITCODE
