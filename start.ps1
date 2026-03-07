param(
    [Alias("app", "api")]
    [switch]$Backend,

    [Alias("ui", "web")]
    [switch]$Frontend
)

if (-not $Backend -and -not $Frontend) {
    Write-Host "Usage: .\start.ps1 -app | -ui"
    Write-Host "  -app, --app, -api, --api   Start backend (uvicorn, port 8085)"
    Write-Host "  -ui,  --ui,  -web, --web   Start frontend (vite, port 8094)"
    exit 1
}

if ($Backend) {
    Write-Host "Starting backend on :8085 ..."
    Push-Location "$PSScriptRoot\backend"
    & .venv\Scripts\uvicorn app.main:app --port 8085 --reload
    Pop-Location
}

if ($Frontend) {
    Write-Host "Starting frontend on :8094 ..."
    Push-Location "$PSScriptRoot\frontend"
    & npx vite --port 8094
    Pop-Location
}
