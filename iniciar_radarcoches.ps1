param([switch]$SinNavegador)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$radarPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $radarPython)) { throw 'Falta .venv. Ejecuta scripts\instalar.ps1.' }
try {
    $radarHealth = Invoke-RestMethod -Uri 'http://127.0.0.1:8765/api/health' -TimeoutSec 2
    if ($radarHealth.status -eq 'ok' -and $radarHealth.local_only) {
        Write-Host 'RadarCoches ya esta en marcha: http://127.0.0.1:8765'
        if (-not $SinNavegador) { try { Start-Process 'http://127.0.0.1:8765' } catch { Write-Warning 'El sistema no permite abrir el navegador automaticamente. Abre http://127.0.0.1:8765 manualmente; el servidor funciona.' } }
        exit 0
    }
    throw 'El puerto 8765 esta ocupado por otro servicio.'
} catch [System.Net.WebException] { Write-Verbose 'Servidor no listo' }
New-Item -ItemType Directory -Force -Path 'data' | Out-Null
$radarPreviousInstance = $env:RADAR_INSTANCE_ID
$radarInstance = [guid]::NewGuid().ToString()
$env:RADAR_INSTANCE_ID = $radarInstance
try {
    $radarProc = Start-Process -FilePath $radarPython -ArgumentList @('-m','uvicorn','backend.main:app','--host','127.0.0.1','--port','8765','--no-access-log') -WorkingDirectory $PSScriptRoot -WindowStyle Hidden -RedirectStandardOutput 'data\servidor.log' -RedirectStandardError 'data\servidor-error.log' -PassThru
} finally { $env:RADAR_INSTANCE_ID = $radarPreviousInstance }
$radarReady = $false
for ($radarAttempt = 0; $radarAttempt -lt 30; $radarAttempt++) {
    Start-Sleep -Milliseconds 300
    $radarProc.Refresh()
    if ($radarProc.HasExited) { throw 'El servidor no arranco. Revisa data\servidor-error.log.' }
    try {
        $radarHealth = Invoke-RestMethod -Uri 'http://127.0.0.1:8765/api/health' -TimeoutSec 2
        if ($radarHealth.instance_id -eq $radarInstance) { $radarReady = $true; break }
    } catch { Write-Verbose 'Esperando servidor' }
}
if (-not $radarReady) { throw 'No se verifico el servidor de esta ejecucion. Revisa logs.' }
$radarProcesses = @()
foreach ($radarProcessId in @($radarProc.Id, [int]$radarHealth.process_id) | Select-Object -Unique) {
    $radarRunning = Get-Process -Id $radarProcessId -ErrorAction Stop
    $radarProcesses += @{ id=$radarRunning.Id; start_ticks=$radarRunning.StartTime.ToUniversalTime().Ticks.ToString(); path=$radarRunning.Path }
}
@{instance=$radarInstance; processes=$radarProcesses} | ConvertTo-Json -Depth 4 | Set-Content -Encoding UTF8 -LiteralPath 'data\radar.pid.json'
Write-Host 'RadarCoches disponible: http://127.0.0.1:8765'
if (-not $SinNavegador) { try { Start-Process 'http://127.0.0.1:8765' } catch { Write-Warning 'El sistema no permite abrir el navegador automaticamente. Abre http://127.0.0.1:8765 manualmente; el servidor funciona.' } }
