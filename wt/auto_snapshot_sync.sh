#!/usr/bin/env bash
# 快照热交换看门狗 (单轮, 由任务计划每 30 分钟调用) — 曼波 10-30 定: 大批量快照转储
# 走 NAS 中转+终点, 免授权: 目录静置 30min → rsync 推 NAS → 双端核数 → 通过即清本地
# 安全: 核验不过绝不清; 只处理"子目录单元"; 根级散文件不动; 全程日志
set -u
NAS="qianli@192.168.31.153"
SSH="ssh -p 2222"
VAULT="/mnt/nas_data/公用/windtunnel-vault"
LOG=/mnt/d/WindTunnelSuite/wt/hotswap.log
IDLE_MIN=${IDLE_MIN:-30}
echo "--- hotswap round $(date +%m-%d\ %H:%M) ---" >> "$LOG"

# 配置: 本地根目录 | vault 相对路径  (子目录 = 转储单元)
PAIRS=(
  "/mnt/d/WindTunnelSuite/WindTunnel3D/fluidx3d/vtk|runs/windtunnel3d-vtk"
  "/mnt/d/WindTunnelSuite/renders|archive/renders"
  "/mnt/d/WindTunnelSuite/FanSim3D/fluidx3d/vtk_smoke|archive/fansim3d-vtk_smoke"
)

for item in "${PAIRS[@]}"; do
  ROOT="${item%%|*}"; REL="${item##*|}"
  [ -d "$ROOT" ] || continue
  for d in "$ROOT"/*/; do
    [ -d "$d" ] || continue
    name=$(basename "$d")
    [ -n "$(find "$d" -newermt "-${IDLE_MIN} minutes" -print -quit 2>/dev/null)" ] && continue  # 未静置
    n_src=$(find "$d" -type f 2>/dev/null | wc -l)
    [ "$n_src" -eq 0 ] && continue
    b_src=$(find "$d" -type f -printf '%s\n' 2>/dev/null | awk '{s+=$1} END{print s+0}')
    $SSH "$NAS" "mkdir -p '$VAULT/$REL/$name'"
    rsync -a --partial --info=progress2 -e "$SSH" "$d" "$NAS:$VAULT/$REL/$name/" >/dev/null 2>&1
    rc=$?
    if [ $rc -ne 0 ]; then echo "RSYNC-FAIL $REL/$name rc=$rc" >> "$LOG"; continue; fi
    remote=$($SSH "$NAS" "cd '$VAULT/$REL/$name' && find . -type f | wc -l && find . -type f -printf '%s\n' | awk '{s+=\$1} END{print s+0}'" 2>/dev/null)
    n_r=$(echo "$remote" | sed -n 1p); b_r=$(echo "$remote" | sed -n 2p)
    if [ "$n_src" = "$n_r" ] && [ "$b_src" = "$b_r" ]; then
      rm -rf "$d"
      echo "HOTSWAPPED $REL/$name: $n_r files $b_r bytes, local cleared" >> "$LOG"
    else
      echo "MISMATCH $REL/$name: src $n_src/$b_src vs nas $n_r/$b_r — 本地保留待查" >> "$LOG"
    fi
  done
done
echo "--- round end ---" >> "$LOG"
