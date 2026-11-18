@echo off
setlocal
REM ASCII only. Self-elevates once (sentinel arg prevents any loop).
if /i "%~1"=="__ELEV__" goto run
fltmc >nul 2>&1
if not errorlevel 1 goto run
echo.
echo   [i] Requesting Administrator rights ... click YES on the UAC box.
echo.
powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath '%~f0' -ArgumentList '__ELEV__' -Verb RunAs" 2>nul
if errorlevel 1 (
    echo   [X] Elevation was refused.
    echo       Right-click this file  -^>  "Run as administrator"
    echo.
    timeout /t 10
)
exit /b
:run
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup.ps1"
echo.
echo   log: %~dp0install_log.txt
echo.
pause
