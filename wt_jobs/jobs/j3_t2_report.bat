@echo off
chcp 65001 >nul
title J3 T2 LBM 力报告 (约1分钟)
echo ============================================
echo  J3 拉 R8b 力数据 + 折叠位对照  (跑完自动退出)
echo ============================================
cd /d "%~dp0.."
py -3 lib\t2_report.py
echo.
echo 报告: wt_jobs\out\t2_report.txt
pause
