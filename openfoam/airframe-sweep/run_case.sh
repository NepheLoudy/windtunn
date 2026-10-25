#!/usr/bin/env bash
# 跑一个已生成的扫气 case (WSL2 + OpenFOAM v12, 并行)
#   usage: run_case.sh <case_dir> [nproc]
set -euo pipefail

CASE=$(cd "${1:?usage: run_case.sh <case_dir> [nproc]}" && pwd)
NP=${2:-12}

# v12 环境: 自适应探测 (apt /opt → 源码编译 ~/OpenFOAM-12 → /usr/lib), 或 FOAM_ENV 覆盖
set +u
FOAM_ENV=${FOAM_ENV:-}
if [ -z "$FOAM_ENV" ] && [ -f /opt/openfoam12/etc/bashrc ]; then FOAM_ENV=/opt/openfoam12/etc/bashrc; fi
if [ -z "$FOAM_ENV" ] && [ -f "$HOME/OpenFOAM-12/etc/bashrc" ]; then FOAM_ENV="$HOME/OpenFOAM-12/etc/bashrc"; fi
if [ -z "$FOAM_ENV" ] && [ -f /usr/lib/openfoam/openfoam12/etc/bashrc ]; then FOAM_ENV=/usr/lib/openfoam/openfoam12/etc/bashrc; fi
[ -n "$FOAM_ENV" ] || { echo "找不到 OpenFOAM v12 bashrc (设 FOAM_ENV 指定)"; exit 1; }
# shellcheck disable=SC1090
source "$FOAM_ENV"
set -u
cd "$CASE"

echo "[1/6] blockMesh"
blockMesh > log.blockMesh 2>&1 || { echo "blockMesh FAILED"; tail -20 log.blockMesh; exit 1; }

echo "[2/6] snappyHexMesh"
snappyHexMesh -overwrite > log.snappyHexMesh 2>&1 || { echo "snappy FAILED"; tail -30 log.snappyHexMesh; exit 1; }

echo "[3/6] checkMesh"
checkMesh > log.checkMesh 2>&1 || true
grep -E "Mesh OK|Failed|cells:" log.checkMesh | tail -3

echo "[4/6] decomposePar ($NP)"
# 分区数必须与 mpirun -np 一致, 按 NP 覆盖 decomposeParDict
sed -i "s/^numberOfSubdomains .*/numberOfSubdomains $NP;/" system/decomposeParDict
rm -rf processor*
decomposePar -force > log.decomposePar 2>&1

echo "[5/6] foamRun -parallel ($NP)"
mpirun --allow-run-as-root --oversubscribe -np "$NP" foamRun -parallel > log.foamRun 2>&1 || {
  echo "foamRun FAILED"; tail -40 log.foamRun; exit 1; }

echo "[6/6] reconstructPar"
reconstructPar > log.reconstructPar 2>&1 || true

echo "--- converged? (residual tail) ---"
grep -E "^Time = |Solving for Ux, Initial residual" log.foamRun | tail -8
echo "DONE: $CASE"
