$ErrorActionPreference='Stop'
$taskStatePath=Join-Path $PSScriptRoot '.runtime/processes.json'
if (-not (Test-Path -LiteralPath $taskStatePath)) { Write-Host 'No process state from start.ps1.'; exit }
$taskState=Get-Content -LiteralPath $taskStatePath -Raw | ConvertFrom-Json
foreach ($taskName in @('backend','mysql')) {
    $taskSaved=$taskState.$taskName
    if (-not $taskSaved) { continue }
    $taskProcess=Get-Process -Id $taskSaved.pid -ErrorAction SilentlyContinue
    if ($taskProcess -and $taskProcess.StartTime.ToUniversalTime().Ticks -eq ([datetime]$taskSaved.started).ToUniversalTime().Ticks) {
        if ($taskName -eq 'mysql') {
            & (Join-Path $PSScriptRoot 'backend/.venv/Scripts/python.exe') -c 'from backend.db import connect,execute; c=connect(False); execute("SHUTDOWN",conn=c); c.close()'
            if ($LASTEXITCODE -eq 0) { Write-Host 'Stopped project MySQL gracefully.'; continue }
        }
        Stop-Process -Id $taskProcess.Id
        Write-Host "Stopped project $taskName process."
    }
}
