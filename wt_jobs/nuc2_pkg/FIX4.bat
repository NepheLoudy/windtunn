@echo off
setlocal
if /i "%~1"=="__ELEV__" goto run
fltmc >nul 2>&1
if not errorlevel 1 goto run
echo.
echo   [i] Asking for Administrator rights ... click YES.
echo.
powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath '%~f0' -ArgumentList '__ELEV__' -Verb RunAs" 2>nul
if errorlevel 1 (
    echo   [X] Elevation refused. Right-click this file -^> "Run as administrator"
    echo.
    timeout /t 10
)
exit /b
:run
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0fix4.ps1"
echo.
echo   report: %~dp0fix4.txt
echo.
pause
