param(
    [Parameter(Mandatory = $true)]
    [string]$BackupRoot,
    [string]$ProjectPath = (Split-Path -Parent $PSScriptRoot)
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

foreach ($name in "DJANGO_DB_NAME", "DJANGO_DB_USER", "DJANGO_DB_PASSWORD", "DJANGO_DB_HOST", "DJANGO_DB_PORT") {
    if (-not [Environment]::GetEnvironmentVariable($name)) {
        throw "The $name environment variable is required."
    }
}

$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$destination = Join-Path $BackupRoot $timestamp
New-Item -ItemType Directory -Force -Path $destination | Out-Null

$env:PGPASSWORD = [Environment]::GetEnvironmentVariable("DJANGO_DB_PASSWORD")
& pg_dump --format=custom --file=(Join-Path $destination "database.dump") --host=$env:DJANGO_DB_HOST --port=$env:DJANGO_DB_PORT --username=$env:DJANGO_DB_USER $env:DJANGO_DB_NAME
if ($LASTEXITCODE -ne 0) {
    throw "PostgreSQL backup failed."
}

$mediaPath = Join-Path $ProjectPath "media"
if (Test-Path -LiteralPath $mediaPath) {
    Compress-Archive -Path (Join-Path $mediaPath "*") -DestinationPath (Join-Path $destination "media.zip") -Force
}

Get-FileHash (Join-Path $destination "database.dump") -Algorithm SHA256 |
    Select-Object Algorithm, Hash, Path |
    ConvertTo-Json |
    Set-Content -Path (Join-Path $destination "checksums.json") -Encoding utf8

Write-Output "Backup completed: $destination"
