$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$radarPidFile = Join-Path $PSScriptRoot 'data\radar.pid.json'
if (-not (Test-Path -LiteralPath $radarPidFile)) { Write-Host 'Sin PID registrado. Para arranque manual usa Ctrl+C en su terminal.'; exit 0 }
$radarInfo = Get-Content -Raw -LiteralPath $radarPidFile | ConvertFrom-Json
foreach ($radarRecord in @($radarInfo.processes) | Sort-Object -Property id -Descending) {
    $radarRunning = Get-Process -Id ([int]$radarRecord.id) -ErrorAction SilentlyContinue
    if (-not $radarRunning) { continue }
    if ($radarRunning.StartTime.ToUniversalTime().Ticks.ToString() -ne $radarRecord.start_ticks -or $radarRunning.Path -ne $radarRecord.path) { throw 'PID reutilizado por otro proceso: no se detiene.' }
    Stop-Process -Id $radarRunning.Id -ErrorAction SilentlyContinue
}
Remove-Item -LiteralPath $radarPidFile
Write-Host 'RadarCoches detenido. Los datos siguen guardados.'
