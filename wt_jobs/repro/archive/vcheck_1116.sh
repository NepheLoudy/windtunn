#!/usr/bin/env bash
# V23.55 插值合法性硬核查验 — 三例直接求解 (23.0/23.55/24.0) LBM 侧内部对拍
# Re 一致口径: NU ∝ 1/V (nu(23.0)=0.02*20/23 等), V_LBM = 0.05*V/20
set -e
cd ~/fluidx3d_v3/FluidX3D-master/bin
mkdir -p out

run_case() {
  local TAG=$1 V_LBM=$2 NU=$3 STEPS=${4:-300000}
  local CSV=out/forces_${TAG}.csv
  # 断点续跑: 末行 t==STEPS 则跳过
  if [ -f "$CSV" ]; then
    local last=$(tail -1 "$CSV" | cut -d, -f1)
    [ "$last" = "$STEPS" ] && { echo "[$TAG] already done (t=$last), skip"; return 0; }
  fi
  echo "=== run $TAG V_LBM=$V_LBM NU=$NU STEPS=$STEPS start $(date +%H:%M:%S) ==="
  GEOM_DIR=$HOME/windtunnel/openfoam/airframe-sweep/cad/v1/cfd_geom_multi_parallel \
  ALPHA=0 BETA=0 NX=440 V_LBM=$V_LBM NU=$NU STEPS=$STEPS TAG=$TAG \
  setsid nohup ./FluidX3D > vcheck_${TAG}.log 2>&1
  local rc=$?
  echo "=== $TAG done rc=$rc $(date +%H:%M:%S) ==="
  return $rc
}

run_case _vcheck_v23   0.057500 0.017390 300000
run_case _vcheck_v2355 0.057875 0.016985 300000
run_case _vcheck_v24   0.060000 0.016667 300000
echo "=== VCHECK ALL RUNS DONE $(date) ==="
