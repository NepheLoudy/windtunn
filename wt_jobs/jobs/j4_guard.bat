@echo off
chcp 65001 >nul
title J4 qianli 哨兵 (schtasks 每 30min 触发, 幂等无常驻)
cd /d "%~dp0.."
if not exist out mkdir out
py -3 lib\qianli_guard.py >> out\guard_run.log 2>&1
exit /b %errorlevel%
