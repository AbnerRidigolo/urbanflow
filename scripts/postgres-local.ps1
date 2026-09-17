param([ValidateSet('start','stop')][string]$Action='start')
$ErrorActionPreference='Stop'
Set-Location (Split-Path $PSScriptRoot)
$ufRuntime=(Join-Path (Get-Location) '.runtime')
$ufBin=Join-Path $ufRuntime 'pgsql/bin'
$ufData=Join-Path $ufRuntime 'pgdata'
if (-not (Test-Path "$ufBin/pg_ctl.exe")) { throw 'Extraia os binários oficiais PostgreSQL em .runtime/pgsql primeiro. Veja README.' }
if ($Action -eq 'stop') { & "$ufBin/pg_ctl.exe" -D $ufData stop; exit $LASTEXITCODE }
if (-not (Test-Path "$ufData/PG_VERSION")) {
    $ufPassword=Join-Path $ufRuntime 'init-password.tmp'
    'urbanflow_local_only' | Set-Content $ufPassword -NoNewline
    & "$ufBin/initdb.exe" -D $ufData -U urbanflow --pwfile=$ufPassword --auth=scram-sha-256 -E UTF8 --locale=C
    Remove-Item -LiteralPath $ufPassword
    if ($LASTEXITCODE -ne 0) { throw 'initdb falhou' }
}
& "$ufBin/pg_ctl.exe" -D $ufData -l "$ufRuntime/postgres.log" -o '-h 127.0.0.1 -p 55432' -w start
if ($LASTEXITCODE -ne 0) { throw 'PostgreSQL não iniciou' }
$env:PGPASSWORD='urbanflow_local_only'
& "$ufBin/createdb.exe" -h 127.0.0.1 -p 55432 -U urbanflow urbanflow
Remove-Item Env:PGPASSWORD
