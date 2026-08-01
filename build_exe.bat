@echo off
title Building DVR Monitor EXE...
echo ========================================================
echo        HIKVISION DVR MONITORING SYSTEM - EXE BUILDER
echo ========================================================
echo.

cd /d "%~dp0"

set PYTHON_CMD=python
if exist ".venv\Scripts\python.exe" (
    set PYTHON_CMD=.venv\Scripts\python.exe
    echo Using Virtual Environment Python: .venv\Scripts\python.exe
)

echo [1/4] Checking and installing Python dependencies...
%PYTHON_CMD% -m pip install --upgrade pip
%PYTHON_CMD% -m pip install pyinstaller requests flask cryptography

if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Failed to install required packages!
    pause
    exit /b 1
)

echo.
echo [2/4] Building DVR_Dashboard.exe (Web UI + Monitoring Engine)...
%PYTHON_CMD% -m PyInstaller --noconfirm --onefile --console ^
    --add-data "templates;templates" ^
    --name "DVR_Dashboard" ^
    dashboard.py

if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Failed to build DVR_Dashboard.exe!
    pause
    exit /b 1
)

echo.
echo [3/4] Building DVR_Monitor_CLI.exe (Console Monitor)...
%PYTHON_CMD% -m PyInstaller --noconfirm --onefile --console ^
    --name "DVR_Monitor_CLI" ^
    monitor.py

if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Failed to build DVR_Monitor_CLI.exe!
    pause
    exit /b 1
)

echo.
echo [4/4] Syncing configuration files (dvrs.json, .secret.key)...
copy /Y "dvrs.json" "dist\dvrs.json" >nul
copy /Y ".secret.key" "dist\.secret.key" >nul
if exist "telegram_config.json" (
    copy /Y "telegram_config.json" "dist\telegram_config.json" >nul
)

echo.
echo ========================================================
echo SUCCESS! Executable files built in 'dist' directory:
echo   - dist\DVR_Dashboard.exe
echo   - dist\DVR_Monitor_CLI.exe
echo ========================================================
echo.
pause
