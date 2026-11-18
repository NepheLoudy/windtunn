#!/usr/bin/env bash
# T1 三轮发车 — 根因: 前轮 setsid 裸环境启动, blockMesh 未找到命令 (OpenFOAM env 未传导)
# 修法: 脚本内显式 source bashrc (继承 v25_finish/chain 先例), env 全链传导
set +u
source "$HOME/OpenFOAM-12/etc/bashrc"
unset DISPLAY; export HWLOC_COMPONENTS=-gl
cd "$HOME/windtunnel/openfoam/airframe-sweep" || exit 1
export OUT_CSV="$HOME/sweep_t1/t1_table.csv"
export SWEEP_V="20 21 22 23 24 25"
export SWEEP_ALPHA="-15 -12.5 -10 -7.5 -5 -2.5 0 2.5 5 7.5 10 12.5 15"
export SWEEP_BETA="-15 -10 -5 0 5 10 15"
export SURF_LEVEL=6 FIN_LEVEL=8 BOX_LEVEL=3
export GEOM_DIR="$PWD/cad/v1/cfd_geom_multi_parallel"
# 自检: blockMesh 必须可达才发车
command -v blockMesh >/dev/null || { echo "FATAL: blockMesh not in PATH — bashrc 未生效"; exit 1; }
echo "T1 r3 launch $(date) — blockMesh OK: $(command -v blockMesh)"
setsid nohup ./run_sweep_v2.sh "$HOME/sweep_t1" 14 >> "$HOME/sweep_t1/sweep.log" 2>&1 < /dev/null &
sleep 3
pgrep -cf 'run_sweep_v[2]' >/dev/null && echo T1_R3_ALIVE || echo T1_R3_DEAD
