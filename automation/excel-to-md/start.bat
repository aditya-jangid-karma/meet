@echo off
echo ==============================================
echo  Document to Markdown Converter Starting...
echo ==============================================
echo.
echo Launching Web Server...
echo The interface will open in your browser automatically.
echo Please do not close this black window while using the converter.
echo.

:: Start the browser
start http://127.0.0.1:5000/

:: Start the Flask app
python app.py

pause
