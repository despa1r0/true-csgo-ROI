[CmdletBinding()]
param(
    [switch]$Detached
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "Docker was not found. Install and start Docker Desktop."
}

if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "Created .env. Add CSFLOAT_API_KEY and CSGOMARKET_API_KEY, then run this script again." -ForegroundColor Yellow
    exit 1
}

# Keep existing local databases usable when .env predates the POSTGRES_* fields.
# Process-level variables take precedence in Docker Compose and are not written
# back to disk or printed to the terminal.
$envLines = Get-Content ".env"
$databaseUrlLine = $envLines | Where-Object { $_ -match '^\s*DATABASE_URL\s*=\s*(.+)\s*$' } | Select-Object -First 1
$hasPostgresUser = $envLines | Where-Object { $_ -match '^\s*POSTGRES_USER\s*=\s*[^#\s].*$' }
$hasPostgresPassword = $envLines | Where-Object { $_ -match '^\s*POSTGRES_PASSWORD\s*=\s*[^#\s].*$' }
$hasPostgresDb = $envLines | Where-Object { $_ -match '^\s*POSTGRES_DB\s*=\s*[^#\s].*$' }

if ($databaseUrlLine -and (-not $hasPostgresUser -or -not $hasPostgresPassword -or -not $hasPostgresDb)) {
    $databaseUrl = ($databaseUrlLine -replace '^\s*DATABASE_URL\s*=\s*', '').Trim()
    try {
        $databaseUri = [System.Uri]$databaseUrl
        $credentials = $databaseUri.UserInfo.Split(':', 2)
        if ($credentials.Count -eq 2) {
            if (-not $hasPostgresUser) { $env:POSTGRES_USER = [System.Uri]::UnescapeDataString($credentials[0]) }
            if (-not $hasPostgresPassword) { $env:POSTGRES_PASSWORD = [System.Uri]::UnescapeDataString($credentials[1]) }
            if (-not $hasPostgresDb) { $env:POSTGRES_DB = $databaseUri.AbsolutePath.TrimStart('/') }
        }
    }
    catch {
        throw "DATABASE_URL in .env is invalid. Add POSTGRES_DB, POSTGRES_USER, and POSTGRES_PASSWORD explicitly."
    }
}

$hasCsfloatKey = Get-Content ".env" | Where-Object {
    $_ -match '^\s*CSFLOAT_API_KEY\s*=\s*[^#\s].*$'
}
if (-not $hasCsfloatKey) {
    throw "CSFLOAT_API_KEY is empty in .env."
}

$hasCsgoMarketKey = Get-Content ".env" | Where-Object {
    $_ -match '^\s*CSGOMARKET_API_KEY\s*=\s*[^#\s].*$'
}
if (-not $hasCsgoMarketKey) {
    throw "CSGOMARKET_API_KEY is empty in .env."
}

if ($Detached) {
    docker compose up --build --detach
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    Write-Host "trueROI is running: http://localhost:8005" -ForegroundColor Green
    Write-Host "Stop it with: docker compose down"
    exit 0
}

Write-Host "Open http://localhost:8005 when startup completes." -ForegroundColor Cyan
docker compose up --build
exit $LASTEXITCODE
