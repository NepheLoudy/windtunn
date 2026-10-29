@echo off
chcp 65001 >nul
title J1 同步+审计 (一次执行约2-5分钟)
echo ============================================
echo  J1 拉表+六锚审计+仪表台数据  (跑完自动退出)
echo ============================================
cd /d "%~dp0.."
py -3 lib\sync_and_audit.py
echo.
echo 报告: wt_jobs\out\audit_report.txt
pause
