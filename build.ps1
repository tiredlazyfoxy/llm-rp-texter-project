param(
    [switch]$Images,
    [switch]$Config
)

$ErrorActionPreference = "Stop"

# Default: --all (both images and config)
if (-not $Images -and -not $Config) {
    $Images = $true
    $Config = $true
}

# Get version from latest git tag
$version = git describe --tags --abbrev=0 2>$null
if (-not $version) {
    Write-Error "No git tags found. Create one with: git tag v0.0.1"
    exit 1
}

Write-Host "Building version: $version" -ForegroundColor Cyan

# Validate DOCKER_STORE
if (-not $env:DOCKER_STORE) {
    Write-Error "DOCKER_STORE environment variable is not set"
    exit 1
}
if (-not (Test-Path $env:DOCKER_STORE)) {
    Write-Error "DOCKER_STORE path does not exist: $env:DOCKER_STORE"
    exit 1
}

$outputDir = Join-Path $env:DOCKER_STORE "llmrp"
if (-not (Test-Path $outputDir)) {
    New-Item -ItemType Directory -Path $outputDir | Out-Null
}

if ($Images) {
    # Build API image
    Write-Host "`nBuilding llmrp-api..." -ForegroundColor Yellow
    docker build -f backend/Dockerfile `
        -t "iezious/llmrp-api:$version" `
        -t "iezious/llmrp-api:latest" `
        .
    if ($LASTEXITCODE -ne 0) { Write-Error "API image build failed"; exit 1 }

    # Build Gate image
    Write-Host "`nBuilding llmrp-gate..." -ForegroundColor Yellow
    docker build -f frontend/Dockerfile `
        -t "iezious/llmrp-gate:$version" `
        -t "iezious/llmrp-gate:latest" `
        .
    if ($LASTEXITCODE -ne 0) { Write-Error "Gate image build failed"; exit 1 }

    # Save and compress to local temp files, then move to DOCKER_STORE
    $tempDir = Join-Path $env:TEMP "llmrp-build"
    if (Test-Path $tempDir) { Remove-Item $tempDir -Recurse -Force }
    New-Item -ItemType Directory -Path $tempDir | Out-Null

    try {
        Write-Host "`nSaving llmrp-api to 7z..." -ForegroundColor Yellow
        $apiTemp = Join-Path $tempDir "llmrp-api-latest.7z"
        docker save "iezious/llmrp-api:latest" | 7z a -si "$apiTemp"
        if ($LASTEXITCODE -ne 0) { Write-Error "API image save failed"; exit 1 }

        Write-Host "`nSaving llmrp-gate to 7z..." -ForegroundColor Yellow
        $gateTemp = Join-Path $tempDir "llmrp-gate-latest.7z"
        docker save "iezious/llmrp-gate:latest" | 7z a -si "$gateTemp"
        if ($LASTEXITCODE -ne 0) { Write-Error "Gate image save failed"; exit 1 }

        Write-Host "`nMoving files to $outputDir..." -ForegroundColor Yellow
        Move-Item $apiTemp -Destination $outputDir -Force
        Move-Item $gateTemp -Destination $outputDir -Force

        Write-Host "  API:  $outputDir\llmrp-api-latest.7z" -ForegroundColor Green
        Write-Host "  Gate: $outputDir\llmrp-gate-latest.7z" -ForegroundColor Green
    } finally {
        if (Test-Path $tempDir) { Remove-Item $tempDir -Recurse -Force }
    }
}

if ($Config) {
    Copy-Item "docker-compose.prod.yml" -Destination (Join-Path $outputDir "docker-compose.yml") -Force
    Write-Host "  Compose: $outputDir\docker-compose.yml" -ForegroundColor Green
}

Write-Host "`nBuild complete!" -ForegroundColor Green
