# ==============================================================================
# 🩸 Phyrexian Forge - One-Click Setup Script (Windows PowerShell)
# ==============================================================================

$ErrorActionPreference = "Stop"

Write-Host "=====================================================" -ForegroundColor Cyan
Write-Host "🩸 Phyrexian Forge - Windows Setup (PowerShell)" -ForegroundColor Cyan
Write-Host "=====================================================" -ForegroundColor Cyan

$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectDir

# 1. Check Python
Write-Host "`n[1/6] Checking Python installation..." -ForegroundColor Yellow
$PythonCmd = $null
if (Get-Command python -ErrorAction SilentlyContinue) {
    $PythonCmd = "python"
} elseif (Get-Command py -ErrorAction SilentlyContinue) {
    $PythonCmd = "py -3"
} else {
    Write-Host "❌ Error: Python is not found in PATH." -ForegroundColor Red
    Write-Host "Please install Python 3.11 - 3.13 from https://www.python.org/downloads/windows/"
    Write-Host "Ensure you check 'Add python.exe to PATH' during installation."
    Exit 1
}

$PyVersion = Invoke-Expression "$PythonCmd --version"
Write-Host "✓ Found $PyVersion" -ForegroundColor Green

# 2. Check Poetry
Write-Host "`n[2/6] Checking Poetry package manager..." -ForegroundColor Yellow
if (-not (Get-Command poetry -ErrorAction SilentlyContinue)) {
    Write-Host "⚠️ Poetry is not found in PATH." -ForegroundColor Yellow
    Write-Host "Installing Poetry via official PowerShell script..."
    (Invoke-WebRequest -Uri https://install.python-poetry.org -UseBasicParsing).Content | Invoke-Expression

    $UserPath = [System.Environment]::GetEnvironmentVariable("Path", "User")
    $PoetryBin = "$env:APPDATA\Python\Scripts"
    if ($UserPath -notlike "*$PoetryBin*") {
        $env:Path = "$PoetryBin;$env:Path"
    }

    if (-not (Get-Command poetry -ErrorAction SilentlyContinue)) {
        Write-Host "❌ Poetry installed but not detected in current session." -ForegroundColor Red
        Write-Host "Please restart your PowerShell terminal and run .\setup.ps1 again."
        Exit 1
    }
}
$PoetryVersion = poetry --version
Write-Host "✓ Found Poetry ($PoetryVersion)" -ForegroundColor Green

# 3. Check Node.js and npm
Write-Host "`n[3/6] Checking Node.js and npm..." -ForegroundColor Yellow
if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
    Write-Host "❌ Error: Node.js is not installed." -ForegroundColor Red
    Write-Host "Please download and install Node.js 18+ from https://nodejs.org/"
    Exit 1
}
if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
    Write-Host "❌ Error: npm is not installed." -ForegroundColor Red
    Write-Host "Please install npm from https://nodejs.org/"
    Exit 1
}
$NodeVersion = node -v
$NpmVersion = npm -v
Write-Host "✓ Found Node.js $NodeVersion and npm $NpmVersion" -ForegroundColor Green

# 4. Environment (.env) Setup
Write-Host "`n[4/6] Setting up environment configuration (.env)..." -ForegroundColor Yellow
if (-not (Test-Path ".env")) {
    if (Test-Path ".env_example") {
        Copy-Item ".env_example" ".env"
        Write-Host "✓ Created .env from .env_example" -ForegroundColor Green
    } else {
        New-Item -ItemType File -Name ".env" -Force | Out-Null
        Add-Content -Path ".env" -Value "GEMINI_API_KEY="
        Write-Host "✓ Created new .env file" -ForegroundColor Green
    }

    # Generate random secret key for JWT
    $Bytes = New-Object byte[] 32
    $Rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    $Rng.GetBytes($Bytes)
    $RandomKey = -join ($Bytes | ForEach-Object { "{0:x2}" -f $_ })
    Add-Content -Path ".env" -Value "`nJWT_SECRET_KEY=$RandomKey"
    Write-Host "ℹ️  Generated secure JWT_SECRET_KEY in .env" -ForegroundColor Cyan
} else {
    Write-Host "✓ Existing .env file found (skipping overwrite)" -ForegroundColor Green
}

# Ensure asset directories exist
New-Item -ItemType Directory -Force -Path "data\portraits" | Out-Null
New-Item -ItemType Directory -Force -Path "data\audio" | Out-Null
New-Item -ItemType Directory -Force -Path "data\modules" | Out-Null

# 5. Backend Dependencies (Poetry)
Write-Host "`n[5/6] Installing Backend Dependencies (Poetry)..." -ForegroundColor Yellow
poetry install --no-interaction
if (Test-Path ".git") {
    poetry run pre-commit install 2>$null
}
Write-Host "✓ Backend dependencies installed successfully!" -ForegroundColor Green

# 6. Frontend Dependencies (Angular)
Write-Host "`n[6/6] Installing Frontend Dependencies (npm)..." -ForegroundColor Yellow
Set-Location "$ProjectDir\client"
if (Test-Path "package-lock.json") {
    npm ci --prefer-offline --no-audit
} else {
    npm install --no-audit
}
Set-Location $ProjectDir
Write-Host "✓ Frontend dependencies installed successfully!" -ForegroundColor Green

# Check MongoDB
Write-Host "`n=====================================================" -ForegroundColor Cyan
Write-Host "🔍 Checking MongoDB service status..." -ForegroundColor Yellow
$MongoTest = Test-NetConnection -ComputerName "localhost" -Port 27017 -WarningAction SilentlyContinue
if ($MongoTest.TcpTestSucceeded) {
    Write-Host "✓ Local MongoDB is reachable on port 27017." -ForegroundColor Green
} else {
    Write-Host "⚠️  Warning: Local MongoDB on port 27017 was not detected." -ForegroundColor Yellow
    Write-Host "   Make sure MongoDB is running before starting the server:"
    Write-Host "   - Windows Service: net start MongoDB" -ForegroundColor Cyan
    Write-Host "   - Docker:          docker run -d -p 27017:27017 --name mongo mongo:latest" -ForegroundColor Cyan
    Write-Host "   - Or configure remote MONGO_URI in your .env file." -ForegroundColor Cyan
}

Write-Host "`n🎉 Windows Setup completed successfully!" -ForegroundColor Green
Write-Host "`nTo start both Backend and Frontend, run:" -ForegroundColor White
Write-Host "   .\start.ps1  (or double-click start.bat)" -ForegroundColor Cyan
Write-Host "=====================================================" -ForegroundColor Cyan
