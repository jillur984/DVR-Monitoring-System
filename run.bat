@echo off
title Hikvision DVR Health Monitor System
set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"

call .venv\Scripts\activate.bat

echo ========================================================
echo        HIKVISION DVR MONITOR & DASHBOARD SYSTEM
echo ========================================================
echo [1] Start Web Dashboard (Recommended - Browser UI)
echo [2] Start CLI Monitor (Terminal Dashboard)
echo [3] Start Both (Web Dashboard + Browser + CLI)
echo ========================================================
set /p choice="Select Option [1-3] (Default: 1): "

if "%choice%"=="2" goto start_cli
if "%choice%"=="3" goto start_both

:start_web
echo Starting Web Dashboard...
start "" timeout /t 2 >nul & start http://127.0.0.1:5000
python "%SCRIPT_DIR%dashboard.py"
goto end

:start_cli
echo Starting CLI Monitor...
python "%SCRIPT_DIR%monitor.py"
goto end

:start_both
echo Starting Web Dashboard and CLI Monitor...
start "DVR Web Dashboard" cmd /c "call .venv\Scripts\activate.bat && start http://127.0.0.1:5000 && python dashboard.py"
python "%SCRIPT_DIR%monitor.py"
goto end

:end
pause