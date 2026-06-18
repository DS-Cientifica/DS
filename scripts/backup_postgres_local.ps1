param(
    [string]$DatabaseName = "axion_db",
    [string]$DatabaseUser = "postgres",
    [string]$DatabaseHost = "localhost",
    [int]$DatabasePort = 5432,
    [string]$BackupRoot = "$env:USERPROFILE\Backups\AXION\PostgreSQL",
    [int]$RetentionDays = 14,
    [string]$PgDumpPath = "",
    [switch]$PlainSql
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Find-PgDump {
    param([string]$PreferredPath)

    if ($PreferredPath -and (Test-Path $PreferredPath)) {
        return (Resolve-Path $PreferredPath).Path
    }

    $fromPath = Get-Command pg_dump.exe -ErrorAction SilentlyContinue
    if ($fromPath) {
        return $fromPath.Source
    }

    $candidates = Get-ChildItem "C:\Program Files\PostgreSQL" -Directory -ErrorAction SilentlyContinue |
        Sort-Object Name -Descending |
        ForEach-Object { Join-Path $_.FullName "bin\pg_dump.exe" }

    foreach ($candidate in $candidates) {
        if (Test-Path $candidate) {
            return $candidate
        }
    }

    throw "pg_dump.exe não encontrado. Informe -PgDumpPath ou instale o cliente do PostgreSQL."
}

function Ensure-Password {
    if ($env:PGPASSWORD) {
        return
    }

    $securePassword = Read-Host "Informe a senha do PostgreSQL para o backup" -AsSecureString
    $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($securePassword)
    try {
        $env:PGPASSWORD = [Runtime.InteropServices.Marshal]::PtrToStringAuto($bstr)
    }
    finally {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
    }
}

function Remove-ExpiredBackups {
    param(
        [string]$RootPath,
        [int]$DaysToKeep
    )

    if (-not (Test-Path $RootPath)) {
        return
    }

    $limitDate = (Get-Date).AddDays(-1 * $DaysToKeep)
    Get-ChildItem $RootPath -File |
        Where-Object { $_.LastWriteTime -lt $limitDate } |
        Remove-Item -Force
}

$pgDump = Find-PgDump -PreferredPath $PgDumpPath
Ensure-Password

$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$null = New-Item -ItemType Directory -Path $BackupRoot -Force

$extension = if ($PlainSql) { "sql" } else { "backup" }
$dumpFile = Join-Path $BackupRoot "$($DatabaseName)_$timestamp.$extension"
$logFile = Join-Path $BackupRoot "$($DatabaseName)_$timestamp.log"
$hashFile = "$dumpFile.sha256"

$args = @(
    "--host=$DatabaseHost"
    "--port=$DatabasePort"
    "--username=$DatabaseUser"
    "--no-password"
)

if ($PlainSql) {
    $args += @(
        "--format=plain"
        "--file=$dumpFile"
        $DatabaseName
    )
}
else {
    $args += @(
        "--format=custom"
        "--blobs"
        "--compress=9"
        "--file=$dumpFile"
        $DatabaseName
    )
}

Write-Host "Iniciando backup do banco $DatabaseName em $dumpFile"
& $pgDump @args 2>&1 | Tee-Object -FilePath $logFile

if (-not (Test-Path $dumpFile)) {
    throw "Backup não foi gerado. Verifique o log em $logFile"
}

$hash = Get-FileHash -Path $dumpFile -Algorithm SHA256
$hash.Hash | Set-Content -Path $hashFile -Encoding ASCII

Remove-ExpiredBackups -RootPath $BackupRoot -DaysToKeep $RetentionDays

Write-Host ""
Write-Host "Backup concluído com sucesso."
Write-Host "Arquivo: $dumpFile"
Write-Host "Hash SHA256: $hashFile"
Write-Host "Log: $logFile"
