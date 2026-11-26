param([ValidateSet('start','stop')][string]$Action = 'start', [string]$MySQLHome = 'D:/MySQL/server')
$ErrorActionPreference = 'Stop'
$runtime = Join-Path $PSScriptRoot '.runtime'
$data = Join-Path $runtime 'mysql-real'
$state = Join-Path $runtime 'real-instance.json'
$secret = Join-Path $runtime 'real-db-password'
$init = Join-Path $data 'first-launch.sql'
$exe = Join-Path $MySQLHome 'bin/mysqld.exe'
$owned = $null
$identity = Join-Path $data 'auto.cnf'
function Test-LocalServer([switch]$Shutdown) {
    if (-not (Test-Path -LiteralPath $identity)) { return $false }
    $uuid = ((Get-Content -LiteralPath $identity | Select-String '^server-uuid=').Line -split '=')[1]
    $probe = "from backend.db import connect,one,execute,ROOT; import os,sys; os.environ.update(REAL_DB_HOST='127.0.0.1',REAL_DB_PORT='3308',REAL_DB_USER='root',REAL_DB_PASSWORD=(ROOT/'.runtime/real-db-password').read_text().strip()); c=connect(False,source='real'); assert one('SELECT @@server_uuid u,@@port p',conn=c)==dict(u=sys.argv[1],p=3308);"
    if ($Shutdown) { $probe += "execute('SHUTDOWN',conn=c);" }
    Push-Location $PSScriptRoot
    try { $probe | & 'backend/.venv/Scripts/python.exe' - $uuid 2>$null; return ($LASTEXITCODE -eq 0) } finally { Pop-Location }
}
if (Test-Path -LiteralPath $state) {
    $record = Get-Content -Raw -LiteralPath $state | ConvertFrom-Json
    $p = Get-Process -Id $record.pid -ErrorAction SilentlyContinue
    if ($p -and $p.StartTime.ToUniversalTime().Ticks -eq ([datetime]$record.started).ToUniversalTime().Ticks) { $owned = $p }
}
if ($Action -eq 'stop') {
    if ($owned) {
        if (-not (Test-LocalServer -Shutdown)) { throw 'Could not verify and stop owned MySQL.' }
        if (-not $owned.WaitForExit(20000)) { throw 'MySQL is still stopping.' }
    }
    return
}
if ($owned) {
    if (-not (Test-LocalServer)) { throw 'Recorded process does not match the public database instance.' }
    if (Test-Path -LiteralPath $init) { Remove-Item -LiteralPath $init }
    Write-Host 'Public-data MySQL already running on 127.0.0.1:3308'; return
}
if (-not (Test-Path -LiteralPath $exe)) { throw 'Pass -MySQLHome pointing to a MySQL 8+ installation.' }
if (Get-NetTCPConnection -LocalPort 3308 -State Listen -ErrorAction SilentlyContinue) { throw 'Port 3308 already occupied by another service.' }
New-Item -ItemType Directory -Path $data -Force | Out-Null
if (-not (Test-Path -LiteralPath (Join-Path $data 'auto.cnf'))) {
    Push-Location $data
    try {
        & $exe --no-defaults --initialize-insecure "--basedir=$MySQLHome" --datadir=. --log-error=initialize.err
        if ($LASTEXITCODE -ne 0) { throw 'MySQL initialization failed.' }
    } finally { Pop-Location }
}
if (-not (Test-Path -LiteralPath $secret)) {
    $password = [Guid]::NewGuid().ToString('N') + [Guid]::NewGuid().ToString('N')
    Set-Content -LiteralPath $secret -Encoding ascii -NoNewline -Value $password
}
# The local instance owns this password. Reapplying it also recovers an interrupted first start.
$password = (Get-Content -Raw -LiteralPath $secret).Trim()
if ($password -notmatch '^[a-f0-9]{64}$') { throw 'Invalid project MySQL credential file.' }
Set-Content -LiteralPath $init -Encoding ascii -Value "ALTER USER 'root'@'localhost' IDENTIFIED BY '$password';"
$p = Start-Process -FilePath $exe -ArgumentList @('--no-defaults',('--basedir="'+$MySQLHome+'"'),'--datadir=.','--port=3308','--bind-address=127.0.0.1','--mysqlx=OFF','--log-error=server.err','--init-file=first-launch.sql') -WorkingDirectory $data -WindowStyle Hidden -PassThru
@{ pid=$p.Id; started=$p.StartTime.ToUniversalTime().ToString('O') } | ConvertTo-Json | Set-Content -LiteralPath $state
for ($i=0; $i -lt 40; $i++) {
    if ($p.HasExited) { throw 'MySQL failed to start. See .runtime/mysql-real/server.err.' }
    if (Test-LocalServer) {
        Remove-Item -LiteralPath $init
        Write-Host 'Public-data MySQL listening on 127.0.0.1:3308'
        return
    }
    Start-Sleep -Milliseconds 300
}
throw 'Timed out waiting for project MySQL.'
