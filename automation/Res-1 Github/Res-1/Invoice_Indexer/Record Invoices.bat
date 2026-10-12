@echo off
REM ===============================================================
REM  RECORD INVOICES - types the spreadsheet into Bottomline.
REM
REM  Menu:
REM    1) Dry run            - shows what WOULD be entered. 100%% safe.
REM    2) Fill invoices      - the REAL run. Opens Bottomline.
REM    3) Resume from a row  - real run, starting partway down the list.
REM    4) Rehearse filling   - offline walk-through of the fill order.
REM    5) Test the navigator - offline self-tests.
REM    6) Show fields        - look-only; prints a screen's field names.
REM    7) Re-record fields   - recapture selectors when Bottomline changes.
REM
REM  The real run NEVER presses Save or Convert to Invoice. It fills
REM  the boxes and STOPS - you check the work and press the buttons.
REM  Close invoices.xlsx before a real run (it stamps rows DONE).
REM ===============================================================

setlocal
cd /d "%~dp0"
title Invoice Indexer - Record Invoices

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
echo   RECORD INVOICES
echo  ================================================================
echo.
echo    -- everyday --
echo    1) Dry run             (safe preview, nothing typed)
echo    2) Fill invoices       (REAL - opens Bottomline)
echo    3) Resume from a row   (REAL - start partway down)
echo.
echo    -- checks (offline, safe) --
echo    4) Rehearse the filling
echo    5) Test the navigator
echo.
echo    -- diagnostics (only when a box cannot be found) --
echo    6) Show fields on a page
echo    7) Re-record Bottomline fields
echo.
set "PICK="
set /p PICK=Choose a number (or close this window):
if "%PICK%"=="1" goto dryrun
if "%PICK%"=="2" goto fill
if "%PICK%"=="3" goto resume
if "%PICK%"=="4" goto rehearse
if "%PICK%"=="5" goto testnav
if "%PICK%"=="6" goto showfields
if "%PICK%"=="7" goto rerecord
echo   Not a valid choice - try again.
goto menu

:dryrun
echo.
echo   DRY RUN - nothing is typed, no browser opens.
echo.
".venv\Scripts\python.exe" "automation\invoice_recorder.py" --dry-run
goto end

:fill
call :needenv
echo.
echo   FILLING INVOICES - this types into the REAL Bottomline system.
echo   It will NOT save - you press Save / Convert yourself.
echo   Close invoices.xlsx first. Close this window now to cancel.
echo.
pause
".venv\Scripts\python.exe" "automation\invoice_recorder.py"
goto end

:resume
call :needenv
echo.
set "STARTROW="
set /p STARTROW=Resume from which row? (a number, e.g. 5):
if "%STARTROW%"=="" (
  echo   No number entered. Nothing was run.
  goto end
)
echo.
echo   Resuming from row %STARTROW%. NOTE: this is the position in the
echo   FILLED rows, not the Excel line number. Blank rows are not counted.
echo   Close invoices.xlsx first. Close this window now to cancel.
pause
".venv\Scripts\python.exe" "automation\invoice_recorder.py" --start-row %STARTROW%
goto end

:rehearse
echo.
echo   REHEARSAL - offline. Walks the fill order through a PRETEND
echo   Bottomline. Nothing connects, nothing is typed for real.
echo.
".venv\Scripts\python.exe" "automation\rehearse_fill.py"
goto end

:testnav
echo.
echo   OFFLINE TESTS - navigator logic. No browser, no Bottomline.
echo.
".venv\Scripts\python.exe" "automation\selftest_queue.py"
echo.
echo   Look for "OK" above. Anything else means something is broken.
goto end

:showfields
call :needenv
echo.
echo   SHOW FIELDS - look only. Opens Bottomline; you navigate to a
echo   screen and press ENTER; it prints every box's internal name.
echo   It never types, clicks or saves. Result saved under logs\.
echo.
".venv\Scripts\python.exe" "automation\page_probe.py"
goto end

:rerecord
echo.
echo   RE-RECORD FIELDS - use only when the real run reports it cannot
echo   find a box (Bottomline changed its screen).
echo   Paste your Bottomline web address, then press Enter.
echo   Example:  https://something.nexuspayables.com/login.php
echo.
set "SITEURL="
set /p SITEURL=Web address:
if "%SITEURL%"=="" (
  echo   No address entered. Nothing was run.
  goto end
)
".venv\Scripts\python.exe" "automation\selector_recorder.py" "%SITEURL%"
echo.
echo   The raw capture is  automation\selectors_recorded.json  - that is
echo   NOT the field map. Someone must read it and update
echo   automation\selectors.json by hand. See README.md.
goto end

:needenv
if not exist ".env" (
  echo.
  echo   PROBLEM: the .env file is missing.
  echo   Create a file called  .env  in this folder with these lines:
  echo       BOTTOMLINE_URL=
  echo       BOTTOMLINE_USERNAME=
  echo       BOTTOMLINE_PASSWORD=
  echo   No quotes. No spaces around the = sign. Never send this file.
  echo.
  pause
  exit /b 1
)
goto :eof

:end
echo.
echo  ================================================================
echo   Finished. Check the log file in the logs folder.
echo  ================================================================
echo.
pause
