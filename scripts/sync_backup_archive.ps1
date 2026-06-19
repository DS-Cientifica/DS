param(
    [string]$SourceRoot = "$env:USERPROFILE\Backups\AXION\PostgreSQL",
    [string]$TargetRoot = "",
    [int]$RetentionDays = 30
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Get-DefaultTargetRoot {
    $candidates = @(
        (Join-Path $env:USERPROFILE "OneDrive\Backups\AXION\PostgreSQL"),
        (Join-Path $env:USERPROFILE "Google Drive\Backups\AXION\PostgreSQL"),
        (Join-Path $env:USERPROFILE "Dropbox\Backups\AXION\PostgreSQL")
    )

    foreach ($candidate in $candidates) {
        $parent = Split-Path $candidate -Parent
        if (Test-Path $parent) {
            return $candidate
        }
    }

    throw "Nenhum diretório de nuvem padrão encontrado. Informe -TargetRoot manualmente."
}

function Remove-ExpiredFiles {
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

if (-not $TargetRoot) {
    $TargetRoot = Get-DefaultTargetRoot
}

if (-not (Test-Path $SourceRoot)) {
    throw "Diretório de origem não encontrado: $SourceRoot"
}

$null = New-Item -ItemType Directory -Path $TargetRoot -Force

$copied = 0
$skipped = 0

Get-ChildItem $SourceRoot -File | ForEach-Object {
    $sourceFile = $_.FullName
    $targetFile = Join-Path $TargetRoot $_.Name

    if (Test-Path $targetFile) {
        $sourceHash = (Get-FileHash $sourceFile -Algorithm SHA256).Hash
        $targetHash = (Get-FileHash $targetFile -Algorithm SHA256).Hash
        if ($sourceHash -eq $targetHash) {
            $skipped += 1
            return
        }
    }

    Copy-Item -Path $sourceFile -Destination $targetFile -Force
    $copied += 1
}

Remove-ExpiredFiles -RootPath $TargetRoot -DaysToKeep $RetentionDays

Write-Host "Sincronização concluída."
Write-Host "Origem: $SourceRoot"
Write-Host "Destino: $TargetRoot"
Write-Host "Arquivos copiados: $copied"
Write-Host "Arquivos ignorados: $skipped"
