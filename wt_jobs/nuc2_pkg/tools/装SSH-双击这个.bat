@echo off
chcp 65001 >nul
cd /d "%~dp0"
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo [提权] 正在以管理员身份重新启动...
    powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install_openssh_oneclick.ps1"
