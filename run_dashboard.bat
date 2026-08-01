@echo off
title Hikvision DVR Web Dashboard
set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"

echo ========================================================
echo       Starting Hikvision DVR Web Dashboard Server
echo ========================================================
echo.

call .venv\Scripts\activate.bat

:: Open browser automatically after 2 seconds
start "" timeout /t 2 >nul & start http://127.0.0.1:5000

python "%SCRIPT_DIR%dashboard.py"
pause
