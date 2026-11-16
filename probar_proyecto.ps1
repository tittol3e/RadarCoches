$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
& '.\.venv\Scripts\python.exe' 'scripts\run_tests.py'
exit $LASTEXITCODE
