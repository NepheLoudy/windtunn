@echo off
chcp 65001 >nul
title J5 计划任务注册 (一次性安装: 哨兵 30min + 仪表台登录自启)
echo ============================================
echo  注册 Windows 计划任务 (需当前用户已登录)
echo    WT_qianli_guard : 每 30min 探活 qianli 三守护, 掉线自动拉回
echo    WT_dashboard    : 登录时自启本机仪表台 8123
echo ============================================
schtasks /Create /TN "WT_qianli_guard" /TR "D:\WindTunnelSuite\wt_jobs\jobs\j4_guard.bat" /SC MINUTE /MO 30 /F
schtasks /Create /TN "WT_dashboard" /TR "D:\WindTunnelSuite\wt_jobs\jobs\j2_dashboard.bat" /SC ONLOGON /F
echo.
echo -- 校验 --
schtasks /Query /TN "WT_qianli_guard" | findstr /C:"TaskName" /C:"Status" /C:"任务名" /C:"状态"
schtasks /Query /TN "WT_dashboard" | findstr /C:"TaskName" /C:"Status" /C:"任务名" /C:"状态"
echo.
echo 注意: 任务随当前用户会话运行 (本机 24h 登录态). 人工立即触发:
echo   schtasks /Run /TN "WT_qianli_guard"
pause
