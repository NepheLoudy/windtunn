@echo off
rem NAS 一键接线 + 101G 风洞数据迁移 (2026-10-30 曼波指令: 全部迁 NAS 作数据交换)
rem 用法: 填好下面两行凭据后双击 (或告诉我凭据由能天使执行)
rem   NAS_ADDR   = \\192.168.31.40\share   (已探明, 共享名 "share")
rem   NAS_USER   = 填用户名
rem   NAS_PASS   = 填密码 (或交互输入: 去掉 /pass 参数)

set NAS_ADDR=\\192.168.31.40\share
set NAS_USER=
set NAS_PASS=

if "%NAS_USER%"=="" (
  net use Z: "%NAS_ADDR%" /persistent:yes
) else (
  net use Z: "%NAS_ADDR%" /user:%NAS_USER% "%NAS_PASS%" /persistent:yes
)
if errorlevel 1 (
  echo 挂载失败 — 检查凭据
  pause
  exit /b 1
)
echo === Z: 已挂载, 建 vault 目录 ===
mkdir Z:\windtunnel-vault 2>nul
cd /d D:\WindTunnelSuite
echo === dry-run 迁移计划 ===
bash wt/wt.sh doctor --sizes
bash wt/wt.sh migrate
echo.
echo === 确认无误后执行: bash wt/wt.sh migrate --exec ===
pause
