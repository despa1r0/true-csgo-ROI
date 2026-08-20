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
    Write-Host "Created .env. Add CSFLOAT_API_KEY and run this script again." -ForegroundColor Yellow
    exit 1
}

$hasCsfloatKey = Get-Content ".env" | Where-Object {
    $_ -match '^\s*CSFLOAT_API_KEY\s*=\s*[^#\s].*$'
}
if (-not $hasCsfloatKey) {
    throw "CSFLOAT_API_KEY is empty in .env."
}

if ($Detached) {
    docker compose up --build --detach
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    Write-Host "trueROI is running: http://localhost:8000" -ForegroundColor Green
    Write-Host "Stop it with: docker compose down"
    exit 0
}

Write-Host "Open http://localhost:8000 when startup completes." -ForegroundColor Cyan
docker compose up --build
exit $LASTEXITCODE
