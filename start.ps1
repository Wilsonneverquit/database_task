param([string]$MySQLHome = '', [switch]$SkipBuild)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$taskPython = Join-Path $PSScriptRoot 'backend/.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $taskPython)) {
    python -m venv backend/.venv
    if ($LASTEXITCODE -ne 0) { throw 'Python 3.10+ is required.' }
}
& $taskPython -c 'import flask,pymysql,dotenv,cryptography' 2>$null
if ($LASTEXITCODE -ne 0) {
    & $taskPython -m pip install -r backend/requirements.txt
    if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
}
New-Item -ItemType Directory -Path '.runtime/mysql' -Force | Out-Null
$taskMysqlCommand = Get-Command mysqld.exe -ErrorAction SilentlyContinue
if (-not $MySQLHome) {
    if ($taskMysqlCommand) { $MySQLHome = Split-Path (Split-Path $taskMysqlCommand.Source) }
    elseif (Test-Path 'D:/MySQL/server/bin/mysqld.exe') { $MySQLHome = 'D:/MySQL/server' }
    else { throw 'Pass -MySQLHome with your MySQL 8+ installation folder.' }
}
$taskMysqlExe = Join-Path $MySQLHome 'bin/mysqld.exe'
if (Test-Path '.runtime/mysql-real/auto.cnf') {
    & (Join-Path $PSScriptRoot 'real-instance.ps1') -Action start -MySQLHome $MySQLHome
}
$taskState = @{}
if (Test-Path '.runtime/processes.json') {
    $taskOldState=Get-Content -LiteralPath '.runtime/processes.json' -Raw | ConvertFrom-Json
    if ($taskOldState.mysql) {
        $taskOldMysql=Get-Process -Id $taskOldState.mysql.pid -ErrorAction SilentlyContinue
        if ($taskOldMysql -and $taskOldMysql.StartTime.ToUniversalTime().Ticks -eq ([datetime]$taskOldState.mysql.started).ToUniversalTime().Ticks) { $taskState.mysql=$taskOldState.mysql }
    }
    if ($taskOldState.backend) {
        $taskOldBackend=Get-Process -Id $taskOldState.backend.pid -ErrorAction SilentlyContinue
        if ($taskOldBackend -and $taskOldBackend.StartTime.ToUniversalTime().Ticks -eq ([datetime]$taskOldState.backend.started).ToUniversalTime().Ticks) {
            Write-Host 'Project backend is already running: http://127.0.0.1:5000'
            exit
        }
    }
}
$taskConfigPort='from backend.db import ROOT; import os; print(os.getenv("DB_PORT","3307"))' | & $taskPython -
$taskConfigHost='from backend.db import ROOT; import os; print(os.getenv("DB_HOST","127.0.0.1"))' | & $taskPython -
$taskPortCheck = 'import socket; s=socket.socket(); s.settimeout(1); print(s.connect_ex(("127.0.0.1",3307))==0); s.close()'
$taskListening = $taskPortCheck | & $taskPython -
if ($taskListening -ne 'True' -and $taskConfigPort -eq '3307' -and $taskConfigHost -eq '127.0.0.1') {
    if (-not (Test-Path '.runtime/mysql/auto.cnf')) {
        Push-Location '.runtime/mysql'
        try { & $taskMysqlExe --no-defaults --initialize-insecure "--basedir=$MySQLHome" --datadir=. --console }
        finally { Pop-Location }
        if ($LASTEXITCODE -ne 0) { throw 'MySQL initialization failed.' }
    }
    $taskMysqlProcess = Start-Process -FilePath $taskMysqlExe -ArgumentList @('--no-defaults',('--basedir="'+$MySQLHome+'"'),'--datadir=.','--port=3307','--bind-address=127.0.0.1','--mysqlx=OFF','--log-error=server.err') -WorkingDirectory (Join-Path $PSScriptRoot '.runtime/mysql') -WindowStyle Hidden -PassThru
    $taskState.mysql = @{pid=$taskMysqlProcess.Id;started=$taskMysqlProcess.StartTime.ToUniversalTime().ToString('O')}
    for ($taskAttempt=0; $taskAttempt -lt 30; $taskAttempt++) {
        Start-Sleep -Milliseconds 500
        if (($taskPortCheck | & $taskPython -) -eq 'True') { break }
    }
}
& $taskPython -m backend.manage migrate
if ($LASTEXITCODE -ne 0) { throw 'Migration failed. Check backend/.env or project MySQL log.' }
$taskSeeded = 'from backend.db import connect,one; c=connect(); print(one("SELECT COUNT(*) n FROM sys_user",conn=c)["n"]); c.close()' | & $taskPython -
if ($taskSeeded -eq '0') {
    & $taskPython -m backend.manage seed
    if ($LASTEXITCODE -ne 0) { throw 'Dataset loading failed; see the error above.' }
}
if (-not $SkipBuild) {
    Push-Location frontend
    try {
        if (-not (Test-Path 'node_modules')) { npm ci; if ($LASTEXITCODE -ne 0) { throw 'npm ci failed.' } }
        npm run build
        if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed.' }
    } finally { Pop-Location }
}
if (-not (Test-Path 'frontend/dist/index.html')) { throw 'Run without -SkipBuild first.' }
$taskBackendProcess = Start-Process -FilePath $taskPython -ArgumentList @('-m','backend.app') -WorkingDirectory $PSScriptRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $PSScriptRoot '.runtime/backend.log') -RedirectStandardError (Join-Path $PSScriptRoot '.runtime/backend-error.log') -PassThru
Start-Sleep -Milliseconds 800
if ($taskBackendProcess.HasExited) { throw 'Backend failed to start. See .runtime/backend-error.log.' }
$taskState.backend = @{pid=$taskBackendProcess.Id;started=$taskBackendProcess.StartTime.ToUniversalTime().ToString('O')}
$taskState | ConvertTo-Json | Set-Content -LiteralPath '.runtime/processes.json' -Encoding UTF8
Write-Host 'Open http://127.0.0.1:5000  |  analyst1 / 123456'
Write-Host 'The original risk_alert database is untouched. Use stop.ps1 to stop processes started here.'
