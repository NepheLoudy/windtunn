#!/usr/bin/env bash
# T1 高保真档启动器 (算力节点)  — 用文件而非内联引号, 避免嵌套转义
set +e
set +u
source ~/OpenFOAM-12/etc/bashrc 2>/dev/null
unset DISPLAY
export HWLOC_COMPONENTS=-gl
set -u

ROOT=${1:-$HOME/sweep_t1}
NP=${2:-14}
SURF=${SURF_LEVEL:-6}
FIN=${FIN_LEVEL:-8}
BOX=${BOX_LEVEL:-3}

pkill -9 -f run_sweep_v2 2>/dev/null
pkill -9 -f foamRun 2>/dev/null
sleep 2
rm -rf "$ROOT"
mkdir -p "$ROOT"

cd "$HOME/windtunnel/openfoam/airframe-sweep" || exit 1
export OUT_CSV="$ROOT/t1_table.csv"
export SWEEP_V="15 20 25 30"
export SWEEP_ALPHA="-15 -12.5 -10 -7.5 -5 -2.5 0 2.5 5 7.5 10 12.5 15"
export SWEEP_BETA="-15 -10 -5 0 5 10 15"
export SURF_LEVEL="$SURF"
export FIN_LEVEL="$FIN"
export BOX_LEVEL="$BOX"
export GEOM_DIR="$PWD/cad/v1/cfd_geom_multi"

setsid nohup ./run_sweep_v2.sh "$ROOT" "$NP" > "$ROOT/sweep.log" 2>&1 < /dev/null &
echo "T1 launched: root=$ROOT np=$NP surf=$SURF fin=$FIN"
