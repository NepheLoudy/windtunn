@echo off
rem J1 sync+audit: schtasks WT_sync every 2min, or double-click. Auto-exit, no pause.
rem 11-02: pause removed (schtasks session hangs forever on pause, IgnoreNew blocks next fires)
chcp 65001 >nul
cd /d "%~dp0.."
py -3 lib\sync_and_audit.py >> out\j1_schtasks.log 2>&1
exit /b %errorlevel%
