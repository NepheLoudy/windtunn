#!/usr/bin/env bash
# 风洞数据 → 旧NAS vault 大迁移 (曼波 10-30: 全部迁 NAS, 102.4G)
# 传输: rsync over ssh (2222), --partial 可断点, 逐项 MANIFEST + 完成标记
# 迁完本地不删 — 验证通过后由曼波确认再清 (wt 铁律: 校验放心后清本地)
set -u
NAS="qianli@192.168.31.153"
SSH="ssh -p 2222"
VAULT="/mnt/nas_data/公用/windtunnel-vault"
LOG=/mnt/d/WindTunnelSuite/wt/migrate_exec.log
echo "migrate start $(date)" >> "$LOG"

# 逐项: 源路径 | vault 相对路径
ITEMS=(
  "/mnt/d/WindTunnelSuite/WindTunnel3D/fluidx3d/vtk|runs/windtunnel3d-vtk"
  "/mnt/d/WindTunnelSuite/WindTunnel3D/fluidx3d/vtk_prev|archive/windtunnel3d-vtk_prev"
  "/mnt/d/WindTunnelSuite/WindTunnel3D/fluidx3d/vtk_oldmix|archive/windtunnel3d-vtk_oldmix"
  "/mnt/d/WindTunnelSuite/FanSim3D/fluidx3d/vtk_prev|archive/fansim3d-vtk_prev"
  "/mnt/d/WindTunnelSuite/FanSim3D/fluidx3d/vtk_smoke|archive/fansim3d-vtk_smoke"
  "/mnt/d/WindTunnelSuite/renders/of|archive/renders-of"
  "/mnt/d/WindTunnelSuite/WindTunnel3D/flow3d_result.mat|archive/flow3d_result.mat"
)

for item in "${ITEMS[@]}"; do
  SRC="${item%%|*}"; REL="${item##*|}"
  MARKER="$SRC/.migrated_to_nas"
  if [ -f "$MARKER" ]; then echo "skip (done) $REL" >> "$LOG"; continue; fi
  echo "=== rsync $REL $(date +%H:%M:%S) ===" >> "$LOG"
  # MANIFEST: 文件数 + 字节总数 (源侧)
  n_src=$(find "$SRC" -type f 2>/dev/null | wc -l)
  b_src=$(find "$SRC" -type f -printf '%s\n' 2>/dev/null | awk '{s+=$1} END{print s+0}')
  echo "$n_src files, $b_src bytes" >> "$LOG"
  $SSH "$NAS" "mkdir -p '$VAULT/$(dirname "$REL")'"
  rsync -a --partial --info=progress2 -e "$SSH" "$SRC/" \
    "$NAS:$VAULT/$REL/" >> "$LOG" 2>&1
  rc=$?
  if [ $rc -eq 0 ]; then
    # 远端核数: 文件数 + 字节
    remote=$($SSH "$NAS" "cd '$VAULT/$REL' && find . -type f | wc -l && find . -type f -printf '%s\n' | awk '{s+=\$1} END{print s+0}'" 2>/dev/null)
    n_r=$(echo "$remote" | sed -n 1p); b_r=$(echo "$remote" | sed -n 2p)
    if [ "$n_src" = "$n_r" ] && [ "$b_src" = "$b_r" ]; then
      touch "$MARKER"
      echo "VERIFIED $REL: $n_r files, $b_r bytes" >> "$LOG"
    else
      echo "MISMATCH $REL: src $n_src/$b_src vs nas $n_r/$b_r" >> "$LOG"
    fi
  else
    echo "RSYNC-FAIL rc=$rc $REL" >> "$LOG"
  fi
done
echo "migrate done $(date)" >> "$LOG"
