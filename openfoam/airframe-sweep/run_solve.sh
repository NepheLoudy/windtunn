#!/usr/bin/env bash
# 对已建好网格的 case 只跑求解 (decompose + foamRun + reconstruct)
#   usage: run_solve.sh <case_dir> [nproc] [endTime]
set -euo pipefail

CASE=$(cd "${1:?usage: run_solve.sh <case> [nproc] [endTime]}" && pwd)
NP=${2:-8}
ET=${3:-}

# ---- OpenFOAM v12 环境自适应 (apt /opt → 源码 ~/OpenFOAM-12 → /usr/lib) ----
# set +e/+u 包住 source: bashrc 噪音会杀死 set -e 脚本; 未定义变量会杀死 set -u 脚本
set +e
set +u
if [ -f /opt/openfoam12/etc/bashrc ]; then FOAM_ENV=/opt/openfoam12/etc/bashrc
elif [ -f "$HOME/OpenFOAM-12/etc/bashrc" ]; then FOAM_ENV="$HOME/OpenFOAM-12/etc/bashrc"
elif [ -f /usr/lib/openfoam/openfoam12/etc/bashrc ]; then FOAM_ENV=/usr/lib/openfoam/openfoam12/etc/bashrc
else FOAM_ENV=""; fi
[ -n "$FOAM_ENV" ] || { echo "找不到 OpenFOAM v12 bashrc (设 FOAM_ENV)"; exit 1; }
# shellcheck disable=SC1090
source "$FOAM_ENV" 2>/dev/null
set -eu

# ---- MPI 启动参数自适应 (按 --version 输出内容判断) ----
# OpenMPI: --allow-run-as-root --oversubscribe
# MPICH  : -iface lo  (无头机校园网拦非 loopback rank 握手; 必须配 HWLOC_COMPONENTS=-gl)
if mpirun --version 2>&1 | grep -q "Open MPI"; then
  MPI_ARGS="--allow-run-as-root --oversubscribe"
else
  MPI_ARGS="-iface lo"
fi
# 无头机: MPICH 的 hwloc_gl 插件在 MPI_Init 里 XOpenDisplay 会挂死
unset DISPLAY
export HWLOC_COMPONENTS=-gl

cd "$CASE"

if [ -n "$ET" ]; then
  sed -i "s/^endTime.*/endTime         $ET;/" system/controlDict
  # T1 档 (SURF_LEVEL>=6): endTime 上限抬到 3000, 收敛由 residualControl 1e-5 判停 (roadmap 对齐)
  if [ "${SURF_LEVEL:-0}" -ge 6 ]; then
    sed -i "s/^endTime.*/endTime         3000;/" system/controlDict
  fi
fi
sed -i "s/^numberOfSubdomains .*/numberOfSubdomains $NP;/" system/decomposeParDict

decomposePar -force > log.decomposePar 2>&1
mpirun $MPI_ARGS -np "$NP" foamRun -parallel > log.foamRun 2>&1 || {
  echo "foamRun FAILED"; tail -30 log.foamRun; exit 1; }
reconstructPar > log.reconstructPar 2>&1 || true
echo "solved: $CASE ($(grep -c '^Time = ' log.foamRun) steps)"
