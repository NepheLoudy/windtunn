#!/usr/bin/env bash
# T0-v2b: 填实镖头几何启动器 (scp 部署, 不走内联 heredoc — 10-30 引号地狱教训)
set +e; set +u
source "$HOME/OpenFOAM-12/etc/bashrc" 2>/dev/null
unset DISPLAY; export HWLOC_COMPONENTS=-gl
set -u
# T0 优先: 若 T1 引擎在跑, 先停 (chain 会在 T0 完成后自动重启 T1)
# 子进程一并击杀 (孤儿 snappy 污染求解教训 10-30): 引擎/求解器/网格器全杀
pkill -f "run_sweep_v[2]" 2>/dev/null; sleep 1
pkill -f "foamRu[n]" 2>/dev/null
pkill -f "snappyHexMes[h]" 2>/dev/null
pkill -f "blockMes[h]" 2>/dev/null
pkill -f "reconstructPa[r]" 2>/dev/null
pkill -f "decomposePa[r]" 2>/dev/null
sleep 3
ROOT=$HOME/sweep_t0v2; NP=14
rm -rf "$ROOT"
mkdir -p "$ROOT"
cd "$HOME/windtunnel/openfoam/airframe-sweep" || exit 1
export OUT_CSV="$ROOT/t0_table.csv"
export SWEEP_V="15 20 25 30"
export SWEEP_ALPHA="-15 -12.5 -10 -7.5 -5 -2.5 0 2.5 5 7.5 10 12.5 15"
export SWEEP_BETA="-15 -10 -5 0 5 10 15"
export SURF_LEVEL=5 FIN_LEVEL=7 BOX_LEVEL=3
export GEOM_DIR="$PWD/cad/v1/cfd_geom_multi_parallel"
setsid nohup ./run_sweep_v2.sh "$ROOT" "$NP" > "$ROOT/sweep.log" 2>&1 < /dev/null &
echo "T0-v2b launched $(date)"
