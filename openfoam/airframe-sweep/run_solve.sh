#!/usr/bin/env bash
# 对已建好网格的 case 只跑求解 (decompose + foamRun + reconstruct)
#   usage: run_solve.sh <case_dir> [nproc] [endTime]
set -euo pipefail

CASE=$(cd "${1:?usage: run_solve.sh <case> [nproc] [endTime]}" && pwd)
NP=${2:-8}
ET=${3:-}

set +u
set +e
source /opt/openfoam12/etc/bashrc
set -eu
cd "$CASE"

if [ -n "$ET" ]; then
  sed -i "s/^endTime.*/endTime         $ET;/" system/controlDict
fi
sed -i "s/^numberOfSubdomains .*/numberOfSubdomains $NP;/" system/decomposeParDict

decomposePar -force > log.decomposePar 2>&1
mpirun --allow-run-as-root --oversubscribe -np "$NP" foamRun -parallel > log.foamRun 2>&1 || {
  echo "foamRun FAILED"; tail -30 log.foamRun; exit 1; }
reconstructPar > log.reconstructPar 2>&1 || true
echo "solved: $CASE ($(grep -c '^Time = ' log.foamRun) steps)"
