param([ValidateSet('fixture','ingest','etl','run','serve')][string]$Command='run', [string]$Kind='synthetic', [string[]]$Months=@('2024-01','2024-02','2024-03'))
$ErrorActionPreference='Stop'
Set-Location (Split-Path $PSScriptRoot)
$env:PYTHONPATH='src'
if (Test-Path 'C:/Program Files/Java/jdk-17/bin/java.exe') { $env:JAVA_HOME='C:/Program Files/Java/jdk-17' }
& ./.venv/Scripts/python.exe -m urbanflow.cli $Command --kind $Kind --months $Months
exit $LASTEXITCODE
