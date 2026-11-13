@echo off
chcp 65001 >nul
title J2 仪表台 http://127.0.0.1:8123  (随用随开, 空闲30min自动退)
rem 2026-11-07 曼波定: WT_dashboard 任务已禁用, 本脚本=手动开启器 (幂等)
rem no-paren-block: cmd+chcp65001+UTF-8 block parse aborts silently on this box
cd /d "%~dp0.."
netstat -ano | findstr ":8123" | findstr "LISTENING" >nul 2>&1
if not errorlevel 1 goto open
wscript.exe "jobs\j2_serve-hidden.vbs"
timeout /t 2 /nobreak >nul
:open
start "" http://127.0.0.1:8123
exit /b 0
