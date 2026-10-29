#!/usr/bin/env bash
# 当前 102.4G 迁移的收尾清本机 — 热交换模式免授权 (曼波 10-30: 不需要我授权)
# 条件: migrate 日志出现 "migrate done" 且 7 项全 VERIFIED 且 0 MISMATCH/FAIL
# 动作: 删本地已 VERIFIED 的源目录, 保留代码仓
set -u
LOG=/mnt/d/WindTunnelSuite/wt/migrate_exec.log
CL=/mnt/d/WindTunnelSuite/wt/migrate_cleanup.log
while ! grep -q "migrate done" "$LOG" 2>/dev/null; do sleep 300; done
v=$(grep -c VERIFIED "$LOG" 2>/dev/null || echo 0)
bad=$(grep -cE "MISMATCH|RSYNC-FAIL" "$LOG" 2>/dev/null || echo 0)
echo "cleanup check $(date): verified=$v bad=$bad" > "$CL"
if [ "$v" -lt 7 ] || [ "$bad" -gt 0 ]; then
  echo "ABORT: 存在未验证/失败项, 本地保留, 待人工核查" >> "$CL"; exit 1
fi
declare -A SRCS=(
  ["/mnt/d/WindTunnelSuite/WindTunnel3D/fluidx3d/vtk"]=1
  ["/mnt/d/WindTunnelSuite/WindTunnel3D/fluidx3d/vtk_prev"]=1
  ["/mnt/d/WindTunnelSuite/WindTunnel3D/fluidx3d/vtk_oldmix"]=1
  ["/mnt/d/WindTunnelSuite/FanSim3D/fluidx3d/vtk_prev"]=1
  ["/mnt/d/WindTunnelSuite/FanSim3D/fluidx3d/vtk_smoke"]=1
  ["/mnt/d/WindTunnelSuite/renders/of"]=1
  ["/mnt/d/WindTunnelSuite/WindTunnel3D/flow3d_result.mat"]=1
)
for s in "${!SRCS[@]}"; do
  if [ -e "$s" ]; then
    sz=$(du -sm "$s" | cut -f1)
    rm -rf "$s"
    echo "cleared $s (${sz}M)" >> "$CL"
  fi
done
echo "local cleanup complete $(date)" >> "$CL"
