param(
    [string]$DatabaseName = "axion_db",
    [string]$DatabaseUser = "postgres",
    [string]$DatabaseHost = "localhost",
    [int]$DatabasePort = 5432,
    [string]$BackupRoot = "$env:USERPROFILE\Backups\AXION\PostgreSQL",
    [int]$RetentionDays = 14,
    [string]$PgDumpPath = "",
    [switch]$PlainSql,
    [long]$MinimumBackupSizeBytes = 10240
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

    throw "pg_dump.exe nao encontrado. Informe -PgDumpPath ou instale o cliente do PostgreSQL."
}

function Find-PgRestore {
    param([string]$PgDumpExecutable)

    $sameFolder = Join-Path (Split-Path -Parent $PgDumpExecutable) "pg_restore.exe"
    if (Test-Path $sameFolder) {
        return (Resolve-Path $sameFolder).Path
    }

    $fromPath = Get-Command pg_restore.exe -ErrorAction SilentlyContinue
    if ($fromPath) {
        return $fromPath.Source
    }

    throw "pg_restore.exe nao encontrado. A validacao do backup nao pode ser executada."
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

function Write-LogLine {
    param(
        [string]$Message,
        [string]$LogPath
    )

    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    "[$timestamp] $Message" | Add-Content -Path $LogPath -Encoding UTF8
}

function Validate-CustomBackup {
    param(
        [string]$PgRestoreExecutable,
        [string]$BackupFile,
        [string]$LogPath
    )

    Write-LogLine -Message "Validando backup custom com pg_restore -l" -LogPath $LogPath
    $restoreOutput = & $PgRestoreExecutable -l $BackupFile 2>&1
    $restoreOutput | Add-Content -Path $LogPath -Encoding UTF8

    if ($LASTEXITCODE -ne 0) {
        throw "Falha na validacao do backup custom. Verifique o log em $LogPath"
    }
}

$pgDump = Find-PgDump -PreferredPath $PgDumpPath
$pgRestore = if (-not $PlainSql) { Find-PgRestore -PgDumpExecutable $pgDump } else { $null }
Ensure-Password

$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$null = New-Item -ItemType Directory -Path $BackupRoot -Force

$extension = if ($PlainSql) { "sql" } else { "backup" }
$dumpFile = Join-Path $BackupRoot "$($DatabaseName)_$timestamp.$extension"
$logFile = Join-Path $BackupRoot "$($DatabaseName)_$timestamp.log"
$hashFile = "$dumpFile.sha256"

Set-Content -Path $logFile -Value "" -Encoding UTF8
Write-LogLine -Message "Iniciando backup do banco $DatabaseName" -LogPath $logFile
Write-LogLine -Message "Destino: $dumpFile" -LogPath $logFile
Write-LogLine -Message "Executavel pg_dump: $pgDump" -LogPath $logFile

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
$dumpOutput = & $pgDump @args 2>&1
$dumpOutput | Add-Content -Path $logFile -Encoding UTF8

if ($LASTEXITCODE -ne 0) {
    throw "pg_dump retornou codigo $LASTEXITCODE. Verifique o log em $logFile"
}

if (-not (Test-Path $dumpFile)) {
    throw "Backup nao foi gerado. Verifique o log em $logFile"
}

$dumpInfo = Get-Item $dumpFile
Write-LogLine -Message "Arquivo gerado com $($dumpInfo.Length) bytes" -LogPath $logFile

if ($dumpInfo.Length -lt $MinimumBackupSizeBytes) {
    throw "Backup gerado com tamanho suspeito ($($dumpInfo.Length) bytes). Verifique o log em $logFile"
}

if (-not $PlainSql) {
    Validate-CustomBackup -PgRestoreExecutable $pgRestore -BackupFile $dumpFile -LogPath $logFile
}

$hash = Get-FileHash -Path $dumpFile -Algorithm SHA256
$hash.Hash | Set-Content -Path $hashFile -Encoding ASCII
Write-LogLine -Message "Hash SHA256 gerado em $hashFile" -LogPath $logFile

Remove-ExpiredBackups -RootPath $BackupRoot -DaysToKeep $RetentionDays
Write-LogLine -Message "Rotina concluida com sucesso" -LogPath $logFile

Write-Host ""
Write-Host "Backup concluido com sucesso."
Write-Host "Arquivo: $dumpFile"
Write-Host "Hash SHA256: $hashFile"
Write-Host "Log: $logFile"
