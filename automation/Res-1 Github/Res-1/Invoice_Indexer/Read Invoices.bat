@echo off
REM ===============================================================
REM  READ INVOICES - Qwen reads the PDFs and fills the spreadsheet.
REM
REM  Menu:
REM    1) Read for real   - Qwen reads each NEW PDF and writes a row.
REM    2) Preview         - shows which PDFs are new. No Qwen, nothing written.
REM    3) Test the reader - offline self-tests (no Qwen, no live sheet).
REM
REM  HOW IT DECIDES WHAT IS NEW: a PDF is matched to the sheet by its
REM  FILE NAME (the Image Name column) - NOT by the invoice number or
REM  any amount. A PDF whose file name is already in the sheet is
REM  skipped; only file names not yet in the sheet are read as new.
REM  So editing the invoice number/vendor/amount in Excel afterwards
REM  does NOT make a PDF look new again - only the file name matters.
REM
REM  Keep invoices.xlsx CLOSED during a real read.
REM ===============================================================

setlocal
cd /d "%~dp0"
title Invoice Indexer - Read Invoices

REM  Poppler (renders each PDF page to an image for Qwen). First choice:
REM  use whatever Poppler is already on this PC's PATH (works for anyone
REM  who installed it via winget/choco/manual PATH edit). If nothing is
REM  found on PATH, fall back to the folder below -- edit that one line
REM  if your own install lives somewhere else.
where pdftoppm.exe >nul 2>nul
if %ERRORLEVEL%==0 (
  set "POPPLER="
) else (
  set "POPPLER=C:\Users\Meet Patel\AppData\Local\Microsoft\WinGet\Packages\oschwartz10612.Poppler_Microsoft.Winget.Source_8wekyb3d8bbwe\poppler-25.07.0\Library\bin"
)

if not exist ".venv\Scripts\python.exe" (
  echo.
  echo   PROBLEM: the virtual environment is missing.
  echo   The project has not been set up on this PC yet.
  echo   See README.md, "Setting up on a new PC".
  echo.
  pause
  exit /b 1
)

:menu
echo.
echo  ================================================================
echo   READ INVOICES
echo  ================================================================
echo.
echo    -- Standard Invoices --
echo    1) Read for real           (Qwen reads new PDFs, writes rows)
echo    2) Preview only            (shows which PDFs are new, writes nothing)
echo.
echo    -- Utility Bills (Pepco, Gas, Water) --
echo    3) Read Utility Bills      (runs with --utility mode)
echo    4) Preview Utility Bills   (offline preview for utility mode)
echo.
echo    -- Diagnostic --
echo    5) Test the reader         (offline self-tests)
echo.
set "PICK="
set /p PICK=Choose a number (or close this window):
if "%PICK%"=="1" goto real
if "%PICK%"=="2" goto preview
if "%PICK%"=="3" goto real_utility
if "%PICK%"=="4" goto preview_utility
if "%PICK%"=="5" goto test
echo   Not a valid choice - try again.
goto menu

:real
echo.
echo   Enter the Mac's Ollama address (the machine running Qwen).
echo   Example:  http://192.168.1.42:11434
echo.
set "HOSTADDR="
set /p HOSTADDR=Mac address:
if "%HOSTADDR%"=="" (
  echo   No address entered. Nothing was run.
  goto end
)
echo.
echo   Make sure invoices.xlsx is CLOSED before continuing.
pause
".venv\Scripts\python.exe" "automation\invoice_reader.py" --host "%HOSTADDR%" --poppler-path "%POPPLER%"
goto end

:real_utility
echo.
echo   Enter the Mac's Ollama address (the machine running Qwen).
echo   Example:  http://192.168.1.42:11434
echo.
set "HOSTADDR="
set /p HOSTADDR=Mac address:
if "%HOSTADDR%"=="" (
  echo   No address entered. Nothing was run.
  goto end
)
echo.
echo   Make sure invoices.xlsx is CLOSED before continuing.
pause
".venv\Scripts\python.exe" "automation\invoice_reader.py" --utility --host "%HOSTADDR%" --poppler-path "%POPPLER%"
goto end

:preview
echo.
echo   PREVIEW - no Qwen, nothing written. Lists the PDFs and marks
echo   which ones are already recorded (would be skipped).
echo.
".venv\Scripts\python.exe" "automation\invoice_reader.py" --dry-run --poppler-path "%POPPLER%"
goto end

:preview_utility
echo.
echo   UTILITY PREVIEW - shows unread utility bills with crosswalk.
echo.
".venv\Scripts\python.exe" "automation\invoice_reader.py" --utility --dry-run --poppler-path "%POPPLER%"
goto end

:test
echo.
echo   OFFLINE TESTS - no Qwen, no browser, no live sheet.
echo.
".venv\Scripts\python.exe" "automation\selftest_reader.py"
echo.
echo   Look for "OK" above. Anything else means something is broken.
goto end

:end
echo.
echo  ================================================================
echo   Finished.
echo  ================================================================
echo.
pause
