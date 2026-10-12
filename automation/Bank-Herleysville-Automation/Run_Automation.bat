@echo off
title Harleysville Bank Automation
echo =======================================================
echo       Harleysville Bank Statement Automation
echo =======================================================
echo.

:: Navigate to the directory where this .bat file is located
cd /d "%~dp0"

:: Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not added to PATH.
    echo Please install Python 3.10 or higher and check "Add Python to PATH".
    echo.
    pause
    exit /b
)

:: Run the automation script
python Automation_Updated-code_bank-herleysville.py

echo.
echo =======================================================
echo                 Execution Completed
echo =======================================================
pause
