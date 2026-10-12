@echo off
title American Express Statement Automation
echo =======================================================
echo       American Express Statement Automation
echo =======================================================
echo.

:: Navigate to the directory where this .bat file is located
cd /d "%~dp0"

:: Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not added to PATH.
    echo Please install Python 3.10 or higher and check "Add Python to PATH" during installation.
    echo.
    pause
    exit /b
)

echo [SYSTEM] Verifying Python requirements...
pip install -r requirements.txt

echo.
echo [SYSTEM] Ensuring automation browsers are installed...
python -m playwright install chromium

echo.
echo =======================================================
echo ⚠️ WARNING: CHROME WILL BE CLOSED
echo =======================================================
echo This script is configured to force-close Google Chrome.
echo Please make sure all your browsing work is saved before 
echo you continue!
echo.
pause

echo.
echo [SYSTEM] Starting automation script...
python American-Automation-fix-date-ready_backup_1788261753.py

echo.
echo =======================================================
echo                 Execution Completed
echo =======================================================
pause
