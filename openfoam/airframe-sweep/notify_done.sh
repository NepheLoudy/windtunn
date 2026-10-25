#!/usr/bin/env bash
# 扫气完成 → Windows toast 弹窗提醒 (WSL interop)
#   usage: notify_done.sh <标题> <内容>
# 失败静默 — 不影响扫气结果本身
TITLE="${1:?usage: notify_done.sh <title> <body>}"
BODY="${2:?usage: notify_done.sh <title> <body>}"
echo "[notify] $TITLE | $BODY"
PS1W="/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe"
PS_EXE="$PS1W"
[ -x "$PS_EXE" ] || PS_EXE="powershell.exe"
"$PS_EXE" -NoProfile -ExecutionPolicy Bypass -File \
  "D:\\WindTunnelSuite\\openfoam\\airframe-sweep\\notify.ps1" \
  -Title "$TITLE" -Body "$BODY" >/dev/null 2>&1 || true
