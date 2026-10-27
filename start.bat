@echo off
setlocal
cd /d "%~dp0"

echo =====================================================
echo 🩸 Starting Phyrexian Forge...
echo =====================================================

if not exist "client\node_modules\" (
    echo ⚠️ Dependencies missing. Running setup first...
    call "%~dp0setup.bat"
)

start "Phyrexian Forge - FastAPI Backend" cmd /k "cd /d "%~dp0" && poetry run uvicorn server.main:app --reload --port 8000"
timeout /t 2 /nobreak >nul

echo Starting Angular Client on http://localhost:4200...
cd "%~dp0client"
npm start
