@echo off
setlocal
cd /d "%~dp0"
echo =====================================================
echo 🩸 Launching Phyrexian Forge Windows Setup...
echo =====================================================
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup.ps1"
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ❌ Setup encountered an error.
    pause
    exit /b %ERRORLEVEL%
)
echo.
echo Press any key to exit...
pause >nul
