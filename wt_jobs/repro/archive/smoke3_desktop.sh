#!/usr/bin/env bash
# 本机(桌面 WSL) T0 档单例冒烟 — 探针用常规点 (20,5,0), 不用 a0_b0 (SIGFPE 家族)
set +e          # bashrc 的 pop_var_context 噪音会杀 set -e 脚本 (老坑)
source /opt/openfoam12/etc/bashrc
set -e
unset DISPLAY; export HWLOC_COMPONENTS=-gl

A=/mnt/d/WindTunnelSuite/openfoam/airframe-sweep
S=/mnt/d/WindTunnelSuite/wt_jobs/tmp/smoke3
export GEOM_DIR=$A/cad/v1/cfd_geom_multi_parallel
export SURF_LEVEL=5 FIN_LEVEL=7 BOX_LEVEL=3

rm -rf "$S"
cd "$A"
echo "[1/5] make_case $(date +%H:%M:%S)"
bash make_case.sh 20 5 0 "$S" > /dev/null

echo "[2/5] blockMesh"
( cd "$S" && blockMesh > log.blockMesh 2>&1 )

echo "[3/5] snappyHexMesh"
( cd "$S" && snappyHexMesh -overwrite > log.snappy 2>&1 )
grep -E 'Finished meshing' "$S/log.snappy" | tail -1

echo "[4/5] run_solve np=8 ET=600"
cd "$A"
bash run_solve.sh "$S" 8 600 > /tmp/smoke3_solve.log 2>&1

echo "[5/5] post_process"
python3 post_process.py "$S" \
  --mass-props "$A/cad/v1/cfd/mass_properties.json" \
  --json "$S/results.json" --out "$S/smoke3_table.csv" 2>&1 | tail -6

echo "=== SMOKE3 COMPLETE $(date +%H:%M:%S) ==="
tail -1 "$S/smoke3_table.csv"
