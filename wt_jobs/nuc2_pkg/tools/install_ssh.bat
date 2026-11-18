@echo off
setlocal
REM ---- ASCII only. No chcp needed. Loop-proof elevation via sentinel arg. ----
if /i "%~1"=="__ELEV__" goto run
fltmc >nul 2>&1
if not errorlevel 1 goto run
echo [i] Requesting Administrator rights ...
powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath '%~f0' -ArgumentList '__ELEV__' -Verb RunAs"
exit /b
:run
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install_openssh.ps1"
echo.
echo Exit code: %errorlevel%
pause
