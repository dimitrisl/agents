# ==============================================================================
# 🩸 Phyrexian Forge - Start Script (Windows PowerShell)
# Launches FastAPI backend on port 8000 and Angular frontend on port 4200.
# ==============================================================================

$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectDir

if (-not (Test-Path "client\node_modules") -or -not (Test-Path ".env")) {
    Write-Host "⚠️ Project is not set up yet. Running .\setup.ps1 first..." -ForegroundColor Yellow
    & "$ProjectDir\setup.ps1"
}

Write-Host "=====================================================" -ForegroundColor Cyan
Write-Host "🚀 Launching Phyrexian Forge (Windows)..." -ForegroundColor Cyan
Write-Host "   Backend:  http://localhost:8000" -ForegroundColor White
Write-Host "   Frontend: http://localhost:4200" -ForegroundColor White
Write-Host "=====================================================" -ForegroundColor Cyan

# Start FastAPI backend in a separate PowerShell window
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$ProjectDir'; Write-Host '🚀 FastAPI Backend running on http://localhost:8000' -ForegroundColor Green; poetry run uvicorn server.main:app --reload --port 8000"

Start-Sleep -Seconds 2

# Start Angular client in the current window
Set-Location "$ProjectDir\client"
Write-Host "`n💻 Starting Angular Client..." -ForegroundColor Green
npm start
