$ErrorActionPreference='Stop'
if (Test-Path -LiteralPath (Join-Path $PSScriptRoot '.runtime/real-instance.json')) {
    & (Join-Path $PSScriptRoot 'real-instance.ps1') -Action stop
}
$taskStatePath=Join-Path $PSScriptRoot '.runtime/processes.json'
if (-not (Test-Path -LiteralPath $taskStatePath)) { Write-Host 'No process state from start.ps1.'; exit }
$taskState=Get-Content -LiteralPath $taskStatePath -Raw | ConvertFrom-Json
foreach ($taskName in @('backend','mysql')) {
    $taskSaved=$taskState.$taskName
    if (-not $taskSaved) { continue }
    $taskProcess=Get-Process -Id $taskSaved.pid -ErrorAction SilentlyContinue
    if ($taskProcess -and $taskProcess.StartTime.ToUniversalTime().Ticks -eq ([datetime]$taskSaved.started).ToUniversalTime().Ticks) {
        if ($taskName -eq 'mysql') {
            'from backend.db import ROOT,connect,execute,one; import configparser; conf=configparser.ConfigParser(); conf.read(ROOT/".runtime/mysql/auto.cnf"); c=connect(False); assert one("SELECT @@server_uuid u, @@port p",conn=c)==dict(u=conf["auto"]["server-uuid"],p=3307); execute("SHUTDOWN",conn=c); c.close()' | & (Join-Path $PSScriptRoot 'backend/.venv/Scripts/python.exe') -
            if ($LASTEXITCODE -eq 0) { Write-Host 'Stopped project MySQL gracefully.'; continue }
        }
        Stop-Process -Id $taskProcess.Id
        Write-Host "Stopped project $taskName process."
    }
}
