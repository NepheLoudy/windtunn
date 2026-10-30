#!/usr/bin/env bash
# 迁移回执验证器 v2 — 修 awk 科学计数法误报 (printf %.0f) + 单文件项补传
# 输出: 每项 SRC/NAS 文件数+字节 整数比对 → 回执数据 nas_receipt.txt
set -u
NAS="qianli@192.168.31.153"
SSH="ssh -p 2222"
VAULT="/mnt/nas_data/公用/windtunnel-vault"
OUT=/mnt/d/WindTunnelSuite/wt/nas_receipt.txt
echo "# NAS 迁移回执验证 $(date '+%F %T')" > "$OUT"

ITEMS=(
  "/mnt/d/WindTunnelSuite/WindTunnel3D/fluidx3d/vtk|runs/windtunnel3d-vtk"
  "/mnt/d/WindTunnelSuite/WindTunnel3D/fluidx3d/vtk_prev|archive/windtunnel3d-vtk_prev"
  "/mnt/d/WindTunnelSuite/WindTunnel3D/fluidx3d/vtk_oldmix|archive/windtunnel3d-vtk_oldmix"
  "/mnt/d/WindTunnelSuite/FanSim3D/fluidx3d/vtk_prev|archive/fansim3d-vtk_prev"
  "/mnt/d/WindTunnelSuite/FanSim3D/fluidx3d/vtk_smoke|archive/fansim3d-vtk_smoke"
  "/mnt/d/WindTunnelSuite/renders/of|archive/renders-of"
)

pass=0; total=0
for item in "${ITEMS[@]}"; do
  SRC="${item%%|*}"; REL="${item##*|}"; total=$((total+1))
  if [ ! -d "$SRC" ]; then echo "$REL|SRC-GONE(已清)" >> "$OUT"; continue; fi
  n_src=$(find "$SRC" -type f -not -name .migrated_to_nas | wc -l)
  b_src=$(find "$SRC" -type f -not -name .migrated_to_nas -printf '%s\n' | awk '{s+=$1} END{printf "%.0f\n", s}')
  remote=$($SSH "$NAS" "cd '$VAULT/$REL' && find . -type f | wc -l && find . -type f -printf '%s\n' | awk '{s+=\$1} END{printf \"%.0f\\n\", s}'" 2>/dev/null)
  n_r=$(echo "$remote" | sed -n 1p); b_r=$(echo "$remote" | sed -n 2p)
  if [ "$n_src" = "$n_r" ] && [ "$b_src" = "$b_r" ]; then
    echo "$REL|PASS|files=$n_src|bytes=$b_src" >> "$OUT"; pass=$((pass+1))
    touch "$SRC/.migrated_to_nas"
  else
    echo "$REL|FAIL|src=$n_src/$b_src nas=$n_r/$b_r" >> "$OUT"
  fi
done

# 单文件项补传 (v1 脚本对单文件误加尾斜杠 → rc=23)
MAT_SRC="/mnt/d/WindTunnelSuite/WindTunnel3D/flow3d_result.mat"
MAT_REL="archive/flow3d_result.mat"
if [ -f "$MAT_SRC" ]; then
  b_src=$(stat -c%s "$MAT_SRC")
  $SSH "$NAS" "mkdir -p '$VAULT/archive'"
  rsync -a --partial -e "$SSH" "$MAT_SRC" "$NAS:$VAULT/$MAT_REL" >/dev/null 2>&1
  b_r=$($SSH "$NAS" "stat -c%s '$VAULT/$MAT_REL'" 2>/dev/null)
  if [ "$b_src" = "$b_r" ]; then
    echo "$MAT_REL|PASS|files=1|bytes=$b_src" >> "$OUT"; pass=$((pass+1)); total=$((total+1))
    touch "$MAT_SRC.migrated_to_nas"
  else
    echo "$MAT_REL|FAIL|src=1/$b_src nas=1/$b_r" >> "$OUT"; total=$((total+1))
  fi
fi

echo "# RESULT: $pass/$total PASS" >> "$OUT"
cat "$OUT"
